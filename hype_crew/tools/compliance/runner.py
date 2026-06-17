"""Compliance gate orchestrator: runs all 4 layers in sequence, returns final verdict.

Flow:
    L1 CLIP consistency  → fail-fast if CLIP FAIL
    L2 OCR forbidden     → fail-fast if forbidden text
    L3 Aesthetic score   → continue regardless of verdict
    L4 LLM judge         → ONLY if any prior layer NEEDS_REVIEW or mixed (cost guard)

Final verdict (strict):
    PASS        : all layers PASS (or LLM judge PASS in gray zone)
    NEEDS_REVIEW: at least one NEEDS_REVIEW + no FAIL
    FAIL        : any layer FAIL

Persists results to persona_assets columns:
    clip_persona_similarity, ocr_text, ocr_flagged, aesthetic_score,
    llm_judge_verdict, llm_judge_reasoning, compliance_passed
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from ..supabase_client import make_supabase
from .clip_consistency import check_consistency, ClipConsistencyResult
from .ocr_check import check_ocr, OcrResult
from .aesthetic_score import score_aesthetic, AestheticResult
from .llm_judge import judge_image, LlmJudgeResult


@dataclass
class ComplianceReport:
    clip: ClipConsistencyResult | None
    ocr: OcrResult | None
    aesthetic: AestheticResult | None
    llm: LlmJudgeResult | None
    final_verdict: str          # 'PASS' | 'NEEDS_REVIEW' | 'FAIL'
    final_reason: str
    layers_run: list[str]


def _final_verdict(report: ComplianceReport) -> tuple[str, str]:
    layers = []
    needs_review = []
    fails = []

    if report.clip is not None:
        layers.append(("clip", report.clip.verdict))
    if report.ocr is not None:
        layers.append(("ocr", report.ocr.verdict))
    if report.aesthetic is not None:
        layers.append(("aesthetic", report.aesthetic.verdict))
    if report.llm is not None:
        layers.append(("llm", report.llm.verdict))

    for name, v in layers:
        if v == "FAIL":
            fails.append(name)
        elif v == "NEEDS_REVIEW":
            needs_review.append(name)

    if fails:
        return "FAIL", f"failed_layers={fails}"
    if needs_review:
        return "NEEDS_REVIEW", f"needs_review_layers={needs_review}"
    return "PASS", "all_layers_pass"


async def _download_image_bytes(url: str) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(url)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
    return resp.content, content_type


async def run_compliance(
    *,
    image_bytes: bytes,
    image_mime: str,
    persona_id: str,
    persona_asset_id: str | None = None,
    skip_llm: bool = False,
    skip_ocr: bool | None = None,
    visual_mode: str = "face",  # Phase 25.G — face | conceptual | hybrid
) -> ComplianceReport:
    """Run 4-layer compliance gate against a generated image.

    OCR layer (easyocr) is RAM-heavy (~1.5GB peak) and runs alongside CLIP (~2GB).
    On low-memory hosts (e.g. Hetzner 7.6GB VPS with concurrent contentfactory),
    concurrent load triggers OOM. Set HYPE_SKIP_OCR=true to disable. Default: skip
    OCR (it rarely fires for Cansu-style lifestyle images without rendered text).

    Phase 25.G — mode-aware CLIP gating:
      face       → full check (anchor cosine ≥0.55 PASS / 0.50-0.55 NEEDS_REVIEW)
      conceptual → CLIP SKIPPED (no persona face expected in image)
      hybrid     → CLIP lenient (small overlay; threshold lowered to 0.40)
    """
    import os

    if skip_ocr is None:
        skip_ocr = os.environ.get("HYPE_SKIP_OCR", "true").lower() in ("1", "true", "yes")

    layers_run: list[str] = []

    # L1: CLIP consistency — mode-aware (Phase 25.G)
    if visual_mode == "conceptual":
        # SKIPPED: no persona face expected in image (n8n Content Factory style).
        # Synthesized result keeps downstream report shape consistent. Use a
        # neutral score=0.0 + threshold=0.0 so any consumer that reads min/max
        # later doesn't break; the verdict='SKIPPED' is the only signal callers
        # should branch on.
        clip_result = ClipConsistencyResult(
            score=0.0, min_score=0.0, max_score=0.0, anchor_count=0,
            verdict="SKIPPED", threshold=0.0,
        )
        layers_run.append("clip:skip")
        logger.info("L1 CLIP: SKIPPED (visual_mode=conceptual)")
    else:
        # Hybrid mode uses a looser CLIP floor since Cansu is a small overlay
        # rather than the dominant subject — full-frame cosine will be lower
        # by construction.
        clip_kwargs = {"threshold": 0.40} if visual_mode == "hybrid" else {}
        clip_result = await check_consistency(
            generated_image_bytes=image_bytes,
            persona_id=persona_id,
            **clip_kwargs,
        )
        layers_run.append("clip")
        logger.info(
            f"L1 CLIP: score={clip_result.score:.3f} verdict={clip_result.verdict} "
            f"(min={clip_result.min_score:.3f}, max={clip_result.max_score:.3f}, "
            f"anchors={clip_result.anchor_count}, mode={visual_mode})"
        )

    # L2: OCR (optional — skipped by default on memory-constrained hosts)
    ocr_result = None
    if not skip_ocr:
        ocr_result = check_ocr(image_bytes)
        layers_run.append("ocr")
        logger.info(
            f"L2 OCR: text='{ocr_result.text[:80]}' "
            f"detections={ocr_result.detection_count} "
            f"forbidden={ocr_result.forbidden_matches} verdict={ocr_result.verdict}"
        )
    else:
        logger.info("L2 OCR: SKIPPED (HYPE_SKIP_OCR=true)")

    # L3: Aesthetic
    aesthetic_result = score_aesthetic(image_bytes)
    layers_run.append("aesthetic")
    logger.info(
        f"L3 Aesthetic: raw={aesthetic_result.raw_score:.2f}/10 "
        f"norm={aesthetic_result.normalized:.3f} verdict={aesthetic_result.verdict}"
    )

    # Tentative verdict before LLM
    tentative = ComplianceReport(
        clip=clip_result, ocr=ocr_result, aesthetic=aesthetic_result,
        llm=None, final_verdict="", final_reason="", layers_run=list(layers_run),
    )
    pre_verdict, pre_reason = _final_verdict(tentative)

    # L4: LLM judge — runs when:
    #   (a) upstream NEEDS_REVIEW (classic gray zone), OR
    #   (b) ONLY CLIP failed (CLIP unreliable for scene-different comparisons; LLM
    #       can verify face identity directly from anchor reference and image).
    # OCR FAIL = hard fail, no LLM. Aesthetic FAIL alone → trust the score.
    llm_result: LlmJudgeResult | None = None
    ocr_failed = ocr_result is not None and ocr_result.verdict == "FAIL"
    only_clip_failed = (
        clip_result.verdict == "FAIL"
        and not ocr_failed
        and aesthetic_result.verdict != "FAIL"
    )
    should_run_llm = (
        not skip_llm
        and (pre_verdict == "NEEDS_REVIEW" or only_clip_failed)
    )
    if should_run_llm:
        ocr_summary = (
            f"OCR: text='{ocr_result.text[:60]}' "
            f"forbidden={ocr_result.forbidden_matches} ({ocr_result.verdict})\n"
            if ocr_result is not None
            else "OCR: SKIPPED\n"
        )
        context = (
            f"CLIP: {clip_result.score:.3f} ({clip_result.verdict}), "
            f"anchors={clip_result.anchor_count}\n"
            f"{ocr_summary}"
            f"Aesthetic: {aesthetic_result.normalized:.3f} "
            f"(raw {aesthetic_result.raw_score:.2f}/10, {aesthetic_result.verdict})"
        )
        try:
            llm_result = await judge_image(
                image_bytes=image_bytes,
                image_mime=image_mime,
                context_summary=context,
                # Phase 42.B-12B — let the judge see visual_mode so it
                # picks the right prompt (face / conceptual / hybrid).
                visual_mode=visual_mode,
            )
            layers_run.append("llm")
            logger.info(
                f"L4 LLM: verdict={llm_result.verdict} "
                f"reasoning='{llm_result.reasoning[:100]}' "
                f"tells={llm_result.tells} cost=${llm_result.cost_usd:.4f}"
            )
        except Exception as e:
            logger.warning(f"L4 LLM failed: {e} — using tentative verdict")

    report = ComplianceReport(
        clip=clip_result,
        ocr=ocr_result,
        aesthetic=aesthetic_result,
        llm=llm_result,
        final_verdict="",
        final_reason="",
        layers_run=layers_run,
    )
    final_verdict, final_reason = _final_verdict(report)
    report.final_verdict = final_verdict
    report.final_reason = final_reason

    # Persist to persona_assets if asset_id provided
    if persona_asset_id:
        await _persist_report(persona_asset_id, report)

    return report


async def _persist_report(asset_id: str, report: ComplianceReport) -> None:
    sb = make_supabase()
    payload: dict[str, Any] = {}
    if report.clip:
        payload["clip_persona_similarity"] = round(report.clip.score, 4)
    if report.ocr:
        payload["ocr_text"] = report.ocr.text[:2000] if report.ocr.text else None
        payload["ocr_flagged"] = bool(report.ocr.forbidden_matches)
    if report.aesthetic:
        payload["aesthetic_score"] = round(report.aesthetic.normalized, 4)
    if report.llm:
        payload["llm_judge_verdict"] = report.llm.verdict
        payload["llm_judge_reasoning"] = report.llm.reasoning[:2000] if report.llm.reasoning else None
    payload["compliance_passed"] = report.final_verdict == "PASS"
    payload["status"] = (
        "compliance_passed" if report.final_verdict == "PASS"
        else "compliance_failed" if report.final_verdict == "FAIL"
        else "generated"  # NEEDS_REVIEW stays as 'generated' so user can decide
    )
    sb.table("persona_assets").update(payload).eq("id", asset_id).execute()

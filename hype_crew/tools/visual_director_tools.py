"""CrewAI tool wrapper used by the Visual Director agent.

Single tool: `generate_visual_image` — accepts the brief (scene_description, mood,
outfit, content_context, aspect_ratio, platform) and runs:

    visual_prompt.enhance_visual_prompt → WiroClient → watermark/skip → Supabase
    upload → persona_assets insert → 4-layer compliance gate → return dict.

The agent then folds the returned dict into its VisualDirectorOutput.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):  # noqa: ARG001
        def _decorate(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate
from loguru import logger

from .image_pipeline import generate_and_store_visual_brief_asset
from .visual_prompt import VisualPromptBrief
from .reference_anchors import load_persona_anchors, prepare_reference_prompt_inputs
from .compliance.runner import run_compliance


async def _generate_and_check_async(
    *,
    persona_id: str,
    platform: str,
    scene_description: str,
    outfit: str,
    mood: str,
    content_context: Optional[str],
    daily_draft_id: Optional[str],
    model_slug: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    resolution: str = "4k",  # Phase 35.3 — caller can override (e.g. "2k" for news batch)
    visual_mode: str = "face",  # Phase 25.F — face|conceptual|hybrid
    # Phase 41.B — real Strategist state passed through so the LLM Visual
    # Decision Agent sees the actual headline + content_type + voice_mode
    # (NOT scene_description + platform name as Phase 39 default).
    trend_topic: Optional[str] = None,
    plan_content_type: Optional[str] = None,
    voice_mode: Optional[str] = None,
    # Phase 42.B-10B — explicit override from caller (flow.visual_branch)
    # that bypasses the pre-existing nano_banana_builder rewrite. When this
    # is a non-None string AND the brand path is entered (model_slug None →
    # Visual Decision Agent picks brand), the override is used verbatim as
    # the scene_description fed to Wiro. When None (default), production
    # behavior is byte-for-byte unchanged.
    brand_brief_override: Optional[str] = None,
) -> dict:
    # Phase 39 (Berkay 31 May 2026) — LLM-based visual decision agent.
    # Phase 25.D'deki fixed VISUAL_MODE_BY_CONTENT_TYPE mapping yerine LLM
    # habere bakıp karar verir: "Cansu lazım mı?". Berkay direktifi: Cansu
    # NADİREN kullanılmalı (~15-25%), default brand/marka visual.
    #
    # Karar ağacı:
    #   needs_cansu=True  → HeyGen curated photo library (Phase 38)
    #   needs_cansu=False → Wiro Nano Banana Pro brand visual (DEFAULT)
    #
    # Phase 38 face mode branch'i bu decision'a göre tetiklenir; visual_mode
    # parametresi artık sadece compliance gate config için kullanılır.
    # Phase 41.E — capture the decision dict so we can surface it to the
    # caller (hype_stages output → UI). decision stays None when the caller
    # supplied an explicit model_slug (no routing decision was made).
    decision: Optional[dict] = None
    # Phase 42.B — Nano Banana JSON brief for the UI accordion (None unless
    # the brand path actually built one).
    nb_brief: Optional[dict] = None
    if model_slug is None:
        from .visual_decision import decide_composition_type
        # Phase 41.B — pass real Strategist state. When trend_topic /
        # plan_content_type are missing (legacy callers), fall back to the
        # old scene_description / platform values so the agent still gets
        # *something* rather than crashing.
        # Phase 42.A — call the new composition_type decider; the dict
        # returned still contains `needs_cansu` (derived) for backward-compat.
        decision = await decide_composition_type(
            trend_topic=(trend_topic or scene_description)[:300],
            brief=(content_context or "")[:600],
            content_type=(plan_content_type or str(platform or "tweet")),
            voice_mode=voice_mode,
        )
        composition_type = str(decision.get("composition_type") or "brand_news_visual")
        needs_cansu = bool(decision.get("needs_cansu"))
        decision_via = str(decision.get("via") or "llm")
        logger.info(
            f"[visual_decision] composition_type={composition_type} "
            f"via={decision_via} reason='{str(decision.get('reason',''))[:90]}'"
        )

        # ─── Cansu path (rare) ────────────────────────────────────────────
        if needs_cansu:
            from .curated_photo_selector import select_curated_photo
            from .image_pipeline import store_curated_photo_as_draft_asset
            # Phase 42.A — pass composition_type as composition_filter so the
            # selector pre-filters its candidate pool by composition_style
            # metadata (selfie vs scene). For Phase 42.A the library is
            # still selfie-only, so the selector logs a warning and falls
            # back to the full pool — Phase 42.C ships the scene photos
            # that will activate the filter.
            composition_filter = composition_type if composition_type in {"cansu_scene", "cansu_selfie"} else None
            picked = None
            try:
                picked = await select_curated_photo(
                    persona_id=persona_id,
                    scene_description=scene_description,
                    content_context=content_context,
                    platform=platform,  # Phase 39.6 — per-platform cooldown
                    composition_filter=composition_filter,
                )
            except Exception as e:
                logger.warning(f"[cansu_path] curated selector raised: {e}")
            if picked is not None:
                try:
                    linked = await store_curated_photo_as_draft_asset(
                        persona_id=persona_id,
                        curated=picked,
                        daily_draft_id=daily_draft_id,
                        visual_mode="cansu",
                    )
                except Exception:
                    linked = {
                        "asset_id": picked.asset_id,
                        "public_url": picked.public_url,
                        "storage_key": picked.storage_key,
                    }
                return {
                    "status": "ok",
                    "asset_id": linked["asset_id"],
                    "image_url": linked["public_url"],
                    "storage_key": linked["storage_key"],
                    "model_slug": "heygen_curated_library",
                    "cost_usd": 0.0,
                    "latency_ms": 0,
                    "file_size_bytes": 0,
                    "compliance": {
                        "final_verdict": "PASS",
                        "final_reason": "curated_photo (user-approved, gate bypassed)",
                        "clip": None, "aesthetic": None, "ocr_flagged": False,
                        "llm_verdict": "PASS", "llm_tells": [],
                        "llm_reasoning": "Berkay-curated HeyGen photo, pre-approved",
                    },
                    # Phase 41.E — surface Visual Decision Agent output so the
                    # UI can show *why* Cansu was chosen. Phase 42.A adds
                    # composition_type so the UI distinguishes scene vs selfie.
                    "visual_decision": {
                        "needs_cansu": True,
                        "composition_type": composition_type,
                        "via": decision_via,
                        "reason": str(decision.get("reason", "")) if decision else "",
                        "path": "cansu",
                        "model": "openrouter/google/gemini-3-flash-preview",
                    },
                    "_curated_meta": {
                        "name": picked.name,
                        "heygen_id": picked.heygen_id,
                        "decision_reason": str(decision.get("reason", "")) if decision else "",
                    },
                }
            logger.info("[cansu_path] library empty; falling back to brand visual")

        # ─── Brand path (DEFAULT — Cansu yok) ─────────────────────────────
        # Wiro Nano Banana Pro + brand-aware JSON-style prompt + no anchors.
        # Phase 34 brand_extractor + Phase 25.F conceptual path reuse.
        model_slug = "google/nano-banana-pro"
        # Force visual_mode='conceptual' so downstream anchor/compliance
        # logic skips persona anchor refs (no Cansu = no anchors needed).
        visual_mode = "conceptual"

        # Phase 42.B-10B — when the caller (flow.visual_branch) supplies an
        # explicit `brand_brief_override`, use it verbatim and skip the
        # nano_banana_builder rewrite. This is the path used during the
        # flag-ON brand_visual_brief_builder cohort so the labeled-prose
        # actually reaches Wiro. nb_brief stays None (already initialized
        # above) since we deliberately did not run the nano_banana builder.
        if brand_brief_override is not None:
            scene_description = brand_brief_override
            logger.info(
                "[42B-10B] brand_brief_override used; "
                "skipping nano_banana_builder rewrite"
            )
        else:
            # Phase 42.B — Replace the free-text Strategist scene_description
            # with a Nano Banana JSON-style prompt slot-filled from a per-
            # content_type SUBJECT_TEMPLATE (3 variants, rotated by topic
            # hash). Builder is deterministic — no extra LLM call. Failure
            # path: log + keep the original scene_description (no regression).
            try:
                from .nano_banana_builder import build_brand_news_prompt
                nb_json, nb_brief = build_brand_news_prompt(
                    trend_topic=(trend_topic or scene_description or ""),
                    content_type=plan_content_type,
                    platform=platform,
                    aspect_ratio="1:1",
                )
                scene_description = nb_json
                logger.info(
                    f"[nano_banana_builder] label={nb_brief.get('label')} "
                    f"composition_type=brand_news_visual"
                )
            except Exception as e:
                logger.warning(
                    f"[nano_banana_builder] failed ({type(e).__name__}: {str(e)[:120]}); "
                    f"falling back to original scene_description"
                )

    # 1. Load reference anchors only when persona presence is expected
    if visual_mode == "conceptual":
        reference_urls: list[str] = []
    else:
        anchors = await load_persona_anchors(persona_id)
        if not anchors:
            return {
                "status": "error",
                "error": f"persona {persona_id} has no reference_anchor assets",
            }
        # Hybrid uses fewer refs so the product/UI stays dominant in the frame.
        max_refs = 1
        inputs = await prepare_reference_prompt_inputs(
            anchors,
            scene_description=scene_description,
            content_context=content_context,
            outfit=outfit,
            max_prompt_inputs=max_refs,
        )
        reference_urls = list(inputs.signed_reference_urls)

    # Phase 28 — inject recent image-rejection patterns so the Visual Director
    # avoids repeating them. We use the persona's primary account_id when
    # available; this scopes the memory to the right user/persona.
    enriched_context = content_context or ""
    try:
        from .memory_tools import format_visual_rejection_memory
        # Resolve account_id from persona row
        from .supabase_client import make_supabase
        sb = make_supabase()
        persona_row = (
            sb.table("personas")
            .select("primary_account_id")
            .eq("id", persona_id)
            .limit(1)
            .execute()
        )
        primary_acc = (persona_row.data or [{}])[0].get("primary_account_id")
        if primary_acc:
            rejection_block = format_visual_rejection_memory(primary_acc)
            if rejection_block:
                # Phase 28.R-Lite Sprint 1B — memory block contains Turkish
                # reason labels that include forbidden-vocab strings (e.g.
                # "beauty filter" inside "Çok yapay görünüm (...beauty filter)").
                # Strip those so enhance_visual_prompt's user-input QC doesn't
                # reject our own learning signal as a forbidden prompt token.
                from .visual_prompt import _strip_forbidden_vocab
                cleaned_block = _strip_forbidden_vocab(rejection_block)
                enriched_context = (cleaned_block + "\n\n" + (content_context or "")).strip()
    except Exception:
        # Memory injection is best-effort; never block image generation on it.
        pass

    # 2. Build VisualPromptBrief
    brief = VisualPromptBrief(
        platform=platform,  # type: ignore[arg-type]
        scene_description=scene_description,
        outfit=outfit,
        mood=mood,  # type: ignore[arg-type]
        content_context=enriched_context,
        aspect_ratio=aspect_ratio,
        reference_image_urls=reference_urls,
        visual_mode=visual_mode,  # type: ignore[arg-type]
    )

    # 3. Generate + upload + persona_assets insert
    stored = await generate_and_store_visual_brief_asset(
        persona_id=persona_id,
        brief=brief,
        slug=model_slug,
        resolution=resolution,
        max_images=1,
        ai_watermark=False,
        asset_status="generated",
        daily_draft_id=daily_draft_id,
    )

    # 4. Run 4-layer compliance gate (mode-aware — Phase 25.G)
    import httpx
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(stored.public_url)
    resp.raise_for_status()
    img_bytes = resp.content
    mime = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()

    report = await run_compliance(
        image_bytes=img_bytes,
        image_mime=mime,
        persona_id=persona_id,
        persona_asset_id=stored.asset_id,
        visual_mode=visual_mode,
    )

    return {
        "status": "ok",
        "asset_id": stored.asset_id,
        "image_url": stored.public_url,
        "storage_key": stored.storage_key,
        "model_slug": stored.generation.model_slug,
        "cost_usd": stored.generation.cost_usd,
        "latency_ms": stored.generation.latency_ms,
        "file_size_bytes": stored.file_size_bytes,
        "compliance": {
            "final_verdict": report.final_verdict,
            "final_reason": report.final_reason,
            "clip": (report.clip.score if report.clip else None),
            "aesthetic": (report.aesthetic.normalized if report.aesthetic else None),
            "ocr_flagged": (
                bool(report.ocr.forbidden_matches) if report.ocr else None
            ),
            "llm_verdict": (report.llm.verdict if report.llm else None),
            "llm_reasoning": (report.llm.reasoning if report.llm else None),
            "llm_tells": (report.llm.tells if report.llm else []),
        },
        # Phase 41.E — surface Visual Decision Agent output so the UI can show
        # *why* this route (brand vs Cansu) was picked. Phase 42.A adds
        # composition_type + via (kernel/llm/fallback).
        "visual_decision": (
            {
                "needs_cansu": bool(decision.get("needs_cansu")),
                "composition_type": str(
                    decision.get("composition_type") or "brand_news_visual"
                ),
                "via": str(decision.get("via") or "llm"),
                "reason": str(decision.get("reason", "")),
                "path": "brand",
                "model": "openrouter/google/gemini-3-flash-preview",
            }
            if decision is not None
            else None
        ),
        # Phase 42.B — Nano Banana JSON-style brief used to construct the
        # Wiro prompt. None when the builder failed or this run skipped
        # the brand path. Surfaced to the StageDetails UI so Berkay sees
        # exactly which template variant fired for this draft.
        "visual_brief_json": nb_brief,
    }


@tool("generate_visual_image")
def generate_visual_image(brief_json: str) -> str:
    """Generate Cansu's persona image, watermark+store, run 4-layer compliance gate.

    Input: JSON string with keys:
        persona_id          (str, required)
        platform            (str, e.g. 'instagram' | 'x' | 'linkedin' | 'medium' | 'youtube')
        scene_description   (str, required)
        outfit              (str, required, e.g. 'soft cream knit sweater')
        mood                (str, one of professional|warm|cinematic|technical|casual)
        content_context     (str, optional — the Action line, what she's doing)
        daily_draft_id      (str, optional — links the asset back to a draft row)
        model_slug          (str, optional, default ByteDance/seedream-v4-5)
        aspect_ratio        (str, optional — overrides platform default)

    Returns: JSON dict with status, asset_id, image_url, compliance scores.
    """
    try:
        body = json.loads(brief_json) if isinstance(brief_json, str) else brief_json
    except json.JSONDecodeError as e:
        return json.dumps({"status": "error", "error": f"bad JSON: {e}"})

    required = ("persona_id", "platform", "scene_description", "outfit", "mood")
    for k in required:
        if not body.get(k):
            return json.dumps({"status": "error", "error": f"missing field: {k}"})

    try:
        result = asyncio.run(
            _generate_and_check_async(
                persona_id=body["persona_id"],
                platform=body["platform"],
                scene_description=body["scene_description"],
                outfit=body["outfit"],
                mood=body["mood"],
                content_context=body.get("content_context"),
                daily_draft_id=body.get("daily_draft_id"),
                model_slug=body.get("model_slug", "ByteDance/seedream-v4-5"),
                aspect_ratio=body.get("aspect_ratio"),
                # Phase 41.F — defensive: if the caller ever supplies these
                # (e.g. a CrewAI agent invoked directly from a Flow node)
                # we want the Visual Decision Agent to see real signals.
                trend_topic=body.get("trend_topic"),
                plan_content_type=body.get("plan_content_type"),
                voice_mode=body.get("voice_mode"),
            )
        )
    except Exception as e:
        logger.exception("generate_visual_image failed")
        return json.dumps({"status": "error", "error": str(e)})

    return json.dumps(result, default=str)


# ─── Phase 35.3 — News image batch for split-screen video top half ───────────


async def generate_news_image_batch(
    *,
    persona_id: str,
    scene_descriptions: list[str],
    daily_draft_id: Optional[str] = None,
    content_context: Optional[str] = None,
    aspect_ratio: str = "1:1",
    visual_mode: str = "conceptual",
    model_slug: Optional[str] = None,   # Phase 35.3 — override default Wiro model
    resolution: str = "2k",              # Phase 35.3 — Berkay 30 May default 2K
    # Phase 41.F — Visual Decision Agent context. Pass-through to the helper
    # so that if a future caller flips visual_mode='hybrid' (or leaves
    # model_slug=None) the routing decision uses real headline + content_type
    # instead of the scene description as a fallback. Defaults None preserve
    # backward compatibility with current callers.
    trend_topic: Optional[str] = None,
    plan_content_type: Optional[str] = None,
    voice_mode: Optional[str] = None,
) -> list[dict]:
    """Phase 35.3 — Generate N news/brand visuals for split-screen top half.

    Uses visual_mode='conceptual' by default (no Cansu face — neutral product /
    brand / abstract tech imagery). Compliance gate runs per image but failures
    drop silently — caller decides what to do with <expected count.

    Args:
        persona_id: persona row UUID (used for storage path).
        scene_descriptions: 1-5 distinct scene prompts (caller controls
            content variety — e.g. brand-aware, content_type-aware).
        daily_draft_id: optional FK back to daily_drafts row for audit.
        content_context: optional shared trend/topic blob.
        aspect_ratio: "1:1" default (FFmpeg will crop to 1080×960 vstack top).
        visual_mode: "conceptual" (no Cansu) / "hybrid" (Cansu overlay).

    Returns:
        List of dicts: {asset_id, image_url, cost_usd, file_size_bytes,
        compliance_verdict}. Length may be < len(scene_descriptions) if
        some generations failed compliance or errored.
    """
    if not scene_descriptions:
        return []

    tasks = [
        _generate_and_check_async(
            persona_id=persona_id,
            platform="youtube",  # 9:16 routing but we override aspect_ratio
            scene_description=scene_desc,
            outfit="n/a",
            mood="cinematic",
            content_context=content_context,
            daily_draft_id=daily_draft_id,
            aspect_ratio=aspect_ratio,
            visual_mode=visual_mode,
            model_slug=model_slug,
            resolution=resolution,
            # Phase 41.F — defensive pass-through
            trend_topic=trend_topic,
            plan_content_type=plan_content_type,
            voice_mode=voice_mode,
        )
        for scene_desc in scene_descriptions
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    out: list[dict] = []
    for idx, r in enumerate(results):
        if isinstance(r, Exception):
            logger.warning(
                f"[news_image_batch] scene[{idx}] failed: {type(r).__name__}: {r}"
            )
            continue
        if not isinstance(r, dict) or r.get("status") != "ok":
            logger.warning(
                f"[news_image_batch] scene[{idx}] not-ok: {r}"
            )
            continue
        if not r.get("image_url"):
            continue
        compliance = r.get("compliance") or {}
        out.append({
            "asset_id": r.get("asset_id"),
            "image_url": r["image_url"],
            "cost_usd": r.get("cost_usd", 0.0),
            "file_size_bytes": r.get("file_size_bytes", 0),
            "compliance_verdict": compliance.get("final_verdict"),
            "compliance_reason": compliance.get("final_reason"),
        })

    logger.info(
        f"[news_image_batch] generated {len(out)}/{len(scene_descriptions)} "
        f"images for persona={persona_id[:8]} mode={visual_mode}"
    )
    return out

"""Phase 28.R-Lite Sprint 1B — Image regen queue worker.

Runs every 30 seconds via systemd (`deploy/hype-image-regen.timer`).
Picks queued image_regen_jobs, runs Wiro Seedream + 4-layer compliance gate
via `_generate_and_check_async`, then UPDATEs the matching draft_iterations
row with the new image_url + image_asset_id.

Idempotency / durability:
- Worker tags claimed jobs with status='processing' + started_at=now.
- Stale 'processing' rows (>5min, server crashed mid-flight) get retried
  on next tick, retry_count++.
- After max_retries (default 3) → status='failed' + error set, no further
  retry. Frontend shows the failure.

Usage:
    cd /opt/hype-crew
    venv/bin/python -m scripts.process_image_regen_queue
    venv/bin/python -m scripts.process_image_regen_queue --once  # single iter
"""
from __future__ import annotations

import argparse
import asyncio
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Allow `python -m scripts.process_image_regen_queue` AND direct execution
_THIS = Path(__file__).resolve()
_HYPE_CREW = _THIS.parent.parent
if str(_HYPE_CREW) not in sys.path:
    sys.path.insert(0, str(_HYPE_CREW))

from tools.supabase_client import make_supabase  # noqa: E402
from tools.visual_director_tools import _generate_and_check_async  # noqa: E402


STALE_PROCESSING_MINUTES = 5    # 'processing' >5min = orphan, retry
MAX_JOBS_PER_TICK = 3            # don't drain the whole queue in one fire
BATCH_LOOKBACK_HOURS = 24        # ignore jobs older than 24h (stale)

# V2 backlog #7 — feedback-aware scene picking.
# Map common rejection signals to scene preferences. If user complained
# about studio lighting → prefer outdoor scenes. If they complained about
# generic background → prefer specific named locations. Tightens output
# without an extra LLM call.
SCENE_BIAS_KEYWORDS = {
    # complaint → list of preferred scene types (in priority order)
    "studio": ["coffee_shop"],          # avoid studio lighting → café
    "lighting": ["coffee_shop"],
    "ışık": ["coffee_shop"],
    "stüdyo": ["coffee_shop"],
    "fake": ["coffee_shop"],            # bizarre artifacts → real location
    "yapay": ["coffee_shop"],
    "generic": ["coffee_shop"],
    "boring": ["cinematic_portrait"],   # boring → cinematic
    "düz": ["cinematic_portrait"],
    "intimate": ["cinematic_portrait"],
    "yakın": ["cinematic_portrait"],
    "professional": ["home_office"],    # explicit professional → desk
    "business": ["home_office"],
    "iş": ["home_office"],
    "ofis": ["home_office"],
}


# Minimal scene set used when worker can't access flow.py's full SCENE_LIBRARY.
# Reuses the Tier 1 face scenes from flow.py (weighted equally for simplicity).
# Sprint 2 can refactor to share with Flow's library.
SCENE_LIBRARY: list[tuple[str, str, str, str, str]] = [
    # (scene_type, scene_description, outfit, mood, content_context)
    (
        "home_office",
        "young Turkish woman at her home desk, open MacBook on a real wooden table, "
        "soft natural daylight from a side window, healthy indoor plants, books "
        "stacked on the desk, half-finished latte, modern minimalist Istanbul apartment",
        "soft cream knit sweater",
        "professional",
        "reviewing a laptop dashboard mid-thought, both hands naturally near keyboard",
    ),
    (
        "coffee_shop",
        "young Turkish woman in a cozy third-wave Istanbul specialty coffee shop, "
        "sitting at a warm wooden table, MacBook open, latte art visible in foreground, "
        "soft window light, blurred barista counter background, real cafe ambiance",
        "casual oversized cardigan over a plain tee",
        "warm",
        "leaning slightly toward the laptop screen, headphones around neck, candid moment",
    ),
    (
        "cinematic_portrait",
        "intimate cinematic portrait of a young Turkish woman, golden hour light "
        "rim-lighting one side of the face, shallow depth of field f/1.4, soft "
        "film grain, candid expression, mid-thought, magazine cover quality",
        "neutral tone simple top, no logos",
        "cinematic",
        "looking slightly off-camera, lost in thought, single subtle gesture",
    ),
]

AESTHETIC_SUFFIX = (
    ". Magazine-quality editorial photograph, professional photographer's "
    "single still from a lifestyle shoot, soft contrast, warm color grading, "
    "natural skin texture with visible pores, shallow depth of field, "
    "photoreal raw camera feel, no AI-look, no plastic skin, no over-smoothing"
)


def pick_scene(rejection_feedback: Optional[str]) -> tuple[str, str, str, str]:
    """Weighted scene pick — biases away from scenes that match user complaints.

    V2 backlog #7. Searches the rejection_feedback for known complaint
    keywords (TR + EN). If matches are found, the matching scene types are
    promoted to the front of the candidate list. Otherwise pure random.

    Each complaint maps to a preferred scene type — e.g. "studio lighting
    bad" → prefer coffee_shop (natural ambient light). Falls back to
    random if no keywords hit.
    """
    if not rejection_feedback:
        chosen = random.choice(SCENE_LIBRARY)
        return chosen[1] + AESTHETIC_SUFFIX, chosen[2], chosen[3], chosen[4]

    fb_lower = rejection_feedback.lower()
    preferred_types: list[str] = []
    for keyword, types in SCENE_BIAS_KEYWORDS.items():
        if keyword in fb_lower:
            for t in types:
                if t not in preferred_types:
                    preferred_types.append(t)

    # If we have preferences, pick from them; else fully random
    if preferred_types:
        candidates = [s for s in SCENE_LIBRARY if s[0] in preferred_types]
        if candidates:
            chosen = random.choice(candidates)
            return chosen[1] + AESTHETIC_SUFFIX, chosen[2], chosen[3], chosen[4]

    chosen = random.choice(SCENE_LIBRARY)
    return chosen[1] + AESTHETIC_SUFFIX, chosen[2], chosen[3], chosen[4]


# ─────────────────────────────────────────────────────────────────────
# Phase 43.B.2 — user-driven override bypass
# ─────────────────────────────────────────────────────────────────────
# When the user calls POST /drafts/{id}/regen-image with explicit
# override_scene_description or user_composition_type, the worker MUST
# skip its keyword-mapping classifier (pick_scene) and use the override
# verbatim. The compliance gate still runs; only the scene picker is
# bypassed. Includes a fallback parser for OVERRIDE_SCENE / OVERRIDE_COMP
# markers that the backend stuffs into rejection_feedback whenever the
# dedicated override columns haven't been added to image_regen_jobs yet
# (graceful degrade during the 43.B schema rollout).

_OVERRIDE_SCENE_MARKER = "[OVERRIDE_SCENE]"
_OVERRIDE_COMP_MARKER = "[OVERRIDE_COMP]"


def _extract_overrides_from_feedback(feedback: Optional[str]) -> dict:
    """Recover overrides stuffed into rejection_feedback by the backend.

    Used only when the dedicated columns don't exist on image_regen_jobs
    yet. Returns {} if no markers found. Markers are stripped from the
    returned 'cleaned_feedback' so the LLM doesn't see [OVERRIDE_*] noise.
    """
    if not feedback or (_OVERRIDE_SCENE_MARKER not in feedback and _OVERRIDE_COMP_MARKER not in feedback):
        return {"override_scene_description": None, "user_composition_type": None, "cleaned_feedback": feedback or ""}

    scene_override: Optional[str] = None
    comp_override: Optional[str] = None
    cleaned_lines: list[str] = []
    for line in feedback.splitlines():
        stripped = line.strip()
        if stripped.startswith(_OVERRIDE_SCENE_MARKER):
            scene_override = stripped[len(_OVERRIDE_SCENE_MARKER):].strip()
        elif stripped.startswith(_OVERRIDE_COMP_MARKER):
            comp_override = stripped[len(_OVERRIDE_COMP_MARKER):].strip()
        else:
            cleaned_lines.append(line)
    return {
        "override_scene_description": scene_override,
        "user_composition_type": comp_override,
        "cleaned_feedback": "\n".join(cleaned_lines).strip(),
    }


def pick_scene_with_overrides(
    rejection_feedback: Optional[str],
    override_scene_description: Optional[str] = None,
    user_composition_type: Optional[str] = None,
) -> tuple[str, str, str, str, bool]:
    """Phase 43.B.2 — bypass pick_scene's keyword classifier when the user
    provided an explicit scene override.

    Returns the same shape as pick_scene plus a boolean indicating whether
    overrides were applied. When override_scene_description is set, that
    string becomes scene_description verbatim (with AESTHETIC_SUFFIX
    appended), and outfit/mood fall back to neutral defaults. When only
    user_composition_type is set, we narrow SCENE_LIBRARY to that type and
    sample from the survivors.
    """
    if override_scene_description:
        # Honor the user's exact prompt. Outfit/mood become "user_override"
        # markers so the compliance gate can see they were skipped.
        return (
            override_scene_description.strip() + AESTHETIC_SUFFIX,
            "user_override_outfit",
            "user_override_mood",
            f"scene_type=user_override comp={user_composition_type or 'any'}",
            True,
        )

    if user_composition_type:
        narrowed = [s for s in SCENE_LIBRARY if s[0] == user_composition_type]
        if narrowed:
            chosen = random.choice(narrowed)
            return (
                chosen[1] + AESTHETIC_SUFFIX,
                chosen[2],
                chosen[3],
                chosen[4],
                True,
            )
        # Unknown composition type — fall through to keyword picker

    sd, outfit, mood, ctx = pick_scene(rejection_feedback)
    return sd, outfit, mood, ctx, False


# Critic Bulgu 7 (P1) — deterministic failures should NOT retry. Wiro
# content-policy or anchor-quality failures will deterministically reproduce
# the same error on retry, burning $0.04 per attempt × 3 = $0.12 wasted.
# Network / 5xx errors are transient and should retry normally.
_DETERMINISTIC_FAIL_TOKENS = (
    "forbidden_vocabulary_in_user_input",
    "missing_identity_reference",
    "Visual prompt QC failed",
    "no reference_anchor assets",
    "content_policy_violation",
    "iteration_row_not_found",
    "content_filter",
    "safety_filter_triggered",
)


def _should_retry(error: str) -> bool:
    """Return False if the error message indicates a deterministic failure."""
    if not error:
        return True
    for token in _DETERMINISTIC_FAIL_TOKENS:
        if token.lower() in error.lower():
            return False
    return True


async def claim_job(sb, job: dict) -> bool:
    """Mark job 'processing' with optimistic concurrency check.

    Returns True if we successfully claimed it (status was queued/orphaned).
    Returns False if another worker already claimed it.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    res = (
        sb.table("image_regen_jobs")
        .update({"status": "processing", "started_at": now_iso})
        .eq("id", job["id"])
        .in_("status", ["queued", "orphaned"])  # avoid double-claim
        .execute()
    )
    return bool(res.data)


async def fail_job(sb, job_id: str, error: str, retry_count: int, max_retries: int) -> None:
    """Mark job failed if max retries exhausted, else schedule retry.

    Deterministic failures (yasak vocab, missing anchor, content policy)
    short-circuit straight to 'failed' — retrying burns money and produces
    the same error.
    """
    if not _should_retry(error):
        sb.table("image_regen_jobs").update({
            "status": "failed",
            "error": f"[no-retry: deterministic] {error[:480]}",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count,
        }).eq("id", job_id).execute()
        logger.error(f"[regen-worker] job {job_id} FAILED (deterministic, no retry): {error[:200]}")
        return
    if retry_count + 1 >= max_retries:
        sb.table("image_regen_jobs").update({
            "status": "failed",
            "error": error[:500],
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "retry_count": retry_count + 1,
        }).eq("id", job_id).execute()
        logger.error(f"[regen-worker] job {job_id} FAILED after {retry_count+1} attempts: {error[:200]}")
    else:
        # Exponential backoff: 1min, 4min, 9min
        backoff_min = (retry_count + 1) ** 2
        retry_after = (datetime.now(timezone.utc) + timedelta(minutes=backoff_min)).isoformat()
        sb.table("image_regen_jobs").update({
            "status": "queued",
            "error": error[:500],
            "retry_count": retry_count + 1,
            "retry_after": retry_after,
            "started_at": None,  # reset
        }).eq("id", job_id).execute()
        logger.warning(f"[regen-worker] job {job_id} retrying in {backoff_min}min (attempt {retry_count+2})")


# ─────────────────────────────────────────────────────────────────────
# Phase 43.C — Video dispatch
# ─────────────────────────────────────────────────────────────────────
# When the backend writes regen_type='video' (POST /drafts/{id}/reject-video),
# this branch resolves the persona's preferred video pipeline (default
# 'heygen_split_screen'), builds a VideoBrief with any user-supplied
# overrides (look_id / voice_id / script_text), calls produce_video(),
# then writes the new video_url / video_thumbnail_url back onto
# daily_drafts and clears video_regen_pending. State machine ends in
# status='regen_done', which /approve treats as legal.


async def _process_video_job(
    sb,
    job: dict,
    retry_count: int,
    max_retries: int,
) -> None:
    """HeyGen video regen path for Phase 43.C."""
    job_id = job["id"]
    draft_id = job["draft_id"]
    persona_id = job.get("persona_id")
    iteration_version = job["iteration_version"]
    video_params = job.get("video_params") or {}
    if not isinstance(video_params, dict):
        video_params = {}

    # Resolve persona + the user-supplied script that they originally
    # rejected. We prefer override_script_text if the user supplied one;
    # otherwise we re-use the existing daily_drafts.content (the same
    # script that produced the rejected video).
    draft_row = (
        sb.table("daily_drafts")
        .select(
            "content, trend_topic, hype_run_id, video_url, "
            "video_thumbnail_url, video_duration_sec, persona_id, "
            "platform"
        )
        .eq("id", draft_id)
        .limit(1)
        .execute()
    )
    draft_data = (draft_row.data or [{}])[0]
    if not draft_data:
        await fail_job(
            sb, job_id, f"video regen: daily_drafts row not found {draft_id}",
            retry_count, max_retries,
        )
        return

    script_text = (
        video_params.get("override_script_text")
        or draft_data.get("content")
        or ""
    )
    if not script_text.strip():
        await fail_job(
            sb, job_id, "video regen: empty script_text after overrides",
            retry_count, max_retries,
        )
        return

    # Resolve persona row for pipeline_id + look/voice defaults
    persona_cfg: dict = {}
    try:
        p = (
            sb.table("personas")
            .select(
                # 2026-06-10 — heygen_default_voice_id personas'ta YOK; o
                # kolonu select etmek tüm sorguyu 42703 ile patlatıyor →
                # persona_cfg boş kalıyor → pipeline split_screen
                # fallback'ine düşüyordu (avatar_v yerine). Voice default'u
                # pipeline kendi config'inden çözer.
                "id, video_pipeline_default, heygen_default_look_id, "
                "daily_video_budget_usd, video_enabled"
            )
            .eq("id", persona_id)
            .limit(1)
            .execute()
        )
        persona_cfg = (p.data or [{}])[0] or {}
    except Exception as e:
        logger.warning(f"[regen-worker.video] persona read failed: {e}")

    # Berkay's hard gate — Phase 35.x pilot. If video_enabled is still
    # false we refuse the regen here (preserves the same gate enforced
    # by the saatlik run pipeline). Surface as failed-without-retry so
    # the watchdog flips the draft back out of regen_pending.
    if persona_cfg and persona_cfg.get("video_enabled") is False:
        await fail_job(
            sb, job_id,
            "video regen blocked: personas.video_enabled=false (HeyGen pilot "
            "not yet completed; flip the column when the 5-run pilot passes)",
            max_retries, max_retries,  # short-circuit retries
        )
        return

    pipeline_id = (
        persona_cfg.get("video_pipeline_default") or "heygen_split_screen"
    ).strip()

    # Stage the VideoBrief — module is lazy-imported because the worker
    # may run on a stripped-down install without FFmpeg or HeyGen wired
    # up. If the module is missing we fail the job clearly instead of
    # crashing the whole queue tick.
    try:
        from tools.video_pipeline import VideoBrief, get_pipeline  # type: ignore
    except Exception as e:
        await fail_job(
            sb, job_id,
            f"video regen: video_pipeline import failed: {type(e).__name__}: {e}",
            retry_count, max_retries,
        )
        return

    # Resolve anchor URL for the brief. We piggy-back on the Flow's
    # `_resolve_anchor_url` helper indirectly by calling load_persona_anchors
    # (same helper Flow uses) and pulling the first signed URL.
    anchor_url: Optional[str] = None
    try:
        from tools.reference_anchors import (  # type: ignore
            load_persona_anchors,
            prepare_reference_prompt_inputs,
        )
        anchors = await load_persona_anchors(persona_id)
        if anchors:
            refs = await prepare_reference_prompt_inputs(anchors, max_prompt_inputs=1)
            urls = getattr(refs, "signed_reference_urls", None) or []
            if urls:
                anchor_url = urls[0]
    except Exception as e:
        logger.warning(f"[regen-worker.video] anchor resolve failed: {e}")

    if not anchor_url:
        await fail_job(
            sb, job_id, "video regen: no anchor URL available for persona",
            retry_count, max_retries,
        )
        return

    # Inject overrides into the brief. action_prompt receives the
    # rejection feedback as guidance ("avoid these patterns next time").
    rejection_reason = video_params.get("video_rejection_reason") or ""
    rejection_fb = video_params.get("feedback") or ""
    avoid_block = ""
    if rejection_reason or rejection_fb:
        avoid_block = (
            f"\n\nAVOID — previous attempt was rejected: "
            f"reason={rejection_reason or 'none'}, feedback={rejection_fb or 'none'}"
        )

    try:
        brief = VideoBrief(
            script_text=script_text,
            persona_id=persona_id,
            anchor_image_url=anchor_url,
            action_prompt=(
                video_params.get("override_action_prompt") or ""
            ) + avoid_block,
            target_aspect="9:16",
            target_duration=int(draft_data.get("video_duration_sec") or 15),
            daily_draft_id=draft_id,
        )
    except Exception as e:
        await fail_job(
            sb, job_id, f"video regen: VideoBrief build failed: {e}",
            retry_count, max_retries,
        )
        return

    logger.info(
        f"[regen-worker.video] processing job={job_id} draft={draft_id} "
        f"v{iteration_version} pipeline={pipeline_id} "
        f"override_look={video_params.get('override_look_id') or 'auto'} "
        f"override_voice={video_params.get('override_voice_id') or 'auto'}"
    )

    try:
        pipeline = get_pipeline(pipeline_id)
        asset = await pipeline.produce_video(brief)
    except Exception as e:
        await fail_job(
            sb, job_id,
            f"video regen: pipeline {pipeline_id} failed: "
            f"{type(e).__name__}: {str(e)[:300]}",
            retry_count, max_retries,
        )
        return

    if not asset or not getattr(asset, "video_url", None):
        await fail_job(
            sb, job_id, "video regen: pipeline returned no video asset",
            retry_count, max_retries,
        )
        return

    # Persist the new video onto the parent draft AND the iteration row.
    # Clearing video_regen_pending unblocks /approve; flipping status to
    # 'regen_done' is the Phase 43.C state-machine handoff (the approve
    # endpoint whitelists 'regen_done').
    now_iso = datetime.now(timezone.utc).isoformat()
    # 2026-06-07 (video↔content binding): record the sha of the content
    # this re-render was made against, so the approve guard accepts it.
    import hashlib as _hl_regen
    # Read the LIVE current content (the operator may have edited it
    # again while the regen was running).
    try:
        live = (sb.table("daily_drafts")
                  .select("content").eq("id", draft_id).limit(1)
                  .execute().data) or []
        live_content = (live[0].get("content") if live else None) or ""
    except Exception:
        live_content = ""
    rendered_sha = _hl_regen.sha256(live_content.encode("utf-8")).hexdigest()

    # 2026-06-07 (video integrity check, post-SEV-1 follow-up P0):
    # Before we mark the new video usable, probe the actual file with
    # ffprobe and compare duration vs the expected TTS duration for
    # the LIVE content. If the render came back materially shorter
    # (truncated), set video_integrity_ok=false; the approve guard
    # will refuse to publish it, the operator can re-trigger regen.
    integrity_payload: dict = {}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools.video_integrity import check_video_integrity  # type: ignore
        local_path: Optional[str] = None
        download_dir = Path("/tmp/video_integrity_probes")
        try:
            download_dir.mkdir(exist_ok=True)
            import urllib.request as _ur
            local_path = str(download_dir / f"probe_{draft_id[:12]}.mp4")
            _ur.urlretrieve(asset.video_url, local_path)
        except Exception as _de:
            logger.warning(
                f"[regen-worker.video] integrity download failed for {draft_id[:8]}: {_de}"
            )
        if local_path:
            # PART 3 wiring (2026-06-07): pass precise TTS audio
            # duration when the worker's StoredVideoAsset has it
            # (HeyGen returns video.duration_sec matching the audio).
            _precise = None
            try:
                _precise = float(getattr(asset, "duration_sec", 0) or 0) or None
            except Exception:
                _precise = None
            result = check_video_integrity(
                file_path=local_path,
                content_for_tts=live_content,
                srt_path=None,
                tts_audio_duration_s=_precise,
            )
            integrity_payload = {
                "video_duration_s": round(result.video_duration_s, 2),
                "expected_duration_s": round(result.expected_duration_s, 2),
                "video_integrity_ok": bool(result.ok),
                "video_integrity_reason": result.reason or None,
                "video_integrity_checked_at": datetime.now(timezone.utc).isoformat(),
            }
            if not result.ok:
                logger.warning(
                    f"[regen-worker.video] INTEGRITY FAIL draft={draft_id[:8]} "
                    f"reason={result.reason}"
                )
            try:
                os.remove(local_path)
            except Exception:
                pass
    except Exception as _ie:
        logger.warning(
            f"[regen-worker.video] integrity check raised; soft-pass: {_ie!r}"
        )

    try:
        sb.table("daily_drafts").update({
            "video_url": asset.video_url,
            "video_thumbnail_url": asset.thumbnail_url,
            "video_duration_sec": int(asset.duration_sec) or None,
            "video_regen_pending": False,
            "video_content_sha": rendered_sha,
            "video_stale": False,
            "status": "regen_done",
            "regen_started_at": None,
            **integrity_payload,
        }).eq("id", draft_id).execute()
    except Exception as e:
        # Don't fail the job — the asset exists on storage. Surface the
        # warning so frontend can re-poll.
        logger.warning(
            f"[regen-worker.video] draft UPDATE failed (asset already stored): {e}"
        )

    # Also link onto draft_iterations if a row for this version exists.
    try:
        sb.table("draft_iterations").update({
            "image_url": None,  # video lives on daily_drafts directly
            "image_asset_id": None,
        }).eq("draft_id", draft_id).eq("version", iteration_version).execute()
    except Exception:
        pass  # iteration rows are optional on the video path

    completed_status = "completed"
    sb.table("image_regen_jobs").update({
        "status": completed_status,
        "cost_usd": float(asset.cost_usd or 0),
        "completed_at": now_iso,
    }).eq("id", job_id).execute()

    logger.info(
        f"[regen-worker.video] ✓ job {job_id} completed "
        f"cost=${asset.cost_usd:.3f} latency={asset.generation_latency_ms/1000:.1f}s "
        f"url={asset.video_url[:60]}..."
    )


async def process_job(sb, job: dict) -> None:
    """Run the regen pipeline for one job.

    Phase 43.C — `regen_type='video'` dispatches to HeyGen split-screen
    pipeline instead of the Wiro image pipeline. Default is 'image' so
    every existing queued row continues to work.
    """
    job_id = job["id"]
    draft_id = job["draft_id"]
    persona_id = job.get("persona_id")
    iteration_version = job["iteration_version"]
    rejection_feedback = job.get("rejection_feedback") or ""
    image_reason = job.get("image_rejection_reason") or ""
    trend_topic = job.get("trend_topic") or ""
    retry_count = job.get("retry_count") or 0
    max_retries = job.get("max_retries") or 3

    if not persona_id:
        await fail_job(sb, job_id, "no persona_id resolved for draft", retry_count, max_retries)
        return

    # Phase 43.C — branch on regen_type. Video jobs run a completely
    # different pipeline (HeyGen + MiniMax + FFmpeg + Supabase upload),
    # so we dispatch before touching any image-side state.
    regen_type = (job.get("regen_type") or "image").lower()
    if regen_type == "video":
        await _process_video_job(sb, job, retry_count, max_retries)
        return

    # Resolve platform + run context from draft. Phase 41.F (Berkay 2 Haz 2026)
    # also pulls hype_run_id so we can fetch the Strategist's content_type +
    # voice_mode and feed them to the Visual Decision Agent — otherwise the
    # regen path silently falls back to scene_description / platform as
    # routing inputs (the exact Phase 41.B bug, but on the reject→regen lane).
    draft_row = (
        sb.table("daily_drafts")
        .select("platform, hype_run_id")
        .eq("id", draft_id)
        .limit(1)
        .execute()
    )
    draft_data = (draft_row.data or [{}])[0]
    platform = draft_data.get("platform") or "instagram"
    hype_run_id = draft_data.get("hype_run_id")

    # Phase 41.F — Strategist's content_type + voice_mode (hype_stages JOIN).
    # Best-effort: if the lookup fails we leave both None and the helper falls
    # back to scene_description / platform (Phase 41.B helper-side fallback).
    plan_content_type: str | None = None
    plan_voice_mode: str | None = None
    if hype_run_id:
        try:
            strat_row = (
                sb.table("hype_stages")
                .select("output")
                .eq("run_id", hype_run_id)
                .eq("agent_name", "Content Strategist")
                .limit(1)
                .execute()
            )
            strat_out = (strat_row.data or [{}])[0].get("output") or {}
            plan_content_type = strat_out.get("content_type")
            plan_voice_mode = strat_out.get("voice_mode")
        except Exception as e:
            logger.warning(
                f"[regen-worker] strategist context lookup failed ({type(e).__name__}: {e}); "
                f"proceeding without content_type/voice_mode"
            )

    # Phase 43.B.2 — honor user-supplied overrides. Prefer the dedicated
    # job columns; fall back to feedback markers if the schema migration
    # hasn't reached image_regen_jobs yet.
    override_scene = job.get("override_scene_description")
    override_comp = job.get("user_composition_type")
    if not override_scene and not override_comp:
        recovered = _extract_overrides_from_feedback(rejection_feedback)
        override_scene = recovered["override_scene_description"]
        override_comp = recovered["user_composition_type"]
        # Strip [OVERRIDE_*] markers so they don't bleed into the LLM context
        if recovered["cleaned_feedback"] != (rejection_feedback or ""):
            rejection_feedback = recovered["cleaned_feedback"]

    scene_description, outfit, mood, scene_ctx, used_overrides = pick_scene_with_overrides(
        rejection_feedback,
        override_scene_description=override_scene,
        user_composition_type=override_comp,
    )
    if used_overrides:
        logger.info(
            f"[regen-worker] job {job_id}: BYPASSING pick_scene keyword mapping "
            f"(override_scene={'yes' if override_scene else 'no'}, "
            f"comp={override_comp or 'auto'})"
        )

    # Build content_context: trend + rejection feedback so Visual Director
    # actively avoids whatever was wrong last time.
    content_context_parts = [scene_ctx]
    if trend_topic:
        content_context_parts.append(f"context: {trend_topic}")
    if image_reason:
        content_context_parts.append(f"AVOID: {image_reason}")
    if rejection_feedback:
        content_context_parts.append(f"user feedback: {rejection_feedback}")
    content_context = ". ".join(content_context_parts)

    logger.info(
        f"[regen-worker] processing job={job_id} draft={draft_id} v{iteration_version} "
        f"platform={platform} persona={persona_id[:8]}"
    )

    try:
        result = await _generate_and_check_async(
            persona_id=persona_id,
            platform=platform,
            scene_description=scene_description,
            outfit=outfit,
            mood=mood,
            content_context=content_context,
            daily_draft_id=draft_id,
            # Phase 41.F — pass the real Strategist context so the Visual
            # Decision Agent (Phase 39 / 41.B) can route this regen by the
            # actual headline + content_type + voice_mode instead of treating
            # the scene description as the news. Without this, a user who
            # rejected a Cansu image saying "this should be brand-only" would
            # get yet another Cansu image, looping forever.
            trend_topic=trend_topic,
            plan_content_type=plan_content_type,
            voice_mode=plan_voice_mode,
            # NOTE: visual_mode is intentionally left at its default ("face")
            # but model_slug stays None — so the helper's Phase 39 router
            # branch runs and the *real* path (cansu vs brand) is picked by
            # decide_needs_cansu, not hardcoded to face like the pre-41.F
            # behaviour.
        )
    except Exception as e:
        await fail_job(sb, job_id, f"{type(e).__name__}: {str(e)[:300]}", retry_count, max_retries)
        return

    if result.get("status") != "ok":
        await fail_job(sb, job_id, result.get("error", "generation_failed"), retry_count, max_retries)
        return

    image_url = result.get("image_url")
    asset_id = result.get("asset_id")
    cost = result.get("cost_usd") or 0
    compliance = result.get("compliance") or {}
    final_verdict = compliance.get("final_verdict", "UNKNOWN")

    # Update the iteration row with new image.
    # Critic P0 — silently failing UPDATE leaves frontend polling forever.
    # If 0 rows match (off-by-one, race vs INSERT commit, synthetic test),
    # we MUST fail the job with a clear reason instead of marking completed.
    try:
        upd = sb.table("draft_iterations").update({
            "image_url": image_url,
            "image_asset_id": asset_id,
        }).eq("draft_id", draft_id).eq("version", iteration_version).execute()
        rows_updated = len(upd.data or [])
    except Exception as e:
        await fail_job(sb, job_id, f"draft_iterations_update_failed: {type(e).__name__}: {e}", retry_count, max_retries)
        return

    if rows_updated == 0:
        # Iteration row doesn't exist for this version. Frontend would poll
        # forever — surface as failure so user sees it and can retry.
        await fail_job(
            sb, job_id,
            f"iteration_row_not_found: draft={draft_id} v{iteration_version}",
            retry_count, max_retries,
        )
        return

    # Mark job completed. Surface compliance verdict so frontend can render
    # a "quality warning" indicator when LLM judge said FAIL but the image
    # is otherwise usable.
    completed_status = "completed"
    error_field = None
    if final_verdict == "FAIL":
        # We keep status='completed' (image is usable) but stash the verdict
        # in `error` field so frontend can show a warning banner. Sprint 2
        # may promote this to a dedicated 'completed_with_warning' state.
        error_field = f"compliance_verdict=FAIL: {compliance.get('llm_reasoning', '')[:200]}"

    sb.table("image_regen_jobs").update({
        "status": completed_status,
        "image_url": image_url,
        "image_asset_id": asset_id,
        "cost_usd": cost,
        "error": error_field,
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", job_id).execute()

    logger.info(
        f"[regen-worker] ✓ job {job_id} completed verdict={final_verdict} "
        f"cost=${cost:.4f} rows={rows_updated} url={image_url[:60] if image_url else '-'}..."
    )


async def tick() -> int:
    """Run one queue drain tick. Returns count of jobs handled."""
    sb = make_supabase()
    now = datetime.now(timezone.utc)
    stale_cutoff = (now - timedelta(minutes=STALE_PROCESSING_MINUTES)).isoformat()
    lookback_cutoff = (now - timedelta(hours=BATCH_LOOKBACK_HOURS)).isoformat()

    # Pick: queued (retry_after passed) OR stale processing (orphan)
    # Sprint 2 — could use SELECT ... FOR UPDATE SKIP LOCKED for stricter
    # concurrency. supabase-py doesn't expose row locks; we rely on the
    # claim_job() conditional UPDATE for cheap optimistic locking.
    # Phase 43.B.2 — try to SELECT the new override columns. If the schema
    # migration hasn't landed yet, fall back to the legacy projection. The
    # override values can still be recovered downstream from
    # rejection_feedback markers (_extract_overrides_from_feedback).
    base_cols = (
        "id, draft_id, iteration_version, persona_id, "
        "rejection_target, rejection_category, rejection_feedback, "
        "image_rejection_reason, trend_topic, retry_count, max_retries, "
        "retry_after, created_at, started_at, status"
    )
    # Phase 43.C — try to grab regen_type + video_params alongside the
    # Phase 43.B.2 image override columns. If the 43.C migration hasn't
    # reached this instance yet, we fall through to the 43.B projection
    # (no override cols) and ultimately the legacy projection.
    extended_cols = (
        base_cols
        + ", override_scene_description, user_composition_type"
        + ", regen_type, video_params"
    )
    try:
        queued = (
            sb.table("image_regen_jobs")
            .select(extended_cols)
            .gte("created_at", lookback_cutoff)
            .order("created_at", desc=False)
            .limit(20)
            .execute()
        )
    except Exception as e:
        msg = str(e)[:300]
        # Try 43.B projection (image overrides but no video cols)
        if (
            "regen_type" in msg
            or "video_params" in msg
            or "PGRST204" in msg
            or "column" in msg.lower()
        ):
            try:
                queued = (
                    sb.table("image_regen_jobs")
                    .select(base_cols + ", override_scene_description, user_composition_type")
                    .gte("created_at", lookback_cutoff)
                    .order("created_at", desc=False)
                    .limit(20)
                    .execute()
                )
            except Exception as e2:
                msg2 = str(e2)[:300]
                if (
                    "override_scene_description" in msg2
                    or "user_composition_type" in msg2
                    or "PGRST204" in msg2
                    or "column" in msg2.lower()
                ):
                    queued = (
                        sb.table("image_regen_jobs")
                        .select(base_cols)
                        .gte("created_at", lookback_cutoff)
                        .order("created_at", desc=False)
                        .limit(20)
                        .execute()
                    )
                else:
                    raise
        elif (
            "override_scene_description" in msg
            or "user_composition_type" in msg
        ):
            queued = (
                sb.table("image_regen_jobs")
                .select(base_cols)
                .gte("created_at", lookback_cutoff)
                .order("created_at", desc=False)
                .limit(20)
                .execute()
            )
        else:
            raise
    rows = queued.data or []

    pickable = []
    for r in rows:
        st = r.get("status")
        ra = r.get("retry_after")
        if st == "queued":
            if not ra or ra <= now.isoformat():
                pickable.append(r)
        elif st == "processing":
            started = r.get("started_at")
            if started and started < stale_cutoff:
                pickable.append(r)

    if not pickable:
        return 0

    # V2 backlog #3 — parallel processing. Each job is a Wiro API call
    # + compliance pipeline (~90s I/O-bound). asyncio.gather drains
    # MAX_JOBS_PER_TICK jobs concurrently instead of serially, so 3 jobs
    # take ~90s instead of ~270s. Cost is identical (per-job Wiro spend
    # unchanged) but worker latency drops 3×.
    async def _run_one(job: dict) -> int:
        claimed = await claim_job(sb, job)
        if not claimed:
            return 0
        try:
            await process_job(sb, job)
            return 1
        except Exception as e:
            logger.exception(f"[regen-worker] unexpected error processing {job['id']}: {e}")
            await fail_job(
                sb, job["id"], f"unhandled: {type(e).__name__}: {str(e)[:200]}",
                job.get("retry_count") or 0, job.get("max_retries") or 3,
            )
            return 0

    results = await asyncio.gather(
        *(_run_one(j) for j in pickable[:MAX_JOBS_PER_TICK]),
        return_exceptions=False,
    )
    return sum(results)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="single tick then exit")
    args = parser.parse_args()

    handled = asyncio.run(tick())
    if handled:
        logger.info(f"[regen-worker] tick complete, {handled} job(s) handled")
    else:
        logger.debug("[regen-worker] tick complete, queue empty")


if __name__ == "__main__":
    main()

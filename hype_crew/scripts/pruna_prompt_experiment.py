"""Pruna lip-sync prompt-engineering experiment.

5 controlled variations: same anchor + same seed + same audio,
only `videoPrompt` changes. Goal: find prompt style that minimises
face distortion / "melting" / identity drift across frames.

Hypothesis: explicit anti-distortion language + identity-preserving
hints in videoPrompt reduce Pruna's face artefacts.

Usage:
    cd hype_crew
    venv/bin/python -m scripts.pruna_prompt_experiment

Cost: ~$1.55 (5 × $0.31). Compute: ~5 × 60s = ~5 min total.
Output: /tmp/pruna_prompt_exp.json + each video URL printed.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

_THIS = Path(__file__).resolve()
_HYPE_CREW = _THIS.parent.parent
if str(_HYPE_CREW) not in sys.path:
    sys.path.insert(0, str(_HYPE_CREW))

from scripts.pilot_4_video_pipelines import _resolve_persona, _get_anchor_url  # noqa: E402
from tools.minimax_tts_client import MinimaxTTSClient  # noqa: E402
from tools.wiro_client import WiroClient  # noqa: E402
from tools.supabase_storage import SupabaseStorage  # noqa: E402
from config import settings  # noqa: E402


# Sabit deneysel parametreler — sadece videoPrompt değişken
FIXED_SEED = 42
FIXED_SCRIPT_TR = (
    "Merhaba, ben Cansu. Bu hafta Hype Crew otonom video pipeline ekledim, "
    "üç dakikada Türkçe konuşan klipler üretiyor."
)


PROMPTS: dict[str, str] = {
    "v1_minimal_motion": (
        "A young woman sitting still and talking calmly to camera. "
        "Static face position, minimal head movement, no exaggerated expressions, "
        "only the lips move with the audio. Photoreal skin with natural pores, "
        "no smoothing, no AI face artifacts, no plastic look."
    ),
    "v2_anti_distortion": (
        "Close-up of a real Turkish woman speaking quietly to the camera. "
        "Anatomically correct facial features at all times. Stable mouth shape. "
        "No warping or melting of the face. No double pupils. No floating teeth. "
        "Sharp eye detail. Realistic skin texture with visible pores. "
        "Identity remains consistent frame to frame."
    ),
    "v3_documentary_locked": (
        "Documentary-style talking head shot of a 25-year-old Turkish woman. "
        "Her face stays anchored and stable throughout the entire clip. "
        "Only the lips and subtle facial muscles move with the audio. "
        "Background is a soft-focus home office. Lighting is natural mid-morning "
        "daylight from a window. Shot on a real camera, photoreal."
    ),
    "v4_identity_preserving": (
        "Cinematic 1080p portrait shot of a Turkish woman in her mid-twenties "
        "speaking to camera. Maintain her exact facial features throughout: "
        "her eye color, nose shape, brow structure, and jawline must not change "
        "between frames. Warm natural daylight, shallow depth of field, "
        "photoreal raw camera footage feel, no AI-look."
    ),
    "v5_negative_focused": (
        "A young woman talking naturally to camera. NO AI face artefacts, "
        "NO plastic synthetic skin, NO smoothed faces, NO warped features, "
        "NO inconsistent identity, NO melting or morphing, NO facial deformation, "
        "NO floating teeth, NO doubled pupils. Just a real person talking, "
        "photoreal documentary capture, natural micro-expressions only."
    ),
}


async def _synthesize_tts(persona_id: str) -> tuple[str, float]:
    """Reuse the same TTS audio across all 5 runs (saved + uploaded once)."""
    client = MinimaxTTSClient()
    result, public_url = await client.synthesize_and_upload(
        text=FIXED_SCRIPT_TR, persona_id=persona_id,
    )
    return public_url, result.cost_usd


async def _run_one(
    label: str,
    video_prompt: str,
    *,
    anchor_url: str,
    audio_url: str,
    persona_id: str,
) -> dict:
    """Run one Pruna generation with the given videoPrompt."""
    t0 = time.perf_counter()
    try:
        async with WiroClient() as client:
            result = await client.generate_talking_avatar(
                portrait_url=anchor_url,
                audio_url=audio_url,
                slug="pruna/p-video-avatar",
                resolution=1080,
                videoPrompt=video_prompt,
                seed=FIXED_SEED,
            )
        elapsed = time.perf_counter() - t0
        # Pruna returns asset_url; we don't run FFmpeg here — pure model output
        return {
            "label": label,
            "status": "ok",
            "video_prompt": video_prompt,
            "asset_url": result.asset_url,
            "cost_usd": round(result.cost_usd, 4),
            "elapsed_sec": round(elapsed, 1),
            "model_slug": "pruna/p-video-avatar",
            "resolution": "1080p",
            "seed": FIXED_SEED,
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        logger.exception(f"[exp] {label} FAILED: {e}")
        return {
            "label": label,
            "status": "failed",
            "video_prompt": video_prompt,
            "error": f"{type(e).__name__}: {e}",
            "elapsed_sec": round(elapsed, 1),
        }


async def main() -> int:
    persona = _resolve_persona("cansu_dut")
    logger.info(f"[exp] persona={persona['slug']} id={persona['id']}")

    # Step 1: single TTS — shared across all 5 runs
    logger.info("[exp] step 1: MiniMax TTS (shared)")
    audio_url, tts_cost = await _synthesize_tts(persona["id"])
    logger.info(f"[exp] TTS URL ready, cost=${tts_cost:.5f}")

    # Step 2: single anchor URL — shared across all 5 runs (deterministic
    # selection by reference_anchors heuristic)
    anchor_url = await _get_anchor_url(persona["id"])
    logger.info(f"[exp] anchor selected (deterministic)")

    # Step 3: run all 5 prompt variations SEQUENTIALLY (avoid Wiro rate
    # issues + easier to inspect logs)
    results = []
    for label, prompt in PROMPTS.items():
        logger.info(f"[exp] running {label}...")
        r = await _run_one(
            label, prompt,
            anchor_url=anchor_url,
            audio_url=audio_url,
            persona_id=persona["id"],
        )
        results.append(r)

    summary = {
        "experiment": "pruna_prompt_engineering_anti_distortion",
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "persona_slug": persona["slug"],
        "persona_id": persona["id"],
        "script_text": FIXED_SCRIPT_TR,
        "fixed_seed": FIXED_SEED,
        "resolution": "1080p",
        "shared_audio_url_prefix": audio_url[:90],
        "shared_anchor_signed_url_prefix": anchor_url[:90],
        "tts_cost_usd": round(tts_cost, 5),
        "results": results,
        "total_cost_usd": round(
            tts_cost + sum(r.get("cost_usd", 0) for r in results), 4
        ),
    }
    out_path = Path("/tmp/pruna_prompt_exp.json")
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[exp] summary written: {out_path}")

    print("\n" + "=" * 78)
    print(f"PRUNA PROMPT EXPERIMENT — total cost ${summary['total_cost_usd']:.3f}")
    print("=" * 78)
    for r in results:
        if r["status"] == "ok":
            print(f"  ✓ {r['label']:<26}  ${r['cost_usd']:.3f}  {r['elapsed_sec']:.0f}s")
            print(f"      → {r['asset_url']}")
        else:
            print(f"  ✗ {r['label']:<26}  FAILED: {r.get('error', '?')[:80]}")
    print()
    print("Yan yana izle, en az distortion olanı seç. Sonra ona göre Pipeline A defaultu güncelle.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

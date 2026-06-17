"""End-to-end test: generate Cansu's first AI image via Wiro Nano Banana Pro.

Pipeline:
    load 5 anchors → signed URLs → visual_prompt.enhance_visual_prompt →
    Wiro generate_image → download → watermark → Supabase upload →
    persona_assets row insert → print public_url.

Run:
    cd hype_crew && venv/bin/python -m scripts.test_first_image
"""
from __future__ import annotations

import asyncio
import json
import sys
import time

from loguru import logger

from tools.image_pipeline import generate_and_store_visual_brief_asset
from tools.reference_anchors import (
    load_persona_anchors,
    prepare_reference_prompt_inputs,
)
from tools.visual_prompt import VisualPromptBrief

PERSONA_ID = "653cea63-8105-478e-803c-24377038c39c"

SCENE_DESCRIPTION = (
    "Cansu at her home office desk in front of an open MacBook, "
    "natural mid-morning daylight from a window, a small indoor plant on the "
    "desk, a half-finished coffee cup, candid unposed atmosphere, "
    "unretouched raw photo"
)
OUTFIT = "soft cream knit sweater"
CONTENT_CONTEXT = (
    "reviewing a laptop dashboard mid-thought, both hands naturally near the "
    "keyboard or trackpad"
)
MOOD = "casual"  # available daylight, soft overcast (per guide §9.1 — most natural)
PLATFORM = "instagram"  # 1:1 aspect ratio


async def main() -> int:
    logger.info("=== PART 2 — FIRST REAL WIRO IMAGE ===")
    t0 = time.perf_counter()

    # 1. Load anchors and prepare signed URLs (1 identity anchor — winning recipe)
    logger.info(f"loading anchors for persona {PERSONA_ID}...")
    anchors = await load_persona_anchors(PERSONA_ID)
    logger.info(f"  found {len(anchors)} anchors")

    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description=SCENE_DESCRIPTION,
        content_context=CONTENT_CONTEXT,
        outfit=OUTFIT,
        max_prompt_inputs=1,  # single identity anchor — Wiro stays anchored on face only
    )
    logger.info(f"  selected {len(inputs.signed_reference_urls)} anchors for prompt")

    # 2. Build VisualPromptBrief
    brief = VisualPromptBrief(
        platform=PLATFORM,
        scene_description=SCENE_DESCRIPTION,
        outfit=OUTFIT,
        mood=MOOD,
        content_context=CONTENT_CONTEXT,
        reference_image_urls=inputs.signed_reference_urls,
    )

    # 3. Generate + upload + DB insert
    # Canonical recipe (Phase 21 PART 2 winning combo):
    #   - ByteDance/seedream-v4-5 model (lowest cost, best lifelike output)
    #   - 4k resolution
    #   - single identity anchor only (Image 1 = face source, no role-confused supports)
    #   - visual_prompt.enhance_visual_prompt with iPhone 11 standardized phrasing
    #     (baked into _opening_line_for_model / _camera_for_model / GPT_IMAGE_REALISM_BLOCK)
    #   - no post-watermark (constraints clause already says "no watermark")
    logger.info("submitting to Wiro Seedream v4.5 with canonical iPhone-11 recipe...")
    stored = await generate_and_store_visual_brief_asset(
        persona_id=PERSONA_ID,
        brief=brief,
        slug="ByteDance/seedream-v4-5",
        resolution="4k",
        max_images=1,
        ai_watermark=False,
    )

    elapsed = time.perf_counter() - t0
    logger.success("=" * 70)
    logger.success("✓ FIRST CANSU IMAGE GENERATED")
    logger.success(f"  asset_id:      {stored.asset_id}")
    logger.success(f"  public_url:    {stored.public_url}")
    logger.success(f"  storage_key:   {stored.bucket}/{stored.storage_key}")
    logger.success(f"  file_size:     {stored.file_size_bytes / 1024:.1f} KB")
    logger.success(f"  cost_usd:      ${stored.generation.cost_usd}")
    logger.success(f"  wiro_latency:  {stored.generation.latency_ms} ms")
    logger.success(f"  total_elapsed: {elapsed:.1f}s")
    logger.success("=" * 70)
    logger.info("Open public_url in browser to inspect the generated image.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

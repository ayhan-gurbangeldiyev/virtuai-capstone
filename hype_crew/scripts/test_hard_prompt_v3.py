"""v3 hard prompt — iPhone 11 camera (less computational photography → more amateur feel).

Changes from v2:
- iPhone 16 Pro → iPhone 11 (2019-era sensor, less AI photography polish)
- 24mm → 26mm equivalent (iPhone 11 wide camera)
- f/1.8 explicit aperture
- Add iPhone 11 specific behaviors: noisier shadows, less aggressive sharpening,
  softer autofocus, slightly muted colors
- Drop "natural HDR" (iPhone 11's HDR is much less aggressive than 16 Pro)
- Add "2020-era casual phone photo aesthetic"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

from loguru import logger

from tools.image_pipeline import store_wiro_image_asset
from tools.reference_anchors import (
    load_persona_anchors,
    prepare_reference_prompt_inputs,
)
from tools.wiro_client import WiroClient

PERSONA_ID = "653cea63-8105-478e-803c-24377038c39c"

HARD_PROMPT_V3 = """\
Image 1 (IDENTITY ANCHOR) — use ONLY for the face and identity. Do NOT copy its pose, \
hair gesture, clothing, background, lighting, or camera angle.

Match the face of the person in Image 1 pixel-faithfully. Use Image 1 as the only \
source for facial identity. Do not invent or alter facial features. Preserve identity \
from Image 1 pixel-faithfully.

A raw casual snapshot of the same person from Image 1, taken on an iPhone 11 by a \
friend during an ordinary Tuesday morning around 2020. This is NOT an editorial \
photo, NOT a portrait session, NOT a fashion shoot, NOT a stock photo, NOT a social \
media post. This is a casual unposed moment captured mid-action with an older phone.

Action: she is looking at her laptop screen, both hands resting naturally near the \
keyboard, gaze fixed on the screen, eyebrows slightly drawn together in focus. She \
is NOT looking at the camera. She is NOT posing. She does not know the photo is \
being taken.

Setting: an ordinary small home office desk — a modern silver laptop open in front \
of her with a generic clean UI on the screen (no specific app visible), a plain \
ceramic mug of coffee next to the laptop, a small monstera plant in the corner of \
the desk, soft mid-morning daylight from a single window on the left, no other \
light source, simple uncluttered desk.

Composition: phone-eye-level frame, subject slightly off-center to the right third, \
slight tilt as if the photographer was rushing, real framing imperfections, slight \
hand-held camera shake feel.

Camera: shot on iPhone 11 main wide camera, 26mm equivalent, f/1.8, 12MP sensor. \
2019-era smartphone camera — less computational photography polish, less aggressive \
sharpening, less aggressive HDR, slightly softer autofocus, slightly muted colors \
compared to modern phones. NO portrait mode. NO bokeh. NO beauty filter. NO modern \
computational smoothing. NO studio lens compression. Just a casual 2020-era phone \
photo aesthetic.

Skin: matte natural skin with visible pores around the nose and cheeks, slight oily \
T-zone, mild under-eye shadow, tiny flyaway hairs near the hairline, subtle facial \
asymmetry — left brow slightly higher than right, a faint redness on one cheek, no \
makeup or only a hint of natural lip color, no facial smoothing whatsoever.

Eyes: single soft catchlight in each eye, natural moisture, eyes focused on the \
laptop screen, NOT looking at the camera.

Hair: shoulder-length wavy medium brown hair, slightly unstyled, a few stray strands \
across the forehead.

Wardrobe: soft cream knit sweater, slightly oversized, visible fabric weave and \
natural fold creases at the elbows, no fashion polish, no logo, minimal jewelry only \
if anything.

Lighting: available window daylight only, soft overcast feel, no studio quality, \
faint shadow on the right side of her face, no rim light, no key light, no fill light.

Color: slightly muted natural color balance typical of an iPhone 11, slightly cool \
indoor white balance from window light, no cinematic grading, no teal-orange grade, \
no saturation push, no contrast boost.

Texture: visible digital noise in the shadow areas typical of iPhone 11 small \
sensor, mild graininess overall, fabric weave clearly visible on the sweater, slight \
chromatic aberration on high-contrast edges, no AI-smooth surfaces.

Atmosphere: real ordinary Tuesday morning, not glamorous, not staged, a real person \
doing real work captured candidly — no advertising aesthetic, no curated lifestyle \
pose, no influencer feel.

Aspect ratio: 1:1.

Constraints: matte natural skin only, candid unposed framing only, amateur 2020-era \
phone snapshot feel only, raw unedited phone photo only, true material textures \
only, slightly muted neutral colors only, identity from Image 1 only, a normal \
everyday laptop only.

Do not include: any AI smoothing, any plastic look, any waxy highlights, any \
symmetric perfection, any over-saturation, any teal-orange grade, any cinematic \
grading, any studio polish, any beauty filter, any portrait mode blur, any \
professional photography polish, any stock-photo polish, any influencer aesthetic, \
any modern computational photography look (iPhone 13/14/15/16 look), any aggressive \
HDR, any watermark, any on-screen text or logo on the laptop, any brand logo, any \
religious symbol, any political imagery, any other person in the frame, any extra \
fingers, any duplicate hands, any distorted laptop, any oversized or undersized \
laptop, any weird laptop keyboard.

The output MUST feel like a real iPhone 11 photo from a real person's 2020 camera \
roll, NOT a generated image, NOT a portrait session, NOT a stock photo. The image \
should have the slightly muted, slightly noisy, slightly soft aesthetic of an \
iPhone 11 — not a polished modern smartphone photo. If it looks polished or modern, \
it is wrong.
"""


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", default="ByteDance/seedream-v4-5")
    parser.add_argument("--resolution", default="4k")
    args = parser.parse_args()

    logger.info(f"=== HARD PROMPT v3 (iPhone 11) — model={args.slug} resolution={args.resolution} ===")
    t0 = time.perf_counter()

    anchors = await load_persona_anchors(PERSONA_ID)
    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description="home office laptop work",
        outfit="cream knit sweater",
        max_prompt_inputs=1,
    )
    logger.info(f"prompt length: {len(HARD_PROMPT_V3)} chars")

    async with WiroClient() as client:
        gen = await client.generate_image(
            slug=args.slug,
            prompt=HARD_PROMPT_V3,
            aspect_ratio="1:1",
            resolution=args.resolution,
            max_images=1,
            watermark=False,
            input_image=inputs.signed_reference_urls,
        )
    logger.info(f"wiro complete: ${gen.cost_usd} in {gen.latency_ms / 1000:.1f}s")

    stored = await store_wiro_image_asset(
        persona_id=PERSONA_ID,
        generation=gen,
        prompt=HARD_PROMPT_V3,
        ai_watermark=False,
        asset_status="generated",
        generation_metadata_overrides={
            "prompt_strategy": "hard_manual_v3_iphone11",
            "anchor_count": 1,
            "anchor_role": "identity_only",
            "model_slug_requested": args.slug,
            "v3_change": "iphone_11_camera_aesthetic",
        },
    )

    elapsed = time.perf_counter() - t0
    logger.success("=" * 70)
    logger.success(f"public_url:    {stored.public_url}")
    logger.success(f"asset_id:      {stored.asset_id}")
    logger.success(f"cost_usd:      ${stored.generation.cost_usd}")
    logger.success(f"wiro_latency:  {stored.generation.latency_ms / 1000:.1f}s")
    logger.success(f"total_elapsed: {elapsed:.1f}s")
    logger.success("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

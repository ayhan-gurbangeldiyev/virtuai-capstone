"""Hard-prompt test: bypass visual_prompt.enhance_visual_prompt and craft a
maximally anti-plastic prompt manually. Single identity anchor only.

Stacks §7.4 Plastic Detector fixes:
- raw amateur iPhone snapshot framing (not editorial)
- visible skin pores, oily T-zone, micro-asymmetry, redness
- single catchlight, natural moisture, eyes off-camera
- Kodak Portra 400 + ISO 800 grain, phone sensor noise
- fabric weave, fold creases (anti-plastic garment)
- "candid moment captured by a friend" framing
- explicit "no AI smoothing, no portrait mode, no beauty filter" closing
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

HARD_PROMPT = """\
Image 1 (IDENTITY ANCHOR) — use ONLY for the face and identity. Do NOT copy its pose, \
hair gesture, clothing, background, lighting, or camera angle.

Match the face of the person in Image 1 pixel-faithfully. Use Image 1 as the only \
source for facial identity. Do not invent or alter facial features. Preserve identity \
from Image 1 pixel-faithfully.

A raw amateur iPhone snapshot of the same person from Image 1, taken by a friend \
during an ordinary Tuesday morning. This is NOT an editorial photo, NOT a portrait \
session, NOT a fashion shoot, NOT a stock photo, NOT a social media post. This is a \
casual unposed moment captured mid-action with a phone.

Action: she is reviewing a laptop dashboard mid-thought, both hands resting naturally \
near the keyboard, gaze fixed on the screen, eyebrows slightly drawn together in focus. \
She is NOT looking at the camera. She is NOT posing. She does not know the photo is \
being taken.

Setting: an ordinary small home office in Istanbul — a wooden desk with a closed \
notebook, a half-finished mug of coffee with a faint condensation ring on the wood, \
a small monstera plant in the corner, soft mid-morning daylight from a single window \
to the left, no other light source, unstaged desk clutter, a tangled charging cable \
half-visible.

Composition: phone-eye-level frame, subject slightly off-center to the right third, \
slight tilt as if the photographer was rushing, real framing imperfections, edges \
include random objects (corner of a chair, part of a wall).

Camera: shot on iPhone 16 Pro main camera, 24mm equivalent, natural HDR. NO portrait \
mode. NO bokeh. NO beauty filter. NO computational smoothing. NO studio lens \
compression. Phone HDR look only.

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

Color: natural color balance, slightly cool indoor white balance from window light, \
no cinematic grading, no teal-orange grade, no saturation push, no contrast boost.

Texture: faint film grain like Kodak Portra 400 pushed to ISO 800, subtle phone \
sensor noise in the shadow areas, fabric weave clearly visible on the sweater, real \
reflection on the laptop screen, micro-scratches on the laptop edge where it would \
naturally show.

Atmosphere: real ordinary Tuesday morning, not glamorous, not staged, a real founder \
doing real work captured candidly — no advertising aesthetic, no curated lifestyle \
pose, no influencer feel.

Aspect ratio: 1:1.

Constraints: matte natural skin only, candid unposed framing only, amateur snapshot \
feel only, raw unedited phone photo only, true material textures only, neutral color \
balance only, identity from Image 1 only.

Do not include: any AI smoothing, any plastic look, any waxy highlights, any \
symmetric perfection, any over-saturation, any teal-orange grade, any cinematic \
grading, any studio polish, any beauty filter, any portrait mode blur, any \
professional photography polish, any stock-photo polish, any influencer aesthetic, \
any watermark, any on-screen text, any brand logo, any religious symbol, any \
political imagery, any other person in the frame, any extra fingers, any duplicate \
hands.

The output MUST feel like a real iPhone photo from a real person's camera roll, NOT \
a generated image, NOT a portrait session, NOT a stock photo. If it looks polished, \
it is wrong.
"""


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--slug",
        default="ByteDance/seedream-v4-5",
        help="Wiro model slug, e.g. ByteDance/seedream-v4-5 or openai/gpt-image-2",
    )
    parser.add_argument("--resolution", default="4k")
    args = parser.parse_args()

    logger.info(f"=== HARD PROMPT TEST — model={args.slug} resolution={args.resolution} ===")
    t0 = time.perf_counter()

    # Load 1 identity anchor only
    anchors = await load_persona_anchors(PERSONA_ID)
    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description="home office laptop work",
        outfit="cream knit sweater",
        max_prompt_inputs=1,  # ONE anchor — identity only
    )
    logger.info(f"using single identity anchor: {len(inputs.signed_reference_urls)} URL")
    logger.info(f"prompt length: {len(HARD_PROMPT)} chars")

    # Direct Wiro call — no visual_prompt enhancement
    async with WiroClient() as client:
        gen = await client.generate_image(
            slug=args.slug,
            prompt=HARD_PROMPT,
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
        prompt=HARD_PROMPT,
        ai_watermark=False,
        asset_status="generated",
        generation_metadata_overrides={
            "prompt_strategy": "hard_manual_v1",
            "anchor_count": 1,
            "anchor_role": "identity_only",
            "model_slug_requested": args.slug,
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

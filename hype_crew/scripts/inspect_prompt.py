"""Print the exact prompt that visual_prompt.enhance_visual_prompt emits.

Run:
    venv/bin/python -m scripts.inspect_prompt
"""
from __future__ import annotations

import asyncio

from tools.reference_anchors import (
    load_persona_anchors,
    prepare_reference_prompt_inputs,
)
from tools.visual_prompt import VisualPromptBrief, enhance_visual_prompt

PERSONA_ID = "653cea63-8105-478e-803c-24377038c39c"


async def main() -> None:
    anchors = await load_persona_anchors(PERSONA_ID)
    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description=(
            "Cansu at her home office desk in front of an open MacBook, "
            "natural mid-morning daylight from a window, a small indoor plant "
            "on the desk, a half-finished coffee cup, candid unposed atmosphere, "
            "unretouched raw photo"
        ),
        content_context=(
            "reviewing a laptop dashboard mid-thought, both hands naturally near "
            "the keyboard or trackpad"
        ),
        outfit="soft cream knit sweater",
        max_prompt_inputs=4,
    )
    brief = VisualPromptBrief(
        platform="instagram",
        scene_description=(
            "Cansu at her home office desk in front of an open MacBook, "
            "natural mid-morning daylight from a window, a small indoor plant "
            "on the desk, a half-finished coffee cup, candid unposed atmosphere, "
            "unretouched raw photo"
        ),
        outfit="soft cream knit sweater",
        mood="casual",
        content_context=(
            "reviewing a laptop dashboard mid-thought, both hands naturally near "
            "the keyboard or trackpad"
        ),
        reference_image_urls=inputs.signed_reference_urls,
    )
    enhanced = enhance_visual_prompt(brief, model_slug="ByteDance/seedream-v4-5")
    print("=" * 80)
    print(f"MODE: {enhanced.mode}")
    print(f"MODEL_TARGET: {enhanced.model_target}")
    print(f"ASPECT: {enhanced.aspect_ratio}")
    print(f"WARNINGS: {enhanced.warnings}")
    print(f"QC: {enhanced.qc_passed}")
    print("=" * 80)
    print("PROMPT:")
    print(enhanced.prompt)
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

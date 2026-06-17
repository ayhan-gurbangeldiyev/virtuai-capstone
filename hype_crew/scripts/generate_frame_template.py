"""Generate the Cansu news-card FRAME template on Wiro (Nano Banana Pro, 4:5, 4K).

Gen-Z OAKBERRY purple theme. The frame is the FIXED img2img reference: an empty
light hero area on top (filled later per-news) + a deep-purple bottom band with the
HABER pill and a 2-line headline placeholder.

Usage:
    ./venv/bin/python scripts/generate_frame_template.py [variant] [out_path]

variant: 'with_chrome' (default — keeps top-left logo + 1/1 counter) or
         'clean' (no logo, no counter — minimal band-only).

Prints the temporary Wiro CDN URL + cost. Downloads a local copy for review.
Does NOT upload to Supabase (do that once the design is approved).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import httpx

# Make hype_crew/ importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.wiro_client import WiroClient  # noqa: E402

_PLACEHOLDER = "Haber başlığı yer alacak buraya satır iki"

# Shared art direction (Gen-Z purple, faceless news-card frame).
_BASE = (
    "A clean modern 4:5 vertical FULL-SCREEN news POSTER background, edge-to-edge, "
    "Gen-Z editorial design system, flat clean vector-like UI (NOT a photo). "
    "This is NOT a card and NOT a sticker — there is NO container shape, the artwork "
    "is the entire image and bleeds to all four edges with sharp 90-degree corners. "
    "TOP ~78%: an intentionally EMPTY bright area — soft off-white to pale lavender "
    "gradient with lots of calm negative space (this area is reserved, leave it empty, "
    "no logo, no monogram, no letters, no watermark). "
    "BOTTOM ~22%: a full-width DEEP SATURATED EGGPLANT-PURPLE gradient band "
    "(rich OAKBERRY purple, from #2A0E3F at the bottom to #1A0526), softly fading "
    "upward into the light canvas. Inside the band, left-aligned: a white OUTLINED "
    "rounded pill with transparent fill and white uppercase letters reading 'HABER', "
    "and directly below it a TWO-LINE bold white sans-serif headline placeholder "
    f"reading '{_PLACEHOLDER}'. "
    "Confident Gen-Z energy, sharp clean typography, retro-ish rounded pills, "
    "generous white space, premium minimal. "
    "FULL-BLEED composition: the design fills the ENTIRE canvas edge-to-edge — "
    "NO outer white margin, NO card border, NO rounded outer corners, NO drop "
    "shadow around the artwork. Both the light hero area and the purple band run "
    "all the way to every edge of the image. "
    "NO people, NO human face, NO product photo, no extra decorations, no clutter. "
    "4:5 vertical, 4K."
)

_CHROME = (
    " TOP-LEFT corner: a small bold geometric monogram logo mark (dark on light). "
    "TOP-RIGHT corner: a small rounded light-gray pill showing '1 / 1'."
)

# Canonical Mor Glow template (LOCKED theme). Aura + HABER pill + EMPTY title
# zone (no dummy headline -> no leak). No hero subject (i2i fills it). This is
# the fixed input_image reference reused for every news item.
_GLOW_CANONICAL = (
    "A full-bleed 4:5 vertical Gen-Z news poster BACKGROUND: a glowing "
    "violet-to-magenta radial AURA blooming softly from the lower-center upward, "
    "smooth gradient-mesh, deep eggplant-purple toward the edges, premium, dreamy, "
    "NO hard dividing lines — one continuous glow filling the whole frame. "
    "FULL-BLEED edge-to-edge: NOT a card or sticker, no outer margin, no border, "
    "no rounded outer corners, sharp 90-degree corners. "
    "In the LOWER-LEFT, a single small white-outline rounded 'HABER' pill "
    "(transparent fill, white uppercase letters) — spelled exactly H A B E R. "
    "Leave the area BELOW the pill completely EMPTY (reserved for a headline). "
    "NO other text anywhere, NO people, NO face, NO objects, NO logos — only the "
    "purple aura and the single HABER pill. 4:5 vertical, 4K, premium Gen-Z."
)

VARIANTS = {
    "with_chrome": _BASE + _CHROME,
    "clean": _BASE + " No logo and no counter in the top corners — keep them empty.",
    "glow": _GLOW_CANONICAL,
}


async def main() -> None:
    variant = sys.argv[1] if len(sys.argv) > 1 else "with_chrome"
    if variant not in VARIANTS:
        raise SystemExit(f"unknown variant '{variant}', choose: {list(VARIANTS)}")
    out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(
        f"../tmp_frames/cansu_frame_genz_{variant}.png"
    )
    prompt = VARIANTS[variant]
    resolution = os.environ.get("FRAME_RES", "4K").strip() or "4K"

    print(f"[frame] variant={variant} slug=google/nano-banana-pro 4:5 {resolution}")
    async with WiroClient() as client:
        gen = await client.generate_image(
            slug="google/nano-banana-pro",
            prompt=prompt,
            aspect_ratio="4:5",
            resolution=resolution,
            max_images=1,
            watermark=False,
        )
    print(f"[frame] DONE url={gen.asset_url}")
    print(f"[frame] cost_usd={gen.cost_usd} latency_ms={gen.latency_ms}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        r = await c.get(gen.asset_url)
    r.raise_for_status()
    out_path.write_bytes(r.content)
    print(f"[frame] saved local copy -> {out_path.resolve()} ({len(r.content)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())

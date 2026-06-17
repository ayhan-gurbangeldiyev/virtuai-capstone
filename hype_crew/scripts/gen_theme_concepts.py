"""Generate 5 distinct Gen-Z theme concepts for the Cansu news card (text2image).

Each is a faceless, full-bleed 4:5 poster with a real sample headline baked in
(no dummy placeholder -> demonstrates the structural bug fix). For theme
selection only; the production frame of the chosen theme will have an EMPTY
title area + i2i.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.wiro_client import WiroClient  # noqa: E402

HEADLINE = "Claude AI yanıt hızını ikiye katladı"

RULES = (
    " STRICT RULES: faceless — NO people, NO human face, NO portrait. "
    "FULL-BLEED edge-to-edge — this is NOT a card or sticker container, "
    "NO outer white margin, NO border, NO rounded outer corners, sharp 90-degree "
    "corners, the artwork is the entire image. 4:5 vertical. "
    "Render the Turkish headline EXACTLY with correct Turkish letters (ı, ş, ğ, ü, ö, ç), "
    "spelled perfectly, no other text besides the headline and the 'HABER' label. "
    "Gen-Z editorial, confident, premium, sharp clean typography, no clutter."
)

THEMES = {
    "1_mor_daldirma": (
        "A full-bleed 4:5 vertical news poster living entirely in a rich Gen-Z PURPLE "
        "world: a deep eggplant-to-violet gradient mesh fills the WHOLE frame. The top "
        "~75% is a reserved empty hero area rendered as soft purple ambient gradient with "
        "a gentle lighter-violet glow and subtle abstract shapes. The bottom ~25% smoothly "
        "deepens into darker eggplant where the text sits — NO hard dividing line, one "
        "continuous color flowing as a single whole. Bottom-left: a white-outline rounded "
        "'HABER' pill (transparent fill, white uppercase). Below it a bold WHITE sans-serif "
        f"Turkish headline, left-aligned, 1-2 lines: \"{HEADLINE}\". Immersive, bold, cohesive."
    ),
    "2_ince_serit": (
        "A full-bleed 4:5 vertical EDITORIAL news poster, clean and premium. The top ~82% "
        "is a bright reserved empty hero area, soft off-white to very pale lavender. The "
        "purple footprint is MINIMAL: only a THIN horizontal violet accent line near the "
        "bottom plus a compact title zone sitting on a subtle soft upward purple-tinted "
        "scrim (NOT a solid block). A thin violet keyline runs just inside the entire poster "
        "edge to tie the layout together. Bottom-left: a violet-outline rounded 'HABER' pill. "
        f"Below it a bold DARK-EGGPLANT sans-serif Turkish headline, 1-2 lines: \"{HEADLINE}\". "
        "Restrained, magazine-grade, cohesive via the thin purple keyline."
    ),
    "3_mor_glow": (
        "A full-bleed 4:5 vertical Gen-Z news poster with a glowing purple aura. The reserved "
        "empty hero area has a soft violet radial GLOW blooming from the bottom-center upward, "
        "melting gradually into darker purple toward the bottom — NO hard edge, hero and title "
        "blend as one continuous gradient-mesh aura. Dreamy yet bold. Bottom-left: a white-outline "
        "rounded 'HABER' pill. Below it a bold WHITE softly-glowing sans-serif Turkish headline, "
        f"1-2 lines: \"{HEADLINE}\". Cohesive — the glow unifies the whole frame."
    ),
    "4_sticker_chip": (
        "A full-bleed 4:5 vertical Gen-Z news poster using a sticker/chip design language. A soft "
        "light tech background fills the whole reserved hero frame. Near the bottom, a single "
        "FLOATING rounded-rectangle PURPLE chip (deep eggplant, soft drop shadow) overlaps the hero "
        "and contains the text. On the chip: a small white-outline 'HABER' tag, and below it a bold "
        f"WHITE sans-serif Turkish headline, 1-2 lines: \"{HEADLINE}\". A consistent rounded-pill "
        "design system ties it together; the purple footprint is just the chip. Playful yet premium."
    ),
    "5_diyagonal": (
        "A full-bleed 4:5 vertical Gen-Z news poster with dynamic energy. A bold DIAGONAL purple "
        "shape (deep eggplant-to-violet gradient) sweeps across the BOTTOM-LEFT corner, angling "
        "upward to the right (NOT a flat horizontal band). The rest is a bright reserved empty hero "
        "area. On the diagonal purple shape: a white-outline rounded 'HABER' pill and a bold WHITE "
        f"sans-serif Turkish headline following the angled baseline, 1-2 lines: \"{HEADLINE}\". "
        "Asymmetric, energetic, punchy, modern; smaller angular purple footprint."
    ),
}


async def _gen(client: WiroClient, key: str, prompt: str) -> None:
    print(f"[theme {key}] submitting...")
    gen = await client.generate_image(
        slug="google/nano-banana-pro",
        prompt=prompt + RULES,
        aspect_ratio="4:5",
        resolution="2K",
        max_images=1,
        watermark=False,
    )
    out = Path(f"../tmp_frames/theme_{key}.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        r = await c.get(gen.asset_url)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"[theme {key}] DONE cost={gen.cost_usd} -> {out.name}  url={gen.asset_url}")


async def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    async with WiroClient() as client:
        for key, prompt in THEMES.items():
            if only and only not in key:
                continue
            await _gen(client, key, prompt)


if __name__ == "__main__":
    asyncio.run(main())

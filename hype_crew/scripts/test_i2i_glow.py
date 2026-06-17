"""i2i on the Mor Glow (aura) theme with a real trend — see how a news subject
sits inside the purple glow while the aura + HABER + headline are preserved."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # noqa: E402
from tools.brand_extractor import extract_brand_from_topic, build_brand_subject  # noqa: E402
from tools.wiro_client import WiroClient  # noqa: E402


def _pick_trend() -> dict:
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat()
    rows = (sb.table("trends")
            .select("id,topic,category,score")
            .gte("created_at", since).eq("is_visible", True).eq("is_archived", False)
            .order("score", desc=True).limit(12).execute()).data or []
    if not rows:
        raise SystemExit("no trends")
    for t in rows:
        if extract_brand_from_topic(t.get("topic") or ""):
            return t
    return rows[0]


def _glow_prompt(headline: str, hero_concept: str) -> str:
    return (
        "Using the provided purple-aura news poster as the EXACT base: keep the glowing "
        "violet-to-magenta radial AURA atmosphere, the full-bleed background, the "
        "white-outline 'HABER' pill and the headline styling. "
        "In the headline area, COMPLETELY REPLACE any existing text and write ONLY this "
        f"exact headline, bold white sans-serif, 1-2 lines: \"{headline}\". "
        "Do NOT keep any dummy words. "
        f"In the UPPER portion of the aura, place {hero_concept} as a single clear subject "
        "that sits naturally INSIDE the purple glow — lit by the purple ambient light, "
        "softly glowing, blending into the aura (NOT a separate box or card). "
        "Faceless: no people, no human face. No extra logos, no circuit-board / "
        "glowing-brain / humanoid-robot cliché. Keep 4:5 vertical, 4K, premium Gen-Z."
    )


async def main() -> None:
    frame_url = (os.environ.get("FRAME_URL") or "").strip()
    if not frame_url:
        raise SystemExit("set FRAME_URL (the theme_3 glow image url)")
    trend = _pick_trend()
    topic = trend.get("topic") or ""
    brand = extract_brand_from_topic(topic)
    headline = topic if len(topic) <= 64 else topic[:64].rsplit(" ", 1)[0]
    hero = build_brand_subject(brand, "conceptual") if brand else ""
    if not hero:
        hero = f"a clean editorial visual representing: {topic}"

    print(f"[glow] trend: [{trend.get('score')}] {topic}")
    print(f"[glow] brand: {brand or '(none)'} | headline: {headline}")
    print(f"[glow] hero : {hero[:140]}")

    async with WiroClient() as client:
        gen = await client.generate_image(
            slug="google/nano-banana-pro",
            prompt=_glow_prompt(headline, hero),
            aspect_ratio="4:5", resolution="2K", max_images=1,
            watermark=False, input_image=[frame_url],
        )
    print(f"[glow] DONE cost={gen.cost_usd} url={gen.asset_url}")
    out = Path("../tmp_frames/test_glow_i2i_output.png")
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        r = await c.get(gen.asset_url)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"[glow] saved -> {out.resolve()} ({len(r.content)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())

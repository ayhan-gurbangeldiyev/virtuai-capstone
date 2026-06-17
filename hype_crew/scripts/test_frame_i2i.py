"""Trial: real trend -> framed i2i image (no DB writes).

Pulls a real trend from Supabase, derives headline + hero_concept exactly like
flow.generate_visual() does (brand_extractor reuse), builds the SAME i2i prompt
the pipeline uses (framed_news_image.build_frame_i2i_prompt), and renders ONE
Wiro Nano Banana Pro img2img against the frame template. Downloads locally.

Env:
    FRAME_URL  — the frame template URL to use as input_image (required)
    FRAME_RES  — resolution (default 2K)
"""
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
from tools.framed_news_image import build_frame_i2i_prompt  # noqa: E402
from tools.wiro_client import WiroClient  # noqa: E402


def _pick_trend() -> dict:
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=96)).isoformat()
    rows = (
        sb.table("trends")
        .select("id,topic,category,score,source_name")
        .gte("created_at", since)
        .eq("is_visible", True).eq("is_archived", False)
        .order("score", desc=True)
        .limit(12).execute()
    ).data or []
    if not rows:
        raise SystemExit("no trends found in the last 96h")
    # Prefer a trend whose topic carries a known brand so the brand path fires.
    for t in rows:
        if extract_brand_from_topic(t.get("topic") or ""):
            return t
    return rows[0]


def _clean_headline(topic: str, limit: int = 95) -> str:
    topic = (topic or "").strip()
    if len(topic) <= limit:
        return topic
    cut = topic[:limit].rsplit(" ", 1)[0]
    return cut


async def main() -> None:
    frame_url = (os.environ.get("FRAME_URL") or "").strip()
    if not frame_url:
        raise SystemExit("set FRAME_URL to the frame template image URL")
    resolution = os.environ.get("FRAME_RES", "2K").strip() or "2K"

    forced = (os.environ.get("TOPIC") or "").strip()
    if forced:
        trend = {"score": "manual", "topic": forced}
    else:
        trend = _pick_trend()
    topic = trend.get("topic") or ""
    brand = extract_brand_from_topic(topic)
    headline = _clean_headline(topic)
    if brand:
        hero_concept = build_brand_subject(brand, "conceptual") or ""
    else:
        hero_concept = ""
    if not hero_concept:
        hero_concept = f"a clean editorial tech-news visual representing: {topic}"

    print(f"[i2i-test] trend   : [{trend.get('score')}] {topic}")
    print(f"[i2i-test] brand   : {brand or '(none, concept fallback)'}")
    print(f"[i2i-test] headline: {headline}")
    print(f"[i2i-test] hero    : {hero_concept[:140]}")

    prompt = build_frame_i2i_prompt(headline=headline, hero_concept=hero_concept)
    print(f"[i2i-test] generating ({resolution}, 4:5, input_image=frame)...")
    async with WiroClient() as client:
        gen = await client.generate_image(
            slug="google/nano-banana-pro",
            prompt=prompt,
            aspect_ratio="4:5",
            resolution=resolution,
            max_images=1,
            watermark=False,
            input_image=[frame_url],
        )
    print(f"[i2i-test] DONE url={gen.asset_url}")
    print(f"[i2i-test] cost_usd={gen.cost_usd} latency_ms={gen.latency_ms}")

    out = Path("../tmp_frames/test_i2i_output.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as c:
        r = await c.get(gen.asset_url)
    r.raise_for_status()
    out.write_bytes(r.content)
    print(f"[i2i-test] saved -> {out.resolve()} ({len(r.content)} bytes)")


if __name__ == "__main__":
    asyncio.run(main())

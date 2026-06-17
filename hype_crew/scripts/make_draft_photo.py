"""End-to-end (visual only): real trend -> accurate grounded headline ->
framed glow i2i photo -> PERSISTED to the system (persona_assets).

Saves the news-card image as a draft asset for the account's persona. Platform
TEXT drafts require the full crew (heavy ML deps) and run on the prod box.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # noqa: E402
from tools.brand_extractor import extract_brand_from_topic  # noqa: E402
from tools.news_headline import generate_news_headline_async  # noqa: E402
from tools.framed_news_image import (  # noqa: E402
    generate_framed_news_image_async,
    build_frame_hero_concept,
)

ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "4f13b200-9364-42df-aa44-5fb2b8399cd0")
FRAME_URL = os.environ.get(
    "FRAME_URL",
    "https://awlsmfhxcsifabyanwfv.supabase.co/storage/v1/object/public/"
    "persona-generated/frames/cansu_glow_canonical_v1.png",
)
TOPIC_MATCH = os.environ.get("TOPIC_MATCH", "%Cowork%limit%")


async def main() -> None:
    sb = make_supabase()

    persona = (sb.table("personas").select("id, slug, display_name, visual_enabled")
               .eq("primary_account_id", ACCOUNT_ID).limit(1).execute()).data
    if not persona:
        raise SystemExit(f"no persona for account {ACCOUNT_ID}")
    persona = persona[0]
    print(f"[draft] persona: {persona.get('slug')} ({persona['id']}) "
          f"visual_enabled={persona.get('visual_enabled')}")

    trow = (sb.table("trends").select("id, topic, raw_content")
            .ilike("topic", TOPIC_MATCH).order("created_at", desc=True)
            .limit(1).execute()).data
    if not trow:
        raise SystemExit(f"no trend matching {TOPIC_MATCH}")
    trow = trow[0]
    topic = trow.get("topic") or ""
    raw = trow.get("raw_content")
    print(f"[draft] trend: {topic}")
    print(f"[draft] source: {(raw or '')[:160]}")

    headline = await generate_news_headline_async(topic=topic, source_text=raw)
    brand = extract_brand_from_topic(topic)
    _hidx = os.environ.get("HERO_IDX")
    hero = build_frame_hero_concept(
        brand, topic, style_idx=int(_hidx) if _hidx not in (None, "") else None
    )
    print(f"[draft] HEADLINE: {headline}")
    print(f"[draft] brand={brand} hero={hero[:90]}")

    result = await generate_framed_news_image_async(
        persona_id=persona["id"],
        headline=headline,
        hero_concept=hero,
        frame_url=FRAME_URL,
    )
    print(f"[draft] status      : {result.get('status')}")
    print(f"[draft] asset_id    : {result.get('asset_id')}")
    print(f"[draft] image_url   : {result.get('image_url')}")
    print(f"[draft] storage_key : {result.get('storage_key')}")
    print(f"[draft] cost_usd    : {result.get('cost_usd')}")
    comp = result.get("compliance") or {}
    print(f"[draft] compliance  : {comp.get('final_verdict')} ({comp.get('final_reason')})")


if __name__ == "__main__":
    asyncio.run(main())

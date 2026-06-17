"""Re-skin existing drafts to the new glow card style.

For each trend_id: generate a fresh glow i2i card (grounded headline + varied
minimal-text hero) and relink ALL of that trend's daily_drafts to the new image.
Text content is untouched — only the visual style is updated.

Usage: TREND_IDS=id1,id2,... ACCOUNT_ID=.. python -m scripts.reskin_drafts
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
    generate_framed_news_image_async, build_frame_hero_concept,
)

ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "2b731bf7-8c24-40c5-8237-d348ee822d51")
TREND_IDS = [x.strip() for x in (os.environ.get("TREND_IDS") or "").split(",") if x.strip()]


async def reskin_one(sb, persona_id: str, trend_id: str) -> str:
    t = (sb.table("trends").select("topic, raw_content, full_source_text")
         .eq("id", trend_id).limit(1).execute()).data
    if not t:
        return f"{trend_id[:8]}: trend not found"
    t = t[0]
    topic = t.get("topic") or ""
    source = t.get("full_source_text") or t.get("raw_content") or ""
    headline = await generate_news_headline_async(topic=topic, source_text=source)
    brand = extract_brand_from_topic(topic)
    hero = build_frame_hero_concept(brand, topic)
    res = await generate_framed_news_image_async(
        persona_id=persona_id, headline=headline, hero_concept=hero,
    )
    if res.get("status") != "ok":
        return f"{trend_id[:8]} '{topic[:40]}': GEN FAILED {res.get('error')}"
    url = res["image_url"]; aid = res["asset_id"]
    upd = (sb.table("daily_drafts").update({"image_url": url, "image_asset_id": aid})
           .eq("trend_id", trend_id).execute()).data or []
    return f"{trend_id[:8]} '{topic[:40]}': OK relinked={len(upd)} hl='{headline[:50]}'"


async def main() -> None:
    if not TREND_IDS:
        raise SystemExit("set TREND_IDS=comma,separated,ids")
    sb = make_supabase()
    persona = (sb.table("personas").select("id").eq("primary_account_id", ACCOUNT_ID)
               .limit(1).execute()).data[0]
    pid = persona["id"]
    print(f"persona={pid} reskinning {len(TREND_IDS)} trends")
    for i, tid in enumerate(TREND_IDS, 1):
        try:
            msg = await reskin_one(sb, pid, tid)
        except Exception as e:  # noqa: BLE001
            msg = f"{tid[:8]}: EXC {type(e).__name__}: {str(e)[:120]}"
        print(f"[{i}/{len(TREND_IDS)}] {msg}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())

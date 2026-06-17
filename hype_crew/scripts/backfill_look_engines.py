"""Phase 40.A — Backfill supported_api_engines for existing curated looks.

Phase 38 sync (Mayıs 2026) HeyGen avatar group'undan AI-generated photo'ları
persona_assets'a yazıyordu ama her look'un Avatar V uyumluluğunu kaydetmiyordu.
Phase 40.A (1 Haz 2026) sync'i bunu yeni look'lar için ekledi; bu script
mevcut sync'lenmiş satırlar için aynı bilgiyi geri-doldurur.

Çalıştır: `python -m scripts.backfill_look_engines --persona-slug=cansu_dut`

Idempotent — `generation_metadata.supported_api_engines` zaten doluysa atlar.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.supabase_client import make_supabase
from tools.heygen_client import HeyGenClient


async def backfill_one(sb, hg: HeyGenClient, row: dict[str, Any]) -> dict[str, Any]:
    meta = dict(row.get("generation_metadata") or {})
    heygen_id = meta.get("heygen_id") or row.get("provider_task_uuid")
    if not heygen_id:
        return {"asset_id": row["id"], "status": "skip", "reason": "no heygen_id"}
    if isinstance(meta.get("supported_api_engines"), list):
        return {
            "asset_id": row["id"],
            "heygen_id": heygen_id,
            "status": "already_backfilled",
            "engines": meta["supported_api_engines"],
        }

    try:
        look = await hg.get_look(heygen_id)
    except Exception as e:
        logger.warning(f"  {heygen_id[:8]}: get_look failed: {e}")
        return {"asset_id": row["id"], "heygen_id": heygen_id, "status": "fetch_fail"}

    engines = list(look.supported_api_engines or [])
    meta["supported_api_engines"] = engines
    sb.table("persona_assets").update({"generation_metadata": meta}).eq("id", row["id"]).execute()
    return {
        "asset_id": row["id"],
        "heygen_id": heygen_id,
        "status": "backfilled",
        "engines": engines,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona-slug", default="cansu_dut")
    args = parser.parse_args()

    sb = make_supabase()
    p_res = sb.table("personas").select("id, slug").eq("slug", args.persona_slug).limit(1).execute()
    persona_rows = p_res.data or []
    if not persona_rows:
        logger.error(f"persona '{args.persona_slug}' not found")
        sys.exit(1)
    persona_id = persona_rows[0]["id"]

    res = (
        sb.table("persona_assets")
        .select("id, provider_task_uuid, generation_metadata")
        .eq("persona_id", persona_id)
        .eq("asset_type", "curated_photo")
        .eq("status", "publish_ready")
        .order("created_at", desc=False)
        .execute()
    )
    rows = res.data or []
    logger.info(f"Found {len(rows)} curated_photo rows for persona '{args.persona_slug}'")

    hg = HeyGenClient()
    results = []
    for row in rows:
        r = await backfill_one(sb, hg, row)
        results.append(r)
        engines_str = ",".join(r.get("engines") or []) or "—"
        logger.info(
            f"  {(r.get('heygen_id') or '?')[:8]} {r['status']:20s} engines=[{engines_str}]"
        )

    # Summary
    by_status: dict[str, int] = {}
    for r in results:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    logger.info(f"\nDone — {by_status}")
    # Avatar V eligible count
    avatar_v_count = sum(
        1 for r in results
        if any(str(e).lower() == "avatar_v" for e in (r.get("engines") or []))
    )
    logger.info(f"Avatar V eligible: {avatar_v_count} / {len(rows)}")


if __name__ == "__main__":
    asyncio.run(main())

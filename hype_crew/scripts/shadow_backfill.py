"""Backfill the faithfulness shadow gate over historical daily_drafts.

Runs the advisory gate against every recent daily_draft with a known
source (joined via trends.raw_content), tags each verdict with
path='shadow_backfill', and also re-derives the human_decision from the
historical status (approved → approve; auto_rejected → reject) so the
graduation-readiness math has a paired (gate, human) signal from day 1.

Usage:
    cd /opt/hype-crew && venv/bin/python scripts/shadow_backfill.py \
        --days 30 --account 2b731bf7-8c24-40c5-8237-d348ee822d51 \
        --max 200 --concurrency 6

This is idempotent: drafts whose id already has a shadow_backfill row
are skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.guarded_postiz import shadow_gate, record_human_decision  # type: ignore
from tools.supabase_client import make_supabase                       # type: ignore


HUMAN_FROM_STATUS = {
    "approved": "approve",
    "published": "approve",
    "auto_approved": "approve",
    "auto_scheduled": "approve",
    "auto_rejected": "reject",
    "dismissed": "reject",
    "deleted": "reject",
}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--account", type=str, default=None,
                    help="Filter to one account_id; omit for all accounts.")
    ap.add_argument("--max", type=int, default=200)
    ap.add_argument("--concurrency", type=int, default=6)
    args = ap.parse_args()

    sb = make_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()

    q = (
        sb.table("daily_drafts")
        .select("id, account_id, trend_id, content, status, source_url, created_at")
        .gt("created_at", cutoff)
        .order("created_at", desc=True)
        .limit(args.max)
    )
    if args.account:
        q = q.eq("account_id", args.account)
    drafts = q.execute().data or []
    print(f"Loaded {len(drafts)} candidate drafts from last {args.days}d "
          f"(account={args.account or 'all'}).")

    # Cache raw_content from trends in batch
    trend_ids = list({d["trend_id"] for d in drafts if d.get("trend_id")})
    raw_by_trend = {}
    url_by_trend = {}
    if trend_ids:
        for chunk_start in range(0, len(trend_ids), 50):
            chunk = trend_ids[chunk_start:chunk_start + 50]
            rows = (
                sb.table("trends").select("id, raw_content, url")
                .in_("id", chunk).execute().data or []
            )
            for r in rows:
                raw_by_trend[r["id"]] = r.get("raw_content") or ""
                url_by_trend[r["id"]] = r.get("url")

    # Skip drafts that already have a shadow_backfill row
    existing_ids = set()
    if drafts:
        existing = (
            sb.table("faithfulness_verdicts")
            .select("draft_id")
            .eq("path", "shadow_backfill")
            .in_("draft_id", [d["id"] for d in drafts])
            .execute().data or []
        )
        existing_ids = {r["draft_id"] for r in existing}

    todo = [d for d in drafts if d["id"] not in existing_ids
            and (raw_by_trend.get(d.get("trend_id") or "") or "")
            and d.get("content")]
    print(f"  already-backfilled: {len(existing_ids)}    todo: {len(todo)}")

    sem = asyncio.Semaphore(args.concurrency)
    n_pass = 0
    n_block = 0
    n_err = 0

    async def run_one(d):
        nonlocal n_pass, n_block, n_err
        async with sem:
            src = raw_by_trend.get(d.get("trend_id") or "") or ""
            try:
                outcome = await shadow_gate(
                    draft_text=d["content"],
                    source_raw_content=src,
                    draft_id=d["id"],
                    account_id=d.get("account_id"),
                    trend_id=d.get("trend_id"),
                    source_url=d.get("source_url") or url_by_trend.get(d.get("trend_id") or ""),
                    path_tag="shadow_backfill",
                )
                if outcome.verdict == "PASS":
                    n_pass += 1
                elif outcome.verdict == "HARD_BLOCK":
                    n_block += 1
                else:
                    n_err += 1
            except Exception as e:
                print(f"  [err] {d['id'][:8]}: {e!r}")
                n_err += 1
                return

            # Pair with the historical human decision when one exists
            human = HUMAN_FROM_STATUS.get((d.get("status") or "").lower())
            if human:
                record_human_decision(
                    d["id"], human,
                    reason=f"backfill_from_status={d.get('status')}",
                    decided_by="backfill",
                )

    await asyncio.gather(*[run_one(d) for d in todo])
    print(f"\nBackfill done: PASS={n_pass}  HARD_BLOCK={n_block}  ERROR={n_err}")


if __name__ == "__main__":
    asyncio.run(main())

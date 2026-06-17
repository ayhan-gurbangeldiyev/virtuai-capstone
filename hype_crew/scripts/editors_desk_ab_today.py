"""Today's editorial pool — editor's-desk pick vs reactive TrendScout pick.

For each connected account, fetches the current post-Lever-A pool, runs the
editor's-desk select_lead() pass, then reports:
  - editor's pick (lead + grounded reason)
  - strongest passed-over (per the same call)
  - what the reactive rubric would have picked (top by score)
  - a side-by-side so the operator can see whether the editor's choice is
    defensibly better.

Runs against the LIVE pool but writes nothing to the live editorial_lead_judgments
table (the script is read-only — actual writes happen inside flow.py:_run_editors_desk
when the real cron fires).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, "/opt/contentfactory")

from tools.supabase_client import make_supabase  # type: ignore
from tools.supabase_tools import query_trends    # type: ignore
from backend.services.editors_desk import select_lead  # type: ignore


ACCOUNTS = [
    ("Cansu DUT X (twitter)",       "2b731bf7-8c24-40c5-8237-d348ee822d51"),
    # Add LinkedIn if exists; uncomment after confirming the id.
]


def reactive_pick(candidates: list[dict]) -> dict | None:
    """What the old rubric path (TrendScout's `score >= 90 or is_vip`) would
    pick — highest score wins (ties broken by published_at desc)."""
    if not candidates:
        return None
    sorted_pool = sorted(
        candidates,
        key=lambda c: (
            c.get("score") or 0,
            c.get("published_at") or "",
        ),
        reverse=True,
    )
    return sorted_pool[0]


def enrich(candidates: list[dict], sb) -> list[dict]:
    tids = [c.get("id") for c in candidates if c.get("id")]
    if not tids:
        return []
    rows = (
        sb.table("trends")
        .select("id, raw_content, url, source_name, published_at, "
                "cluster_id, semantic_triggers, category, topic, score")
        .in_("id", tids)
        .execute()
        .data
    ) or []
    by_id = {r["id"]: r for r in rows if isinstance(r, dict)}
    out = []
    for c in candidates:
        r = by_id.get(c.get("id"), {})
        out.append({
            "trend_id": c.get("id"),
            "cluster_id": r.get("cluster_id"),
            "topic": c.get("topic") or r.get("topic"),
            "category": c.get("category") or r.get("category"),
            "semantic_triggers": c.get("semantic_triggers")
                                  or r.get("semantic_triggers") or [],
            "score": c.get("score") or r.get("score"),
            "source_url": r.get("url"),
            "source_name": r.get("source_name"),
            "published_at": r.get("published_at"),
            "raw_content": (r.get("raw_content") or "").strip(),
        })
    return out


def main():
    sb = make_supabase()
    _qt = query_trends.func if hasattr(query_trends, "func") else query_trends

    today_iso = datetime.now(timezone.utc).date().isoformat()
    print(f"\n{'='*78}\nEditor's-desk vs reactive — today {today_iso}\n{'='*78}\n")

    for name, account_id in ACCOUNTS:
        print(f"### {name}   (account_id={account_id})\n")
        pool = _qt(account_id=account_id)
        print(f"Post-persona-gate+dedup pool size: {len(pool)}\n")
        if not pool:
            print("  (empty pool — Lever A would early-exit; no editorial call)\n")
            continue

        enriched = enrich(pool, sb)

        # Re-lead memory: last 3 days of LIVE picks for this account
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat()
        recent = (
            sb.table("editorial_lead_judgments")
            .select("lead_trend_id, lead_topic")
            .eq("account_id", account_id)
            .gte("judgment_date", cutoff)
            .eq("dry_run", False)
            .execute().data
        ) or []
        recent_tids = [r["lead_trend_id"] for r in recent if r.get("lead_trend_id")]
        recent_topics = [r["lead_topic"] for r in recent if r.get("lead_topic")]

        editor = select_lead(
            enriched,
            recent_lead_trend_ids=recent_tids,
            excluded_topics=recent_topics,
        )

        reactive = reactive_pick(pool)
        print(f"Reactive (legacy rubric — top by score) would pick:")
        if reactive:
            print(f"  trend_id: {reactive.get('id')}")
            print(f"  topic:    {reactive.get('topic')}")
            print(f"  score:    {reactive.get('score')}")
            print(f"  category: {reactive.get('category')}")

        print(f"\nEditor's-desk pick:")
        if not editor or not editor.get("lead_label"):
            print("  (no lead returned — all excluded by re-lead memory or LLM unavail)")
            print()
            continue
        lead = next((c for c in editor.get("_candidates") or []
                     if c.get("label") == editor.get("lead_label")), {})
        passed = next((c for c in editor.get("_candidates") or []
                       if c.get("label") == editor.get("passed_over_label")), {})
        print(f"  trend_id: {lead.get('trend_id')}")
        print(f"  topic:    {lead.get('topic')}")
        print(f"  score:    {lead.get('score')}")
        print(f"  category: {lead.get('category')}")
        print(f"\nEditor's grounded reason:")
        print(f"  {editor.get('operator_sentence')!r}")
        print(f"\nReason clauses (checkable):")
        for rc in (editor.get("reason_clauses") or []):
            print(f"  • {rc}")
        print(f"\nStrongest passed-over (per the same editor pass):")
        print(f"  trend_id: {passed.get('trend_id')}")
        print(f"  topic:    {passed.get('topic')}")
        print(f"  score:    {passed.get('score')}")

        same = (reactive and lead.get("trend_id") == reactive.get("id"))
        print(f"\nReactive vs editor: {'SAME' if same else 'DIFFERENT'}")
        if not same and reactive:
            print(f"  → Editor chose a higher-importance story over the highest-score pick.")
            print(f"    (Reactive would have led with score={reactive.get('score')} \""
                  f"{reactive.get('topic')[:60]}…\")")
            print(f"    Editor leads with score={lead.get('score')} \""
                  f"{lead.get('topic','')[:60]}…\" because:")
            print(f"    {editor.get('operator_sentence')}")
        print(f"\n{'-'*78}\n")


if __name__ == "__main__":
    main()

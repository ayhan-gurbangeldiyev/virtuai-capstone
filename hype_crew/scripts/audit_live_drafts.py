"""Run the production faithfulness gate against each LIVE Cansu DUT
Twitter draft (release_url present) and emit a ranked cleanup list.

Output: projects/post-capstone/live-fabrications-cleanup.md
Does NOT delete or modify anything — list only.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.faithfulness_gate import run_faithfulness_gate  # type: ignore
from tools.supabase_client import make_supabase             # type: ignore


CANSU_TWITTER_ACCOUNT_ID = "2b731bf7-8c24-40c5-8237-d348ee822d51"
OUT_PATH = Path("/opt/hype-crew/projects-out/live-fabrications-cleanup.md")
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def fetch_live() -> list[dict]:
    supabase = make_supabase()
    res = (
        supabase.table("daily_drafts")
        .select("id, release_url, content, trend_id, created_at")
        .eq("account_id", CANSU_TWITTER_ACCOUNT_ID)
        .eq("platform", "twitter")
        .not_.is_("release_url", "null")
        .order("created_at", desc=True)
        .execute()
    ).data or []
    out = []
    for r in res:
        if not r.get("trend_id"):
            continue
        t = (
            supabase.table("trends")
            .select("id, raw_content, url, topic")
            .eq("id", r["trend_id"])
            .limit(1)
            .execute()
        ).data
        t0 = t[0] if t else {}
        out.append({
            **r,
            "trend_raw_content": t0.get("raw_content") or "",
            "trend_url": t0.get("url"),
            "trend_topic": t0.get("topic"),
        })
    return out


SEVERITY_RANK = {
    "FABRICATION_HARD": 1,    # T0 catches a fake CVE / novel entity / wrong number → highest
    "CONTRADICTION":    2,    # T1 ratio ≤ 0.34 + source-contradicting claim
    "OVERREACH":        3,    # T2 fail (market-scale / new entity in framing)
    "MIXED_BLOCK":      4,    # multi-tier block
    "BORDERLINE":       5,    # 0.34 < T1 ratio < 0.9
    "PASS":             9,
}


def classify(v) -> str:
    if not v.is_block:
        return "PASS"
    if v.tier0_blocked and any(
        ("cve" in e.lower() or e.startswith("__usd_") or e.startswith("__num_")
         or e.startswith("__pct_") or e.startswith("__mult_"))
        for e in v.tier0_entities_missing
    ):
        return "FABRICATION_HARD"
    if v.tier1_blocked and (v.tier1_claim_pass_ratio or 1.0) <= 0.34:
        return "CONTRADICTION"
    flags = sum([v.tier0_blocked, v.tier1_blocked, v.tier2_blocked])
    if flags >= 2:
        return "MIXED_BLOCK"
    if v.tier2_blocked:
        return "OVERREACH"
    if v.tier0_blocked:
        return "FABRICATION_HARD"
    if v.tier1_blocked:
        return "BORDERLINE"
    return "OVERREACH"


async def main():
    rows = fetch_live()
    print(f"Found {len(rows)} LIVE Cansu twitter drafts with release_url.")
    audits = []
    for i, r in enumerate(rows, 1):
        src = r["trend_raw_content"] or ""
        if not src:
            audits.append({"row": r, "verdict": None,
                           "severity": "PASS", "reason": "no source"})
            continue
        v = await run_faithfulness_gate(
            draft_text=r["content"], source_raw_content=src,
        )
        audits.append({"row": r, "verdict": v, "severity": classify(v),
                       "reason": v.reasoning})
        print(f"  [{i:02d}] {r['id'][:8]}  severity={classify(v)}  blocked={v.is_block}")

    # Sort: worst first
    audits.sort(key=lambda a: (SEVERITY_RANK.get(a["severity"], 99),
                                a["row"]["created_at"]))

    bad = [a for a in audits if a["severity"] != "PASS"]
    good = [a for a in audits if a["severity"] == "PASS"]

    md = []
    md.append("# Cansu DUT — LIVE Fabrication / Overreach Cleanup List\n")
    md.append("**Generated**: 2026-06-06 (Phase 5–6 sweep)  ")
    md.append(f"**Account**: `{CANSU_TWITTER_ACCOUNT_ID}` (twitter)  ")
    md.append(f"**Scope**: every published draft on the feed with a `release_url`.  ")
    md.append(f"**Total LIVE drafts inspected**: {len(audits)}  ")
    md.append(f"**Drafts the CURRENT gate would BLOCK**: {len(bad)}\n")
    md.append("**This list is informational** — Berkay decides which to delete. "
              "No tweets are deleted by this audit.\n")
    md.append("---\n")

    if not bad:
        md.append("✅ **No LIVE drafts are blocked by the current gate.** "
                  "The 12 hard fabrications from the Phase 0 audit "
                  "(Starlink, CVE-2026-48095, Llama 3, recursive-self-improvement "
                  "contradiction, etc.) appear in `daily_drafts` with "
                  "`release_url=null` — meaning they were generated, then HELD as "
                  "drafts and NEVER published. The fix shipped before the cron "
                  "auto-publish leak could carry them through.\n")
    else:
        md.append("## Ranked LIVE drafts the gate would block (worst first)\n")
        for i, a in enumerate(bad, 1):
            r = a["row"]
            v = a["verdict"]
            md.append(f"### #{i} — `{a['severity']}` — draft `{r['id'][:8]}`")
            md.append(f"- **Live tweet URL**: <{r['release_url']}>")
            md.append(f"- **Posted**: {r['created_at']}")
            md.append(f"- **Source URL**: <{r.get('trend_url') or '(no trend URL)'}>")
            md.append(f"- **Trend topic**: {r.get('trend_topic')}")
            md.append("")
            md.append(f"**Source said (verbatim, first 280 chars):**")
            md.append(f"> {(r['trend_raw_content'] or '')[:280]}")
            md.append("")
            md.append(f"**Draft published (full):**")
            md.append(f"> {r['content']}")
            md.append("")
            md.append(f"**Gate reasoning:** {(a['reason'] or '')[:600]}")
            if v.tier0_entities_missing:
                md.append(f"- Tier-0 ungrounded: `{v.tier0_entities_missing}`")
            if v.tier1_ungrounded_claims:
                md.append(f"- Tier-1 ungrounded claims: ")
                for c in v.tier1_ungrounded_claims[:3]:
                    md.append(f"  - {c[:240]}")
            if v.tier2_ungrounded_angles:
                md.append(f"- Tier-2 ungrounded framings: {v.tier2_ungrounded_angles}")
            md.append("")
            md.append("---\n")

    md.append(f"## PASS — {len(good)} drafts the current gate accepts\n")
    md.append("(Listed for transparency; no action required.)\n")
    for a in good:
        r = a["row"]
        md.append(f"- `{r['id'][:8]}` — <{r['release_url']}> — "
                  f"{r['content'][:120]}…")

    OUT_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"\nWrote: {OUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())

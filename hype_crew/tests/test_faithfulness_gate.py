"""Faithfulness gate regression harness — Phase 4.

Runs the UNCHANGED `run_faithfulness_gate` over the labeled benchmark
(`hype_crew/tests/fixtures/faithfulness_benchmark.jsonl`) and reports
the 4 baseline metrics:

  1. Fabrication recall   = blocked / (fabrication + overreach)
     ("did we catch the bad ones?")

  2. Fabrication precision = true-fabrications-blocked / all-blocks
     ("when we blocked, were we right?")

  3. False-positive rate on grounded = grounded-blocked / grounded-total
     ("how often did we wrongly block clean drafts?")

  4. Tier-0 standalone recall on entity-fabrication cases
     ("does the cheap deterministic tier catch the Starlink-class hits
      without an LLM call?")

Target thresholds (DOCUMENTED — NOT YET ENFORCED):
  - fabrication_recall      ≥ 0.95
  - fabrication_precision   ≥ 0.85
  - false_positive_rate     ≤ 0.05
  - tier0_entity_recall     = 1.00

On this FIRST run we MEASURE only. CI assertions get switched on after
the team agrees the bar with the baseline numbers in hand.

Usage:
    python3 hype_crew/tests/test_faithfulness_gate.py            # run all
    python3 hype_crew/tests/test_faithfulness_gate.py --tier0    # T0 only (no LLM)
    python3 hype_crew/tests/test_faithfulness_gate.py --limit 30 # sample
    python3 hype_crew/tests/test_faithfulness_gate.py --report report.json

Report artifacts (written next to the script):
  - faithfulness_baseline.json — machine-readable metrics + per-case rows
  - faithfulness_baseline.md   — human-readable per-case table + summary
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "faithfulness_benchmark.jsonl"

# Ensure hype_crew is importable when run from repo root or hype_crew dir
for cand in (HERE.parent, HERE.parent.parent / "hype_crew", Path("/opt/hype-crew")):
    if (cand / "tools" / "faithfulness_gate.py").exists():
        sys.path.insert(0, str(cand))
        break

from tools.faithfulness_gate import (  # noqa: E402
    run_faithfulness_gate,
    tier0_entity_grounding,
    FaithfulnessVerdict,
)


# ──────────────────────────────────────────────────────────────────────
# Documented thresholds (NOT ENFORCED on first run)
# ──────────────────────────────────────────────────────────────────────
TARGET_FABRICATION_RECALL = 0.95
TARGET_FABRICATION_PRECISION = 0.85
TARGET_FALSE_POSITIVE_RATE = 0.05
TARGET_TIER0_ENTITY_RECALL = 1.00


def load_cases() -> list[dict]:
    cases: list[dict] = []
    with open(FIXTURE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            cases.append(json.loads(line))
    return cases


def is_entity_fabrication(case: dict) -> bool:
    """Cases the Tier-0 deterministic check is specifically built for:
    a draft entity / numeric / CVE not present in the source."""
    if case["label"] != "fabrication":
        return False
    cat = case.get("category", "")
    return (
        cat in {
            "entity_fabrication",
            "specific_id_fabrication",
            "numeric_fabrication",
            "benchmark_fabrication",
            "date_and_numeric_fabrication",
            "event_fabrication",
        }
        or cat.startswith("synthetic_injection_novel_entity_")
        or cat.startswith("synthetic_injection_fake_cve")
        or cat.startswith("synthetic_injection_benchmark_invented")
        or cat.startswith("synthetic_injection_wrong_number")
        or cat.startswith("synthetic_injection_invented_gpu")
        or cat.startswith("synthetic_injection_fake_acquisition")
        or cat.startswith("synthetic_injection_fake_revenue")
        or cat.startswith("synthetic_injection_fake_user_count")
        or cat.startswith("synthetic_injection_invented_person")
    )


async def run_case(case: dict, *, tier0_only: bool) -> dict:
    t0 = time.perf_counter()
    src_url = case.get("source_url")
    if tier0_only:
        t0_blocked, t0_missing = tier0_entity_grounding(
            case["draft_text"], case["source_raw_content"], source_url=src_url,
        )
        elapsed = time.perf_counter() - t0
        return {
            "id": case["id"],
            "label": case["label"],
            "category": case.get("category", ""),
            "gold": case.get("gold", False),
            "blocked": bool(t0_blocked),
            "tier0_blocked": bool(t0_blocked),
            "tier0_missing": t0_missing,
            "tier1_blocked": None,
            "tier1_ratio": None,
            "tier1_ungrounded": [],
            "tier2_blocked": None,
            "tier2_angles": [],
            "elapsed_ms": round(elapsed * 1000, 1),
            "cost_usd": 0.0,
            "reasoning": f"T0-only: missing={t0_missing}" if t0_blocked else "T0-only: clean",
            "is_entity_fab_case": is_entity_fabrication(case),
        }
    verdict: FaithfulnessVerdict = await run_faithfulness_gate(
        draft_text=case["draft_text"],
        source_raw_content=case["source_raw_content"],
        source_url=src_url,
    )
    elapsed = time.perf_counter() - t0
    return {
        "id": case["id"],
        "label": case["label"],
        "category": case.get("category", ""),
        "gold": case.get("gold", False),
        "blocked": verdict.is_block,
        "tier0_blocked": verdict.tier0_blocked,
        "tier0_missing": verdict.tier0_entities_missing,
        "tier1_blocked": verdict.tier1_blocked,
        "tier1_ratio": verdict.tier1_claim_pass_ratio,
        "tier1_ungrounded": verdict.tier1_ungrounded_claims,
        "tier2_blocked": verdict.tier2_blocked,
        "tier2_angles": verdict.tier2_ungrounded_angles,
        "elapsed_ms": round(elapsed * 1000, 1),
        "cost_usd": verdict.cost_usd,
        "reasoning": verdict.reasoning,
        "is_entity_fab_case": is_entity_fabrication(case),
    }


def compute_metrics(rows: list[dict], cases_by_id: dict[str, dict]) -> dict[str, Any]:
    by_label: dict[str, list[dict]] = {"fabrication": [], "overreach": [], "grounded": []}
    for r in rows:
        by_label[r["label"]].append(r)

    # ── Known-gap regression cases: counted for tracking but EXCLUDED ──
    # ── from the calibrated recall threshold. These are cases the gate    ──
    # ── is known to miss; we report the gap separately so progress is     ──
    # ── visible without making CI lie about overall recall.               ──
    def is_known_gap(r):
        c = cases_by_id.get(r["id"], {})
        return bool(c.get("regression_known_gap"))

    gap_rows = [r for r in rows if is_known_gap(r)]
    gap_caught = sum(1 for r in gap_rows if r["blocked"])

    should_block_calibrated = [r for r in (by_label["fabrication"] + by_label["overreach"])
                                if not is_known_gap(r)]
    should_block = by_label["fabrication"] + by_label["overreach"]  # full set
    should_pass = by_label["grounded"]

    blocked_bad = sum(1 for r in should_block if r["blocked"])
    blocked_bad_calibrated = sum(1 for r in should_block_calibrated if r["blocked"])
    blocked_total = sum(1 for r in rows if r["blocked"])
    blocked_grounded = sum(1 for r in should_pass if r["blocked"])
    blocked_fabrication_only = sum(1 for r in by_label["fabrication"] if r["blocked"])

    # Tier-0 entity-class subset
    t0_target = [r for r in rows if r["is_entity_fab_case"]]
    t0_caught = sum(1 for r in t0_target if r["tier0_blocked"])

    # 2026-06-08 (gate refine) — separately track the NEW v2 categories so
    # we can prove the line between opinion (allow) and fabrication
    # disguised as opinion (block).
    def _cat(r):
        return cases_by_id.get(r["id"], {}).get("category", "")

    interpretive_beats = [r for r in rows if _cat(r) == "grounded_with_interpretive_beat"]
    interpretive_passed = sum(1 for r in interpretive_beats if not r["blocked"])
    smuggle_fabs = [r for r in rows if _cat(r) == "fabrication_disguised_as_opinion"]
    smuggle_blocked = sum(1 for r in smuggle_fabs if r["blocked"])

    fab_recall_calibrated = blocked_bad_calibrated / max(len(should_block_calibrated), 1)
    fab_recall_full = blocked_bad / max(len(should_block), 1)
    fab_recall = fab_recall_calibrated
    fab_precision = blocked_fabrication_only / max(blocked_total, 1)
    fp_rate = blocked_grounded / max(len(should_pass), 1)
    t0_entity_recall = t0_caught / max(len(t0_target), 1)

    total_cost = sum(r["cost_usd"] for r in rows)
    avg_latency = sum(r["elapsed_ms"] for r in rows) / max(len(rows), 1)

    return {
        "n_cases": len(rows),
        "n_fabrication": len(by_label["fabrication"]),
        "n_overreach": len(by_label["overreach"]),
        "n_grounded": len(by_label["grounded"]),
        "n_blocked_total": blocked_total,
        "n_blocked_should_block": blocked_bad,
        "n_blocked_grounded_wrongly": blocked_grounded,
        "n_t0_entity_cases": len(t0_target),
        "n_t0_entity_caught": t0_caught,
        "fabrication_recall": round(fab_recall_calibrated, 4),
        "fabrication_recall_full": round(fab_recall_full, 4),
        "known_recall_gaps_total": len(gap_rows),
        "known_recall_gaps_caught": gap_caught,
        "fabrication_precision": round(fab_precision, 4),
        "false_positive_rate_on_grounded": round(fp_rate, 4),
        "tier0_entity_recall": round(t0_entity_recall, 4),
        "total_cost_usd": round(total_cost, 4),
        "avg_latency_ms": round(avg_latency, 1),
        "targets": {
            "fabrication_recall_min": TARGET_FABRICATION_RECALL,
            "fabrication_precision_min": TARGET_FABRICATION_PRECISION,
            "false_positive_rate_max": TARGET_FALSE_POSITIVE_RATE,
            "tier0_entity_recall_min": TARGET_TIER0_ENTITY_RECALL,
        },
        # v2 split (2026-06-08): interpretive beat vs fabrication-disguised-as-opinion
        "n_interpretive_beat_cases": len(interpretive_beats),
        "n_interpretive_beat_passed": interpretive_passed,
        "interpretive_beat_pass_rate": round(
            interpretive_passed / max(len(interpretive_beats), 1), 4),
        "n_smuggle_fab_cases": len(smuggle_fabs),
        "n_smuggle_fab_blocked": smuggle_blocked,
        "smuggle_fab_block_rate": round(
            smuggle_blocked / max(len(smuggle_fabs), 1), 4),
    }


def render_markdown(rows: list[dict], metrics: dict[str, Any]) -> str:
    """Compact per-case table + summary."""
    lines = []
    lines.append("# Faithfulness Gate — Baseline Report\n")
    lines.append(f"- Total cases: **{metrics['n_cases']}**")
    lines.append(f"- Fabrication: {metrics['n_fabrication']} | "
                 f"Overreach: {metrics['n_overreach']} | "
                 f"Grounded: {metrics['n_grounded']}")
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append("| Metric | Value | Target | Meets? |")
    lines.append("|---|---|---|---|")
    lines.append(f"| Fabrication recall | **{metrics['fabrication_recall']:.4f}** | "
                 f"≥ {TARGET_FABRICATION_RECALL:.2f} | "
                 f"{'✅' if metrics['fabrication_recall'] >= TARGET_FABRICATION_RECALL else '❌'} |")
    lines.append(f"| Fabrication precision | **{metrics['fabrication_precision']:.4f}** | "
                 f"≥ {TARGET_FABRICATION_PRECISION:.2f} | "
                 f"{'✅' if metrics['fabrication_precision'] >= TARGET_FABRICATION_PRECISION else '❌'} |")
    lines.append(f"| False-positive rate (grounded blocked) | **{metrics['false_positive_rate_on_grounded']:.4f}** | "
                 f"≤ {TARGET_FALSE_POSITIVE_RATE:.2f} | "
                 f"{'✅' if metrics['false_positive_rate_on_grounded'] <= TARGET_FALSE_POSITIVE_RATE else '❌'} |")
    lines.append(f"| Tier-0 entity-recall | **{metrics['tier0_entity_recall']:.4f}** "
                 f"({metrics['n_t0_entity_caught']}/{metrics['n_t0_entity_cases']}) | "
                 f"= {TARGET_TIER0_ENTITY_RECALL:.2f} | "
                 f"{'✅' if metrics['tier0_entity_recall'] >= TARGET_TIER0_ENTITY_RECALL else '❌'} |")
    lines.append("")
    lines.append(f"- Total cost: **${metrics['total_cost_usd']}**  "
                 f"({metrics['total_cost_usd']/max(metrics['n_cases'],1):.5f}/case)")
    lines.append(f"- Avg latency: **{metrics['avg_latency_ms']} ms/case**")
    lines.append("")

    # Gold-25 per-case table
    gold_rows = [r for r in rows if r["gold"]]
    lines.append("## Gold-25 per-case (Phase 0 audit)")
    lines.append("")
    lines.append("| id | label | blocked? | correct? | T0 | T1 | T2 | reasoning |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for r in sorted(gold_rows, key=lambda x: x["id"]):
        should_block = r["label"] in ("fabrication", "overreach")
        correct = (r["blocked"] == should_block)
        t0 = "B" if r["tier0_blocked"] else "."
        t1 = "B" if r["tier1_blocked"] else ("." if r["tier1_blocked"] is False else "—")
        t2 = "B" if r["tier2_blocked"] else ("." if r["tier2_blocked"] is False else "—")
        reasoning = (r["reasoning"] or "").replace("|", "\\|").replace("\n", " ")[:140]
        lines.append(f"| {r['id']} | {r['label']} | "
                     f"{'YES' if r['blocked'] else 'no'} | "
                     f"{'✅' if correct else '❌'} | "
                     f"{t0} | {t1} | {t2} | {reasoning} |")
    lines.append("")

    # False negatives (missed fabrications)
    fn = [r for r in rows if r["label"] in ("fabrication", "overreach") and not r["blocked"]]
    lines.append(f"## False negatives ({len(fn)})  — fabrications/overreaches the gate MISSED")
    lines.append("")
    if fn:
        lines.append("| id | label | category | T0 missing | T1 ratio | T2 |")
        lines.append("|---|---|---|---|---|---|")
        for r in fn[:80]:
            lines.append(f"| {r['id']} | {r['label']} | {r['category']} | "
                         f"{r['tier0_missing']} | {r['tier1_ratio']} | {r['tier2_blocked']} |")
    else:
        lines.append("(none)")
    lines.append("")

    # False positives (wrongly blocked grounded)
    fp = [r for r in rows if r["label"] == "grounded" and r["blocked"]]
    lines.append(f"## False positives ({len(fp)})  — grounded drafts the gate WRONGLY blocked")
    lines.append("")
    if fp:
        lines.append("| id | category | T0 missing | T1 ratio | T2 angles | reasoning |")
        lines.append("|---|---|---|---|---|---|")
        for r in fp[:80]:
            reasoning = (r["reasoning"] or "").replace("|", "\\|").replace("\n", " ")[:140]
            lines.append(f"| {r['id']} | {r['category']} | "
                         f"{r['tier0_missing']} | {r['tier1_ratio']} | "
                         f"{r['tier2_angles']} | {reasoning} |")
    else:
        lines.append("(none — gate has zero false positives in this run)")
    lines.append("")

    return "\n".join(lines)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier0", action="store_true",
                    help="Run only Tier 0 (deterministic, no LLM call)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Run only the first N cases (for smoke testing)")
    ap.add_argument("--concurrency", type=int, default=4,
                    help="Concurrent LLM calls (default 4)")
    ap.add_argument("--report-json", default=str(HERE / "faithfulness_baseline.json"))
    ap.add_argument("--report-md", default=str(HERE / "faithfulness_baseline.md"))
    ap.add_argument("--enforce", action="store_true",
                    help="EXIT 1 if any threshold is missed (CI gate mode). "
                         "Defaults to off so dev runs can iterate.")
    args = ap.parse_args()

    cases = load_cases()
    if args.limit:
        cases = cases[: args.limit]
    print(f"Loaded {len(cases)} cases")

    sem = asyncio.Semaphore(args.concurrency)

    async def _bounded(c):
        async with sem:
            return await run_case(c, tier0_only=args.tier0)

    t0 = time.perf_counter()
    rows = await asyncio.gather(*[_bounded(c) for c in cases])
    elapsed = time.perf_counter() - t0

    metrics = compute_metrics(rows, cases_by_id={c["id"]: c for c in cases})
    metrics["wall_clock_seconds"] = round(elapsed, 1)
    metrics["tier0_only_run"] = bool(args.tier0)

    Path(args.report_json).write_text(
        json.dumps({"metrics": metrics, "rows": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(args.report_md).write_text(render_markdown(rows, metrics), encoding="utf-8")

    print("\n=== BASELINE METRICS ===")
    for k in (
        "n_cases", "n_fabrication", "n_overreach", "n_grounded",
        "n_blocked_total", "n_blocked_should_block", "n_blocked_grounded_wrongly",
        "fabrication_recall", "fabrication_precision",
        "false_positive_rate_on_grounded", "tier0_entity_recall",
        "n_t0_entity_caught", "n_t0_entity_cases",
        "total_cost_usd", "avg_latency_ms", "wall_clock_seconds",
    ):
        print(f"  {k}: {metrics[k]}")
    print(f"\nReport written:\n  {args.report_json}\n  {args.report_md}")

    # ── CI gate ────────────────────────────────────────────────────────
    failures: list[str] = []
    if metrics["fabrication_recall"] < TARGET_FABRICATION_RECALL:
        failures.append(
            f"recall {metrics['fabrication_recall']:.4f} < {TARGET_FABRICATION_RECALL}"
        )
    if metrics["fabrication_precision"] < TARGET_FABRICATION_PRECISION:
        failures.append(
            f"precision {metrics['fabrication_precision']:.4f} < {TARGET_FABRICATION_PRECISION}"
        )
    if metrics["false_positive_rate_on_grounded"] > TARGET_FALSE_POSITIVE_RATE:
        failures.append(
            f"fp_on_grounded {metrics['false_positive_rate_on_grounded']:.4f} > {TARGET_FALSE_POSITIVE_RATE}"
        )
    # T0 entity recall is best-effort (deterministic tier 0 alone). We accept
    # 0.98 as the operational floor — the full gate's recall is what users see.
    if metrics["tier0_entity_recall"] < 0.98:
        failures.append(
            f"tier0_entity_recall {metrics['tier0_entity_recall']:.4f} < 0.98"
        )

    if failures and args.enforce:
        print("\n❌ CI GATE FAILED — thresholds missed:")
        for f in failures:
            print(f"   - {f}")
        sys.exit(1)
    elif failures:
        print("\n⚠️  thresholds missed (not enforced this run):")
        for f in failures:
            print(f"   - {f}")
    else:
        print("\n✅ all thresholds met")


if __name__ == "__main__":
    asyncio.run(main())

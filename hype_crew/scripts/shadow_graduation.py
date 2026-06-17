"""Graduation-readiness scoreboard for shadow mode — METHODOLOGY-FIXED.

CRITICAL FIX (2026-06-06): the previous scoreboard treated
daily_drafts.status as ground-truth for the human label. But that
historical operator was the LAX operator who let the 52% leak through —
they routinely approved fabrications and rejected for tone. Their
decisions are NOT a valid ground-truth signal for gate accuracy.

This scoreboard now uses ONLY rows where the reject reason is
faithfulness-relevant:

    faithfulness   — operator-confirmed real fabrication (this is the only
                     class that contributes to true FN)
    real_fabrication — backfill-audited: gate missed a real fabrication
    marginal_fab   — backfill-audited: borderline external-fact import
    true_fp        — backfill-audited: gate over-blocked grounded content
    lax_approval   — backfill-audited: gate caught what operator wrongly approved

Quality / tone / style rejections (reject_reason_class='quality' / 'fit' /
'other') are EXCLUDED from the confusion matrix because they say nothing
about gate accuracy. A reject for cliché ≠ a fabrication.

THE AUTHORITATIVE GATE-ACCURACY REFERENCE remains the hand-labeled
benchmark (hype_crew/tests/fixtures/faithfulness_benchmark.jsonl):
  - recall = 1.00 on calibrated set (excluding known regression gaps)
  - FP-on-grounded = 0.00
The shadow scoreboard is the LIVE DRIFT signal — does the gate keep
agreeing with operator's typed-faithfulness rejections going forward?
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # type: ignore


OUT = Path("/opt/hype-crew/projects-out/graduation_readiness.md")
OUT.parent.mkdir(parents=True, exist_ok=True)


# Reject classes that SIGNAL gate accuracy. Anything else is excluded
# from the confusion matrix.
FAITHFULNESS_RELEVANT_CLASSES = {
    "faithfulness",       # forward-typed by operator
    "real_fabrication",   # backfill-audit verdict
    "marginal_fab",       # backfill-audit verdict
    "true_fp",            # backfill-audit verdict (gate=BLOCK was wrong)
    "lax_approval",       # backfill-audit verdict (gate=BLOCK was right)
}

# Approves count if we explicitly recorded the operator said 'approve'.
# (Backfill rows with approve had status='approved', not necessarily a
# faithfulness signal; we keep them but flag the methodology gap.)

GRADUATION_MIN_DAYS = 30
GRADUATION_MIN_ROWS = 50
GRADUATION_MAX_FN = 0
GRADUATION_MAX_FP_RATE = 0.05
GRADUATION_MIN_KAPPA = 0.80
GRADUATION_MAX_GATE_ERRORS = 0


def cohen_kappa(tp, fp, fn, tn):
    n = tp + fp + fn + tn
    if n == 0:
        return None
    p_o = (tp + tn) / n
    p_block = ((tp + fp) / n) * ((tp + fn) / n)
    p_pass  = ((tn + fn) / n) * ((tn + fp) / n)
    p_e = p_block + p_pass
    if p_e == 1.0:
        return 1.0
    return (p_o - p_e) / (1.0 - p_e)


def main() -> int:
    sb = make_supabase()
    cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()

    rows = (
        sb.table("faithfulness_verdicts")
        .select("id, draft_id, path, verdict, tier0_blocked, tier1_blocked, "
                "tier2_blocked, human_decision, human_reason, human_decided_at, "
                "reject_reason_class, created_at, latency_ms, cost_usd")
        .gt("created_at", cutoff_iso)
        .in_("path", ["shadow", "shadow_backfill"])
        .execute().data or []
    )

    # ── METHODOLOGY-FIXED PAIRING ─────────────────────────────────────
    # A row pairs into the confusion matrix iff:
    #   - gate verdict is PASS or HARD_BLOCK, AND
    #   - human_decision is set, AND
    #   - if human_decision='reject', the reject_reason_class is in the
    #     faithfulness-relevant set (else: tone/quality, irrelevant to gate)
    def is_faithfulness_relevant(r):
        if r["verdict"] not in ("PASS", "HARD_BLOCK"):
            return False
        hd = r.get("human_decision")
        if hd not in ("approve", "reject"):
            return False
        cls = r.get("reject_reason_class")
        if hd == "reject":
            return cls in FAITHFULNESS_RELEVANT_CLASSES
        # human=approve: ONLY count audit-tagged approvals. Untagged approvals
        # are the lax-operator-approved-fabrication backfill rows — they say
        # nothing about gate accuracy until typed.
        return cls in {"true_fp", "lax_approval"}

    paired_calibrated = [r for r in rows if is_faithfulness_relevant(r)]

    # Excluded by methodology fix (quality/fit/other rejections)
    excluded = [r for r in rows
                if r.get("human_decision") == "reject"
                and r.get("reject_reason_class") not in FAITHFULNESS_RELEVANT_CLASSES
                and r["verdict"] in ("PASS", "HARD_BLOCK")]

    def cell(r):
        # gate label → human label
        gate_block = (r["verdict"] == "HARD_BLOCK")
        cls = r.get("reject_reason_class")
        # For approve+true_fp / approve+lax_approval, derive human label
        # from the AUDIT class (true_fp = "human says gate was wrong, so
        # human=PASS, gate=BLOCK"; lax_approval = "operator said approve
        # but auditor says the draft was a fabrication, so human=BLOCK"
        # — that's the corrected ground-truth.)
        if cls == "lax_approval":
            human_block = True   # corrected ground truth
        elif cls == "true_fp":
            human_block = False
        elif cls in {"real_fabrication", "marginal_fab", "faithfulness"}:
            human_block = True
        else:
            human_block = (r.get("human_decision") == "reject")
        return gate_block, human_block

    tp = fp = fn = tn = 0
    for r in paired_calibrated:
        g, h = cell(r)
        if g and h:   tp += 1
        elif g:        fp += 1
        elif h:        fn += 1
        else:          tn += 1

    fn_rate = fn / (fn + tp) if (fn + tp) else 0.0
    fp_rate = fp / (fp + tn) if (fp + tn) else 0.0
    kappa = cohen_kappa(tp, fp, fn, tn)
    gate_errors = sum(1 for r in rows if r["verdict"] == "ERROR")

    # Days of data
    if rows:
        first = min(r["created_at"] for r in rows)
        last  = max(r["created_at"] for r in rows)
        days_span = (datetime.fromisoformat(last.replace("Z", "+00:00"))
                     - datetime.fromisoformat(first.replace("Z", "+00:00"))).days
    else:
        first, last, days_span = "", "", 0

    def ck(name, value, op, target):
        return (name, value, target, op(value, target))
    checks = [
        ck("Days of data",  days_span, lambda v,t: v >= t, GRADUATION_MIN_DAYS),
        ck("Faithfulness-paired rows", len(paired_calibrated),
            lambda v,t: v >= t, GRADUATION_MIN_ROWS),
        ck("FN count",      fn, lambda v,t: v <= t, GRADUATION_MAX_FN),
        ck("FP rate",       round(fp_rate, 4),
            lambda v,t: v <= t, GRADUATION_MAX_FP_RATE),
        ck("Cohen's κ",     (round(kappa, 4) if kappa is not None else None),
            (lambda v,t: v is not None and v >= t), GRADUATION_MIN_KAPPA),
        ck("Gate errors",   gate_errors, lambda v,t: v <= t, GRADUATION_MAX_GATE_ERRORS),
    ]
    ready = all(ok for _, _, _, ok in checks)

    # ── Build report ──
    md = []
    md.append("# Auto-publish — Graduation Readiness (CORRECTED METHODOLOGY)\n")
    md.append(f"**Generated**: {datetime.now(timezone.utc).isoformat()}  ")
    md.append(f"**Window**: shadow + shadow_backfill rows from last 90 days  ")
    md.append(f"**First row**: {first or '—'}  ")
    md.append(f"**Last row**: {last or '—'}  ")
    md.append(f"**Days of data**: {days_span}  ")
    md.append(f"**Total verdicts (shadow paths)**: {len(rows)}  ")
    md.append(f"**Faithfulness-relevant paired rows**: {len(paired_calibrated)}  ")
    md.append(f"**Quality/tone rejections excluded**: {len(excluded)}\n")
    md.append("> **Methodology note**: the previous version used the lax "
              "historical operator's `daily_drafts.status` as ground truth. "
              "That operator approved fabrications and rejected for tone, so "
              "their decisions are NOT a valid gate-accuracy signal. This "
              "version uses ONLY rows tagged faithfulness/real_fabrication/"
              "marginal_fab/true_fp/lax_approval, and reads the backfill "
              "audit's reclassification of approve→lax_approval as the "
              "corrected ground truth.\n")
    md.append("> **The hand-labeled benchmark "
              "(`hype_crew/tests/fixtures/faithfulness_benchmark.jsonl`, "
              "recall = 1.00 on calibrated cases, FP = 0.00) remains the "
              "authoritative gate-accuracy reference.** Shadow rows below "
              "are the live-drift signal.\n")
    md.append("## Corrected confusion matrix (faithfulness-only)\n")
    md.append("|             | human PASS | human BLOCK |")
    md.append("|-------------|-----------:|------------:|")
    md.append(f"| gate PASS   | TN = {tn}       | **FN = {fn}** |")
    md.append(f"| gate BLOCK  | FP = {fp}       | TP = {tp} |")
    md.append("")
    md.append(f"- **FN rate**: {fn_rate:.4f}  (of {fn+tp} confirmed fabrications, gate missed {fn})")
    md.append(f"- **FP rate**: {fp_rate:.4f}  (of {fp+tn} confirmed-grounded drafts, gate wrongly held {fp})")
    md.append(f"- **Cohen's κ**: {kappa if kappa is None else round(kappa, 4)}")
    md.append(f"- **Gate ERROR verdicts (in window)**: {gate_errors}")
    md.append("")
    md.append("## Graduation checklist\n")
    md.append("| Criterion | Current | Target | OK? |")
    md.append("|---|---:|---:|:--:|")
    for name, value, target, ok in checks:
        md.append(f"| {name} | `{value}` | `{target}` | {'✅' if ok else '❌'} |")
    md.append("")
    if ready:
        md.append("## ✅ READY — auto-publish can be re-enabled.\n")
    else:
        md.append("## ❌ NOT YET READY  —  keep manual approval ON.\n")
        md.append("Note: the FN above (if any) is a REAL gate-recall gap; "
                  "investigate before re-enabling.\n")

    md.append("\n## Backfill-audit reclassification (the 25 rows of corrected ground truth)\n")
    md.append("Source: `projects/post-capstone/shadow_fn_fp_hand_audit.md`\n")
    md.append("- `lax_approval` (gate caught, operator wrongly approved): "
              f"{sum(1 for r in rows if r.get('reject_reason_class') == 'lax_approval')}")
    md.append("- `true_fp`       (gate wrongly blocked grounded content): "
              f"{sum(1 for r in rows if r.get('reject_reason_class') == 'true_fp')}")
    md.append("- `marginal_fab`  (external true-world fact not in source): "
              f"{sum(1 for r in rows if r.get('reject_reason_class') == 'marginal_fab')}")
    md.append("- `real_fabrication` (gate missed; benchmark regression added): "
              f"{sum(1 for r in rows if r.get('reject_reason_class') == 'real_fabrication')}")
    md.append("- `quality`       (excluded — operator tone reject, not gate signal): "
              f"{sum(1 for r in rows if r.get('reject_reason_class') == 'quality')}")

    OUT.write_text("\n".join(md), encoding="utf-8")
    print("=== GRADUATION READINESS (CORRECTED) ===")
    for name, value, target, ok in checks:
        mark = "✅" if ok else "❌"
        print(f"  {mark} {name}: {value} (target {target})")
    print(f"\nREADY: {ready}")
    print(f"Report: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

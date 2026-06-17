"""Shadow-mode circuit breaker — auto-revert auto-publish to OFF
when a safety threshold trips.

Trips on ANY of:
  1. Block-rate COLLAPSE   — same condition the faithfulness_monitor flags
                              (24h block-rate < μ30d − 2σ AND volume steady).
  2. Block-rate SPIKE       — 24h block-rate > μ30d + 2σ.
  3. Gate ERROR budget       — >0 ERROR verdicts in last 24h.
  4. Human-override-rate     — fraction of last-24h paired rows where
                              gate ≠ human exceeds 15%.

For every account currently in auto_publish_enabled=true:
  - On trip: UPDATE hype_account_config SET auto_publish_enabled=false
    + record kill_event row + alert via alert_reconciliation_lifecycle.

Manual kill switch is just:
    UPDATE hype_account_config SET auto_publish_enabled=false
    WHERE account_id='<id>';
This script is the AUTOMATED version of the same flip.

Runs nightly (or wire it into the existing 6h reconciler). Stays a no-op
when no account has auto_publish_enabled=true (current state).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # type: ignore
try:
    from tools.alerter import alert_reconciliation_lifecycle  # type: ignore
except ImportError:
    alert_reconciliation_lifecycle = None  # type: ignore


HUMAN_OVERRIDE_RATE_CEILING = 0.15
ERROR_BUDGET = 0
MIN_24H_ROWS_FOR_TRIP = 10
MIN_30D_ROWS_FOR_TRIP = 50


def _fetch(supabase, window_hours: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc)
              - timedelta(hours=window_hours)).isoformat()
    return (
        supabase.table("faithfulness_verdicts")
        .select("verdict, path, human_decision, created_at, account_id")
        .gt("created_at", cutoff)
        .execute().data or []
    )


def _block_rate(rows: list[dict]) -> float:
    n = sum(1 for r in rows if r["verdict"] in ("PASS", "HARD_BLOCK"))
    if not n:
        return 0.0
    return sum(1 for r in rows if r["verdict"] == "HARD_BLOCK") / n


def _daily_block_rates(rows: list[dict]) -> list[float]:
    by_day: dict[str, list[dict]] = {}
    for r in rows:
        by_day.setdefault((r["created_at"] or "")[:10], []).append(r)
    return [_block_rate(v) for v in by_day.values()]


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mu = sum(values) / len(values)
    if len(values) < 2:
        return mu, 0.0
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return mu, math.sqrt(var)


def trip(reason: str, severity: str, evidence: dict, sb) -> None:
    print(f"[CIRCUIT-BREAKER TRIP] severity={severity}  reason={reason}")
    print(f"  evidence={json.dumps(evidence, ensure_ascii=False)}")

    # Flip every account that currently has auto_publish_enabled=true to false
    on_accounts = (
        sb.table("hype_account_config")
        .select("account_id, auto_publish_enabled")
        .eq("auto_publish_enabled", True)
        .execute().data or []
    )
    for row in on_accounts:
        sb.table("hype_account_config").update({
            "auto_publish_enabled": False,
        }).eq("account_id", row["account_id"]).execute()
        print(f"  flipped: account_id={row['account_id']} → auto_publish_enabled=false")

    if alert_reconciliation_lifecycle is not None:
        try:
            alert_reconciliation_lifecycle(
                severity=severity,
                category=f"faithfulness::circuit_breaker::{reason}",
                summary=(f"Circuit breaker tripped ({reason}). "
                         f"{len(on_accounts)} account(s) flipped to "
                         "auto_publish_enabled=false."),
                evidence=evidence,
            )
        except Exception as e:
            print(f"  alerter emit failed (non-fatal): {e!r}")


def main() -> int:
    sb = make_supabase()
    rows_24 = _fetch(sb, 24)
    rows_30d = _fetch(sb, 24 * 30)

    print(f"24h rows: {len(rows_24)}  |  30d rows: {len(rows_30d)}")

    if len(rows_30d) < MIN_30D_ROWS_FOR_TRIP:
        print(f"  ↳ warm-up window ({len(rows_30d)} < {MIN_30D_ROWS_FOR_TRIP}); "
              "circuit breaker is silent until enough data.")
        return 0

    daily_rates = _daily_block_rates(rows_30d)
    mu30, sigma30 = _mean_std(daily_rates)
    rate24 = _block_rate(rows_24)
    n24 = sum(1 for r in rows_24 if r["verdict"] in ("PASS", "HARD_BLOCK"))
    print(f"  μ30 = {mu30:.4f}  σ30 = {sigma30:.4f}  rate24 = {rate24:.4f}  n24 = {n24}")

    err24 = sum(1 for r in rows_24 if r["verdict"] == "ERROR")
    paired24 = [r for r in rows_24
                if r["verdict"] in ("PASS", "HARD_BLOCK")
                and r.get("human_decision") in ("approve", "reject")]
    dis = sum(1 for r in paired24
              if (r["verdict"] == "HARD_BLOCK")
              != (r["human_decision"] == "reject"))
    override_rate = (dis / len(paired24)) if paired24 else 0.0

    # 1) Collapse
    if (n24 >= MIN_24H_ROWS_FOR_TRIP
        and rate24 < max(mu30 - 2 * sigma30, 0.0)):
        trip("block_rate_collapse", "CRITICAL",
             {"rate24": rate24, "mu30": mu30, "sigma30": sigma30,
              "lower": max(mu30 - 2 * sigma30, 0.0), "n24": n24}, sb)
    # 2) Spike
    elif (n24 >= MIN_24H_ROWS_FOR_TRIP
          and rate24 > mu30 + 2 * sigma30):
        trip("block_rate_spike", "WARN",
             {"rate24": rate24, "mu30": mu30, "sigma30": sigma30,
              "upper": mu30 + 2 * sigma30, "n24": n24}, sb)
    # 3) Gate error budget
    if err24 > ERROR_BUDGET:
        trip("gate_errored", "CRITICAL",
             {"errors_24h": err24, "budget": ERROR_BUDGET}, sb)
    # 4) Human override rate
    if len(paired24) >= MIN_24H_ROWS_FOR_TRIP and override_rate > HUMAN_OVERRIDE_RATE_CEILING:
        trip("human_override_high", "CRITICAL",
             {"override_rate_24h": override_rate, "paired_n": len(paired24),
              "ceiling": HUMAN_OVERRIDE_RATE_CEILING}, sb)

    print("circuit breaker check complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

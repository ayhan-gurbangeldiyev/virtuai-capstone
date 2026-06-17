"""Phase 6 — nightly rolling-metrics + σ-band alerts for the faithfulness gate.

Reads `public.faithfulness_verdicts`, computes rolling-30d statistics,
and emits an alert when the LIVE 24h block-rate diverges from the
rolling-30d mean by more than 2σ.

THE FOUR ALERTS (in order of importance):

  (b) BLOCK-RATE COLLAPSE  — the gate has silently been bypassed or is
      erroring-open. Most important; this is the failure that caused
      the 52% leak. Fires when 24h block-rate < (μ30d - 2σ) AND volume
      is steady (≥50% of 30d daily mean).
  (a) BLOCK-RATE SPIKE     — writer or source upstream regressed.
      Fires when 24h block-rate > (μ30d + 2σ).
  (c) GATE-ERRORED         — any 'ERROR' verdicts in last 24h fires.
      Critical because ERROR means "could not evaluate" — fail-closed
      semantics depend on this being NEAR ZERO in steady state.
  (d) HEAL-SUCCESS-DROP    — fraction of blocks that healed in last 24h
      < (μ30d - 2σ). Writer regression signal.

The alerter helper is reused: `alert_reconciliation_lifecycle` from
`tools/alerter.py` (added in the reconciler patch). Severities map:

  block-rate collapse → CRITICAL
  block-rate spike    → WARN
  gate-errored > 0    → CRITICAL
  heal-success drop   → WARN

Run via systemd timer (nightly is enough; cron-rate is low for the
critical "collapse" alert because the leak surfaces over hours,
not seconds).
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase                  # type: ignore
try:
    from tools.alerter import alert_reconciliation_lifecycle      # type: ignore
except ImportError:  # alerter helper may not yet ship the lifecycle variant
    alert_reconciliation_lifecycle = None  # type: ignore


WINDOW_30D = "30 days"
WINDOW_24H = "24 hours"
MIN_30D_SAMPLES = 50           # below this, σ is too noisy to alert
MIN_24H_SAMPLES = 10           # below this, 24h block rate too noisy
VOLUME_STEADY_FLOOR = 0.5      # 24h volume / (30d-mean-per-day) must be ≥ this
                               # before "collapse" can fire (else volume drop
                               # explains the rate drop, not a bypass)


def _fetch_rows(supabase, window: str) -> list[dict]:
    rsp = supabase.rpc("execute_sql_admin", {
        "query": (
            "SELECT verdict, healed, retry_count, created_at "
            "FROM public.faithfulness_verdicts "
            f"WHERE created_at > NOW() - INTERVAL '{window}' "
            "ORDER BY created_at DESC"
        )
    }).execute()
    return rsp.data or []


def _fetch_rows_simple(supabase, window: str) -> list[dict]:
    """Direct REST query (no RPC needed)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(
        days=30 if "30" in window else 1
    )).isoformat()
    return (
        supabase.table("faithfulness_verdicts")
        .select("verdict, healed, retry_count, created_at")
        .gt("created_at", cutoff)
        .execute()
        .data or []
    )


def _block_rate(rows: list[dict]) -> tuple[float, int, int]:
    n = len(rows)
    if n == 0:
        return (0.0, 0, 0)
    blocks = sum(1 for r in rows if r.get("verdict") == "HARD_BLOCK")
    return (blocks / n, blocks, n)


def _per_day_block_rates(rows_30d: list[dict]) -> list[float]:
    """Bucket 30d rows by day and return one block-rate per day."""
    buckets: dict[str, list[dict]] = {}
    for r in rows_30d:
        day = (r["created_at"] or "")[:10]
        buckets.setdefault(day, []).append(r)
    rates = []
    for day, dr in buckets.items():
        rate, _, _ = _block_rate(dr)
        rates.append(rate)
    return rates


def _mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    mu = sum(values) / len(values)
    if len(values) < 2:
        return (mu, 0.0)
    var = sum((v - mu) ** 2 for v in values) / (len(values) - 1)
    return (mu, math.sqrt(var))


def _emit(severity: str, category: str, msg: str, evidence: dict) -> None:
    print(f"[ALERT] severity={severity} category={category} :: {msg}")
    print(f"        evidence={json.dumps(evidence, ensure_ascii=False)}")
    if alert_reconciliation_lifecycle is not None:
        try:
            alert_reconciliation_lifecycle(
                severity=severity,
                category=f"faithfulness::{category}",
                summary=msg,
                evidence=evidence,
            )
        except Exception as e:
            print(f"        alerter emit failed (non-fatal): {e!r}")


def main() -> int:
    supabase = make_supabase()
    rows_30 = _fetch_rows_simple(supabase, WINDOW_30D)
    rows_24 = _fetch_rows_simple(supabase, WINDOW_24H)

    print(f"30d rows: {len(rows_30)}  |  24h rows: {len(rows_24)}")
    print()

    # ── BLOCK-RATE: 30d daily-rates μ/σ ────────────────────────────────
    if len(rows_30) < MIN_30D_SAMPLES:
        print(f"  ↳ insufficient 30d data ({len(rows_30)} < {MIN_30D_SAMPLES}); "
              "skipping σ-band alerts (warm-up window).")
        return 0

    daily_rates = _per_day_block_rates(rows_30)
    mu30, sigma30 = _mean_std(daily_rates)
    rate_24, blocks_24, n_24 = _block_rate(rows_24)
    daily_mean_volume = len(rows_30) / max(len(daily_rates), 1)
    volume_ratio = n_24 / max(daily_mean_volume, 1.0)
    print(f"  30d daily block-rate: μ={mu30:.4f} σ={sigma30:.4f}")
    print(f"  24h block-rate      : {rate_24:.4f}  (blocks={blocks_24} / {n_24})")
    print(f"  Volume vs 30d/day   : {volume_ratio:.2f}x")

    upper = mu30 + 2 * sigma30
    lower = max(mu30 - 2 * sigma30, 0.0)

    # (b) COLLAPSE — most important
    if (rate_24 < lower and
        volume_ratio >= VOLUME_STEADY_FLOOR and
        n_24 >= MIN_24H_SAMPLES):
        _emit("CRITICAL", "block_rate_collapse",
              f"24h block-rate {rate_24:.4f} crashed below μ-2σ "
              f"({lower:.4f}). Gate may be silently bypassed or erroring-open.",
              {"rate_24h": rate_24, "mu_30d": mu30, "sigma_30d": sigma30,
               "lower_bound": lower, "n_24h": n_24,
               "volume_ratio_vs_30d_daily": volume_ratio})

    # (a) SPIKE
    if rate_24 > upper and n_24 >= MIN_24H_SAMPLES:
        _emit("WARN", "block_rate_spike",
              f"24h block-rate {rate_24:.4f} exceeds μ+2σ ({upper:.4f}). "
              "Writer or source regressed.",
              {"rate_24h": rate_24, "mu_30d": mu30, "sigma_30d": sigma30,
               "upper_bound": upper, "n_24h": n_24})

    # (c) GATE-ERRORED
    err_24 = sum(1 for r in rows_24 if r.get("verdict") == "ERROR")
    if err_24 > 0:
        _emit("CRITICAL", "gate_errored",
              f"{err_24} ERROR verdicts in last 24h. Fail-closed semantics "
              "rely on this being zero.",
              {"err_count_24h": err_24, "n_24h": n_24})

    # (d) HEAL-SUCCESS-DROP
    blocks_30 = [r for r in rows_30 if r.get("verdict") == "HARD_BLOCK"]
    if len(blocks_30) >= 20:
        # Compute daily heal-success
        heal_buckets: dict[str, tuple[int, int]] = {}
        for r in blocks_30:
            day = (r["created_at"] or "")[:10]
            healed = 1 if r.get("healed") else 0
            tot, h = heal_buckets.get(day, (0, 0))
            heal_buckets[day] = (tot + 1, h + healed)
        daily_heal_rates = [
            h / tot for tot, h in heal_buckets.values() if tot > 0
        ]
        if daily_heal_rates:
            mu_h, sigma_h = _mean_std(daily_heal_rates)
            blocks_24_list = [r for r in rows_24 if r.get("verdict") == "HARD_BLOCK"]
            healed_24 = sum(1 for r in blocks_24_list if r.get("healed"))
            heal_rate_24 = healed_24 / max(len(blocks_24_list), 1)
            heal_lower = max(mu_h - 2 * sigma_h, 0.0)
            if len(blocks_24_list) >= 10 and heal_rate_24 < heal_lower:
                _emit("WARN", "heal_success_drop",
                      f"24h heal-success {heal_rate_24:.2f} dropped below "
                      f"μ-2σ ({heal_lower:.2f}).",
                      {"heal_24h": heal_rate_24, "mu_30d": mu_h,
                       "sigma_30d": sigma_h, "lower_bound": heal_lower,
                       "n_blocks_24h": len(blocks_24_list)})

    print()
    print("monitor complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Stage 2 Step 5 — supply-health monitor.

Runs daily (via deploy/hype-trend-supply.timer). For each AI batch
type (ai_core / ai_news_en / ai_news_tr), counts the distinct
usernames and distinct tweets fetched in the LAST 24h. If any batch
falls below its minimum threshold, fires alert_supply(...) so the
operator sees the gap before the day's content slot runs dry.

This does NOT publish anything and does NOT touch the gate. It only
observes the trend_x_sources → tweet_feed supply path.

Env knobs:
  SUPPLY_HEALTH_DRYRUN=true   → log only, never call alert_supply.
                                Default false (so the timer alerts
                                in production). Use 'true' for the
                                first dry-run on Hetzner.
  SUPPLY_HEALTH_MIN_TWEETS_AI_CORE=8     (default)
  SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_EN=5  (default)
  SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_TR=5  (default)
  SUPPLY_HEALTH_MIN_DISTINCT_ACCOUNTS=3  (per batch, default)
"""
from __future__ import annotations

import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

# Make ``backend`` importable when invoked via systemd as a script.
_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("supply_health")


_BATCH_THRESHOLDS = {
    "ai_core":    int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_CORE",    "8")),
    "ai_news_en": int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_EN", "5")),
    "ai_news_tr": int(os.environ.get("SUPPLY_HEALTH_MIN_TWEETS_AI_NEWS_TR", "5")),
}
_MIN_ACCOUNTS = int(os.environ.get("SUPPLY_HEALTH_MIN_DISTINCT_ACCOUNTS", "3"))
_DRYRUN = (os.environ.get("SUPPLY_HEALTH_DRYRUN", "") or "").strip().lower() in {
    "1", "true", "yes", "on",
}


def _get_supabase():
    from supabase import create_client
    url = (os.environ.get("SUPABASE_URL") or "").strip()
    key = (os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_KEY") or "").strip()
    if not (url and key):
        raise RuntimeError("SUPABASE_URL / SUPABASE_KEY missing in env")
    return create_client(url, key)


def _summarize_last_24h(sb) -> dict[str, dict]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    rows = (
        sb.table("tweet_feed")
        .select("id, batch_type, username, tweet_created_at")
        .in_("batch_type", list(_BATCH_THRESHOLDS.keys()))
        .gt("tweet_created_at", since)
        .limit(5000)
        .execute()
        .data
    ) or []

    summary: dict[str, dict] = {
        b: {"tweets": 0, "accounts": set()} for b in _BATCH_THRESHOLDS
    }
    for r in rows:
        bt = r.get("batch_type")
        if bt not in summary:
            continue
        summary[bt]["tweets"] += 1
        u = (r.get("username") or "").lower()
        if u:
            summary[bt]["accounts"].add(u)
    return summary


def _evaluate(summary: dict[str, dict]) -> list[dict]:
    """Return a list of breach dicts (one per batch under threshold)."""
    breaches = []
    for bt, threshold in _BATCH_THRESHOLDS.items():
        s = summary.get(bt, {"tweets": 0, "accounts": set()})
        tweets = int(s["tweets"])
        accounts = len(s["accounts"])
        if tweets < threshold or accounts < _MIN_ACCOUNTS:
            breaches.append({
                "batch_type": bt,
                "tweets_24h": tweets,
                "accounts_24h": accounts,
                "threshold_tweets": threshold,
                "threshold_accounts": _MIN_ACCOUNTS,
                "sample_accounts": sorted(s["accounts"])[:8],
            })
    return breaches


def main() -> int:
    try:
        sb = _get_supabase()
    except Exception as e:
        logger.exception(f"Supabase client init failed: {e!r}")
        return 2

    summary = _summarize_last_24h(sb)
    for bt in _BATCH_THRESHOLDS:
        s = summary[bt]
        logger.info(
            f"batch={bt} tweets_24h={s['tweets']} "
            f"distinct_accounts={len(s['accounts'])} "
            f"min_tweets={_BATCH_THRESHOLDS[bt]} min_accounts={_MIN_ACCOUNTS}"
        )

    breaches = _evaluate(summary)
    if not breaches:
        logger.info("supply healthy across all AI batches")
        return 0

    summary_line = "; ".join(
        f"{b['batch_type']}: {b['tweets_24h']} tweets / "
        f"{b['accounts_24h']} accts (need ≥{b['threshold_tweets']}/"
        f"{b['threshold_accounts']})"
        for b in breaches
    )
    logger.warning(f"SUPPLY BREACH — {summary_line}")

    if _DRYRUN:
        logger.warning(
            "SUPPLY_HEALTH_DRYRUN=true — skipping alert_supply(). "
            "Would have fired CRITICAL silent_supply."
        )
        return 0

    try:
        from services.alerter import alert_supply
        alert_supply(
            severity="CRITICAL",
            category="silent_supply",
            summary=f"AI supply below threshold in last 24h — {summary_line}",
            evidence={"breaches": breaches, "min_accounts": _MIN_ACCOUNTS},
        )
    except Exception as e:
        logger.exception(f"alert_supply() raised: {e!r}")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())

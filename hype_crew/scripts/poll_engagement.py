"""Phase 22 — Engagement Feedback Loop poller.

Runs every 6 hours via systemd (`deploy/hype-engagement.timer`).
For each Cansu (and any active persona) daily_drafts row with a real Postiz
post_id from the last 7 days, calls Postiz analytics → writes a
`hype_memory.performance_log` entry → Strategist sees the new context in
the next hype-crew run.

Idempotency: skips post_ids that already have a performance_log entry written
within the last 5 hours (so a 6h cadence doesn't double-count).

Skips DRY_RUN_xxx synthetic post_ids (dry_run_mode=true posts).

Usage:
    cd /opt/hype-crew
    venv/bin/python -m scripts.poll_engagement
    venv/bin/python -m scripts.poll_engagement --account=<uuid>
    venv/bin/python -m scripts.poll_engagement --dry-run  # don't write to DB
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from loguru import logger

# Allow `python -m scripts.poll_engagement` AND direct execution
_THIS = Path(__file__).resolve()
_HYPE_CREW = _THIS.parent.parent
if str(_HYPE_CREW) not in sys.path:
    sys.path.insert(0, str(_HYPE_CREW))

from config import settings  # noqa: E402
from tools.memory_tools import save_memory_entry  # noqa: E402
from tools.postiz_client import PostizClient  # noqa: E402
from tools.supabase_client import make_supabase  # noqa: E402


POLL_LOOKBACK_DAYS = 7          # only poll posts created in the last 7 days
POLL_DEDUP_HOURS = 5            # skip if same post_id polled in last N hours
DRY_RUN_ID_PREFIX = "DRY_RUN_"  # synthetic IDs we never call Postiz on
ANALYTICS_DATE_WINDOW = 7       # Postiz `?date=N` lookback days

# Phase E1 — reconciler defaults
RECONCILE_LOOKBACK_DAYS = 30
RECONCILE_FORWARD_DAYS = 7
SYNTHETIC_POSTIZ_PREFIXES = ("DRY_RUN_", "ERROR_")
SYNTHETIC_POSTIZ_SENTINELS = {"PENDING_REVIEW"}

# Phase E1.1 — Postiz lifecycle severity bands (see operator-handover.md
# "Postiz lifecycle reference"). Hours of lateness vs scheduled_at.
QUEUE_INFO_MAX_HOURS = 2.0     # 0..2h late → INFO (in Postiz self-heal window)
QUEUE_WARN_MAX_HOURS = 4.0     # 2..4h late → WARN; ≥4h → CRITICAL
PUBLISHED_NO_URL_MIN_HOURS = 2.0   # PUBLISHED w/o release_url → WARN after 2h
PUBLISHED_NO_URL_PLATFORMS = {"twitter", "linkedin"}


def _lifecycle_alerts_enabled() -> bool:
    """Opt-in switch — set RECONCILER_LIFECYCLE_ALERTS=true to activate
    lifecycle-aware severity bands. Defaults to false so the pre-E1.1
    single-tier WARN classification stays in effect until explicitly
    enabled during dry-run / controlled deploy."""
    import os as _os
    return _os.environ.get("RECONCILER_LIFECYCLE_ALERTS", "false").lower() in (
        "1", "true", "yes"
    )


def _parse_scheduled_at(scheduled_at: Optional[str]) -> Optional[datetime]:
    if not scheduled_at:
        return None
    try:
        return datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
    except Exception:
        return None


def _reconciler_write_mode() -> bool:
    """Default ON post-Day3-activation. Set RECONCILER_WRITE_MODE=false to
    fall back to log-only behavior (Day-2 observe-mode)."""
    import os as _os
    return _os.environ.get("RECONCILER_WRITE_MODE", "true").lower() in (
        "1", "true", "yes"
    )


def _is_real_postiz_id(pid: Optional[str]) -> bool:
    if not pid or not isinstance(pid, str):
        return False
    if pid in SYNTHETIC_POSTIZ_SENTINELS:
        return False
    if any(pid.startswith(p) for p in SYNTHETIC_POSTIZ_PREFIXES):
        return False
    return True


async def _classify_via_analytics(pc: PostizClient, pid: str) -> tuple[str, str]:
    """Fallback when list_posts misses an id. Empty analytics → silent
    failure; non-empty → still alive. Returns (verdict, state_label)."""
    try:
        a = pc.get_post_analytics(pid, days=ANALYTICS_DATE_WINDOW)
    except Exception as e:  # noqa: BLE001
        return "unreachable", f"FETCH_ERROR:{type(e).__name__}"
    if not isinstance(a, list) or not a:
        return "failed_silently", "MISSING_FROM_LIST"
    return "live", "INFERRED_LIVE"


def _fetch_postiz_inventory(pc: PostizClient) -> dict[str, dict]:
    """Sweep Postiz list_posts across multiple windows to maximize coverage
    of the 19-row pagination cap."""
    inventory: dict[str, dict] = {}
    now = datetime.now(timezone.utc)
    windows = [
        (RECONCILE_LOOKBACK_DAYS, RECONCILE_FORWARD_DAYS),
        (14, 1),
        (7, 1),
        (3, 1),
    ]
    for back, forward in windows:
        try:
            posts = pc.list_posts(
                start_date=(now - timedelta(days=back)).isoformat(),
                end_date=(now + timedelta(days=forward)).isoformat(),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"[reconciler] list_posts(-{back}d..+{forward}d) failed: "
                f"{type(e).__name__}: {str(e)[:160]}"
            )
            continue
        for p in posts:
            pid = p.get("id") or p.get("_id")
            if pid and pid not in inventory:
                inventory[pid] = p
    return inventory


async def reconcile_postiz_state(sb, *, write_mode: bool) -> dict[str, int]:
    """Phase E1 — reconcile local daily_drafts.postiz_post_id against
    Postiz state. Updates daily_drafts.postiz_state + release_url when
    write_mode is True. Emits alerts via tools.alerter for anomalies
    whose scheduled_at has passed.

    Returns counters dict: {candidates, live, queued, anomalies, alerted,
    db_updates}.
    """
    pc = PostizClient()
    since = (
        datetime.now(timezone.utc) - timedelta(days=RECONCILE_LOOKBACK_DAYS)
    ).isoformat()

    rows = (
        sb.table("daily_drafts")
        .select("id, postiz_post_id, platform, status, scheduled_at, "
                "created_at, postiz_state, release_url")
        .not_.is_("postiz_post_id", "null")
        # 2026-06-10 — silinen/arşivlenen/reddedilen draftlar reconcile
        # edilmez: postları Postiz'den BİLEREK kaldırıldı, "missing"
        # olmaları anomali değil. (12:00 UTC'de 5 false-CRITICAL spam'i:
        # 7 Haz'da silinmiş Anthropic seti + 1 Haz arşivi alarm üretti.)
        .not_.in_("status", ["deleted", "archived_quality_sweep", "auto_rejected", "dismissed"])
        .is_("deleted_at", "null")
        .gte("created_at", since)
        .order("created_at", desc=True)
        .execute()
    ).data or []
    rows = [r for r in rows if _is_real_postiz_id(r.get("postiz_post_id"))]

    counters = {"candidates": len(rows), "live": 0, "queued": 0,
                "anomalies": 0, "alerted": 0, "db_updates": 0}
    if not rows:
        logger.info("[reconciler] no real-postiz candidates in window")
        return counters

    inventory = _fetch_postiz_inventory(pc)
    logger.info(
        f"[reconciler] candidates={len(rows)} inventory={len(inventory)} "
        f"write_mode={write_mode}"
    )

    # Lazy alerter import — keep poller importable on hosts without alerter
    try:
        from tools.alerter import (
            alert_reconciliation_anomaly,
            alert_reconciliation_lifecycle,
        )
    except Exception:  # noqa: BLE001
        alert_reconciliation_anomaly = None  # type: ignore
        alert_reconciliation_lifecycle = None  # type: ignore

    lifecycle_on = _lifecycle_alerts_enabled()
    now = datetime.now(timezone.utc)
    for r in rows:
        pid = r["postiz_post_id"]
        plat = r.get("platform") or "?"
        plat_lc = plat.lower()
        draft_id = r["id"]
        scheduled_at = r.get("scheduled_at")
        sched_dt = _parse_scheduled_at(scheduled_at)
        late_hours: Optional[float] = None
        if sched_dt is not None:
            late_hours = (now - sched_dt).total_seconds() / 3600.0

        # Pre-init for static analyzers; overwritten by the inventory-miss branch.
        verdict = "live"
        p = inventory.get(pid)
        if p is not None:
            state = (p.get("state") or "").upper() or "UNKNOWN"
            release_url = p.get("releaseURL") or p.get("release_url")
            postiz_err = p.get("error") or p.get("errorMessage")
            in_inventory = True
        else:
            verdict, state = await _classify_via_analytics(pc, pid)
            release_url = None
            postiz_err = None
            in_inventory = False

        # ─── Severity classification ──────────────────────────────────
        # When lifecycle_on=False (default), behavior matches pre-E1.1:
        # in-inventory anomalies fire as single WARN via the legacy helper
        # using the pre-existing verdict labels. When lifecycle_on=True,
        # severity is banded by lateness.
        severity: Optional[str] = None
        category: Optional[str] = None
        verdict_bucket = "live"  # for counters: live / queued / anomaly

        if in_inventory:
            if state == "PUBLISHED":
                if release_url:
                    verdict_bucket = "live"
                elif (
                    lifecycle_on
                    and plat_lc in PUBLISHED_NO_URL_PLATFORMS
                    and late_hours is not None
                    and late_hours > PUBLISHED_NO_URL_MIN_HOURS
                ):
                    verdict_bucket = "anomaly"
                    severity = "WARN"
                    category = "published_no_url"
                else:
                    verdict_bucket = "live"
            elif state in ("QUEUE", "PROCESSING", "DRAFT"):
                if late_hours is None or late_hours < 0:
                    verdict_bucket = "queued"  # not yet due
                elif not lifecycle_on:
                    # Pre-E1.1: single WARN via legacy helper.
                    verdict_bucket = "queued"
                    severity = "WARN"
                    category = "scheduled_not_live"  # legacy verdict label
                elif late_hours < QUEUE_INFO_MAX_HOURS:
                    verdict_bucket = "queued"
                    severity = "INFO"
                    category = "queue_late_short"
                elif late_hours < QUEUE_WARN_MAX_HOURS:
                    verdict_bucket = "anomaly"
                    severity = "WARN"
                    category = "queue_late_long"
                else:
                    verdict_bucket = "anomaly"
                    severity = "CRITICAL"
                    category = "queue_stuck"
            elif state == "ERROR":
                verdict_bucket = "anomaly"
                severity = "CRITICAL"
                # Lifecycle ON → new category; OFF → preserve legacy "failed_silently"
                # so pre-E1.1 callers see the same title.
                category = "error_terminal" if lifecycle_on else "failed_silently"
            else:
                verdict_bucket = "anomaly"
                severity = "WARN"
                category = "postiz_only_unknown"
        else:
            # Analytics-fallback path: preserve legacy verdicts unchanged.
            if verdict == "live":
                verdict_bucket = "live"
            elif verdict == "failed_silently":
                verdict_bucket = "anomaly"
                severity = "CRITICAL"
                category = "failed_silently"
            else:
                verdict_bucket = "anomaly"
                severity = "WARN"
                category = "postiz_only_unknown"

        if verdict_bucket == "live":
            counters["live"] += 1
        elif verdict_bucket == "queued":
            counters["queued"] += 1
        else:
            counters["anomalies"] += 1

        # Write-mode: persist state to daily_drafts
        if write_mode:
            updates: dict = {}
            if r.get("postiz_state") != state:
                updates["postiz_state"] = state
            if release_url and r.get("release_url") != release_url:
                updates["release_url"] = release_url
            if updates:
                try:
                    sb.table("daily_drafts").update(updates).eq(
                        "id", draft_id
                    ).execute()
                    counters["db_updates"] += 1
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        f"[reconciler] update {draft_id[:8]} failed: {e}"
                    )

        # Emit alert via the appropriate helper.
        if severity and category:
            try:
                if category in ("failed_silently", "scheduled_not_live", "postiz_only_unknown") \
                        and alert_reconciliation_anomaly is not None:
                    # Legacy helper signature — preserves pre-E1.1 alert titles.
                    alert_reconciliation_anomaly(
                        draft_id=draft_id,
                        postiz_post_id=pid,
                        platform=plat,
                        verdict=category,
                        state=state,
                        evidence=postiz_err,
                    )
                    counters["alerted"] += 1
                elif alert_reconciliation_lifecycle is not None:
                    alert_reconciliation_lifecycle(
                        draft_id=draft_id,
                        postiz_post_id=pid,
                        platform=plat,
                        severity=severity,
                        category=category,
                        state=state,
                        late_hours=late_hours,
                        evidence=postiz_err,
                    )
                    counters["alerted"] += 1
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[reconciler] alert failed for {pid[:8]}: {e}")

    logger.info(f"[reconciler] DONE — {counters}")
    return counters


def _parse_postiz_metrics(
    analytics_payload: list[dict[str, Any]],
    *,
    publish_iso: Optional[str],
) -> Optional[dict[str, Any]]:
    """Convert Postiz analytics response to a flat metrics dict.

    Postiz returns an array of {label, data:[{total,date}], percentageChange}.
    We aggregate by taking the LATEST `total` per label (analytics emit
    cumulative-style daily snapshots), and normalize the label name into a
    snake_case metric key our memory entries can rely on.
    """
    if not isinstance(analytics_payload, list) or not analytics_payload:
        return None

    # Postiz label conventions vary by platform; map common ones to canonical
    # snake_case keys. Unknown labels are kept as-is with lowercase+snake.
    LABEL_MAP = {
        "likes": "likes",
        "favorites": "likes",          # X legacy
        "retweets": "retweets",
        "reposts": "retweets",          # LinkedIn/X variants
        "replies": "replies",
        "comments": "replies",
        "shares": "shares",
        "impressions": "impressions",
        "views": "impressions",
        "video views": "video_views",
        "engagements": "engagements",
        "followers": "followers",
        "clicks": "clicks",
    }

    out: dict[str, Any] = {}
    for metric in analytics_payload:
        if not isinstance(metric, dict):
            continue
        raw_label = (metric.get("label") or "").strip().lower()
        if not raw_label:
            continue
        key = LABEL_MAP.get(raw_label, raw_label.replace(" ", "_"))
        data = metric.get("data") or []
        latest_total = 0
        for point in reversed(data):
            try:
                latest_total = int(point.get("total") or 0)
                break
            except (TypeError, ValueError):
                continue
        out[key] = latest_total
        # Carry percentage change if present (useful for "trending up?" signal)
        pct = metric.get("percentageChange")
        if isinstance(pct, (int, float)):
            out[f"{key}_pct_change"] = round(float(pct), 2)

    # Derived: time since publish
    if publish_iso:
        try:
            pub = datetime.fromisoformat(publish_iso.replace("Z", "+00:00"))
            hours = max(0, (datetime.now(timezone.utc) - pub).total_seconds() / 3600)
            out["hours_since_publish"] = round(hours, 1)
        except Exception:
            pass

    return out if out else None


def _engagement_importance(metrics: dict[str, Any]) -> float:
    """Heuristic 0.0-1.0 importance score for hype_memory ranking.

    Weighted (engagements / impressions): replies > retweets > likes.
    Pinned high-engagement posts get higher importance so format_memory_context
    surfaces them first when context budget is tight.
    """
    likes = int(metrics.get("likes") or 0)
    retweets = int(metrics.get("retweets") or 0)
    replies = int(metrics.get("replies") or 0)
    impressions = max(int(metrics.get("impressions") or 1), 1)
    weighted = likes + (retweets * 3) + (replies * 2)
    ratio = weighted / impressions
    # Cap at 1.0; typical strong engagement_rate ~3-10% → ratio*10 → 0.3-1.0
    return round(min(ratio * 10, 1.0), 3)


def _already_polled_recently(
    sb, *, account_id: str, postiz_post_id: str
) -> bool:
    """Check if a performance_log row exists for this post_id in last
    POLL_DEDUP_HOURS. Returns True → skip."""
    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=POLL_DEDUP_HOURS)
    ).isoformat()
    res = (
        sb.table("hype_memory")
        .select("id, metadata, created_at")
        .eq("account_id", account_id)
        .eq("memory_type", "performance_log")
        .gte("created_at", cutoff)
        .execute()
    )
    for r in (res.data or []):
        meta = r.get("metadata") or {}
        if meta.get("postiz_post_id") == postiz_post_id:
            return True
    return False


async def poll_account_engagement(
    account_id: str, *, dry_run: bool = False
) -> dict[str, int]:
    """Poll engagement for one account's recent published drafts.

    Returns a summary dict: {polled, skipped_dedup, skipped_dry_run_id,
    skipped_unpublished, errors, total_drafts}.
    """
    sb = make_supabase()
    since = (
        datetime.now(timezone.utc) - timedelta(days=POLL_LOOKBACK_DAYS)
    ).isoformat()

    # Pull recent hype_auto drafts with a postiz_post_id
    drafts_q = (
        sb.table("daily_drafts")
        .select(
            "id, postiz_post_id, platform, content, trend_topic, "
            "created_at, scheduled_at, account_id, status"
        )
        .eq("account_id", account_id)
        .eq("source", "hype_auto")
        .not_.is_("postiz_post_id", "null")
        .gte("created_at", since)
        .order("created_at", desc=True)
    )
    drafts_data = drafts_q.execute().data or []
    summary = {
        "polled": 0,
        "skipped_dedup": 0,
        "skipped_dry_run_id": 0,
        "skipped_unpublished": 0,
        "errors": 0,
        "total_drafts": len(drafts_data),
    }
    if not drafts_data:
        logger.info(f"[poller] account={account_id}: no recent drafts with postiz_post_id")
        return summary

    pc = PostizClient()
    for d in drafts_data:
        pid: str = d["postiz_post_id"]
        if pid.startswith(DRY_RUN_ID_PREFIX):
            summary["skipped_dry_run_id"] += 1
            continue
        if _already_polled_recently(sb, account_id=account_id, postiz_post_id=pid):
            summary["skipped_dedup"] += 1
            continue

        # Pull analytics. Postiz returns 404 (or empty array) for posts that
        # are not yet published, or whose releaseId is 'missing'.
        try:
            analytics = pc.get_post_analytics(pid, days=ANALYTICS_DATE_WINDOW)
        except Exception as e:  # httpx errors, JSON errors, etc.
            err = f"{type(e).__name__}: {str(e)[:160]}"
            logger.warning(f"[poller] {pid} analytics failed: {err}")
            summary["errors"] += 1
            continue

        publish_iso = d.get("scheduled_at") or d.get("created_at")
        metrics = _parse_postiz_metrics(analytics, publish_iso=publish_iso)
        if metrics is None:
            summary["skipped_unpublished"] += 1
            logger.debug(f"[poller] {pid}: no metrics yet")
            continue

        summary_text = (
            f"{d['platform']}: '{(d.get('trend_topic') or '')[:60]}' → "
            f"{metrics.get('likes', 0)}L / {metrics.get('retweets', 0)}RT / "
            f"{metrics.get('replies', 0)}R / "
            f"{metrics.get('impressions', 0)}imp "
            f"(published {metrics.get('hours_since_publish', '?')}h ago)"
        )
        importance = _engagement_importance(metrics)

        if dry_run:
            logger.info(f"[poller] DRY: would write — {summary_text} importance={importance}")
            summary["polled"] += 1
            continue

        try:
            save_memory_entry(
                account_id=account_id,
                memory_type="performance_log",
                content=summary_text,
                metadata={
                    "postiz_post_id": pid,
                    "draft_id": d["id"],
                    "platform": d["platform"],
                    "trend_topic": d.get("trend_topic"),
                    **metrics,
                },
                importance=importance,
                skip_embedding=True,  # performance_log retrieved by recency, not semantics
            )
            summary["polled"] += 1
            logger.info(f"[poller] ✓ {summary_text} importance={importance}")
        except Exception as e:
            logger.exception(f"[poller] save_memory_entry failed for {pid}: {e}")
            summary["errors"] += 1

    return summary


PENDING_REAP_AGE_HOURS = 24
PENDING_REAP_MAX_AGE_HOURS = 24 * 7   # ignore drafts older than 7 days
                                       # (those are historical noise, not actionable)
PENDING_REAP_MAX_ALERTS_PER_RUN = 5    # cap alert volume per reaper run
ZERO_PUBLISH_WINDOW_HOURS = 24
ZERO_PUBLISH_MIN_EXPECTED = 1


def reap_pending_drafts(sb) -> dict[str, int]:
    """Phase E4 — alert on drafts stuck in status='pending' for > N hours.

    'pending' is an intermediate state — drafts should progress to
    'pending_review' (for human approval) or 'pending'/'approved' with a
    real postiz_post_id. Drafts left in 'pending' with no postiz_post_id
    after 24h usually mean a flow run completed without persisting the
    publish branch.

    Read-only against draft state. Never modifies rows. Emits one
    [ALERT][WARN] per stale draft via the alerter.
    """
    counters = {"checked": 0, "stale_actionable": 0, "stale_ancient": 0, "alerted": 0}
    now = datetime.now(timezone.utc)
    cutoff_min_age = (now - timedelta(hours=PENDING_REAP_AGE_HOURS)).isoformat()
    cutoff_max_age = (now - timedelta(hours=PENDING_REAP_MAX_AGE_HOURS)).isoformat()
    try:
        rows = (
            sb.table("daily_drafts")
            .select("id, platform, status, created_at, postiz_post_id")
            .eq("status", "pending")
            .lt("created_at", cutoff_min_age)
            .limit(50)
            .execute()
        ).data or []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[reaper] query failed (non-fatal): {e}")
        return counters

    counters["checked"] = len(rows)
    if not rows:
        return counters

    try:
        from tools.alerter import send_alert
    except Exception:  # noqa: BLE001
        send_alert = None  # type: ignore

    for r in rows:
        # Skip ancient drafts — they're noise, not actionable operationally.
        if r.get("created_at") and r["created_at"] < cutoff_max_age:
            counters["stale_ancient"] += 1
            continue
        counters["stale_actionable"] += 1
        if counters["alerted"] >= PENDING_REAP_MAX_ALERTS_PER_RUN:
            continue  # rate-limit alerts per run
        if send_alert is None:
            continue
        try:
            send_alert(
                title="Takılı taslak (onay bekliyor)",
                severity="WARN",
                platform=r.get("platform"),
                draft_id=r.get("id"),
                postiz_post_id=r.get("postiz_post_id"),
                reason=f"Bu taslak {PENDING_REAP_AGE_HOURS} saatten uzun süredir "
                       f"onay bekliyor, yayınlanmadı.",
                action="Panelden taslağı incele: onayla, reddet ya da kapat. "
                       "Eğer yinelenen/başıboş bir kopyaysa kapat.",
            )
            counters["alerted"] += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[reaper] alert for {r.get('id')[:8]} failed: {e}")

    logger.info(f"[reaper] DONE — {counters}")
    return counters


def check_zero_publishes(sb) -> dict[str, int]:
    """Phase X3 — alert when auto-publish is enabled but no drafts have
    reached postiz_state='PUBLISHED' in the trailing N hours.

    Skips when no account has auto_publish_enabled=true (system is in
    manual mode by design; zero publishes is the expected behavior).

    Read-only. Never modifies rows. Emits one [ALERT][CRITICAL] when
    the window is empty.
    """
    counters = {"auto_publish_accounts": 0, "published_in_window": 0, "alerted": 0}

    # Skip entirely if nobody is on auto-publish
    try:
        cfgs = (
            sb.table("hype_account_config")
            .select("account_id, auto_publish_enabled")
            .eq("auto_publish_enabled", True)
            .execute()
        ).data or []
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[zero-publish-check] cfg query failed: {e}")
        return counters
    counters["auto_publish_accounts"] = len(cfgs)
    if not cfgs:
        return counters

    cutoff = (
        datetime.now(timezone.utc) - timedelta(hours=ZERO_PUBLISH_WINDOW_HOURS)
    ).isoformat()
    try:
        # Use scheduled_at — that's when Postiz attempted publish.
        # created_at is set at draft generation and can be much earlier.
        published = (
            sb.table("daily_drafts")
            .select("id", count="exact")
            .eq("postiz_state", "PUBLISHED")
            .gte("scheduled_at", cutoff)
            .limit(1)
            .execute()
        )
        n_published = published.count if hasattr(published, "count") else len(published.data or [])
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[zero-publish-check] published query failed: {e}")
        return counters

    counters["published_in_window"] = n_published or 0
    if (n_published or 0) >= ZERO_PUBLISH_MIN_EXPECTED:
        return counters

    # Anomaly: auto-publish ON, zero publishes in window
    try:
        from tools.alerter import alert_zero_publishes_in_window
        alert_zero_publishes_in_window(
            window_hours=ZERO_PUBLISH_WINDOW_HOURS,
            expected_min=ZERO_PUBLISH_MIN_EXPECTED,
        )
        counters["alerted"] = 1
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[zero-publish-check] alert failed: {e}")
    logger.info(f"[zero-publish-check] DONE — {counters}")
    return counters


async def main_async(args) -> int:
    sb = make_supabase()

    # Phase E1 — Postiz state reconciler. Runs BEFORE the engagement poll
    # so any anomalies are flagged before we try to fetch analytics for
    # potentially-dead posts. write_mode controlled by RECONCILER_WRITE_MODE
    # env (default ON post-Day3-activation).
    try:
        await reconcile_postiz_state(sb, write_mode=_reconciler_write_mode())
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[poller] reconciler crashed (non-fatal): {e}")

    # Phase E4 — pending reaper. Surfaces drafts that have been stuck in
    # status='pending' for >24h, which usually means a flow run completed
    # without reaching the publish/pending_review branch (data leak). Logs
    # an alert per stale draft; does NOT change row state — operator decides.
    try:
        reap_pending_drafts(sb)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[poller] pending reaper crashed (non-fatal): {e}")

    # Phase X3 — zero-publishes-in-24h alert. Surfaces the case where
    # auto-publish is enabled but no daily_drafts have reached
    # postiz_state='PUBLISHED' in the trailing 24h.
    try:
        check_zero_publishes(sb)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[poller] zero-publishes check crashed (non-fatal): {e}")

    # Resolve target accounts: --account or all personas
    account_ids: list[str] = []
    if args.account:
        account_ids = [args.account]
    else:
        personas = (
            sb.table("personas")
            .select("primary_account_id, slug")
            .eq("is_active", True)
            .execute()
        )
        for p in (personas.data or []):
            if p.get("primary_account_id"):
                account_ids.append(p["primary_account_id"])
                logger.info(f"[poller] persona {p['slug']} → account {p['primary_account_id']}")

    if not account_ids:
        logger.warning("[poller] no accounts to poll (no active personas)")
        return 0

    overall = {"accounts": len(account_ids), "polled": 0, "errors": 0}
    for aid in account_ids:
        try:
            s = await poll_account_engagement(aid, dry_run=args.dry_run)
            overall["polled"] += s["polled"]
            overall["errors"] += s["errors"]
            logger.info(f"[poller] account={aid}: {s}")
        except Exception as e:
            logger.exception(f"[poller] account={aid} crashed: {e}")
            overall["errors"] += 1

    logger.info(f"[poller] DONE — {overall}")
    return 0 if overall["errors"] == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 22 engagement poller")
    parser.add_argument("--account", help="UUID of connected_accounts row; default: all active personas")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't write to hype_memory; just log what would be written")
    args = parser.parse_args()

    logger.info(
        f"[poller] start dry_run={args.dry_run} lookback={POLL_LOOKBACK_DAYS}d "
        f"dedup_window={POLL_DEDUP_HOURS}h"
    )
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())

"""Phase 43.B.5 — Regen watchdog.

Recovers two failure modes that would otherwise leave a draft stuck:

  1) `daily_drafts.status = 'regen_pending'` with `regen_started_at` older
     than REGEN_TIMEOUT_MIN. The worker either crashed, the Wiro call
     never returned, or the systemd unit was killed mid-flight. We flip
     the row to `regen_failed` so the UI can offer a manual retry path
     and `/approve` stops 409-ing forever.

  2) `image_regen_jobs.status = 'processing'` with `started_at` older
     than REGEN_TIMEOUT_MIN. These are the queue-side orphans. The
     worker already has its own claim-job retry path, but this watchdog
     is the safety net for cases where the worker process disappeared
     between claim and update. We mark the job 'failed' with a clear
     reason so retry_count logic doesn't keep re-claiming it forever.

Designed to be idempotent and cheap: a single SELECT per side plus
UPDATEs only for the orphan rows. Default cadence (systemd timer) is
once a minute — REGEN_TIMEOUT_MIN of 15 means the worst-case stuck time
is ~16 min, comfortably below the user's attention budget.

CLI:
    python -m scripts.regen_watchdog            # one-shot scan
    python -m scripts.regen_watchdog --dry-run  # log only, no UPDATEs
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timedelta, timezone

# Workdir is /opt/hype-crew on Hetzner; lokal smoke also runs from there.
try:
    from tools.supabase_client import make_supabase
except Exception:  # pragma: no cover — package-import fallback
    from hype_crew.tools.supabase_client import make_supabase  # type: ignore

logger = logging.getLogger("regen-watchdog")
if not logger.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(h)
    logger.setLevel(logging.INFO)


# 15-minute orphan threshold. Wiro Seedream at its slowest hits ~4 min,
# and the compliance gate adds maybe another minute, so 15 leaves a fat
# margin for slow networks while still recovering before the user gives
# up and starts a manual regen.
REGEN_TIMEOUT_MIN = 15


def _cutoff_iso(minutes: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()


def recover_orphan_drafts(dry_run: bool = False) -> int:
    """Flip drafts stuck in regen_pending past the timeout to regen_failed."""
    sb = make_supabase()
    cutoff = _cutoff_iso(REGEN_TIMEOUT_MIN)
    try:
        candidates = (
            sb.table("daily_drafts")
            .select("id, status, regen_started_at, image_regen_count")
            .eq("status", "regen_pending")
            .lt("regen_started_at", cutoff)
            .limit(50)
            .execute()
        )
    except Exception as e:
        msg = str(e)[:200]
        if "regen_started_at" in msg or "PGRST204" in msg or "column" in msg.lower():
            logger.warning(
                "regen_started_at column missing — skipping draft-side recovery "
                "(43.B schema migration pending)"
            )
            return 0
        logger.exception(f"draft SELECT failed: {e}")
        return 0

    rows = candidates.data or []
    if not rows:
        return 0

    recovered = 0
    for row in rows:
        draft_id = row.get("id")
        started = row.get("regen_started_at")
        if not draft_id:
            continue
        logger.info(
            f"orphan draft {draft_id}: regen_started_at={started} → marking regen_failed"
        )
        if dry_run:
            recovered += 1
            continue
        try:
            sb.table("daily_drafts").update({
                "status": "regen_failed",
            }).eq("id", draft_id).eq("status", "regen_pending").execute()
            recovered += 1
        except Exception as e:
            logger.warning(f"draft {draft_id}: UPDATE failed (non-fatal): {e}")
    return recovered


def recover_orphan_jobs(dry_run: bool = False) -> int:
    """Mark queue rows whose 'processing' state outlived the worker."""
    sb = make_supabase()
    cutoff = _cutoff_iso(REGEN_TIMEOUT_MIN)
    try:
        candidates = (
            sb.table("image_regen_jobs")
            .select("id, status, started_at, retry_count, draft_id")
            .eq("status", "processing")
            .lt("started_at", cutoff)
            .limit(50)
            .execute()
        )
    except Exception as e:
        logger.exception(f"job SELECT failed: {e}")
        return 0

    rows = candidates.data or []
    if not rows:
        return 0

    recovered = 0
    now_iso = datetime.now(timezone.utc).isoformat()
    for row in rows:
        job_id = row.get("id")
        draft_id = row.get("draft_id")
        if not job_id:
            continue
        logger.info(
            f"orphan job {job_id} (draft={draft_id}): started_at={row.get('started_at')} "
            f"→ marking failed (watchdog timeout)"
        )
        if dry_run:
            recovered += 1
            continue
        try:
            sb.table("image_regen_jobs").update({
                "status": "failed",
                "error": f"watchdog: stuck in processing >{REGEN_TIMEOUT_MIN}min",
                "completed_at": now_iso,
            }).eq("id", job_id).eq("status", "processing").execute()
            # Side-effect: if the linked draft is still regen_pending,
            # surface the failure to the UI so /approve unblocks.
            if draft_id:
                try:
                    sb.table("daily_drafts").update({
                        "status": "regen_failed",
                    }).eq("id", draft_id).eq("status", "regen_pending").execute()
                except Exception:
                    pass
            recovered += 1
        except Exception as e:
            logger.warning(f"job {job_id}: UPDATE failed (non-fatal): {e}")
    return recovered


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    drafts_recovered = recover_orphan_drafts(dry_run=args.dry_run)
    jobs_recovered = recover_orphan_jobs(dry_run=args.dry_run)
    logger.info(
        f"watchdog pass complete: drafts_recovered={drafts_recovered} "
        f"jobs_recovered={jobs_recovered} dry_run={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

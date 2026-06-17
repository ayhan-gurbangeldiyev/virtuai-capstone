"""
DB Cleanup - limit generations per user, scheduled cleanup.
"""
import logging
import asyncio
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

MAX_GENERATIONS_PER_USER = 1000


async def cleanup_old_generations(supabase):
    """Delete excess generations per user (keep latest MAX_GENERATIONS_PER_USER)."""
    try:
        # Get all user_ids with generation counts
        result = supabase.rpc("get_users_with_excess_generations", {
            "max_count": MAX_GENERATIONS_PER_USER
        }).execute()

        # If RPC doesn't exist, do it manually
        if not result.data:
            # Fallback: get distinct user_ids
            users_result = supabase.table("generations").select("user_id").execute()
            user_ids = set(r["user_id"] for r in (users_result.data or []) if r.get("user_id"))

            for user_id in user_ids:
                try:
                    # Count total
                    count_result = supabase.table("generations").select("id", count="exact").eq("user_id", user_id).execute()
                    total = count_result.count or 0

                    if total > MAX_GENERATIONS_PER_USER:
                        excess = total - MAX_GENERATIONS_PER_USER
                        # Get oldest IDs to delete
                        old_result = supabase.table("generations") \
                            .select("id") \
                            .eq("user_id", user_id) \
                            .order("created_at", desc=False) \
                            .limit(excess) \
                            .execute()

                        ids_to_delete = [r["id"] for r in (old_result.data or [])]
                        if ids_to_delete:
                            for batch_start in range(0, len(ids_to_delete), 100):
                                batch = ids_to_delete[batch_start:batch_start + 100]
                                supabase.table("generations").delete().in_("id", batch).execute()

                            logger.info(f"Cleaned up {len(ids_to_delete)} old generations for user {user_id}")
                except Exception as e:
                    logger.error(f"Cleanup error for user {user_id}: {e}")

    except Exception as e:
        logger.error(f"Generation cleanup error: {e}")


TREND_RETENTION_DAYS = 30


async def cleanup_old_trends(supabase):
    """Delete trends older than TREND_RETENTION_DAYS."""
    try:
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=TREND_RETENTION_DAYS)).isoformat()
        result = supabase.table("trends").delete().lt("created_at", cutoff).execute()
        deleted = len(result.data) if result.data else 0
        if deleted:
            logger.info(f"Trend retention: deleted {deleted} trends older than {TREND_RETENTION_DAYS} days")
    except Exception as e:
        logger.error(f"Trend retention cleanup error: {e}")


def start_cleanup_task(supabase):
    """Start background cleanup + feed refresh tasks."""
    async def _periodic_cleanup():
        while True:
            await asyncio.sleep(6 * 3600)  # 6 hours
            await cleanup_old_generations(supabase)
            await cleanup_old_trends(supabase)

    # Stage 2 Step 2 (2026-06-07) — _periodic_feed_refresh REMOVED.
    # That in-process asyncio.sleep(12h) loop reset on every deploy, so
    # the paid Xquik fetch could go silent for any uninterrupted 12h
    # window. Replaced by deploy/hype-trend-fetch.{service,timer} which
    # is `Persistent=true` and re-fires missed schedules across deploys
    # and reboots. The legacy /api/trends/auto-refresh endpoint stays
    # available for the existing external Hetzner crontab as a belt-
    # and-suspenders backup.
    try:
        loop = asyncio.get_event_loop()
        loop.create_task(_periodic_cleanup())
        logger.info("DB cleanup task scheduled (feed refresh via systemd timer)")
    except Exception as e:
        logger.warning(f"Could not start background tasks: {e}")

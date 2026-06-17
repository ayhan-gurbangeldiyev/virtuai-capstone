"""Tweet Feed API — Lovable frontend için tweet_feed tablosundan veri çeker.

GET /api/feed - Feed listesi (batch_type filtreli, pagination, sıralama)
GET /api/feed/stats - Batch bazlı özet istatistikler
POST /api/feed/refresh - Manuel feed yenileme (cron secret ile korunan)
"""
import os
import hmac
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Header, BackgroundTasks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/feed", tags=["feed"])

# Supabase client
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None

VALID_BATCH_TYPES = {"ai_tech", "tr_haber", "spor", "monitor"}
VALID_SORT = {"recent", "popular"}


@router.get("")
async def get_feed(
    batch_type: Optional[str] = Query(None, description="Filter: ai_tech, tr_haber, spor, monitor"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("recent", description="recent or popular"),
    hours: int = Query(48, ge=1, le=168, description="Son kaç saat (max 7 gün)"),
    has_media: Optional[bool] = Query(None, description="Filter: only items with media"),
):
    """Tweet feed listesi. Lovable frontend bu endpoint'i kullanır."""
    if not _supabase:
        raise HTTPException(status_code=503, detail="Database not configured")

    if batch_type and batch_type not in VALID_BATCH_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid batch_type. Valid: {', '.join(VALID_BATCH_TYPES)}")

    if sort not in VALID_SORT:
        raise HTTPException(status_code=400, detail=f"Invalid sort. Valid: {', '.join(VALID_SORT)}")

    try:
        query = (
            _supabase.table("tweet_feed")
            .select("*", count="exact")
            .gte("tweet_created_at", (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat())
        )

        if batch_type:
            query = query.eq("batch_type", batch_type)
        else:
            query = query.neq("batch_type", "radar")

        if has_media is not None:
            query = query.eq("has_media", has_media)

        if sort == "recent":
            query = query.order("tweet_created_at", desc=True)
        else:
            query = query.order("likes", desc=True).order("tweet_created_at", desc=True)

        query = query.range(offset, offset + limit - 1)
        result = query.execute()

        items = result.data or []
        total = result.count or 0

        return {
            "items": items,
            "total": total,
            "has_more": (offset + limit) < total,
            "limit": limit,
            "offset": offset,
        }
    except Exception as e:
        logger.error(f"Feed query error: {e}")
        raise HTTPException(status_code=500, detail="Feed query failed")


@router.get("/stats")
async def get_feed_stats():
    """Batch bazlı feed istatistikleri."""
    if not _supabase:
        raise HTTPException(status_code=503, detail="Database not configured")

    try:
        result = (
            _supabase.rpc("get_feed_stats")
            .execute()
        )
        if result.data:
            return result.data

        # Fallback: manual count per batch_type
        stats = {}
        for bt in VALID_BATCH_TYPES:
            count_result = (
                _supabase.table("tweet_feed")
                .select("id", count="exact")
                .eq("batch_type", bt)
                .execute()
            )
            stats[bt] = count_result.count or 0

        return stats
    except Exception as e:
        logger.error(f"Feed stats error: {e}")
        raise HTTPException(status_code=500, detail="Feed stats failed")


@router.post("/refresh")
async def refresh_feed(
    background_tasks: BackgroundTasks,
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    mode: str = Query("all", description="all or batch_only"),
):
    """Manuel feed yenileme. Cron secret ile korunan.

    mode:
    - all: batch + monitor (tam yenileme)
    - batch_only: sadece 3 batch (ücretli, günde 2x)
    """
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not x_cron_secret or not hmac.compare_digest(expected, x_cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    if mode not in {"all", "batch_only"}:
        raise HTTPException(status_code=400, detail="Invalid mode. Valid: all, batch_only")

    background_tasks.add_task(_run_feed_refresh, mode)
    return {"status": "accepted", "mode": mode, "message": f"Feed refresh ({mode}) started in background"}


async def _run_feed_refresh(mode: str):
    """Background feed refresh."""
    from services.twitter_trend_fetcher import (
        fetch_all_twitter_signals,
        fetch_batch_signals,
    )

    try:
        if mode == "batch_only":
            result = await fetch_batch_signals()
            logger.info(f"Feed batch refresh: {len(result)} tweets")
        else:
            result = await fetch_all_twitter_signals()
            logger.info(f"Feed full refresh: {len(result)} total signals")
    except Exception as e:
        logger.error(f"Feed refresh error ({mode}): {e}")

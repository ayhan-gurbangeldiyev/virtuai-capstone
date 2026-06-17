"""
Cache Manager — L1 (in-memory) + L2 (Supabase) katmanlı cache.

L1: dict, 5 dakika TTL, process-local
L2: Supabase api_cache tablosu, configurable TTL
"""
import os
import time
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# L1: In-memory cache
_l1_cache: dict = {}
L1_TTL = 300  # 5 dakika

# Supabase
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
_supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL else None


async def cache_get(key: str) -> Optional[Any]:
    """L1 → L2 sırasıyla cache'e bak."""
    # L1 check
    entry = _l1_cache.get(key)
    if entry and entry["expires_at"] > time.time():
        return entry["data"]

    # L1 expired, temizle
    if entry:
        del _l1_cache[key]

    # L2 check (Supabase)
    if not _supabase:
        return None

    try:
        result = (
            _supabase.table("api_cache")
            .select("data, expires_at")
            .eq("cache_key", key)
            .single()
            .execute()
        )
        if result.data:
            from datetime import datetime, timezone
            expires_at = datetime.fromisoformat(
                result.data["expires_at"].replace("Z", "+00:00")
            )
            if expires_at > datetime.now(timezone.utc):
                data = result.data["data"]
                # L1'e de yaz
                _l1_cache[key] = {
                    "data": data,
                    "expires_at": time.time() + L1_TTL,
                }
                return data
            else:
                # Expired, sil
                _supabase.table("api_cache").delete().eq("cache_key", key).execute()
    except Exception as e:
        logger.debug(f"Cache L2 read error [{key}]: {e}")

    return None


async def cache_set(key: str, data: Any, ttl_seconds: int = 1800) -> None:
    """L1 + L2'ye yaz."""
    # L1
    _l1_cache[key] = {
        "data": data,
        "expires_at": time.time() + min(ttl_seconds, L1_TTL),
    }

    # L2 (Supabase)
    if not _supabase:
        return

    try:
        from datetime import datetime, timezone, timedelta
        expires_at = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
        ).isoformat()

        _supabase.table("api_cache").upsert({
            "cache_key": key,
            "data": data,
            "expires_at": expires_at,
        }, on_conflict="cache_key").execute()
    except Exception as e:
        logger.debug(f"Cache L2 write error [{key}]: {e}")


async def cache_delete(key: str) -> None:
    """L1 + L2'den sil."""
    _l1_cache.pop(key, None)
    if _supabase:
        try:
            _supabase.table("api_cache").delete().eq("cache_key", key).execute()
        except Exception:
            pass


def cache_clear_l1() -> int:
    """L1 cache temizle. Returns: silinen entry sayısı."""
    count = len(_l1_cache)
    _l1_cache.clear()
    return count


# ================================================================
# TTL PRESETS
# ================================================================
TTL_ACCOUNT_ANALYSIS = 86400     # 24h
TTL_VIRAL_PATTERNS = 86400       # 24h
TTL_USER_INFO = 43200            # 12h
TTL_VIP_BATCH = 7200             # 2h
TTL_X_TRENDS = 1800              # 30dk
TTL_RADAR = 1800                 # 30dk
TTL_STYLE = 604800               # 7 gün
TTL_COMPOSE = 3600               # 1h

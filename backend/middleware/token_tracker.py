"""
OpenAI Token Usage Tracker - per-user daily limits.
"""
import os
import time
import logging
from collections import defaultdict
from fastapi import HTTPException

logger = logging.getLogger(__name__)

DAILY_TOKEN_LIMIT = int(os.environ.get("DAILY_TOKEN_LIMIT", "500000"))
DISABLE_TOKEN_BUDGET = os.environ.get("DISABLE_TOKEN_BUDGET", "0").lower() in ("1", "true", "yes")
TOKEN_BUDGET_BYPASS_USERS = {
    u.strip() for u in os.environ.get("TOKEN_BUDGET_BYPASS_USERS", "").split(",") if u.strip()
}

# user_id -> {date_str: total_tokens}
_token_usage: dict[str, dict[str, int]] = defaultdict(dict)


def _get_today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def check_token_budget(user_id: str) -> int:
    """Check remaining token budget. Raises 429 if exceeded."""
    if DISABLE_TOKEN_BUDGET or user_id in TOKEN_BUDGET_BYPASS_USERS:
        return DAILY_TOKEN_LIMIT

    today = _get_today()
    user_usage = _token_usage[user_id]

    # Clean old dates
    for old_date in list(user_usage.keys()):
        if old_date != today:
            del user_usage[old_date]

    used = user_usage.get(today, 0)
    if used >= DAILY_TOKEN_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Günlük token limitine ulaştınız ({DAILY_TOKEN_LIMIT} token/gün). Yarın tekrar deneyin."
        )
    return DAILY_TOKEN_LIMIT - used


def record_token_usage(user_id: str, tokens_used: int, supabase=None, generation_id: str = None):
    """Record token usage for a user."""
    today = _get_today()
    user_usage = _token_usage[user_id]

    current = user_usage.get(today, 0)
    user_usage[today] = current + tokens_used

    logger.info(f"Token usage: user={user_id} today={user_usage[today]}/{DAILY_TOKEN_LIMIT} (+{tokens_used})")

    # Optionally write to DB
    if supabase and generation_id:
        try:
            supabase.table("generations").update({
                "tokens_used": tokens_used
            }).eq("id", generation_id).execute()
        except Exception as e:
            logger.warning(f"Failed to update token usage in DB: {e}")

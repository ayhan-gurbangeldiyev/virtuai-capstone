"""
Rate limiter - user_id + IP bazlı istek sınırlama.
Burst koruması, günlük limit, dakikalık limit.
"""
import time
import os
from collections import defaultdict
from fastapi import Request, HTTPException, Depends
from middleware.auth import optional_auth

# ---- Storage ----
# user_id -> [timestamp listesi]
_user_requests: dict[str, list[float]] = defaultdict(list)
# IP -> [timestamp listesi] (fallback for unauthenticated)
_ip_requests: dict[str, list[float]] = defaultdict(list)
# user_id -> daily count tracking {date_str: count}
_daily_counts: dict[str, dict[str, int]] = defaultdict(dict)
# IP/user_id -> ban expiry timestamp
_bans: dict[str, float] = {}

# ---- Config ----
MAX_REQUESTS_PER_MINUTE = int(os.environ.get("RATE_LIMIT_MAX_PER_MIN", "10"))
WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60"))
DAILY_LIMIT = int(os.environ.get("RATE_LIMIT_DAILY_LIMIT", "100"))
BURST_WINDOW = int(os.environ.get("RATE_LIMIT_BURST_WINDOW", "3"))
BURST_MAX = int(os.environ.get("RATE_LIMIT_BURST_MAX", "5"))
BAN_DURATION = int(os.environ.get("RATE_LIMIT_BAN_DURATION", "300"))
RATE_LIMIT_BYPASS_USERS = {
    u.strip() for u in os.environ.get("RATE_LIMIT_BYPASS_USERS", "").split(",") if u.strip()
}

# Trusted proxy IPs (add your infra IPs here)
TRUSTED_PROXIES = set(
    os.environ.get("TRUSTED_PROXIES", "127.0.0.1").split(",")
)


def _get_client_ip(request: Request) -> str:
    """Get real client IP, with X-Forwarded-For spoof protection."""
    client_ip = request.client.host if request.client else "unknown"

    # Only trust X-Forwarded-For from trusted proxies
    if client_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Take the rightmost untrusted IP
            ips = [ip.strip() for ip in forwarded.split(",")]
            for ip in reversed(ips):
                if ip not in TRUSTED_PROXIES:
                    return ip
    return client_ip


def _get_today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


async def rate_limit(request: Request):
    """
    Rate limiter dependency for generate endpoints.
    - User-based if authenticated, IP-based fallback
    - 10/min, 100/day, burst protection (5 in 3s -> 5min ban)
    """
    # Try to get user from auth header (lightweight, no error)
    user = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from middleware.auth import _get_supabase
            token = auth_header.replace("Bearer ", "")
            sb = _get_supabase()
            user_response = sb.auth.get_user(token)
            user = user_response.user
        except Exception:
            pass

    client_ip = _get_client_ip(request)
    identifier = f"user:{user.id}" if user else f"ip:{client_ip}"
    if user and user.id in RATE_LIMIT_BYPASS_USERS:
        return
    now = time.time()

    # --- Check ban ---
    ban_until = _bans.get(identifier, 0)
    if now < ban_until:
        remaining = int(ban_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Geçici olarak engellendiniz. {remaining} saniye sonra tekrar deneyin."
        )

    # --- Get request history ---
    requests_list = _user_requests[identifier]

    # --- Burst detection: 5+ requests in 3 seconds -> ban ---
    burst_cutoff = now - BURST_WINDOW
    recent_burst = [t for t in requests_list if t > burst_cutoff]
    if len(recent_burst) >= BURST_MAX:
        _bans[identifier] = now + BAN_DURATION
        raise HTTPException(
            status_code=429,
            detail=f"Çok hızlı istek gönderiyorsunuz. {BAN_DURATION // 60} dakika beklemeniz gerekiyor."
        )

    # --- Per-minute limit ---
    minute_cutoff = now - WINDOW_SECONDS
    requests_list[:] = [t for t in requests_list if t > minute_cutoff]

    if len(requests_list) >= MAX_REQUESTS_PER_MINUTE:
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla istek. Dakikada en fazla {MAX_REQUESTS_PER_MINUTE} üretim yapabilirsiniz."
        )

    # --- Daily limit (only for authenticated users) ---
    if user:
        today = _get_today()
        user_daily = _daily_counts[user.id]
        # Clean old dates
        for old_date in list(user_daily.keys()):
            if old_date != today:
                del user_daily[old_date]

        daily_count = user_daily.get(today, 0)
        if daily_count >= DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Günlük üretim limitine ulaştınız ({DAILY_LIMIT}/gün). Yarın tekrar deneyin."
            )
        user_daily[today] = daily_count + 1

    # Record request
    requests_list.append(now)

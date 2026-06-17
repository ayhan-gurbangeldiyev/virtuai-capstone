"""
JWT Auth Middleware - Supabase token doğrulama, whitelist kontrolü, brute force koruması.
"""
import os
import time
import logging
from collections import defaultdict
from typing import Optional
from fastapi import Header, HTTPException, Request

logger = logging.getLogger(__name__)

# Env'den izin verilen email listesi (virgülle ayrılmış)
_allowed_raw = os.environ.get("ALLOWED_EMAILS", "")
ALLOWED_EMAILS: set[str] | None = (
    {e.strip().lower() for e in _allowed_raw.split(",") if e.strip()}
    if _allowed_raw.strip()
    else None  # None = fail-closed in production
)

# Fail-closed: ALLOWED_EMAILS boşsa ve DEBUG değilse, kimse geçemez
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

# Brute force koruması
# - Sadece TOKEN VAR + Supabase REJECT durumunda counter artar (gerçek attack
#   pattern: invalid token brute-forcing). "Header yok" = anonim ziyaretçi,
#   sayfa yenileme veya login öncesi check — counter ARTMAZ.
# - Eski ayar 5 / 15dk Berkay'ın 5 sayfa yenilemesinde ban'layıp 429 fırlattı,
#   gerçek brute force değildi. 20 / 5dk daha gerçekçi: gerçek bir attacker
#   saniyede onlarca deneme yapar, normal kullanıcı 5 dk'da 20'ye varmaz.
_failed_attempts: dict[str, list[float]] = defaultdict(list)
_auth_bans: dict[str, float] = {}
MAX_FAILED_ATTEMPTS = 20
BAN_DURATION = 300  # 5 dakika


def _get_supabase():
    """server.py'deki supabase client'ı import et."""
    from server import supabase
    return supabase


def _check_brute_force(client_ip: str):
    """Check if IP is banned from too many failed auth attempts."""
    now = time.time()

    # Check ban
    ban_until = _auth_bans.get(client_ip, 0)
    if now < ban_until:
        remaining = int(ban_until - now)
        raise HTTPException(
            status_code=429,
            detail=f"Çok fazla başarısız giriş denemesi. {remaining} saniye sonra tekrar deneyin."
        )

    # Clean old attempts (older than ban duration)
    cutoff = now - BAN_DURATION
    _failed_attempts[client_ip] = [t for t in _failed_attempts[client_ip] if t > cutoff]


def _record_failed_attempt(client_ip: str):
    """Record a failed auth attempt and ban if threshold exceeded."""
    now = time.time()
    _failed_attempts[client_ip].append(now)

    if len(_failed_attempts[client_ip]) >= MAX_FAILED_ATTEMPTS:
        _auth_bans[client_ip] = now + BAN_DURATION
        _failed_attempts[client_ip].clear()
        logger.warning(f"Auth brute force ban: IP={client_ip} banned for {BAN_DURATION}s")


async def require_auth(authorization: Optional[str] = Header(None), request: Request = None) -> dict:
    """
    Zorunlu auth dependency.
    Bearer token yoksa veya geçersizse 401 döner.
    Whitelist varsa email kontrolü yapar, yoksa fail-closed (prod'da).
    Brute force koruması: 5 başarısız → 15dk ban.
    """
    # Get client IP for brute force tracking
    client_ip = "unknown"
    if request and request.client:
        client_ip = request.client.host

    _check_brute_force(client_ip)

    # Generic error message to prevent account enumeration
    GENERIC_AUTH_ERROR = "Geçersiz kimlik bilgileri"

    # "No Authorization header" anonim ziyaretçi demek (browser yenileme,
    # logged-out state'inde sayfa açma vb). Brute force sayma — sadece
    # 401 dön. Aksi halde 5 sayfa yenileme = 15dk ban yaşanır.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)

    token = authorization.replace("Bearer ", "")
    try:
        sb = _get_supabase()
        user_response = sb.auth.get_user(token)
        user = user_response.user
    except Exception:
        # Token mevcut ama Supabase reddetti — gerçek brute force pattern.
        # Counter artsın.
        _record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)

    if not user:
        _record_failed_attempt(client_ip)
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)

    # Token expiry kontrolü (Supabase handles this via get_user, but double check)
    # Supabase get_user() already validates token expiry, so this is covered.

    # Whitelist kontrolü - FAIL-CLOSED
    if ALLOWED_EMAILS is not None:
        user_email = (user.email or "").lower()
        if user_email not in ALLOWED_EMAILS:
            raise HTTPException(status_code=403, detail="Bu hesap erişim izni olmayan bir kullanıcıya ait")
    elif not DEBUG:
        # ALLOWED_EMAILS not set and not in debug mode -> fail-closed
        logger.error("ALLOWED_EMAILS not configured and DEBUG is off. Blocking all access.")
        raise HTTPException(
            status_code=403,
            detail="Erişim yapılandırması eksik. Yönetici ile iletişime geçin."
        )
    # DEBUG=true alone is NOT sufficient to bypass whitelist; require explicit ALLOW_OPEN_LOGIN=true
    elif os.environ.get("ALLOW_OPEN_LOGIN", "").lower() != "true":
        # DEBUG mode with no ALLOWED_EMAILS and no explicit ALLOW_OPEN_LOGIN -> fail-closed
        logger.error("DEBUG mode active but ALLOW_OPEN_LOGIN is not set to true. Blocking all access.")
        raise HTTPException(
            status_code=403,
            detail="Erişim yapılandırması eksik. Yönetici ile iletişime geçin."
        )
    # else: DEBUG=true + ALLOW_OPEN_LOGIN=true -> allow all (dev mode)

    # Exception handler'lar için user'ı request state'e kaydet
    if request:
        request.state.user = user

    return user


async def optional_auth(authorization: Optional[str] = Header(None)):
    """
    Opsiyonel auth dependency.
    Token varsa user döner, yoksa None döner. Hata fırlatmaz.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.replace("Bearer ", "")
    try:
        sb = _get_supabase()
        user_response = sb.auth.get_user(token)
        return user_response.user
    except Exception:
        return None

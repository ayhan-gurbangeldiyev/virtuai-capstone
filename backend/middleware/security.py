"""
Security Middleware - CSRF, security headers, anti-curl, request fingerprinting.
"""
import os
import logging
from urllib.parse import urlparse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# Allowed origins for CSRF checks
DEBUG = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

ALLOWED_ORIGINS = [
    "https://typehype.io",
    "https://www.typehype.io",
]

# Add Vercel preview URLs pattern
VERCEL_PREVIEW_PATTERN = "frontend-"
VERCEL_DOMAIN = ".vercel.app"

# Lovable preview domains
LOVABLE_DOMAINS = (".lovableproject.com", ".lovable.app")

if DEBUG:
    ALLOWED_ORIGINS.extend([
        "http://localhost:3000",
        "http://localhost:3457",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3457",
    ])

# Extend from env (additive, never replaces production origins)
_env_origins = os.environ.get("CORS_ORIGINS", "")
if _env_origins.strip():
    for _o in _env_origins.split(","):
        _o = _o.strip()
        if _o and _o not in ALLOWED_ORIGINS:
            ALLOWED_ORIGINS.append(_o)


def _is_allowed_origin(origin: str) -> bool:
    """Check if origin is in allowed list or matches Vercel preview pattern."""
    if not origin:
        return False
    if origin in ALLOWED_ORIGINS:
        return True
    # Check Vercel preview pattern
    parsed = urlparse(origin)
    hostname = parsed.hostname or ""
    if hostname.endswith(VERCEL_DOMAIN) and VERCEL_PREVIEW_PATTERN in hostname:
        return True
    # Check Lovable preview pattern
    if any(hostname.endswith(domain) for domain in LOVABLE_DOMAINS):
        return True
    return False


# State-changing methods that need CSRF protection
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths exempt from anti-curl / custom header check
EXEMPT_PATHS = {
    "/api/", "/api/health", "/api/trends/health", "/api/cookies/telegram-update",
    # Cron-triggered endpoints (authenticated via X-Cron-Secret)
    "/api/trends/auto-refresh",
    "/api/trends/process-signals",
    "/api/favorites/auto-purge",
    "/api/cookies/health",
    "/api/feed/refresh",
    "/api/internal/generate-tweet",  # Hype Crew worker (X-Cron-Secret auth)
    # Feed endpoints (public, no auth needed — consumed by Lovable frontend)
    "/api/feed",
    "/api/feed/stats",
    # MCP server endpoint (authenticated via Bearer token)
    "/api/mcp",
}

# Suspicious User-Agent patterns
SUSPICIOUS_UA_PATTERNS = [
    "",  # empty UA
    "curl",
    "wget",
    "httpie",
    "python-requests",
    "go-http-client",
    "java/",
    "libwww",
]


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # --- 1. CSRF: Origin/Referer validation for state-changing requests ---
        if request.method in STATE_CHANGING_METHODS and not path.startswith("/docs") and not path.startswith("/openapi"):
            origin = request.headers.get("origin", "")
            referer = request.headers.get("referer", "")

            # At least one must be present and valid
            origin_ok = _is_allowed_origin(origin) if origin else False
            referer_ok = False
            if referer:
                parsed_ref = urlparse(referer)
                ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}"
                referer_ok = _is_allowed_origin(ref_origin)

            if not origin_ok and not referer_ok:
                # Allow if no origin AND no referer (same-origin non-CORS request from browser)
                # But block if origin is present and invalid
                if origin:
                    logger.warning(f"CSRF blocked: invalid origin={origin} path={path}")
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF doğrulaması başarısız"}
                    )

        # --- 2. Anti-curl: Custom header check (skip exempt paths and OPTIONS) ---
        # Phase 43.D — /api/hype/audits/{id}/{pass|fail} is a Slack-link
        # endpoint. Users click straight from Slack, so no X-TH-Client
        # header is set. The capability is the UUID in the URL.
        if request.method != "OPTIONS" and path not in EXEMPT_PATHS and not path.startswith("/api/accounts/avatar/") and not path.startswith("/api/hype/audits/") and path.startswith("/api/"):
            x_th_client = request.headers.get("x-th-client", "")
            if not x_th_client:
                logger.warning(f"Anti-curl blocked: missing X-TH-Client header, path={path}, UA={request.headers.get('user-agent', '')[:50]}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Geçersiz istemci"}
                )

        # --- 3. Request fingerprinting: suspicious UA check ---
        # Phase 43.D — also exempt the Slack-link audit endpoints.
        if path.startswith("/api/") and path not in EXEMPT_PATHS and not path.startswith("/api/hype/audits/"):
            ua = (request.headers.get("user-agent", "") or "").lower().strip()
            if not ua or any(sus in ua for sus in SUSPICIOUS_UA_PATTERNS if sus):
                # Allow empty check only if UA is truly empty
                if not ua:
                    logger.warning(f"Fingerprint blocked: empty User-Agent, path={path}")
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Geçersiz istemci"}
                    )

        # --- Process request ---
        response: Response = await call_next(request)

        # --- 4. Security headers ---
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: https://*.supabase.co https://pbs.twimg.com; "
            "connect-src 'self' https://*.supabase.co https://api.fxtwitter.com; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"

        return response

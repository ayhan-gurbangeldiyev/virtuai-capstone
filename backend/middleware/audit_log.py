"""
Audit Logging Middleware - tracks auth attempts, generation requests, suspicious patterns.
"""
import time
import logging
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("audit")

# Track IP -> set of user_ids for suspicious pattern detection
_ip_user_map: dict[str, set[str]] = defaultdict(set)
_ip_user_timestamps: dict[str, list[float]] = defaultdict(list)

SUSPICIOUS_USER_THRESHOLD = 5  # 5 different users from same IP in 1 hour
SUSPICIOUS_WINDOW = 3600  # 1 hour

# Paths to audit
GENERATION_PATHS = {"/api/generate/", "/api/analyze/", "/api/repurpose/", "/api/trends/refresh"}
AUTH_PATH = "/api/auth/"


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path
        method = request.method

        response: Response = await call_next(request)
        status = response.status_code

        # Log auth failures
        if status == 401 or status == 403:
            auth_header = request.headers.get("authorization", "")
            # Don't log the actual token
            has_token = "Bearer ***" if auth_header.startswith("Bearer ") else "none"
            logger.warning(
                f"AUTH_FAIL ip={client_ip} path={path} status={status} token={has_token} "
                f"ua={request.headers.get('user-agent', '')[:80]}"
            )

        # Log generation requests
        if method == "POST" and any(path.startswith(p) for p in GENERATION_PATHS):
            # Extract user_id from response headers or auth
            user_id = request.headers.get("authorization", "")[:20] + "..." if request.headers.get("authorization") else "anon"
            logger.info(
                f"GENERATION ip={client_ip} path={path} status={status} "
                f"method={method}"
            )

        # Suspicious pattern detection: multiple users from same IP
        if request.headers.get("authorization", "").startswith("Bearer "):
            token_prefix = request.headers["authorization"][7:15]  # first 8 chars as identifier
            now = time.time()
            _ip_user_map[client_ip].add(token_prefix)
            _ip_user_timestamps[client_ip].append(now)

            # Clean old entries
            cutoff = now - SUSPICIOUS_WINDOW
            _ip_user_timestamps[client_ip] = [
                t for t in _ip_user_timestamps[client_ip] if t > cutoff
            ]

            # Check threshold
            if len(_ip_user_map[client_ip]) >= SUSPICIOUS_USER_THRESHOLD:
                logger.critical(
                    f"SUSPICIOUS_PATTERN ip={client_ip} unique_tokens={len(_ip_user_map[client_ip])} "
                    f"requests_1h={len(_ip_user_timestamps[client_ip])} path={path}"
                )
                # Reset after alerting
                _ip_user_map[client_ip].clear()

        return response

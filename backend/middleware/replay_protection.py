"""
Replay Attack Protection - nonce/timestamp validation.
"""
import time
import logging
from collections import OrderedDict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

MAX_TIMESTAMP_AGE = 300  # 5 minutes
NONCE_CACHE_SIZE = 10000

# LRU-style nonce cache
_seen_nonces: OrderedDict[str, float] = OrderedDict()

# Only protect state-changing generation endpoints
PROTECTED_PATHS = {
    "/api/generate/tweet",
    "/api/generate/quote",
    "/api/generate/reply",
    "/api/generate/article",
    "/api/generate/linkedin",
    "/api/generate/linkedin/carousel",
    "/api/generate/linkedin/hooks",
    "/api/generate/linkedin/analyze",
    "/api/generate/linkedin/image-prompt",
    "/api/generate/instagram/caption",
    "/api/generate/instagram/reel-script",
    "/api/generate/instagram/hashtags",
    "/api/generate/instagram/story-ideas",
    "/api/generate/youtube/idea",
    "/api/generate/youtube/script",
    "/api/generate/youtube/title",
    "/api/generate/youtube/description",
    "/api/generate/tiktok/script",
    "/api/generate/tiktok/caption",
    "/api/generate/blog/outline",
    "/api/generate/blog/full",
    "/api/generate/blog/seo-optimize",
    "/api/generate/blog/cover-image",
    "/api/generate/blog/repurpose",
    "/api/repurpose/video-script",
    "/api/media/generate-image-prompt",
    "/api/analyze/account",
    "/api/trends/refresh",
}


class ReplayProtectionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method != "POST" or request.url.path not in PROTECTED_PATHS:
            return await call_next(request)

        # Check X-TH-Timestamp header
        ts_header = request.headers.get("x-th-timestamp", "")
        nonce_header = request.headers.get("x-th-nonce", "")

        if not ts_header:
            return JSONResponse(
                status_code=400,
                content={"detail": "Timestamp header gerekli (X-TH-Timestamp)"}
            )

        try:
            ts = int(ts_header)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={"detail": "Geçersiz timestamp formatı"}
            )

        now = int(time.time())
        age = now - ts  # Only accept past timestamps, not future

        if age < 0 or age > MAX_TIMESTAMP_AGE:
            logger.warning(f"Replay blocked: timestamp too old ({age}s), path={request.url.path}")
            return JSONResponse(
                status_code=403,
                content={"detail": "İstek süresi dolmuş. Lütfen tekrar deneyin."}
            )

        # Nonce check (optional but recommended)
        if nonce_header:
            if nonce_header in _seen_nonces:
                logger.warning(f"Replay blocked: duplicate nonce={nonce_header[:20]}")
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Tekrarlanan istek tespit edildi."}
                )

            _seen_nonces[nonce_header] = now
            # Evict old nonces
            while len(_seen_nonces) > NONCE_CACHE_SIZE:
                _seen_nonces.popitem(last=False)

        return await call_next(request)

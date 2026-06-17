"""
Request Size Limiter Middleware.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Default: 1MB, image upload endpoints: 5MB
DEFAULT_MAX_BODY = 1 * 1024 * 1024  # 1MB
IMAGE_MAX_BODY = 5 * 1024 * 1024    # 5MB
MAX_URL_LENGTH = 2048

# Paths that accept larger bodies (image uploads)
LARGE_BODY_PATHS = {
    "/api/generate/tweet",  # image_base64 field
    "/api/media/generate-image-prompt",
}


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # URL length check
        full_url = str(request.url)
        if len(full_url) > MAX_URL_LENGTH:
            return JSONResponse(
                status_code=414,
                content={"detail": f"URL çok uzun (max {MAX_URL_LENGTH} karakter)"}
            )

        # Body size check
        content_length = request.headers.get("content-length")
        if content_length:
            size = int(content_length)
            max_allowed = IMAGE_MAX_BODY if request.url.path in LARGE_BODY_PATHS else DEFAULT_MAX_BODY

            if size > max_allowed:
                mb = max_allowed / (1024 * 1024)
                logger.warning(f"Request too large: {size} bytes, path={request.url.path}")
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"İstek boyutu çok büyük (max {mb:.0f}MB)"}
                )

        return await call_next(request)

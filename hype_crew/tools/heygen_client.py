"""Phase 35.2.1 — HeyGen client (Avatar V + photar look + audio asset).

Thin async client over the HeyGen REST API. Used by the
HeyGenAvatarVPipeline strategy registered in `video_pipeline.py`.

API surface (all manual smoke-tested 29-30 May 2026):

  - Upload audio asset    POST upload.heygen.com/v1/asset (audio/mpeg)
  - List avatar group     GET  /v2/avatar_group/{id}/avatars
  - Look engine support   GET  /v3/avatars/looks/{id} (supported_api_engines)
  - Photar look generate  POST /v2/photo_avatar/look/generate    (V2 — disabled in V1 pipeline)
  - Photar look poll      GET  /v2/photo_avatar/generation/{id}
  - Avatar V video gen    POST /v3/videos   engine.type=avatar_v
  - Video status poll     GET  /v1/video_status.get?video_id=...
  - Download MP4          GET  signed URL → bytes

Authentication: `X-Api-Key: <HEYGEN_API_KEY>` header. Configured via
`config.settings.heygen_api_key`. Raises `HeyGenError` on missing key.

This client is INTENTIONALLY isolated:
- No coupling to Flow, no DB writes, no Supabase.
- Failures are propagated to the caller as `HeyGenError` (with HTTP body
  attached) so the pipeline composer can decide on graceful skip.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from loguru import logger

from config import settings


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class HeyGenError(RuntimeError):
    """Wraps any HeyGen API failure with status code + body excerpt."""

    def __init__(self, message: str, *, status_code: int = 0, body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.body = body[:1000]


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HeyGenVideoResult:
    """Output of `wait_for_video()` — minimal stable shape for callers."""

    video_id: str
    video_url: str
    thumbnail_url: Optional[str]
    gif_url: Optional[str]
    duration_sec: float
    poll_count: int
    total_latency_ms: int


@dataclass(frozen=True)
class HeyGenLook:
    """One look from an avatar group (V1 = pick from 78 existing looks)."""

    id: str
    name: Optional[str]
    image_url: str
    preferred_orientation: Optional[str]
    supported_api_engines: list[str]


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class HeyGenClient:
    """Async HeyGen client.

    Usage:
        client = HeyGenClient()
        asset_id = await client.upload_audio_asset(mp3_bytes)
        video_id = await client.generate_avatar_v_video(
            talking_photo_id=look_id,
            audio_asset_id=asset_id,
        )
        result = await client.wait_for_video(video_id)
        mp4_bytes = await client.download(result.video_url)
    """

    UPLOAD_BASE = "https://upload.heygen.com/v1"
    API_BASE = "https://api.heygen.com"

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        request_timeout: float = 60.0,
    ):
        self.api_key = api_key or getattr(settings, "heygen_api_key", None)
        if not self.api_key:
            raise HeyGenError("HEYGEN_API_KEY missing (settings.heygen_api_key)")
        self.request_timeout = request_timeout

    # -----------------------------------------------------------------------
    # Internal HTTP helpers
    # -----------------------------------------------------------------------
    def _headers(self, content_type: Optional[str] = "application/json") -> dict[str, str]:
        h = {"X-Api-Key": self.api_key}
        if content_type:
            h["Content-Type"] = content_type
        return h

    async def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: Optional[dict] = None,
        binary_body: Optional[bytes] = None,
        content_type: Optional[str] = "application/json",
        expect_json: bool = True,
        timeout: Optional[float] = None,
    ) -> Any:
        """Single-shot request with HeyGen error normalization."""
        async with httpx.AsyncClient(
            timeout=timeout or self.request_timeout
        ) as client:
            r = await client.request(
                method,
                url,
                headers=self._headers(content_type=content_type),
                json=json_body if binary_body is None else None,
                content=binary_body,
            )
        if r.status_code >= 400:
            raise HeyGenError(
                f"HeyGen {method} {url} -> {r.status_code}",
                status_code=r.status_code,
                body=r.text or "",
            )
        if not expect_json:
            return r.content
        try:
            data = r.json()
        except Exception as e:
            raise HeyGenError(
                f"HeyGen {method} {url} non-JSON response: {e}",
                status_code=r.status_code,
                body=r.text or "",
            )
        # MiniMax-style internal error envelope { "error": {...}, "data": null }
        if isinstance(data, dict) and data.get("error"):
            err = data["error"]
            err_msg = err.get("message") if isinstance(err, dict) else str(err)
            err_code = err.get("code") if isinstance(err, dict) else None
            raise HeyGenError(
                f"HeyGen {method} {url} error: {err_msg} (code={err_code})",
                status_code=r.status_code,
                body=r.text or "",
            )
        return data

    # -----------------------------------------------------------------------
    # Quota / bakiye probu (2026-06-10, otonomi D0-3)
    # HeyGen kredisi 2026-06-10'da pipeline ORTASINDA sessizce bitti
    # (MOVIO_PAYMENT_INSUFFICIENT_CREDIT) — render başlatılıp para/zaman
    # yakıldıktan sonra öğrenildi. Bu prob render ÖNCESİ çağrılır.
    async def get_remaining_quota(self) -> Optional[float]:
        """Kalan API kredisini döndürür (HeyGen 'quota' birimi; 60 quota
        ≈ 1 API kredisi ≈ ~1 sn avatar video). Endpoint hatasında None
        döner — çağıran fail-open davranır (probe kesintisi render'ı
        durdurmamalı), ama None'ı loglar."""
        try:
            data = await self._request(
                "GET", f"{self.API_BASE}/v2/user/remaining_quota", timeout=15.0,
            )
            q = (data.get("data") or {}).get("remaining_quota")
            return float(q) if q is not None else None
        except Exception as e:  # noqa: BLE001
            logger.warning(f"heygen.get_remaining_quota probe hatası: {e}")
            return None


    # -----------------------------------------------------------------------
    # Audio asset upload
    # -----------------------------------------------------------------------
    async def upload_audio_asset(self, mp3_bytes: bytes) -> str:
        """POST /v1/asset (Content-Type: audio/mpeg). Returns asset id."""
        if not mp3_bytes:
            raise HeyGenError("upload_audio_asset: empty mp3_bytes")
        data = await self._request(
            "POST",
            f"{self.UPLOAD_BASE}/asset",
            binary_body=mp3_bytes,
            content_type="audio/mpeg",
        )
        # Response shape: {"code":100,"data":{"id":"...","file_type":"audio",...}}
        asset_id = (data or {}).get("data", {}).get("id")
        if not asset_id:
            raise HeyGenError(
                f"upload_audio_asset: no id in response: {str(data)[:300]}"
            )
        logger.info(
            f"heygen.upload_audio_asset: size={len(mp3_bytes)}B asset_id={asset_id}"
        )
        return asset_id

    # -----------------------------------------------------------------------
    # Avatar group / look introspection
    # -----------------------------------------------------------------------
    async def list_avatar_group(self, group_id: str) -> list[HeyGenLook]:
        """GET /v2/avatar_group/{id}/avatars → list of looks."""
        data = await self._request(
            "GET",
            f"{self.API_BASE}/v2/avatar_group/{group_id}/avatars",
        )
        raw = ((data or {}).get("data") or {}).get("avatar_list") or []
        # avatar_list rows only have id + image_url; engine list needs v3 call.
        return [
            HeyGenLook(
                id=r.get("id", ""),
                name=None,
                image_url=r.get("image_url", ""),
                preferred_orientation=None,
                supported_api_engines=[],
            )
            for r in raw
            if r.get("id")
        ]

    async def get_look(self, look_id: str) -> HeyGenLook:
        """GET /v3/avatars/looks/{id} — engines + orientation + name."""
        data = await self._request(
            "GET",
            f"{self.API_BASE}/v3/avatars/looks/{look_id}",
        )
        d = (data or {}).get("data") or {}
        return HeyGenLook(
            id=d.get("id", look_id),
            name=d.get("name"),
            image_url=d.get("preview_image_url", ""),
            preferred_orientation=d.get("preferred_orientation"),
            supported_api_engines=list(d.get("supported_api_engines") or []),
        )

    # -----------------------------------------------------------------------
    # Photar look generation (V2 path — DISABLED in pipeline V1 due to
    # quality concerns; helper kept for future quality iteration)
    # -----------------------------------------------------------------------
    async def generate_photar_look(
        self,
        group_id: str,
        prompt: str,
        *,
        orientation: str = "vertical",
        pose: str = "half_body",
        style: str = "Realistic",
    ) -> str:
        """POST /v2/photo_avatar/look/generate. Returns generation_id."""
        body = {
            "group_id": group_id,
            "prompt": prompt,
            "orientation": orientation,
            "pose": pose,
            "style": style,
        }
        data = await self._request(
            "POST",
            f"{self.API_BASE}/v2/photo_avatar/look/generate",
            json_body=body,
        )
        gen_id = ((data or {}).get("data") or {}).get("generation_id")
        if not gen_id:
            raise HeyGenError(
                f"generate_photar_look: no generation_id: {str(data)[:300]}"
            )
        return gen_id

    async def wait_for_photar_look(
        self,
        generation_id: str,
        *,
        poll_interval_sec: float = 8.0,
        timeout_sec: float = 240.0,
    ) -> list[str]:
        """Poll generation status, return list of talking_photo_id (1+)."""
        url = f"{self.API_BASE}/v2/photo_avatar/generation/{generation_id}"
        deadline = time.time() + timeout_sec
        polls = 0
        while time.time() < deadline:
            data = await self._request("GET", url)
            d = (data or {}).get("data") or {}
            status = d.get("status")
            polls += 1
            if status == "success":
                ids = d.get("image_key_list") or []
                # Map image_key → talking_photo_id format. HeyGen returns
                # image_key like "photo_generation/<gen_id>/<uuid>.jpg".
                # For Avatar V we need actual talking_photo_id from the group;
                # in practice the generation result needs to be promoted into
                # the group first via separate endpoint. V2 PATH RESERVED.
                logger.warning(
                    "wait_for_photar_look: success but talking_photo_id promotion "
                    "not yet implemented; returning image keys for inspection only"
                )
                return list(ids)
            if status in {"failed", "error"}:
                err = d.get("msg") or "unknown"
                raise HeyGenError(f"photar generation {status}: {err}")
            await asyncio.sleep(poll_interval_sec)
        raise HeyGenError(
            f"photar generation timeout after {timeout_sec}s ({polls} polls)"
        )

    # -----------------------------------------------------------------------
    # Avatar V video generation (V3 endpoint)
    # -----------------------------------------------------------------------
    async def generate_avatar_v_video(
        self,
        talking_photo_id: str,
        audio_asset_id: str,
        *,
        aspect_ratio: str = "9:16",
        resolution: str = "1080p",
        title: Optional[str] = None,
        caption: bool = True,
    ) -> str:
        """POST /v3/videos with engine.type=avatar_v.

        Smoke-tested 30 May 2026: same as Berkay's manual Cansu pipeline.
        Returns video_id (async job).

        `caption=True` (Phase 35.2.11) enables HeyGen's native subtitle
        burn-in — replaces the heuristic FFmpeg captions which Berkay
        rejected for being out of sync.
        """
        body: dict[str, Any] = {
            "type": "avatar",
            "avatar_id": talking_photo_id,
            "audio_asset_id": audio_asset_id,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "engine": {"type": "avatar_v"},
        }
        # NOTE: v3/videos rejects `caption` field (400) — confirmed
        # 30 May 2026 Phase 35.2.11. v3 schema does NOT expose a caption
        # toggle. The `caption` parameter is kept on the function signature
        # for forward compat but ignored. Surface subtitles via a different
        # pipeline step (Wiro Whisper, etc.).
        _ = caption  # explicitly acknowledge unused (forward-compat shim)
        if title:
            body["title"] = title
        data = await self._request(
            "POST",
            f"{self.API_BASE}/v3/videos",
            json_body=body,
        )
        video_id = ((data or {}).get("data") or {}).get("video_id")
        if not video_id:
            raise HeyGenError(
                f"generate_avatar_v_video: no video_id: {str(data)[:300]}"
            )
        logger.info(
            f"heygen.generate_avatar_v_video: look={talking_photo_id[:8]} "
            f"asset={audio_asset_id[:8]} video_id={video_id}"
        )
        return video_id

    async def wait_for_video(
        self,
        video_id: str,
        *,
        poll_interval_sec: float = 15.0,
        timeout_sec: float = 600.0,
    ) -> HeyGenVideoResult:
        """Poll /v1/video_status.get until completed/failed.

        Avatar V typically completes in 60-180s for 20s scripts.
        Falls back to /v1 endpoint which gives URL + duration cleanly.
        """
        url = f"{self.API_BASE}/v1/video_status.get?video_id={video_id}"
        deadline = time.time() + timeout_sec
        t0 = time.perf_counter()
        polls = 0
        while time.time() < deadline:
            data = await self._request("GET", url)
            d = (data or {}).get("data") or {}
            status = d.get("status")
            polls += 1
            if status == "completed":
                duration = float(d.get("duration") or 0.0)
                result = HeyGenVideoResult(
                    video_id=video_id,
                    video_url=d.get("video_url") or "",
                    thumbnail_url=d.get("thumbnail_url"),
                    gif_url=d.get("gif_url"),
                    duration_sec=duration,
                    poll_count=polls,
                    total_latency_ms=int((time.perf_counter() - t0) * 1000),
                )
                logger.info(
                    f"heygen.wait_for_video: completed video_id={video_id} "
                    f"polls={polls} duration={duration:.2f}s "
                    f"latency_ms={result.total_latency_ms}"
                )
                return result
            if status == "failed":
                err = d.get("error") or "unknown"
                raise HeyGenError(f"video {video_id} failed: {err}")
            await asyncio.sleep(poll_interval_sec)
        raise HeyGenError(
            f"video {video_id} timeout after {timeout_sec}s ({polls} polls)"
        )

    # -----------------------------------------------------------------------
    # Download (signed URL → bytes)
    # -----------------------------------------------------------------------
    async def download(self, url: str, *, timeout: float = 120.0) -> bytes:
        """GET signed URL with follow_redirects. Returns binary content."""
        if not url:
            raise HeyGenError("download: empty url")
        async with httpx.AsyncClient(
            timeout=timeout, follow_redirects=True
        ) as client:
            r = await client.get(url)
            if r.status_code >= 400:
                raise HeyGenError(
                    f"download GET {url[:80]}... -> {r.status_code}",
                    status_code=r.status_code,
                    body=r.text or "",
                )
            return r.content

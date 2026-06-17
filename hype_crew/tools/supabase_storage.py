"""Supabase Storage async client for Hype Crew anchor + generated assets.

Ported from VirtuAI providers/supabase_storage.py.
Adapted: uses hype_crew.config.settings (no mock mode).
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote, urljoin

import httpx
from loguru import logger

from config import settings


@dataclass(frozen=True)
class UploadResult:
    storage_key: str
    public_url: str
    bucket: str
    content_hash: str
    size_bytes: int
    latency_ms: int


class StorageClient(Protocol):
    async def upload_bytes(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> UploadResult: ...


class SupabaseStorage:
    """Async Supabase Storage REST client using the service-role key."""

    def __init__(
        self,
        supabase_url: str | None = None,
        service_role_key: str | None = None,
        public_url_base: str | None = None,
    ) -> None:
        self.supabase_url = (supabase_url or settings.supabase_url).rstrip("/")
        self.service_role_key = service_role_key or settings.supabase_service_key
        self.public_url_base = (public_url_base or self.supabase_url).rstrip("/")

    async def upload_bytes(
        self,
        *,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        upsert: bool = False,
    ) -> UploadResult:
        if not self.supabase_url:
            raise RuntimeError("SUPABASE_URL is required for Supabase Storage uploads")
        if not self.service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_KEY is required for Supabase Storage uploads")

        upload_url = self._object_url(bucket, key)
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                upload_url,
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": content_type,
                    "cache-control": "31536000",
                    "x-upsert": "true" if upsert else "false",
                },
                content=data,
            )
        response.raise_for_status()
        latency_ms = int((time.perf_counter() - t0) * 1000)

        logger.info(f"supabase_storage.upload bucket={bucket} key={key} size={len(data)} ms={latency_ms}")

        return UploadResult(
            storage_key=key,
            public_url=self.public_url(bucket, key),
            bucket=bucket,
            content_hash=self._sha256(data),
            size_bytes=len(data),
            latency_ms=latency_ms,
        )

    async def download_bytes(self, bucket: str, key: str) -> bytes:
        """Download raw bytes from a Supabase Storage object (works for both public+private)."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                self._object_url(bucket, key),
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                },
            )
        response.raise_for_status()
        return response.content

    def public_url(self, bucket: str, key: str) -> str:
        encoded_key = quote(key.strip("/"), safe="/")
        return f"{self.public_url_base}/storage/v1/object/public/{bucket}/{encoded_key}"

    async def signed_url(
        self,
        bucket: str,
        key: str,
        *,
        expires_seconds: int = 3600,
    ) -> str:
        if not self.supabase_url:
            raise RuntimeError("SUPABASE_URL is required for Supabase Storage signed URLs")
        if not self.service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_KEY is required for Supabase Storage signed URLs")

        sign_url = self._sign_url(bucket, key)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                sign_url,
                headers={
                    "apikey": self.service_role_key,
                    "Authorization": f"Bearer {self.service_role_key}",
                    "Content-Type": "application/json",
                },
                json={"expiresIn": expires_seconds},
            )
        response.raise_for_status()
        payload = response.json()
        signed_path = payload.get("signedURL") or payload.get("signedUrl")
        if not isinstance(signed_path, str) or not signed_path:
            raise RuntimeError("Supabase signed URL response did not include a signed URL")
        if signed_path.startswith("http://") or signed_path.startswith("https://"):
            return signed_path
        return urljoin(f"{self.supabase_url}/", _normalize_signed_storage_path(signed_path))

    def _object_url(self, bucket: str, key: str) -> str:
        encoded_key = quote(key.strip("/"), safe="/")
        return f"{self.supabase_url}/storage/v1/object/{bucket}/{encoded_key}"

    def _sign_url(self, bucket: str, key: str) -> str:
        encoded_key = quote(key.strip("/"), safe="/")
        return f"{self.supabase_url}/storage/v1/object/sign/{bucket}/{encoded_key}"

    @staticmethod
    def _sha256(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def make_key(*, prefix: str, filename: str | None = None, ext: str = "bin") -> str:
        if filename:
            return f"{prefix.rstrip('/')}/{filename}"
        return f"{prefix.rstrip('/')}/{uuid.uuid4()}.{ext}"


def _normalize_signed_storage_path(path: str) -> str:
    normalized = path.lstrip("/")
    if normalized.startswith("object/"):
        return f"storage/v1/{normalized}"
    return normalized

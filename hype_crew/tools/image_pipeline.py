"""End-to-end image pipeline: Wiro → watermark → Supabase Storage → persona_assets row.

Simplified port of VirtuAI providers/image_asset_pipeline.py for Hype Crew:
- No org_id (single-tenant TypeHype)
- No SQLAlchemy ORM (direct Supabase REST via tools.supabase_client.make_supabase)
- No mock_mode branch (user decision: real Wiro only)
- Generated images go to public bucket persona-generated, status='generated'
- Compliance scores stay null at this stage (filled by separate compliance gate in PART 3)
"""
from __future__ import annotations

import base64
import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Literal, Optional

import httpx
from loguru import logger
from PIL import Image, ImageDraw

from config import settings
from .image_watermark import apply_ai_watermark
from .supabase_client import make_supabase
from .supabase_storage import SupabaseStorage, UploadResult
from .visual_prompt import VisualPromptBrief, enhance_visual_prompt
from .wiro_client import GenerationResult, WiroClient


@dataclass(frozen=True)
class DownloadedImage:
    data: bytes
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class StoredImageAsset:
    asset_id: str
    public_url: str
    storage_key: str
    bucket: str
    content_hash: str
    file_size_bytes: int
    generation: GenerationResult
    upload: UploadResult


async def generate_and_store_wiro_image_asset(
    *,
    persona_id: str,
    prompt: str,
    slug: str | None = None,
    aspect_ratio: str = "1:1",
    resolution: str = "2K",
    max_images: int = 1,
    negative_prompt: str | None = None,
    input_image: str | list[str] | None = None,
    ai_watermark: bool = False,  # Berkay 30 May 2026: "AI generated asla istemiyorum"
    watermark_text: str = "AI generated",
    asset_status: Literal["generated", "compliance_passed", "publish_ready"] = "generated",
    generation_metadata_overrides: dict[str, Any] | None = None,
    daily_draft_id: str | None = None,
    storage: SupabaseStorage | None = None,
) -> StoredImageAsset:
    """Generate one image with Wiro, watermark it, store in Supabase, insert persona_assets row."""
    model_slug = slug or settings.wiro_image_default_slug

    async with WiroClient() as client:
        generation = await client.generate_image(
            slug=model_slug,
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            max_images=max_images,
            watermark=False,  # Wiro's built-in WM off — we apply our own
            negative_prompt=negative_prompt,
            input_image=input_image,
        )

    return await store_wiro_image_asset(
        persona_id=persona_id,
        generation=generation,
        prompt=prompt,
        ai_watermark=ai_watermark,
        watermark_text=watermark_text,
        asset_status=asset_status,
        generation_metadata_overrides=generation_metadata_overrides,
        daily_draft_id=daily_draft_id,
        storage=storage,
    )


async def generate_and_store_visual_brief_asset(
    *,
    persona_id: str,
    brief: VisualPromptBrief,
    slug: str | None = None,
    resolution: str = "2K",
    max_images: int = 1,
    ai_watermark: bool = False,  # Berkay 30 May 2026: "AI generated asla istemiyorum"
    asset_status: Literal["generated", "compliance_passed", "publish_ready"] = "generated",
    generation_metadata_overrides: dict[str, Any] | None = None,
    daily_draft_id: str | None = None,
    storage: SupabaseStorage | None = None,
) -> StoredImageAsset:
    """Build prompt from VisualPromptBrief then generate + store."""
    model_slug = slug or settings.wiro_image_default_slug
    enhanced = enhance_visual_prompt(brief, model_slug=model_slug)
    if not enhanced.qc_passed:
        raise RuntimeError(
            "Visual prompt QC failed: " + ", ".join(enhanced.warnings or ["unknown"])
        )
    prompt_metadata = {
        "prompt_mode": enhanced.mode,
        "prompt_model_target": enhanced.model_target,
        "prompt_qc_passed": enhanced.qc_passed,
        "prompt_warnings": enhanced.warnings,
        "prompt_fallback_applied": enhanced.fallback_applied,
        "platform_target_aspect": enhanced.platform_target_aspect,
        "emitted_aspect": enhanced.emitted_aspect,
        "brief_platform": brief.platform,
        "brief_scene_description": brief.scene_description,
        "brief_outfit": brief.outfit,
        "brief_mood": brief.mood,
        # Phase 25.H — persisted on persona_assets row by downstream insert
        # via the `visual_mode` column override below.
        "visual_mode": getattr(brief, "visual_mode", "face"),
    }
    merged_metadata = {**prompt_metadata, **(generation_metadata_overrides or {})}
    return await generate_and_store_wiro_image_asset(
        persona_id=persona_id,
        prompt=enhanced.prompt,
        slug=model_slug,
        aspect_ratio=enhanced.aspect_ratio,
        resolution=resolution,
        max_images=max_images,
        negative_prompt=enhanced.negative_prompt or None,
        input_image=enhanced.wiro_input_image,
        ai_watermark=ai_watermark,
        asset_status=asset_status,
        generation_metadata_overrides=merged_metadata,
        daily_draft_id=daily_draft_id,
        storage=storage,
    )


async def store_wiro_image_asset(
    *,
    persona_id: str,
    generation: GenerationResult,
    prompt: str,
    ai_watermark: bool = False,  # Berkay 30 May 2026: "AI generated asla istemiyorum"
    watermark_text: str = "AI generated",
    asset_status: Literal["generated", "compliance_passed", "publish_ready"] = "generated",
    generation_metadata_overrides: dict[str, Any] | None = None,
    daily_draft_id: str | None = None,
    storage: SupabaseStorage | None = None,
) -> StoredImageAsset:
    """Download Wiro asset, optionally watermark, upload to Supabase, insert DB row."""
    image = await download_image(generation.asset_url)
    watermark_metadata: dict[str, object] = {"applied": False}
    if ai_watermark:
        wm = apply_ai_watermark(
            image.data,
            image.content_type,
            text=watermark_text,
            position="bottom_right",
        )
        watermark_metadata = {
            "applied": True,
            "text": wm.text,
            "position": wm.position,
            "width": wm.width,
            "height": wm.height,
            "source_content_type": image.content_type,
        }
        image = DownloadedImage(
            data=wm.data,
            content_type=wm.content_type,
            size_bytes=len(wm.data),
        )

    storage_client = storage or SupabaseStorage()
    bucket = settings.supabase_generated_bucket
    storage_key = _storage_key_for_generation(
        persona_id=persona_id,
        generation=generation,
        content_type=image.content_type,
    )
    upload = await storage_client.upload_bytes(
        bucket=bucket,
        key=storage_key,
        data=image.data,
        content_type=image.content_type,
        upsert=True,
    )

    # Compose metadata
    metadata: dict[str, Any] = {
        "provider_task_uuid": generation.task_uuid,
        "provider_asset_url": generation.asset_url,
        "provider_cost_usd": generation.cost_usd,
        "provider_latency_ms": generation.latency_ms,
        "storage_provider": "supabase_storage",
        "storage_bucket": bucket,
        "ai_watermark": watermark_metadata,
        "generation_prompt": prompt,
    }
    if generation_metadata_overrides:
        metadata.update(generation_metadata_overrides)

    # Determine dimensions from watermark result or original
    width = watermark_metadata.get("width") if watermark_metadata.get("applied") else None
    height = watermark_metadata.get("height") if watermark_metadata.get("applied") else None

    # Insert persona_assets row
    sb = make_supabase()
    # Phase 25.H — visual_mode column (face/conceptual/hybrid) — pulled from
    # metadata if the caller chained generate_and_store_visual_brief_asset.
    visual_mode_val = metadata.get("visual_mode") if isinstance(metadata, dict) else None
    row = {
        "persona_id": persona_id,
        "asset_type": "generated_image",
        "status": asset_status,
        "storage_bucket": upload.bucket,
        "storage_key": upload.storage_key,
        "public_url": upload.public_url,
        "content_hash": upload.content_hash,
        "mime_type": image.content_type,
        "file_size_bytes": upload.size_bytes,
        "width": width,
        "height": height,
        "provider": "wiro",
        "provider_model_slug": generation.model_slug,
        "provider_task_uuid": generation.task_uuid,
        "generation_metadata": metadata,
        "generation_cost_usd": float(generation.cost_usd),
        "generation_latency_ms": int(generation.latency_ms),
        "daily_draft_id": daily_draft_id,
        "visual_mode": visual_mode_val,
    }
    result = sb.table("persona_assets").insert(row).execute()
    asset_row = result.data[0]
    logger.info(
        f"persona_assets row inserted: {asset_row['id']} "
        f"slug={generation.model_slug} cost=${generation.cost_usd}"
    )

    return StoredImageAsset(
        asset_id=asset_row["id"],
        public_url=upload.public_url,
        storage_key=upload.storage_key,
        bucket=upload.bucket,
        content_hash=upload.content_hash,
        file_size_bytes=upload.size_bytes,
        generation=generation,
        upload=upload,
    )


# ─── Phase 38 — Curated photo reuse helper (Berkay 31 May 2026) ─────────


async def store_curated_photo_as_draft_asset(
    *,
    persona_id: str,
    curated: "CuratedPhoto",  # type: ignore[name-defined]
    daily_draft_id: Optional[str] = None,
    visual_mode: str = "face",
) -> dict[str, Any]:
    """Reuse a `curated_photo` persona_assets row for a new draft.

    No re-upload: curated photos already live in persona-generated/{id}/curated/.
    We just (a) optionally link to the daily_draft via metadata + (b) return
    the same URL/asset_id shape that `_generate_and_check_async` expects.

    Compliance gate is skipped because the curated_photo was pre-approved by
    the user (Berkay-curated, HeyGen "Design with AI" output).
    """
    sb = make_supabase()

    # Update the curated row's daily_draft_id pointer so feed enrichment can
    # backref correctly. Optional — non-fatal if it fails.
    if daily_draft_id:
        try:
            sb.table("persona_assets").update({
                "daily_draft_id": daily_draft_id,
                "visual_mode": visual_mode,
            }).eq("id", curated.asset_id).execute()
        except Exception as e:
            logger.warning(
                f"[curated_photo] link to daily_draft {daily_draft_id} failed (non-fatal): {e}"
            )

    return {
        "asset_id": curated.asset_id,
        "public_url": curated.public_url,
        "storage_key": curated.storage_key,
        "name": curated.name,
        "heygen_id": curated.heygen_id,
    }


async def download_image(url: str) -> DownloadedImage:
    """Download generated image bytes from Wiro asset URL."""
    if url.startswith("data:image/"):
        return _decode_data_url_image(url)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        response = await client.get(url)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    if not content_type.startswith("image/"):
        # Fall back: infer from URL extension
        lower = url.lower()
        if lower.endswith(".jpg") or lower.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif lower.endswith(".png"):
            content_type = "image/png"
        elif lower.endswith(".webp"):
            content_type = "image/webp"
        else:
            raise RuntimeError(
                f"Expected image content from Wiro URL, got {content_type or 'unknown'}"
            )
    data = response.content
    if not data:
        raise RuntimeError("Wiro image URL returned an empty response body")
    return DownloadedImage(data=data, content_type=content_type, size_bytes=len(data))


def _decode_data_url_image(url: str) -> DownloadedImage:
    header, _, payload = url.partition(",")
    content_type = header.removeprefix("data:").split(";", 1)[0]
    if not content_type.startswith("image/") or not payload:
        raise RuntimeError("Expected image data URL from generated image provider")
    data = base64.b64decode(payload)
    return DownloadedImage(data=data, content_type=content_type, size_bytes=len(data))


def _storage_key_for_generation(
    *,
    persona_id: str,
    generation: GenerationResult,
    content_type: str,
) -> str:
    day = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    task = _slugify_key_part(generation.task_uuid)
    ext = _extension_for_content_type(content_type)
    return f"{persona_id}/{day}/{task}.{ext}"


def _extension_for_content_type(content_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }.get(content_type, "bin")


def _slugify_key_part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in value)
    return cleaned.strip("-_") or str(uuid.uuid4())

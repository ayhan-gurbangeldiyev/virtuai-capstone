"""Phase 38 — Sync HeyGen AI-generated Cansu looks to Supabase library.

Berkay 31 May 2026: HeyGen UI'da "Design with AI" ile ürettiği 11 look'u
(business_type='generated') sistemimize indir + Supabase storage'a permanent
upload + persona_assets'a `asset_type='curated_photo'` insert.

Sonuç: VisualDirector face mode bu kütüphaneden seçim yapar (Wiro Seedream
yerine) → kalite Berkay-garantili, AI hatası yok.

Idempotent: aynı heygen_id zaten persona_assets'ta varsa skip.

Kullanım:
    cd /opt/hype-crew && venv/bin/python -m scripts.sync_heygen_curated --persona-slug=cansu_dut
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from loguru import logger

from config import settings
from tools.supabase_client import make_supabase
from tools.supabase_storage import SupabaseStorage


CANSU_GROUP_ID = "f9d9c017a46d4e2da9fbbb4d9e6cbe2a"


async def fetch_generated_avatars(api_key: str, group_id: str) -> list[dict[str, Any]]:
    """List all avatars in the HeyGen group, filter to business_type='generated'."""
    url = f"https://api.heygen.com/v2/avatar_group/{group_id}/avatars"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, headers={"X-Api-Key": api_key})
        r.raise_for_status()
        data = r.json()
    arr = data.get("data") or []
    if isinstance(arr, dict):
        arr = arr.get("avatar_list") or arr.get("list") or arr.get("avatars") or []
    generated = [a for a in arr if a.get("business_type") == "generated"]
    logger.info(f"HeyGen group {group_id[:8]}: {len(arr)} total, {len(generated)} generated")
    return generated


async def download_image(url: str) -> tuple[bytes, str]:
    """Returns (bytes, content_type)."""
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "image/webp").split(";")[0].strip()
        return r.content, ct


def already_synced(sb, persona_id: str, heygen_id: str) -> Optional[str]:
    """Return existing persona_assets.id if this heygen_id is already in library."""
    res = (
        sb.table("persona_assets")
        .select("id")
        .eq("persona_id", persona_id)
        .eq("asset_type", "curated_photo")
        .filter("generation_metadata->>heygen_id", "eq", heygen_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0]["id"] if rows else None


async def sync_one(
    *,
    sb,
    storage: SupabaseStorage,
    persona_id: str,
    avatar: dict[str, Any],
    default_composition_style: Optional[str] = None,
    skip_clip_gate: bool = False,
) -> dict[str, Any]:
    heygen_id = avatar["id"]
    name = avatar.get("name", "Untitled")
    src_url = avatar.get("image_url") or avatar.get("preview_image_url")
    if not src_url:
        return {"heygen_id": heygen_id, "status": "skipped", "reason": "no image_url"}

    existing_id = already_synced(sb, persona_id, heygen_id)
    if existing_id:
        return {"heygen_id": heygen_id, "name": name, "status": "skipped_existing", "asset_id": existing_id}

    # Phase 40.A — fetch Avatar V eligibility via /v3/avatars/looks/{id}.
    # Picker filters by this so we don't try to render a look on an engine
    # it doesn't support (HeyGen would 400 the video gen call).
    supported_engines: list[str] = []
    try:
        from tools.heygen_client import HeyGenClient
        hg = HeyGenClient()
        look_detail = await hg.get_look(heygen_id)
        supported_engines = list(look_detail.supported_api_engines or [])
    except Exception as e:
        logger.warning(f"[sync] {heygen_id[:8]}: get_look failed, skipping engine list: {e}")

    # Download
    t0 = time.perf_counter()
    img_bytes, content_type = await download_image(src_url)
    ext = "webp" if "webp" in content_type else ("jpg" if "jpeg" in content_type else "png")
    content_hash = hashlib.sha256(img_bytes).hexdigest()

    # Phase 42.C — CLIP-similarity gate against the existing curated baseline
    # (mean embedding of publish_ready photos). PASS → status='publish_ready'.
    # NEEDS_REVIEW → status='needs_review' (invisible to picker until
    # Berkay flips it). REJECT → skip the insert entirely.
    # The gate is FAIL-SAFE: any embedding or download error returns
    # SKIPPED and we proceed with the original publish_ready status.
    gate_meta: dict[str, Any] = {}
    target_status = "publish_ready"
    if not skip_clip_gate:
        try:
            from tools.curated_clip_gate import check_curated_photo
            gate = check_curated_photo(persona_id=persona_id, new_image_bytes=img_bytes)
            gate_meta = {
                "verdict": gate.verdict,
                "score": gate.score,
                "baseline_size": gate.baseline_size,
                "threshold_pass": gate.threshold_pass,
                "threshold_review": gate.threshold_review,
                "reason": gate.reason,
            }
            if gate.verdict == "REJECT":
                logger.error(
                    f"[sync] {heygen_id[:8]} REJECTED by CLIP gate "
                    f"(score={gate.score}, baseline={gate.baseline_size}): {gate.reason}"
                )
                return {
                    "heygen_id": heygen_id,
                    "name": name,
                    "status": "rejected_clip_drift",
                    "reason": gate.reason,
                    "score": gate.score,
                }
            if gate.verdict == "NEEDS_REVIEW":
                # Phase 42.C v2 — `needs_review` is NOT in asset_status_enum.
                # Park the row at `publish_ready` but stamp the verdict on
                # metadata so the picker (curated_photo_selector) can
                # pre-filter NEEDS_REVIEW rows out of its candidate pool
                # without an enum migration. Berkay can promote the photo
                # by removing the metadata flag (Supabase Studio) once he
                # eye-balls the drift.
                logger.warning(
                    f"[sync] {heygen_id[:8]} NEEDS_REVIEW by CLIP gate "
                    f"(score={gate.score}): row will land as 'publish_ready' "
                    f"with metadata.clip_gate.verdict='NEEDS_REVIEW' "
                    f"— picker will skip it until the flag is cleared."
                )
        except Exception as e:
            logger.warning(
                f"[sync] {heygen_id[:8]}: CLIP gate raised "
                f"({type(e).__name__}: {e}); proceeding as publish_ready (fail-safe)"
            )

    # Upload to persona-generated bucket, path with /curated/ prefix
    storage_key = f"{persona_id}/curated/{heygen_id}.{ext}"
    bucket = settings.supabase_generated_bucket  # 'persona-generated'
    upload = await storage.upload_bytes(
        bucket=bucket,
        key=storage_key,
        data=img_bytes,
        content_type=content_type,
        upsert=True,
    )

    # persona_assets row
    metadata: dict[str, Any] = {
        "heygen_id": heygen_id,
        "name": name,
        "business_type": "generated",
        "synced_from": "v2/avatar_group/{group_id}/avatars",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "source_signed_url": src_url[:200],
        # Phase 40.A — Avatar V eligibility check (picker filters by this)
        "supported_api_engines": supported_engines,
    }
    # Phase 42.C — tag composition_style if caller specified one. The
    # curated_photo_selector pre-filters by this when the Visual Decision
    # Agent picks cansu_scene vs cansu_selfie.
    if default_composition_style:
        metadata["composition_style"] = default_composition_style
    # Phase 42.C — persist CLIP gate verdict (kept on every photo for audit)
    if gate_meta:
        metadata["clip_gate"] = gate_meta

    row = {
        "persona_id": persona_id,
        "asset_type": "curated_photo",
        "status": target_status,
        "storage_bucket": bucket,
        "storage_key": storage_key,
        "public_url": upload.public_url,
        "content_hash": content_hash,
        "mime_type": content_type,
        "file_size_bytes": len(img_bytes),
        "provider": "heygen",
        "provider_model_slug": "photo_avatar_look_generate",
        "provider_task_uuid": heygen_id,
        "generation_metadata": metadata,
        "generation_cost_usd": 0.0,  # already paid via HeyGen UI
        "generation_latency_ms": int((time.perf_counter() - t0) * 1000),
    }
    result = sb.table("persona_assets").insert(row).execute()
    asset_id = result.data[0]["id"]
    return {
        "heygen_id": heygen_id,
        "name": name,
        "status": "synced",
        "row_status": target_status,
        "asset_id": asset_id,
        "public_url": upload.public_url,
        "size_bytes": len(img_bytes),
        "clip_gate": gate_meta or None,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--persona-slug", default="cansu_dut")
    parser.add_argument("--group-id", default=CANSU_GROUP_ID)
    # Phase 42.C — tag newly synced photos with a composition_style
    # ("scene" for non-selfie, "selfie" for portrait). Pass when batching
    # a category from HeyGen. Existing photos are not re-tagged.
    parser.add_argument(
        "--default-composition-style",
        default=None,
        choices=[None, "scene", "selfie"],
        help="composition_style metadata tag for newly synced photos",
    )
    # Phase 42.C — bypass the CLIP similarity gate (development only).
    parser.add_argument(
        "--skip-clip-gate",
        action="store_true",
        help="bypass the CLIP similarity drift gate (dev only)",
    )
    args = parser.parse_args()

    if not settings.heygen_api_key:
        logger.error("HEYGEN_API_KEY missing")
        sys.exit(1)

    sb = make_supabase()
    storage = SupabaseStorage()

    # Resolve persona_id from slug
    res = sb.table("personas").select("id, slug, display_name").eq("slug", args.persona_slug).limit(1).execute()
    if not res.data:
        logger.error(f"persona '{args.persona_slug}' not found")
        sys.exit(1)
    persona = res.data[0]
    persona_id = persona["id"]
    logger.info(f"Persona: {persona['display_name']} ({persona_id[:8]})")

    # Fetch + sync
    generated = await fetch_generated_avatars(settings.heygen_api_key, args.group_id)
    if not generated:
        logger.warning("No generated avatars found in HeyGen group")
        return

    results: list[dict[str, Any]] = []
    for avatar in generated:
        try:
            r = await sync_one(
                sb=sb,
                storage=storage,
                persona_id=persona_id,
                avatar=avatar,
                default_composition_style=args.default_composition_style,
                skip_clip_gate=args.skip_clip_gate,
            )
            results.append(r)
            tag = r["status"].upper()
            row_status = r.get("row_status", "")
            gate = r.get("clip_gate") or {}
            extra = ""
            if row_status and row_status != "publish_ready":
                extra += f" status={row_status}"
            if gate and gate.get("score") is not None:
                extra += f" clip={gate['score']:.3f}({gate.get('verdict','?')})"
            logger.success(
                f"[{tag}] {r.get('name','?')[:40]:42} → {r.get('asset_id','-')[:12]}{extra}"
            )
        except Exception as e:
            logger.exception(f"Failed to sync {avatar.get('id','?')}: {e}")
            results.append({"heygen_id": avatar.get("id"), "status": "failed", "error": str(e)[:200]})

    # Summary
    counts: dict[str, int] = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    logger.info(f"=== SYNC SUMMARY ===")
    for k, v in counts.items():
        logger.info(f"  {k}: {v}")
    synced_count = counts.get("synced", 0)
    existing_count = counts.get("skipped_existing", 0)
    logger.success(
        f"Library now contains: {synced_count + existing_count} curated photos for {persona['display_name']}"
    )


if __name__ == "__main__":
    asyncio.run(main())

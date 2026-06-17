"""CLI: upload Cansu persona anchor photos to Supabase Storage + persona_assets.

Usage (from hype_crew/ root with venv activated):
    python -m scripts.upload_anchors \
        --persona-slug cansu_dut \
        --dir /Users/berkay/Desktop/cansudut \
        --metadata-file metadata.json     # optional, per-file tags

Per-file metadata example (metadata.json next to images, or single file with map):
    {
        "IMG_6617.jpg": {"pose": "front", "expression": "neutral", "setting": "office"},
        "IMG_6618.jpg": {"pose": "three_quarter", "expression": "smile", "setting": "home"},
        ...
    }

If no metadata.json is given, every photo gets the default tag set
(pose=front, expression=neutral, setting=unspecified).

Required consent metadata is always stamped:
    consent_confirmed=true
    real_person_reference=true
    do_not_publish=true
    private_reference_storage=true
    biometric_identity_verification=false
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

from loguru import logger
from PIL import Image

from config import settings
from tools.supabase_client import make_supabase
from tools.supabase_storage import SupabaseStorage

SUPPORTED_EXT_TO_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

DEFAULT_PHOTO_TAGS = {"pose": "front", "expression": "neutral", "setting": "unspecified"}


async def upload_one(
    *,
    storage: SupabaseStorage,
    persona_id: str,
    bucket: str,
    file_path: Path,
    photo_tags: dict[str, str],
) -> dict:
    """Upload single photo + INSERT persona_assets row."""
    raw = file_path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    ext = file_path.suffix.lower()
    mime = SUPPORTED_EXT_TO_MIME.get(ext)
    if mime is None:
        raise ValueError(f"unsupported extension {ext} for {file_path.name}")

    # Read dimensions
    with Image.open(file_path) as im:
        width, height = im.size
    if width < 512 or height < 512:
        raise ValueError(
            f"{file_path.name} too small: {width}x{height} (min 512×512)"
        )

    # Storage key — persona-scoped path
    storage_key = f"{persona_id}/{sha[:16]}{ext}"

    # Upload to Supabase Storage (private bucket)
    upload = await storage.upload_bytes(
        bucket=bucket,
        key=storage_key,
        data=raw,
        content_type=mime,
        upsert=True,  # idempotent reruns
    )

    # Compose metadata
    metadata = {
        **photo_tags,
        "consent_confirmed": True,
        "real_person_reference": True,
        "do_not_publish": True,
        "private_reference_storage": True,
        "biometric_identity_verification": False,
        "original_filename": file_path.name,
        "storage_bucket": bucket,
    }

    # Insert persona_assets row (idempotent via storage_key unique constraint)
    sb = make_supabase()
    insert_row = {
        "persona_id": persona_id,
        "asset_type": "reference_anchor",
        "status": "generated",
        "storage_bucket": bucket,
        "storage_key": storage_key,
        "public_url": None,  # private bucket
        "content_hash": sha,
        "mime_type": mime,
        "file_size_bytes": len(raw),
        "width": width,
        "height": height,
        "generation_metadata": metadata,
    }
    # Upsert-style: catch unique violation and update
    try:
        result = sb.table("persona_assets").insert(insert_row).execute()
        asset_row = result.data[0]
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg:
            update_row = {k: v for k, v in insert_row.items() if k not in ("persona_id",)}
            update_row["generation_metadata"] = metadata
            result = (
                sb.table("persona_assets")
                .update(update_row)
                .eq("storage_bucket", bucket)
                .eq("storage_key", storage_key)
                .execute()
            )
            asset_row = result.data[0]
        else:
            raise

    return {
        "id": asset_row["id"],
        "file": file_path.name,
        "size": f"{width}x{height}",
        "sha": sha[:12],
        "upload_ms": upload.latency_ms,
    }


async def main_async(args: argparse.Namespace) -> int:
    base_dir = Path(args.dir).expanduser().resolve()
    if not base_dir.is_dir():
        logger.error(f"--dir is not a directory: {base_dir}")
        return 2

    # Resolve persona_id from slug
    sb = make_supabase()
    persona_row = (
        sb.table("personas")
        .select("id, slug, display_name")
        .eq("slug", args.persona_slug)
        .limit(1)
        .execute()
    )
    if not persona_row.data:
        logger.error(f"No persona with slug={args.persona_slug}")
        return 3
    persona_id = persona_row.data[0]["id"]
    logger.info(f"persona resolved: {persona_row.data[0]['display_name']} ({persona_id})")

    # Optional metadata
    metadata_map: dict[str, dict[str, str]] = {}
    if args.metadata_file:
        meta_path = Path(args.metadata_file).expanduser().resolve()
        metadata_map = json.loads(meta_path.read_text())

    # Discover images
    files = sorted(
        p
        for p in base_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in SUPPORTED_EXT_TO_MIME
        and not p.name.startswith(".")
    )
    if not files:
        logger.error(f"No images found in {base_dir}")
        return 4

    logger.info(f"found {len(files)} candidate images in {base_dir}")

    bucket = args.bucket or settings.supabase_reference_bucket
    storage = SupabaseStorage()
    results = []
    failures = []
    for f in files:
        tags = metadata_map.get(f.name, DEFAULT_PHOTO_TAGS)
        try:
            r = await upload_one(
                storage=storage,
                persona_id=persona_id,
                bucket=bucket,
                file_path=f,
                photo_tags=tags,
            )
            results.append(r)
            logger.success(
                f"uploaded {r['file']} → {r['id'][:8]} ({r['size']}, {r['upload_ms']}ms)"
            )
        except Exception as e:
            logger.error(f"FAILED {f.name}: {e}")
            failures.append({"file": f.name, "error": str(e)})

    logger.info("=" * 60)
    logger.info(f"DONE — {len(results)} uploaded, {len(failures)} failed")
    if failures:
        logger.warning(json.dumps(failures, indent=2))
    return 0 if not failures else 5


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload persona anchor photos")
    parser.add_argument("--persona-slug", required=True, help="e.g. cansu_dut")
    parser.add_argument("--dir", required=True, help="directory containing photos")
    parser.add_argument("--metadata-file", help="optional JSON map of filename → tags")
    parser.add_argument(
        "--bucket",
        help="override default bucket (settings.supabase_reference_bucket)",
    )
    args = parser.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())

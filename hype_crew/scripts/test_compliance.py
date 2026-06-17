"""Run 4-layer compliance gate against the latest generated image.

Usage:
    venv/bin/python -m scripts.test_compliance
    venv/bin/python -m scripts.test_compliance --asset-id <uuid>
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time

import httpx
from loguru import logger

from tools.compliance.runner import run_compliance
from tools.supabase_client import make_supabase

PERSONA_ID = "653cea63-8105-478e-803c-24377038c39c"


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--asset-id", help="persona_assets.id; defaults to latest generated")
    parser.add_argument("--skip-llm", action="store_true", help="Skip L4 LLM judge")
    args = parser.parse_args()

    sb = make_supabase()
    if args.asset_id:
        q = sb.table("persona_assets").select("*").eq("id", args.asset_id).limit(1)
    else:
        q = (
            sb.table("persona_assets")
            .select("*")
            .eq("persona_id", PERSONA_ID)
            .eq("asset_type", "generated_image")
            .order("created_at", desc=True)
            .limit(1)
        )
    rows = q.execute()
    if not rows.data:
        logger.error("no asset found")
        return 1
    asset = rows.data[0]
    logger.info(f"asset: {asset['id']} url={asset['public_url']}")

    # Download
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        resp = await client.get(asset["public_url"])
    resp.raise_for_status()
    image_bytes = resp.content
    mime = asset["mime_type"] or "image/jpeg"
    logger.info(f"downloaded {len(image_bytes) / 1024:.1f} KB")

    t0 = time.perf_counter()
    report = await run_compliance(
        image_bytes=image_bytes,
        image_mime=mime,
        persona_id=PERSONA_ID,
        persona_asset_id=asset["id"],
        skip_llm=args.skip_llm,
    )
    elapsed = time.perf_counter() - t0

    logger.success("=" * 70)
    logger.success(f"FINAL VERDICT: {report.final_verdict}")
    logger.success(f"reason:        {report.final_reason}")
    logger.success(f"layers run:    {report.layers_run}")
    logger.success(f"total time:    {elapsed:.1f}s")
    logger.success("=" * 70)
    return 0 if report.final_verdict != "FAIL" else 2


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

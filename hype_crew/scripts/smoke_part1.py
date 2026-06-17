"""PART 1 smoke test:
1. Load Cansu's anchors from DB (5 rows expected)
2. Run readiness check (must be ready=True)
3. Build signed URLs (must return https URLs)
4. Existence check on Wiro client (no real call, just import + signature)
"""
from __future__ import annotations

import asyncio

from loguru import logger

from config import settings
from tools.reference_anchors import (
    load_persona_anchors,
    build_reference_anchor_readiness,
    prepare_reference_prompt_inputs,
)
from tools.supabase_storage import SupabaseStorage
from tools.wiro_client import WiroClient

PERSONA_ID = "653cea63-8105-478e-803c-24377038c39c"


async def main() -> int:
    logger.info("=== PART 1 SMOKE TEST ===")

    # 1. Load anchors
    anchors = await load_persona_anchors(PERSONA_ID)
    logger.info(f"loaded {len(anchors)} anchors")
    assert len(anchors) >= 3, f"need >=3, got {len(anchors)}"

    # 2. Readiness check
    readiness = build_reference_anchor_readiness(anchors)
    logger.info(f"readiness: ready={readiness.ready}, usable={readiness.usable_anchor_count}/{readiness.anchor_count}")
    if not readiness.ready:
        logger.error(f"BLOCKERS: {readiness.blockers}")
        return 1
    assert readiness.ready, "readiness failed"

    # 3. Prepare prompt inputs (signed URLs)
    inputs = await prepare_reference_prompt_inputs(
        anchors,
        scene_description="home office, MacBook open, natural daylight",
        outfit="cream knit sweater",
    )
    logger.info(f"signed URLs returned: {len(inputs.signed_reference_urls)}")
    for url in inputs.signed_reference_urls:
        assert url.startswith("https://"), f"bad signed URL: {url}"
        logger.info(f"  → {url[:80]}...")

    # 4. Wiro client smoke (no real call — just verify env + headers compile)
    client = WiroClient()
    logger.info(f"wiro client base: {client.base_url}")
    logger.info(f"wiro key set: {bool(client.api_key)}")
    logger.info(f"wiro secret set: {bool(client.api_secret)}")
    assert client.api_key, "WIRO_API_KEY missing"
    headers = client._headers()
    assert "x-api-key" in headers, "x-api-key not set"
    if client.api_secret:
        assert "x-signature" in headers, "x-signature missing"
        assert "x-nonce" in headers, "x-nonce missing"
    logger.info(f"headers ok: {list(headers.keys())}")

    logger.success("=== ALL SMOKE CHECKS PASSED ===")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))

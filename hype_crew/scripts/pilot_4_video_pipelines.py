"""PART 23.6 — Run all 4 video pipelines with the same script + anchor.

Side-by-side review experiment: take one Türkçe narration + one Cansu anchor →
produce 4 different videos (A/B/C/D) → store them in Supabase persona-videos →
print URLs for manual comparison.

Usage:
  cd hype_crew
  venv/bin/python -m scripts.pilot_4_video_pipelines \\
      --persona-slug cansu_dut \\
      --pipelines all          # or comma-list: talking_head_memo,hybrid_seedance_memo
      --script "Merhaba ben Cansu, bugün ..."

Results are written to /tmp/hype_pilot_results.json and logged.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

# Make this script runnable both as a module (-m scripts.pilot_...) and direct.
_THIS = Path(__file__).resolve()
_HYPE_CREW = _THIS.parent.parent
if str(_HYPE_CREW) not in sys.path:
    sys.path.insert(0, str(_HYPE_CREW))

from config import settings  # noqa: E402
from tools.reference_anchors import (  # noqa: E402
    load_persona_anchors, prepare_reference_prompt_inputs,
)
from tools.supabase_client import make_supabase  # noqa: E402
from tools.video_pipeline import (  # noqa: E402
    VideoBrief, PIPELINES, get_pipeline, StoredVideoAsset,
)


DEFAULT_SCRIPT_TR = (
    "Merhaba, ben Cansu. Bu hafta Hype Crew için video pipeline ekledik. "
    "Otonom sistem her saat bir trend buluyor, dört farklı platforma içerik üretiyor."
)


def _resolve_persona(slug: str) -> dict:
    sb = make_supabase()
    r = (
        sb.table("personas")
        .select("id, slug, display_name, video_enabled, video_pipeline_default")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )
    rows = r.data or []
    if not rows:
        raise RuntimeError(f"persona slug={slug} not found")
    return rows[0]


async def _get_anchor_url(persona_id: str) -> str:
    anchors = await load_persona_anchors(persona_id)
    if not anchors:
        raise RuntimeError(f"persona {persona_id} has no anchors uploaded")
    refs = await prepare_reference_prompt_inputs(anchors, max_prompt_inputs=1)
    if not refs.signed_reference_urls:
        raise RuntimeError("could not produce a signed anchor URL")
    return refs.signed_reference_urls[0]


async def _run_pipeline(
    pipeline_id: str, brief: VideoBrief
) -> tuple[str, Optional[StoredVideoAsset], Optional[str]]:
    """Run one pipeline; return (id, asset, error_or_None)."""
    try:
        pipeline = get_pipeline(pipeline_id)
    except ValueError as e:
        return pipeline_id, None, f"unknown pipeline: {e}"
    t0 = time.perf_counter()
    try:
        asset = await pipeline.produce_video(brief)
    except Exception as e:
        logger.exception(f"[pilot] pipeline={pipeline_id} FAILED: {e}")
        return pipeline_id, None, f"{type(e).__name__}: {e}"
    elapsed = time.perf_counter() - t0
    logger.success(
        f"[pilot] pipeline={pipeline_id} OK in {elapsed:.1f}s — "
        f"url={asset.video_url} cost=${asset.cost_usd:.3f}"
    )
    return pipeline_id, asset, None


async def main_async(args) -> dict:
    persona = _resolve_persona(args.persona_slug)
    logger.info(f"[pilot] persona={persona['slug']} id={persona['id']}")

    anchor_url = await _get_anchor_url(persona["id"])
    logger.info(f"[pilot] anchor URL acquired (signed, short-lived)")

    pipelines_to_run = (
        list(PIPELINES.keys()) if args.pipelines == "all" else
        [p.strip() for p in args.pipelines.split(",") if p.strip()]
    )
    logger.info(f"[pilot] running pipelines: {pipelines_to_run}")

    brief = VideoBrief(
        script_text=args.script,
        persona_id=persona["id"],
        anchor_image_url=anchor_url,
        action_prompt=args.action_prompt or None,
        target_aspect="9:16",
        target_duration=15,
    )

    results: list[dict] = []
    if args.parallel:
        # Run all in parallel — total runtime ≈ slowest pipeline
        tasks = [_run_pipeline(pid, brief) for pid in pipelines_to_run]
        done = await asyncio.gather(*tasks)
    else:
        # Sequential — easier to read logs + isolate failures
        done = []
        for pid in pipelines_to_run:
            done.append(await _run_pipeline(pid, brief))

    for pid, asset, err in done:
        if asset:
            results.append({
                "pipeline_id": pid,
                "status": "ok",
                "video_url": asset.video_url,
                "thumbnail_url": asset.thumbnail_url,
                "duration_sec": asset.duration_sec,
                "cost_usd": round(asset.cost_usd, 4),
                "elapsed_sec": round(asset.generation_latency_ms / 1000, 1),
                "file_size_mb": round(asset.file_size_bytes / 1_000_000, 2),
                "components": {
                    k: {ck: cv for ck, cv in (v or {}).items() if ck != "asset_url"}
                    for k, v in (asset.raw_components or {}).items()
                },
            })
        else:
            results.append({
                "pipeline_id": pid,
                "status": "failed",
                "error": err,
            })

    summary = {
        "persona_slug": persona["slug"],
        "persona_id": persona["id"],
        "ran_at_utc": datetime.now(timezone.utc).isoformat(),
        "script_text": args.script,
        "anchor_signed_url_first_chars": anchor_url[:80],
        "results": results,
        "total_cost_usd": round(sum(r.get("cost_usd", 0) for r in results), 4),
    }

    out_path = Path(args.output_file)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[pilot] summary written to {out_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 4 video pipelines side-by-side")
    parser.add_argument("--persona-slug", default="cansu_dut")
    parser.add_argument("--script", default=DEFAULT_SCRIPT_TR,
                        help="Türkçe narration text for TTS")
    parser.add_argument("--action-prompt", default="",
                        help="Optional action scene prompt for Seedance/Veo")
    parser.add_argument("--pipelines", default="all",
                        help="'all' or comma-list of pipeline ids")
    parser.add_argument("--parallel", action="store_true",
                        help="Run pipelines concurrently (faster, harder to debug)")
    parser.add_argument("--output-file", default="/tmp/hype_pilot_results.json")
    args = parser.parse_args()

    logger.info(f"[pilot] settings: dry_run={settings.dry_run} model_smart={settings.model_smart}")
    summary = asyncio.run(main_async(args))

    print("\n" + "=" * 70)
    print(f"PILOT SUMMARY — total cost ${summary['total_cost_usd']:.3f}")
    print("=" * 70)
    for r in summary["results"]:
        if r["status"] == "ok":
            print(f"  ✓ {r['pipeline_id']:<24}  ${r['cost_usd']:.3f}  "
                  f"{r['duration_sec']:.1f}s  {r['elapsed_sec']:.0f}s  "
                  f"{r['file_size_mb']:.1f}MB")
            print(f"      → {r['video_url']}")
        else:
            print(f"  ✗ {r['pipeline_id']:<24}  FAILED: {r['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

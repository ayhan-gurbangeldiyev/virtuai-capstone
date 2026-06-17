"""Standalone video test harness — careful, one-at-a-time.

Phase 1 (cheap): trend -> dedicated 3-act script (video_script_writer) ->
  pre_spend_guard length check (510-1000). Prints the script. NO render.
Phase 2 (RENDER=1): heygen_avatar_v produce_video -> download -> check_video_integrity
  (verifies the video is NOT cut off / truncated).

Usage:
  TREND_ID=.. python -m scripts.video_test            # script + guard only
  TREND_ID=.. RENDER=1 python -m scripts.video_test   # also render + integrity
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.supabase_client import make_supabase  # noqa: E402
from tools.video_script_writer import build_video_script_candidates, assemble_script  # noqa: E402
from tools.pre_spend_guard import assert_render_safe, PreSpendRejected  # noqa: E402

ACCOUNT_ID = os.environ.get("ACCOUNT_ID", "2b731bf7-8c24-40c5-8237-d348ee822d51")
TREND_ID = os.environ["TREND_ID"]


async def main() -> None:
    sb = make_supabase()
    persona = (sb.table("personas")
               .select("id, heygen_default_look_id")
               .eq("primary_account_id", ACCOUNT_ID).limit(1).execute()).data[0]
    pid = persona["id"]
    t = (sb.table("trends").select("topic, raw_content, full_source_text")
         .eq("id", TREND_ID).limit(1).execute()).data[0]
    topic = t.get("topic") or ""
    source = t.get("full_source_text") or t.get("raw_content") or ""
    print(f"trend: {topic}\nlook_id set: {bool(persona.get('heygen_default_look_id'))}\n")

    cand = await build_video_script_candidates(topic=topic, raw_content=source)
    if not cand:
        raise SystemExit("script writer returned no candidates")
    script = assemble_script(cand, pair_idx=0)
    print("=== 3-ACT SCRIPT ===")
    print(script)
    print(f"\nlen={len(script)} chars")
    try:
        n = assert_render_safe(script, draft_id="vtest")
        print(f"PRE_SPEND_GUARD: PASS ({n} chars in [510,1000])")
    except PreSpendRejected as e:
        print(f"PRE_SPEND_GUARD: REJECT — {e}")
        return

    if os.environ.get("RENDER") != "1":
        print("\n(dry run — set RENDER=1 to render + integrity-check)")
        return

    # Phase 2 — render + integrity
    from tools.video_pipeline import get_pipeline, VideoBrief
    from tools.video_integrity import check_video_integrity
    import httpx

    brief = VideoBrief(
        script_text=script, persona_id=pid, anchor_image_url="",
        target_aspect="9:16", daily_draft_id=None,
    )
    print("\n[render] heygen_avatar_v produce_video ...")
    asset = await get_pipeline("heygen_avatar_v").produce_video(brief)
    print(f"[render] video_url={asset.video_url}")
    print(f"[render] duration_sec={asset.duration_sec} cost=${getattr(asset,'cost_usd',0)}")

    out = Path(tempfile.mkdtemp()) / "vtest.mp4"
    async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as c:
        r = await c.get(asset.video_url)
    out.write_bytes(r.content)
    res = check_video_integrity(
        file_path=str(out), content_for_tts=script,
        tts_audio_duration_s=getattr(asset, "duration_sec", None),
    )
    print(f"\n=== INTEGRITY ===")
    print(f"ok={res.ok} reason={getattr(res,'reason',None)}")
    print(f"video_dur={getattr(res,'video_duration_s',None)} "
          f"expected={getattr(res,'expected_duration_s',None)}")
    print(f"LOCAL: {out}")


if __name__ == "__main__":
    asyncio.run(main())

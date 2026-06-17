"""Stage 2 Step 2 — durable trend-fetch entrypoint for the systemd timer.

Runs ONE fetch_batch_signals + the radar/monitor pipelines via
trend_engine.refresh_all(). Same code path the legacy crontab's
POST /api/trends/auto-refresh hits, but as a standalone process so it
survives across uvicorn deploys and reboots (Persistent=true).

Exit code 0 = the fetch attempt completed (even if some accounts
returned 0 tweets — that's a real-world signal, not a script failure).
Exit code 1 = the fetch raised (which the alerter will already have
emitted a CRITICAL line for). systemd's OnFailure= can hook here for
deeper escalation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Repo layout: backend/scripts/run_trend_fetch.py → backend/ at parent.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trend-fetch-timer")


def _sb():
    """Best-effort supabase client for trend_fetch_runs telemetry (cron yolu)."""
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_ANON_KEY", "")
        return create_client(url, key) if url and key else None
    except Exception:
        return None


async def main() -> int:
    t0 = time.perf_counter()
    # Faz 2 — cron yolu da trend_fetch_runs'a yazsın (eskiden sadece manuel
    # trigger yazıyordu → cron fetch'leri telemetride görünmüyordu).
    sb = _sb()
    run_id = None
    if sb is not None:
        try:
            ins = sb.table("trend_fetch_runs").insert(
                {"triggered_by": "cron", "status": "running"}
            ).execute()
            run_id = (ins.data or [{}])[0].get("id")
        except Exception as e:
            logger.warning(f"trend_fetch_runs insert (cron) failed: {e}")

    def _finish(status: str, result=None, error: str = None):
        if sb is None or run_id is None:
            return
        upd = {"status": status, "finished_at": datetime.now(timezone.utc).isoformat()}
        if isinstance(result, dict):
            if result.get("twitter_items") is not None:
                upd["twitter_items"] = result["twitter_items"]
            if result.get("trends_saved") is not None:
                upd["trends_saved"] = result["trends_saved"]
        if error:
            upd["error"] = error[:500]
        try:
            sb.table("trend_fetch_runs").update(upd).eq("id", run_id).execute()
        except Exception as e:
            logger.warning(f"trend_fetch_runs update (cron) failed: {e}")

    # Faz 4 — flag ON ise LangGraph kabuğu (checkpoint+resume), OFF ise eski yol birebir.
    use_lg = os.environ.get("TREND_INGEST_LANGGRAPH_ENABLED", "").lower() in ("1", "true", "yes", "on")
    try:
        if use_lg and run_id:
            from lg.ingest_graph import run_or_resume_ingest
            result = await run_or_resume_ingest(run_id, triggered_by="cron")
        else:
            from services.trend_engine import trend_engine
            result = await trend_engine.refresh_all()
    except Exception as e:
        logger.exception(f"trend fetch FAILED: {e!r}")
        _finish("failed", error=f"{type(e).__name__}: {e}")
        try:
            from services.alerter import alert_supply
            alert_supply(
                severity="CRITICAL",
                category="trend_fetch_timer::refresh_failed",
                summary=f"Scheduled trend fetch raised: {type(e).__name__}",
                evidence={"error": str(e)[:500]},
            )
        except Exception:
            pass
        return 1
    elapsed = time.perf_counter() - t0
    _finish("done", result=result)
    logger.info(
        f"trend fetch complete in {elapsed:.1f}s — "
        f"result_keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

"""asyncpg LISTEN/NOTIFY realtime listener.

Subscribes to Postgres channels and enqueues event-triggered meetings:
  - daily_draft_inserted → CBPO (review new pending draft)
  - run_failed           → CPO + CRO (diagnose failure)

Resilient: on connection loss, sleeps 30s and reconnects forever.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

import asyncpg
from loguru import logger

from .config import settings


def _payload(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


async def realtime_listener(queue: asyncio.PriorityQueue, stop: asyncio.Event) -> None:
    while not stop.is_set():
        conn = None
        try:
            conn = await asyncpg.connect(settings.supabase_db_url)
            logger.info("[listener] asyncpg connection opened")

            def on_draft(_conn, _pid, _channel, raw):
                event = {
                    "kind": "event_triggered",
                    "event": "draft_pending_review",
                    "payload": _payload(raw),
                    "attendees": ["CBPO"],
                }
                queue.put_nowait((2, datetime.now(timezone.utc).timestamp(), event))
                logger.info(f"[listener] daily_draft_inserted → enqueued CBPO event")

            def on_run_failed(_conn, _pid, _channel, raw):
                event = {
                    "kind": "event_triggered",
                    "event": "run_failed",
                    "payload": _payload(raw),
                    "attendees": ["CPO", "CRO"],
                }
                queue.put_nowait((1, datetime.now(timezone.utc).timestamp(), event))
                logger.info(f"[listener] run_failed → enqueued CPO+CRO event")

            await conn.add_listener("daily_draft_inserted", on_draft)
            await conn.add_listener("run_failed", on_run_failed)

            # Keep connection alive; asyncpg listener fires from background task.
            while not stop.is_set():
                if conn.is_closed():
                    raise RuntimeError("asyncpg connection closed")
                try:
                    await asyncio.wait_for(stop.wait(), timeout=60)
                    return
                except asyncio.TimeoutError:
                    pass
        except Exception as e:
            logger.warning(f"[listener] reconnect in 30s after error: {type(e).__name__}: {e}")
            try:
                if conn and not conn.is_closed():
                    await conn.close()
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=30)
                return
            except asyncio.TimeoutError:
                continue

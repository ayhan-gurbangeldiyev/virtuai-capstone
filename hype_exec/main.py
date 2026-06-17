"""Daemon entry point — `python -m hype_exec.main`.

Uses asyncio.TaskGroup (Python 3.11+) for structured concurrency:
  - scheduler.hourly_loop / daily_loop / weekly_loop
  - listener.realtime_listener
  - worker.event_worker (drains queue, invokes graph)
  - resume_worker (Phase 26.F — handles human approval resume)
  - health.health_server (uvicorn :8090)

SIGTERM/SIGINT → stop event set → all tasks exit cleanly within ~5s.
"""
from __future__ import annotations

import asyncio
import os
import signal
import sys

from loguru import logger

from .checkpointer import build_checkpointer, build_pool
from .config import settings
from .graph import build_graph
from .health import health_server, record_tick
from .listener import realtime_listener
from .scheduler import daily_loop, hourly_loop, weekly_loop
from .worker import event_worker


def _configure_logging() -> None:
    logger.remove()
    fmt = "{time:YYYY-MM-DD HH:mm:ss}|{level: <7}|{name}:{function}:{line}|{message}"
    logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO"), format=fmt)


async def _amain() -> None:
    _configure_logging()
    logger.info("hype-exec starting")
    logger.info(
        f"account={settings.account_id} model={settings.model_default} "
        f"pool={settings.pool_min}/{settings.pool_max} health_port={settings.health_port}"
    )

    if not settings.supabase_db_url:
        logger.error("SUPABASE_DB_URL is not set; refusing to start")
        sys.exit(2)

    pool = await build_pool()
    checkpointer = await build_checkpointer(pool)
    skeleton = os.environ.get("HYPE_EXEC_SKELETON", "false").lower() in ("1", "true", "yes")
    graph = build_graph(checkpointer, skeleton=skeleton)

    queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    # Record a startup tick so /health doesn't 503 immediately
    record_tick("startup")

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(hourly_loop(queue, stop), name="hourly_loop")
            tg.create_task(daily_loop(queue, stop), name="daily_loop")
            tg.create_task(weekly_loop(queue, stop), name="weekly_loop")
            tg.create_task(realtime_listener(queue, stop), name="realtime_listener")
            tg.create_task(event_worker(queue, graph, stop), name="event_worker")
            tg.create_task(_tick_recorder(stop), name="tick_recorder")
            tg.create_task(health_server(stop), name="health_server")
            # Phase 26.F worker (lazy import — file added in that phase)
            from .resume_worker import resume_worker
            tg.create_task(resume_worker(graph, stop), name="resume_worker")

            await stop.wait()
            logger.info("stop signal received; cancelling tasks")
            # Triggers CancelledError in all children; TaskGroup waits for them.
            raise asyncio.CancelledError
    except* asyncio.CancelledError:
        logger.info("hype-exec shutdown complete")
    finally:
        await pool.close()


async def _tick_recorder(stop: asyncio.Event) -> None:
    """Record a periodic 'hourly' tick so /health stays green even on idle days."""
    while not stop.is_set():
        record_tick("hourly")
        try:
            await asyncio.wait_for(stop.wait(), timeout=300)
            return
        except asyncio.TimeoutError:
            continue


if __name__ == "__main__":
    asyncio.run(_amain())

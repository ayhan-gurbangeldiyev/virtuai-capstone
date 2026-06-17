"""FastAPI /health + /metrics endpoint for systemd watchdog and observability."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, Response
from loguru import logger

from .config import settings

_last_tick: dict[str, datetime] = {}


def record_tick(kind: str) -> None:
    _last_tick[kind] = datetime.now(timezone.utc)


def get_ticks() -> dict[str, str]:
    return {k: v.isoformat() for k, v in _last_tick.items()}


app = FastAPI(title="hype-exec")


@app.get("/health")
async def health() -> Response:
    # Daemon is healthy if it ticked within the last 90 minutes for hourly
    # (gives one missed hour grace). On boot before first tick we return ok=true
    # but mark "warming".
    now = datetime.now(timezone.utc)
    last_hourly = _last_tick.get("hourly")
    if last_hourly is not None and (now - last_hourly).total_seconds() > 5400:
        return Response(status_code=503, content="stale_hourly_tick")
    return Response(status_code=200, content="ok")


@app.get("/metrics")
async def metrics() -> Response:
    try:
        from prometheus_client import generate_latest
        return Response(content=generate_latest(), media_type="text/plain; version=0.0.4")
    except Exception:
        return Response(status_code=503, content="prometheus_client_unavailable")


async def health_server(stop: asyncio.Event) -> None:
    """Run uvicorn on settings.health_port until stop is set."""
    config = uvicorn.Config(
        app, host="127.0.0.1", port=settings.health_port,
        log_level="warning", access_log=False, lifespan="on",
    )
    server = uvicorn.Server(config)
    logger.info(f"[health] listening on http://127.0.0.1:{settings.health_port}")
    serve_task = asyncio.create_task(server.serve())
    try:
        await stop.wait()
    finally:
        server.should_exit = True
        await serve_task

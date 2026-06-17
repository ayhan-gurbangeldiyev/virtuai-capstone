"""Time-based event source for the daemon.

Three loops:
  - hourly  → on the hour (CPO + CRO attend)
  - daily   → 09:00 TR = 06:00 UTC (all 5 attend)
  - weekly  → Monday 14:00 TR = 11:00 UTC (all 5 attend)

Each loop puts a meeting event onto the shared asyncio.PriorityQueue. The
event worker drains the queue and invokes the graph.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def _sleep_until(target: datetime, stop: asyncio.Event) -> None:
    """Sleep until target time, but wake on stop event."""
    while True:
        now = _now_utc()
        if now >= target:
            return
        delta = (target - now).total_seconds()
        try:
            await asyncio.wait_for(stop.wait(), timeout=min(delta, 60))
            return  # stop was set
        except asyncio.TimeoutError:
            continue


async def hourly_loop(queue: asyncio.PriorityQueue, stop: asyncio.Event) -> None:
    """Every hour on the hour. Priority=1 (higher number = lower priority)."""
    while not stop.is_set():
        now = _now_utc()
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await _sleep_until(next_hour, stop)
        if stop.is_set():
            return
        event = {"kind": "hourly_heartbeat", "attendees": ["CPO", "CRO"]}
        await queue.put((1, datetime.now(timezone.utc).timestamp(), event))
        logger.info("[sched] enqueued hourly_heartbeat")


async def daily_loop(queue: asyncio.PriorityQueue, stop: asyncio.Event) -> None:
    """09:00 TR = 06:00 UTC daily standup. Priority=0 (highest)."""
    while not stop.is_set():
        now = _now_utc()
        target = now.replace(hour=6, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)
        await _sleep_until(target, stop)
        if stop.is_set():
            return
        event = {"kind": "daily_standup", "attendees": ["CEO", "CPO", "CBPO", "CFO", "CRO"]}
        await queue.put((0, datetime.now(timezone.utc).timestamp(), event))
        logger.info("[sched] enqueued daily_standup")


async def weekly_loop(queue: asyncio.PriorityQueue, stop: asyncio.Event) -> None:
    """Monday 14:00 TR = 11:00 UTC weekly review. Priority=0 (highest)."""
    while not stop.is_set():
        now = _now_utc()
        # Days until next Monday (weekday 0 = Monday)
        days_ahead = (0 - now.weekday()) % 7
        target = (now + timedelta(days=days_ahead)).replace(hour=11, minute=0, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=7)
        await _sleep_until(target, stop)
        if stop.is_set():
            return
        event = {"kind": "weekly_review", "attendees": ["CEO", "CPO", "CBPO", "CFO", "CRO"]}
        await queue.put((0, datetime.now(timezone.utc).timestamp(), event))
        logger.info("[sched] enqueued weekly_review")

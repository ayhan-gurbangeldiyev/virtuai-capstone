"""Event worker — drains the meeting queue and invokes the graph.

Concurrency control: per-meeting-kind asyncio.Lock prevents two of the same
meeting type from running simultaneously (would race on LangGraph checkpoint
state under the same thread_id).
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from loguru import logger

from .config import settings
from .tools.hype_crew_reader import build_agenda
from .tools.meetings import start_meeting


_LOCKS: dict[str, asyncio.Lock] = {}


def _kind_lock(kind: str) -> asyncio.Lock:
    if kind not in _LOCKS:
        _LOCKS[kind] = asyncio.Lock()
    return _LOCKS[kind]


async def event_worker(queue: asyncio.PriorityQueue, graph, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            item = await asyncio.wait_for(queue.get(), timeout=5)
        except asyncio.TimeoutError:
            continue
        # PriorityQueue items are (priority, sequence, event)
        try:
            _priority, _seq, event = item
        except Exception:
            logger.warning(f"[worker] bad queue item: {item!r}")
            continue

        kind = event.get("kind", "unknown")
        attendees = event.get("attendees") or ["CEO", "CPO", "CBPO", "CFO", "CRO"]
        async with _kind_lock(kind):
            await _invoke_one(graph, kind=kind, attendees=attendees, event=event)


async def _invoke_one(graph, *, kind: str, attendees: list[str], event: dict) -> None:
    account_id = settings.account_id
    thread_id = f"{kind}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"

    # Build agenda from Hype Crew tables (event-triggered passes its own payload).
    if kind == "event_triggered":
        agenda = {"event": event.get("event"), "payload": event.get("payload")}
    else:
        agenda = build_agenda(account_id, kind=kind)

    meeting_id: str | None = None
    try:
        meeting_id = start_meeting(
            account_id=account_id, kind=kind, attendees=attendees,
            agenda=agenda, thread_id=thread_id,
        )
    except Exception as e:
        logger.exception(f"[worker] start_meeting failed: {e}")

    state_in = {
        "meeting_id": meeting_id,
        "thread_id": thread_id,
        "meeting_kind": kind,
        "account_id": account_id,
        "attendees": attendees,
        "agenda": agenda,
        "event": event if kind == "event_triggered" else None,
        "messages": [],
        "pending_decisions": [],
        "memos": [],
    }
    config = {"configurable": {"thread_id": thread_id, "recursion_limit": settings.recursion_limit}}

    try:
        final = await graph.ainvoke(state_in, config=config)
        logger.info(
            f"[worker] meeting={kind} done thread={thread_id} "
            f"executed={len(final.get('executed_decision_ids') or [])} "
            f"awaiting={len(final.get('awaiting_approval_ids') or [])}"
        )
    except Exception as e:
        logger.exception(f"[worker] graph.ainvoke failed for {kind}: {e}")

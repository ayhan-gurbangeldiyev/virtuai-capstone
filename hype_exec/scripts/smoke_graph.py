"""Phase 26.B smoke test — compile graph + invoke a dummy daily_standup.

Requires SUPABASE_DB_URL to be set (real Supabase Postgres connection so
AsyncPostgresSaver.setup() can create checkpoint tables).

Run:
    cd hype_exec
    .venv/bin/python -m scripts.smoke_graph
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from loguru import logger

from ..checkpointer import build_checkpointer, build_pool
from ..config import settings
from ..graph import build_graph
from ..tools.hype_crew_reader import build_agenda
from ..tools.meetings import start_meeting


async def main() -> None:
    skeleton = os.environ.get("HYPE_EXEC_SKELETON", "false").lower() in ("1", "true", "yes")
    kind = os.environ.get("HYPE_EXEC_SMOKE_KIND", "daily_standup")
    attendees_env = os.environ.get("HYPE_EXEC_SMOKE_ATTENDEES")
    attendees = [a.strip() for a in attendees_env.split(",")] if attendees_env else ["CEO", "CPO", "CBPO", "CFO", "CRO"]

    pool = await build_pool()
    try:
        checkpointer = await build_checkpointer(pool)
        graph = build_graph(checkpointer, skeleton=skeleton)

        thread_id = f"smoke-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        config = {"configurable": {"thread_id": thread_id, "recursion_limit": settings.recursion_limit}}

        # Build a real agenda + create a real executive_meetings row so FK
        # constraints on decisions/memos can be satisfied during commit.
        agenda = build_agenda(settings.account_id, kind=kind)
        agenda["smoke"] = True
        meeting_id = start_meeting(
            account_id=settings.account_id, kind=kind, attendees=attendees,
            agenda=agenda, thread_id=thread_id,
        )

        state_in = {
            "meeting_id": meeting_id,
            "thread_id": thread_id,
            "meeting_kind": kind,
            "account_id": settings.account_id,
            "attendees": attendees,
            "agenda": agenda,
            "messages": [],
            "pending_decisions": [],
            "memos": [],
        }

        logger.info(f"invoking graph thread={thread_id} meeting={meeting_id} skeleton={skeleton}")
        final = await graph.ainvoke(state_in, config=config)
        logger.info(f"final state keys: {sorted(final.keys())}")
        logger.info(f"decisions emitted: {len(final.get('pending_decisions') or [])}")
        for d in final.get("pending_decisions") or []:
            logger.info(f"  {d.get('role')} → {d.get('action_type')}: {(d.get('rationale') or '')[:160]}")
        logger.info(f"executed_decision_ids: {final.get('executed_decision_ids') or []}")
        logger.info(f"awaiting_approval_ids: {final.get('awaiting_approval_ids') or []}")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

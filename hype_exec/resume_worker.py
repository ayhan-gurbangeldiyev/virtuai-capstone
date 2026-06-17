"""Resume worker — polls executive_decisions for user-approved rows and
re-enters the graph via Command(resume=...).

Backend route `/api/exec/decisions/:id/approve` flips status from
'awaiting_approval' to 'approved_pending_resume' (or rejected variant).
This worker picks them up every 5 seconds and feeds the verdict back into
the paused LangGraph thread.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from loguru import logger

from .tools.supabase_client import make_supabase


async def resume_worker(graph, stop: asyncio.Event) -> None:
    sb = make_supabase()
    while not stop.is_set():
        try:
            rows = sb.table("executive_decisions").select(
                "id, checkpoint_ns, status"
            ).in_("status", ["approved_pending_resume", "rejected_pending_resume"])\
              .limit(10).execute()
            for r in (rows.data or []):
                await _resume_one(graph, sb, r)
        except Exception as e:
            logger.exception(f"[resume_worker] poll error: {e}")
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
            return
        except asyncio.TimeoutError:
            continue


async def _resume_one(graph, sb, row: dict) -> None:
    decision_id = row.get("id")
    status = row.get("status")
    thread_id = row.get("checkpoint_ns")
    if not thread_id:
        logger.warning(f"[resume_worker] decision {decision_id} has no checkpoint_ns; marking failed")
        sb.table("executive_decisions").update({
            "status": "failed", "error": "missing checkpoint_ns",
        }).eq("id", decision_id).execute()
        return

    verdict = "approve" if status == "approved_pending_resume" else "reject"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        from langgraph.types import Command
        logger.info(f"[resume_worker] resuming thread={thread_id} verdict={verdict} decision={decision_id}")
        await graph.ainvoke(Command(resume=verdict), config=config)
        # On success, human_approval_interrupt updated the row to 'executed' or 'rejected'.
    except Exception as e:
        logger.exception(f"[resume_worker] resume failed for {decision_id}: {e}")
        sb.table("executive_decisions").update({
            "status": "failed",
            "error": f"resume_failed: {type(e).__name__}: {e}",
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", decision_id).execute()

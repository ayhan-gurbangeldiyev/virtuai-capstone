"""Non-role graph nodes: supervisor, commit_decisions, human_approval interrupt."""
from __future__ import annotations

from typing import Literal

from loguru import logger

from .state import ExecState, RoleName

# Order in which the supervisor visits attendees. Same role can't be visited
# twice — supervisor walks attendees once, in this order, then routes to commit.
_ROLE_ORDER: tuple[RoleName, ...] = ("CEO", "CPO", "CBPO", "CFO", "CRO")


def _role_was_visited(state: ExecState, role: RoleName) -> bool:
    for d in state.get("pending_decisions") or []:
        if d.get("role") == role:
            return True
    for m in state.get("memos") or []:
        if m.get("role") == role:
            return True
    return False


async def supervisor_node(state: ExecState) -> dict:
    """No-op: routing happens in conditional edge `route_to_role`."""
    return {}


def route_to_role(state: ExecState) -> Literal["CEO", "CPO", "CBPO", "CFO", "CRO", "done"]:
    """Visit each attendee once in canonical order, then go to commit_decisions."""
    attendees = set(state.get("attendees") or [])
    for role in _ROLE_ORDER:
        if role in attendees and not _role_was_visited(state, role):
            return role
    return "done"


def route_after_role(state: ExecState) -> Literal["interrupt", "back"]:
    """If the most recent decision has a threshold_breach, pause for user approval."""
    decisions = state.get("pending_decisions") or []
    if not decisions:
        return "back"
    last = decisions[-1]
    if last.get("threshold_breach"):
        return "interrupt"
    return "back"


async def human_approval_interrupt(state: ExecState) -> dict:
    """Pause graph; wait for user approve/reject; apply or mark rejected.

    Lifecycle:
      1. Persist the breaching decision row as 'awaiting_approval'.
      2. Call interrupt() — LangGraph saves checkpoint, returns when
         graph.ainvoke is re-entered via Command(resume=...).
      3. Resume value is "approve" or "reject".
      4. If approve → call _execute_auto + DB status='executed'.
         If reject → DB status='rejected'.
      5. Annotate the decision in state with decision_id + final status so
         commit_decisions can skip it (already handled).
    """
    # Local imports to keep node module light.
    from datetime import datetime, timezone

    from langgraph.types import interrupt

    from .tools.action_executor import _execute_auto, enforce_threshold
    from .tools.hype_crew_reader import get_account_config
    from .tools.supabase_client import make_supabase

    decisions = state.get("pending_decisions") or []
    if not decisions:
        return {}
    last = decisions[-1]
    account_id = state.get("account_id") or ""
    meeting_id = state.get("meeting_id")
    thread_id = state.get("thread_id")

    sb = make_supabase()
    current_config = get_account_config(account_id) if account_id else {}
    breach = enforce_threshold(last, current_config=current_config)

    inserted = sb.table("executive_decisions").insert({
        "account_id": account_id,
        "meeting_id": meeting_id,
        "role_responsible": last.get("role"),
        "decision_type": last.get("action_type"),
        "decision_text": last.get("rationale") or "",
        "target_table": last.get("target_table"),
        "target_id": last.get("target_id"),
        "old_value": current_config if last.get("target_table") == "hype_account_config" else None,
        "new_value": last.get("new_value"),
        "triggered_by": _triggered_by(state.get("meeting_kind")),
        "threshold_breach": breach,
        "rationale_memo": last.get("rationale"),
        "checkpoint_ns": thread_id,
        "status": "awaiting_approval",
    }).execute()
    decision_row = (inserted.data or [{}])[0]
    decision_id = decision_row.get("id")
    logger.warning(
        f"[hitl] queued role={last.get('role')} action={last.get('action_type')} "
        f"decision_id={decision_id} breach={breach}"
    )

    # ── This call blocks the graph until resumed externally ──
    verdict = interrupt({
        "decision_id": decision_id,
        "role": last.get("role"),
        "action_type": last.get("action_type"),
        "rationale": last.get("rationale"),
        "threshold_breach": breach,
        "new_value": last.get("new_value"),
    })
    verdict_str = (verdict or "").lower() if isinstance(verdict, str) else "reject"
    logger.info(f"[hitl] resumed decision_id={decision_id} verdict={verdict_str}")

    now_iso = datetime.now(timezone.utc).isoformat()
    if verdict_str == "approve":
        try:
            _execute_auto(last, account_id)
            sb.table("executive_decisions").update({
                "status": "executed", "executed_at": now_iso,
            }).eq("id", decision_id).execute()
            final_status = "executed"
        except Exception as e:
            logger.exception(f"[hitl] approve execute failed: {e}")
            sb.table("executive_decisions").update({
                "status": "failed", "error": f"{type(e).__name__}: {e}",
            }).eq("id", decision_id).execute()
            final_status = "failed"
    else:
        sb.table("executive_decisions").update({
            "status": "rejected",
        }).eq("id", decision_id).execute()
        final_status = "rejected"

    # Annotate the decision with the resolution so commit_decisions can skip it.
    annotated = {**last, "decision_id": decision_id, "_hitl_status": final_status}
    return {"pending_decisions": [annotated]}


def _triggered_by(meeting_kind: str | None) -> str:
    return {
        "hourly_heartbeat": "schedule_heartbeat",
        "daily_standup": "schedule_standup",
        "weekly_review": "schedule_weekly",
        "event_triggered": "event_realtime",
    }.get(meeting_kind or "", "manual")


async def commit_decisions_node(state: ExecState) -> dict:
    """Persist decisions + memos to Supabase, finishing the meeting row."""
    # Local imports — Supabase client + executor are tightly coupled to env.
    from .tools.action_executor import persist_decision, persist_memo
    from .tools.hype_crew_reader import get_account_config
    from .tools.meetings import finish_meeting

    account_id = state.get("account_id") or ""
    meeting_id = state.get("meeting_id")
    meeting_kind = state.get("meeting_kind") or "unknown"
    thread_id = state.get("thread_id")
    triggered_by = {
        "hourly_heartbeat": "schedule_heartbeat",
        "daily_standup": "schedule_standup",
        "weekly_review": "schedule_weekly",
        "event_triggered": "event_realtime",
    }.get(meeting_kind, "manual")

    current_config = get_account_config(account_id) if account_id else {}

    decisions = state.get("pending_decisions") or []
    memos = state.get("memos") or []

    executed_ids: list[str] = []
    awaiting_ids: list[str] = []
    transcript_lines: list[str] = [f"# {meeting_kind} — {state.get('thread_id')}"]

    for d in decisions:
        # HITL-handled decisions already have a decision_id + _hitl_status set
        # by human_approval_interrupt; don't re-persist.
        if d.get("decision_id") and d.get("_hitl_status"):
            row_id = d["decision_id"]
            if d["_hitl_status"] == "executed":
                executed_ids.append(row_id)
            else:
                awaiting_ids.append(row_id)
            transcript_lines.append(
                f"- [{d['_hitl_status']}] {d.get('role')} {d.get('action_type')}: {d.get('rationale', '')[:200]}"
            )
            continue
        try:
            row = persist_decision(
                decision=d,
                account_id=account_id,
                meeting_id=meeting_id,
                triggered_by=triggered_by,
                checkpoint_ns=thread_id,
                current_config=current_config,
            )
            row_id = row.get("id")
            if row.get("status") == "awaiting_approval":
                awaiting_ids.append(row_id)
            else:
                executed_ids.append(row_id)
            transcript_lines.append(
                f"- [{row.get('status')}] {d.get('role')} {d.get('action_type')}: {d.get('rationale', '')[:200]}"
            )
        except Exception as e:
            logger.exception(f"persist_decision failed: {e}")
            transcript_lines.append(f"- [persist_error] {d.get('role')} {d.get('action_type')}: {e}")

    for m in memos:
        try:
            persist_memo(
                account_id=account_id,
                role=m.get("role") or "CEO",
                kind=m.get("kind") or "observation",
                content=m.get("content") or "",
                meeting_id=meeting_id,
            )
        except Exception as e:
            logger.exception(f"persist_memo failed: {e}")

    if meeting_id:
        try:
            finish_meeting(
                meeting_id=meeting_id,
                transcript="\n".join(transcript_lines),
                decisions_made_ids=executed_ids + awaiting_ids,
            )
        except Exception as e:
            logger.exception(f"finish_meeting failed: {e}")

    logger.info(
        f"[commit] meeting={meeting_kind} executed={len(executed_ids)} awaiting={len(awaiting_ids)}"
    )
    return {"executed_decision_ids": executed_ids, "awaiting_approval_ids": awaiting_ids}

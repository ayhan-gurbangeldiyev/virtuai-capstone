"""LLM-backed role node implementations (Phase 26.C).

Each role node:
  1. Loads its system prompt + Pydantic schema.
  2. Builds an input message with formatted agenda + most recent decisions
     from peer roles (so e.g. CRO can react to CFO's cost-cap call).
  3. Calls LLM via with_structured_output to get a typed decision.
  4. Falls back to noop if LLM fails (daemon must never crash a meeting).
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from ..prompts.roles import ROLE_PROMPTS
from ..prompts.shared import format_agenda
from ..state import Decision, ExecState, Memo, RoleName
from ..tools.llm_client import make_llm, make_llm_critical
from .schemas import ROLE_SCHEMA


def _format_peer_decisions(state: ExecState, self_role: RoleName) -> str:
    decisions = state.get("pending_decisions") or []
    peer = [d for d in decisions if d.get("role") != self_role]
    if not peer:
        return "(no peer decisions yet)"
    lines = []
    for d in peer[-5:]:  # last 5 max
        lines.append(
            f"- {d.get('role')}: {d.get('action_type')} — {d.get('rationale', '')[:160]}"
        )
    return "\n".join(lines)


async def _run_role(role: RoleName, state: ExecState, *, critical: bool = False) -> dict:
    schema = ROLE_SCHEMA[role]
    prompt = ROLE_PROMPTS[role]

    agenda_text = format_agenda(state.get("agenda"))
    peer_text = _format_peer_decisions(state, role)
    meeting_kind = state.get("meeting_kind", "unknown")

    user_msg = (
        f"## Meeting: {meeting_kind}\n\n"
        f"## Agenda\n{agenda_text}\n\n"
        f"## Peer decisions so far\n{peer_text}\n\n"
        "Decide ONE action (or noop) per the rules. "
        "Return ONLY the JSON object matching the schema."
    )

    try:
        llm_base = make_llm_critical() if critical else make_llm()
        llm = llm_base.with_structured_output(schema, method="json_schema")
        result = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content=user_msg),
        ])
    except Exception as e:
        logger.exception(f"{role} LLM call failed; emitting safety noop. error={e}")
        # Phase 28.J — audit LLM parse / API failure for observability
        try:
            from hype_exec.audit import log_audit
            log_audit(
                event_type="parse_failure",
                account_id=state.get("account_id"),
                meeting_id=state.get("meeting_id"),
                role=role,
                error_message=f"{type(e).__name__}: {str(e)[:300]}",
            )
            log_audit(
                event_type="noop_fallback",
                account_id=state.get("account_id"),
                meeting_id=state.get("meeting_id"),
                role=role,
                metadata={"reason": "parse_failure", "error_type": type(e).__name__},
            )
        except Exception:
            pass
        decision: Decision = {
            "role": role,
            "action_type": "noop",
            "rationale": f"[LLM failure → safe noop] {type(e).__name__}",
            "threshold_breach": None,
        }
        memo: Memo = {
            "role": role,
            "kind": "alert",
            "content": f"{role} LLM call failed: {type(e).__name__}. Noop emitted to preserve graph stability.",
        }
        return {"pending_decisions": [decision], "memos": [memo]}

    decision = {
        "role": role,
        "action_type": result.action_type,
        "rationale": result.rationale,
        "target_table": result.target_table,
        "target_id": result.target_id,
        "new_value": result.new_value,
        "threshold_breach": result.threshold_breach,
    }
    memo = {
        "role": role,
        "kind": "alert" if result.threshold_breach else "observation",
        "content": result.memo,
    }
    return {"pending_decisions": [decision], "memos": [memo]}


# Public node functions used by graph.py.
# CEO uses critical model on weekly_review only; CPO etc always default.
async def ceo_node(state: ExecState) -> dict:
    use_critical = state.get("meeting_kind") == "weekly_review"
    return await _run_role("CEO", state, critical=use_critical)


async def cpo_node(state: ExecState) -> dict:
    return await _run_role("CPO", state)


async def cbpo_node(state: ExecState) -> dict:
    return await _run_role("CBPO", state)


async def cfo_node(state: ExecState) -> dict:
    return await _run_role("CFO", state)


async def cro_node(state: ExecState) -> dict:
    return await _run_role("CRO", state)

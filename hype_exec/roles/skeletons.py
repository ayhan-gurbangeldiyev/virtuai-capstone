"""Skeleton role nodes — Phase 26.B. LLM-backed implementations in Phase 26.C.

Each role node receives ExecState and returns a partial update (dict).
In skeleton form, each role emits a "noop" Decision so the graph compiles and
end-to-end flow can be tested before LLM wiring.
"""
from __future__ import annotations

from loguru import logger

from ..state import Decision, ExecState, Memo, RoleName


def _noop(role: RoleName, state: ExecState) -> dict:
    kind = state.get("meeting_kind", "?")
    decision: Decision = {
        "role": role,
        "action_type": "noop",
        "rationale": f"[skeleton] {role} acknowledged {kind}; no action.",
        "threshold_breach": None,
    }
    memo: Memo = {
        "role": role,
        "kind": "observation",
        "content": f"[skeleton] {role} ran for {kind}.",
    }
    logger.debug(f"role={role} noop emitted for meeting={kind}")
    return {"pending_decisions": [decision], "memos": [memo]}


async def ceo_node(state: ExecState) -> dict:
    return _noop("CEO", state)


async def cpo_node(state: ExecState) -> dict:
    return _noop("CPO", state)


async def cbpo_node(state: ExecState) -> dict:
    return _noop("CBPO", state)


async def cfo_node(state: ExecState) -> dict:
    return _noop("CFO", state)


async def cro_node(state: ExecState) -> dict:
    return _noop("CRO", state)

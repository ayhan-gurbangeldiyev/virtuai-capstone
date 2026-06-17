"""LangGraph ExecState — TypedDict + custom reducers for the 24/7 daemon.

Critical for 7/24 daemon: AnyMessage list would grow unbounded without trimming,
leading to context bloat + OOM. trim_messages reducer caps at 30.
"""
from __future__ import annotations

from operator import add
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AnyMessage

RoleName = Literal["CEO", "CPO", "CBPO", "CFO", "CRO"]
MeetingKind = Literal["hourly_heartbeat", "daily_standup", "weekly_review", "event_triggered"]


def trim_messages(left: list, right: list) -> list:
    """Cap messages history at last 30 entries.

    Used as a reducer on ExecState.messages so the conversation log
    cannot grow unbounded across hourly meetings.
    """
    combined = (left or []) + (right or [])
    return combined[-30:]


class Decision(TypedDict, total=False):
    role: RoleName
    action_type: str                    # cost_cap_adjust | persona_lifecycle | strategy_pivot | ...
    target_table: str | None
    target_id: str | None
    old_value: dict | None
    new_value: dict | None
    rationale: str
    threshold_breach: dict | None       # {field, current, threshold} → triggers interrupt
    decision_id: str | None             # set by commit_decisions after DB insert


class Memo(TypedDict, total=False):
    role: RoleName
    kind: Literal["strategy", "observation", "dissent", "alert"]
    content: str


class ExecState(TypedDict, total=False):
    # Identity
    meeting_id: str
    thread_id: str
    meeting_kind: MeetingKind
    account_id: str

    # Inputs
    attendees: list[RoleName]
    agenda: dict
    event: dict | None                  # for event_triggered meetings

    # Working memory
    messages: Annotated[list[AnyMessage], trim_messages]
    pending_decisions: Annotated[list[Decision], add]
    memos: Annotated[list[Memo], add]

    # Outputs (set by commit_decisions node)
    executed_decision_ids: list[str]
    awaiting_approval_ids: list[str]

"""executive_meetings row lifecycle helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from .supabase_client import make_supabase


def start_meeting(
    *, account_id: str, kind: str, attendees: list[str], agenda: dict[str, Any], thread_id: str | None
) -> str:
    sb = make_supabase()
    row = sb.table("executive_meetings").insert({
        "account_id": account_id,
        "kind": kind,
        "attendees": attendees,
        "agenda": agenda,
        "thread_id": thread_id,
    }).execute()
    meeting_id = (row.data or [{}])[0].get("id")
    logger.info(f"[meeting] started {kind} meeting_id={meeting_id} attendees={attendees}")
    return meeting_id


def finish_meeting(
    *, meeting_id: str, transcript: str | None, decisions_made_ids: list[str],
    total_tokens: int = 0, total_cost_usd: float = 0,
) -> None:
    if not meeting_id:
        return
    sb = make_supabase()
    sb.table("executive_meetings").update({
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "transcript": (transcript or "")[:20000],
        "decisions_made_ids": decisions_made_ids,
        "total_tokens": int(total_tokens),
        "total_cost_usd": round(float(total_cost_usd), 4),
    }).eq("id", meeting_id).execute()

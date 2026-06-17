"""Phase 28.J — Best-effort audit logging for the Executive C-Suite daemon.

Every silently-coerced field, dropped key, parse failure, or DB insert
error gets one row in `executive_audit_log`. NEVER raises; if the audit
write itself fails (network / DB blip), the caller flow continues.

Used by:
- roles/schemas.py Pydantic field_validators (L1)
- tools/action_executor.py _sanitize_new_value (L4)
- roles/llm_nodes.py LLM parse failure handlers (L5)
- nodes.py human_approval_interrupt INSERT exceptions (defensive)
"""
from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


_VALID_EVENTS = {
    "schema_coerce",
    "schema_drop_field",
    "parse_failure",
    "insert_fail",
    "key_whitelist_drop",
    "value_coerce",
    "revert",
    "noop_fallback",
}


def log_audit(
    *,
    event_type: str,
    account_id: Optional[str] = None,
    meeting_id: Optional[str] = None,
    role: Optional[str] = None,
    decision_type: Optional[str] = None,
    field_name: Optional[str] = None,
    original_value: Optional[Any] = None,
    coerced_value: Optional[Any] = None,
    error_message: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert one audit row. Best-effort — exceptions are swallowed.

    `original_value` and `coerced_value` are coerced to short strings
    (max ~500 chars) to keep rows small.
    """
    if event_type not in _VALID_EVENTS:
        logger.warning(f"[audit] unknown event_type={event_type!r}; logging anyway")

    def _stringify(v: Any) -> Optional[str]:
        if v is None:
            return None
        try:
            s = v if isinstance(v, str) else repr(v)
        except Exception:
            s = f"<{type(v).__name__}>"
        return s[:500]

    payload = {
        "event_type": event_type,
        "account_id": account_id,
        "meeting_id": meeting_id,
        "role": role,
        "decision_type": decision_type,
        "field_name": field_name,
        "original_value": _stringify(original_value),
        "coerced_value": _stringify(coerced_value),
        "error_message": (error_message or "")[:500] or None,
        "metadata": metadata or {},
    }

    try:
        # Lazy import to avoid circular deps at module load.
        from hype_exec.tools.supabase_client import make_supabase  # type: ignore
        sb = make_supabase()
        sb.table("executive_audit_log").insert(payload).execute()
    except Exception as exc:
        # Never let audit failures break the daemon. Log + drop.
        logger.warning(
            f"[audit] failed to persist event={event_type} field={field_name}: {exc!s}"
        )

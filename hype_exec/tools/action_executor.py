"""Action executor — applies executive decisions to Supabase.

Threshold guard logic mirrors the prompt-side guide so the daemon never
auto-executes an action that should require user approval, even if the LLM
forgets to set `threshold_breach`.

Routing:
  - threshold_breach present → insert as 'awaiting_approval', return decision_id
  - otherwise → apply diff, insert as 'auto_executed', return decision_id

Routing failures (DB error, unknown action_type) → insert as 'failed' with
error message; never raise out of executor (daemon must not crash on a bad
decision).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger

from .supabase_client import make_supabase


# ─────────────────────────────────────────────────────────────────────────
# Phase 28.J — L4 defense: per-table key whitelist + type coerce
# ─────────────────────────────────────────────────────────────────────────
# Anything the LLM puts in `new_value` that isn't in this spec gets dropped
# (with audit log). Values are coerced to the expected type; numeric values
# get clamped to (lo, hi) when defined.

# Spec format: { table_name: { key: (type, lo_or_None, hi_or_None) } }
TABLE_KEY_SPECS: dict[str, dict[str, tuple[type, float | None, float | None]]] = {
    "hype_account_config": {
        "daily_cost_cap_usd": (float, 0.0, 10.0),
        "auto_publish_enabled": (bool, None, None),
        "dry_run_mode": (bool, None, None),
        "executive_freeze": (bool, None, None),
        "cro_auto_freeze_on_violation": (bool, None, None),
        "daily_post_quota": (int, 0, 20),
    },
    "daily_drafts": {
        # only 'status' accepted, and only with a fixed allowed value below
        "status": (str, None, None),
    },
    "personas": {
        "video_enabled": (bool, None, None),
        "visual_enabled": (bool, None, None),
        "is_active": (bool, None, None),
    },
}

# Allowed string-value enums per (table, key)
_VALUE_ENUMS: dict[tuple[str, str], set[str]] = {
    ("daily_drafts", "status"): {"auto_rejected", "edited"},
}


def _audit_safe(**kwargs) -> None:
    try:
        from hype_exec.audit import log_audit
        log_audit(**kwargs)
    except Exception:
        pass


def _coerce_value(target_type: type, v: Any) -> Any:
    """Best-effort coerce. bool needs special handling (bool('0') is True)."""
    if target_type is bool:
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return bool(v)
        if isinstance(v, str):
            s = v.strip().lower()
            if s in ("true", "1", "yes", "on", "evet"):
                return True
            if s in ("false", "0", "no", "off", "hayır", "hayir"):
                return False
            raise ValueError(f"can't coerce {v!r} to bool")
        raise ValueError(f"can't coerce {type(v).__name__} to bool")
    return target_type(v)


def sanitize_new_value(target_table: str | None, raw: dict | None) -> dict:
    """Per-table key whitelist + type coerce + range clamp + enum check.

    Returns a CLEAN dict containing only valid keys with coerced values.
    Drops unknown keys, invalid types, out-of-range values, and invalid enums
    — audit-logs each event.

    Safe to call with None target_table / None raw → returns {}.
    """
    if not raw or not isinstance(raw, dict):
        return {}
    if not target_table or target_table not in TABLE_KEY_SPECS:
        # Unknown target table — drop everything and audit.
        for k, v in raw.items():
            _audit_safe(
                event_type="key_whitelist_drop",
                field_name=k,
                original_value=v,
                error_message=f"target_table {target_table!r} not in spec; all keys dropped",
            )
        return {}

    spec = TABLE_KEY_SPECS[target_table]
    clean: dict[str, Any] = {}
    for k, v in raw.items():
        if k not in spec:
            _audit_safe(
                event_type="key_whitelist_drop",
                field_name=k,
                original_value=v,
                error_message=f"key not allowed for table {target_table!r}",
            )
            continue
        target_type, lo, hi = spec[k]
        try:
            coerced = v if isinstance(v, target_type) else _coerce_value(target_type, v)
        except (ValueError, TypeError) as e:
            _audit_safe(
                event_type="key_whitelist_drop",
                field_name=k,
                original_value=v,
                error_message=f"type coerce failed ({target_type.__name__}): {e}",
            )
            continue

        # range clamp for numerics
        if lo is not None and isinstance(coerced, (int, float)) and coerced < lo:
            _audit_safe(
                event_type="value_coerce",
                field_name=k,
                original_value=coerced,
                coerced_value=lo,
                error_message=f"below lower bound {lo}; clamped",
            )
            coerced = type(coerced)(lo) if isinstance(coerced, int) else lo
        if hi is not None and isinstance(coerced, (int, float)) and coerced > hi:
            _audit_safe(
                event_type="value_coerce",
                field_name=k,
                original_value=coerced,
                coerced_value=hi,
                error_message=f"above upper bound {hi}; clamped",
            )
            coerced = type(coerced)(hi) if isinstance(coerced, int) else hi

        # enum check
        enum_set = _VALUE_ENUMS.get((target_table, k))
        if enum_set is not None and coerced not in enum_set:
            _audit_safe(
                event_type="key_whitelist_drop",
                field_name=k,
                original_value=v,
                error_message=f"value {coerced!r} not in enum {sorted(enum_set)}",
            )
            continue

        if coerced != v:
            _audit_safe(
                event_type="value_coerce",
                field_name=k,
                original_value=v,
                coerced_value=coerced,
                error_message=f"type coerced {type(v).__name__} → {target_type.__name__}",
            )
        clean[k] = coerced
    return clean


# ----- threshold guard -----------------------------------------------------

# Server-side guard: regardless of what the LLM said, these actions are always
# threshold-breach (force interrupt).
ALWAYS_THRESHOLD = {
    "persona_create",
    "persona_retire",
    "model_swap",
    "weekly_review_directive",        # CEO weekly directives need owner buy-in
    "forbidden_topic_remove",
    "compliance_halt",
    # CRO compliance_halt is auto IF cro_auto_freeze_on_violation flag is on;
    # but we still mark it threshold so the user sees it in the queue.
    # Phase 28 incident: CEO auto-toggled executive_freeze during a smoke
    # daily_standup and blocked the entire pipeline for 5 hours. Kill-switch
    # toggles must ALWAYS require human approval — there's no autonomy upside
    # to the system pausing itself silently.
    "executive_freeze_toggle",
    "cro_auto_freeze_toggle",
    "pipeline_freeze",
    "pipeline_unfreeze",
}

# Cost-cap threshold: auto if new value ≤ 5.00 AND delta within ±20% of old.
_COST_CAP_CEILING = 5.00
_COST_CAP_DELTA_MAX = 0.20


def _validate_cost_cap(old_value: dict | None, new_value: dict | None) -> dict | None:
    if not new_value or "daily_cost_cap_usd" not in new_value:
        return None
    new_cap = float(new_value.get("daily_cost_cap_usd") or 0)
    old_cap = float((old_value or {}).get("daily_cost_cap_usd") or 0)
    if new_cap > _COST_CAP_CEILING:
        return {"field": "daily_cost_cap_usd", "current": new_cap, "threshold": _COST_CAP_CEILING}
    if old_cap > 0:
        delta = abs(new_cap - old_cap) / old_cap
        if delta > _COST_CAP_DELTA_MAX:
            return {"field": "daily_cost_cap_usd_delta", "current": round(delta, 3), "threshold": _COST_CAP_DELTA_MAX}
    return None


def enforce_threshold(decision: dict[str, Any], *, current_config: dict[str, Any] | None = None) -> dict | None:
    """Server-side check that overrides LLM. Returns threshold_breach dict or None."""
    if decision.get("threshold_breach"):
        return decision["threshold_breach"]  # respect LLM
    action_type = decision.get("action_type")
    if action_type in ALWAYS_THRESHOLD:
        return {"field": "action_type", "current": action_type, "threshold": "always_review"}
    if action_type == "cost_cap_adjust":
        return _validate_cost_cap(current_config or {}, decision.get("new_value") or {})
    return None


# ----- DB writes (auto-executed actions) -----------------------------------

def _apply_config_diff(account_id: str, new_value: dict) -> None:
    """Apply key→value diff to hype_account_config row. Phase 28.J: sanitize
    via TABLE_KEY_SPECS before write. Unknown/invalid keys silently dropped."""
    sb = make_supabase()
    clean = sanitize_new_value("hype_account_config", new_value)
    if not clean:
        logger.warning(
            f"[exec] _apply_config_diff: sanitized new_value is empty "
            f"(raw={new_value!r}); skipping update"
        )
        return
    payload = {**clean, "updated_at": datetime.now(timezone.utc).isoformat()}
    sb.table("hype_account_config").update(payload).eq("account_id", account_id).execute()


def _apply_post_takedown(target_id: str) -> None:
    sb = make_supabase()
    sb.table("daily_drafts").update({"status": "auto_rejected"}).eq("id", target_id).execute()


def _apply_persona_update(target_id: str, new_value: dict) -> None:
    """Phase 28.J: persona table updates (video_enabled, is_active, etc)."""
    sb = make_supabase()
    clean = sanitize_new_value("personas", new_value)
    if not clean:
        logger.warning(f"[exec] _apply_persona_update: sanitized new_value empty; skipping")
        return
    sb.table("personas").update(clean).eq("id", target_id).execute()


# Action dispatch table for auto-executed decisions.
_AUTO_DISPATCH = {
    # action_type → (target_table, applier)
    "cost_cap_adjust": ("hype_account_config", _apply_config_diff),
    "content_type_weight_adjust": ("hype_account_config", _apply_config_diff),
    "visual_mode_distribution_adjust": ("hype_account_config", _apply_config_diff),
    "scene_rotation_update": ("hype_account_config", _apply_config_diff),
    "executive_freeze_toggle": ("hype_account_config", _apply_config_diff),
    "cro_auto_freeze_toggle": ("hype_account_config", _apply_config_diff),
    "cadence_adjust": ("hype_account_config", _apply_config_diff),
    "retry_policy_change": ("hype_account_config", _apply_config_diff),
    "forbidden_topic_add": ("hype_account_config", _apply_config_diff),
    "pipeline_freeze": ("hype_account_config", _apply_config_diff),
    "pipeline_unfreeze": ("hype_account_config", _apply_config_diff),
    "post_takedown": ("daily_drafts", lambda account_id, _new: None),   # uses target_id below
}


def _execute_auto(decision: dict, account_id: str) -> None:
    action_type = decision.get("action_type")
    if action_type in ("noop", "observation", "strategy_observation", "cost_alert", "voice_drift_alert", "model_downgrade_recommend"):
        return  # nothing to apply; memo + decision row are the artifact
    if action_type == "post_takedown":
        target_id = decision.get("target_id")
        if not target_id:
            raise ValueError("post_takedown without target_id")
        _apply_post_takedown(target_id)
        return
    entry = _AUTO_DISPATCH.get(action_type)
    if not entry:
        raise ValueError(f"unknown auto action_type: {action_type}")
    _, applier = entry
    new_value = decision.get("new_value") or {}
    if not new_value:
        raise ValueError(f"{action_type} requires non-empty new_value")
    applier(account_id, new_value)


# ----- public API ----------------------------------------------------------

def persist_decision(
    *,
    decision: dict[str, Any],
    account_id: str,
    meeting_id: str | None,
    triggered_by: str,
    checkpoint_ns: str | None,
    current_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert decision row + optionally apply changes. Returns inserted row.

    Idempotency: caller passes a deterministic-enough meeting_id; this function
    does not dedupe (LangGraph checkpointer protects against re-runs of the
    same node within a thread). If you replay an old thread you may get a
    second row — acceptable for audit log purposes.
    """
    sb = make_supabase()
    breach = enforce_threshold(decision, current_config=current_config)
    role = decision.get("role")
    base_row = {
        "account_id": account_id,
        "meeting_id": meeting_id,
        "role_responsible": role,
        "decision_type": decision.get("action_type"),
        "decision_text": decision.get("rationale") or decision.get("action_type") or "",
        "target_table": decision.get("target_table"),
        "target_id": decision.get("target_id"),
        "old_value": current_config if decision.get("target_table") == "hype_account_config" else None,
        "new_value": decision.get("new_value"),
        "triggered_by": triggered_by,
        "threshold_breach": breach,
        "rationale_memo": decision.get("rationale"),
        "checkpoint_ns": checkpoint_ns,
    }

    if breach:
        base_row["status"] = "awaiting_approval"
        inserted = sb.table("executive_decisions").insert(base_row).execute()
        logger.info(
            f"[exec] decision queued for approval role={role} action={decision.get('action_type')} "
            f"breach={breach}"
        )
        return (inserted.data or [{}])[0]

    # auto-execute path
    try:
        _execute_auto(decision, account_id)
        base_row["status"] = "auto_executed"
        base_row["executed_at"] = datetime.now(timezone.utc).isoformat()
        inserted = sb.table("executive_decisions").insert(base_row).execute()
        logger.info(f"[exec] auto-executed role={role} action={decision.get('action_type')}")
        return (inserted.data or [{}])[0]
    except Exception as e:
        logger.exception(f"[exec] auto-execute failed: {e}")
        base_row["status"] = "failed"
        base_row["error"] = f"{type(e).__name__}: {e}"
        inserted = sb.table("executive_decisions").insert(base_row).execute()
        return (inserted.data or [{}])[0]


def persist_memo(*, account_id: str, role: str, kind: str, content: str, meeting_id: str | None) -> None:
    sb = make_supabase()
    sb.table("executive_memos").insert({
        "account_id": account_id,
        "author_role": role,
        "kind": kind,
        "content": content[:8000],
        "meeting_id": meeting_id,
    }).execute()


def revert_decision(decision_id: str) -> dict[str, Any]:
    """Undo an auto-executed (or user-executed) decision by re-applying its
    old_value. Phase 28.J — extended to support daily_drafts (post takedown
    undo) and personas (enable/disable toggle undo) in addition to the
    existing hype_account_config path.

    Behaviour:
      hype_account_config → re-apply old config keys
      daily_drafts (post_takedown)  → flip status back from auto_rejected to
                                       prior status (default pending_review)
      personas (is_active / enable flags) → re-apply old persona keys
      anything else → raises ValueError (UI will show error)
    """
    sb = make_supabase()
    row = sb.table("executive_decisions").select("*").eq("id", decision_id).single().execute()
    d = row.data or {}
    if d.get("status") not in ("auto_executed", "executed"):
        raise ValueError(f"only auto_executed/executed decisions are revertible (got {d.get('status')})")

    target_table = d.get("target_table")
    target_id = d.get("target_id")
    old = d.get("old_value") or {}
    decision_type = d.get("decision_type")
    account_id = d.get("account_id")

    if target_table == "hype_account_config":
        if not old:
            raise ValueError("hype_account_config revert needs old_value")
        _apply_config_diff(account_id, old)

    elif target_table == "daily_drafts":
        if not target_id:
            raise ValueError("daily_drafts revert needs target_id")
        # post_takedown set status=auto_rejected; revert to old status (or pending_review).
        prior_status = (old or {}).get("status") if isinstance(old, dict) else None
        prior_status = prior_status or "pending_review"
        sb.table("daily_drafts").update({"status": prior_status}).eq("id", target_id).execute()
        _audit_safe(
            event_type="revert",
            account_id=account_id,
            decision_type=decision_type,
            field_name="status",
            original_value="auto_rejected",
            coerced_value=prior_status,
            metadata={"draft_id": target_id},
        )

    elif target_table == "personas":
        if not target_id:
            raise ValueError("personas revert needs target_id")
        if decision_type == "persona_retire":
            # retire set is_active=false → revert by re-enabling
            sb.table("personas").update({"is_active": True}).eq("id", target_id).execute()
        elif old and isinstance(old, dict):
            # generic enable/disable toggle revert
            clean = sanitize_new_value("personas", old)
            if clean:
                sb.table("personas").update(clean).eq("id", target_id).execute()
            else:
                raise ValueError("personas revert: old_value did not sanitize to any valid keys")
        else:
            raise ValueError(f"persona revert not supported for decision_type={decision_type}")
        _audit_safe(
            event_type="revert",
            account_id=account_id,
            decision_type=decision_type,
            metadata={"persona_id": target_id},
        )

    else:
        raise ValueError(f"revert not implemented for target_table={target_table}")

    sb.table("executive_decisions").update({
        "status": "reverted",
        "reverted_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", decision_id).execute()
    return {"status": "reverted", "decision_id": decision_id, "table": target_table}

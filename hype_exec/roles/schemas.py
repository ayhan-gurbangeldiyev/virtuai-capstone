"""Pydantic decision schemas — one per executive role.

Each schema is passed to LLM via `with_structured_output(method="json_schema")`
so the model is constrained to return parseable JSON. Validation is enforced
by Pydantic; on parse failure LangChain retries (max_retries=2 on the LLM).

Phase 28.J — 4 field_validators (mode=before) added to silently coerce
non-conforming LLM outputs to safe defaults rather than crash:
- target_id: any non-UUID string → None (with audit log)
- target_table: any string not in allow-list → None
- new_value: anything not a dict → None
- threshold_breach: anything not a dict → None; missing impact key filled
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

ThresholdBreach = dict  # {"field": "...", "current": <num>, "threshold": <num>, "impact": "..."}


# Allowed target_table values across all roles. Anything else is reset to None
# (and audit-logged). Kept in sync with TABLE_KEY_SPECS in action_executor.
_ALLOWED_TARGET_TABLES = {
    "hype_account_config",
    "daily_drafts",
    "personas",
    "trends",
    "connected_accounts",
    "hype_memory",
}


def _audit_safe(**kwargs) -> None:
    """Lazy-import audit to avoid circular load at module init."""
    try:
        from hype_exec.audit import log_audit
        log_audit(**kwargs)
    except Exception:
        # Audit failures must never bubble up from a Pydantic validator.
        pass


class _BaseDecision(BaseModel):
    """Common shape for all role outputs."""

    action_type: str = Field(
        ...,
        description="machine-readable action verb (English enum) e.g. cost_cap_adjust, persona_freeze, noop",
    )
    rationale: str = Field(
        ...,
        description="Türkçe — 1-3 cümle, gündemde geçen sayılara atıf yap. Düz konuşma diliyle yaz.",
    )
    target_table: str | None = Field(
        None,
        description=(
            "Etkilenen tablo adı (Phase 28.J — allow-list zorunlu). "
            "Sadece şunlar: 'hype_account_config' (workspace config), "
            "'daily_drafts' (single post takedown), 'personas' (persona ops), "
            "'trends', 'connected_accounts', 'hype_memory'. "
            "Liste dışı değer otomatik None'a çekilir."
        ),
    )
    target_id: str | None = Field(
        None,
        description=(
            "Etkilenen row'un UUID'si (account_id, draft_id, persona_id). "
            "ZORUNLU UUID FORMATI veya null. Persona slug ('cansu_dut'), "
            "config ismi ('hype_crew_pipeline'), env var ismi ('HYPE_MODEL_SMART') "
            "geçersizdir; UUID bilmiyorsan null bırak — sistem account_id "
            "fallback kullanır."
        ),
    )
    new_value: dict | None = Field(
        None,
        description=(
            "Uygulanacak key→value diff. Anahtar şeması:\n"
            "- hype_account_config için: {daily_cost_cap_usd: float 0-10}, "
            "{auto_publish_enabled: bool}, {executive_freeze: bool}, "
            "{dry_run_mode: bool}, {cro_auto_freeze_on_violation: bool}, "
            "{daily_post_quota: int 0-20}\n"
            "- daily_drafts için: {status: 'auto_rejected'}\n"
            "- personas için: {video_enabled: bool}, {visual_enabled: bool}\n"
            "Bilmediğin key'leri ekleme — action_executor onları drop eder."
        ),
    )
    threshold_breach: ThresholdBreach | None = Field(
        None,
        description=(
            "{'field': '<env_var>', 'current': <num>, 'threshold': <num>, "
            "'impact': '<Türkçe açıklama: bu karar onaylanırsa ne olur>'}. "
            "Dolduğunda kullanıcı onayı tetiklenir."
        ),
    )
    memo: str = Field(
        ...,
        description="Türkçe — toplantı transkripti için 1-3 cümlelik not. Sade ve insanca.",
    )

    # ─────────────────────────────────────────────────────────────────────
    # Phase 28.J — defensive validators (mode=before so LLM raw output is
    # coerced BEFORE Pydantic type narrowing complains).
    # ─────────────────────────────────────────────────────────────────────

    @field_validator("target_id", mode="before")
    @classmethod
    def _coerce_target_id_to_uuid_or_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        try:
            return str(UUID(str(v)))  # validates and canonicalises
        except (ValueError, TypeError):
            _audit_safe(
                event_type="schema_coerce",
                field_name="target_id",
                original_value=v,
                coerced_value=None,
                error_message="non-UUID value (likely persona slug or config name); coerced to None",
            )
            return None

    @field_validator("target_table", mode="before")
    @classmethod
    def _coerce_target_table_to_allowed_or_none(cls, v):
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return None
        if not isinstance(v, str):
            _audit_safe(
                event_type="schema_drop_field",
                field_name="target_table",
                original_value=v,
                error_message="non-string value; dropped",
            )
            return None
        normalized = v.strip().lower()
        if normalized not in _ALLOWED_TARGET_TABLES:
            _audit_safe(
                event_type="schema_coerce",
                field_name="target_table",
                original_value=v,
                coerced_value=None,
                error_message=f"value {v!r} not in allow-list; coerced to None",
            )
            return None
        return normalized

    @field_validator("new_value", mode="before")
    @classmethod
    def _validate_new_value_is_dict_or_none(cls, v):
        if v is None:
            return None
        if not isinstance(v, dict):
            _audit_safe(
                event_type="schema_drop_field",
                field_name="new_value",
                original_value=v,
                error_message=f"new_value not a dict (got {type(v).__name__}); dropped",
            )
            return None
        return v  # Detailed key whitelist runs in action_executor (L4)

    @field_validator("threshold_breach", mode="before")
    @classmethod
    def _validate_threshold_breach(cls, v):
        if v is None:
            return None
        if not isinstance(v, dict):
            _audit_safe(
                event_type="schema_drop_field",
                field_name="threshold_breach",
                original_value=v,
                error_message=f"threshold_breach not a dict (got {type(v).__name__}); dropped",
            )
            return None
        # Required 'impact' key — if missing, fill with default to avoid silent UX gap
        if not v.get("impact") or not isinstance(v.get("impact"), str):
            _audit_safe(
                event_type="schema_coerce",
                field_name="threshold_breach.impact",
                original_value=v.get("impact"),
                coerced_value="<filled default>",
                error_message="impact missing/non-string; filled placeholder",
            )
            v = {**v, "impact": "İmpact alanı boş bırakıldı — manuel inceleme gerek."}
        return v


class CEODecision(_BaseDecision):
    action_type: Literal[
        "noop", "strategy_observation", "persona_create",
        "persona_retire", "model_swap", "executive_freeze_toggle",
        "weekly_review_directive",
    ]


class CPODecision(_BaseDecision):
    action_type: Literal[
        "noop", "model_swap", "cadence_adjust", "pipeline_freeze",
        "pipeline_unfreeze", "retry_policy_change", "observation",
    ]


class CBPODecision(_BaseDecision):
    action_type: Literal[
        "noop", "content_type_weight_adjust", "visual_mode_distribution_adjust",
        "scene_rotation_update", "voice_drift_alert", "observation",
    ]


class CFODecision(_BaseDecision):
    action_type: Literal[
        "noop", "cost_cap_adjust", "cost_alert",
        "model_downgrade_recommend", "observation",
    ]


class CRODecision(_BaseDecision):
    action_type: Literal[
        "noop", "forbidden_topic_add", "forbidden_topic_remove",
        "post_takedown", "compliance_halt", "cro_auto_freeze_toggle",
        "observation",
    ]


ROLE_SCHEMA = {
    "CEO": CEODecision,
    "CPO": CPODecision,
    "CBPO": CBPODecision,
    "CFO": CFODecision,
    "CRO": CRODecision,
}

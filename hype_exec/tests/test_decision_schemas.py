"""Phase 28.J — Pydantic validator behaviour tests."""
from uuid import uuid4

import pytest

from hype_exec.roles.schemas import CEODecision, CPODecision, CRODecision


def _ceo_kwargs(**override):
    base = dict(action_type="noop", rationale="test", memo="test")
    base.update(override)
    return base


def _cpo_kwargs(**override):
    base = dict(action_type="pipeline_freeze", rationale="test", memo="test")
    base.update(override)
    return base


# ─── target_id validator ────────────────────────────────────────────────

def test_target_id_valid_uuid_kept(mock_audit_log):
    uuid_str = str(uuid4())
    d = CPODecision(**_cpo_kwargs(target_id=uuid_str))
    assert d.target_id == uuid_str
    mock_audit_log.assert_not_called()


def test_target_id_slug_coerced_to_none(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_id="cansu_dut_pipeline"))
    assert d.target_id is None
    mock_audit_log.assert_called_once()
    call = mock_audit_log.call_args
    assert call.kwargs.get("event_type") == "schema_coerce"
    assert call.kwargs.get("field_name") == "target_id"


def test_target_id_empty_string_coerced_to_none(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_id=""))
    assert d.target_id is None
    mock_audit_log.assert_not_called()  # empty != coerce event


def test_target_id_explicit_none_kept(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_id=None))
    assert d.target_id is None
    mock_audit_log.assert_not_called()


def test_target_id_int_coerced_to_none(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_id=12345))
    assert d.target_id is None
    mock_audit_log.assert_called_once()


# ─── target_table validator ─────────────────────────────────────────────

def test_target_table_allowed_kept(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_table="hype_account_config"))
    assert d.target_table == "hype_account_config"
    mock_audit_log.assert_not_called()


def test_target_table_unknown_coerced_to_none(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_table="random_table_xyz"))
    assert d.target_table is None
    mock_audit_log.assert_called_once()
    assert mock_audit_log.call_args.kwargs.get("field_name") == "target_table"


def test_target_table_case_normalized(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(target_table="HYPE_ACCOUNT_CONFIG"))
    assert d.target_table == "hype_account_config"


# ─── threshold_breach validator ─────────────────────────────────────────

def test_threshold_breach_valid_kept(mock_audit_log):
    d = CRODecision(
        action_type="compliance_halt", rationale="x", memo="y",
        threshold_breach={"field": "x", "current": 1, "threshold": 0, "impact": "ok"},
    )
    assert d.threshold_breach["impact"] == "ok"


def test_threshold_breach_missing_impact_filled(mock_audit_log):
    d = CRODecision(
        action_type="compliance_halt", rationale="x", memo="y",
        threshold_breach={"field": "x", "current": 1},
    )
    assert "impact" in d.threshold_breach
    assert "manuel inceleme" in d.threshold_breach["impact"].lower() or \
           "placeholder" in d.threshold_breach["impact"].lower() or \
           d.threshold_breach["impact"]
    # audit log called for missing impact
    assert any(c.kwargs.get("field_name") == "threshold_breach.impact"
               for c in mock_audit_log.call_args_list)


def test_threshold_breach_non_dict_dropped(mock_audit_log):
    d = CEODecision(**_ceo_kwargs(threshold_breach="not a dict"))
    assert d.threshold_breach is None
    assert any(c.kwargs.get("event_type") == "schema_drop_field"
               for c in mock_audit_log.call_args_list)


# ─── new_value validator ────────────────────────────────────────────────

def test_new_value_dict_kept(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(new_value={"executive_freeze": True}))
    assert d.new_value == {"executive_freeze": True}


def test_new_value_non_dict_dropped(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(new_value="freeze"))
    assert d.new_value is None
    assert any(c.kwargs.get("field_name") == "new_value"
               for c in mock_audit_log.call_args_list)


def test_new_value_none_kept(mock_audit_log):
    d = CPODecision(**_cpo_kwargs(new_value=None))
    assert d.new_value is None
    mock_audit_log.assert_not_called()

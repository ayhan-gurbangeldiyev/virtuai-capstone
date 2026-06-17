"""Phase 28.J — action_executor sanitize_new_value behaviour tests."""
import pytest

from hype_exec.tools.action_executor import sanitize_new_value, TABLE_KEY_SPECS


def test_sanitize_unknown_table_drops_everything(mock_audit_log):
    out = sanitize_new_value("random_table", {"some_key": "some_value"})
    assert out == {}
    assert any(c.kwargs.get("event_type") == "key_whitelist_drop"
               for c in mock_audit_log.call_args_list)


def test_sanitize_unknown_key_dropped(mock_audit_log):
    out = sanitize_new_value(
        "hype_account_config",
        {"daily_cost_cap_usd": 3.5, "unknown_random_key": "x"},
    )
    assert out == {"daily_cost_cap_usd": 3.5}
    assert any(c.kwargs.get("field_name") == "unknown_random_key"
               and c.kwargs.get("event_type") == "key_whitelist_drop"
               for c in mock_audit_log.call_args_list)


def test_sanitize_type_coerce_str_to_float(mock_audit_log):
    out = sanitize_new_value("hype_account_config", {"daily_cost_cap_usd": "4.50"})
    assert out == {"daily_cost_cap_usd": 4.5}
    # value_coerce event fired
    assert any(c.kwargs.get("event_type") == "value_coerce"
               and c.kwargs.get("field_name") == "daily_cost_cap_usd"
               for c in mock_audit_log.call_args_list)


def test_sanitize_range_clamp_high(mock_audit_log):
    # daily_cost_cap_usd hi=10.0
    out = sanitize_new_value("hype_account_config", {"daily_cost_cap_usd": 99.0})
    assert out["daily_cost_cap_usd"] == 10.0
    assert any(c.kwargs.get("event_type") == "value_coerce"
               and "above upper bound" in (c.kwargs.get("error_message") or "")
               for c in mock_audit_log.call_args_list)


def test_sanitize_range_clamp_low(mock_audit_log):
    out = sanitize_new_value("hype_account_config", {"daily_cost_cap_usd": -3.0})
    assert out["daily_cost_cap_usd"] == 0.0
    assert any(c.kwargs.get("event_type") == "value_coerce"
               and "below lower bound" in (c.kwargs.get("error_message") or "")
               for c in mock_audit_log.call_args_list)


def test_sanitize_bool_string_true(mock_audit_log):
    out = sanitize_new_value("hype_account_config", {"executive_freeze": "true"})
    assert out == {"executive_freeze": True}


def test_sanitize_bool_string_false(mock_audit_log):
    out = sanitize_new_value("hype_account_config", {"auto_publish_enabled": "no"})
    assert out == {"auto_publish_enabled": False}


def test_sanitize_invalid_bool_dropped(mock_audit_log):
    out = sanitize_new_value("hype_account_config", {"executive_freeze": "maybe"})
    assert out == {}
    assert any(c.kwargs.get("event_type") == "key_whitelist_drop"
               for c in mock_audit_log.call_args_list)


def test_sanitize_daily_drafts_invalid_status_dropped(mock_audit_log):
    out = sanitize_new_value("daily_drafts", {"status": "weird_status"})
    assert out == {}
    assert any(c.kwargs.get("event_type") == "key_whitelist_drop"
               and "not in enum" in (c.kwargs.get("error_message") or "")
               for c in mock_audit_log.call_args_list)


def test_sanitize_daily_drafts_valid_status(mock_audit_log):
    out = sanitize_new_value("daily_drafts", {"status": "auto_rejected"})
    assert out == {"status": "auto_rejected"}


def test_sanitize_none_table_drops(mock_audit_log):
    out = sanitize_new_value(None, {"daily_cost_cap_usd": 3.5})
    assert out == {}


def test_sanitize_empty_raw_returns_empty(mock_audit_log):
    assert sanitize_new_value("hype_account_config", {}) == {}
    assert sanitize_new_value("hype_account_config", None) == {}


def test_sanitize_persona_keys(mock_audit_log):
    out = sanitize_new_value("personas", {"video_enabled": True, "visual_enabled": "1"})
    assert out == {"video_enabled": True, "visual_enabled": True}

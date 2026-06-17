"""pytest fixtures + audit mocking (avoid real DB writes during tests)."""
import sys
import pytest
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def mock_audit_log(monkeypatch):
    """Stub log_audit + supabase_client so tests don't touch Supabase.

    Yields a MagicMock so tests can assert on captured events.
    """
    audit_mock = MagicMock()

    # Patch the actual function — every callsite uses lazy import
    # `from hype_exec.audit import log_audit` so module-level patch works.
    import hype_exec.audit as audit_mod
    monkeypatch.setattr(audit_mod, "log_audit", audit_mock)

    # Also patch make_supabase (lazy-imported inside log_audit) so even
    # if the real function path is followed we never hit network.
    fake_sb = MagicMock()
    fake_sb.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])

    if "hype_exec.tools.supabase_client" in sys.modules:
        monkeypatch.setattr(
            sys.modules["hype_exec.tools.supabase_client"],
            "make_supabase",
            lambda: fake_sb,
        )

    return audit_mock

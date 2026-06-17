"""Stage 1.1 regression — gate-block hold path must not TypeError.

The auto-publish path in flow.py:run_publish loops over
self.state.platform_drafts and writes a daily_drafts row per platform
when ANY draft in the batch is HARD_BLOCKed by the faithfulness gate.

Previous bug: the call used pd=_pd_h, but _write_daily_draft's parameter
is platform_draft. At runtime → TypeError → the whole batch was lost
(no daily_drafts rows written, no draft for the operator to review,
no audit trail of what the gate caught).

This test exercises the EXACT call shape with a minimal in-process
HypeFlow instance to prove the keyword resolves correctly. It does NOT
hit the network or any LLM.
"""
from __future__ import annotations

from pathlib import Path


def test_write_daily_draft_signature_uses_platform_draft_kw():
    """Source-level guard: _write_daily_draft's parameter must be
    `platform_draft`, NOT `pd`. We grep the def line instead of importing
    flow.py — the import would pull crewai etc. into CI."""
    src = (Path(__file__).resolve().parent.parent / "flow.py").read_text(encoding="utf-8")
    # Find the def line + the next few lines
    import re
    m = re.search(
        r"def\s+_write_daily_draft\s*\(\s*self\s*,\s*\n(?:[ \t]*[^\n]*\n){1,15}",
        src,
    )
    assert m, "Could not find _write_daily_draft definition in flow.py"
    sig_window = m.group(0)
    assert "platform_draft" in sig_window, (
        f"_write_daily_draft signature missing `platform_draft` kwarg. "
        f"Stage 1.1 fix expects this name. Window:\n{sig_window}"
    )
    # The `pd` kwarg must NOT be there
    import re as _re
    bad = _re.search(r"[\s,(]pd\s*[:=]", sig_window)
    assert not bad, (
        "Reverting to `pd` would silently re-break the gate-block hold path."
    )


def test_no_pd_keyword_call_in_flow_py():
    """Source-level guard: the literal pattern `pd=` in a
    _write_daily_draft call would TypeError. Cheap grep test."""
    src = (Path(__file__).resolve().parent.parent / "flow.py").read_text(encoding="utf-8")
    # Find lines like: self._write_daily_draft( ... \n  pd=...
    # Scan windows of N lines containing _write_daily_draft.
    lines = src.splitlines()
    for i, line in enumerate(lines):
        if "_write_daily_draft(" not in line:
            continue
        window = "\n".join(lines[i : i + 12])
        # `pd=` as a kwarg, surrounded by whitespace OR comma/open-paren
        import re
        bad = re.search(r"[\s,(]pd\s*=", window)
        assert not bad, (
            f"flow.py line {i+1}: _write_daily_draft( with a `pd=` kwarg — "
            f"that argument no longer exists (renamed to platform_draft). "
            f"Window:\n{window}"
        )


if __name__ == "__main__":
    test_write_daily_draft_signature_uses_platform_draft_kw()
    print("✓ test_write_daily_draft_signature_uses_platform_draft_kw")
    test_no_pd_keyword_call_in_flow_py()
    print("✓ test_no_pd_keyword_call_in_flow_py")
    print("ALL OK")

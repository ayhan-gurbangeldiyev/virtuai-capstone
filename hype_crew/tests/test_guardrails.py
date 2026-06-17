"""Guardrail tests — formatting + safety."""
from types import SimpleNamespace

from guardrails import (
    writer_formatting_guardrail,
    compliance_safety_guardrail,
    content_safety_check,
)


def _writer_output(content: str):
    """Mock a CrewAI TaskOutput with .pydantic.content attribute."""
    return SimpleNamespace(pydantic=SimpleNamespace(content=content))


def _compliance_output(approved: bool, rejection_reason: str | None = None):
    return SimpleNamespace(pydantic=SimpleNamespace(approved=approved, rejection_reason=rejection_reason))


# ─── writer_formatting_guardrail ───────────────────────────────────────────


def test_writer_guardrail_passes_clean():
    out = _writer_output("hook line.\n\nbody beat.\n\npunchline.")
    passed, feedback = writer_formatting_guardrail(out)
    assert passed, feedback


def test_writer_guardrail_em_dash_rejected():
    out = _writer_output("this is great — let me explain.")
    passed, feedback = writer_formatting_guardrail(out)
    assert not passed
    assert "em-dash" in feedback.lower() or "em dash" in feedback.lower()


def test_writer_guardrail_corporate_words_rejected():
    out = _writer_output("we will leverage this exciting opportunity to unlock potential.")
    passed, feedback = writer_formatting_guardrail(out)
    assert not passed
    assert "leverage" in feedback.lower()


def test_writer_guardrail_too_long_rejected():
    # Ceiling raised to 4000 (schema-aligned, X Premium long-form). Use 4500
    # to assert the upper bound still rejects walls of text.
    out = _writer_output("x" * 4500)
    passed, feedback = writer_formatting_guardrail(out)
    assert not passed
    assert "4000" in feedback or "too long" in feedback.lower()


def test_writer_guardrail_wall_of_text_rejected():
    # 100 char single line with no breaks
    out = _writer_output("a" * 100)
    passed, feedback = writer_formatting_guardrail(out)
    assert not passed
    assert "wall" in feedback.lower() or "break" in feedback.lower()


def test_writer_guardrail_empty_rejected():
    out = _writer_output("")
    passed, feedback = writer_formatting_guardrail(out)
    assert not passed


# ─── compliance_safety_guardrail ───────────────────────────────────────────


def test_compliance_guardrail_clean_approve():
    out = _compliance_output(approved=True, rejection_reason=None)
    passed, msg = compliance_safety_guardrail(out)
    assert passed


def test_compliance_guardrail_clean_reject():
    out = _compliance_output(approved=False, rejection_reason="forbidden_topic: politics")
    passed, msg = compliance_safety_guardrail(out)
    assert passed  # Compliance correctly rejecting is FINE — guardrail passes


def test_compliance_guardrail_inconsistent_decision():
    out = _compliance_output(approved=True, rejection_reason="dedup similarity 0.91")
    passed, msg = compliance_safety_guardrail(out)
    assert not passed
    assert "inconsistent" in msg.lower() or "rejection_reason" in msg.lower()


# ─── content_safety_check ──────────────────────────────────────────────────


def test_content_safety_clean():
    passed, violations = content_safety_check("just shipped a new feature")
    assert passed
    assert violations == []


def test_content_safety_phishing():
    passed, violations = content_safety_check("click here to verify your account")
    assert not passed
    assert len(violations) > 0

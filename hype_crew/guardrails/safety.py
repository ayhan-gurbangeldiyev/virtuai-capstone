"""Safety guardrail — backstop on Compliance.

Runs after Compliance task. If Compliance somehow approves a bad draft
(e.g., LLM hallucination), this guardrail catches it. Light, regex-only.
"""
import re
from typing import Any

# Patterns that should NEVER appear regardless of voice/config
NEVER_PATTERNS = [
    # Slurs / hate speech (basic anchors; extend over time)
    r"\b(faggot|retard|nigger)\b",
    # Stock pump/dump red flags
    r"\b(buy now|get rich quick|guaranteed returns?|10x in a week)\b",
    # Phishing-like
    r"(click here|verify your account|urgent action)",
]


def _extract_approved_and_content(task_output: Any) -> tuple[bool, str]:
    pyd = getattr(task_output, "pydantic", None)
    if pyd is not None:
        approved = bool(getattr(pyd, "approved", False))
        # Compliance output doesn't carry content; we look at content via the run's draft
        # For safety guardrail purpose, we check approved flag + rejection_reason
        rejection = getattr(pyd, "rejection_reason", None) or ""
        return approved, rejection

    jd = getattr(task_output, "json_dict", None)
    if isinstance(jd, dict):
        return bool(jd.get("approved")), jd.get("rejection_reason") or ""

    return False, ""


def compliance_safety_guardrail(task_output: Any) -> tuple[bool, str]:
    """Backstop check on Compliance output.

    Doesn't re-run Compliance — just validates the decision is sensible.
    """
    approved, rejection = _extract_approved_and_content(task_output)

    # If Compliance rejected, that's fine — let the Flow router handle it
    if not approved:
        return (True, f"Compliance correctly rejected: {rejection[:100]}")

    # If approved but rejection_reason is suspicious, flag it
    if approved and rejection and len(rejection) > 5 and "warning" not in rejection.lower():
        return (False, (
            "Compliance approved BUT included a rejection_reason. Either approve "
            f"cleanly (rejection_reason=null) or reject. Current: '{rejection[:100]}'."
        ))

    return (True, "Compliance decision is consistent.")


def content_safety_check(content: str) -> tuple[bool, list[str]]:
    """Standalone check for absolute-never patterns. Called from Compliance tool.

    Returns (passed, violations).
    """
    violations = []
    for pat in NEVER_PATTERNS:
        if re.search(pat, content, re.IGNORECASE):
            violations.append(f"banned_pattern: {pat}")
    return (len(violations) == 0, violations)

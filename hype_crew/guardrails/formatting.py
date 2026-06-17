"""Formatting guardrail for Writer task.

Runs after Writer produces output. If formatting violations detected, returns
(False, feedback) — CrewAI retries Writer with the feedback included.

Cheap (no LLM, just regex) — runs every time as a fast check before
Compliance does deeper analysis.
"""
import re
from typing import Any


CORPORATE_WORDS = [
    "leverage", "leveraging", "exciting", "game-changing", "synergy",
    "unlock potential", "in the era of", "in today's fast-paced",
    "deep dive", "moving forward", "circle back", "low-hanging fruit",
    "robust", "scalable solution", "best-in-class", "thought leadership",
    "value-add", "paradigm shift", "next-generation",
]


def _extract_content(task_output: Any) -> str:
    """Pull content string from a CrewAI TaskOutput, regardless of shape."""
    # Pydantic output path
    pyd = getattr(task_output, "pydantic", None)
    if pyd is not None and hasattr(pyd, "content"):
        return pyd.content

    # JSON dict path
    jd = getattr(task_output, "json_dict", None)
    if isinstance(jd, dict) and "content" in jd:
        return jd["content"]

    # Raw string fallback
    raw = getattr(task_output, "raw", None) or str(task_output)
    return raw if isinstance(raw, str) else ""


def writer_formatting_guardrail(task_output: Any) -> tuple[bool, str]:
    """Validate Writer's output. Returns (passed, feedback).

    If passed=False, CrewAI re-runs Writer with `feedback` as additional
    context (up to guardrail_max_retries times).
    """
    content = _extract_content(task_output)

    if not content or not content.strip():
        return (False, "Output is empty. Produce a tweet with line breaks and a hook.")

    issues = []

    # 1. Em-dash detection
    if "—" in content or "–" in content:
        issues.append("Em-dash (—) detected. Replace with comma, period, or line break.")

    # 2. Length check — aligned with schema (4000) + X Premium long-form support.
    # Strategist picks uzunluk; Compliance enforces the upper ceiling only.
    if len(content) > 4000:
        issues.append(f"Too long: {len(content)} chars. Hard ceiling is 4000.")

    if len(content) < 10:
        issues.append(f"Too short: {len(content)} chars. Minimum 10.")

    # 3. Corporate words
    content_low = content.lower()
    detected = [w for w in CORPORATE_WORDS if re.search(r"\b" + re.escape(w) + r"\b", content_low)]
    if detected:
        issues.append(f"Corporate words detected: {detected[:5]}. Use plain conversational language.")

    # 4. Line break requirement for >80 char content
    if len(content) > 80 and "\n" not in content:
        issues.append("Wall of text detected. Break into multiple lines with blank line between thoughts.")

    # 5. Long-line check removed — long-form posts naturally contain longer
    # sentences. Voice/style critic handles density downstream.

    if issues:
        feedback = (
            "FORMATTING ISSUES — please rewrite addressing these:\n"
            + "\n".join(f"- {x}" for x in issues)
            + "\n\nKeep the same core message and hook, just fix the format."
        )
        return (False, feedback)

    return (True, "Format check passed.")

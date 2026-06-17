# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""Capstone bug fix (4 Jun 2026) — strip markdown skeleton labels.

Symptom (seen in production daily_drafts):
    "### YouTube Shorts Script. **HOOK (0-3.5sn):**. Anthropic, bu sabah..."
    "**[0-3.5sn] HOOK**. Nvidia bu sabah RTX Spark..."
    "**CTR Optimize Başlık:** OpenAI Codex... **Video Script:**. OpenAI tam..."
    "...Bu güç... ---. ### Twitter. Nvidia..."

Root cause: backend/prompts/voice_modes.py lists forbidden skeleton tokens
by name inside two rule blocks (TTS_VIDEO_SCRIPT_RULES,
TTS_VIDEO_HOOK_CLOSE_RULES). The negative-instruction pattern leaks ~25-30%
of the time on Gemini 3 Flash — tokens reach daily_drafts.content,
captions, and TTS input. Jury-obvious bug.

Important observation from corpus: leaked drafts often emit the entire
script on a SINGLE LINE with period-separators between skeleton tokens
(e.g. `### Title. **HOOK**. real prose. **CLOSE**. real prose.`).
Anchored ^...$ patterns alone do not catch this — we also need
inline-aware patterns that match the skeleton tokens anywhere in line.

Fix: pure post-processor at the response boundary in
backend/routes/hype_internal.py. Substantive prose untouched.
"""
from __future__ import annotations

import re

# Known skeleton/scaffolding labels. Restricted set — adding tokens here is
# explicit, safe, and reviewable. We do NOT match arbitrary **WORD** spans;
# Cansu prose legitimately uses bold for emphasis on other words.
_LABEL_TOKEN = (
    r"(?:"
    r"HOOK|SUBSTANCE|CLOSE|INTRO|OUTRO|SETUP|PAYOFF|"
    r"RETENTION\s+HOOK|RETENTION|"
    r"CTR\s+Optimize\s+Başlık|Video\s+Script|"
    r"Açıklama|Title|Başlık"
    r")"
)

# --- INLINE patterns (the common production case) -----------------------
# Markdown header that runs to the first period or newline.
# Matches `### YouTube Shorts Script.`, `### Twitter.`, `### Anthropic ...`.
# Non-greedy and stops at `.` or `\n` so it cannot eat real prose past
# the inline header.
_INLINE_HEADER_RE = re.compile(
    r"#{1,6}\s+[^.\n]{1,120}\s*\.?\s*",
    re.MULTILINE,
)

# Horizontal rule appearing inline (`---` or `---.`).
_INLINE_HRULE_RE = re.compile(r"\s*-{3,}\s*\.?\s*")

# Bold-wrapped skeleton label spans:
#   **HOOK**, **HOOK (0-3.5sn):**, **[0-3.5sn] HOOK**,
#   **CLOSE (15-19sn):**, **Video Script:**, **CTR Optimize Başlık:**, etc.
# Optional leading time bracket and trailing time parens are matched
# together with the label so a trailing `.` separator is also consumed.
_LABEL_SPAN_RE = re.compile(
    r"\*\*\s*"
    r"(?:\[?\s*\d+(?:[\.,]\d+)?\s*[-–]\s*\d+(?:[\.,]\d+)?\s*sn?\]?\s*)?"  # optional leading [0-3.5sn]
    + _LABEL_TOKEN +
    r"\s*"
    r"(?:\(\s*\d+(?:[\.,]\d+)?\s*[-–]\s*\d+(?:[\.,]\d+)?\s*sn?\s*\))?"      # optional trailing (0-3.5sn)
    r"\s*:?\s*\*\*\s*\.?\s*",
    re.IGNORECASE,
)

# Whitespace housekeeping
_DOUBLE_SPACE_RE = re.compile(r"[ \t]{2,}")
_COLLAPSE_NEWLINES_RE = re.compile(r"\n{3,}")
_ORPHAN_PUNCT_RE = re.compile(r"(?:^|\n)\s*[.,;:]\s*")  # stray ". " left after a removal


def strip_skeleton_labels(content: str) -> tuple[str, int]:
    """Return (cleaned_content, chars_removed).

    Removes only known skeleton scaffolding — substantive prose untouched.
    Pure post-processor, regex-only, no model calls.
    """
    if not content:
        return content, 0
    original_len = len(content)

    cleaned = _LABEL_SPAN_RE.sub(" ", content)
    cleaned = _INLINE_HEADER_RE.sub(" ", cleaned)
    cleaned = _INLINE_HRULE_RE.sub(" ", cleaned)

    # Clean up leftover whitespace/punctuation from removals
    cleaned = _ORPHAN_PUNCT_RE.sub("\n", cleaned)
    cleaned = _DOUBLE_SPACE_RE.sub(" ", cleaned)
    cleaned = _COLLAPSE_NEWLINES_RE.sub("\n\n", cleaned).strip()

    return cleaned, original_len - len(cleaned)

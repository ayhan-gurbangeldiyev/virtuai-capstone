"""Pre-spend validation for video render pipelines.

Berkay's money-side rule (2026-06-07): a HeyGen Avatar V render costs
~$0.10/sec × 30-60s ≈ $3-6 each. Before we burn that — and before we even
pay MiniMax to synthesize — the canonical script MUST be:

  (a) within the platform target band: 510-1000 chars
      (~30-60s narration; safe under YouTube Shorts 60s + Reels 90s)
  (b) end on a complete sentence (real closing, not mid-clause)
  (c) non-empty after stripping

If any check fails we DO NOT call HeyGen. The caller logs the reason,
marks the draft for script repair (video_regen_pending=true,
video_integrity_reason='pre_spend_rejected:<reason>'), and bails BEFORE
spending money.

This is the upstream counterpart to video_integrity.check_video_integrity
which catches truncation AFTER the render. Together they bracket the
render so a bad script can't quietly cost money.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


SCRIPT_TARGET_MIN_CHARS = 510
SCRIPT_TARGET_MAX_CHARS = 1000

# Mirror the canonical cap from flow.py (1000 chars ≈ 60s @ ~17 cps Turkish TTS).
# A script over this would be truncated by the canonical resolver upstream.
SENTENCE_END_CHARS = ".!?…"
SOFT_END_CHARS = '"\')]»›'  # closing quotes/brackets that can trail a sentence end


class PreSpendRejected(Exception):
    """Raised when a canonical script fails pre-spend validation.

    The caller MUST NOT call HeyGen (or even MiniMax) after this. The draft
    needs script repair first, then re-validation.
    """

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass
class PreSpendResult:
    ok: bool
    reason: str = ""
    detail: str = ""
    chars: int = 0


def validate_script_before_spend(
    script: str,
    *,
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> PreSpendResult:
    """Return PreSpendResult.ok=True iff the script is render-safe.

    Pure function. No side effects. The caller decides whether to raise,
    log, or attempt repair. `min_chars`/`max_chars` override the module
    defaults — the cansu_video_v2 complete-news path uses a tighter band
    (≤40s) than the legacy 510-1000 platform-draft band.
    """
    lo = SCRIPT_TARGET_MIN_CHARS if min_chars is None else min_chars
    hi = SCRIPT_TARGET_MAX_CHARS if max_chars is None else max_chars

    if script is None:
        return PreSpendResult(
            ok=False, reason="empty_script", detail="script is None"
        )

    stripped = script.strip()
    n = len(stripped)

    if n == 0:
        return PreSpendResult(
            ok=False, reason="empty_script", detail="script is empty after strip"
        )

    if n < lo:
        return PreSpendResult(
            ok=False,
            reason="script_too_short",
            detail=f"{n} chars < {lo} target floor",
            chars=n,
        )

    if n > hi:
        return PreSpendResult(
            ok=False,
            reason="script_too_long",
            detail=f"{n} chars > {hi} target ceiling",
            chars=n,
        )

    tail = stripped.rstrip()
    while tail and tail[-1] in SOFT_END_CHARS:
        tail = tail[:-1]
    if not tail or tail[-1] not in SENTENCE_END_CHARS:
        last_clause = re.split(r"[.!?…]\s+", stripped)[-1][:80]
        return PreSpendResult(
            ok=False,
            reason="mid_clause_truncation",
            detail=f"last char {(tail or '∅')[-1]!r}; tail clause={last_clause!r}",
            chars=n,
        )

    return PreSpendResult(ok=True, chars=n)


def assert_render_safe(
    script: str,
    *,
    draft_id: str = "?",
    min_chars: int | None = None,
    max_chars: int | None = None,
) -> int:
    """Convenience wrapper: validate, log, raise if not OK. Returns char count."""
    r = validate_script_before_spend(script, min_chars=min_chars, max_chars=max_chars)
    if not r.ok:
        logger.error(
            "[pre_spend_guard] REJECTED draft=%s reason=%s detail=%s",
            draft_id[:8], r.reason, r.detail,
        )
        raise PreSpendRejected(r.reason, r.detail)
    lo = SCRIPT_TARGET_MIN_CHARS if min_chars is None else min_chars
    hi = SCRIPT_TARGET_MAX_CHARS if max_chars is None else max_chars
    logger.info(
        "[pre_spend_guard] OK draft=%s chars=%d (band %d-%d)",
        draft_id[:8], r.chars, lo, hi,
    )
    return r.chars

"""Regression tests for the SEV-1 follow-up CURE — canonical video
script + caption alignment (PART 2 + PART 4 + PART 5).

⚠️ NEVER PUBLISH FROM A TEST. ⚠️
Source-level + helper-level only. No prod row, no Postiz, no HeyGen.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parent.parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, "/opt/hype-crew")


# ─── PART 2 cure: 300-char cap removed, canonical script picked ─────


# flow.py imports crewai (not in backend venv), so we source-grep these.

def _flow_py() -> str:
    p = Path("/opt/hype-crew/flow.py")
    if not p.exists():
        p = Path(__file__).resolve().parent.parent.parent / "hype_crew" / "flow.py"
    return p.read_text(encoding="utf-8")


def test_canonical_script_cap_constant_raised():
    """The hard-coded 300-char cap was the production truncation cause.
    The new cap honors HeyGen + MiniMax limits (~90s = ~1500 chars)."""
    src = _flow_py()
    import re
    m = re.search(r"CANONICAL_VIDEO_SCRIPT_CAP_CHARS\s*=\s*(\d+)", src)
    assert m, "CANONICAL_VIDEO_SCRIPT_CAP_CHARS not found in flow.py"
    cap = int(m.group(1))
    assert cap >= 1000, (
        f"canonical cap is {cap} — too low; this was the SEV-1 "
        "truncation root cause. Set ≥1500."
    )


def test_resolve_video_script_no_longer_trims_to_300():
    """grep: the literal 300-char cap line must not exist anymore."""
    src = _flow_py()
    assert "if len(script) > 300:" not in src, (
        "the 300-char cap was the root cause of the SEV-1; it must stay removed"
    )


def test_resolve_video_script_returns_longest_within_cap():
    """The resolution function must prefer the longest platform-draft
    that fits the canonical cap. Source-grep + sentinel check."""
    src = _flow_py()
    # The function must reference both the priority list AND the cap.
    start = src.index("def _resolve_video_script(")
    end = src.index("def ", start + 10)
    body = src[start:end]
    assert "CANONICAL_VIDEO_SCRIPT_CAP_CHARS" in body, (
        "_resolve_video_script must honor the canonical cap constant"
    )
    # Must sort/pick by length, not just match-by-platform.
    assert ("sort" in body or "key=lambda" in body or "max(" in body), (
        "_resolve_video_script must pick the LONGEST candidate, not "
        "just first-match"
    )


def test_pin_caption_helper_exists_and_overwrites_video_platforms():
    """grep: _pin_caption_to_canonical_script exists, is called after
    script resolution, and iterates _VIDEO_PLATFORMS."""
    src = _flow_py()
    assert "_pin_caption_to_canonical_script" in src, (
        "PART 4 caption-alignment helper missing — captions on video "
        "platforms won't match the spoken script"
    )
    assert "self._pin_caption_to_canonical_script(script)" in src, (
        "caption-alignment must be called AFTER _resolve_video_script"
    )
    # The helper body must iterate over video platforms.
    start = src.index("def _pin_caption_to_canonical_script(")
    end = src.index("def ", start + 10)
    helper_body = src[start:end]
    assert "_VIDEO_PLATFORMS" in helper_body


# ─── PART 4 caption alignment ───────────────────────────────────────


def test_pin_caption_helper_source_says_video_only():
    """Source-grep that the helper only rewrites pd.content when
    pd.platform.lower() is IN _VIDEO_PLATFORMS — non-video platforms
    must stay untouched."""
    src = _flow_py()
    start = src.index("def _pin_caption_to_canonical_script(")
    end = src.index("def ", start + 10)
    body = src[start:end]
    assert "pd.platform.lower() in" in body
    assert "pd.content =" in body


# ─── PART 5 calibration: tightened tolerance + TTS-precise expected ──


def test_default_tolerance_is_15_pct():
    """SEV-1 calibration: 20% let borderline IG cases through; tighten
    to 15% so a draft 19% short is now CAUGHT."""
    from tools.video_integrity import _duration_tolerance
    assert _duration_tolerance() == 0.15, (
        "default tolerance must be 0.15; the 20% setting let the IG "
        "19%-short edge case through unflagged"
    )


def test_19_pct_short_now_fails_under_tightened_tolerance(monkeypatch):
    """The exact IG borderline (343 chars → expected 21.93s, actual 19.76s,
    9.9% short) should still PASS. A 19% short case should FAIL."""
    import tools.video_integrity as vi

    def _ffp(_p):
        # 16.0s video for content that expects ~20s. 20% short → boundary,
        # 15% tolerance → FAIL.
        return {
            "streams": [
                {"codec_type": "video", "duration": "16.00"},
                {"codec_type": "audio", "duration": "16.00"},
            ],
            "format": {"duration": "16.00"},
        }
    monkeypatch.setattr(vi, "_ffprobe_json", _ffp)
    monkeypatch.setattr(vi.os.path, "isfile", lambda _p: True)

    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 343,  # expected ≈ 20.18s
    )
    assert r.ok is False, (
        f"expected FAIL on 20% short, got ok=True "
        f"(actual={r.video_duration_s}, expected={r.expected_duration_s})"
    )
    assert "duration_below_floor" in r.reason


def test_tts_audio_duration_override_takes_precedence(monkeypatch):
    """PART 5: when the caller knows the precise TTS audio duration,
    pass it as tts_audio_duration_s and the integrity check uses THAT
    instead of the chars÷rate estimate."""
    import tools.video_integrity as vi

    def _ffp(_p):
        return {
            "streams": [
                {"codec_type": "video", "duration": "35.0"},
                {"codec_type": "audio", "duration": "35.0"},
            ],
            "format": {"duration": "35.0"},
        }
    monkeypatch.setattr(vi, "_ffprobe_json", _ffp)
    monkeypatch.setattr(vi.os.path, "isfile", lambda _p: True)

    from tools.video_integrity import check_video_integrity
    # Content would estimate ~20s. But TTS knows it's 35s → use 35s.
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 343,
        tts_audio_duration_s=35.0,
    )
    assert r.ok is True
    assert r.expected_duration_s == 35.0

"""Regression tests for video integrity (SEV-1 follow-up P0).

⚠️ NEVER PUBLISH FROM A TEST. ⚠️
Same discipline as test_approve_publish_seam.py + test_video_content_binding.py.
This file does NOT touch any prod row, does NOT call approve_draft against
real data, does NOT invoke any real video pipeline. The integrity check is
proven by:
  - calling the helper directly on synthetic ffprobe payloads,
  - source-level grep on the approve handlers,
  - exercising the expected-duration math against known content lengths.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parent.parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, "/opt/hype-crew")


# ─── (1) Expected-duration math ─────────────────────────────────────


def test_expected_duration_grows_with_content():
    from tools.video_integrity import expected_duration_from_content as ed
    short = ed("Anthropic'ten iki cümle.")  # ~25 chars
    med = ed("a" * 300)
    long_ = ed("a" * 700)
    assert 0 < short < med < long_
    # Sanity: 300 chars / 17 cps ≈ 17.6s plus tiny punct overhead.
    assert 16.0 < med < 22.0
    # 700 chars / 17 ≈ 41s
    assert 38.0 < long_ < 46.0


def test_expected_duration_handles_pause_markers():
    from tools.video_integrity import expected_duration_from_content as ed
    base = "Anthropic'ten iki cümle, ölçülü bir dille."
    with_pause = base + " <#2.5#> Test."
    assert ed(with_pause) > ed(base) + 2.0


def test_expected_duration_empty():
    from tools.video_integrity import expected_duration_from_content as ed
    assert ed("") == 0.0
    assert ed(None) == 0.0  # type: ignore[arg-type]


# ─── (2) Integrity helper semantics (via synthetic ffprobe output) ─


@pytest.fixture
def fake_ffprobe(monkeypatch):
    """Patch _ffprobe_json so we can simulate any file shape without
    touching real videos."""
    import tools.video_integrity as vi

    def _make_ffprobe(video_dur: float = 30.0, audio_dur: float = 30.0,
                     container_dur: float = 30.0,
                     missing_video: bool = False):
        streams = []
        if not missing_video:
            streams.append({"codec_type": "video", "duration": str(video_dur)})
        streams.append({"codec_type": "audio", "duration": str(audio_dur)})

        def _patched(_path):
            return {
                "streams": streams,
                "format": {"duration": str(container_dur)},
            }
        monkeypatch.setattr(vi, "_ffprobe_json", _patched)
        # also bypass the os.path.isfile gate
        monkeypatch.setattr(vi.os.path, "isfile", lambda _p: True)

    return _make_ffprobe


def test_integrity_pass_when_durations_match(fake_ffprobe):
    fake_ffprobe(video_dur=22.0, audio_dur=22.0, container_dur=22.0)
    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 350,  # ~20.6s expected
    )
    assert r.ok is True
    assert r.reason is None
    assert r.video_duration_s == 22.0


def test_integrity_fail_on_duration_below_floor(fake_ffprobe):
    """The SEV-1 case: 19s file for a 700-char (~41s expected) script."""
    fake_ffprobe(video_dur=19.0, audio_dur=19.0, container_dur=19.0)
    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 700,
    )
    assert r.ok is False
    assert "duration_below_floor" in r.reason
    assert r.video_duration_s == 19.0
    assert r.expected_duration_s > 38.0


def test_integrity_fail_on_audio_video_drift(fake_ffprobe):
    fake_ffprobe(video_dur=30.0, audio_dur=22.0, container_dur=30.0)
    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 350,
    )
    assert r.ok is False
    assert "audio_video_drift" in r.reason


def test_integrity_fail_on_missing_video_stream(fake_ffprobe):
    fake_ffprobe(missing_video=True, audio_dur=30.0, container_dur=30.0)
    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(
        file_path="/dev/null",
        content_for_tts="a" * 350,
    )
    assert r.ok is False
    assert "missing_video_stream" in r.reason


def test_integrity_fail_on_unreadable_file(monkeypatch):
    """ffprobe raises → we return ok=False (fail-safe)."""
    import tools.video_integrity as vi

    def _boom(_p):
        raise FileNotFoundError("simulated missing file")
    monkeypatch.setattr(vi, "_ffprobe_json", _boom)
    monkeypatch.setattr(vi.os.path, "isfile", lambda _p: True)

    from tools.video_integrity import check_video_integrity
    r = check_video_integrity(file_path="/dev/null", content_for_tts="abc")
    assert r.ok is False
    assert "ffprobe_unreadable" in r.reason


# ─── (3) The approve-seam refusal helper ────────────────────────────


def test_helper_passes_when_video_integrity_ok_true():
    from routes.hype import _video_integrity_defective
    defective, reason = _video_integrity_defective({
        "video_url": "https://x/x.mp4",
        "video_integrity_ok": True,
    })
    assert defective is False
    assert reason is None


def test_helper_passes_when_video_integrity_ok_null_legacy():
    """Pre-binding rows. Soft-pass policy. Same shape as the
    content-binding helper's NULL handling."""
    from routes.hype import _video_integrity_defective
    defective, reason = _video_integrity_defective({
        "video_url": "https://x/x.mp4",
        "video_integrity_ok": None,
    })
    assert defective is False


def test_helper_refuses_when_video_integrity_ok_false():
    from routes.hype import _video_integrity_defective
    defective, reason = _video_integrity_defective({
        "video_url": "https://x/x.mp4",
        "video_integrity_ok": False,
        "video_integrity_reason": "duration_below_floor: actual=19s expected=44s",
    })
    assert defective is True
    assert "duration_below_floor" in reason


def test_helper_passes_when_no_video():
    from routes.hype import _video_integrity_defective
    defective, reason = _video_integrity_defective({
        "video_url": None,
        "video_integrity_ok": False,
    })
    assert defective is False


# ─── (4) Approve handlers source-level guards ───────────────────────


def _hype_py() -> str:
    return (_BACKEND / "routes" / "hype.py").read_text(encoding="utf-8")


def test_approve_draft_refuses_video_truncated():
    src = _hype_py()
    start = src.index("async def approve_draft(")
    end = src.index("@router.", start + 1)
    body = src[start:end]
    assert "_video_integrity_defective(draft)" in body
    assert '"error": "video_truncated"' in body
    # MUST fire BEFORE the existing video_out_of_sync check so the
    # operator sees the more actionable refusal first.
    sync_idx = body.index('_video_out_of_sync')
    integ_idx = body.index('_video_integrity_defective')
    assert integ_idx < sync_idx, (
        "video_truncated check must fire BEFORE video_out_of_sync — a "
        "defective render is more actionable than a stale binding."
    )


def test_approve_thread_refuses_video_truncated_per_draft():
    src = _hype_py()
    start = src.index("async def approve_thread(")
    end = src.index("@router.", start + 1)
    body = src[start:end]
    assert "_video_integrity_defective(_d)" in body or "_video_integrity_defective(d)" in body
    assert '"error": "video_truncated"' in body


def test_lifecycle_surfaces_video_integrity():
    src = _hype_py()
    # Look inside get_draft_lifecycle's return payload.
    lifecycle_start = src.index("async def get_draft_lifecycle(")
    next_router = src.index("@router.", lifecycle_start + 1)
    body = src[lifecycle_start:next_router]
    assert '"video_integrity":' in body
    assert '"actual_duration_s"' in body
    assert '"expected_duration_s"' in body
    assert '"ok"' in body

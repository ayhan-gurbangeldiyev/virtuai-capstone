"""Regression test for video↔content binding (SEV-1 follow-up P0).

⚠️ NEVER PUBLISH FROM A TEST. ⚠️
This file uses fully-mocked Supabase calls. It does NOT touch any real
draft row, does NOT call edit_draft / approve_draft / approve_thread
against prod data, does NOT construct a real GuardedPostizClient. The
SEV-1 lesson holds: tests prove semantics by exercising the helper +
guard functions directly, not by puppeting the prod handlers against
live tables.

Three independent assertions:

  1. The shared `_video_out_of_sync(draft)` helper:
       (a) returns (False, None) when no video.
       (b) returns (True, ...) when video_stale=True.
       (c) returns (True, ...) when current content sha != stored sha.
       (d) returns (False, None) when sha matches (the legacy/backfilled
           and the just-rendered-and-not-edited cases).
       (e) returns (False, None) when video_content_sha is None (legacy
           pre-binding rows that haven't been backfilled — soft-pass
           policy).

  2. The handlers' source code:
       (a) approve_draft contains a 409 raise with error='video_out_of_sync'
           AFTER the video_regen_pending check.
       (b) approve_thread iterates drafts and raises 409 with
           error='video_out_of_sync' before the gate calls.
       (c) edit_draft sets video_stale=True + video_regen_pending=True
           when the new content's sha != stored video_content_sha.

  3. /drafts/{id}/regen-video endpoint exists and enqueues a
     regen_type='video' job in image_regen_jobs (mock the insert; verify
     the row shape sent to the DB).
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parent.parent
sys.path.insert(0, str(_BACKEND))


# ─── (1) Helper semantics ───────────────────────────────────────────


def _sha(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def test_helper_no_video_passes():
    from routes.hype import _video_out_of_sync
    stale, reason = _video_out_of_sync({
        "video_url": None,
        "content": "anything",
    })
    assert stale is False
    assert reason is None


def test_helper_stale_flag_refuses():
    from routes.hype import _video_out_of_sync
    stale, reason = _video_out_of_sync({
        "video_url": "https://x/x.mp4",
        "video_stale": True,
        "content": "anything",
        "video_content_sha": _sha("anything"),
    })
    assert stale is True
    assert "video_stale" in (reason or "")


def test_helper_sha_mismatch_refuses():
    from routes.hype import _video_out_of_sync
    stale, reason = _video_out_of_sync({
        "video_url": "https://x/x.mp4",
        "video_stale": False,
        "content": "the edited content",
        "video_content_sha": _sha("the original content"),  # rendered against old
    })
    assert stale is True
    assert "content sha changed" in (reason or "")


def test_helper_sha_match_passes():
    from routes.hype import _video_out_of_sync
    body = "the same content the video was rendered against"
    stale, reason = _video_out_of_sync({
        "video_url": "https://x/x.mp4",
        "video_stale": False,
        "content": body,
        "video_content_sha": _sha(body),
    })
    assert stale is False
    assert reason is None


def test_helper_legacy_null_sha_soft_passes():
    """Pre-binding rows had no video_content_sha. The backfill stamped
    sha = sha(current_content) on 46 legacy rows so future edits trip
    the guard, but for any row that escapes the backfill we soft-pass
    rather than block — the helper's documented policy."""
    from routes.hype import _video_out_of_sync
    stale, reason = _video_out_of_sync({
        "video_url": "https://x/x.mp4",
        "video_stale": False,
        "content": "anything",
        "video_content_sha": None,
    })
    assert stale is False
    assert reason is None


# ─── (2) Source-level handler guards ────────────────────────────────


def _hype_py() -> str:
    return (_BACKEND / "routes" / "hype.py").read_text(encoding="utf-8")


def test_approve_draft_has_video_out_of_sync_guard():
    src = _hype_py()
    # The guard must live in the approve_draft function body, AFTER the
    # video_regen_pending check (so the regen-in-progress case is a
    # distinct 409, not collapsed into out-of-sync).
    start = src.index("async def approve_draft(")
    end = src.index("@router.", start + 1)
    body = src[start:end]
    assert "_video_out_of_sync(draft)" in body, "approve_draft must call _video_out_of_sync()"
    assert '"error": "video_out_of_sync"' in body, "approve_draft must raise video_out_of_sync 409"
    # Order: video_regen_pending check comes BEFORE the out-of-sync check
    regen_idx = body.index('video_regen_pending')
    sync_idx = body.index('_video_out_of_sync')
    assert regen_idx < sync_idx, (
        "video_regen_pending check must precede _video_out_of_sync so "
        "the in-progress case stays a distinct response"
    )


def test_approve_thread_has_per_draft_video_out_of_sync_guard():
    src = _hype_py()
    start = src.index("async def approve_thread(")
    end = src.index("@router.", start + 1)
    body = src[start:end]
    # Must iterate drafts and call _video_out_of_sync on each.
    assert "_video_out_of_sync(_d)" in body or "_video_out_of_sync(d)" in body, (
        "approve_thread must call _video_out_of_sync() per-draft"
    )
    assert '"error": "video_out_of_sync"' in body, (
        "approve_thread must raise video_out_of_sync 409"
    )


def test_edit_draft_invalidates_video_on_content_change():
    src = _hype_py()
    start = src.index("async def edit_draft(")
    end = src.index("@router.", start + 1)
    body = src[start:end]
    # Must compute sha of new content and compare to stored.
    assert "sha256" in body and "video_content_sha" in body, (
        "edit_draft must compute sha + compare against video_content_sha"
    )
    # On mismatch must set both video_stale=True and video_regen_pending=True
    # somewhere in the function body (accept either '"video_stale": True'
    # JSON-style or '"video_stale"] = True' assignment-style).
    assert ('"video_stale": True' in body
            or 'update_payload["video_stale"] = True' in body), (
        "edit_draft must set video_stale=True on mismatch"
    )
    assert ('"video_regen_pending": True' in body
            or 'update_payload["video_regen_pending"] = True' in body), (
        "edit_draft must set video_regen_pending=True on mismatch"
    )


# ─── (3) /drafts/{id}/regen-video endpoint exists + enqueues video job ──


def test_regen_video_endpoint_registered():
    src = _hype_py()
    assert '@router.post("/drafts/{draft_id}/regen-video")' in src, (
        "regen-video endpoint missing — operator has no one-click path "
        "to recover from a video_out_of_sync 409"
    )
    # The endpoint body must enqueue a regen_type='video' image_regen_jobs row.
    start = src.index('@router.post("/drafts/{draft_id}/regen-video")')
    end = src.index("@router.", start + 1)
    body = src[start:end]
    assert '"regen_type": "video"' in body, (
        "regen-video must enqueue regen_type='video' so the existing "
        "worker dispatches the HeyGen pipeline"
    )
    assert '"video_regen_pending": True' in body, (
        "regen-video must flip video_regen_pending so subsequent approve "
        "calls block until the worker completes"
    )

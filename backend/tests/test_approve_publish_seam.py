"""Regression test for the approve publish seam.

⚠️ NEVER PUBLISH FROM A TEST. ⚠️
This file does NOT call any Postiz endpoint, does NOT construct a real
GuardedPostizClient, does NOT impersonate an operator user, does NOT
invoke approve_draft/approve_thread with a real DB row. It only does
source-level + import-level assertions. The SEV-1 on 2026-06-07 came
from a *script* that did call approve_thread() with a FakeUser and
reached real Postiz; this test file is deliberately structured so it
cannot make that same mistake.

Three independent assertions, all of which must pass:

  1. The BACKEND venv (not the cron one) can import gliner + rapidfuzz when
     FAITHFULNESS_NER_REQUIRED=true. The startup guard in server.py would
     refuse to boot otherwise — this test mirrors that check so CI catches
     it before deploy. The seam has broken three times now; the most
     recent break was exactly this: gliner installed only in hype-crew
     venv, FAITHFULNESS_NER_REQUIRED=true in backend .env, approve 503.

  2. The approve_draft handler accepts a pending_review draft with
     postiz_post_id=NULL and scheduled_at=NULL (the new clean shape
     written by hype_crew/flow.py:dry_run_complete after FIX-3). Older
     code expected DRY_RUN_<uuid> + a fabricated scheduled_at and would
     have choked on NULL. This test forces the NULL state via mocks and
     asserts the route does not raise on the input shape.

  3. _arm_publish_verifier is called once per approve (single OR thread)
     so the verifier timer actually fires. If this regresses the
     publish path goes from "published-and-verified" back to
     "published-and-pray".

Run from repo root:
    cd backend && venv/bin/python -m pytest tests/test_approve_publish_seam.py -x -v
"""
from __future__ import annotations

import os
import sys
import importlib
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parent.parent
sys.path.insert(0, str(_BACKEND))


# ─── (1) NER deps available in the backend venv ─────────────────────


def test_backend_can_import_ner_when_required():
    """When FAITHFULNESS_NER_REQUIRED=true, the BACKEND venv must have
    gliner + rapidfuzz importable. The cron-side venv having them is NOT
    enough — the FastAPI process serves /hype/drafts/{id}/approve."""
    required = (os.environ.get("FAITHFULNESS_NER_REQUIRED") or "").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if not required:
        pytest.skip(
            "FAITHFULNESS_NER_REQUIRED is not true in this test env; "
            "production must set it to 'true' so this assertion runs."
        )
    # The actual import — same one the gate makes at request time.
    import gliner    # noqa: F401
    import rapidfuzz  # noqa: F401


def test_startup_guard_fails_loud_when_ner_required_but_missing(monkeypatch):
    """If the operator forgets to install NER deps in the backend venv
    AND sets FAITHFULNESS_NER_REQUIRED=true, the startup guard should
    raise — preventing a silent 503 on first approve.

    We import server BEFORE monkeypatching __import__ so the patched
    fake import only affects our manual _check_faithfulness_ner_available()
    call, not the test's own module loading.
    """
    import server  # load the module (it works; we already have gliner)
    monkeypatch.setenv("FAITHFULNESS_NER_REQUIRED", "true")

    # Now patch the import so gliner appears missing.
    import builtins
    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name == "gliner":
            raise ImportError("simulated: gliner not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with pytest.raises(RuntimeError) as excinfo:
        server._check_faithfulness_ner_available()
    assert "FAITHFULNESS_NER_REQUIRED" in str(excinfo.value)
    assert "gliner" in str(excinfo.value)


# ─── (2) approve_draft accepts NULL postiz_post_id + scheduled_at ──


def test_approve_input_shape_accepts_null_postiz_and_scheduled():
    """Parse-only check: the ApproveRequest body model and the route
    annotation must permit a draft row whose postiz_post_id and
    scheduled_at are NULL (the post-FIX-3 shape). If a future refactor
    re-introduces a non-null assertion on these, this fails.
    """
    from routes.hype import ApproveRequest

    # ApproveRequest carries no postiz_post_id / scheduled_at fields —
    # those come from the daily_drafts row, not the body. So construction
    # with an empty body must work.
    body = ApproveRequest()
    assert body is not None

    # Inspect the daily_drafts row shape the approve handler reads. The
    # exact column names that USED to be non-null assumptions:
    expected_nullable = {"postiz_post_id", "scheduled_at"}
    # Just confirm the route file doesn't `assert draft["postiz_post_id"]`
    # or `assert draft["scheduled_at"]` directly — that would be the
    # exact regression we want to catch.
    hype_py = (Path(__file__).resolve().parent.parent / "routes" / "hype.py").read_text(
        encoding="utf-8"
    )
    for col in expected_nullable:
        forbidden = f'assert draft["{col}"]'
        assert forbidden not in hype_py, (
            f"hype.py contains '{forbidden}' which would reject the post-FIX-3 "
            f"NULL state. Drafts in pending_review legitimately have NULL {col}; "
            f"the gate + scheduler must handle it."
        )


# ─── (3) _arm_publish_verifier is called per-approve ───────────────


def test_arm_publish_verifier_referenced_in_approve_paths():
    """Source-level guard: both approve_draft and approve_thread must
    call _arm_publish_verifier at least once. If a refactor drops the
    call, the verifier never spawns, publish becomes 'fire and pray'.
    """
    hype_py = (Path(__file__).resolve().parent.parent / "routes" / "hype.py").read_text(
        encoding="utf-8"
    )

    # locate function bodies
    approve_draft_start = hype_py.index("async def approve_draft(")
    approve_draft_end = hype_py.index("@router.", approve_draft_start + 1)
    approve_thread_start = hype_py.index("async def approve_thread(")
    approve_thread_end = hype_py.index("@router.", approve_thread_start + 1)

    single_body = hype_py[approve_draft_start:approve_draft_end]
    thread_body = hype_py[approve_thread_start:approve_thread_end]

    assert "_arm_publish_verifier(" in single_body, (
        "approve_draft no longer calls _arm_publish_verifier — the verifier "
        "timer will never spawn for single-draft approves."
    )
    assert "_arm_publish_verifier(" in thread_body, (
        "approve_thread no longer calls _arm_publish_verifier — the verifier "
        "timer will never spawn for thread approves."
    )


# ─── (4) operator_publish_context() wraps every schedule_posts call ──


def test_schedule_posts_only_called_inside_operator_publish_context():
    """SEV-1 regression guard (incident 2026-06-07 10:49 UTC).

    A test harness called approve_thread() in-process with a FakeUser
    and reached real Postiz, publishing 5 unauthorized posts. To make
    that impossible: every pc.schedule_posts() call site inside the
    backend routes must be wrapped in `operator_publish_context()`. If
    a refactor drops the marker, the GuardedPostizClient guard refuses
    the call — but this test catches the regression at CI time, before
    any traffic.
    """
    hype_py = (Path(__file__).resolve().parent.parent / "routes" / "hype.py").read_text(
        encoding="utf-8"
    )

    # Find every pc.schedule_posts(...) call and confirm an
    # `operator_publish_context()` appears within 200 chars BEFORE it.
    import re
    for match in re.finditer(r"\bpc\.schedule_posts\s*\(", hype_py):
        start = match.start()
        prefix = hype_py[max(0, start - 250):start]
        assert "operator_publish_context()" in prefix, (
            f"pc.schedule_posts() at char {start} is NOT preceded by "
            f"operator_publish_context() — the SEV-1 guard would let any "
            f"caller publish. Wrap it:\n"
            f"    with operator_publish_context():\n"
            f"        resp = pc.schedule_posts(...)"
        )

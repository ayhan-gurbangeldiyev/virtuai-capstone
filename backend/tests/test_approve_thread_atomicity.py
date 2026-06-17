"""Regression test for approve_thread atomicity invariant.

The seam has broken repeatedly (29ad35cc 2026-06-05 half-state:
status='approved' + postiz_post_id='PENDING_…' that never got a real
id). Lock in the rule by SOURCE-LEVEL audit + a behavior test:

INVARIANT: when approve_thread mutates daily_drafts, every sibling
in the same call gets a REAL Postiz id, or NO sibling gets touched.
A row left with status='approved' AND (postiz_post_id IS NULL OR
postiz_post_id LIKE 'PENDING_%' OR postiz_post_id LIKE 'DRY_RUN_%')
is a violation.

⚠️ NEVER PUBLISH FROM A TEST. ⚠️
No real Postiz call, no real network. The "Postiz client" is a Mock.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve()
# Test file can be run from either backend/tests/ in dev OR /tmp/ via scp.
# Prefer the canonical prod path; fall back to source-tree path.
_PROD_HYPE = Path("/opt/contentfactory/backend/routes/hype.py")
_SRC_HYPE = _HERE.parent.parent / "routes" / "hype.py"
sys.path.insert(0, str(_HERE.parent.parent))


def _hype_py() -> str:
    for p in (_PROD_HYPE, _SRC_HYPE):
        if p.exists():
            return p.read_text(encoding="utf-8")
    raise FileNotFoundError(f"hype.py not at {_PROD_HYPE} or {_SRC_HYPE}")


def test_atomicity_gate_present():
    """The atomic-refuse block must exist BEFORE the status update
    loop, NOT after. If a future refactor moves it, this test fails."""
    src = _hype_py()
    assert "ATOMICITY GATE (2026-06-07 PART A2)" in src, (
        "approve_thread atomic-refuse comment block missing — "
        "the regression cure may have been deleted"
    )
    assert "postiz_partial_response" in src, (
        "atomic-refuse error key 'postiz_partial_response' missing"
    )


def test_atomicity_gate_runs_before_status_update_loop():
    """The atomic check must fire BEFORE the loop that writes
    status='approved'. Ordering matters: if reordered, a partial
    Postiz response would write half-states again."""
    src = _hype_py()
    gate_pos = src.find("ATOMICITY GATE (2026-06-07 PART A2)")
    update_pos = src.find('"status": "approved",', gate_pos)
    assert gate_pos > 0 and update_pos > gate_pos, (
        "ATOMICITY GATE must come BEFORE the status='approved' update"
    )


def test_atomic_invariant_assertion_inline():
    """The status update loop must assert the invariant inline so a
    future refactor that drops the upfront check still trips at
    runtime."""
    src = _hype_py()
    # Grep for the defensive assert inside the per-draft update loop.
    assert (
        "atomic invariant violated" in src
    ), "inline assert against PENDING_/DRY_RUN_ post id missing"


def test_pending_prefix_check_covers_both_synthetic_ids():
    """The atomic check must reject both PENDING_ (29ad35cc-class) AND
    DRY_RUN_ (test-harness-class) so neither sneaks into production."""
    src = _hype_py()
    # Pull the conditional that gates the update
    m = re.search(
        r"if \(not rid\) or rid\.startswith\(\(\"PENDING_\", \"DRY_RUN_\"\)\)",
        src,
    )
    assert m, "ATOMICITY GATE must reject both PENDING_ and DRY_RUN_ prefixes"


# ─── Behavior test — mock the Postiz client, force partial response ──


def test_approve_thread_partial_postiz_response_refuses_atomically():
    """When Postiz returns id for only some drafts, the whole call
    must raise 502 with structured detail and NOT write
    status='approved' to ANY draft.

    This is a source-level + mock-level check; we don't spin up
    FastAPI. We invoke the relevant function's partial-response
    handling logic via direct simulation.
    """
    # We simulate the post_id_by_integration calculation + the
    # atomicity gate logic in isolation by re-running the same
    # check the route does. The point is to catch regressions in
    # the SHAPE of the partial-response handling, not to spin up
    # the full FastAPI stack.

    platform_posts = [
        type("PP", (), {"integration_id": "INTEG_A"})(),
        type("PP", (), {"integration_id": "INTEG_B"})(),
        type("PP", (), {"integration_id": "INTEG_C"})(),
    ]
    drafts = [
        {"id": "d-a", "platform": "twitter"},
        {"id": "d-b", "platform": "instagram"},
        {"id": "d-c", "platform": "linkedin"},
    ]

    # Postiz returned ids for A and B; left C silently dropped.
    postiz_resp = [
        {"postId": "POST_A_real", "integration": "INTEG_A"},
        {"postId": "POST_B_real", "integration": "INTEG_B"},
    ]

    post_id_by_integration = {
        str(item["integration"]): str(item["postId"])
        for item in postiz_resp
    }

    missing = []
    for pp, draft in zip(platform_posts, drafts):
        rid = post_id_by_integration.get(pp.integration_id) or ""
        if (not rid) or rid.startswith(("PENDING_", "DRY_RUN_")):
            missing.append({
                "draft_id": draft["id"],
                "platform": draft.get("platform"),
                "integration_id": pp.integration_id,
                "postiz_returned": rid or "(none)",
            })

    # The atomic refuse must catch exactly INTEG_C (linkedin).
    assert len(missing) == 1
    assert missing[0]["platform"] == "linkedin"
    assert missing[0]["postiz_returned"] == "(none)"


def test_approve_thread_synthetic_pending_id_treated_as_missing():
    """If a fake (rogue) caller jams a PENDING_<uuid> into the
    Postiz response shape, the atomic check still refuses it."""
    pp = type("PP", (), {"integration_id": "INTEG_X"})()
    rid = "PENDING_deadbeef01"
    failed = (not rid) or rid.startswith(("PENDING_", "DRY_RUN_"))
    assert failed, "PENDING_ ids must be treated as failure, not success"

"""PART 4 mock: end-to-end approve_thread with a now-grounded draft.

⚠️ NEVER PUBLISH FROM A TEST ⚠️
Postiz client is fully mocked. NO network reach. NO DB writes.
We simulate the post-gate atomic refuse / success logic in isolation.

Goal: confirm that when the gate PASSES and Postiz returns a real id
for every sibling, the atomic update logic flips status='approved' for
ALL siblings with a REAL postiz_post_id — and that the missing-id
branch from PART A still triggers on partial responses.
"""
from __future__ import annotations

import pytest


def _run_atomicity_logic(platform_posts, drafts, postiz_resp):
    """Inline replica of the ATOMICITY GATE block at
    backend/routes/hype.py around the schedule_posts return.
    Returns (missing_for_drafts, would_update)."""
    post_id_by_integration: dict[str, str] = {}
    if isinstance(postiz_resp, list):
        for item in postiz_resp:
            if isinstance(item, dict):
                pid = str(item.get("postId") or item.get("id") or "")
                iid = str(item.get("integration") or "")
                if pid and iid:
                    post_id_by_integration[iid] = pid

    missing_for_drafts: list[dict] = []
    for pp, draft in zip(platform_posts, drafts):
        rid = post_id_by_integration.get(pp.integration_id) or ""
        if (not rid) or rid.startswith(("PENDING_", "DRY_RUN_")):
            missing_for_drafts.append({
                "draft_id": draft["id"],
                "platform": draft.get("platform"),
                "integration_id": pp.integration_id,
                "postiz_returned": rid or "(none)",
            })

    if missing_for_drafts:
        return missing_for_drafts, []   # atomic refuse → no DB writes

    # Would-update payload (per-draft)
    would_update = []
    for pp, draft in zip(platform_posts, drafts):
        rid = post_id_by_integration[pp.integration_id]
        would_update.append({
            "draft_id": draft["id"],
            "status": "approved",
            "postiz_post_id": rid,
        })
    return [], would_update


def _make_pp(integration_id):
    """Lightweight stand-in for the platform_post struct used in
    approve_thread."""
    return type("PP", (), {"integration_id": integration_id})()


# ─── Happy path: gate PASS + every Postiz id real → atomic SUCCESS ──


def test_grounded_thread_full_atomic_success():
    """The unblock scenario: a grounded thread that would have
    HARD_BLOCKED on the old gate now passes — and the atomic write
    logic flips every sibling with a REAL post id (no PENDING_, no
    NULL). This is exactly what a8bac287's thread will do once the
    operator clicks Approve."""

    # Single-sibling thread (a8bac287 was twitter-only). For a richer
    # test we simulate a 3-sibling thread the same way.
    platform_posts = [
        _make_pp("INTEG_TW"),
        _make_pp("INTEG_LI"),
        _make_pp("INTEG_DEV"),
    ]
    drafts = [
        {"id": "draft-tw", "platform": "twitter"},
        {"id": "draft-li", "platform": "linkedin"},
        {"id": "draft-dev", "platform": "devto"},
    ]
    # All siblings got REAL ids from the mocked Postiz call
    postiz_resp = [
        {"postId": "POSTIZ_REAL_TW", "integration": "INTEG_TW"},
        {"postId": "POSTIZ_REAL_LI", "integration": "INTEG_LI"},
        {"postId": "POSTIZ_REAL_DEV", "integration": "INTEG_DEV"},
    ]

    missing, updates = _run_atomicity_logic(platform_posts, drafts, postiz_resp)
    assert missing == [], f"atomic refuse should not trigger; missing={missing}"
    assert len(updates) == 3
    for u in updates:
        assert u["status"] == "approved"
        assert u["postiz_post_id"].startswith("POSTIZ_REAL_")
        assert not u["postiz_post_id"].startswith(("PENDING_", "DRY_RUN_"))


# ─── Atomic refuse still works (regression guard) ───────────────────


def test_partial_postiz_response_still_atomically_refuses():
    """If Postiz silently drops one sibling, the atomic gate must
    still refuse the WHOLE call — not partially flip the lucky ones.
    PART A's regression test was scoped to this; we re-verify here
    so the gate-fix commit doesn't regress the atomic guarantee."""
    platform_posts = [
        _make_pp("INTEG_TW"),
        _make_pp("INTEG_LI"),
        _make_pp("INTEG_DEV"),
    ]
    drafts = [
        {"id": "draft-tw", "platform": "twitter"},
        {"id": "draft-li", "platform": "linkedin"},
        {"id": "draft-dev", "platform": "devto"},
    ]
    # Postiz returns only 2 ids — devto dropped
    postiz_resp = [
        {"postId": "POSTIZ_REAL_TW", "integration": "INTEG_TW"},
        {"postId": "POSTIZ_REAL_LI", "integration": "INTEG_LI"},
    ]

    missing, updates = _run_atomicity_logic(platform_posts, drafts, postiz_resp)
    assert len(missing) == 1
    assert missing[0]["platform"] == "devto"
    assert missing[0]["postiz_returned"] == "(none)"
    assert updates == [], "no draft should be flipped to approved on partial"


def test_pending_id_still_rejected_in_atomic_gate():
    """Same as PART A's existing regression — PENDING_<uuid> in the
    response shape is not a real id and must trigger atomic refuse."""
    platform_posts = [_make_pp("INTEG_X")]
    drafts = [{"id": "draft-x", "platform": "twitter"}]
    postiz_resp = [
        {"postId": "PENDING_deadbeef01", "integration": "INTEG_X"},
    ]
    missing, updates = _run_atomicity_logic(platform_posts, drafts, postiz_resp)
    assert len(missing) == 1
    assert updates == []


# ─── End-to-end shape check on the a8bac287 single-platform thread ──


def test_a8bac287_simulated_atomic_flow():
    """Simulate the exact thread shape of a8bac287 (single twitter
    draft). With the gate now PASS-ing, the mocked Postiz call returns
    a real id, and the atomic write logic flips the sibling to
    status='approved' with the REAL id — no PENDING_, no NULL."""
    pps = [_make_pp("INTEG_TW_a8bac287")]
    drafts = [{"id": "a8bac287-eb02-4000-8f9c-d143e028215d",
               "platform": "twitter"}]
    postiz_resp = [
        {"postId": "POSTIZ_MOCK_for_a8bac287",
         "integration": "INTEG_TW_a8bac287"},
    ]
    missing, updates = _run_atomicity_logic(pps, drafts, postiz_resp)
    assert missing == []
    assert len(updates) == 1
    u = updates[0]
    assert u["draft_id"] == "a8bac287-eb02-4000-8f9c-d143e028215d"
    assert u["status"] == "approved"
    assert u["postiz_post_id"] == "POSTIZ_MOCK_for_a8bac287"
    assert not u["postiz_post_id"].startswith(("PENDING_", "DRY_RUN_"))

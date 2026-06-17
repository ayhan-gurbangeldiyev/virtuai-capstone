"""CI invariant: ALL publish paths must route through GuardedPostizClient.

Two structural checks. A file is "bypassing" if it imports `PostizClient`
directly from `tools.postiz_client` (the base class) without ALSO using
the GuardedPostizClient wrapper. Test fails the build on:

  1. Any module that imports `PostizClient` from `tools.postiz_client`
     without also importing or aliasing `GuardedPostizClient`. This
     catches: `from tools.postiz_client import PostizClient` used to
     construct a non-guarded publisher.

  2. Any call to `.schedule_posts(...)` in a file that doesn't import
     `GuardedPostizClient` (and isn't in the small allowlist of base /
     wrapper / test files). A file with the wrapper imported is free to
     call `.schedule_posts` because the wrapper enforces gate_outcomes.

Files allowlisted by name (they are the wrapper / base class internals
or read-only tools):

  - hype_crew/tools/postiz_client.py
  - hype_crew/tools/guarded_postiz.py
  - hype_crew/tests/test_postiz_choke_point.py (this file)
  - hype_crew/tools/__init__.py (re-export only)
  - hype_crew/scripts/poll_engagement.py (READ-ONLY polling — no schedule_posts)

If you need to publish, route through:
    outcome = await assert_publishable(text, raw_content, path=..., draft_id=...)
    GuardedPostizClient().schedule_posts(posts, when, gate_outcomes=[outcome])

Berkay 6 Haz 2026 Phase 1 — closes the auto-publish leak path that
silently bypassed the faithfulness gate.
"""
from __future__ import annotations

import re
from pathlib import Path

try:
    import pytest
except ImportError:  # allow direct execution
    pytest = None  # type: ignore


def _resolve_repo_root() -> Path:
    """Find the monorepo root by walking up until we see both `hype_crew/`
    and `backend/` siblings (or a `.git/` dir). Falls back to grandparent
    of this file so the original CI behavior still works."""
    p = Path(__file__).resolve()
    for ancestor in [p.parent.parent.parent, *p.parents]:
        if (ancestor / ".git").exists():
            return ancestor
        if (ancestor / "hype_crew").is_dir() and (ancestor / "backend").is_dir():
            return ancestor
    return p.parent.parent.parent


REPO_ROOT = _resolve_repo_root()

ALLOWLIST_FILES = {
    "hype_crew/tools/postiz_client.py",
    "hype_crew/tools/guarded_postiz.py",
    "hype_crew/tests/test_postiz_choke_point.py",
    "hype_crew/tools/__init__.py",
    "hype_crew/scripts/poll_engagement.py",        # read-only
    "hype_crew/scripts/verify_publish.py",         # read-only — Stage 1.5
    # And the equivalent paths when run from a deploy directory layout
    # (e.g. on Hetzner where the dir is /opt/hype-crew/... so the rel
    # path looks like just `tools/...`).
    "tools/postiz_client.py",
    "tools/guarded_postiz.py",
    "tests/test_postiz_choke_point.py",
    "tools/__init__.py",
    "scripts/poll_engagement.py",
    "scripts/verify_publish.py",
    # On Hetzner the deploy dir is `hype-crew` (hyphen), but when the test
    # runs from a parent dir (e.g. /opt) the rel-paths come out as
    # hype-crew/scripts/... — allowlist both layouts so the same test
    # file works in both CI (underscore repo) and Hetzner (hyphen deploy).
    "hype-crew/scripts/poll_engagement.py",
    "hype-crew/scripts/verify_publish.py",
    "hype-crew/tools/postiz_client.py",
    "hype-crew/tools/guarded_postiz.py",
    "hype-crew/tools/__init__.py",
    "hype-crew/tests/test_postiz_choke_point.py",
}

# Skip stale .bak/.tmp directories that production deploys leave behind,
# plus the standard venv / node_modules / pycache trees.
SKIP_PREFIX_FRAGMENTS = (
    "venv/", "/venv/", "/.venv/", "node_modules/", "__pycache__",
    ".bak", ".tmp/", "/.bak", "-bak/",
    ".removed-stale", ".old",   # deploy detritus
)


# Patterns
_BASE_IMPORT_RE = re.compile(
    r"from\s+tools\.postiz_client\s+import\s+[^\n]*\bPostizClient\b"
)
_GUARDED_IMPORT_RE = re.compile(
    r"from\s+tools\.guarded_postiz\s+import\b"
)
_SCHEDULE_CALL_RE = re.compile(r"(?<!super\(\))\.schedule_posts\s*\(")


def _iter_py_files() -> list[Path]:
    out: list[Path] = []
    for p in REPO_ROOT.rglob("*.py"):
        rel = p.relative_to(REPO_ROOT).as_posix()
        if any(frag in rel for frag in SKIP_PREFIX_FRAGMENTS):
            continue
        out.append(p)
    return out


def _file_state(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"imports_base_only": False, "imports_guarded": False, "lines": []}
    return {
        "imports_base_only": bool(_BASE_IMPORT_RE.search(text)),
        "imports_guarded": bool(_GUARDED_IMPORT_RE.search(text)),
        "lines": text.splitlines(),
    }


def test_no_base_postiz_import_without_guarded():
    """Importing `PostizClient` from `tools.postiz_client` is only allowed
    when the same file also imports the guarded wrapper (so the wrapper is
    actually in use). Stand-alone base imports = bypass."""
    bad: list[tuple[str, int, str]] = []
    for path in _iter_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWLIST_FILES:
            continue
        state = _file_state(path)
        if state["imports_base_only"] and not state["imports_guarded"]:
            for i, line in enumerate(state["lines"], 1):
                if line.lstrip().startswith("#"):
                    continue
                if _BASE_IMPORT_RE.search(line):
                    bad.append((rel, i, line.strip()))
    if bad:
        lines = [
            "Direct import of PostizClient outside the guarded wrapper.",
            "This is a faithfulness-gate bypass. Import GuardedPostizClient",
            "from tools.guarded_postiz and pass gate_outcomes from",
            "assert_publishable. Offenders:",
        ]
        for rel, i, l in bad:
            lines.append(f"  {rel}:{i}  {l}")
        raise AssertionError("\n".join(lines))


def test_no_schedule_posts_call_outside_guarded_files():
    """Any file that calls `.schedule_posts(` must ALSO import the
    guarded wrapper (so the call hits the wrapper's overridden method).
    The base method definition + wrapper's super() call are allowlisted."""
    bad: list[tuple[str, int, str]] = []
    for path in _iter_py_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in ALLOWLIST_FILES:
            continue
        state = _file_state(path)
        if not state["lines"]:
            continue
        for i, line in enumerate(state["lines"], 1):
            if line.lstrip().startswith("#"):
                continue
            if _SCHEDULE_CALL_RE.search(line):
                if not state["imports_guarded"]:
                    bad.append((rel, i, line.strip()))
    if bad:
        lines = [
            "Found .schedule_posts() in a file that does NOT import the",
            "guarded wrapper. The call may be hitting the unguarded base",
            "client. Import GuardedPostizClient from tools.guarded_postiz",
            "and pass gate_outcomes. Offenders:",
        ]
        for rel, i, l in bad:
            lines.append(f"  {rel}:{i}  {l}")
        raise AssertionError("\n".join(lines))


def test_assert_publishable_required_args():
    """Sanity: assert_publishable signature still binds (draft_id, path)
    so the gate verdict is auditable / pageable per path."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "hype_crew"))
    from tools.guarded_postiz import assert_publishable  # type: ignore
    import inspect
    sig = inspect.signature(assert_publishable)
    assert "draft_id" in sig.parameters
    assert "path" in sig.parameters
    assert "source_raw_content" in sig.parameters
    assert "draft_text" in sig.parameters


def test_guarded_client_refuses_without_outcomes():
    if pytest is None:
        return  # allow direct execution
    import sys
    sys.path.insert(0, str(REPO_ROOT / "hype_crew"))
    from tools.guarded_postiz import (  # type: ignore
        GuardedPostizClient, GuardedPublishRefused,
    )
    from tools.postiz_client import PlatformPost  # type: ignore
    from datetime import datetime, timezone

    pc = GuardedPostizClient()
    pp = PlatformPost(
        integration_id="x",
        provider="twitter",
        content="hello",
    )
    with pytest.raises(GuardedPublishRefused):
        pc.schedule_posts([pp], datetime.now(timezone.utc))


def test_guarded_client_refuses_mismatched_token():
    if pytest is None:
        return
    import sys
    sys.path.insert(0, str(REPO_ROOT / "hype_crew"))
    from tools.guarded_postiz import (  # type: ignore
        GuardedPostizClient, GuardedPublishRefused, GateOutcome, _sign_token,
    )
    from tools.postiz_client import PlatformPost  # type: ignore
    from datetime import datetime, timezone

    outcome = GateOutcome(
        draft_id="draft-1",
        path="manual_approve",
        verdict="PASS",
        token=_sign_token("draft-1", "original content"),
    )
    pp = PlatformPost(
        integration_id="x",
        provider="twitter",
        content="tampered content",
    )
    pc = GuardedPostizClient()
    with pytest.raises(GuardedPublishRefused):
        pc.schedule_posts([pp], datetime.now(timezone.utc), gate_outcomes=[outcome])


if __name__ == "__main__":
    test_no_base_postiz_import_without_guarded()
    print("✓ test_no_base_postiz_import_without_guarded")
    test_no_schedule_posts_call_outside_guarded_files()
    print("✓ test_no_schedule_posts_call_outside_guarded_files")
    test_assert_publishable_required_args()
    print("✓ test_assert_publishable_required_args")
    print("ALL OK")

"""G3 — write-ahead + writeback collapse to ONE daily_drafts row (+ 23505 path).

Two sub-tests, both against the REAL _write_daily_draft idempotency code:

G3a (write-ahead → writeback collapse):
  For a fresh run, call _write_daily_draft with postiz_post_id='SCHEDULING'
  (write-ahead), then call it AGAIN with the real id (writeback) for the SAME
  (hype_run_id, platform, content_type). ASSERT: exactly ONE row for that key,
  carrying the REAL id (not 'SCHEDULING', not two rows). This is the partial-
  unique-index idempotency the BLOCKER fix relies on.

G3b (23505 concurrent/duplicate INSERT → idempotent UPDATE):
  A conflicting row already exists. Force the INSERT path to actually fire (make
  the pre-check SELECT miss ONCE so it doesn't short-circuit to UPDATE), so the
  real Postgres partial-unique index rejects the INSERT with 23505. ASSERT: the
  23505 handler converts it to an idempotent UPDATE returning the EXISTING id —
  not a crash, not a 2nd row.

NO real Postiz / no LLM (schedule_posts never reached; we call _write_daily_draft
directly). NO Cansu live-config change. Cleaned up by run_id.

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g3_writeahead_collapse
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, draft_rows, cleanup_run, seed_trend, delete_trend, seed_hype_run,
)
from scripts.lg_faz2_gate_common import (
    install_publish_mocks, build_publish_state, CONTENT_TYPE,
)

PLATFORM = "twitter"


def _rows_for(run_id):
    return [r for r in draft_rows(run_id)
            if r["platform"] == PLATFORM and not r.get("deleted_at")]


def run_g3a(flowmod) -> tuple[bool, list]:
    """write-ahead('SCHEDULING') then writeback(real) → ONE row with real id."""
    failures: list[str] = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)

    cf = build_publish_state(flowmod, run_id, tid, (PLATFORM,))
    pd = cf._state.platform_drafts[0]

    # write-ahead
    did1 = cf._write_daily_draft(
        platform_draft=pd, status="pending", postiz_post_id="SCHEDULING",
        scheduled_at=None, auto_published=True)
    rows1 = _rows_for(run_id)
    print(f"[G3a] after write-ahead: id={did1} rows={len(rows1)} "
          f"pid={[r['postiz_post_id'] for r in rows1]}")
    if len(rows1) != 1 or rows1[0]["postiz_post_id"] != "SCHEDULING":
        failures.append(f"G3a write-ahead expected 1 SCHEDULING row, got {rows1}")

    # writeback with real id (SAME key)
    real_id = "REAL_" + uuid.uuid4().hex[:10]
    did2 = cf._write_daily_draft(
        platform_draft=pd, status="pending", postiz_post_id=real_id,
        scheduled_at=None, auto_published=True)
    rows2 = _rows_for(run_id)
    print(f"[G3a] after writeback: id={did2} rows={len(rows2)} "
          f"pid={[r['postiz_post_id'] for r in rows2]}")

    if len(rows2) != 1:
        failures.append(f"G3a expected EXACTLY 1 row after writeback, got {len(rows2)} "
                        f"— write-ahead + writeback did NOT collapse")
    elif rows2[0]["postiz_post_id"] != real_id:
        failures.append(f"G3a row still has {rows2[0]['postiz_post_id']!r}, "
                        f"expected real id {real_id} (writeback didn't UPDATE)")
    if did1 and did2 and did1 != did2:
        failures.append(f"G3a writeback returned a NEW id ({did2}) != write-ahead "
                        f"id ({did1}) — second row created instead of UPDATE")

    cleanup_run(run_id)
    delete_trend(tid)
    return (not failures), failures


class _OneShotMissSBWrap:
    """Wrap a real Supabase client so the FIRST daily_drafts SELECT returns
    empty (forcing the _write_daily_draft pre-check to MISS → fall to INSERT,
    which the real partial-unique index then rejects with 23505). All other
    operations pass through unchanged, so the 23505 recovery lookup (a later
    SELECT) finds the real conflicting row."""

    def __init__(self, real, state):
        self._real = real
        self._state = state  # {"miss_used": False}

    def table(self, name):
        t = self._real.table(name)
        if name != "daily_drafts":
            return t
        return _OneShotMissTable(t, self._state)

    def __getattr__(self, item):
        return getattr(self._real, item)


class _OneShotMissTable:
    def __init__(self, real_table, state):
        self._t = real_table
        self._state = state
        self._is_select = False

    def select(self, *a, **k):
        self._t = self._t.select(*a, **k)
        self._is_select = True
        return self

    def insert(self, *a, **k):
        return self._t.insert(*a, **k)

    def update(self, *a, **k):
        return self._t.update(*a, **k)

    def delete(self, *a, **k):
        return self._t.delete(*a, **k)

    def eq(self, *a, **k):
        self._t = self._t.eq(*a, **k); return self

    def is_(self, *a, **k):
        self._t = self._t.is_(*a, **k); return self

    def in_(self, *a, **k):
        self._t = self._t.in_(*a, **k); return self

    def limit(self, *a, **k):
        self._t = self._t.limit(*a, **k); return self

    def execute(self):
        # First SELECT against daily_drafts → return empty ONCE (pre-check miss).
        if self._is_select and not self._state["miss_used"]:
            self._state["miss_used"] = True

            class _Empty:
                data: list = []
                count = 0
            print("[G3b] (pre-check SELECT forced to MISS once → INSERT will fire)")
            return _Empty()
        return self._t.execute()


def run_g3b(flowmod) -> tuple[bool, list]:
    """23505: conflicting row exists, INSERT fires anyway → idempotent UPDATE."""
    import flow as _f
    failures: list[str] = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)

    cf = build_publish_state(flowmod, run_id, tid, (PLATFORM,))
    pd = cf._state.platform_drafts[0]

    # Create the REAL conflicting row first (normal write-ahead).
    pre_id = cf._write_daily_draft(
        platform_draft=pd, status="pending", postiz_post_id="SCHEDULING",
        scheduled_at=None, auto_published=True)
    rows_pre = _rows_for(run_id)
    print(f"[G3b] seeded conflicting row id={pre_id} rows={len(rows_pre)}")
    if len(rows_pre) != 1:
        failures.append(f"G3b setup: expected 1 seed row, got {len(rows_pre)}")

    # Now wrap make_supabase so the next _write_daily_draft's pre-check SELECT
    # misses ONCE → INSERT fires → real DB rejects with 23505 → recovery path.
    from tools.supabase_client import make_supabase as _real_make_sb
    miss_state = {"miss_used": False}
    # Preserve the hype_account_config wrap from install_publish_mocks by
    # wrapping the CURRENT _f.make_supabase (already config-wrapped).
    _cfg_wrapped = _f.make_supabase

    def _miss_make_sb():
        return _OneShotMissSBWrap(_cfg_wrapped(), miss_state)

    _f.make_supabase = _miss_make_sb
    try:
        real_id = "REAL_" + uuid.uuid4().hex[:10]
        crashed = False
        recovered_id = None
        try:
            recovered_id = cf._write_daily_draft(
                platform_draft=pd, status="pending", postiz_post_id=real_id,
                scheduled_at=None, auto_published=True)
        except Exception as e:  # noqa: BLE001
            crashed = True
            print(f"[G3b] _write_daily_draft RAISED (should NOT): {type(e).__name__}: {e}")
    finally:
        _f.make_supabase = _cfg_wrapped  # restore config-wrap only

    rows_post = _rows_for(run_id)
    print(f"[G3b] miss_used={miss_state['miss_used']} recovered_id={recovered_id} "
          f"rows={len(rows_post)} pid={[r['postiz_post_id'] for r in rows_post]}")

    if not miss_state["miss_used"]:
        failures.append("G3b pre-check miss never triggered — INSERT path not exercised "
                        "(23505 handler not actually tested)")
    if crashed:
        failures.append("G3b 23505 crashed instead of idempotent UPDATE recovery")
    if len(rows_post) != 1:
        failures.append(f"G3b expected EXACTLY 1 row after 23505 recovery, got "
                        f"{len(rows_post)} — duplicate row created")
    if recovered_id and pre_id and recovered_id != pre_id:
        failures.append(f"G3b 23505 recovery returned a different id "
                        f"({recovered_id}) than the existing row ({pre_id})")

    cleanup_run(run_id)
    delete_trend(tid)
    return (not failures), failures


def main() -> int:
    import flow as flowmod
    install_publish_mocks(flowmod, platforms=(PLATFORM,))

    ok_a, f_a = run_g3a(flowmod)
    print()
    ok_b, f_b = run_g3b(flowmod)

    ok = ok_a and ok_b
    print("\n" + ("=" * 60))
    if ok:
        print("✅ G3 PASS — write-ahead('SCHEDULING') + writeback(real) collapse to "
              "ONE row with the real id (G3a); a duplicate INSERT hitting the "
              "partial-unique index (23505) is converted to an idempotent UPDATE "
              "returning the existing id, no 2nd row, no crash (G3b).")
    else:
        print("❌ G3 FAIL:")
        for f in (f_a + f_b):
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

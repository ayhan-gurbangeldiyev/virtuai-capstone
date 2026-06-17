"""G2 — mid-node crash between schedule_posts() and writeback → resume does NOT
double-post. The real-world version of G1 and the CORE of the BLOCKER fix.

Real scenario: node_publish wraps the WHOLE publish_to_drafts method; LangGraph
only checkpoints AFTER the node returns. So a crash between the Postiz
schedule_posts() call and the writeback of the real postiz_post_id leaves the
daily_drafts row at the 'SCHEDULING' write-ahead sentinel. On resume, the WHOLE
node re-runs publish_to_drafts → it must see the SCHEDULING orphan and fail-closed
(NOT re-POST).

Simulation:
  CRASH RUN  — drive publish_to_drafts with schedule_posts spied (records + returns
    fake ids). The real-id writeback step (_write_daily_draft called with a real
    postiz_post_id, AFTER schedule_posts returned) is patched to RAISE, so the row
    stays at 'SCHEDULING'. The exception propagates out of publish_to_drafts exactly
    as it would out of node_publish (no checkpoint of the writeback).
  RESUME RUN — re-invoke publish_to_drafts for the SAME run_id (== what node_publish
    does on resume; re-runs the whole method).

ASSERT: schedule_posts call count for the scheduled platform == 1 across
crash+resume (NOT 2). Resume hit the SCHEDULING orphan → fail-closed, did NOT
re-POST. Plus: resume run is 'failed' + CRITICAL alert.

NO real Postiz, NO paid LLM, NO Cansu live-config change. Cleaned up by run_id.

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g2_crash_resume
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, draft_rows, cleanup_run, seed_trend, delete_trend, seed_hype_run,
)
from scripts.lg_faz2_gate_common import (
    install_publish_mocks, build_publish_state, RECORDER, ALERTS,
    platform_call_count,
)

# Single platform keeps the crash window unambiguous (one schedule_posts call,
# one writeback). twitter is the scheduled platform.
PLATFORMS = ("twitter",)
SCHED_PLATFORM = "twitter"


class _WritebackCrash(RuntimeError):
    """Raised to simulate a crash AFTER schedule_posts returns but BEFORE the
    real postiz_post_id is persisted (row stays at 'SCHEDULING')."""


def main() -> int:
    import flow as flowmod
    install_publish_mocks(flowmod, platforms=PLATFORMS)

    failures: list[str] = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)

    RECORDER["calls"].clear()
    ALERTS.clear()

    # ── CRASH RUN ────────────────────────────────────────────────────────
    # Patch _write_daily_draft so the WRITE-AHEAD ('SCHEDULING') call goes
    # through to the real DB (so the orphan row truly persists), but the
    # WRITEBACK call (real postiz id, after schedule_posts) RAISES — exactly the
    # crash window the BLOCKER fix protects.
    _orig_wdd = flowmod.AutonomousContentFlow._write_daily_draft

    def _crashing_wdd(self, *args, **kwargs):
        ppid = kwargs.get("postiz_post_id")
        if ppid == "SCHEDULING":
            # write-ahead: let it persist the sentinel row
            return _orig_wdd(self, *args, **kwargs)
        if ppid is None:
            # pending_review / deferred paths — let through (not our crash point)
            return _orig_wdd(self, *args, **kwargs)
        # writeback with a real id → CRASH before persisting it
        raise _WritebackCrash(
            f"simulated crash before persisting real postiz_post_id={ppid}")

    flowmod.AutonomousContentFlow._write_daily_draft = _crashing_wdd

    crashed = False
    cf1 = build_publish_state(flowmod, run_id, tid, PLATFORMS)
    try:
        cf1.publish_to_drafts()
    except _WritebackCrash as e:
        crashed = True
        print(f"[G2.crash] publish_to_drafts crashed as designed: {e}")
    except Exception as e:  # noqa: BLE001
        crashed = True
        print(f"[G2.crash] publish_to_drafts raised: {type(e).__name__}: {e}")

    crash_calls = platform_call_count(SCHED_PLATFORM)
    print(f"[G2.crash] schedule_posts({SCHED_PLATFORM}) call count after crash: "
          f"{crash_calls} (expected 1 — the post DID go out before crash)")
    if not crashed:
        failures.append("G2.crash publish_to_drafts did NOT crash (writeback patch ineffective)")
    if crash_calls != 1:
        failures.append(
            f"G2.crash schedule_posts({SCHED_PLATFORM}) called {crash_calls}x "
            f"in crash run (expected exactly 1)")

    # Confirm the row is stranded at 'SCHEDULING' (the orphan the resume must catch)
    rows_after_crash = {r["platform"]: r for r in draft_rows(run_id)
                        if not r.get("deleted_at")}
    tw_after_crash = rows_after_crash.get(SCHED_PLATFORM, {}).get("postiz_post_id")
    print(f"[G2.crash] {SCHED_PLATFORM} row postiz_post_id after crash: {tw_after_crash} "
          f"(expected 'SCHEDULING' orphan)")
    if tw_after_crash != "SCHEDULING":
        failures.append(
            f"G2.crash row not stranded at SCHEDULING (got {tw_after_crash!r}) "
            f"— crash window not reproduced correctly")

    # ── RESUME RUN ───────────────────────────────────────────────────────
    # Restore the REAL _write_daily_draft (resume process is healthy; the only
    # leftover is the SCHEDULING orphan in the DB). Re-invoke publish_to_drafts
    # for the SAME run_id == what node_publish re-runs on resume.
    flowmod.AutonomousContentFlow._write_daily_draft = _orig_wdd
    ALERTS.clear()

    cf2 = build_publish_state(flowmod, run_id, tid, PLATFORMS)
    cf2.publish_to_drafts()
    st2 = cf2._state

    total_calls = platform_call_count(SCHED_PLATFORM)
    print(f"[G2.resume] schedule_posts({SCHED_PLATFORM}) TOTAL call count "
          f"across crash+resume: {total_calls} (MUST be 1, NOT 2)")
    print(f"[G2.resume] all schedule_posts calls: {RECORDER['calls']}")
    print(f"[G2.resume] state.error: {st2.error!r}")
    print(f"[G2.resume] state.final_status: {st2.final_status!r}")
    print(f"[G2.resume] alerts: {[(a['title'][:40], a['severity']) for a in ALERTS]}")

    # ── THE core assertion: NO double post ──
    if total_calls != 1:
        failures.append(
            f"G2 schedule_posts({SCHED_PLATFORM}) total across crash+resume = "
            f"{total_calls} (MUST be 1). >1 ⇒ DOUBLE LIVE POST — BLOCKER fix BROKEN.")
    # resume must fail-close, not silently succeed
    if not (st2.error and "scheduling_orphan" in st2.error):
        failures.append(
            f"G2.resume did not fail-close on orphan: state.error={st2.error!r}")
    if st2.final_status != "failed":
        failures.append(
            f"G2.resume final_status={st2.final_status!r} (expected 'failed')")
    if not any(a.get("severity") == "critical" for a in ALERTS):
        failures.append("G2.resume no CRITICAL alert fired")

    cleaned = cleanup_run(run_id)
    delete_trend(tid)
    print(f"\n[cleanup] run_id={run_id} → {cleaned}")
    print(f"[evidence] total schedule_posts calls (recorder): {len(RECORDER['calls'])} "
          f"— zero real Postiz")

    ok = not failures
    print("\n" + ("=" * 60))
    if ok:
        print(f"✅ G2 PASS — crash between schedule_posts() and writeback left a "
              f"SCHEDULING orphan; RESUME hit it → fail-closed (run 'failed', "
              f"CRITICAL alert), schedule_posts({SCHED_PLATFORM}) called EXACTLY "
              f"ONCE across crash+resume (NO double LIVE post).")
    else:
        print("❌ G2 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

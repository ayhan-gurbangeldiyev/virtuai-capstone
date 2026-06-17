"""G1 — SCHEDULING-orphan FAIL-CLOSED (no re-POST).

HEADLINE no-double-post safety property. Seed a daily_drafts row for a fresh
TEST run_id with postiz_post_id='SCHEDULING' (write-ahead sentinel) for a
platform the run will try to schedule. Drive publish_to_drafts → it MUST detect
the SCHEDULING orphan and:
  - set state.error (postiz_scheduling_orphan: ...)
  - finalize the run 'failed'
  - fire a CRITICAL alert (tools.alerter.send_alert spied)
  - NOT call schedule_posts for that platform (NO double LIVE post)

NO real Postiz (GuardedPostizClient.schedule_posts replaced with a recorder),
NO paid LLM (faithfulness/clarity gates stubbed PASS), NO Cansu live-config
change (hype_account_config read wrapped in-process). All DB rows cleaned up by
run_id at the end. Checkpointer not used (publish_to_drafts driven directly).

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g1_scheduling_orphan
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, draft_rows, cleanup_run, seed_trend, delete_trend,
    insert_test_draft, seed_hype_run,
)
from scripts.lg_faz2_gate_common import (
    install_publish_mocks, build_publish_state, RECORDER, ALERTS, CONTENT_TYPE,
)

# The run plans to schedule twitter; we pre-seed twitter as a SCHEDULING orphan.
PLATFORMS = ("twitter", "linkedin")
ORPHAN_PLATFORM = "twitter"


def main() -> int:
    import flow as flowmod
    install_publish_mocks(flowmod, platforms=PLATFORMS)

    failures: list[str] = []
    run_id = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    seed_trend(tid)
    seed_hype_run(run_id, CANSU, tid)

    # Seed the SCHEDULING write-ahead sentinel for twitter (matching
    # hype_run_id + platform + content_type the run will try to schedule).
    seed_did = insert_test_draft(
        run_id, CANSU, ORPHAN_PLATFORM, CONTENT_TYPE, "pending", "SCHEDULING")
    print(f"[G1] seeded SCHEDULING orphan: platform={ORPHAN_PLATFORM} "
          f"content_type={CONTENT_TYPE} did={seed_did}")

    RECORDER["calls"].clear()
    ALERTS.clear()

    cf = build_publish_state(flowmod, run_id, tid, PLATFORMS)
    cf.publish_to_drafts()

    st = cf._state

    # ── Assert 1: schedule_posts NOT called for the orphan platform ──
    flat_called = [p for call in RECORDER["calls"] for p in call]
    print(f"[G1] schedule_posts calls: {RECORDER['calls']}")
    print(f"[G1] platforms sent to schedule_posts: {flat_called}")
    if ORPHAN_PLATFORM in flat_called:
        failures.append(
            f"G1 schedule_posts CALLED for orphan platform '{ORPHAN_PLATFORM}' "
            f"— DOUBLE LIVE POST risk (fail-closed did NOT engage)")
    # The whole run must fail-close BEFORE any schedule_posts (fail-closed is
    # evaluated over the full to-schedule set, so even linkedin should not post).
    if flat_called:
        failures.append(
            f"G1 schedule_posts was called at all ({flat_called}) — fail-closed "
            f"must abort the run before ANY Postiz call when an orphan is present")

    # ── Assert 2: state.error set to scheduling_orphan ──
    print(f"[G1] state.error: {st.error!r}")
    print(f"[G1] state.final_status: {st.final_status!r}")
    if not (st.error and "scheduling_orphan" in st.error):
        failures.append(
            f"G1 state.error not set to scheduling_orphan: {st.error!r}")

    # ── Assert 3: run finalized 'failed' ──
    if st.final_status != "failed":
        failures.append(
            f"G1 final_status={st.final_status!r} (expected 'failed')")

    # ── Assert 4: CRITICAL alert fired ──
    print(f"[G1] alerts fired: {[(a['title'][:40], a['severity']) for a in ALERTS]}")
    crit = [a for a in ALERTS if a.get("severity") == "critical"]
    if not crit:
        failures.append("G1 no CRITICAL alert fired (operator never warned)")
    else:
        # the orphan platform should appear in the alert
        a0 = crit[0]
        if ORPHAN_PLATFORM not in (str(a0.get("platform") or "")
                                   + str(a0.get("reason") or "")).lower():
            failures.append(
                f"G1 CRITICAL alert does not name orphan platform "
                f"'{ORPHAN_PLATFORM}': {a0.get('platform')} / {a0.get('reason')}")

    # ── Assert 5: no duplicate live-id row created (orphan stays SCHEDULING) ──
    rows = {r["platform"]: r for r in draft_rows(run_id) if not r.get("deleted_at")}
    tw_pid = rows.get(ORPHAN_PLATFORM, {}).get("postiz_post_id")
    print(f"[G1] post-run twitter row postiz_post_id={tw_pid} (must NOT be a FAKE_ live id)")
    if tw_pid and str(tw_pid).startswith("FAKE_"):
        failures.append(
            f"G1 orphan row got a real/fake live post id {tw_pid} — re-POST happened")

    cleaned = cleanup_run(run_id)
    delete_trend(tid)
    print(f"\n[cleanup] run_id={run_id} → {cleaned}")
    print(f"[evidence] zero real Postiz calls (recorder only): "
          f"total_calls={len(RECORDER['calls'])}")

    ok = not failures
    print("\n" + ("=" * 60))
    if ok:
        print("✅ G1 PASS — SCHEDULING orphan detected → fail-closed: run 'failed', "
              "state.error set, CRITICAL alert fired, schedule_posts NOT called "
              "(no double LIVE post).")
    else:
        print("❌ G1 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

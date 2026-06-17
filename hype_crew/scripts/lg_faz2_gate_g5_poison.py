"""G5 — resume-attempt cap force-fails + cleans up + is NOT re-selected.

Seeds a hype_runs row status='running' with resume_attempts=3 (= AT cap) + an
incomplete checkpoint for its thread_id (run_id) + an orphan daily_drafts row
(pending, postiz_post_id NULL) AND a control row that must SURVIVE (a SCHEDULING /
real-id row on the publish path). Then calls the REAL resume path
(run_or_resume on that run_id).

ASSERTS:
  1. _bump_resume_attempts → 4 (>3) → _force_fail_poison_run sets status='failed'
     + error written.
  2. reap_orphan_drafts soft-deletes the NULL-postiz orphan (deleted_at set) but
     LEAVES the SCHEDULING/real-id row untouched.
  3. CRITICAL alert fired (spy on tools.alerter.send_alert).
  4. graph.invoke NOT called (spy on StateGraph.invoke).
  5. run_or_resume returns None.
  6. get_resumable_run_id then SKIPS this run (resume_attempts >= MAX → never
     re-selected → no infinite force-fail loop).

The incomplete checkpoint is created with a REAL build_state_graph + REAL
sync_checkpointer using interrupt_before so .next is non-empty (snap.next truthy
→ resume branch), exactly what run_or_resume's `if snap.next:` checks. run_crew
is stubbed (no LLM/paid). dry-run config forced. Cansu live config untouched.

CLEANUP: hype_runs + daily_drafts by run_id; langgraph.* checkpoint rows by
thread_id.

Run:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g5_poison
"""
from __future__ import annotations

import os
import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, install_dry_path_mocks, force_dry_run_config,
    cleanup_run, seed_trend, delete_trend, lookup_account_user_id,
)


def _seed_hype_run_at_cap(run_id: str, trend_id: str) -> bool:
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    row = {
        "id": run_id, "account_id": CANSU, "status": "running",
        "triggered_by": "manual", "dry_run": True,
        "resume_attempts": 3,  # AT cap → bump → 4 > 3 → poison
        "trend_id": trend_id,
    }
    try:
        sb.table("hype_runs").insert(row).execute()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[seed] hype_run failed: {str(e)[:200]}")
        return False


def _seed_draft(run_id: str, platform: str, status: str, postiz_post_id):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    row = {
        "account_id": CANSU, "user_id": lookup_account_user_id(CANSU),
        "content": f"g5 poison test seed ({platform})", "platform": platform,
        "status": status, "source": "hype_auto", "hype_run_id": run_id,
        "postiz_post_id": postiz_post_id,
    }
    try:
        r = sb.table("daily_drafts").insert(row).execute()
        rows = r.data if isinstance(r.data, list) else []
        return rows[0].get("id") if rows and isinstance(rows[0], dict) else None
    except Exception as e:  # noqa: BLE001
        print(f"[seed] draft failed: {str(e)[:200]}")
        return None


def _draft_state(draft_id: str):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = (sb.table("daily_drafts").select("id, status, deleted_at, postiz_post_id")
         .eq("id", draft_id).limit(1).execute())
    rows = r.data or []
    return rows[0] if rows else None


def _run_status(run_id: str):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = sb.table("hype_runs").select("status, error, resume_attempts").eq("id", run_id).limit(1).execute()
    rows = r.data or []
    return rows[0] if rows else None


def _cleanup_checkpoint(url: str, thread_id: str):
    import psycopg
    conn = psycopg.connect(url, autocommit=True)
    out = {}
    with conn.cursor() as cur:
        for t in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                cur.execute(f"DELETE FROM langgraph.{t} WHERE thread_id = %s", (thread_id,))
                out[t] = cur.rowcount
            except Exception as e:
                out[t] = f"err: {str(e)[:50]}"
    conn.close()
    return out


def main() -> int:
    import flow as flowmod
    from flow import HypeFlowState
    from lg.graph import build_state_graph
    from lg.checkpointer import sync_checkpointer
    import lg.graph as graphmod
    import tools.alerter as alerter

    url = os.environ.get("HYPE_CHECKPOINT_DB_URL", "")
    failures: list[str] = []

    # run_id == thread_id (stable thread_id invariant). hype_runs.id and
    # trends.id are UUID columns → must be dashed-UUID strings, not bare hex
    # or arbitrary labels (else 22P02 invalid uuid → seeds silently fail and
    # the test exercises a fresh non-poison run).
    run_id = str(uuid.uuid4())
    trend_id = str(uuid.uuid4())

    install_dry_path_mocks(flowmod, trend_id, platforms=("twitter",))
    force_dry_run_config(flowmod)
    seed_trend(trend_id)

    # ── Seed real DB rows ──
    _seed_hype_run_at_cap(run_id, trend_id)
    orphan_id = _seed_draft(run_id, "twitter", "pending", None)            # must be reaped
    survivor_id = _seed_draft(run_id, "devto", "pending", "SCHEDULING")    # must survive
    realid_id = _seed_draft(run_id, "linkedin", "pending", "real-post-123")  # must survive
    print(f"[G5] seeded run={run_id[:8]} orphan={str(orphan_id)[:8]} "
          f"survivor(SCHEDULING)={str(survivor_id)[:8]} realid={str(realid_id)[:8]}")

    # ── Create an INCOMPLETE checkpoint for thread_id (interrupt_before write) ──
    cfg = {"configurable": {"thread_id": run_id}}
    with sync_checkpointer() as cp:
        cf = flowmod.AutonomousContentFlow()
        g = build_state_graph(cf).compile(checkpointer=cp, interrupt_before=["write"])
        init = HypeFlowState(account_id=CANSU, triggered_by="manual")
        init.run_id = run_id
        g.invoke(init, cfg, durability="sync")
        snap = g.get_state(cfg)
        print(f"[G5] checkpoint pending(next)={snap.next} (truthy → resume branch)")
        if not snap.next:
            failures.append("seeded checkpoint has empty .next — resume branch won't trigger")

    # ── Spies ──
    alert_calls: list[dict] = []
    _orig_send_alert = alerter.send_alert

    def _spy_send_alert(*a, **k):
        alert_calls.append({"args": a, "kwargs": k})
        return None  # do NOT actually send to Slack

    alerter.send_alert = _spy_send_alert
    # _force_fail_poison_run imports send_alert from tools.alerter at call time
    # (`from tools.alerter import send_alert`) → patching the module attr works.

    invoke_calls = {"n": 0}
    from langgraph.graph.state import CompiledStateGraph
    _orig_invoke = CompiledStateGraph.invoke

    def _spy_invoke(self, *a, **k):
        invoke_calls["n"] += 1
        return _orig_invoke(self, *a, **k)

    CompiledStateGraph.invoke = _spy_invoke

    result = "UNSET"
    try:
        # ── REAL resume path ──
        result = graphmod.run_or_resume(CANSU, triggered_by="manual", run_id=run_id)
    finally:
        CompiledStateGraph.invoke = _orig_invoke
        alerter.send_alert = _orig_send_alert

    print(f"[G5] run_or_resume returned: {result!r}")
    print(f"[G5] graph.invoke call count during resume: {invoke_calls['n']}")
    print(f"[G5] CRITICAL alert calls: {len(alert_calls)}")

    # ── Assertions ──
    if result is not None:
        failures.append(f"run_or_resume returned {result!r}, expected None (poison)")
    if invoke_calls["n"] != 0:
        failures.append(
            f"graph.invoke called {invoke_calls['n']}x — poison run MUST NOT invoke"
        )
    crit = [c for c in alert_calls
            if str(c["kwargs"].get("severity", "")).lower() == "critical"]
    if not crit:
        failures.append("no CRITICAL alert fired on poison force-fail")

    rs = _run_status(run_id) or {}
    print(f"[G5] hype_run after: status={rs.get('status')} "
          f"resume_attempts={rs.get('resume_attempts')} error={(rs.get('error') or '')[:60]!r}")
    if rs.get("status") != "failed":
        failures.append(f"hype_run status={rs.get('status')} != 'failed'")
    if not rs.get("error"):
        failures.append("hype_run error not written on force-fail")
    if rs.get("resume_attempts") != 4:
        failures.append(f"resume_attempts={rs.get('resume_attempts')} != 4 (bump didn't apply)")

    osd = _draft_state(orphan_id) if orphan_id else None
    if not osd or not osd.get("deleted_at"):
        failures.append("NULL-postiz orphan draft was NOT soft-deleted")
    else:
        print(f"[G5] orphan soft-deleted: deleted_at set ✓")
    ssd = _draft_state(survivor_id) if survivor_id else None
    if not ssd or ssd.get("deleted_at"):
        failures.append("SCHEDULING draft was soft-deleted (should SURVIVE — publish path)")
    else:
        print(f"[G5] SCHEDULING draft survived ✓")
    rsd = _draft_state(realid_id) if realid_id else None
    if not rsd or rsd.get("deleted_at"):
        failures.append("real-id draft was soft-deleted (should SURVIVE — already scheduled)")
    else:
        print(f"[G5] real-id draft survived ✓")

    # ── get_resumable_run_id must SKIP this run (resume_attempts >= MAX) ──
    # Spy invoke again to prove no force-fail loop is triggered by re-selection.
    picked = graphmod.get_resumable_run_id(CANSU)
    print(f"[G5] get_resumable_run_id picked: {picked!r} (must NOT be our run)")
    if picked == run_id:
        failures.append("poison run was RE-SELECTED by get_resumable_run_id (loop risk)")

    # ── CLEANUP ──
    cleaned = cleanup_run(run_id)
    trends_deleted = delete_trend(trend_id)
    cp_cleaned = _cleanup_checkpoint(url, run_id)
    print(f"\n[cleanup] run={run_id[:8]} → {cleaned} trends={trends_deleted} checkpoints={cp_cleaned}")

    ok = not failures
    print("\n" + "=" * 64)
    if ok:
        print("✅ G5 PASS — poison run force-failed (status=failed + error + "
              "resume_attempts=4), NULL-postiz orphan reaped while SCHEDULING/"
              "real-id rows survived, CRITICAL alert fired, graph NOT invoked, "
              "and get_resumable_run_id skips it (no loop).")
    else:
        print("❌ G5 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

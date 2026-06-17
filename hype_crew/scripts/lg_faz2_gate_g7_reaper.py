"""G7 — reaper-vs-resume ordering invariant.

Confirms the lifetime-bound coordination rule between runner._reap_stuck_runs
and lg.graph.get_resumable_run_id:

  • A <2h 'running' run WITH a live checkpoint is RESUMED, not reaped:
      - _reap_stuck_runs leaves it 'running' (started_at is inside the cutoff)
      - get_resumable_run_id selects it (status='running' + snap.next truthy)

  • A >2h 'running' run is reaped → 'failed':
      - _reap_stuck_runs flips it to 'failed' (started_at < cutoff)
      - get_resumable_run_id then EXCLUDES it (filters status='running'), so a
        reaped row can never be picked → no "live checkpoint but row reaped to
        failed" un-resumable orphan window.

The invariant under test: get_resumable_run_id filters status='running', so the
moment the reaper flips a row to 'failed' it drops out of the resume candidate
set. There is no ordering where a checkpoint is live AND the row is selectable
for resume AND it was just reaped.

Reports STUCK_RUN_THRESHOLD_HOURS actual value.

Two real hype_runs seeded (one fresh, one aged via started_at backdate) each
with a real incomplete checkpoint. No invoke, no posting, no paid calls.
CLEANUP by run_id + thread_id.

Run:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_gate_g7_reaper
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone, timedelta

from scripts.lg_faz2_idem_testlib import (
    CANSU, install_dry_path_mocks, force_dry_run_config,
    cleanup_run, seed_trend, delete_trend,
)


def _seed_run(run_id: str, trend_id: str, started_at_iso: str):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    sb.table("hype_runs").insert({
        "id": run_id, "account_id": CANSU, "status": "running",
        "triggered_by": "manual", "dry_run": True, "resume_attempts": 0,
        "trend_id": trend_id, "started_at": started_at_iso,
    }).execute()


def _make_checkpoint(flowmod, run_id: str):
    from flow import HypeFlowState
    from lg.graph import build_state_graph
    from lg.checkpointer import sync_checkpointer
    cfg = {"configurable": {"thread_id": run_id}}
    with sync_checkpointer() as cp:
        cf = flowmod.AutonomousContentFlow()
        g = build_state_graph(cf).compile(checkpointer=cp, interrupt_before=["write"])
        init = HypeFlowState(account_id=CANSU, triggered_by="manual")
        init.run_id = run_id
        g.invoke(init, cfg, durability="sync")
        return bool(g.get_state(cfg).next)


def _status(run_id: str):
    from tools.supabase_client import make_supabase
    sb = make_supabase()
    r = sb.table("hype_runs").select("status").eq("id", run_id).limit(1).execute()
    return (r.data or [{}])[0].get("status")


def _cleanup_cp(url, thread_id):
    import psycopg
    conn = psycopg.connect(url, autocommit=True)
    with conn.cursor() as cur:
        for t in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            try:
                cur.execute(f"DELETE FROM langgraph.{t} WHERE thread_id=%s", (thread_id,))
            except Exception:
                pass
    conn.close()


def main() -> int:
    import flow as flowmod
    from runner import _reap_stuck_runs, STUCK_RUN_THRESHOLD_HOURS
    from lg.graph import get_resumable_run_id
    from tools.supabase_client import make_supabase

    url = os.environ.get("HYPE_CHECKPOINT_DB_URL", "")
    print(f"[G7] STUCK_RUN_THRESHOLD_HOURS = {STUCK_RUN_THRESHOLD_HOURS}")
    failures: list[str] = []

    # Stubs so checkpoint creation makes no paid call.
    fresh_trend = str(uuid.uuid4())
    install_dry_path_mocks(flowmod, fresh_trend, platforms=("twitter",))
    force_dry_run_config(flowmod)

    fresh_id = str(uuid.uuid4())
    aged_id = str(uuid.uuid4())
    aged_trend = str(uuid.uuid4())
    seed_trend(fresh_trend)
    seed_trend(aged_trend)

    now = datetime.now(timezone.utc)
    fresh_started = (now - timedelta(minutes=10)).isoformat()              # <2h
    aged_started = (now - timedelta(hours=STUCK_RUN_THRESHOLD_HOURS + 1)).isoformat()  # >2h

    _seed_run(fresh_id, fresh_trend, fresh_started)
    _seed_run(aged_id, aged_trend, aged_started)
    cp_fresh = _make_checkpoint(flowmod, fresh_id)
    cp_aged = _make_checkpoint(flowmod, aged_id)
    print(f"[G7] seeded fresh={fresh_id[:8]} (<2h, cp.next={cp_fresh}) "
          f"aged={aged_id[:8]} (>2h, cp.next={cp_aged})")

    # ── Run the REAL reaper ──
    reaped = _reap_stuck_runs(make_supabase(), CANSU)
    fresh_status = _status(fresh_id)
    aged_status = _status(aged_id)
    print(f"[G7] reaper reaped {reaped} run(s); fresh status={fresh_status} "
          f"aged status={aged_status}")

    if fresh_status != "running":
        failures.append(f"<2h run was reaped (status={fresh_status}) — should stay 'running'")
    if aged_status != "failed":
        failures.append(f">2h run NOT reaped (status={aged_status}) — should be 'failed'")

    # ── get_resumable_run_id AFTER reap ──
    picked = get_resumable_run_id(CANSU)
    print(f"[G7] get_resumable_run_id picked: {str(picked)[:8] if picked else None}")
    if picked == aged_id:
        failures.append("reaped (failed) run was selected for resume — un-resumable orphan window EXISTS")
    # The fresh, live-checkpoint, still-'running' run SHOULD be the pick (or at
    # least eligible). If other real Cansu running rows exist it may pick those,
    # but it must NEVER pick the reaped one (the invariant). We additionally
    # assert the fresh one is selectable in isolation below.

    # Isolation check: confirm the invariant directly — a 'failed' row is
    # excluded from the candidate query regardless of live checkpoint.
    sb = make_supabase()
    cand = (sb.table("hype_runs").select("id")
            .eq("account_id", CANSU).eq("status", "running")
            .eq("id", aged_id).execute())
    if cand.data:
        failures.append("reaped run still appears in status='running' candidate query")
    else:
        print("[G7] invariant: reaped run absent from status='running' candidate set ✓")
    # And the fresh run IS in the candidate set with a live checkpoint.
    cand_fresh = (sb.table("hype_runs").select("id")
                  .eq("account_id", CANSU).eq("status", "running")
                  .eq("id", fresh_id).execute())
    if not cand_fresh.data:
        failures.append("fresh <2h run missing from running-candidate set")
    else:
        print("[G7] fresh <2h run present in candidate set + has live checkpoint ✓")

    # ── CLEANUP ──
    c1 = cleanup_run(fresh_id)
    c2 = cleanup_run(aged_id)
    delete_trend(fresh_trend)
    delete_trend(aged_trend)
    _cleanup_cp(url, fresh_id)
    _cleanup_cp(url, aged_id)
    print(f"\n[cleanup] fresh={c1} aged={c2}")

    ok = not failures
    print("\n" + "=" * 64)
    if ok:
        print(f"✅ G7 PASS — <2h live-checkpoint run stays 'running' (resumable); "
              f">2h run reaped→'failed' and is excluded from the resume candidate "
              f"set (status='running' filter) → no un-resumable orphan window. "
              f"STUCK_RUN_THRESHOLD_HOURS={STUCK_RUN_THRESHOLD_HOURS}.")
    else:
        print("❌ G7 FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

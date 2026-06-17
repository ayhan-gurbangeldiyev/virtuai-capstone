"""STAGE B — PROD Postgres kill→resume, runner'ın GERÇEK yoluyla.

test_c'nin prod varyantı. Farklar:
  1. Checkpointer = PROD Supabase Postgres (langgraph şeması) — sync_checkpointer()
     arg'sız → HYPE_CHECKPOINT_DB_URL. (test_c lokal SQLite kullanıyordu.)
  2. Resume, g.invoke(None) ile DEĞİL, runner'ın gerçek yoluyla tetiklenir:
     get_resumable_run_id(CANSU) → run_or_resume(CANSU, run_id=rid). Böylece
     "ayrı process resume" senaryosu birebir taklit edilir.
  3. Faz 3 assert'leri: daily_drafts çift satır YOK (count_drafts), checkpoint
     .next boş (tamamlandı), tamamlanan node (run_crew) TEKRAR koşmadı.

GÜVENLİK: force_dry_run_config → Cansu CANLI DB config'ine DOKUNULMAZ (in-process
stub). install_dry_path_mocks → visual/video=False (Wiro/HeyGen ÇAĞRILMAZ) + dry →
publish node'una inilmez → GERÇEK YAYIN YOK. Tüm pahalı node'lar stub (paid çağrı yok).

ÖN-KOŞUL: cron DURDURULMUŞ (ikinci resume yarışı olmasın) + bu hesap için başka
'running' run YOK (yanlış run resume edilmesin). HYPE_LANGGRAPH_ENABLED=true inline
(resume-safety + run_or_resume yolu açılsın; .env'e YAZMA).

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && \
  HYPE_LANGGRAPH_ENABLED=true ./venv/bin/python -m scripts.lg_stageB_kill_resume
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, install_dry_path_mocks, force_dry_run_config,
    cleanup_run, seed_trend, delete_trend, count_drafts, draft_rows,
)

CALLS = {"run_crew": 0, "write": 0, "compliance": 0, "dry_run_complete": 0}


def _wrap_counters(flowmod):
    _orig = {
        "run_crew": flowmod.AutonomousContentFlow.run_crew,
        "write": flowmod.AutonomousContentFlow.write_via_typehype,
        "compliance": flowmod.AutonomousContentFlow.run_compliance,
        "dry_run_complete": flowmod.AutonomousContentFlow.dry_run_complete,
    }

    def _c_run_crew(self, account_id):
        CALLS["run_crew"] += 1
        return _orig["run_crew"](self, account_id)

    def _c_write(self):
        CALLS["write"] += 1
        return _orig["write"](self)

    def _c_compliance(self):
        CALLS["compliance"] += 1
        return _orig["compliance"](self)

    def _c_dry(self):
        CALLS["dry_run_complete"] += 1
        return _orig["dry_run_complete"](self)

    flowmod.AutonomousContentFlow.run_crew = _c_run_crew
    flowmod.AutonomousContentFlow.write_via_typehype = _c_write
    flowmod.AutonomousContentFlow.run_compliance = _c_compliance
    flowmod.AutonomousContentFlow.dry_run_complete = _c_dry


def main() -> int:
    from config import settings
    if not getattr(settings, "langgraph_enabled", False):
        print("❌ HYPE_LANGGRAPH_ENABLED=true ile koş (resume-safety + run_or_resume yolu).")
        return 2
    if not getattr(settings, "checkpoint_db_url", ""):
        print("❌ HYPE_CHECKPOINT_DB_URL boş — prod Postgres checkpointer gerekli.")
        return 2

    import flow as flowmod
    from flow import HypeFlowState
    from lg.graph import build_state_graph, run_or_resume, get_resumable_run_id
    from lg.checkpointer import sync_checkpointer

    tid = str(uuid.uuid4())
    install_dry_path_mocks(flowmod, tid, platforms=("twitter",))
    force_dry_run_config(flowmod)   # Cansu DB'ye DOKUNMAZ
    seed_trend(tid)
    _wrap_counters(flowmod)

    thread_id = str(uuid.uuid4())
    run_id = None
    failures = []

    # ── ADIM 1: PROD Postgres'te 'write' ÖNCESİ kill (checkpoint kalır) ──
    with sync_checkpointer() as cp:   # arg YOK → prod Supabase langgraph şeması
        cfg = {"configurable": {"thread_id": thread_id}}
        cf1 = flowmod.AutonomousContentFlow()
        g1 = build_state_graph(cf1).compile(checkpointer=cp, interrupt_before=["write"])
        init = HypeFlowState(account_id=CANSU, triggered_by="manual")
        init.run_id = thread_id
        g1.invoke(init, cfg, durability="sync")
        snap1 = g1.get_state(cfg)
        run_id = (snap1.values or {}).get("run_id") or thread_id
        print(f"[B.1] KILL: pending={snap1.next} run_crew={CALLS['run_crew']} write={CALLS['write']}")
        if snap1.next != ("write",):
            failures.append(f"B.1 pending beklenen ('write',), gelen {snap1.next}")
        if CALLS["run_crew"] != 1:
            failures.append(f"B.1 run_crew {CALLS['run_crew']} (1 olmalı)")
        if CALLS["write"] != 0:
            failures.append(f"B.1 write {CALLS['write']} (0 olmalı — henüz durduk)")
        if not (snap1.values or {}).get("trend"):
            failures.append("B.1 checkpoint trend tutmuyor — resume imkânsız")

    # ── ADIM 2: RESUME runner'ın GERÇEK yoluyla (ayrı-process taklidi) ──
    rid = get_resumable_run_id(CANSU)
    print(f"[B.2] get_resumable_run_id → {rid} (beklenen {thread_id})")
    if rid != thread_id:
        failures.append(
            f"B.2 get_resumable_run_id {rid} döndü, {thread_id} beklendi "
            "(başka 'running' run mı var? cron durdu mu?)")
    else:
        final = run_or_resume(CANSU, triggered_by="manual", run_id=rid)
        fs = getattr(final, "final_status", None) if final else None
        print(f"[B.2] RESUME tamam: final_status={fs} calls={CALLS}")
        # KRİTİK: tamamlanan node TEKRAR koşmadı
        if CALLS["run_crew"] != 1:
            failures.append(f"B.2 run_crew {CALLS['run_crew']} — RESUME RESTART YAPTI (1 olmalı)")
        if CALLS["write"] != 1:
            failures.append(f"B.2 write {CALLS['write']} (1 olmalı — resume'da devam)")

    # ── ADIM 3: yan-etki çift-satır YOK + checkpoint tamamlandı ──
    drafts = count_drafts(run_id) if run_id else -1
    rows = draft_rows(run_id) if run_id else []
    # (platform, content_type) bazında çift var mı
    seen = {}
    for r in rows:
        k = (r.get("platform"), r.get("content_type"))
        seen[k] = seen.get(k, 0) + 1
    dups = {k: v for k, v in seen.items() if v > 1}
    print(f"[B.3] daily_drafts toplam={drafts} çift-grup={dups or 'YOK'}")
    if dups:
        failures.append(f"B.3 daily_drafts ÇİFT satır: {dups}")
    with sync_checkpointer() as cp:
        g = build_state_graph(flowmod.AutonomousContentFlow()).compile(checkpointer=cp)
        snapf = g.get_state({"configurable": {"thread_id": thread_id}})
        print(f"[B.3] resume sonrası checkpoint .next={snapf.next} (boş=tamamlandı)")
        if snapf.next:
            failures.append(f"B.3 checkpoint .next hâlâ dolu {snapf.next} — tamamlanmadı")

    # ── TEMİZLİK ──
    cleaned = cleanup_run(run_id) if run_id else {}
    trd = delete_trend(tid)
    print(f"\n[cleanup] run_id={run_id} → {cleaned} trends={trd}")
    print("[cleanup] NOT: langgraph.checkpoints/blobs/writes WHERE thread_id="
          f"'{thread_id}' MANUEL silinmeli (testlib checkpoint silmez).")

    ok = not failures
    print("\n" + "=" * 60)
    if ok:
        print(f"✅ STAGE B PASS — PROD Postgres'te kill→resume: run_crew TEK kez "
              f"(CONTINUE, RESTART değil), runner yolu (get_resumable→run_or_resume) "
              f"resume etti, daily_drafts çift YOK, checkpoint tamamlandı. calls={CALLS}")
    else:
        print("❌ STAGE B FAIL:")
        for f in failures:
            print("   -", f)
        print(f"   calls={CALLS}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

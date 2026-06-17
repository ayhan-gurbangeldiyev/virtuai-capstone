"""TEST C — resume CONTINUES, not RESTARTS (pahalı node TEK kez koşar).

Kanıt: interrupt + resume sonrası TAMAMLANMIŞ node (run_crew = pahalı/LLM adımının
temsilcisi) TEKRAR ÇALIŞMAZ. Gerçek build_state_graph + LOKAL SQLite checkpointer
ile, run_crew stub'una bir SAYAÇ koyup interrupt_before=['write'] ile durur, sonra
taze graph compile + aynı thread_id ile resume edilir → run_crew sayacı 1'de kalmalı
(checkpoint resume semantiği = kaldığı yerden devam).

Hiçbir paid çağrı yok (tüm pahalı node'lar stub). Checkpointer SQLite. Sonunda
run_id ile temizlik.

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_test_c_resume
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, install_dry_path_mocks, force_dry_run_config,
    cleanup_run, seed_trend, delete_trend,
)

CALLS = {"run_crew": 0, "write": 0, "compliance": 0, "dry_run_complete": 0}


def main() -> int:
    import flow as flowmod
    from flow import HypeFlowState
    from lg.graph import build_state_graph
    from lg.checkpointer import sync_checkpointer

    tid = str(uuid.uuid4())
    platforms = ("twitter",)
    install_dry_path_mocks(flowmod, tid, platforms=platforms)
    force_dry_run_config(flowmod)
    seed_trend(tid)

    # install_dry_path_mocks'ın stub'larını SAYAÇLA sarmala (her node çağrısını say).
    _orig_run_crew = flowmod.AutonomousContentFlow.run_crew
    _orig_write = flowmod.AutonomousContentFlow.write_via_typehype
    _orig_compliance = flowmod.AutonomousContentFlow.run_compliance
    _orig_dry = flowmod.AutonomousContentFlow.dry_run_complete

    def _c_run_crew(self, account_id):
        CALLS["run_crew"] += 1
        return _orig_run_crew(self, account_id)

    def _c_write(self):
        CALLS["write"] += 1
        return _orig_write(self)

    def _c_compliance(self):
        CALLS["compliance"] += 1
        return _orig_compliance(self)

    def _c_dry(self):
        CALLS["dry_run_complete"] += 1
        return _orig_dry(self)

    flowmod.AutonomousContentFlow.run_crew = _c_run_crew
    flowmod.AutonomousContentFlow.write_via_typehype = _c_write
    flowmod.AutonomousContentFlow.run_compliance = _c_compliance
    flowmod.AutonomousContentFlow.dry_run_complete = _c_dry

    thread_id = str(uuid.uuid4())
    run_id = None
    failures = []

    with sync_checkpointer(db_url="") as cp:
        cfg = {"configurable": {"thread_id": thread_id}}

        # ── ADIM 1: run_crew'i çalıştır, write'TEN ÖNCE dur (çökme noktası) ──
        cf1 = flowmod.AutonomousContentFlow()
        g1 = build_state_graph(cf1).compile(
            checkpointer=cp, interrupt_before=["write"])
        init = HypeFlowState(account_id=CANSU, triggered_by="manual")
        init.run_id = thread_id
        g1.invoke(init, cfg, durability="sync")
        snap1 = g1.get_state(cfg)
        run_id = (snap1.values or {}).get("run_id") or thread_id
        print(f"[C.1] interrupt sonrası pending={snap1.next} "
              f"run_crew_calls={CALLS['run_crew']} write_calls={CALLS['write']}")
        if snap1.next != ("write",):
            failures.append(f"C.1 pending beklenen ('write',), gelen {snap1.next}")
        if CALLS["run_crew"] != 1:
            failures.append(f"C.1 run_crew {CALLS['run_crew']} kez koştu (1 olmalı)")
        if CALLS["write"] != 0:
            failures.append(f"C.1 write {CALLS['write']} kez koştu (0 olmalı — daha durduk)")
        # state run_crew çıktısını (trend/plan) tuttu mu?
        has_trend = bool((snap1.values or {}).get("trend"))
        print(f"[C.1] checkpoint trend tutuyor mu (resume için): {has_trend}")
        if not has_trend:
            failures.append("C.1 checkpoint run_crew çıktısı (trend) tutmuyor — resume imkânsız")

        # ── ADIM 2: RESUME (taze compile, AYNI thread_id) → write'tan devam ──
        cf2 = flowmod.AutonomousContentFlow()
        g2 = build_state_graph(cf2).compile(checkpointer=cp)
        g2.invoke(None, cfg, durability="sync")  # RESUME → write→compliance→dry_run
        snap2 = g2.get_state(cfg)
        print(f"[C.2] resume sonrası pending={snap2.next} (boş = tamamlandı) | "
              f"calls={CALLS}")
        # KRİTİK: resume run_crew'i TEKRAR çalıştırmadı.
        if CALLS["run_crew"] != 1:
            failures.append(
                f"C.2 run_crew {CALLS['run_crew']} kez koştu — RESUME RESTART YAPTI "
                f"(1 olmalıydı; checkpoint resume semantiği KIRIK)")
        # write/compliance/dry_run resume'da bir kez koştu.
        if CALLS["write"] != 1:
            failures.append(f"C.2 write {CALLS['write']} kez koştu (1 olmalı)")
        if CALLS["dry_run_complete"] != 1:
            failures.append(f"C.2 dry_run_complete {CALLS['dry_run_complete']} kez koştu (1 olmalı)")

    cleaned = cleanup_run(run_id) if run_id else {}
    trends_deleted = delete_trend(tid)
    print(f"\n[cleanup] run_id={run_id} → {cleaned} trends_deleted={trends_deleted}")

    ok = not failures
    print("\n" + ("=" * 60))
    if ok:
        print(f"✅ TEST C PASS — run_crew TEK kez koştu (resume RESTART değil CONTINUE), "
              f"trend state korundu, write/compliance/dry_run resume'da devam etti. "
              f"calls={CALLS}")
    else:
        print("❌ TEST C FAIL:")
        for f in failures:
            print("   -", f)
        print(f"   calls={CALLS}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

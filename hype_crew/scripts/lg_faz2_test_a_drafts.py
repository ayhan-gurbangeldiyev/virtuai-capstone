"""TEST A — daily_drafts idempotency under resume (integration, DRY, no posting).

Senaryo:
  1) Gerçek build_state_graph + LOKAL SQLite checkpointer + interrupt_before=
     ['dry_run_complete'] ile koş → graph compliance'tan SONRA, dry_run_complete'TEN
     ÖNCE durur. Bu noktada daily_drafts'a HENÜZ satır YAZILMAMIŞ olmalı (assert 0).
  2) RESUME (taze graph compile + AYNI thread_id, interrupt YOK) → dry_run_complete
     bir kez koşar → her (platform, content_type) için TAM 1 satır.
  3) İKİNCİ resume simülasyonu: checkpoint'i compliance sonrasına geri sar
     (update_state as_node="compliance") + tekrar resume → dry_run_complete TEKRAR
     koşar. _write_daily_draft idempotency'si çift satırı önlemeli → HÂLÂ
     platform başına 1 satır (2 DEĞİL).

Hiçbir paid çağrı yok: run_crew/write/compliance/persona stub'lu (LLM/render YOK),
dry_run=True (Postiz YOK). Checkpointer SQLite (paylaşılan PG'ye dokunmaz).
Sonunda tüm satırlar run_id ile silinir.

Çalıştır:
  cd hype_crew && set -a && . ./.env && set +a && ./venv/bin/python -m scripts.lg_faz2_test_a_drafts
"""
from __future__ import annotations

import uuid

from scripts.lg_faz2_idem_testlib import (
    CANSU, install_dry_path_mocks, force_dry_run_config,
    count_drafts, draft_rows, cleanup_run, seed_trend, delete_trend,
)


def main() -> int:
    import flow as flowmod
    from flow import HypeFlowState
    from lg.graph import build_state_graph
    from lg.checkpointer import sync_checkpointer

    # trend_id daily_drafts.trend_id (uuid sütunu) olarak yazılıyor → geçerli UUID
    tid = str(uuid.uuid4())
    platforms = ("twitter", "linkedin")
    install_dry_path_mocks(flowmod, tid, platforms=platforms)
    force_dry_run_config(flowmod)
    seed_trend(tid)  # daily_drafts.trend_id FK'sini karşıla (cleanup'ta silinir)

    # thread_id == run_id == hype_runs PK (uuid sütunu) → geçerli UUID olmalı
    thread_id = str(uuid.uuid4())
    run_id = None
    failures = []

    # LOKAL SQLite checkpointer (db_url="") → paylaşılan PG langgraph şemasına DOKUNMAZ
    with sync_checkpointer(db_url="") as cp:
        cfg = {"configurable": {"thread_id": thread_id}}

        # ── ADIM 1: interrupt_before=['dry_run_complete'] ile koş ────────────
        cf1 = flowmod.AutonomousContentFlow()
        g1 = build_state_graph(cf1).compile(
            checkpointer=cp, interrupt_before=["dry_run_complete"])
        init = HypeFlowState(account_id=CANSU, triggered_by="manual")
        init.run_id = thread_id  # stable thread_id == run_id (Faz 2 sözleşmesi)
        g1.invoke(init, cfg, durability="sync")

        snap1 = g1.get_state(cfg)
        run_id = (snap1.values or {}).get("run_id") or thread_id
        pending1 = snap1.next
        drafts_at_interrupt = count_drafts(run_id)
        print(f"[A.1] interrupt sonrası pending={pending1} run_id={run_id}")
        print(f"[A.1] daily_drafts (interrupt anı) = {drafts_at_interrupt} (0 bekleniyor)")
        if pending1 != ("dry_run_complete",):
            failures.append(f"A.1 pending beklenen ('dry_run_complete',), gelen {pending1}")
        if drafts_at_interrupt != 0:
            failures.append(f"A.1 interrupt anında draft sayısı {drafts_at_interrupt} (0 olmalı)")

        # ── ADIM 2: RESUME (taze compile, interrupt YOK) → dry_run_complete koşar
        cf2 = flowmod.AutonomousContentFlow()
        g2 = build_state_graph(cf2).compile(checkpointer=cp)
        g2.invoke(None, cfg, durability="sync")  # RESUME
        rows_after_first = draft_rows(run_id)
        live1 = [r for r in rows_after_first if not r.get("deleted_at")]
        cnt1 = len(live1)
        print(f"[A.2] 1. resume sonrası canlı daily_drafts = {cnt1} "
              f"(={len(platforms)} bekleniyor: {list(platforms)})")
        for r in live1:
            print(f"       - platform={r['platform']} ct={r.get('content_type')} "
                  f"status={r['status']} id={r['id'][:8]}")
        if cnt1 != len(platforms):
            failures.append(f"A.2 ilk resume {cnt1} satır yazdı ({len(platforms)} olmalı)")

        # ── ADIM 3: İKİNCİ resume — checkpoint'i compliance sonrasına geri sar,
        #            dry_run_complete'i TEKRAR çalıştır (duplicate-resume simülasyonu).
        # update_state(as_node="compliance") → graph compliance'tan sonra yeniden
        # dry_run_complete'e yönlenir; aynı state ile node TEKRAR koşar.
        snap_now = g2.get_state(cfg)
        vals = dict(snap_now.values or {})
        # publish sentinel'ini temizle ki dry_run_complete'in erken-return guard'ına
        # (draft/platform_drafts var → asıl yola gider) takılmadan tam yazım yapsın.
        g2.update_state(cfg, vals, as_node="compliance")
        snap_rewound = g2.get_state(cfg)
        print(f"[A.3] geri-sarma sonrası pending={snap_rewound.next} "
              f"(dry_run_complete bekleniyor → node tekrar koşacak)")
        g2.invoke(None, cfg, durability="sync")  # 2. kez dry_run_complete

        rows_after_second = draft_rows(run_id)
        live2 = [r for r in rows_after_second if not r.get("deleted_at")]
        cnt2 = len(live2)
        # platform başına satır sayısını da kontrol et (çift var mı?)
        by_key: dict = {}
        for r in live2:
            k = (r["platform"], r.get("content_type"))
            by_key[k] = by_key.get(k, 0) + 1
        print(f"[A.3] 2. resume (dry_run_complete TEKRAR) sonrası canlı = {cnt2} "
              f"(HÂLÂ {len(platforms)} olmalı — çift YOK)")
        for k, v in by_key.items():
            print(f"       - (platform={k[0]}, ct={k[1]}) → {v} satır "
                  f"{'✅' if v == 1 else '❌ ÇİFT!'}")
        if cnt2 != len(platforms):
            failures.append(
                f"A.3 ikinci resume sonrası {cnt2} satır — IDEMPOTENCY KIRIK "
                f"(çift draft! {len(platforms)} olmalıydı)")
        dup_keys = [k for k, v in by_key.items() if v != 1]
        if dup_keys:
            failures.append(f"A.3 çift (platform,content_type) anahtarları: {dup_keys}")

    # ── Temizlik ────────────────────────────────────────────────────────────
    cleaned = cleanup_run(run_id) if run_id else {}
    trends_deleted = delete_trend(tid)
    print(f"\n[cleanup] run_id={run_id} → {cleaned} trends_deleted={trends_deleted}")

    ok = not failures
    print("\n" + ("=" * 60))
    if ok:
        print("✅ TEST A PASS — interrupt'ta 0 draft; resume'da platform başına 1; "
              "ikinci resume'da HÂLÂ 1 (idempotency çift draft'ı önledi).")
    else:
        print("❌ TEST A FAIL:")
        for f in failures:
            print("   -", f)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

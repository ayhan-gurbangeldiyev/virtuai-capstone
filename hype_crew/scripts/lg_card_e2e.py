"""Faz 0 gerçek uçtan-uca kill→resume kanıtı (Cansu, Supabase, dry/pending_review).

İKİ SÜREÇ (gerçek dayanıklılık kanıtı):
  produce: kart graph'ını interrupt_before=['publish'] ile çalıştırır → gerçek kart
           üretilir+render+Supabase upload, checkpoint Postgres'e yazılır, publish'TEN
           ÖNCE durur (= "süreç burada öldü"). thread_id /tmp'ye yazılır.
  resume : YENİ süreç — Postgres checkpoint'ten okur, ainvoke(None) ile publish'i
           çalıştırır. produce TEKRAR ÇALIŞMAZ (no re-LLM, no re-upload). 1 draft yazılır.

Çalıştır:
  cd hype_crew && python -m scripts.lg_card_e2e produce
  cd hype_crew && python -m scripts.lg_card_e2e resume
"""
from __future__ import annotations

import asyncio
import datetime as dt
import json
import sys
import uuid
from pathlib import Path

ACCOUNT = "2b731bf7-8c24-40c5-8237-d348ee822d51"   # Cansu
KIND = "dictionary"
_STATE = Path("/tmp/lg_card_e2e_state.json")


async def _produce() -> int:
    from callbacks.supabase_logger import init_run
    from lg.checkpointer import async_checkpointer
    from lg.card_graph import build, CardState
    from tools.card_scheduler import resolve_persona, cards_publish_enabled

    persona = resolve_persona(ACCOUNT)
    if not persona:
        print("✗ persona yok"); return 1
    publish = cards_publish_enabled()
    print(f"cards_publish_enabled={publish} (False bekleniyor → pending_review, dışarı POST YOK)")
    run_id = init_run(ACCOUNT, trend_id=None, triggered_by="cron", dry_run=not publish)
    thread_id = f"e2e:{uuid.uuid4()}"
    when = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=3)

    async with async_checkpointer() as cp:
        # interrupt_before=['publish'] → produce çalışır, publish'ten ÖNCE durur
        graph = build().compile(checkpointer=cp, interrupt_before=["publish"])
        cfg = {"configurable": {"thread_id": thread_id}}
        init: CardState = {
            "account_id": ACCOUNT, "kind": KIND, "source": "spike",
            "scheduled_at": when.isoformat(), "persona": persona,
            "run_id": run_id, "publish_enabled": publish, "written": False,
        }
        await graph.ainvoke(init, cfg, durability="sync")
        snap = await graph.aget_state(cfg)
        card = (snap.values or {}).get("card") or {}
        print(f"produce sonrası: pending_next={snap.next} written={snap.values.get('written')}")
        print(f"üretilen kart: kind={KIND} image_url={card.get('image_url','?')[:70]}")
        ok = bool(card.get("image_url")) and snap.next == ("publish",)
        _STATE.write_text(json.dumps({"thread_id": thread_id, "run_id": run_id,
                                      "image_url": card.get("image_url")}))
    if ok:
        print(f"\n✅ PRODUCE OK — kart üretildi, checkpoint Postgres'te, publish ÖNCESİ durdu.")
        print(f"   thread={thread_id}\n   Şimdi: python -m scripts.lg_card_e2e resume")
        return 0
    print("\n❌ PRODUCE FAIL"); return 1


async def _resume() -> int:
    from callbacks.supabase_logger import finalize_run
    from lg.checkpointer import async_checkpointer
    from lg.card_graph import build
    from tools.supabase_client import make_supabase

    st = json.loads(_STATE.read_text())
    thread_id, run_id, prod_img = st["thread_id"], st["run_id"], st.get("image_url")
    sb = make_supabase()

    def _draft_count():
        r = sb.table("daily_drafts").select("id", count="exact").eq("hype_run_id", run_id).execute()
        return r.count or 0

    before = _draft_count()
    print(f"resume öncesi draft sayısı (run={run_id[:8]}): {before} (0 bekleniyor)")

    async with async_checkpointer() as cp:
        graph = build().compile(checkpointer=cp)   # interrupt YOK → publish'e devam
        cfg = {"configurable": {"thread_id": thread_id}}
        snap = await graph.aget_state(cfg)
        print(f"checkpoint pending_next={snap.next} (publish bekleniyor)")
        if not snap.next:
            print("✗ resume edilecek pending node yok"); return 1
        result = await graph.ainvoke(None, cfg, durability="sync")   # RESUME
        res_img = (result.get("card") or {}).get("image_url")

    after = _draft_count()
    print(f"resume sonrası draft sayısı: {after} (3 bekleniyor = ig+tw+li, tek kart)")
    same_card = (res_img == prod_img)   # produce TEKRAR çalışmadı → image_url AYNI
    print(f"kart image_url produce ile AYNI mı (re-render YOK kanıtı): {same_card}")

    try:
        finalize_run(run_id, status="completed", started_at_ts=dt.datetime.now().timestamp(),
                     flow_state={"run_kind": "cards", "card_source": "spike", "card_count": 1})
    except Exception as e:  # noqa: BLE001
        print(f"(finalize uyarı: {e})")

    ok = (before == 0 and after == 3 and same_card and result.get("written"))
    if ok:
        print("\n✅ RESUME OK — produce TEKRAR ÇALIŞMADI (aynı kart), publish devam etti, 3 draft yazıldı.")
        print("   → 'çöken run kaldığı yerden, ödeme/üretimi tekrarlamadan devam eder' GERÇEK veriyle kanıtlandı.")
        return 0
    print(f"\n❌ RESUME FAIL — before={before} after={after} same_card={same_card} written={result.get('written')}")
    return 1


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "produce":
        return asyncio.run(_produce())
    if mode == "resume":
        return asyncio.run(_resume())
    print("kullanım: python -m scripts.lg_card_e2e [produce|resume]"); return 2


if __name__ == "__main__":
    raise SystemExit(main())

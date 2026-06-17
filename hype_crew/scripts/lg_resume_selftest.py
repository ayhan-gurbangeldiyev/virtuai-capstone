"""LangGraph resume mekanizması self-test'i — secret/Supabase/LLM GEREKMEZ.

Kanıtlamak istediğimiz tek şey: checkpoint sonrası süreç çökerse, RESUME'da
TAMAMLANMIŞ node TEKRAR ÇALIŞMAZ; yalnız kesilen node devam eder ve state korunur.
Bu, kart/ana flow'da "çöken run kaldığı yerden, ödeme yan-etkisini tekrarlamadan
devam eder" güvencesinin çekirdek mekanizmasıdır.

Senaryo: produce(node_a) → publish(node_b). İlk koşuda node_b bilerek çöker
(checkpoint node_a'dan SONRA atılmıştır). Düzeltip resume edince node_a ATLANIR.

Çalıştır:  cd hype_crew && python -m scripts.lg_resume_selftest
"""
from __future__ import annotations

import asyncio
import uuid
from typing import TypedDict

CALLS = {"produce": 0, "publish": 0}
FAIL_PUBLISH = {"on": True}   # ilk koşuda publish çöksün (crash simülasyonu)


class S(TypedDict, total=False):
    produced: bool
    published: bool
    value: int


async def node_produce(s: S) -> dict:
    # gerçek graph'taki resume-skip deseni (idempotency)
    if s.get("produced"):
        return {}
    CALLS["produce"] += 1
    return {"produced": True, "value": 42}


async def node_publish(s: S) -> dict:
    if s.get("published"):
        return {}
    CALLS["publish"] += 1
    if FAIL_PUBLISH["on"]:
        raise RuntimeError("SİMÜLE ÇÖKME: publish öncesi süreç öldü")
    return {"published": True}


async def main() -> int:
    from lg.checkpointer import async_checkpointer
    from langgraph.graph import StateGraph, START, END

    async with async_checkpointer("") as cp:   # "" → lokal SQLite (secret yok)
        g = StateGraph(S)
        g.add_node("produce", node_produce)
        g.add_node("publish", node_publish)
        g.add_edge(START, "produce")
        g.add_edge("produce", "publish")
        g.add_edge("publish", END)
        graph = g.compile(checkpointer=cp)

        tid = f"selftest:{uuid.uuid4()}"
        cfg = {"configurable": {"thread_id": tid}}

        print("1) İlk koşu (publish çökecek)...")
        try:
            await graph.ainvoke({}, cfg, durability="sync")
            print("   ✗ beklenmiyordu: çökme olmadı")
            return 1
        except RuntimeError as e:
            print(f"   ✓ beklenen çökme: {e}")

        snap = await graph.aget_state(cfg)
        print(f"   çökme sonrası: pending_next={snap.next} produced={snap.values.get('produced')} value={snap.values.get('value')}")
        assert snap.next, "checkpoint pending node tutmuyor — resume imkânsız"
        assert snap.values.get("produced") is True, "produce state checkpoint'e yazılmamış"

        print("2) Düzelt + RESUME (ainvoke(None))...")
        FAIL_PUBLISH["on"] = False
        result = await graph.ainvoke(None, cfg, durability="sync")
        print(f"   resume sonucu: {dict(result)}")
        print(f"   çağrı sayıları: {CALLS}")

        ok = (CALLS["produce"] == 1 and result.get("produced") and result.get("published"))
        if ok:
            print("\n✅ PASS — produce TEK KEZ çalıştı (resume'da atlandı), state korundu, publish devam etti.")
            print("   → 'çöken run, tamamlanan adımı tekrarlamadan devam eder' kanıtlandı.")
            return 0
        print(f"\n❌ FAIL — produce {CALLS['produce']} kez çalıştı (1 olmalıydı).")
        return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

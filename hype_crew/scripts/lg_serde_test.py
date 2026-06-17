"""Faz 1 deterministik de-risk testleri (LLM/maliyet YOK).

Risk agent'ının skip-path parity'sinin KAPSAMADIĞINI söylediği iki sınıfı kanıtlar:

TEST 1 — Populated nested-state SERDE + R6 kalıcılık (çapraz-process):
  Dolu bir HypeFlowState (trend+plan + R6 cache'leri dolu) checkpointer'a yazılır,
  AYRI bir checkpointer/graph örneğiyle (resume-process simülasyonu) geri okunur.
  Kanıt: nested pydantic (TrendScoutOutput/PlannerOutput) kayıpsız round-trip +
  trend_raw_content_cache RESUME'da KORUNUR (R6 fix → olgu-uydurma koruması ayakta).

TEST 2 — sync graph içinde asyncio.run() adacığı (R1):
  graph.invoke (SYNC) altında node içinde asyncio.run() çağrısı patlamamalı
  ("event loop already running" YOK). write/visual/video/publish'in async adacıkları
  bu desene dayanıyor.

Çalıştır:  cd hype_crew && python -m scripts.lg_serde_test
"""
from __future__ import annotations

import asyncio
import uuid


def test_serde_and_r6() -> bool:
    from lg.checkpointer import sync_checkpointer
    from langgraph.graph import StateGraph, START, END
    from flow import HypeFlowState
    from schemas import TrendScoutOutput, PlannerOutput

    trend = TrendScoutOutput(trend_id="t-serde-1", topic="Test Lansmanı", score=90,
                             category="model_launch", urgency_hours=12, reasoning="serde testi")
    plan = PlannerOutput(etki="patlassin", karakter="haberci", uzunluk="punch",
                         brief="serde testi için yeterince uzun bir brief metni burada yer alıyor")
    SRC = "## KAYNAK METİN: gerçek haber gövdesi — olgu-uydurma koruması bu metne dayanır."
    full = HypeFlowState(
        account_id="acc-serde", run_id="run-serde", triggered_by="manual", dry_run=True,
        trend=trend, plan=plan,
        trend_raw_content_cache={"t-serde-1": SRC},
        trend_source_url_cache={"t-serde-1": "https://example.com/haber"},
        editor_decision="editors_desk_pick", editor_decision_error=None,
    )

    def _passthrough(state):  # tüm alanları kanal'a yaz (full-replace deseni)
        return {k: getattr(state, k) for k in type(state).model_fields}

    g = StateGraph(HypeFlowState)
    g.add_node("n", _passthrough)
    g.add_edge(START, "n"); g.add_edge("n", END)

    tid = f"serde:{uuid.uuid4().hex}"
    cfg = {"configurable": {"thread_id": tid}}

    # process-sim 1: yaz (durability=sync → Postgres'e serialize)
    with sync_checkpointer() as cp:
        graph = g.compile(checkpointer=cp)
        graph.invoke(full, cfg, durability="sync")

    # process-sim 2: TAZE checkpointer/graph → storage'dan oku (deserialize = resume)
    with sync_checkpointer() as cp2:
        graph2 = g.compile(checkpointer=cp2)
        snap = graph2.get_state(cfg)
        v = snap.values
        def _get(key):
            return v[key] if isinstance(v, dict) else getattr(v, key)
        rc = _get("trend_raw_content_cache")
        su = _get("trend_source_url_cache")
        tr = _get("trend")
        pl = _get("plan")
        tr_topic = tr["topic"] if isinstance(tr, dict) else tr.topic
        tr_score = tr["score"] if isinstance(tr, dict) else tr.score
        pl_etki = pl["etki"] if isinstance(pl, dict) else pl.etki

    ok_cache = rc.get("t-serde-1") == SRC                  # R6: kaynak metin RESUME'da korundu
    ok_url = su.get("t-serde-1") == "https://example.com/haber"
    ok_trend = tr_topic == "Test Lansmanı" and tr_score == 90   # nested model kayıpsız
    ok_plan = pl_etki == "patlassin"
    print(f"  R6 raw_content_cache korundu: {ok_cache}")
    print(f"  source_url_cache korundu: {ok_url}")
    print(f"  nested TrendScoutOutput kayıpsız: {ok_trend}")
    print(f"  nested PlannerOutput kayıpsız: {ok_plan}")
    return ok_cache and ok_url and ok_trend and ok_plan


def test_async_island() -> bool:
    from lg.checkpointer import sync_checkpointer
    from langgraph.graph import StateGraph, START, END
    from typing import TypedDict

    class S(TypedDict, total=False):
        done: bool

    async def _inner():
        await asyncio.sleep(0)
        return 42

    def node(s):
        # write/visual/video/publish'in içindeki desen: SYNC node içinde asyncio.run()
        val = asyncio.run(_inner())
        return {"done": val == 42}

    g = StateGraph(S)
    g.add_node("n", node)
    g.add_edge(START, "n"); g.add_edge("n", END)

    with sync_checkpointer() as cp:
        graph = g.compile(checkpointer=cp)
        r = graph.invoke({}, {"configurable": {"thread_id": f"async:{uuid.uuid4().hex}"}},
                         durability="sync")
    ok = bool(r.get("done"))
    print(f"  sync graph içinde asyncio.run() OK ('event loop already running' yok): {ok}")
    return ok


def main() -> int:
    print("TEST 1 — populated nested-state serde + R6 kalıcılık (çapraz-process)...")
    t1 = test_serde_and_r6()
    print(f"  → {'PASS' if t1 else 'FAIL'}\n")
    print("TEST 2 — sync graph içinde asyncio.run() adacığı (R1)...")
    t2 = test_async_island()
    print(f"  → {'PASS' if t2 else 'FAIL'}\n")
    if t1 and t2:
        print("✅ İKİSİ DE PASS — nested serde + R6 cache kalıcılığı + async-ada doğrulandı.")
        return 0
    print("❌ FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

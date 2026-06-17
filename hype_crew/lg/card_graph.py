"""Faz 0 SPIKE — kart pipeline'ının LangGraph + checkpoint/resume portu.

Amaç: durability/resume mekanizmasını DÜŞÜK blast-radius'lu, izole kart
pipeline'ında ispatlamak. CrewAI/ana flow'a DOKUNMAZ.

Graph (2 node, aralarında checkpoint sınırı):
    START → produce → publish → END
- produce: produce_card() (gen+gate+render) → state["card"]; UI stage'leri
  (icerik/card_gate/render) yazılır. RESUME'da state["card"] doluysa ATLANIR
  (yeniden LLM üretimi + Supabase upload YOK).
- publish: publish_card_to_postiz (flag açıksa) + write_card_drafts → state["written"].
  RESUME'da state["written"] ise ATLANIR (çift yayın/çift draft YOK).

Telemetri: mevcut init_run/log_stage/finalize_run AYNEN kullanılır → CrewGraph UI
değişmeden çalışır. log_stage idempotency (run_id,stage_order) Faz 2'de eklenecek;
spike'ta resume-skip zaten çift-log'u önler (node atlanınca log da atlanır).

Checkpointer: lg.checkpointer.async_checkpointer() — prod Postgres / dev SQLite.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Optional, TypedDict

from loguru import logger

from callbacks.supabase_logger import finalize_run, init_run
from .checkpointer import async_checkpointer

# Mevcut kart altyapısını AYNEN reuse et (strangler: yeni mantık yok)
from tools.card_scheduler import (
    CARD_PLATFORMS,
    _safe_log,
    cards_publish_enabled,
    produce_card,
    publish_card_to_postiz,
    write_card_drafts,
)


class CardState(TypedDict, total=False):
    account_id: str
    kind: str                 # "dictionary" | "question"
    source: str               # "drought" | "companion" | "spike"
    scheduled_at: str         # ISO (UTC)
    trend_id: Optional[str]
    news_topic: Optional[str]
    news_source: Optional[str]
    persona: dict
    run_id: Optional[str]     # hype_runs.id (telemetri) — caller mint eder, stabil
    publish_enabled: bool
    # üretim çıktıları (checkpoint'e yazılır → resume'da reuse)
    card: Optional[dict]
    produce_failed: bool
    postiz_id: Optional[str]
    written: bool


# ---------------- nodes ----------------
async def node_produce(state: CardState) -> dict:
    # RESUME-SKIP: kart zaten üretildiyse (checkpoint'te) tekrar üretme.
    if state.get("card") or state.get("produce_failed"):
        logger.info("[lg-card] produce ATLANDI (resume — kart zaten var)")
        return {}
    rid = state.get("run_id")
    card = await produce_card(
        state["kind"], state["account_id"],
        news_topic=state.get("news_topic"), news_source=state.get("news_source"),
    )
    if not card:
        _safe_log(rid, 1, "İçerik Üret",
                  {"node": "icerik", "kind": state["kind"], "error": "üretilemedi (gate/LLM)"},
                  status="failed")
        return {"produce_failed": True}
    # UI stage'leri (mevcut _run_card_batch ile birebir aynı şekil)
    _safe_log(rid, 1, "İçerik Üret",
              {"node": "icerik", "card_index": 0, "kind": state["kind"], "main": card["main"],
               "sub": card.get("sub"), "caption": card["caption"], "attempts": card["attempts"]},
              model=card["model"], tokens=card["tokens"], duration_ms=card.get("gen_ms"))
    _safe_log(rid, 2, "Kart Kapısı",
              {"node": "card_gate", "card_index": 0, "ok": True, "reason": card["gate_reason"]},
              duration_ms=card.get("gate_ms"))
    _safe_log(rid, 3, "Render",
              {"node": "render", "card_index": 0, "image_url": card["image_url"]},
              duration_ms=card.get("render_ms"))
    return {"card": card}


async def node_publish(state: CardState) -> dict:
    # RESUME-SKIP: zaten yayınlandı/draft yazıldıysa tekrar yapma (çift post YOK).
    if state.get("written"):
        logger.info("[lg-card] publish ATLANDI (resume — zaten yazıldı)")
        return {}
    card = state.get("card")
    if not card:                       # üretilemedi → publish yok, run'ı kapat
        return {"written": True}
    rid = state.get("run_id")
    persona = state.get("persona") or {}
    publish = bool(state.get("publish_enabled"))
    status = "auto_scheduled" if publish else "pending_review"
    when = dt.datetime.fromisoformat(state["scheduled_at"])
    postiz_id = None
    _p0 = time.perf_counter()
    if publish:
        try:
            postiz_id = publish_card_to_postiz(card=card, scheduled_at=when, persona=persona)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[lg-card] publish hata: {e}")
    publish_ms = int((time.perf_counter() - _p0) * 1000)
    write_card_drafts(
        account_id=state["account_id"], persona=persona, card=card,
        scheduled_at_iso=when.isoformat(), status=status,
        trend_id=state.get("trend_id"), postiz_post_id=postiz_id, hype_run_id=rid,
    )
    _safe_log(rid, 4, "Yayın",
              {"node": "publish", "card_index": 0, "platforms": list(CARD_PLATFORMS),
               "scheduled_at": when.isoformat(), "status": status, "postiz_post_id": postiz_id},
              duration_ms=publish_ms)
    return {"written": True, "postiz_id": postiz_id}


# ---------------- graph ----------------
def build():
    """2-node kart graph'ını kur (compile EDİLMEMİŞ — checkpointer caller'da bağlanır)."""
    from langgraph.graph import StateGraph, START, END
    g = StateGraph(CardState)
    g.add_node("produce", node_produce)
    g.add_node("publish", node_publish)
    g.add_edge(START, "produce")
    g.add_edge("produce", "publish")
    g.add_edge("publish", END)
    return g


async def run_card_graph(account_id: str, kind: str, *, source: str,
                         scheduled_at: dt.datetime, persona: dict,
                         trend_id=None, news_topic: Optional[str] = None,
                         news_source: Optional[str] = None,
                         run_id: Optional[str] = None,
                         thread_id: Optional[str] = None) -> CardState:
    """Tek kartı LangGraph ile çalıştır/RESUME et. thread_id stabil olmalı (resume
    için); verilmezse account+kind+slot'tan deterministik türetilir."""
    publish = cards_publish_enabled()
    thread_id = thread_id or f"card:{account_id}:{kind}:{int(scheduled_at.timestamp())}"

    # run_id (telemetri) caller mint etmezse burada init_run ile üret — ama SADECE
    # taze başlangıçta. Resume'da mevcut checkpoint'teki run_id korunur.
    async with async_checkpointer() as cp:
        graph = build().compile(checkpointer=cp)
        cfg = {"configurable": {"thread_id": thread_id}}
        snap = await graph.aget_state(cfg)
        if snap.next:                       # yarım kalmış → DEVAM ET
            logger.info(f"[lg-card] RESUME thread={thread_id} pending={snap.next}")
            return await graph.ainvoke(None, cfg, durability="sync")
        # taze başlangıç
        if not run_id:
            try:
                run_id = init_run(account_id, trend_id=trend_id,
                                  triggered_by="cron", dry_run=not publish)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[lg-card] init_run hata (kayıtsız): {e}")
        init: CardState = {
            "account_id": account_id, "kind": kind, "source": source,
            "scheduled_at": scheduled_at.isoformat(), "trend_id": trend_id,
            "news_topic": news_topic, "news_source": news_source,
            "persona": persona, "run_id": run_id, "publish_enabled": publish,
            "written": False,
        }
        result = await graph.ainvoke(init, cfg, durability="sync")
        if run_id:
            try:
                finalize_run(run_id, status="completed", started_at_ts=time.time(),
                             trend_id=trend_id,
                             flow_state={"run_kind": "cards", "card_source": source,
                                         "card_count": 1 if result.get("written") else 0,
                                         "cards": ([{"index": 0, "kind": kind,
                                                     "key": (result.get("card") or {}).get("key"),
                                                     "image_url": (result.get("card") or {}).get("image_url")}]
                                                   if result.get("card") else [])})
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[lg-card] finalize_run hata: {e}")
        return result

"""X-ingestion LangGraph kabuğu (async, B1: refresh_all'ı sarar).

`hype_crew/lg/card_graph.py` deseninin ingestion aynası. Tek iş-node'u
`trend_engine.refresh_all()`'ı çağırır (kaynak/mantık DEĞİŞMEZ); LangGraph
yalnızca dayanıklı kabuk: checkpoint (Supabase `langgraph` şeması) + resume +
içerik flow'uyla aynı motor/gözlem dokusu. thread_id = trend_fetch_runs.id.

Flag TREND_INGEST_LANGGRAPH_ENABLED kapalıyken bu modül HİÇ import edilmez
(run_trend_fetch / _run_manual_trend_fetch lazy import eder) → eski yol birebir.

Dürüst not: refresh_all idempotent (tweet_feed + trends upsert) olduğundan
resume marjinal değerli; asıl kazanç motor simetrisi + checkpoint kaydı.
"""
from __future__ import annotations

import logging
from typing import Optional, TypedDict

from .checkpointer import async_checkpointer, using_postgres

logger = logging.getLogger(__name__)


class IngestState(TypedDict, total=False):
    run_id: str
    triggered_by: str
    twitter_items: Optional[int]
    trends_saved: Optional[int]
    ok: bool
    finished: bool


async def node_refresh(state: IngestState) -> dict:
    """Tek iş-node'u: refresh_all sar. Resume-skip: zaten bittiyse tekrar koşma."""
    if state.get("finished"):
        logger.info("[lg-ingest] refresh SKIPPED (resume — already finished)")
        return {}
    from services.trend_engine import trend_engine
    result = await trend_engine.refresh_all()
    r = result if isinstance(result, dict) else {}
    return {
        "twitter_items": r.get("twitter_items"),
        "trends_saved": r.get("trends_saved"),
        "ok": bool(r.get("success", True)),
        "finished": True,
    }


def build():
    """START → refresh → END (uncompiled; çağıran checkpointer bağlar)."""
    from langgraph.graph import StateGraph, START, END
    g = StateGraph(IngestState)
    g.add_node("refresh", node_refresh)
    g.add_edge(START, "refresh")
    g.add_edge("refresh", END)
    return g


async def run_or_resume_ingest(run_id: str, triggered_by: str = "cron") -> dict:
    """Trend fetch'i LangGraph kabuğunda koş/resume et. run_id = trend_fetch_runs.id
    (thread_id). Dönüş refresh_all ile uyumlu dict (twitter_items/trends_saved/success)."""
    async with async_checkpointer() as cp:
        graph = build().compile(checkpointer=cp)
        cfg = {"configurable": {"thread_id": str(run_id)}}
        snap = await graph.aget_state(cfg)
        if snap.next:
            logger.info(f"[lg-ingest] RESUME thread={run_id} pending={snap.next}")
            result = await graph.ainvoke(None, cfg, durability="sync")
        else:
            logger.info(f"[lg-ingest] FRESH thread={run_id} (postgres={using_postgres()})")
            init: IngestState = {"run_id": str(run_id), "triggered_by": triggered_by}
            result = await graph.ainvoke(init, cfg, durability="sync")

    result = result if isinstance(result, dict) else {}
    return {
        "success": bool(result.get("ok", True)),
        "twitter_items": result.get("twitter_items"),
        "trends_saved": result.get("trends_saved"),
        "via": "langgraph",
    }

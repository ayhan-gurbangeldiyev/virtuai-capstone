"""Supabase Postgres checkpointer bağlantı testi (gerçek DB, secret .env'den).

Kanıtlar: (1) pooler bağlantısı + search_path=langgraph çalışıyor, (2) setup()
checkpoint tablolarını langgraph şemasına kuruyor, (3) bir stub graph checkpoint'i
gerçekten Postgres'e yazılıp geri okunuyor (resume zemini).

Çalıştır:  cd hype_crew && python -m scripts.lg_pg_conntest
"""
from __future__ import annotations

import asyncio
import uuid
from typing import TypedDict


class S(TypedDict, total=False):
    a: bool
    b: bool


async def na(s: S) -> dict:
    return {"a": True}


async def nb(s: S) -> dict:
    return {"b": True}


async def main() -> int:
    from lg.checkpointer import async_checkpointer, using_postgres
    from langgraph.graph import StateGraph, START, END

    if not using_postgres():
        print("✗ HYPE_CHECKPOINT_DB_URL boş — Postgres testi yapılamaz")
        return 1

    async with async_checkpointer() as cp:   # arg yok → settings'ten Postgres URL
        g = StateGraph(S)
        g.add_node("a", na); g.add_node("b", nb)
        g.add_edge(START, "a"); g.add_edge("a", "b"); g.add_edge("b", END)
        graph = g.compile(checkpointer=cp)

        tid = f"conntest:{uuid.uuid4()}"
        cfg = {"configurable": {"thread_id": tid}}
        result = await graph.ainvoke({}, cfg, durability="sync")
        print("invoke sonucu:", dict(result))

        snap = await graph.aget_state(cfg)
        ok = bool(snap.values.get("a") and snap.values.get("b")) and not snap.next
        print(f"checkpoint geri okundu: a={snap.values.get('a')} b={snap.values.get('b')} next={snap.next}")

        # tablolar hangi şemada?
        async with cp.conn.connection() as c:  # pool'dan bir bağlantı
            cur = await c.execute(
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_name IN ('checkpoints','checkpoint_blobs','checkpoint_writes','checkpoint_migrations') "
                "ORDER BY table_name"
            )
            rows = await cur.fetchall()
        print("checkpoint tabloları:", [(r["table_schema"], r["table_name"]) for r in rows])
        schemas = {r["table_schema"] for r in rows}

    if ok and schemas == {"langgraph"}:
        print("\n✅ PASS — Supabase Postgres checkpointer çalışıyor; tablolar langgraph şemasında; checkpoint yazıldı/okundu.")
        return 0
    print(f"\n❌ FAIL — ok={ok} şemalar={schemas} (langgraph bekleniyordu)")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

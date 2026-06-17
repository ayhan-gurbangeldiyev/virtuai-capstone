"""LangGraph checkpointer factory.

Tek karar noktası: `HYPE_CHECKPOINT_DB_URL` (settings.checkpoint_db_url) doluysa
**PostgresSaver** (prod — Supabase'in `langgraph` şeması); boşsa **AsyncSqliteSaver**
(dev/spike — secret gerekmez, lokal dosya). Resume mekanizması her iki backend'de
birebir aynı; yalnız kalıcılık katmanı farklı.

Kullanım:
    async with async_checkpointer() as cp:
        graph = build().compile(checkpointer=cp)
        await graph.ainvoke(state, config={"configurable": {"thread_id": run_id}})

Not (prod): HYPE_CHECKPOINT_DB_URL conn string'i `langgraph` şemasına izole etmek
için search_path option'ı taşımalı, ör:
    postgresql://USER:PASS@HOST:5432/postgres?options=-c%20search_path%3Dlanggraph
Böylece PostgresSaver.setup() checkpoint tablolarını public.* yerine langgraph.*'a kurar.
"""
from __future__ import annotations

from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from loguru import logger

# Dev/spike checkpoint dosyası (repo dışına yazılmaz; .gitignore'a eklenmeli)
_SQLITE_PATH = str(Path(__file__).parent / "_checkpoints_dev.sqlite")


def _resolve_db_url() -> str:
    try:
        from config import settings
        return (getattr(settings, "checkpoint_db_url", "") or "").strip()
    except Exception:  # noqa: BLE001
        import os
        return (os.environ.get("HYPE_CHECKPOINT_DB_URL", "") or "").strip()


_SCHEMA = "langgraph"

# Footgun A fix: nested pydantic modellerimizi msgpack allowlist'e kaydet. Aksi halde
# "Deserializing unregistered type ... will be blocked in a future version" uyarısı +
# LANGGRAPH_STRICT_MSGPACK=true olursa deserialize BLOKLANIR (state nested objeleri
# bozulur). (module, classname) string-tuple formatı → flow/schemas import etmeden,
# coupling yaratmadan kaydeder.
_ALLOWED_MSGPACK = [
    ("schemas.trend", "TrendScoutOutput"),
    ("schemas.plan", "PlannerOutput"),
    ("schemas.draft", "WriterOutput"),
    ("schemas.draft", "ComplianceOutput"),
    ("schemas.publish", "PublisherOutput"),
    ("schemas.publish", "FlowState"),
    ("schemas.visual", "VisualDirectorOutput"),
    ("flow", "HypeFlowState"),
    ("flow", "PlatformDraft"),
    ("flow", "VideoOutput"),
]


def _make_serde():
    """allowlist-kayıtlı JsonPlusSerializer — nested modeller uyarısız + strict-güvenli."""
    try:
        from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
        return JsonPlusSerializer(allowed_msgpack_modules=_ALLOWED_MSGPACK)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[lg] serde allowlist kurulamadı (permissive default): {e}")
        return None


async def _configure_conn(conn) -> None:
    """Her yeni bağlantıda şema izolasyonu — pooler URL'deki `options`'ı yutsa bile
    checkpoint tabloları/sorguları kesin `langgraph` şemasına gider."""
    await conn.execute(f"SET search_path TO {_SCHEMA}, public")


@asynccontextmanager
async def async_checkpointer(db_url: str | None = None):
    """Async checkpointer context manager. db_url verilmezse settings'ten çözülür.
    Postgres (prod) → explicit AsyncConnectionPool + search_path=langgraph +
    prepare_threshold=0 (Supabase session pooler uyumu). Boş → SQLite (dev/spike)."""
    url = db_url if db_url is not None else _resolve_db_url()
    if url:
        from psycopg.rows import dict_row
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncConnectionPool(
            conninfo=url, max_size=5, open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            configure=_configure_conn,
        ) as pool:
            cp = AsyncPostgresSaver(pool, serde=_make_serde())
            await cp.setup()  # idempotent — checkpoint tablolarını langgraph.* altına kurar
            logger.info("[lg] PostgresSaver checkpointer aktif (Supabase, langgraph şeması)")
            yield cp
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(_SQLITE_PATH) as cp:
            logger.info(f"[lg] SQLite checkpointer aktif (dev/spike): {_SQLITE_PATH}")
            yield cp


def _configure_conn_sync(conn) -> None:
    """SYNC eşdeğeri: her yeni bağlantıda şema izolasyonu — checkpoint
    tabloları/sorguları kesin `langgraph` şemasına gider (pooler URL'deki
    `options` yutulsa bile)."""
    conn.execute(f"SET search_path TO {_SCHEMA}, public")


@contextmanager
def sync_checkpointer(db_url: str | None = None):
    """SYNC checkpointer context manager — async_checkpointer'ın birebir SYNC
    aynası. Ana flow node'ları içinde `asyncio.run()` adacıkları (write batch,
    video, visual, publish) olduğundan graph SYNC çalışmak ZORUNDA (graph.invoke,
    ainvoke DEĞİL) → dış event-loop olmamalı. Bu da SYNC checkpointer gerektirir.

    Postgres (prod) → explicit ConnectionPool + search_path=langgraph +
    prepare_threshold=0 (Supabase session pooler uyumu). Boş → SQLite (dev/spike).
    db_url verilmezse settings'ten çözülür."""
    url = db_url if db_url is not None else _resolve_db_url()
    if url:
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver
        with ConnectionPool(
            conninfo=url, max_size=5, open=False,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            configure=_configure_conn_sync,
        ) as pool:
            cp = PostgresSaver(pool, serde=_make_serde())
            cp.setup()  # idempotent — checkpoint tablolarını langgraph.* altına kurar
            logger.info("[lg] PostgresSaver (sync) checkpointer aktif (Supabase, langgraph şeması)")
            yield cp
    else:
        from langgraph.checkpoint.sqlite import SqliteSaver
        with SqliteSaver.from_conn_string(_SQLITE_PATH) as cp:
            logger.info(f"[lg] SqliteSaver (sync) checkpointer aktif (dev/spike): {_SQLITE_PATH}")
            yield cp


def using_postgres() -> bool:
    """Prod (Postgres) modunda mıyız? (gözlem/log için)."""
    return bool(_resolve_db_url())

"""LangGraph checkpointer factory (backend / X-ingestion).

`hype_crew/lg/checkpointer.py`'nin backend portu. Tek karar noktası:
`HYPE_CHECKPOINT_DB_URL` doluysa **AsyncPostgresSaver** (prod — Supabase'in
`langgraph` şeması, içerik flow'uyla AYNI checkpoint deposu); boşsa
**AsyncSqliteSaver** (dev/spike — secret gerekmez, lokal dosya).

Backend'de merkezi `config.settings` YOK → URL doğrudan os.environ'dan okunur.
Ingestion state'i basit TypedDict (str/int/dict) olduğu için serde allowlist
GEREKMEZ (içerik tarafındaki nested-pydantic allowlist'i buraya taşınmadı).

Conn string `langgraph` şemasına izole olmalı (search_path); _configure_conn
her bağlantıda bunu garantiler (pooler URL'deki `options` yutulsa bile).
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA = "langgraph"
_SQLITE_PATH = str(Path(__file__).parent / "_checkpoints_dev.sqlite")


def _resolve_db_url() -> str:
    return (os.environ.get("HYPE_CHECKPOINT_DB_URL", "") or "").strip()


async def _configure_conn(conn) -> None:
    """Her yeni bağlantıda şema izolasyonu — checkpoint tabloları/sorguları
    kesin `langgraph` şemasına gider (pooler URL'deki `options` yutulsa bile)."""
    await conn.execute(f"SET search_path TO {_SCHEMA}, public")


@asynccontextmanager
async def async_checkpointer(db_url: str | None = None):
    """Async checkpointer context manager. db_url verilmezse env'den çözülür.
    Postgres (prod) → AsyncConnectionPool + search_path=langgraph +
    prepare_threshold=0 (Supabase session pooler uyumu). Boş → SQLite (dev)."""
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
            cp = AsyncPostgresSaver(pool)
            await cp.setup()  # idempotent — checkpoint tablolarını langgraph.* altına kurar
            logger.info("[lg-ingest] PostgresSaver checkpointer aktif (Supabase, langgraph şeması)")
            yield cp
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        async with AsyncSqliteSaver.from_conn_string(_SQLITE_PATH) as cp:
            logger.info(f"[lg-ingest] SQLite checkpointer aktif (dev/spike): {_SQLITE_PATH}")
            yield cp


def using_postgres() -> bool:
    """Prod (Postgres) modunda mıyız? (gözlem/log için)."""
    return bool(_resolve_db_url())

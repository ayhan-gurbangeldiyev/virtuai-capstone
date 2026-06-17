"""Async Postgres checkpointer for LangGraph durable state."""
from __future__ import annotations

from loguru import logger
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from .config import settings


async def build_pool() -> AsyncConnectionPool:
    """Open psycopg async pool against Supabase Postgres.

    Critical: prepare_threshold=0 is mandatory on Supabase pooler (port 6543
    breaks prepared statements; even 5432 session pooler can flake otherwise).
    autocommit=True needed because LangGraph manages its own txns.
    max_lifetime=3600 recycles connections hourly.
    """
    if not settings.supabase_db_url:
        raise RuntimeError("SUPABASE_DB_URL is not set")
    pool = AsyncConnectionPool(
        conninfo=settings.supabase_db_url,
        min_size=settings.pool_min,
        max_size=settings.pool_max,
        max_lifetime=3600,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
        open=False,
    )
    await pool.open()
    logger.info(f"psycopg pool opened (min={settings.pool_min}, max={settings.pool_max})")
    return pool


async def build_checkpointer(pool: AsyncConnectionPool):
    """Construct AsyncPostgresSaver and run idempotent setup().

    setup() creates 4 tables: checkpoints, checkpoint_blobs,
    checkpoint_writes, checkpoint_migrations.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    checkpointer = AsyncPostgresSaver(pool)
    await checkpointer.setup()
    logger.info("LangGraph AsyncPostgresSaver setup complete")
    return checkpointer

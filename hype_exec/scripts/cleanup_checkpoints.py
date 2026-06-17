"""Weekly cleanup — delete LangGraph checkpoints older than 30 days.

Removes rows from `checkpoints` and `checkpoint_writes`. Triggers cascading
delete from `checkpoint_blobs` via FK if defined; otherwise we delete blobs
referenced by purged checkpoints explicitly.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from loguru import logger

from ..checkpointer import build_pool


RETENTION_DAYS = 30


async def main() -> None:
    pool = await build_pool()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).isoformat()
    try:
        async with pool.connection() as conn:
            # The schema column is `created_at` on `checkpoints` in langgraph-checkpoint-postgres 3.x
            r1 = await conn.execute(
                "DELETE FROM checkpoint_writes WHERE thread_id IN (SELECT thread_id FROM checkpoints WHERE created_at < %s)",
                (cutoff,),
            )
            r2 = await conn.execute(
                "DELETE FROM checkpoint_blobs WHERE thread_id IN (SELECT thread_id FROM checkpoints WHERE created_at < %s)",
                (cutoff,),
            )
            r3 = await conn.execute("DELETE FROM checkpoints WHERE created_at < %s", (cutoff,))
            logger.info(
                f"cleanup: deleted writes={r1.rowcount} blobs={r2.rowcount} checkpoints={r3.rowcount} (older than {RETENTION_DAYS}d)"
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())

"""Trend source management — user-facing API for the X account list that
feeds the trends pipeline.

Endpoints:
  GET    /trends/sources                  — list all sources grouped by batch
  POST   /trends/sources                  — add a new X account to a batch
  DELETE /trends/sources/{source_id}      — remove a source
  PATCH  /trends/sources/{source_id}/toggle — activate/deactivate without deleting

These replace the hardcoded BATCHES dict in twitter_trend_fetcher.py.
The fetcher reads from this table at runtime; if the DB is unreachable it
falls back to the hardcoded dict to avoid pipeline downtime.
"""
import logging
import re
from typing import Optional, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from middleware.auth import require_auth

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trends/sources", tags=["trends-sources"])


def get_supabase():
    from server import supabase
    return supabase


BatchType = Literal[
    "ai_core",        # official labs (OpenAI / Anthropic / Google / etc.)
    "ai_news_en",     # English-language AI curators (Stage 2 Step 1)
    "ai_news_tr",     # Turkish-language AI commentators
    "ai_tech",        # legacy mixed batch (inactive in DB; kept for back-compat)
    "tr_haber",       # legacy general TR news (inactive)
    "spor",           # legacy sports (inactive)
]
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{1,30}$")
_DEFAULT_LIMIT_BY_BATCH = {
    "ai_core":    50,
    "ai_news_en": 30,
    "ai_news_tr": 30,
    "ai_tech":    50,
    "tr_haber":   40,
    "spor":       30,
}


class AddSourceBody(BaseModel):
    batch_type: BatchType
    username: str = Field(..., min_length=1, max_length=32)
    fetch_limit: Optional[int] = Field(None, ge=1, le=200)


@router.get("")
async def list_sources(user=Depends(require_auth)):
    """All X source accounts grouped by batch_type. Each batch is a flat list."""
    sb = get_supabase()
    rows = (
        sb.table("trend_x_sources")
        .select("id, batch_type, username, is_active, fetch_limit, created_at, updated_at")
        .order("batch_type")
        .order("username")
        .execute()
    )
    # Display in source-priority order: live AI batches first, legacy last.
    grouped: dict[str, list] = {
        "ai_core":    [],
        "ai_news_en": [],
        "ai_news_tr": [],
        "ai_tech":    [],   # legacy / inactive
        "tr_haber":   [],   # legacy / inactive
        "spor":       [],   # legacy / inactive
    }
    for r in rows.data or []:
        bt = r.get("batch_type")
        if bt in grouped:
            grouped[bt].append(r)
    return {"sources": grouped, "total": len(rows.data or [])}


@router.post("")
async def add_source(body: AddSourceBody, user=Depends(require_auth)):
    """Add an X handle to a batch. Strips leading @ and validates handle format."""
    handle = body.username.lstrip("@").strip()
    if not _HANDLE_RE.fullmatch(handle):
        raise HTTPException(status_code=400, detail="invalid handle")

    sb = get_supabase()
    fetch_limit = body.fetch_limit or _DEFAULT_LIMIT_BY_BATCH.get(body.batch_type, 50)
    try:
        result = (
            sb.table("trend_x_sources")
            .insert({
                "batch_type": body.batch_type,
                "username": handle,
                "fetch_limit": fetch_limit,
            })
            .execute()
        )
    except Exception as e:
        msg = str(e).lower()
        if "duplicate" in msg or "unique" in msg or "23505" in msg:
            raise HTTPException(status_code=409, detail="already exists")
        logger.error(f"add_source error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="insert failed")
    return (result.data or [None])[0]


@router.delete("/{source_id}")
async def remove_source(source_id: str, user=Depends(require_auth)):
    sb = get_supabase()
    sb.table("trend_x_sources").delete().eq("id", source_id).execute()
    return {"deleted": source_id}


@router.patch("/{source_id}/toggle")
async def toggle_active(source_id: str, user=Depends(require_auth)):
    """Soft-disable a source without removing it from the list."""
    sb = get_supabase()
    row = (
        sb.table("trend_x_sources")
        .select("is_active")
        .eq("id", source_id)
        .limit(1)
        .execute()
    )
    if not row.data:
        raise HTTPException(status_code=404, detail="source not found")
    new_state = not row.data[0]["is_active"]
    sb.table("trend_x_sources").update({
        "is_active": new_state,
    }).eq("id", source_id).execute()
    return {"id": source_id, "is_active": new_state}

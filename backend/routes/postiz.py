"""Phase 36 — Postiz Social Media Manager API.

User-facing endpoints that let the TypeHype UI manage every Postiz post
without sending the user to Postiz's own dashboard.

Endpoints:
    GET    /api/postiz/posts                 list posts (status/platform filter)
    POST   /api/postiz/posts                 create + schedule (multi-platform)
    GET    /api/postiz/posts/{id}            get one post detail
    PUT    /api/postiz/posts/{id}            edit (Postiz POST /posts type=update)
    POST   /api/postiz/posts/{id}/cancel     cancel/delete a scheduled post
    DELETE /api/postiz/posts/{id}            same as cancel (REST sugar)
    GET    /api/postiz/integrations          list connected channels
    GET    /api/postiz/slot                  next free schedule slot
    POST   /api/postiz/upload                upload media from a public URL
"""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# Re-use Hype Crew's PostizClient (already mounted under /opt/hype-crew on
# Hetzner). Same import strategy as backend/routes/hype.py.
for _hype_path in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
    if _hype_path not in sys.path:
        sys.path.insert(0, _hype_path)

try:
    # Phase 1 — direct Postiz API endpoint also goes through the guarded
    # wrapper. The /postiz/posts schedule endpoint accepts raw PlatformPost
    # bodies from the UI without a draft_id, so it can't gate against
    # source raw_content. That endpoint stays available to the UI for
    # manual edits, but it's now restricted to operate ONLY through the
    # guarded subclass; the wrapper will refuse without gate outcomes,
    # forcing this endpoint to be the explicit "I'm the operator, bypass"
    # path. The CI test allowlists this single bypass behind a clearly-
    # labeled operator confirmation.
    from tools.postiz_client import PlatformPost  # type: ignore
    from tools.guarded_postiz import (  # type: ignore
        GuardedPostizClient as PostizClient,
        assert_publishable as _assert_publishable_direct,
        GuardedPublishRefused,
    )
except Exception as e:  # pragma: no cover — only fires on local dev without hype_crew
    PostizClient = None  # type: ignore[assignment]
    PlatformPost = None  # type: ignore[assignment]
    _assert_publishable_direct = None  # type: ignore[assignment]
    GuardedPublishRefused = Exception  # type: ignore[assignment]
    _IMPORT_ERROR = str(e)
else:
    _IMPORT_ERROR = None

from middleware.auth import require_auth  # type: ignore


def get_supabase():
    """Late-import the shared supabase client so this module doesn't pull
    server at import time (same pattern as routes/hype.py)."""
    from server import supabase
    return supabase


logger = logging.getLogger("postiz_api")

router = APIRouter(prefix="/postiz", tags=["postiz"])


def _client() -> Any:
    """Return a PostizClient instance or raise 503 when offline."""
    if PostizClient is None:
        raise HTTPException(
            503,
            f"Postiz integration not available (server config). {_IMPORT_ERROR or ''}",
        )
    api_key = os.getenv("POSTIZ_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "POSTIZ_API_KEY not configured on server")
    return PostizClient()


# ─── Schemas ──────────────────────────────────────────────────────────────


class MediaRef(BaseModel):
    id: str
    path: Optional[str] = None


class PlatformPostBody(BaseModel):
    integration_id: str = Field(..., description="Postiz integration id (channel)")
    provider: str = Field(..., description="Platform key: x|linkedin|devto|instagram|youtube|...")
    content: str = Field(..., min_length=1)
    title: Optional[str] = None
    tags: Optional[List[str]] = None
    media: Optional[List[MediaRef]] = None


class SchedulePostBody(BaseModel):
    scheduled_at: datetime = Field(..., description="ISO 8601 UTC timestamp")
    posts: List[PlatformPostBody]
    publish_now: bool = Field(False, description="Bypass schedule and publish immediately")


class UpdatePostBody(BaseModel):
    group_id: str = Field(..., description="Existing Postiz group id (returned by list)")
    scheduled_at: datetime
    posts: List[PlatformPostBody]


class UploadFromUrlBody(BaseModel):
    url: str = Field(..., description="Public HTTPS URL to a media file")


class StatusChangeBody(BaseModel):
    status: Literal["draft", "schedule"]


# ─── Helpers ──────────────────────────────────────────────────────────────


def _to_platform_post(b: PlatformPostBody) -> Any:
    """Convert API body → hype_crew PlatformPost dataclass."""
    media_list: Optional[list[dict]] = None
    if b.media:
        media_list = [
            {"id": m.id, "path": m.path or ""}
            for m in b.media
        ]
    return PlatformPost(
        integration_id=b.integration_id,
        provider=b.provider,
        content=b.content,
        title=b.title,
        tags=b.tags,
        media=media_list,
    )


def _normalize_post(p: dict) -> dict:
    """Massage Postiz post payload into a UI-friendly shape.

    Postiz returns deeply nested objects. Flatten the bits the UI needs and
    keep the raw payload available under `_raw` for power-user debugging.
    """
    integration = p.get("integration") or {}
    provider = (
        integration.get("providerIdentifier")
        or integration.get("identifier")
        or p.get("provider")
        or "unknown"
    )
    state = (p.get("state") or p.get("status") or "").upper() or "UNKNOWN"
    status_map = {
        "QUEUE": "scheduled",
        "DRAFT": "draft",
        "PUBLISHED": "published",
        "ERROR": "failed",
        "PROCESSING": "processing",
    }
    publish_date = (
        p.get("publishDate")
        or p.get("publishedAt")
        or p.get("releaseDate")
        or p.get("date")
    )
    release_url = (
        p.get("releaseURL")
        or p.get("release_url")
        or p.get("url")
    )
    return {
        "id": p.get("id") or p.get("_id"),
        "group_id": p.get("group") or p.get("groupId"),
        "platform": provider,
        "status": status_map.get(state, state.lower()),
        "raw_state": state,
        "content": p.get("content") or "",
        "scheduled_at": publish_date,
        "release_url": release_url,
        "integration": {
            "id": integration.get("id"),
            "name": integration.get("name"),
            "picture": integration.get("picture"),
            "identifier": integration.get("providerIdentifier") or integration.get("identifier"),
        },
        "media": p.get("media") or p.get("image") or [],
        "error": p.get("error") or p.get("errorMessage"),
        "_raw": p,
    }


# ─── Endpoints ────────────────────────────────────────────────────────────


@router.get("/posts")
async def list_posts(
    status: Optional[str] = Query(None, description="scheduled|published|failed|draft|all"),
    platform: Optional[str] = Query(None, description="filter by provider identifier"),
    days: int = Query(30, ge=1, le=365, description="window in days (now-days → now+days)"),
    user=Depends(require_auth),
):
    """List Postiz posts in a +/-days window. Filter by status + platform.

    The UI uses this as its primary feed. `scheduled` shows upcoming posts,
    `published` shows past ones, `failed` shows errors needing attention.
    """
    pc = _client()
    now = datetime.now(timezone.utc)
    from datetime import timedelta as _td
    start = (now - _td(days=days)).isoformat()
    end = (now + _td(days=days)).isoformat()
    try:
        raw = pc.list_posts(start_date=start, end_date=end)
    except Exception as e:
        logger.exception("postiz list_posts failed")
        raise HTTPException(502, f"Postiz unreachable: {type(e).__name__}: {str(e)[:200]}")

    items = [_normalize_post(p) for p in (raw or []) if isinstance(p, dict)]
    # ── Enrich with media from daily_drafts (audit 6 Haz 2026): Postiz'
    # public list response does NOT echo the uploaded media reference.
    # The video_url / image_url stay in OUR daily_drafts row (keyed by
    # postiz_post_id). One batch lookup; merge into the response so the
    # frontend sees the video and renders the player.
    try:
        post_ids = [i["id"] for i in items if i.get("id")]
        if post_ids:
            sb = get_supabase()
            dd_rows = (
                sb.table("daily_drafts")
                .select("id, postiz_post_id, video_url, image_url, "
                        "video_thumbnail_url, content_thread_id, content_type")
                .in_("postiz_post_id", post_ids)
                .execute()
                .data
            ) or []
            by_pid = {r["postiz_post_id"]: r for r in dd_rows
                      if isinstance(r, dict) and r.get("postiz_post_id")}
            for it in items:
                row = by_pid.get(it.get("id"))
                if not row:
                    continue
                media = []
                if row.get("video_url"):
                    media.append({
                        "path": row["video_url"],
                        "type": "video",
                        "thumbnail": row.get("video_thumbnail_url"),
                    })
                elif row.get("image_url"):
                    media.append({
                        "path": row["image_url"],
                        "type": "image",
                    })
                if media:
                    it["media"] = media
                it["draft_id"] = row.get("id")
                it["content_thread_id"] = row.get("content_thread_id")
                it["content_type"] = row.get("content_type")
    except Exception as _enr:
        logger.warning(f"[postiz/list] daily_drafts media enrich failed: {_enr!r}")

    if status and status != "all":
        items = [i for i in items if i["status"] == status]
    if platform and platform != "all":
        items = [i for i in items if i["platform"] == platform]

    items.sort(key=lambda i: i.get("scheduled_at") or "", reverse=True)
    return {"items": items, "count": len(items)}


@router.get("/posts/{post_id}")
async def get_post(post_id: str, user=Depends(require_auth)):
    """Fetch one post (used by the edit dialog hydration).

    Postiz' public GET /posts/{id} returns 404 (only the LIST endpoint
    works). We re-implement by scanning the list response and matching
    by id, then enrich with media from our daily_drafts row.
    """
    pc = _client()
    try:
        now = datetime.now(timezone.utc)
        from datetime import timedelta as _td
        raw_list = pc.list_posts(
            start_date=(now - _td(days=30)).isoformat(),
            end_date=(now + _td(days=30)).isoformat(),
        )
    except Exception as e:
        logger.exception("postiz list (for get_post) failed")
        raise HTTPException(502, f"Postiz error: {type(e).__name__}: {str(e)[:200]}")

    raw = next((p for p in (raw_list or [])
                if isinstance(p, dict) and (p.get("id") == post_id)), None)
    if not raw:
        raise HTTPException(404, "Post not found")

    norm = _normalize_post(raw)
    # Enrich single-post with daily_drafts media (same as list_posts)
    try:
        sb = get_supabase()
        dd = (
            sb.table("daily_drafts")
            .select("id, video_url, image_url, video_thumbnail_url, "
                    "content_thread_id, content_type")
            .eq("postiz_post_id", post_id)
            .limit(1)
            .execute()
            .data
        ) or []
        row = (dd or [{}])[0] if dd else {}
        if row:
            media = []
            if row.get("video_url"):
                media.append({
                    "path": row["video_url"],
                    "type": "video",
                    "thumbnail": row.get("video_thumbnail_url"),
                })
            elif row.get("image_url"):
                media.append({"path": row["image_url"], "type": "image"})
            if media:
                norm["media"] = media
            norm["draft_id"] = row.get("id")
            norm["content_thread_id"] = row.get("content_thread_id")
            norm["content_type"] = row.get("content_type")
    except Exception as _enr:
        logger.warning(f"[postiz/get_post] enrich failed: {_enr!r}")

    return {"post": norm, "raw": raw}

# (legacy dual-return form is left below for reference; new return above)
async def _legacy_get_post(post_id: str, user=Depends(require_auth)):
    """deprecated — kept only so old call-sites still parse."""
    pc = _client()
    try:
        raw = pc.get_post_status(post_id)
    except Exception as e:
        if "404" in str(e):
            raise HTTPException(404, "Post not found")
        raise HTTPException(502, f"Postiz error: {type(e).__name__}: {str(e)[:200]}")
    return {"post": _normalize_post(raw), "raw": raw}


@router.post("/posts")
async def schedule(body: SchedulePostBody, user=Depends(require_auth)):
    """DEPRECATED Phase 1 (Berkay 6 Haz 2026 fabrication audit).

    This endpoint accepts raw PlatformPost bodies with no draft_id and no
    source raw_content reference, so the faithfulness gate cannot run.
    Until the UI is updated to send draft ids (so the wrapper can gate
    against the draft's stored source), this endpoint refuses to publish
    — operators must use POST /hype/drafts/{draft_id}/approve or
    POST /hype/drafts/by-thread/{thread_id}/approve, both of which DO
    route through the gate.

    Returns HTTP 410 Gone with a structured message that points the UI
    at the approve endpoints.
    """
    raise HTTPException(
        status_code=410,
        detail={
            "error": "deprecated_endpoint",
            "message": (
                "/postiz/posts cannot be used to schedule directly. "
                "Use /hype/drafts/{draft_id}/approve or "
                "/hype/drafts/by-thread/{thread_id}/approve — both route "
                "through the faithfulness gate before publish."
            ),
        },
    )


@router.put("/posts/{post_id}")
async def update_post(post_id: str, body: UpdatePostBody, user=Depends(require_auth)):
    """Edit a scheduled post (Postiz POST /posts type=update)."""
    pc = _client()
    try:
        platform_posts = [_to_platform_post(b) for b in body.posts]
    except (ValueError, TypeError) as e:
        raise HTTPException(400, f"Invalid post body: {e}")
    try:
        resp = pc.update_post(body.group_id, platform_posts, body.scheduled_at)
    except Exception as e:
        logger.exception("postiz update_post failed")
        raise HTTPException(
            502, f"Postiz update failed: {type(e).__name__}: {str(e)[:300]}"
        )
    return {"ok": True, "postiz_response": resp}


@router.post("/posts/{post_id}/cancel")
@router.delete("/posts/{post_id}")
async def cancel_post(post_id: str, user=Depends(require_auth)):
    """Cancel/delete a scheduled post."""
    pc = _client()
    try:
        ok = pc.cancel_post(post_id)
    except Exception as e:
        logger.exception("postiz cancel_post failed")
        raise HTTPException(502, f"Postiz cancel failed: {type(e).__name__}")
    if not ok:
        raise HTTPException(502, "Postiz did not confirm deletion")
    return {"ok": True}


@router.put("/posts/{post_id}/status")
async def change_status(post_id: str, body: StatusChangeBody, user=Depends(require_auth)):
    """Toggle a post between draft and schedule queue."""
    pc = _client()
    try:
        ok = pc.change_post_status(post_id, body.status)
    except Exception as e:
        raise HTTPException(502, f"Postiz status change failed: {type(e).__name__}")
    return {"ok": ok, "status": body.status}


@router.get("/integrations")
async def list_integrations(user=Depends(require_auth)):
    """List all connected platform channels (UI uses this to populate
    platform pickers, profile pictures, etc.)."""
    pc = _client()
    try:
        raw = pc.list_integrations()
    except Exception as e:
        logger.exception("postiz list_integrations failed")
        raise HTTPException(502, f"Postiz integrations unreachable: {type(e).__name__}")
    items = []
    for i in raw or []:
        if not isinstance(i, dict):
            continue
        items.append({
            "id": i.get("id"),
            "name": i.get("name"),
            "identifier": i.get("identifier") or i.get("providerIdentifier"),
            "picture": i.get("picture"),
            "disabled": bool(i.get("disabled")),
            "profile": i.get("profile"),
        })
    return {"items": items, "count": len(items)}


@router.get("/slot")
async def next_free_slot(
    integration_id: Optional[str] = Query(None),
    user=Depends(require_auth),
):
    """Postiz suggests the next free posting slot (respecting the org's
    posting schedule). Used by the "auto pick time" button in the dialog."""
    pc = _client()
    try:
        data = pc.find_slot(integration_id)
    except Exception as e:
        raise HTTPException(502, f"Postiz find-slot failed: {type(e).__name__}")
    return data


@router.post("/upload")
async def upload_from_url(body: UploadFromUrlBody, user=Depends(require_auth)):
    """Upload a media file to Postiz from a public URL. The returned
    ``{id, path}`` should be passed back as ``MediaRef`` on schedule."""
    pc = _client()
    try:
        ref = pc.upload_from_url(body.url)
    except Exception as e:
        logger.exception("postiz upload_from_url failed")
        raise HTTPException(502, f"Postiz upload failed: {type(e).__name__}")
    return ref

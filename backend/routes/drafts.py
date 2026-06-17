"""Daily Drafts API.

GET  /drafts/{id}      — Tek taslak getir (bridge: Creator Hub → /create)
PUT  /drafts/{id}      — Taslak güncelle (edit/dismiss/published)
POST /drafts/score     — X algoritma skoru (Xquik MCP, bedava)
POST /drafts/refine    — Tweet iyileştirme önerileri (Xquik MCP, bedava)
POST /drafts/rules     — X algoritma kuralları al (Xquik MCP, bedava)
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from middleware.auth import require_auth
from pydantic import BaseModel
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/drafts", tags=["drafts"])


def get_supabase():
    from server import supabase
    return supabase


def _accessible(user_id: str) -> list[str]:
    """Phase 28.M — workspace owner ids visible to caller."""
    from services.access_control import accessible_owner_ids
    return accessible_owner_ids(user_id)


class DraftUpdate(BaseModel):
    content: Optional[str] = None
    status: Optional[str] = None  # pending/edited/published/dismissed


class ScoreRequest(BaseModel):
    draft: str  # tweet metni


class RefineRequest(BaseModel):
    draft: str  # tweet metni
    topic: str = ""
    goal: str = "engagement"
    tone: str = "professional"


class ComposeRulesRequest(BaseModel):
    topic: str
    goal: str = "engagement"  # engagement, followers, authority, conversation


@router.get("/{draft_id}")
async def get_draft(draft_id: str, user=Depends(require_auth)):
    """Tek taslak getir. Bridge akışında /create sayfası bunu çeker."""
    sb = get_supabase()
    try:
        result = sb.table("daily_drafts") \
            .select("*") \
            .eq("id", draft_id) \
            .in_("user_id", _accessible(user.id)) \
            .limit(1) \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Taslak bulunamadı")

        return {"success": True, "draft": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Draft get error: {e}")
        raise HTTPException(status_code=500, detail="Taslak getirilemedi")


@router.put("/{draft_id}")
async def update_draft(draft_id: str, body: DraftUpdate, user=Depends(require_auth)):
    """Taslak güncelle (düzenle veya dismiss et)."""
    sb = get_supabase()

    update = {}
    if body.content is not None:
        update["content"] = body.content
        update["status"] = "edited"
    if body.status is not None:
        if body.status not in ("pending", "edited", "published", "dismissed"):
            raise HTTPException(status_code=400, detail="Geçersiz status")
        update["status"] = body.status

    if not update:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")

    try:
        result = sb.table("daily_drafts") \
            .update(update) \
            .eq("id", draft_id) \
            .in_("user_id", _accessible(user.id)) \
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="Taslak bulunamadı")

        return {"success": True, "draft": result.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Draft update error: {e}")
        raise HTTPException(status_code=500, detail="Güncelleme başarısız")


# ================================================================
# Xquik MCP — Tweet Composition (bedava, quota yemiyor)
# ================================================================

@router.post("/score")
async def score_draft(body: ScoreRequest, user=Depends(require_auth)):
    """
    Tweet'i X algoritma ranking faktörlerine karşı skorla.
    Xquik MCP üzerinden, bedava.

    Returns: {checklist: [{factor, passed, suggestion?}...]}
    """
    from services.xquik_client import xquik

    try:
        result = await xquik.score_tweet(body.draft)
        return {"success": True, "score": result}
    except Exception as e:
        logger.error(f"Score error: {e}")
        raise HTTPException(status_code=500, detail="Skor hesaplanamadı")


@router.post("/refine")
async def refine_draft(body: RefineRequest, user=Depends(require_auth)):
    """
    Tweet'i X algoritma kurallarına göre iyileştirme önerileri al.
    Xquik MCP üzerinden, bedava.

    Returns: {suggestions: [...]}
    """
    from services.xquik_client import xquik

    try:
        result = await xquik.refine_tweet(body.draft, topic=body.topic, goal=body.goal, tone=body.tone)
        return {"success": True, "refinement": result}
    except Exception as e:
        logger.error(f"Refine error: {e}")
        raise HTTPException(status_code=500, detail="İyileştirme önerileri alınamadı")


@router.post("/rules")
async def get_compose_rules(body: ComposeRulesRequest, user=Depends(require_auth)):
    """
    X algoritma kuralları + engagement multiplier'ları al.
    Tweet üretiminden önce veya prompt'a enjekte etmek için.
    Xquik MCP üzerinden, bedava.

    Returns: {contentRules: [...], engagementMultipliers: [...]}
    """
    from services.xquik_client import xquik

    try:
        result = await xquik.compose_rules(body.topic, body.goal)
        return {"success": True, "rules": result}
    except Exception as e:
        logger.error(f"Compose rules error: {e}")
        raise HTTPException(status_code=500, detail="Kurallar alınamadı")

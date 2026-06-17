"""User Settings — active profile, persona/tone defaults, active account."""
from fastapi import APIRouter, Depends
from middleware.auth import require_auth
from pydantic import BaseModel, model_validator
from typing import Literal, Optional
import logging
from datetime import datetime, timezone

router = APIRouter(prefix="/settings", tags=["settings"])
logger = logging.getLogger(__name__)


def get_supabase():
    from server import supabase
    return supabase


class DefaultDraftStyle(BaseModel):
    type: Literal["own_voice", "cloned", "archetype"]
    profile_id: Optional[str] = None
    key: Optional[str] = None

    @model_validator(mode="after")
    def validate_shape(self):
        if self.type == "cloned" and not self.profile_id:
            raise ValueError("cloned style için profile_id gerekli")
        if self.type == "archetype" and not self.key:
            raise ValueError("archetype style için key gerekli")
        if self.type == "own_voice":
            self.profile_id = None
            self.key = None
        return self


class SettingsUpdate(BaseModel):
    active_profile_id: Optional[str] = None
    default_persona: Optional[str] = None
    default_tone: Optional[str] = None
    twitter_username: Optional[str] = None
    active_account_id: Optional[str] = None
    default_draft_style: Optional[DefaultDraftStyle] = None


@router.get("")
async def get_settings(user=Depends(require_auth), supabase=Depends(get_supabase)):
    result = supabase.table("user_settings").select("*").eq("user_id", user.id).execute()
    if result.data:
        return result.data[0]
    return {
        "user_id": user.id,
        "active_profile_id": None,
        "default_persona": "otorite",
        "default_tone": "natural",
        "twitter_username": None,
        "active_account_id": None,
        "default_draft_style": None,
        "subscription_tier": "free",
        "account_limit": 1,
    }


@router.patch("")
async def update_settings(body: SettingsUpdate, user=Depends(require_auth), supabase=Depends(get_supabase)):
    update_data = {
        "user_id": user.id,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if body.active_profile_id is not None:
        update_data["active_profile_id"] = body.active_profile_id if body.active_profile_id != "" else None
    if body.default_persona is not None:
        update_data["default_persona"] = body.default_persona
    if body.default_tone is not None:
        update_data["default_tone"] = body.default_tone
    if body.twitter_username is not None:
        username = body.twitter_username.strip().lstrip("@")
        update_data["twitter_username"] = username if username else None
    if body.active_account_id is not None:
        update_data["active_account_id"] = body.active_account_id if body.active_account_id != "" else None
    if "default_draft_style" in body.model_fields_set:
        update_data["default_draft_style"] = (
            body.default_draft_style.model_dump(exclude_none=True)
            if body.default_draft_style is not None
            else None
        )

    result = supabase.table("user_settings").upsert(update_data, on_conflict="user_id").execute()
    if result.data:
        return result.data[0]
    return update_data

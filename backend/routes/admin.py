"""
Admin routes - key rotation, system management.
"""
import os
import logging
from fastapi import APIRouter, HTTPException, Depends
from middleware.auth import require_auth
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])

ADMIN_EMAILS = set(
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
)


def _verify_admin(user):
    if not ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin emails not configured")
    if (user.email or "").lower() not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")


class RotateKeyRequest(BaseModel):
    key_type: str  # "openai" or "supabase_service"
    new_key: str


@router.post("/rotate-key")
async def rotate_key(body: RotateKeyRequest, user=Depends(require_auth)):
    """Rotate API keys without restart."""
    _verify_admin(user)

    if body.key_type == "openai":
        if not body.new_key.startswith("sk-"):
            raise HTTPException(status_code=400, detail="Invalid OpenAI key format")
        from openai import OpenAI
        try:
            new_client = OpenAI(api_key=body.new_key)
            # Quick validation
            new_client.models.list()
        except Exception:
            raise HTTPException(status_code=400, detail="OpenAI key validation failed")

        import server
        server.openai_client = new_client
        os.environ["OPENAI_API_KEY"] = body.new_key
        logger.info(f"OpenAI key rotated by {user.email}")
        return {"success": True, "key_type": "openai", "message": "Key rotated successfully"}

    elif body.key_type == "supabase_service":
        from supabase import create_client
        try:
            new_sb = create_client(os.environ["SUPABASE_URL"], body.new_key)
            # Quick validation
            new_sb.table("status_checks").select("id").limit(1).execute()
        except Exception:
            raise HTTPException(status_code=400, detail="Supabase key validation failed")

        import server
        server.supabase = new_sb
        os.environ["SUPABASE_SERVICE_KEY"] = body.new_key
        logger.info(f"Supabase service key rotated by {user.email}")
        return {"success": True, "key_type": "supabase_service", "message": "Key rotated successfully"}

    else:
        raise HTTPException(status_code=400, detail="key_type must be 'openai' or 'supabase_service'")

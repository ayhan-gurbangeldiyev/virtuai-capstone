"""Phase 28.N — Shared admin login.

Tek bir paylaşılan şifre ile (env'de saklanan) Cansu workspace owner'ı
(berkayaltunel123@gmail.com) olarak giriş yap.

Mekanizma:
- Bir kerelik startup'ta Berkay user'ına email+password kimlik bilgisi
  ekleriz (`auth.admin.update_user_by_id(password=...)`). Berkay'ın
  mevcut Google OAuth giriş yolu BOZULMAZ — Supabase user multiple
  auth provider'a bağlanabilir.
- Frontend /admin-login: tek input (şifre) → Supabase
  `signInWithPassword({email, password})` → Berkay session → dashboard.

Backend endpoint: POST /api/admin-auth/config
  Returns: { email } so frontend knows which email to sign in with.
  (Password frontend tarafında — env üzerinden hardcoded değil, kullanıcı
   girer.)
"""
import os
import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin-auth", tags=["admin-auth"])

ADMIN_LOGIN_EMAIL = os.environ.get(
    "ADMIN_LOGIN_EMAIL", "berkayaltunel123@gmail.com"
)


def get_supabase():
    from server import supabase
    return supabase


@router.get("/config")
async def get_admin_login_config():
    """Returns the email frontend should sign in with.

    Not sensitive — just tells AdminLoginPage which Cansu owner to
    impersonate (the password is supplied by the user typing).
    """
    return {"email": ADMIN_LOGIN_EMAIL}


# One-time helper, callable by Berkay (Google-authed) to set the shared
# password on his own account so the shared-password login works.
class SetAdminPasswordRequest:
    pass


@router.post("/set-password")
async def set_admin_password(body: dict):
    """One-time setup: set Berkay's user password.

    Protected by a setup-token in body to prevent abuse. Berkay calls this
    once (curl) with the setup token + new password. Henceforth the
    shared-password admin login works.

    Body:
      { setup_token: str, new_password: str }
    """
    setup_token = body.get("setup_token", "")
    new_password = body.get("new_password", "")

    expected_token = os.environ.get("ADMIN_SETUP_TOKEN", "")
    if not expected_token:
        raise HTTPException(503, "ADMIN_SETUP_TOKEN not configured in env")
    if setup_token != expected_token:
        raise HTTPException(401, "invalid setup token")
    if not new_password or len(new_password) < 8:
        raise HTTPException(400, "new_password must be at least 8 chars")

    sb = get_supabase()
    # Find Berkay's user_id by email
    try:
        users = sb.auth.admin.list_users()
        # SDK can return list directly or wrap in obj; handle both
        items = users if isinstance(users, list) else getattr(users, "users", [])
        target = next((u for u in items if (getattr(u, "email", None) or "").lower() == ADMIN_LOGIN_EMAIL.lower()), None)
        if not target:
            raise HTTPException(404, f"admin email {ADMIN_LOGIN_EMAIL} not in auth.users")
        user_id = target.id if hasattr(target, "id") else target.get("id")
        sb.auth.admin.update_user_by_id(user_id, {"password": new_password})
        logger.info(f"[admin-auth] password set for {ADMIN_LOGIN_EMAIL} (user_id={user_id})")
        return {"status": "ok", "email": ADMIN_LOGIN_EMAIL}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"[admin-auth] set-password failed: {e}")
        raise HTTPException(500, "set-password failed; check logs")

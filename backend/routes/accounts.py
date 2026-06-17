"""Connected Accounts — CRUD + Paywall + Ghost Merge.

PUT  /accounts/{platform}        — Hesap ekle/güncelle (paywall kontrolü)
GET  /accounts                   — Tüm hesapları listele
DELETE /accounts/{platform}      — Hesap sil
PATCH /accounts/{platform}/primary — Primary yap
PATCH /accounts/switch/{account_id} — Aktif hesap değiştir
GET  /accounts/avatar/instagram/{username} — Instagram avatar proxy
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from middleware.auth import require_auth
from datetime import datetime, timezone
import uuid
import logging
import httpx

router = APIRouter(prefix="/accounts", tags=["accounts"])
logger = logging.getLogger(__name__)

VALID_PLATFORMS = {"twitter", "instagram", "youtube", "tiktok", "linkedin"}


def get_supabase():
    from server import supabase
    return supabase


class AccountUpdate(BaseModel):
    username: str
    label: str | None = None


# ── Ghost Merge: default hesaptaki veriyi gerçek hesaba aktar ──

async def _merge_ghost_account(user_id: str, new_account_id: str, sb):
    """Default (ghost) hesaptaki tüm veriyi yeni gerçek hesaba aktar ve default'u sil."""
    default_res = sb.table("connected_accounts") \
        .select("id") \
        .eq("user_id", user_id) \
        .eq("platform", "default") \
        .limit(1) \
        .execute()

    if not default_res.data:
        return  # Ghost account yok

    old_id = default_res.data[0]["id"]
    tables = ["generations", "favorites", "style_profiles",
              "coach_weekly_plans", "coach_dismissed_cards"]

    for table in tables:
        try:
            sb.table(table) \
                .update({"account_id": new_account_id}) \
                .eq("account_id", old_id) \
                .execute()
        except Exception as e:
            logger.warning(f"Ghost merge {table} error: {e}")

    # Default hesabı sil
    try:
        sb.table("connected_accounts").delete().eq("id", old_id).execute()
        logger.info(f"Ghost merge completed: {old_id} → {new_account_id} for user {user_id}")
    except Exception as e:
        logger.error(f"Ghost account delete error: {e}")


# ── Null Migration: ikinci hesap eklendiğinde ──

async def _run_null_migration(user_id: str, primary_account_id: str, sb):
    """İkinci hesap eklendiğinde, NULL account_id'li verileri primary hesaba ata."""
    tables = ["generations", "favorites", "style_profiles",
              "coach_weekly_plans", "coach_dismissed_cards"]

    for table in tables:
        try:
            sb.table(table) \
                .update({"account_id": primary_account_id}) \
                .eq("user_id", user_id) \
                .is_("account_id", "null") \
                .execute()
        except Exception as e:
            logger.warning(f"Null migration {table} error: {e}")

    logger.info(f"Null migration completed for user {user_id} → account {primary_account_id}")


# ═══════════════════════════════════════════
# HEALTH HELPERS
# ═══════════════════════════════════════════

async def mark_account_broken(user_id: str, platform: str, reason: str, sb=None):
    """Hesabı broken olarak işaretle (reaktif health detection)."""
    if sb is None:
        sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("connected_accounts") \
            .update({"status": "broken", "broken_reason": reason, "broken_at": now}) \
            .eq("user_id", user_id) \
            .eq("platform", platform) \
            .eq("status", "active") \
            .execute()
        logger.warning(f"Account marked broken: user={user_id}, platform={platform}, reason={reason}")
    except Exception as e:
        logger.error(f"Failed to mark account broken: {e}")


async def mark_account_healed(user_id: str, platform: str, sb=None):
    """Başarılı API çağrısı sonrası broken hesabı iyileştir."""
    if sb is None:
        sb = get_supabase()
    try:
        sb.table("connected_accounts") \
            .update({"status": "active", "broken_reason": None, "broken_at": None}) \
            .eq("user_id", user_id) \
            .eq("platform", platform) \
            .eq("status", "broken") \
            .execute()
    except Exception as e:
        logger.error(f"Failed to heal account: {e}")


# ═══════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════

@router.get("")
async def get_accounts(user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Tüm bağlı hesapları listele (soft-deleted hariç, status dahil).
    Phase 28.M: kullanıcının kendi hesapları + accepted workspace collaborator
    olduğu owner'ların hesapları (transparent shared workspace)."""
    from services.access_control import accessible_owner_ids
    result = supabase.table("connected_accounts") \
        .select("*") \
        .in_("user_id", accessible_owner_ids(user.id)) \
        .neq("platform", "default") \
        .is_("deleted_at", "null") \
        .order("created_at") \
        .execute()
    return result.data or []


@router.put("/{platform}")
async def upsert_account(platform: str, body: AccountUpdate, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Hesap ekle/güncelle. Paywall kontrolü + ghost merge."""
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Geçersiz platform: {platform}")

    username = body.username.strip().lstrip("@")
    if not username:
        raise HTTPException(status_code=400, detail="Kullanıcı adı boş olamaz")

    now = datetime.now(timezone.utc).isoformat()

    # ── Provider ID çek (Twitter: değişmez numeric ID) ──
    provider_id = None
    if platform == "twitter":
        try:
            from services.xquik_client import xquik
            user_info = await xquik.get_user_info(username)
            if user_info and user_info.get("id"):
                provider_id = str(user_info["id"])
        except Exception as e:
            logger.warning(f"Provider ID fetch failed for @{username}: {e}")

    # ── 1. Username bazlı eşleşme (aktif hesap güncelleme) ──
    existing = supabase.table("connected_accounts") \
        .select("id, deleted_at, status, provider_id") \
        .eq("user_id", user.id) \
        .eq("platform", platform) \
        .eq("username", username) \
        .execute()

    # ── 2. Provider ID bazlı eşleşme (username değişmiş olabilir) ──
    if not existing.data and provider_id:
        existing = supabase.table("connected_accounts") \
            .select("id, deleted_at, status, provider_id, username") \
            .eq("user_id", user.id) \
            .eq("platform", platform) \
            .eq("provider_id", provider_id) \
            .execute()
        if existing.data:
            old_username = existing.data[0].get("username", "?")
            logger.info(f"Provider ID match: @{old_username} → @{username} (provider_id={provider_id})")

    if existing.data:
        record = existing.data[0]

        # ── Diriliş: soft-deleted hesap geri bağlanıyor ──
        if record.get("deleted_at"):
            restored_id = record["id"]
            supabase.table("connected_accounts") \
                .update({
                    "username": username,
                    "label": body.label,
                    "status": "active",
                    "deleted_at": None,
                    "broken_reason": None,
                    "broken_at": None,
                    "provider_id": provider_id or record.get("provider_id"),
                    "updated_at": now,
                }) \
                .eq("id", restored_id) \
                .execute()
            logger.info(f"Account restored: {platform}/{username} (id={restored_id}) for user {user.id}")
            return {"success": True, "id": restored_id, "restored": True}

        # ── Normal güncelleme ──
        update_data = {"username": username, "updated_at": now, "status": "active",
                       "broken_reason": None, "broken_at": None}
        if provider_id and not record.get("provider_id"):
            update_data["provider_id"] = provider_id  # Retroaktif provider_id doldur
        if body.label is not None:
            update_data["label"] = body.label
        result = supabase.table("connected_accounts") \
            .update(update_data) \
            .eq("id", record["id"]) \
            .execute()
        return result.data[0] if result.data else {"success": True}

    # ── Yeni hesap ekleme ──

    # Paywall: hesap limiti kontrolü (soft-deleted hariç)
    all_real = supabase.table("connected_accounts") \
        .select("id", count="exact") \
        .eq("user_id", user.id) \
        .neq("platform", "default") \
        .is_("deleted_at", "null") \
        .execute()
    current_count = all_real.count if hasattr(all_real, 'count') and all_real.count is not None else len(all_real.data or [])

    # Kullanıcının limit'ini çek
    settings_res = supabase.table("user_settings") \
        .select("account_limit, subscription_tier") \
        .eq("user_id", user.id) \
        .limit(1) \
        .execute()
    account_limit = 1
    tier = "free"
    if settings_res.data:
        account_limit = settings_res.data[0].get("account_limit", 1)
        tier = settings_res.data[0].get("subscription_tier", "free")

    if current_count >= account_limit:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACCOUNT_LIMIT",
                "message": f"Hesap limitine ulaştın ({current_count}/{account_limit})",
                "current": current_count,
                "limit": account_limit,
                "tier": tier,
                "upgrade_url": "/pricing",
            }
        )

    # İlk gerçek hesap mı?
    is_first = current_count == 0

    # Yeni hesap oluştur
    new_id = str(uuid.uuid4())
    result = supabase.table("connected_accounts").insert({
        "id": new_id,
        "user_id": user.id,
        "platform": platform,
        "username": username,
        "provider_id": provider_id,
        "is_primary": is_first,
        "label": body.label,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }).execute()

    # Ghost merge: default hesap varsa veriyi yeni hesaba aktar
    if is_first:
        await _merge_ghost_account(user.id, new_id, supabase)

    # İkinci+ hesap: null migration (güvenlik ağı)
    if not is_first:
        # Primary hesabı bul
        primary_res = supabase.table("connected_accounts") \
            .select("id") \
            .eq("user_id", user.id) \
            .eq("is_primary", True) \
            .limit(1) \
            .execute()
        if primary_res.data:
            await _run_null_migration(user.id, primary_res.data[0]["id"], supabase)

    # Yeni hesabı aktif yap (user_settings)
    if is_first:
        supabase.table("user_settings").upsert({
            "user_id": user.id,
            "active_account_id": new_id,
            "updated_at": now,
        }, on_conflict="user_id").execute()

    return result.data[0] if result.data else {"success": True, "id": new_id}


@router.delete("/by-id/{account_id}")
async def delete_account_by_id(account_id: str, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Hesap soft-delete (account_id bazlı, multi-account safe)."""
    target = supabase.table("connected_accounts") \
        .select("id, is_primary, platform") \
        .eq("id", account_id) \
        .eq("user_id", user.id) \
        .is_("deleted_at", "null") \
        .limit(1) \
        .execute()
    return await _soft_delete_account(target, user, supabase)


@router.delete("/{platform}")
async def delete_account(platform: str, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Hesap soft-delete (legacy platform bazlı, tek hesaplı durumlar için)."""
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Geçersiz platform: {platform}")

    target = supabase.table("connected_accounts") \
        .select("id, is_primary, platform") \
        .eq("user_id", user.id) \
        .eq("platform", platform) \
        .is_("deleted_at", "null") \
        .limit(1) \
        .execute()
    return await _soft_delete_account(target, user, supabase)


async def _soft_delete_account(target, user, supabase):

    if not target.data:
        return {"deleted": 0}

    deleted_id = target.data[0]["id"]
    was_primary = target.data[0].get("is_primary", False)
    now = datetime.now(timezone.utc).isoformat()

    # 1. Cascade soft-delete: ilişkili veriyi işaretle
    cascade_tables = ["generations", "favorites", "style_profiles",
                      "coach_weekly_plans", "coach_dismissed_cards"]
    cascade_counts = {}
    for table in cascade_tables:
        try:
            res = supabase.table(table) \
                .select("id", count="exact") \
                .eq("account_id", deleted_id) \
                .eq("user_id", user.id) \
                .execute()
            cascade_counts[table] = res.count or 0
        except Exception:
            cascade_counts[table] = 0

    # 2. Hesabı soft-delete (hard delete değil, diriliş mümkün)
    supabase.table("connected_accounts") \
        .update({"deleted_at": now, "is_primary": False, "status": "deleted"}) \
        .eq("id", deleted_id) \
        .execute()

    # 3. Aktif hesap silindiyse → fallback
    settings = supabase.table("user_settings") \
        .select("active_account_id") \
        .eq("user_id", user.id) \
        .limit(1) \
        .execute()

    active_was_deleted = settings.data and settings.data[0].get("active_account_id") == deleted_id

    # Kalan AKTİF hesapları bul
    remaining = supabase.table("connected_accounts") \
        .select("id") \
        .eq("user_id", user.id) \
        .neq("platform", "default") \
        .is_("deleted_at", "null") \
        .order("created_at") \
        .limit(1) \
        .execute()

    fallback_id = remaining.data[0]["id"] if remaining.data else None

    if active_was_deleted:
        supabase.table("user_settings").upsert({
            "user_id": user.id,
            "active_account_id": fallback_id,
            "updated_at": now,
        }, on_conflict="user_id").execute()

    if was_primary and fallback_id:
        supabase.table("connected_accounts") \
            .update({"is_primary": True}) \
            .eq("id", fallback_id) \
            .execute()

    return {
        "deleted": 1,
        "fallback_account_id": fallback_id,
        "active_changed": active_was_deleted,
        "cascade": cascade_counts,
        "restorable": True,
    }


@router.patch("/by-id/{account_id}/primary")
async def set_primary_by_id(account_id: str, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Hesabı primary yap (account_id bazlı, multi-account safe)."""
    existing = supabase.table("connected_accounts") \
        .select("id, platform") \
        .eq("id", account_id) \
        .eq("user_id", user.id) \
        .is_("deleted_at", "null") \
        .limit(1) \
        .execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    # Hepsini unset
    supabase.table("connected_accounts") \
        .update({"is_primary": False}) \
        .eq("user_id", user.id) \
        .execute()
    # Bu hesabı set
    supabase.table("connected_accounts") \
        .update({"is_primary": True}) \
        .eq("id", account_id) \
        .execute()

    return {"success": True, "primary_id": account_id}


@router.patch("/{platform}/primary")
async def set_primary(platform: str, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Hesabı primary yap (legacy platform bazlı)."""
    if platform not in VALID_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Geçersiz platform: {platform}")

    existing = supabase.table("connected_accounts") \
        .select("id") \
        .eq("user_id", user.id) \
        .eq("platform", platform) \
        .is_("deleted_at", "null") \
        .limit(1) \
        .execute()
    if not existing.data:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    supabase.table("connected_accounts") \
        .update({"is_primary": False}) \
        .eq("user_id", user.id) \
        .execute()
    supabase.table("connected_accounts") \
        .update({"is_primary": True}) \
        .eq("id", existing.data[0]["id"]) \
        .execute()

    return {"success": True, "primary": platform}


@router.patch("/switch/{account_id}")
async def switch_account(account_id: str, user=Depends(require_auth), supabase=Depends(get_supabase)):
    """Aktif hesabı değiştir."""
    from services.access_control import accessible_owner_ids
    # Hesap bu kullanıcıya ait mi?
    acc = supabase.table("connected_accounts") \
        .select("id, platform, username, status") \
        .eq("id", account_id) \
        .in_("user_id", accessible_owner_ids(user.id, supabase)) \
        .limit(1) \
        .execute()

    if not acc.data:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı")

    now = datetime.now(timezone.utc).isoformat()
    supabase.table("user_settings").upsert({
        "user_id": user.id,
        "active_account_id": account_id,
        "updated_at": now,
    }, on_conflict="user_id").execute()

    account = acc.data[0]
    return {
        "success": True,
        "active_account": account,
        "warning": "Bu hesabın bağlantısı kopmuş" if account.get("status") != "active" else None,
    }


# ── Avatar Proxy ──

@router.get("/avatar/instagram/{username}", include_in_schema=False)
async def instagram_avatar(username: str):
    """Instagram profil fotoğrafı proxy."""
    username = username.strip().lstrip("@")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}",
                headers={
                    "User-Agent": "Instagram 219.0.0.12.117",
                    "X-IG-App-ID": "936619743392459",
                }
            )
            if r.status_code == 200:
                data = r.json()
                pic_url = data.get("data", {}).get("user", {}).get("profile_pic_url_hd") or \
                          data.get("data", {}).get("user", {}).get("profile_pic_url", "")
                if pic_url:
                    return RedirectResponse(url=pic_url, status_code=302)
    except Exception as e:
        logger.warning(f"Instagram avatar fetch failed for @{username}: {e}")

    raise HTTPException(status_code=404, detail="Avatar not found")

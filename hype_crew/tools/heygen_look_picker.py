"""Phase 40.A — HeyGen Avatar V look picker.

Berkay'ın direktifi (1 Haz 2026):
  "ai generated olanları yapmamız lazım tek tek kullanılan da bir daha
   kullanılmasın"

Mevcut video pipeline (Phase 35.3) `persona.heygen_default_look_id` env
var'dan TEK look kullanıyor — her video aynı "blue sofa" Cansu'sunu
konuşturuyor. Berkay 11 AI-generated look'un (Phase 38 sync'i ile gelen
`asset_type='curated_photo'` + `business_type='generated'`) rotate
edilmesini istiyor. Bir kez kullanılan tekrar kullanılmasın. Pool
tükenince LRU (en eski kullanılan tekrar gelsin) — Berkay onayı.

Picker mantığı:
  1. persona_assets'tan curated_photo + generated + Avatar V uyumlu
     look'ları al.
  2. `used_in_video=true` olmayan havuzdan random pick.
  3. Pool boşsa: LRU — en eski `used_in_video_at` olan look'u seç.
  4. Seçilen look'u `used_in_video=true, used_in_video_at=now()` ile mark.

Avatar V uyumluluğu için `generation_metadata.supported_api_engines`
kontrolü yapılır. Phase 38 sync güçlendirildi — her yeni look için
`GET /v3/avatars/looks/{id}` ile bu liste kaydedilir. Eski (Phase 38'den
sync edilmiş 11 look) için `backfill_avatar_v_compatibility` script ile
populate edilebilir.

Fallback: helper None döner ise caller `cfg["heygen_default_look_id"]`'i
kullanır (Berkay onaylı "blue sofa").
"""
from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional, Any
from loguru import logger

from .supabase_client import make_supabase


async def pick_heygen_look_for_video(persona_id: str) -> Optional[dict[str, Any]]:
    """Avatar V'de konuşacak look'u seç.

    Return: {"asset_id": ..., "heygen_id": ..., "name": ..., "was_lru": bool}
    veya None (havuz tamamen boş — caller default'a düşer).
    """
    sb = make_supabase()

    # 1. AI-generated + Avatar V eligible olan tüm look'ları çek
    res = (
        sb.table("persona_assets")
        .select("id, provider_task_uuid, generation_metadata")
        .eq("persona_id", persona_id)
        .eq("asset_type", "curated_photo")
        .eq("status", "publish_ready")
        .order("created_at", desc=False)
        .execute()
    )
    rows = res.data or []
    if not rows:
        logger.warning(f"[look_picker] persona {persona_id[:8]}: zero curated_photo rows")
        return None

    def is_avatar_v_eligible(row: dict[str, Any]) -> bool:
        meta = row.get("generation_metadata") or {}
        engines = meta.get("supported_api_engines")
        # If we haven't checked engines yet, assume eligible (fail-open).
        # The video gen call itself will surface incompatibility; safer than
        # excluding everything until backfill runs.
        if engines is None:
            return True
        if isinstance(engines, list):
            return any(str(e).lower() == "avatar_v" for e in engines)
        return False

    # Capstone (3 Haz 2026): respect owner block list.
    # generation_metadata.blocked_by_owner=true → skip.
    def _is_blocked(row: dict[str, Any]) -> bool:
        meta = row.get("generation_metadata") or {}
        return bool(meta.get("blocked_by_owner"))

    rows = [r for r in rows if not _is_blocked(r)]
    if not rows:
        logger.warning(
            f"[look_picker] persona {persona_id[:8]}: zero rows after "
            f"blocked_by_owner filter"
        )
        return None

    eligible = [r for r in rows if is_avatar_v_eligible(r)]
    if not eligible:
        logger.warning(
            f"[look_picker] persona {persona_id[:8]}: zero Avatar V eligible looks "
            f"({len(rows)} total curated, none with avatar_v in supported_api_engines)"
        )
        return None

    # 2. Unused havuz
    unused = [
        r for r in eligible
        if not (r.get("generation_metadata") or {}).get("used_in_video")
    ]

    if unused:
        chosen = random.choice(unused)
        was_lru = False
        logger.info(
            f"[look_picker] persona {persona_id[:8]}: "
            f"{len(unused)} unused / {len(eligible)} eligible — picked fresh"
        )
    else:
        # 3. LRU fallback — en eski `used_in_video_at` olan look'u seç
        def used_at_key(row: dict[str, Any]) -> str:
            meta = row.get("generation_metadata") or {}
            return str(meta.get("used_in_video_at") or "")
        eligible_sorted = sorted(eligible, key=used_at_key)
        chosen = eligible_sorted[0]
        was_lru = True
        logger.info(
            f"[look_picker] persona {persona_id[:8]}: pool exhausted ({len(eligible)} total) — "
            f"LRU pick"
        )

    meta = chosen.get("generation_metadata") or {}
    return {
        "asset_id": chosen["id"],
        "heygen_id": meta.get("heygen_id") or chosen.get("provider_task_uuid"),
        "name": meta.get("name", "Unnamed"),
        "was_lru": was_lru,
    }


async def mark_look_used(asset_id: str) -> None:
    """Video başarıyla üretildikten sonra mark et.

    `generation_metadata.used_in_video = true` + `used_in_video_at` set.
    Idempotent — birden fazla mark hata vermez (JSONB merge).
    """
    sb = make_supabase()
    # Read existing metadata, merge flags, write back
    res = (
        sb.table("persona_assets")
        .select("generation_metadata")
        .eq("id", asset_id)
        .limit(1)
        .execute()
    )
    if not res.data:
        logger.warning(f"[look_picker] mark_used: asset {asset_id} not found")
        return
    meta = dict(res.data[0].get("generation_metadata") or {})
    now = datetime.now(timezone.utc).isoformat()
    meta["used_in_video"] = True
    meta["used_in_video_at"] = now
    # LRU counter — track how many times used
    meta["video_use_count"] = int(meta.get("video_use_count") or 0) + 1

    sb.table("persona_assets").update({"generation_metadata": meta}).eq("id", asset_id).execute()
    logger.info(
        f"[look_picker] marked asset {asset_id[:8]} used "
        f"(count={meta['video_use_count']})"
    )

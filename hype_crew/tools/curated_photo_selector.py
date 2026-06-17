"""Phase 38 — Curated photo selector (Berkay 31 May 2026).

VisualDirector face mode'da Wiro Seedream üretimi yerine, Berkay'ın
HeyGen UI'da "Design with AI" ile ürettiği ve persona_assets'a
`asset_type='curated_photo'` olarak sync'lenen kütüphaneden semantic
match ile en uygun fotoyu seçer.

Avantajlar:
- Kalite Berkay-onaylı (anatomi temiz, yüz garantili)
- $0 generation cost (kütüphane reuse)
- Düşük latency (LLM call + DB query)
- Compliance gate bypass edilebilir (curated_photo zaten publish_ready)

Strateji:
1. Persona için tüm curated_photo'ları çek (publish_ready status)
2. Son 24h içinde kullanılan asset'leri aday listesinden düş (rotasyon)
3. LLM (gemini-flash) çağrısı: "Bu sahne için en uygun foto hangisi?"
   → integer index (1-N) döner
4. Asset bilgilerini döndür (url, asset_id, name, metadata)

Fallback: Eğer LLM call fail veya kütüphane boş → None döner, caller
Wiro Seedream'e fallback yapar.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from loguru import logger

from config import settings
from .supabase_client import make_supabase


@dataclass(frozen=True)
class CuratedPhoto:
    asset_id: str
    public_url: str
    name: str
    storage_key: str
    heygen_id: str
    metadata: dict[str, Any]


async def list_curated_photos(persona_id: str) -> list[CuratedPhoto]:
    """Fetch all curated photos for a persona (publish_ready only).

    Phase 42.C v2 — Skip rows whose CLIP gate verdict was NEEDS_REVIEW.
    `asset_status_enum` doesn't contain a 'needs_review' value, so the
    sync script parks gray-zone photos at status='publish_ready' but
    stamps `generation_metadata.clip_gate.verdict='NEEDS_REVIEW'`. The
    picker has to honor that flag client-side. To promote a parked
    photo, clear the metadata flag in Supabase Studio (or set
    verdict='APPROVED_BY_USER').
    """
    sb = make_supabase()
    res = (
        sb.table("persona_assets")
        .select("id, public_url, storage_key, generation_metadata")
        .eq("persona_id", persona_id)
        .eq("asset_type", "curated_photo")
        .eq("status", "publish_ready")
        .order("created_at", desc=False)
        .execute()
    )
    rows = res.data or []
    out: list[CuratedPhoto] = []
    skipped_review = 0
    for r in rows:
        meta = r.get("generation_metadata") or {}
        # Phase 42.C v2 — client-side NEEDS_REVIEW filter
        clip_gate = (meta.get("clip_gate") or {}) if isinstance(meta, dict) else {}
        if str(clip_gate.get("verdict") or "").upper() == "NEEDS_REVIEW":
            skipped_review += 1
            continue
        out.append(CuratedPhoto(
            asset_id=r["id"],
            public_url=r["public_url"],
            name=meta.get("name", "Untitled"),
            storage_key=r["storage_key"],
            heygen_id=meta.get("heygen_id", ""),
            metadata=meta,
        ))
    if skipped_review:
        logger.info(
            f"[curated_selector] persona {persona_id[:8]}: hid {skipped_review} "
            f"NEEDS_REVIEW photos (parked, awaiting manual approval)"
        )
    return out


async def get_recently_used_asset_ids(persona_id: str, hours: int = 24) -> set[str]:
    """Asset IDs used in daily_drafts.image_asset_id within `hours` ago (any platform)."""
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    res = (
        sb.table("daily_drafts")
        .select("image_asset_id")
        .gte("created_at", since)
        .not_.is_("image_asset_id", "null")
        .execute()
    )
    rows = res.data or []
    return {r["image_asset_id"] for r in rows if r.get("image_asset_id")}


async def get_recently_used_in_platform(
    persona_id: str, platform: str, hours: int = 48
) -> set[str]:
    """Phase 39.6 — Asset IDs used in `daily_drafts` filtered by `platform`
    within `hours`. Per-platform cooldown enforcement: same image won't
    appear on the same platform twice in 48h, but other platforms see it
    independently.
    """
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    res = (
        sb.table("daily_drafts")
        .select("image_asset_id")
        .eq("platform", platform)
        .gte("created_at", since)
        .not_.is_("image_asset_id", "null")
        .execute()
    )
    rows = res.data or []
    return {r["image_asset_id"] for r in rows if r.get("image_asset_id")}


async def get_last_used_at_per_asset(persona_id: str, platform: str) -> dict[str, str]:
    """Phase 39.6 LRU helper — Returns {asset_id: max(created_at_iso)} for the
    given platform. Used to pick the OLDEST-used photo when fresh candidates
    are exhausted (system never fails, just rotates LRU)."""
    sb = make_supabase()
    res = (
        sb.table("daily_drafts")
        .select("image_asset_id, created_at")
        .eq("platform", platform)
        .not_.is_("image_asset_id", "null")
        .order("created_at", desc=True)
        .limit(500)
        .execute()
    )
    rows = res.data or []
    out: dict[str, str] = {}
    for r in rows:
        aid = r.get("image_asset_id")
        ts = r.get("created_at")
        if aid and ts and aid not in out:
            out[aid] = ts  # first occurrence = most recent (rows ordered desc)
    return out


async def _llm_pick_photo(
    *,
    scene_description: str,
    content_context: Optional[str],
    candidates: list[CuratedPhoto],
    api_key: str,
    model: str,
) -> Optional[int]:
    """Ask an LLM which candidate (1-N) fits the scene best. Returns 1-based
    index or None on failure. Uses cheap gemini-flash via OpenRouter."""
    if not candidates:
        return None

    # OpenRouter direct endpoint; settings.model_fast is a litellm-style slug
    # like "openrouter/google/gemini-3-flash-preview" — strip the "openrouter/"
    # prefix when calling the API directly.
    actual_model = model.removeprefix("openrouter/")

    options_str = "\n".join(
        f"{i+1}. {c.name}"
        for i, c in enumerate(candidates)
    )
    sys_prompt = (
        "You pick the most appropriate persona photo for a social-media draft. "
        "Each photo has a short caption. Given a scene_description (what mood/"
        "context the draft needs), reply with ONLY a single integer (1-N) — "
        "the best matching photo index. No other text."
    )
    user_prompt = (
        f"scene_description:\n{scene_description}\n\n"
        f"content_context:\n{content_context or '(none)'}\n\n"
        f"options:\n{options_str}\n\n"
        f"Reply with the integer index only."
    )

    # LiteLLM Router dalı (flag-gated, fail-open). Bu site JSON değil DÜZ TAMSAYI
    # (1-N) döndürür → router_chat_json'ın json_object zorlaması yanıtı bozar; çekirdek
    # router_chat_messages (response_format YOK) kullanılır, ham metin döner ve aşağıdaki
    # MEVCUT regex int-parse aynen uygulanır. Kapalı/hatalı iken httpx yolu byte-identical.
    try:
        from .llm_router import router_enabled, router_chat_messages
        if router_enabled():
            try:
                text, _meta = await router_chat_messages(
                    [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    model_name="gate-fast", temperature=0.2, max_tokens=8,
                )
                text = (text or "").strip()
                import re
                match = re.search(r"\d+", text)
                if not match:
                    logger.warning(f"[curated_selector] LLM returned no integer: {text!r}")
                    return None
                idx = int(match.group(0))
                if 1 <= idx <= len(candidates):
                    return idx
                logger.warning(f"[curated_selector] LLM index {idx} out of range 1-{len(candidates)}")
                return None
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[curated_selector] router atlandı, httpx'e düşülüyor: {e}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[curated_selector] router import hatası, httpx'e düşülüyor: {e}")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": actual_model,
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.2,
                    "max_tokens": 8,
                },
            )
            r.raise_for_status()
            data = r.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        # Parse first integer in response
        import re
        match = re.search(r"\d+", text)
        if not match:
            logger.warning(f"[curated_selector] LLM returned no integer: {text!r}")
            return None
        idx = int(match.group(0))
        if 1 <= idx <= len(candidates):
            return idx
        logger.warning(f"[curated_selector] LLM index {idx} out of range 1-{len(candidates)}")
        return None
    except Exception as e:
        logger.warning(f"[curated_selector] LLM pick failed: {type(e).__name__}: {e}")
        return None


async def select_curated_photo(
    *,
    persona_id: str,
    scene_description: str,
    content_context: Optional[str] = None,
    platform: Optional[str] = None,
    enforce_cooldown_hours: int = 48,
    composition_filter: Optional[str] = None,
) -> Optional[CuratedPhoto]:
    """Pick the best curated photo for a scene.

    Phase 39.6 (Berkay 31 May 2026) — Per-platform cooldown + LRU fallback.
    Phase 42.A (Berkay 2 Jun 2026) — composition_filter: pre-filter the
    candidate pool by `generation_metadata.composition_style` so a request
    for `cansu_scene` cannot draw from the `selfie` pool (and vice versa).
    If the filtered pool is empty (e.g. Phase 42.C scene photos not yet
    synced), we log a warning and fall back to the full library — the
    cooldown / LRU step still runs afterwards.

    Strategy (per platform independence):
      1. composition_filter (if given) narrows the pool before cooldown
      2. Fresh = photos NOT used on this platform in last 48h → LLM picks
      3. If fresh empty → LRU fallback: pick OLDEST-used photo on this platform
      4. If no `platform` given → global 48h cooldown (legacy behavior)

    Returns None only if library is empty.
    """
    all_photos = await list_curated_photos(persona_id)
    if not all_photos:
        logger.info(f"[curated_selector] persona {persona_id[:8]}: empty library")
        return None

    # Phase 42.A — composition filter applies before cooldown ranking. Until
    # Phase 42.C ships scene photos, expect this filter to find 0 matches
    # for `cansu_scene` and fall back; that's the documented transition path.
    if composition_filter:
        filtered = [
            p for p in all_photos
            if str(p.metadata.get("composition_style") or "").lower() == composition_filter.lower()
        ]
        if filtered:
            logger.info(
                f"[curated_selector] composition_filter={composition_filter}: "
                f"{len(filtered)}/{len(all_photos)} photos match"
            )
            all_photos = filtered
        else:
            logger.warning(
                f"[curated_selector] composition_filter={composition_filter} matched 0 photos "
                f"(library has {len(all_photos)} total — Phase 42.C non-selfie photos "
                f"may not be synced yet); falling back to full pool"
            )

    # Per-platform cooldown (Phase 39.6). If platform omitted, fall back to
    # global cooldown so the legacy callers still work.
    if platform:
        recently_used = await get_recently_used_in_platform(
            persona_id, platform, hours=enforce_cooldown_hours
        )
        cooldown_label = f"platform={platform}"
    else:
        recently_used = await get_recently_used_asset_ids(
            persona_id, hours=enforce_cooldown_hours
        )
        cooldown_label = "global"

    fresh = [p for p in all_photos if p.asset_id not in recently_used]

    # Phase 39.6 — LRU fallback: when fresh empty, pick OLDEST-used on this
    # platform (instead of random or "all photos"). Photo never seen on this
    # platform ranks first; otherwise oldest created_at wins.
    if not fresh and platform:
        last_used = await get_last_used_at_per_asset(persona_id, platform)
        # Sort all_photos by last_used_at ASC (oldest first; never-used = "")
        ranked = sorted(all_photos, key=lambda p: last_used.get(p.asset_id, ""))
        oldest = ranked[0]
        logger.warning(
            f"[curated_selector] persona {persona_id[:8]} platform={platform}: "
            f"all {len(all_photos)} cooled down, LRU pick: "
            f"{oldest.name[:40]} (last_used={last_used.get(oldest.asset_id, 'never')[:19]})"
        )
        return oldest

    candidates = fresh if fresh else all_photos
    logger.info(
        f"[curated_selector] persona {persona_id[:8]} {cooldown_label}: "
        f"{len(all_photos)} total, {len(fresh)} fresh (≥{enforce_cooldown_hours}h cooldown), "
        f"using {len(candidates)} candidates"
    )

    # Ask LLM to pick
    idx = await _llm_pick_photo(
        scene_description=scene_description,
        content_context=content_context,
        candidates=candidates,
        api_key=settings.openrouter_api_key,
        model=settings.model_fast,
    )

    if idx is None:
        # LLM unreachable → pick random from candidates
        chosen = random.choice(candidates)
        logger.warning(
            f"[curated_selector] LLM unreachable, random pick: "
            f"{chosen.name[:40]} ({chosen.asset_id[:8]})"
        )
        return chosen

    chosen = candidates[idx - 1]
    logger.success(
        f"[curated_selector] LLM picked #{idx}/{len(candidates)}: "
        f"{chosen.name[:40]} ({chosen.asset_id[:8]})"
    )
    return chosen

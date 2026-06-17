"""AI Coach v2 route'ları.

GET  /api/coach/feed         — Dinamik kart feed (roast/toast/opportunity/daily/repurpose/progress)
GET  /api/coach/insights     — Eski: üretim geçmişi analizi (geriye uyum)
GET  /api/coach/weekly-plan  — Haftalık plan (DB cache)
POST /api/coach/weekly-plan  — Haftalık plan üret + DB'ye kaydet
POST /api/coach/dismiss      — Kartı dismiss et
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from middleware.auth import require_auth
from services.access_control import accessible_owner_ids
from middleware.active_account import get_active_account
from pydantic import BaseModel
from typing import Optional, List
from collections import Counter
from datetime import datetime, timezone, timedelta
import json
import logging
import uuid

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/coach", tags=["coach"])


def get_supabase():
    from server import supabase
    return supabase


from zoneinfo import ZoneInfo

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _this_monday():
    """Bu haftanın Pazartesi tarihini döndür (Istanbul timezone)."""
    today = datetime.now(ISTANBUL_TZ).date()
    return today - timedelta(days=today.weekday())


# ═══════════════════════════════════════════
# FEED — Ana endpoint
# ═══════════════════════════════════════════

@router.get("/feed")
async def get_coach_feed(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Tüm dinamik kartları hesaplayıp priority sırasıyla döndür."""
    from services.coach_engine import (
        get_opportunity_cards,
        get_roast_toast_cards,
        get_daily_goal_cards,
        get_repurpose_cards,
        get_progress_cards,
        get_onboarding_cards,
    )

    sb = get_supabase()
    cards = []

    # Onboarding önce — cold start kontrolü
    onboarding = await get_onboarding_cards(user.id, sb)
    cards += onboarding

    # Yeterli verisi varsa diğer kartları da ekle
    cards += await get_opportunity_cards(user.id, sb)
    cards += await get_roast_toast_cards(user.id, sb)
    cards += await get_daily_goal_cards(user.id, sb)
    cards += await get_repurpose_cards(user.id, sb)
    cards += await get_progress_cards(user.id, sb)

    # Dismissed kartları filtrele
    try:
        dismissed_res = sb.table("coach_dismissed_cards") \
            .select("card_key") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .execute()
        dismissed_keys = {d["card_key"] for d in (dismissed_res.data or [])}
        cards = [c for c in cards if c.get("key") not in dismissed_keys]
    except Exception as e:
        logger.warning(f"Dismissed cards fetch error: {e}")

    # Priority sırasıyla, max 10
    cards.sort(key=lambda c: c.get("priority", 0), reverse=True)
    return {"cards": cards[:10]}


# ═══════════════════════════════════════════
# DISMISS
# ═══════════════════════════════════════════

class DismissRequest(BaseModel):
    card_key: str


@router.post("/dismiss")
async def dismiss_card(body: DismissRequest, user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Kartı dismiss et, bir daha gösterme."""
    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("coach_dismissed_cards").upsert({
            "id": str(uuid.uuid4()),
            "user_id": user.id,
            "card_key": body.card_key,
            "dismissed_at": now,
        }, on_conflict="user_id,card_key").execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Dismiss error: {e}")
        raise HTTPException(status_code=500, detail="Dismiss hatası")


# ═══════════════════════════════════════════
# WEEKLY PLAN — Persistent
# ═══════════════════════════════════════════

@router.get("/weekly-plan")
async def get_weekly_plan(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Bu haftanın planını DB'den getir. Yoksa null döndür."""
    sb = get_supabase()
    monday = _this_monday().isoformat()

    try:
        res = sb.table("coach_weekly_plans") \
            .select("*") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .eq("week_start", monday) \
            .limit(1) \
            .execute()

        if res.data:
            row = res.data[0]
            return {
                "plan": row["plan"],
                "weekly_goal": row.get("weekly_goal"),
                "cached": True,
                "created_at": row["created_at"],
                "week_start": row["week_start"],
            }
        else:
            return {"plan": None, "has_plan": False}
    except Exception as e:
        logger.error(f"Weekly plan GET error: {e}")
        return {"plan": None, "has_plan": False}


class WeeklyPlanRequest(BaseModel):
    niche: str = "tech"


@router.post("/weekly-plan")
async def create_weekly_plan(
    body: WeeklyPlanRequest = WeeklyPlanRequest(),
    user=Depends(require_auth),
    account_id: str = Depends(get_active_account),
):
    """GPT ile haftalık plan üret, DB'ye kaydet."""
    try:
        from server import openai_client
        if not openai_client:
            raise HTTPException(status_code=500, detail="OpenAI yapılandırılmamış")

        sb = get_supabase()

        # Kullanıcının üretim geçmişinden context çıkar
        gen_res = sb.table("generations") \
            .select("persona, tone, length, type") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .order("created_at", desc=True) \
            .limit(30) \
            .execute()
        gens = gen_res.data or []

        # En çok kullanılan persona/tone
        personas = Counter(g["persona"] for g in gens if g.get("persona"))
        tones = Counter(g["tone"] for g in gens if g.get("tone"))
        top_persona = personas.most_common(1)[0][0] if personas else "otorite"
        top_tone = tones.most_common(1)[0][0] if tones else "natural"
        least_persona = personas.most_common()[-1][0] if len(personas) > 1 else None

        # Creator Hub profile
        profile_res = sb.table("user_settings") \
            .select("display_name, niches, brand_voice") \
            .in_("user_id", accessible_owner_ids(user.id)) \
            .limit(1) \
            .execute()
        profile = profile_res.data[0] if profile_res.data else {}
        creator_name = profile.get("display_name") or user.email.split("@")[0]
        creator_niches = profile.get("niches") or []
        brand_voice = profile.get("brand_voice") or {}
        bv_tones = brand_voice.get("tones", {})
        active_bv = {k: v for k, v in bv_tones.items() if v > 0}
        bv_str = ", ".join(f"%{v} {k}" for k, v in sorted(active_bv.items(), key=lambda x: -x[1])) if active_bv else "ayarlanmamış"

        user_context = f"""Kullanıcı bilgisi:
- İsim: {creator_name}
- En çok kullandığı karakter: {top_persona}
- En çok kullandığı ton: {top_tone}
- En az kullandığı karakter: {least_persona or 'bilinmiyor'}
- Toplam üretim: {len(gens)} (son 30 içinde)
- Niche: {body.niche}
- İlgi alanları: {', '.join(creator_niches) if creator_niches else 'belirtilmemiş'}
- Marka tonu: {bv_str}"""

        # Bugünden başlayan 7 günlük sıralama
        DAY_NAMES_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        today_ist = datetime.now(ISTANBUL_TZ).date()
        today_weekday = today_ist.weekday()  # 0=Mon
        ordered_days = []
        for i in range(7):
            d = (today_weekday + i) % 7
            date = today_ist + timedelta(days=i)
            ordered_days.append(f"{DAY_NAMES_TR[d]} ({date.strftime('%d.%m')})")
        days_str = ", ".join(ordered_days)

        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": f"""Sen {creator_name} adlı kullanıcının kişisel sosyal medya stratejistisin. Sıcak ve enerjik bir hitapla (Merhaba {creator_name}!) başla. Kişiselleştirilmiş 7 günlük Twitter içerik planı oluştur.

{user_context}

ÖNEMLİ KURALLAR:
- Plan BUGÜNDEN başlamalı. Gün sırası: {days_str}
- Kullanıcının AZ kullandığı karakter ve tonları da plana dahil et (çeşitlilik)
- Her gün farklı content_type kullan (tweet, thread, quote karışık)
- Konu önerileri SOMUT ve GÜNCEL olsun ("Yapay zeka" değil, "OpenAI o3'ün yazılımcılar için anlamı" gibi)
- Kullanıcının niche'ine uygun konular seç
- Türkçe yaz

JSON formatında döndür:
{{
  "plan": [
    {{
      "day": "Gün Adı (GG.AA)",
      "content_type": "tweet|thread|quote",
      "topic_suggestion": "Somut, spesifik konu önerisi",
      "persona": "otorite|insider|saf|mentalist|haber",
      "tone": "natural|raw|polished|unhinged",
      "best_time": "09:00",
      "reasoning": "Neden bu gün bu içerik (1 cümle)"
    }}
  ],
  "weekly_goal": "Bu haftanın tek cümlelik hedefi"
}}

İlk gün = bugün ({ordered_days[0]}). 7 gün için plan oluştur."""},
                {"role": "user", "content": f"Niche: {body.niche}. 7 günlük içerik planı oluştur."}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        plan_data = json.loads(response.choices[0].message.content)
        now = datetime.now(timezone.utc).isoformat()
        monday = _this_monday().isoformat()

        # DB'ye upsert
        record = {
            "user_id": user.id,
            "account_id": account_id,
            "week_start": monday,
            "niche": body.niche,
            "plan": plan_data.get("plan", []),
            "weekly_goal": plan_data.get("weekly_goal", ""),
            "updated_at": now,
        }

        existing = sb.table("coach_weekly_plans") \
            .select("id") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .eq("week_start", monday) \
            .limit(1) \
            .execute()

        if existing.data:
            sb.table("coach_weekly_plans") \
                .update(record) \
                .eq("id", existing.data[0]["id"]) \
                .execute()
        else:
            record["id"] = str(uuid.uuid4())
            record["created_at"] = now
            sb.table("coach_weekly_plans").insert(record).execute()

        return {
            "plan": plan_data.get("plan", []),
            "weekly_goal": plan_data.get("weekly_goal", ""),
            "cached": False,
            "created_at": now,
            "week_start": monday,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Coach weekly plan create error: {e}")
        raise HTTPException(status_code=500, detail="Plan oluşturulamadı")


# ═══════════════════════════════════════════
# INSIGHTS — Eski endpoint (geriye uyum)
# ═══════════════════════════════════════════

@router.get("/insights")
async def get_insights(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Kullanıcının üretim geçmişini analiz et ve öneriler sun (eski API, geriye uyum)."""
    try:
        sb = get_supabase()

        # Son 100 generation
        gen_res = sb.table("generations") \
            .select("persona, tone, length, type, created_at") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .order("created_at", desc=True) \
            .limit(100) \
            .execute()

        gens = gen_res.data or []
        if not gens:
            return {"stats": {}, "insights": [], "message": "Henüz yeterli veri yok. Birkaç içerik ürettikten sonra koç önerileri burada belirecek."}

        # Favori sayısı
        fav_res = sb.table("favorites") \
            .select("id") \
            .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
            .is_("deleted_at", "null") \
            .execute()
        fav_count = len(fav_res.data or [])

        # Stats
        personas = Counter(g["persona"] for g in gens if g.get("persona"))
        tones_counter = Counter(g["tone"] for g in gens if g.get("tone"))
        lengths = Counter(g["length"] for g in gens if g.get("length"))
        types_counter = Counter(g["type"] for g in gens if g.get("type"))

        # Son 7 gün (rolling) üretim sayısı
        seven_ago = (datetime.now(ISTANBUL_TZ) - timedelta(days=7)).isoformat()
        last7_count = sum(1 for g in gens if g.get("created_at", "") >= seven_ago[:10])

        # Streak: ardışık gün hesaplama
        today_ist = datetime.now(ISTANBUL_TZ).date()
        day_set = set()
        for g in gens:
            ca = g.get("created_at", "")
            if ca:
                day_set.add(ca[:10])
        streak = 0
        check = today_ist
        for _ in range(60):
            if check.isoformat() in day_set:
                streak += 1
                check -= timedelta(days=1)
            else:
                break

        stats = {
            "total": len(gens),
            "favorites": fav_count,
            "favorite_ratio": round(fav_count / max(len(gens), 1) * 100),
            "last_7_days": last7_count,
            "current_streak": streak,
            "personas": dict(personas),
            "tones": dict(tones_counter),
            "lengths": dict(lengths),
            "types": dict(types_counter),
        }

        # Basit insights
        insights = []

        # En çok kullanılan persona
        if personas:
            top_p, top_count = personas.most_common(1)[0]
            pct = round(top_count / len(gens) * 100)
            if pct > 60:
                insights.append({
                    "type": "warning",
                    "title": f"'{top_p}' karakterini çok kullanıyorsun (%{pct})",
                    "description": "Diğer karakterleri de deneyerek farklı kitlelere ulaşabilirsin.",
                })

        # Az kullanılan persona
        all_p = {"otorite", "insider", "saf", "mentalist", "haber"}
        used_p = set(personas.keys())
        unused = all_p - used_p
        if unused:
            p = list(unused)[0]
            insights.append({
                "type": "suggestion",
                "title": f"'{p}' karakterini hiç denemedin",
                "description": f"Farklı bir yaklaşım için '{p}' karakteriyle bir içerik üretmeyi dene.",
                "action": f"{p} ile yaz",
            })

        # Favori oranı düşükse
        if stats["favorite_ratio"] < 15 and len(gens) >= 10:
            insights.append({
                "type": "tip",
                "title": "Favori oranın düşük",
                "description": "Beğendiğin içerikleri favorilere ekleyerek kalite barını yükselt. Bu sana en iyi prompt kombinasyonunu gösterir.",
            })

        # Favori oranı yüksekse
        if stats["favorite_ratio"] > 40 and fav_count >= 5:
            insights.append({
                "type": "praise",
                "title": "Kalite standartların yüksek! 🌟",
                "description": f"Üretimlerinin %{stats['favorite_ratio']}'ini favorilere ekledin. Seçici olmak iyi içeriğin işareti.",
            })

        return {"stats": stats, "insights": insights}

    except Exception as e:
        logger.error(f"Coach insights error: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu")

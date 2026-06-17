"""
AI Coach Feed Engine — Dinamik kart üretimi

Kart tipleri:
  opportunity  → Trend hijacking (priority 10)
  onboarding   → Cold start, yeni kullanıcı (priority 9)
  roast        → Olumsuz veri analizi (priority 6-8)
  toast        → Olumlu veri analizi (priority 2-4)
  daily_goal   → Bugünkü üretim durumu (priority 7)
  daily_complete → Günlük hedef aşıldı (priority 2)
  repurpose    → Eski favori yeniden yazım (priority 5)
  progress     → Haftalık karşılaştırma (priority 3-6)
  progress_down → Tempo düşüşü (priority 6)
  streak       → Ardışık gün serisi (priority 4)
"""

import logging
import random
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# ── Persona / Tone label'ları ──
PERSONA_LABELS = {
    "otorite": "Otorite", "insider": "Insider", "saf": "Saf",
    "mentalist": "Mentalist", "haber": "Haber",
}
TONE_LABELS = {
    "natural": "Natural", "raw": "Raw", "polished": "Polished", "unhinged": "Unhinged",
}
ALL_PERSONAS = list(PERSONA_LABELS.keys())
ALL_TONES = list(TONE_LABELS.keys())


from zoneinfo import ZoneInfo

ISTANBUL_TZ = ZoneInfo("Europe/Istanbul")


def _today_start():
    now = datetime.now(ISTANBUL_TZ)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _days_ago(n):
    return (datetime.now(ISTANBUL_TZ) - timedelta(days=n)).isoformat()


# ═══════════════════════════════════════════
# 1. TREND HIJACKING (Opportunity)
# ═══════════════════════════════════════════

async def get_opportunity_cards(user_id: str, sb) -> list:
    """Son 24 saatin en yüksek skorlu trendlerinden fırsat kartları."""
    cards = []
    try:
        cutoff = _days_ago(1)
        # Önce 70+ dene
        res = sb.table("trends") \
            .select("id, topic, summary, score, source_type, keywords, key_angles, suggested_hooks, created_at") \
            .gte("created_at", cutoff) \
            .gte("score", 70) \
            .order("score", desc=True) \
            .limit(3) \
            .execute()

        # Fallback: 0 sonuç gelirse eşiği 55'e düşür, en az 1 kart göster
        if not res.data:
            res = sb.table("trends") \
                .select("id, topic, summary, score, source_type, keywords, key_angles, suggested_hooks, created_at") \
                .gte("created_at", cutoff) \
                .gte("score", 55) \
                .order("score", desc=True) \
                .limit(1) \
                .execute()

        for trend in (res.data or []):
            # Freshness hesapla
            created = datetime.fromisoformat(trend["created_at"].replace("Z", "+00:00"))
            hours_ago = (datetime.now(timezone.utc) - created).total_seconds() / 3600

            if hours_ago < 1:
                freshness = "Az önce"
            elif hours_ago < 24:
                freshness = f"{int(hours_ago)} saat önce"
            else:
                freshness = f"{int(hours_ago / 24)} gün önce"

            # Suggested hook
            angles = trend.get("key_angles") or []
            hooks = trend.get("suggested_hooks") or []
            suggested_hook = (hooks[0] if hooks else angles[0]) if (hooks or angles) else ""

            cards.append({
                "type": "opportunity",
                "key": f"opportunity_{trend['id']}",
                "title": trend.get("topic", ""),
                "description": (trend.get("summary") or "")[:200],
                "trend_score": trend.get("score", 0),
                "freshness": freshness,
                "action": {
                    "label": "Hemen Yaz →",
                    "platform": "twitter",
                    "topic": f"{trend.get('topic', '')}. {(trend.get('summary') or '')[:150]}",
                    "persona": "insider",
                    "tone": "raw",
                    "hook": suggested_hook,
                },
                "priority": 10,
            })
    except Exception as e:
        logger.warning(f"Opportunity cards error: {e}")
    return cards


# ═══════════════════════════════════════════
# 2. ROAST & TOAST
# ═══════════════════════════════════════════

async def get_roast_toast_cards(user_id: str, sb) -> list:
    """Üretim verilerine dayalı kişiselleştirilmiş roast/toast kartları."""
    cards = []
    today = _today_start().strftime("%Y-%m-%d")

    try:
        # Son 50 generation
        gen_res = sb.table("generations") \
            .select("persona, tone, length, type, created_at, evolution_depth, variants") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .limit(50) \
            .execute()
        gens = gen_res.data or []

        if len(gens) < 5:
            # Yeterli veri yok, roast/toast üretme
            return cards

        # Favori sayısı
        fav_res = sb.table("favorites") \
            .select("id, generation_id, created_at") \
            .eq("user_id", user_id) \
            .is_("deleted_at", "null") \
            .execute()
        favs = fav_res.data or []
        fav_gen_ids = {f["generation_id"] for f in favs if f.get("generation_id")}

        recent_15 = gens[:15]
        recent_20 = gens[:20]

        # ── Persona çeşitliliği ──
        personas = [g["persona"] for g in recent_15 if g.get("persona")]
        if personas:
            unique_personas = set(personas)
            if len(unique_personas) == 1:
                p = personas[0]
                other = random.choice([x for x in ALL_PERSONAS if x != p])
                cards.append({
                    "type": "roast",
                    "key": f"roast_persona_{today}",
                    "title": f"Hep aynı karakter: {PERSONA_LABELS.get(p, p)}",
                    "description": f"Son 15 üretiminde sadece '{PERSONA_LABELS.get(p, p)}' kullandın. Monotonlaşıyorsun. Bugün '{PERSONA_LABELS.get(other, other)}' dene.",
                    "action": {
                        "label": f"{PERSONA_LABELS.get(other, other)} ile Yaz →",
                        "platform": "twitter",
                        "persona": other,
                    },
                    "priority": 8,
                })
            elif len(unique_personas) >= 4:
                cards.append({
                    "type": "toast",
                    "key": f"toast_persona_{today}",
                    "title": f"Çok yönlü performans! 🎭",
                    "description": f"Son 15 üretiminde {len(unique_personas)} farklı karakter kullandın. Harika çeşitlilik.",
                    "priority": 3,
                })

        # ── Tone çeşitliliği ──
        tones = [g["tone"] for g in recent_15 if g.get("tone")]
        if tones:
            unique_tones = set(tones)
            if len(unique_tones) == 1:
                t = tones[0]
                other_tone = random.choice([x for x in ALL_TONES if x != t])
                cards.append({
                    "type": "roast",
                    "key": f"roast_tone_{today}",
                    "title": f"Hep aynı ton: {TONE_LABELS.get(t, t)}",
                    "description": f"Son 15 üretiminde hep '{TONE_LABELS.get(t, t)}' tonu. Farklı tonlar farklı kitlelere ulaşır.",
                    "action": {
                        "label": f"{TONE_LABELS.get(other_tone, other_tone)} Dene →",
                        "platform": "twitter",
                        "tone": other_tone,
                    },
                    "priority": 7,
                })

        # ── Favori oranı ──
        recent_20_ids = {g.get("id") for g in recent_20 if g.get("id")}
        # Generation ID olmayabilir select'te, generation_id ile eşleştir
        recent_fav_count = 0
        for g in recent_20:
            # generations tablosunda id yok select'te, created_at ile eşleştir
            pass
        # Basit yaklaşım: toplam favori / toplam generation oranı
        total_gens = len(gens)
        total_favs = len(favs)
        fav_rate = total_favs / max(total_gens, 1)

        if fav_rate < 0.1 and total_gens >= 10:
            cards.append({
                "type": "roast",
                "key": f"roast_favorites_{today}",
                "title": "Favorilerin boş 😬",
                "description": f"{total_gens} üretiminin sadece {total_favs} tanesini favorilere ekledin (%{int(fav_rate * 100)}). Geçmişe gidip en iyi üretimlerini favorilere ekle.",
                "action": {
                    "label": "Geçmişe Git →",
                    "route": "/dashboard/history",
                },
                "priority": 7,
            })
        elif fav_rate > 0.35 and total_favs >= 5:
            cards.append({
                "type": "toast",
                "key": f"toast_favorites_{today}",
                "title": "Kalite patlaması! 💎",
                "description": f"Üretimlerinin %{int(fav_rate * 100)}'ini favorilere ekledin. Üst düzey seçicilik.",
                "priority": 3,
            })

        # ── Uzunluk analizi ──
        # character_count'ı variants'tan hesapla
        char_counts = []
        for g in recent_20:
            variants = g.get("variants") or []
            if variants and isinstance(variants, list):
                avg_len = sum(len(v.get("content", "") if isinstance(v, dict) else str(v)) for v in variants) / max(len(variants), 1)
                if avg_len > 0:
                    char_counts.append(int(avg_len))
        if char_counts:
            avg_chars = sum(char_counts) / len(char_counts)
            if avg_chars > 260:
                cards.append({
                    "type": "roast",
                    "key": f"roast_length_{today}",
                    "title": "Tweet'lerin çok uzun ✂️",
                    "description": f"Ortalama {int(avg_chars)} karakter yazıyorsun. Twitter'da 100-200 karakter arası daha çok etkileşim alır.",
                    "action": {
                        "label": "Kısa Dene →",
                        "platform": "twitter",
                        "length": "micro",
                    },
                    "priority": 6,
                })
            elif avg_chars < 80 and avg_chars > 0:
                cards.append({
                    "type": "roast",
                    "key": f"roast_length_short_{today}",
                    "title": "Tweet'lerin çok kısa",
                    "description": f"Ortalama {int(avg_chars)} karakter. Biraz daha derinlik katmak etkileşimi artırabilir.",
                    "action": {
                        "label": "Punch Dene →",
                        "platform": "twitter",
                        "length": "punch",
                    },
                    "priority": 5,
                })

        # ── Format çeşitliliği ──
        content_types = [g.get("type", "tweet") for g in recent_15]
        unique_types = set(content_types)
        if len(unique_types) == 1 and len(content_types) >= 10:
            ct = content_types[0]
            cards.append({
                "type": "roast",
                "key": f"roast_format_{today}",
                "title": f"Hep aynı format: {ct}",
                "description": f"Son 15 üretiminde sadece '{ct}' formatı kullandın. Thread veya quote tweet dene, çeşitlilik etkileşimi artırır.",
                "priority": 6,
            })

        # ── Evolution kullanımı ──
        evolved = [g for g in gens if (g.get("evolution_depth") or 0) > 0]
        if len(evolved) == 0 and len(gens) >= 10:
            cards.append({
                "type": "roast",
                "key": f"roast_evolution_{today}",
                "title": "Geliştir özelliğini hiç kullanmadın",
                "description": "İlk üretimi rafine etmek kaliteyi ciddi artırır. Bir sonraki üretiminde 'Geliştir' butonunu dene.",
                "priority": 5,
            })

    except Exception as e:
        logger.warning(f"Roast/toast cards error: {e}")
    return cards


# ═══════════════════════════════════════════
# 3. GÜNLÜK HEDEF
# ═══════════════════════════════════════════

async def get_daily_goal_cards(user_id: str, sb) -> list:
    """Bugün kaç üretim yapılmış kontrolü."""
    cards = []
    today = _today_start().strftime("%Y-%m-%d")
    try:
        today_iso = _today_start().isoformat()
        res = sb.table("generations") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .gte("created_at", today_iso) \
            .execute()

        count = res.count if hasattr(res, 'count') and res.count is not None else len(res.data or [])

        if count == 0:
            cards.append({
                "type": "daily_goal",
                "key": f"daily_goal_{today}",
                "title": "Bugün henüz bir şey üretmedin",
                "description": "Tutarlılık büyümenin anahtarı. Küçük bir adımla başla.",
                "action": {
                    "label": "Yaz →",
                    "platform": "twitter",
                },
                "priority": 7,
            })
        elif count >= 3:
            cards.append({
                "type": "daily_complete",
                "key": f"daily_complete_{today}",
                "title": f"Bugünkü hedefini aştın! 🎉",
                "description": f"Bugün {count} içerik ürettin. Harika tempo devam et.",
                "priority": 2,
            })
    except Exception as e:
        logger.warning(f"Daily goal cards error: {e}")
    return cards


# ═══════════════════════════════════════════
# 4. REPURPOSE
# ═══════════════════════════════════════════

async def get_repurpose_cards(user_id: str, sb) -> list:
    """14+ gün önceki favorileri yeniden yazım önerisi."""
    cards = []
    try:
        cutoff = _days_ago(14)
        res = sb.table("favorites") \
            .select("id, content, created_at") \
            .eq("user_id", user_id) \
            .is_("deleted_at", "null") \
            .lte("created_at", cutoff) \
            .order("created_at", desc=True) \
            .limit(10) \
            .execute()

        old_favs = res.data or []
        if not old_favs:
            return cards

        # Rastgele 1 tane seç
        fav = random.choice(old_favs)
        content = fav.get("content", "")
        if not content or len(content) < 20:
            return cards

        # Farklı persona/tone öner
        other_persona = random.choice(ALL_PERSONAS)
        other_tone = random.choice(ALL_TONES)

        cards.append({
            "type": "repurpose",
            "key": f"repurpose_{fav['id']}",
            "title": "Bu favorini hatırlıyor musun? ♻️",
            "description": f'"{content[:120]}{"..." if len(content) > 120 else ""}"',
            "original_content": content,
            "action": {
                "label": "Yeniden Yaz →",
                "platform": "twitter",
                "topic": content[:300],
                "persona": other_persona,
                "tone": other_tone,
            },
            "priority": 5,
        })
    except Exception as e:
        logger.warning(f"Repurpose cards error: {e}")
    return cards


# ═══════════════════════════════════════════
# 5. PROGRESS & STREAK
# ═══════════════════════════════════════════

async def get_progress_cards(user_id: str, sb) -> list:
    """Haftalık karşılaştırma ve streak hesaplama."""
    cards = []
    today = _today_start()
    today_str = today.strftime("%Y-%m-%d")

    try:
        # Son 14 günün üretimlerini çek
        fourteen_ago = _days_ago(14)
        res = sb.table("generations") \
            .select("created_at") \
            .eq("user_id", user_id) \
            .gte("created_at", fourteen_ago) \
            .execute()

        all_gens = res.data or []
        if not all_gens:
            return cards

        # Gün bazlı grupla
        day_counts = {}
        for g in all_gens:
            day = g["created_at"][:10]  # YYYY-MM-DD
            day_counts[day] = day_counts.get(day, 0) + 1

        # Bu hafta vs geçen hafta
        this_week_start = today - timedelta(days=today.weekday())  # Pazartesi
        last_week_start = this_week_start - timedelta(days=7)

        this_week_count = 0
        last_week_count = 0
        for day_str, count in day_counts.items():
            day_date = datetime.strptime(day_str, "%Y-%m-%d")
            if day_date >= this_week_start.replace(tzinfo=None):
                this_week_count += count
            elif day_date >= last_week_start.replace(tzinfo=None):
                last_week_count += count

        # Haftalık karşılaştırma
        if last_week_count > 0:
            change = ((this_week_count - last_week_count) / last_week_count) * 100
            week_key = this_week_start.strftime("%Y-W%W")

            if change > 20:
                cards.append({
                    "type": "progress",
                    "key": f"progress_{week_key}",
                    "title": f"Bu hafta %{int(change)} artış! 📈",
                    "description": f"Geçen hafta {last_week_count}, bu hafta {this_week_count} üretim. Momentum harika.",
                    "priority": 3,
                })
            elif change < -30:
                cards.append({
                    "type": "progress_down",
                    "key": f"progress_down_{week_key}",
                    "title": "Tempo düşüyor ⚠️",
                    "description": f"Geçen hafta {last_week_count} üretim vardı, bu hafta henüz {this_week_count}.",
                    "action": {
                        "label": "Hemen Başla →",
                        "platform": "twitter",
                    },
                    "priority": 6,
                })

        # ── Streak hesaplama ──
        streak = 0
        check_date = today
        for i in range(30):  # Max 30 gün geriye bak
            day_str = check_date.strftime("%Y-%m-%d")
            if day_counts.get(day_str, 0) > 0:
                streak += 1
                check_date -= timedelta(days=1)
            else:
                break

        if streak >= 3:
            cards.append({
                "type": "streak",
                "key": f"streak_{today_str}",
                "title": f"🔥 {streak} gün üst üste!",
                "description": f"{streak} gündür her gün içerik üretiyorsun. Seriyi bozmamak için bugün de devam et.",
                "priority": 4,
            })

    except Exception as e:
        logger.warning(f"Progress cards error: {e}")
    return cards


# ═══════════════════════════════════════════
# 6. ONBOARDING (Cold Start)
# ═══════════════════════════════════════════

async def get_onboarding_cards(user_id: str, sb) -> list:
    """Yeni kullanıcı veya yeterli verisi olmayan kullanıcılar için onboarding kartları."""
    cards = []
    try:
        # Toplam generation sayısı
        gen_res = sb.table("generations") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        gen_count = gen_res.count if hasattr(gen_res, 'count') and gen_res.count is not None else len(gen_res.data or [])

        if gen_count == 0:
            cards.append({
                "type": "onboarding",
                "key": "onboarding_first",
                "title": "Henüz seni tanımıyorum 👋",
                "description": "Sana taktik verebilmem için önce birkaç içerik üretmen lazım. İlk tweetini oluşturarak başla!",
                "action": {
                    "label": "İlk İçeriğini Üret →",
                    "platform": "twitter",
                },
                "priority": 9,
            })
        elif gen_count < 5:
            cards.append({
                "type": "onboarding",
                "key": "onboarding_few",
                "title": f"Harika başlangıç! ({gen_count}/5)",
                "description": f"Şu ana kadar {gen_count} içerik ürettin. 5'e ulaştığında sana kişiselleştirilmiş öneriler sunmaya başlayacağım.",
                "action": {
                    "label": "Üretmeye Devam →",
                    "platform": "twitter",
                },
                "priority": 9,
            })

        # Connected account kontrolü
        acc_res = sb.table("connected_accounts") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        acc_count = acc_res.count if hasattr(acc_res, 'count') and acc_res.count is not None else len(acc_res.data or [])

        if acc_count == 0 and gen_count >= 1:
            cards.append({
                "type": "onboarding",
                "key": "onboarding_connect",
                "title": "X hesabını bağla 🔗",
                "description": "Hesabını bağlayarak avatarını göster ve daha kişiselleştirilmiş öneriler al.",
                "priority": 6,
            })

        # Style profile kontrolü
        style_res = sb.table("style_profiles") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        style_count = style_res.count if hasattr(style_res, 'count') and style_res.count is not None else len(style_res.data or [])

        if style_count == 0 and gen_count >= 3:
            cards.append({
                "type": "onboarding",
                "key": "onboarding_style",
                "title": "Stil profilini oluştur ✨",
                "description": "Persona Lab'da bir Twitter hesabı analiz ederek kendi yazım stilini klonla. İçeriklerin çok daha özgün olacak.",
                "priority": 7,
            })

    except Exception as e:
        logger.warning(f"Onboarding cards error: {e}")
    return cards

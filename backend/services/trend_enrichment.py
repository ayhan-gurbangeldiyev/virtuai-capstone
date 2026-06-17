"""
Trend Context Enrichment — key_angles, suggested_hooks, content_pillars.

Trend item'a zengin context ekler:
- key_angles: Konunun farklı açıları (3-5 adet)
- suggested_hooks: Content pillar bazlı hook önerileri (insight/building/hot_take/engagement)
- content_pillars: Uygun içerik türleri

social-media-agent skill'inden ilham: %40 insight, %30 building, %20 hot_take, %10 engagement.
"""
import os
import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

ENRICHMENT_PROMPT = """Sen bir sosyal medya içerik stratejistisin. Trend konusu ve sinyalleri verilecek.
Bu konu hakkında içerik üretecek bir kullanıcı için zengin context oluştur.

KONU: {topic}
ÖZET: {summary}
KAYNAKLAR: {sources}
ENGAGEMENT: {engagement} toplam beğeni, {signal_count} farklı kaynak

Aşağıdaki JSON formatında döndür (Türkçe yaz):

{{
  "key_angles": [
    "Açı 1: Konunun spesifik bir boyutu",
    "Açı 2: Farklı bir perspektif",
    "Açı 3: Tartışmalı veya az bilinen bir yön"
  ],
  "suggested_hooks": {{
    "insight": "Sektör analizi açısından tweet hook'u (veri veya trend bazlı)",
    "building": "Kişisel deneyim açısından hook (Ben de denedim/kullandım tarzı)",
    "hot_take": "Tartışmalı/provokatif hook (unpopular opinion tarzı)",
    "engagement": "Soru veya anket tarzı etkileşim hook'u"
  }},
  "content_pillars": ["hot_take", "comparison", "tutorial_teaser", "thread", "news", "opinion"]
}}

KURALLAR:
- key_angles 3-5 adet, her biri farklı açıdan
- suggested_hooks 4 adet, her biri farklı content pillar'a göre
- content_pillars: Bu konuya en uygun 2-4 tür seç
- Hook'lar doğrudan kullanılabilir tweet açılışları olsun, generic olmasın
- Türkçe yaz
- SADECE JSON döndür, başka bir şey yazma
"""


async def enrich_trend(
    topic: str,
    summary: str,
    source_tweets: list = None,
    engagement_total: int = 0,
    signal_count: int = 1,
) -> Optional[dict]:
    """Trend item'a key_angles, suggested_hooks, content_pillars ekle."""

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("OPENAI_API_KEY yok, enrichment atlanıyor")
        return None

    # Kaynak bilgisini formatla
    sources_text = "RSS"
    if source_tweets:
        usernames = list(set(t.get("username", "?") for t in source_tweets[:5]))
        sources_text = ", ".join(f"@{u}" for u in usernames)
        if any(t.get("tier") == 1 for t in source_tweets):
            sources_text += " (resmi hesap)"

    prompt = ENRICHMENT_PROMPT.format(
        topic=topic,
        summary=summary[:500],
        sources=sources_text,
        engagement=engagement_total,
        signal_count=signal_count,
    )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 800,
                    "temperature": 0.7,
                    "response_format": {"type": "json_object"},
                },
            )
            if resp.status_code == 200:
                content = resp.json()["choices"][0]["message"]["content"]
                enrichment = json.loads(content)

                # Validate
                if "key_angles" in enrichment and "suggested_hooks" in enrichment:
                    return enrichment
                else:
                    logger.warning(f"Enrichment eksik alan: {list(enrichment.keys())}")
                    return None
    except Exception as e:
        logger.error(f"Enrichment hatası: {e}")

    return None


def calculate_multi_signal_score(
    base_score: int,
    engagement_total: int = 0,
    signal_count: int = 1,
    has_tier1: bool = False,
    has_tier2: bool = False,
    age_hours: float = 0,
) -> int:
    """Multi-signal trend skoru hesapla.

    base_score: GPT'nin verdiği ham skor (0-100)
    engagement_total: Toplam Twitter like
    signal_count: Kaç farklı kaynaktan geldi
    has_tier1: Resmi hesaptan sinyal var mı
    has_tier2: Key person'dan sinyal var mı
    age_hours: Kaç saat önce

    Returns: 0-100 arası final skor
    """
    # Engagement boost (max +20)
    engagement_boost = min(20, engagement_total / 1000) if engagement_total else 0

    # Multi-source boost (max +15, her ekstra kaynak +5)
    source_boost = min(15, max(0, signal_count - 1) * 5)

    # Insider boost
    insider_boost = 10 if has_tier2 else 0

    # Official boost
    official_boost = 5 if has_tier1 else 0

    # Freshness penalty (mevcut trend engine ile uyumlu)
    freshness_penalty = 0
    if age_hours > 48:
        freshness_penalty = 50
    elif age_hours > 24:
        freshness_penalty = 30
    elif age_hours > 12:
        freshness_penalty = 15

    final = base_score + engagement_boost + source_boost + insider_boost + official_boost - freshness_penalty
    return max(0, min(100, int(final)))

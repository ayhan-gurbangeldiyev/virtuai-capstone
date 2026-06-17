"""
VIP Source Scoring — Tier 1 kaynaklara çarpan, semantic trigger kelimelere bonus.

3 katman:
1. VIP Source Multiplier: Resmi AI lab/product hesaplarından gelen içerik 2-3x boost
2. Semantic Triggers: "Introducing", "Launch", "Breach" gibi kelimeler +15-25 bonus
3. Red Alert Detection: Birden fazla VIP kaynağın aynı konuyu işlemesi = mega boost
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# ─── VIP Twitter Hesapları (Tier 0: Her tweet'leri otomatik yüksek skor) ───
VIP_TWITTER_ACCOUNTS = {
    # AI Labs (resmi ürün hesapları)
    "openai", "anthropicai", "claudeai", "chatgptapp", "googledeepmind",
    "googleai", "mistralai", "aiatmeta", "stabilityai", "cohereai",
    "deepseek_ai", "xai", "perplexity_ai",
    # AI Products
    "cursor_ai", "v0", "claudecode", "windsurf_ai", "huggingface",
    "vercel", "ollama", "notionhq",
    # Key People (CEO/CTO level)
    "sama", "daborekarioamodei", "demishassabis", "karpathy", "ylecun",
    "jeffdean",
}

# ─── VIP RSS Kaynakları ───
VIP_RSS_SOURCES = {
    "anthropic news", "anthropic research", "openai blog",
    "google ai blog", "google deepmind blog", "microsoft research",
}

# ─── Semantic Trigger Kelimeleri ───
# Kategori: (kelimeler, bonus_puan)
SEMANTIC_TRIGGERS = {
    "launch": {
        "keywords": [
            r"\bintroducing\b", r"\blaunching?\b", r"\breleasing?\b",
            r"\bavailable now\b", r"\bjust released\b", r"\bnew in\b",
            r"\bannouncing\b", r"\bwe.re releasing\b", r"\bwe.ve launched\b",
            r"\brolling out\b", r"\bnow available\b", r"\byayınladı\b",
            r"\bduyurdu\b", r"\bçıkardı\b",
        ],
        "bonus": 20,
        "label": "Ürün Lansmanı",
    },
    "scandal": {
        "keywords": [
            r"\bstolen\b", r"\bbreach\b", r"\bhack(ed|ing)?\b", r"\bleak(ed|s)?\b",
            r"\bscandal\b", r"\bfraud\b", r"\bdistillation attack\b",
            r"\billicit\b", r"\bsafeguard.*(remov|bypass|argue against)\b",
            r"\bcasusluk\b", r"\bsızıntı\b", r"\bskandal\b",
        ],
        "bonus": 25,
        "label": "Skandal/Güvenlik",
    },
    "milestone": {
        "keywords": [
            r"\bstate.of.the.art\b", r"\bsota\b", r"\brecord\b",
            r"\bbenchmark\b", r"\bbreakthrough\b", r"\bfirst ever\b",
            r"\b\$\d+\s*(billion|million|B|M)\b", r"\bfunding\b",
            r"\bacquisition\b", r"\bsatın al\b",
        ],
        "bonus": 15,
        "label": "Kilometre Taşı",
    },
    "breaking": {
        "keywords": [
            r"\bbreaking\b", r"\bjust in\b", r"\bson dakika\b",
            r"\burgent\b", r"\bacil\b", r"\bkritik\b",
        ],
        "bonus": 20,
        "label": "Son Dakika",
    },
}


def is_vip_twitter(username: str) -> bool:
    """Twitter hesabının VIP olup olmadığını kontrol et."""
    return username.lower().strip("@") in VIP_TWITTER_ACCOUNTS


def is_vip_rss(source_name: str) -> bool:
    """RSS kaynağının VIP olup olmadığını kontrol et."""
    return source_name.lower().strip() in VIP_RSS_SOURCES


def detect_semantic_triggers(text: str) -> list:
    """Metinde semantic trigger kelimeleri tespit et.

    Returns:
        List of {"category": str, "label": str, "bonus": int, "matched": str}
    """
    if not text:
        return []

    text_lower = text.lower()
    triggers_found = []

    for category, config in SEMANTIC_TRIGGERS.items():
        for pattern in config["keywords"]:
            match = re.search(pattern, text_lower)
            if match:
                triggers_found.append({
                    "category": category,
                    "label": config["label"],
                    "bonus": config["bonus"],
                    "matched": match.group(0),
                })
                break  # Aynı kategoriden bir tane yeter

    return triggers_found


def apply_vip_scoring(
    base_score: int,
    source_name: str = "",
    twitter_username: str = "",
    content_text: str = "",
    tier: Optional[int] = None,
) -> dict:
    """VIP kaynağa çarpan, semantic trigger'a bonus uygula.

    Returns:
        {
            "final_score": int,
            "vip_boost": int,
            "trigger_boost": int,
            "triggers": list,
            "is_vip": bool,
            "reason": str,
        }
    """
    vip_boost = 0
    trigger_boost = 0
    is_vip = False
    reasons = []

    # 1. VIP Source Multiplier — tiered boost based on base quality
    # High base = high boost, low base = modest boost (prevents inflation)
    if twitter_username and is_vip_twitter(twitter_username):
        is_vip = True
        if base_score >= 80:
            vip_boost = 12
        elif base_score >= 65:
            vip_boost = 10
        else:
            vip_boost = 8
        reasons.append(f"VIP Twitter @{twitter_username} (+{vip_boost})")

    elif source_name and is_vip_rss(source_name):
        is_vip = True
        if base_score >= 80:
            vip_boost = 10
        elif base_score >= 65:
            vip_boost = 8
        else:
            vip_boost = 6
        reasons.append(f"VIP RSS {source_name} (+{vip_boost})")

    elif tier == 1:
        is_vip = True
        if base_score >= 80:
            vip_boost = 8
        elif base_score >= 65:
            vip_boost = 6
        else:
            vip_boost = 5
        reasons.append(f"Tier 1 source (+{vip_boost})")

    # 2. Semantic Triggers — only apply if base quality is good (>= 70)
    # Low-quality content with trigger words = likely spam, not real news
    triggers = detect_semantic_triggers(content_text)
    if triggers and base_score >= 70:
        best_trigger = max(triggers, key=lambda t: t["bonus"])
        trigger_boost = best_trigger["bonus"]
        reasons.append(f"Trigger: {best_trigger['label']} '{best_trigger['matched']}' (+{trigger_boost})")
    elif triggers:
        # Log but don't boost — low base + trigger = suspicious
        best_trigger = max(triggers, key=lambda t: t["bonus"])
        reasons.append(f"Trigger ignored (base {base_score} < 70): {best_trigger['label']}")

    # Final skor (max 99, 100 hiçbir zaman verilmez)
    final_score = min(base_score + vip_boost + trigger_boost, 99)

    # Freshness hard cap hala geçerli (trend_engine'de uygulanır)

    result = {
        "final_score": final_score,
        "vip_boost": vip_boost,
        "trigger_boost": trigger_boost,
        "triggers": triggers,
        "is_vip": is_vip,
        "reason": " | ".join(reasons) if reasons else "Standard scoring",
    }

    if vip_boost or trigger_boost:
        logger.info(f"VIP Scoring: {base_score} → {final_score} ({result['reason']})")

    return result

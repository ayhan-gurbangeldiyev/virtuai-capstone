"""Type Hype Trend Relevance Engine

Multi-dimensional, score-based relevance system for the trend pipeline.
Replaces the old binary keyword matching with a layered scoring approach.

Usage points:
  - Pre-AI filter: Block noise before sending to GPT (saves tokens)
  - Post-AI guard: Validate AI output quality before serving to users
  - Score adjustment: Apply deterministic corrections to AI scores

Architecture:
  Signal → pre_filter() → GPT Analysis → post_filter() → adjust_score() → Serve
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Domain Taxonomy — Type Hype's focus areas with weighted terms
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {"AI", "Dev", "Design", "Crypto", "Startup", "Marketing", "Business", "Science", "Lifestyle", "Education", "Entertainment", "News"}

# Each domain has terms with weights (1-3).
# 3 = core signal (e.g. "openai" for AI)
# 2 = strong indicator (e.g. "neural network")
# 1 = weak/contextual (e.g. "model" — could be fashion model)
DOMAIN_SIGNALS: dict[str, dict[str, int]] = {
    "AI": {
        # Companies & products
        "openai": 3, "anthropic": 3, "deepmind": 3, "deepseek": 3,
        "mistral": 3, "cohere": 3, "stability ai": 3, "midjourney": 3,
        "gpt": 3, "claude": 3, "gemini": 2, "llama": 2, "phi": 2,
        "copilot": 2, "cursor": 2, "windsurf": 2, "v0": 2,
        "perplexity": 2, "huggingface": 3, "hugging face": 3,
        "replicate": 2, "together ai": 2, "groq": 2, "fireworks ai": 2,
        # Concepts
        "llm": 3, "large language model": 3, "foundation model": 3,
        "generative ai": 3, "gen ai": 3, "genai": 3,
        "artificial intelligence": 3, "machine learning": 2,
        "deep learning": 2, "neural network": 2, "transformer": 2,
        "fine-tuning": 2, "fine tuning": 2, "finetuning": 2,
        "rag": 2, "retrieval augmented": 2,
        "prompt engineering": 2, "prompt": 1,
        "inference": 2, "embedding": 2, "tokenizer": 2,
        "benchmark": 2, "sota": 2, "reasoning": 1,
        "ai agent": 3, "ai agents": 3, "agentic": 2,
        "multimodal": 2, "text-to-image": 2, "text-to-video": 2,
        "diffusion model": 2, "image generation": 2,
        "computer vision": 2, "nlp": 2, "speech-to-text": 2,
        "chatbot": 2, "ai safety": 2, "alignment": 2,
        "open source ai": 2, "open-source ai": 2,
        "ai regulation": 2, "ai policy": 2,
    },
    "Tech": {
        # Dev tools & platforms
        "github": 2, "gitlab": 2, "vercel": 2, "netlify": 2,
        "supabase": 2, "firebase": 2, "aws": 2, "azure": 2, "gcp": 2,
        "docker": 2, "kubernetes": 2, "terraform": 2,
        "typescript": 2, "python": 1, "rust": 2, "golang": 2,
        "react": 2, "next.js": 2, "nextjs": 2, "svelte": 2, "vue": 2,
        "node.js": 2, "nodejs": 2, "deno": 2, "bun": 2,
        # Concepts
        "api": 1, "sdk": 2, "cli": 1, "open source": 1,
        "developer": 1, "devtools": 2, "dev tools": 2,
        "saas": 2, "paas": 2, "serverless": 2, "edge computing": 2,
        "web3": 1, "blockchain": 1,
        "cybersecurity": 2, "zero-day": 2, "vulnerability": 2,
        "no-code": 2, "low-code": 2, "automation": 1,
        "database": 1, "sql": 1, "nosql": 2,
    },
    "Business": {
        "startup": 2, "funding": 3, "seed round": 3,
        "series a": 3, "series b": 3, "series c": 3,
        "ipo": 3, "acquisition": 2, "merger": 2,
        "venture capital": 3, "vc": 2, "angel investor": 2,
        "valuation": 2, "unicorn": 2, "bootstrapped": 2,
        "revenue": 1, "arr": 2, "mrr": 2,
        "creator economy": 2, "creator": 1, "monetization": 2,
        "growth hacking": 2, "product-market fit": 2,
        "product hunt": 2, "launch": 1, "launched": 1,
        "social growth": 2, "growth loop": 2, "viral": 1,
        "saas metrics": 2, "churn": 2, "retention": 1,
        "pivot": 2, "scale": 1, "exit": 2,
        "y combinator": 3, "yc": 2, "techstars": 2,
    },
    "Crypto": {
        "bitcoin": 3, "ethereum": 3, "solana": 3,
        "defi": 3, "nft": 2, "web3": 2, "dao": 2,
        "smart contract": 2, "token": 1, "altcoin": 2,
        "crypto exchange": 3, "binance": 3, "coinbase": 3,
        "stablecoin": 2, "layer 2": 2, "l2": 1,
    },
}

# ---------------------------------------------------------------------------
# Noise / Exclusion Rules
# ---------------------------------------------------------------------------

# Hard-block terms: if found, trend is instantly rejected.
# Organized by domain for maintainability.
NOISE_TERMS: dict[str, list[str]] = {
    "sports": [
        "futbol", "football", "soccer", "basketbol", "basketball",
        "maç", "match score", "league", "champions league", "premier league",
        "transfer", "gol", "goal", "stadyum", "stadium",
        "olimpiyat", "olympics", "fifa", "uefa",
    ],
    "entertainment": [
        "magazin", "celebrity", "paparazzi", "red carpet",
        "dizi", "tv show", "reality show", "netflix series",
        "box office", "oscar", "grammy", "emmy",
        "kardashian", "hollywood gossip",
    ],
    "weather_disaster": [
        "hava durumu", "weather forecast", "meteoroloji",
        "deprem", "earthquake", "tsunami", "sel", "flood",
        "kasırga", "hurricane", "tornado", "fırtına",
    ],
    "travel_transport": [
        "havalimanı", "airport", "uçuş", "flight delay",
        "airline", "baggage", "passport control",
        "otobüs", "tren saatleri", "trafik durumu",
    ],
    "politics": [
        "seçim", "election results", "oy", "ballot",
        "siyasi parti", "political party", "cumhurbaşkanı",
        "başbakan", "prime minister", "congress vote",
        "sanction", "yaptırım",
    ],
    "health_medical": [
        "diyet", "kilo verme", "weight loss miracle",
        "alternatif tıp", "homeopathy", "detox",
    ],
    "spam_patterns": [
        "click here", "buy now", "limited offer",
        "100% free", "act now", "congratulations you won",
        "make money fast", "work from home easy",
    ],
}

# Flatten for fast lookup
_ALL_NOISE_TERMS: list[str] = []
for _terms in NOISE_TERMS.values():
    _ALL_NOISE_TERMS.extend(_terms)


# ---------------------------------------------------------------------------
# Trusted / High-quality sources
# ---------------------------------------------------------------------------

TRUSTED_SOURCES: dict[str, int] = {
    # Operatör torpili (Berkay 11 Haz 2026): upcornco haberleri skorlamada
    # öne geçsin — en yüksek kaynak bonusu.
    "upcornco": 12,
    # Tier 1 — Premier tech/AI sources (bonus: +8)
    "techcrunch": 8, "the verge": 8, "wired": 8,
    "ars technica": 8, "mit technology review": 8,
    "reuters": 8, "bloomberg": 8, "financial times": 8,
    # Tier 2 — Strong tech sources (bonus: +5)
    "hacker news": 5, "hackernews": 5,
    "product hunt": 5, "producthunt": 5,
    "venturebeat": 5, "the information": 5,
    "semafor": 5, "platformer": 5,
    "ben thompson": 5, "stratechery": 5,
    # Tier 3 — Good sources (bonus: +3)
    "engadget": 3, "zdnet": 3, "cnet": 3,
    "9to5mac": 3, "9to5google": 3,
    "tom's hardware": 3, "anandtech": 3,
    # Company blogs (informative but self-promo)
    "openai blog": 2, "anthropic blog": 2, "google ai blog": 2,
    "meta ai": 2, "nvidia blog": 2, "microsoft blog": 2,
}


# ---------------------------------------------------------------------------
# Regex compilation
# ---------------------------------------------------------------------------

_WORD_BOUNDARY = r"a-z0-9çğıöşüâîû"


def _compile(term: str) -> re.Pattern:
    escaped = re.escape(term.lower())
    # Replace escaped spaces with \s+ for flexible whitespace matching
    escaped = escaped.replace(r"\ ", r"\s+").replace(" ", r"\s+")
    return re.compile(
        rf"(?<![{_WORD_BOUNDARY}]){escaped}(?![{_WORD_BOUNDARY}])",
        re.IGNORECASE,
    )


# Pre-compiled patterns
_DOMAIN_PATTERNS: dict[str, list[tuple[re.Pattern, int]]] = {}
for _cat, _terms in DOMAIN_SIGNALS.items():
    _DOMAIN_PATTERNS[_cat] = [(_compile(t), w) for t, w in _terms.items()]

_NOISE_PATTERNS: list[re.Pattern] = [_compile(t) for t in _ALL_NOISE_TERMS]

_TRUSTED_PATTERNS: list[tuple[re.Pattern, int]] = [
    (_compile(src), bonus) for src, bonus in TRUSTED_SOURCES.items()
]


# ---------------------------------------------------------------------------
# Core Data Types
# ---------------------------------------------------------------------------

@dataclass
class RelevanceResult:
    """Result of a relevance check with detailed breakdown."""
    is_relevant: bool
    relevance_score: float  # 0-100
    matched_category: str  # Best matching category
    noise_detected: bool
    noise_reasons: list[str] = field(default_factory=list)
    domain_scores: dict[str, float] = field(default_factory=dict)
    source_bonus: int = 0
    freshness_penalty: float = 0.0
    quality_flags: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_relevance(
    topic: str,
    summary: str = "",
    keywords: Optional[Iterable[str]] = None,
    source_name: str = "",
    published_at: Optional[str] = None,
    score_threshold: float = 30.0,
) -> RelevanceResult:
    """Compute multi-dimensional relevance score for a trend.

    Args:
        topic: Trend headline/title
        summary: Description or summary text
        keywords: Associated keywords
        source_name: Name of the source (for trust bonus)
        published_at: ISO datetime string (for freshness)
        score_threshold: Minimum score to be considered relevant

    Returns:
        RelevanceResult with full breakdown
    """
    text = _join_text(topic, summary, keywords)

    if not text:
        return RelevanceResult(
            is_relevant=False, relevance_score=0.0,
            matched_category="", noise_detected=False,
            quality_flags=["empty_content"],
        )

    # Step 1: Noise detection (instant reject)
    noise_reasons = _detect_noise(text)
    if noise_reasons:
        return RelevanceResult(
            is_relevant=False, relevance_score=0.0,
            matched_category="", noise_detected=True,
            noise_reasons=noise_reasons,
        )

    # Step 2: Domain signal scoring
    domain_scores = _score_domains(text)
    best_category = max(domain_scores, key=domain_scores.get) if domain_scores else ""
    best_score = domain_scores.get(best_category, 0.0)

    # Step 3: Source trust bonus
    source_bonus = _get_source_bonus(source_name)

    # Step 4: Freshness penalty
    freshness_penalty = _calc_freshness_penalty(published_at)

    # Step 5: Quality flags
    quality_flags = _check_quality(topic, summary, keywords)

    # Combine into final relevance score (0-100 scale)
    raw_score = min(best_score + source_bonus - freshness_penalty, 100.0)
    final_score = max(raw_score, 0.0)

    return RelevanceResult(
        is_relevant=final_score >= score_threshold,
        relevance_score=round(final_score, 1),
        matched_category=best_category,
        noise_detected=False,
        domain_scores={k: round(v, 1) for k, v in domain_scores.items()},
        source_bonus=source_bonus,
        freshness_penalty=round(freshness_penalty, 1),
        quality_flags=quality_flags,
    )


def pre_filter(
    topic: str,
    summary: str = "",
    keywords: Optional[Iterable[str]] = None,
) -> bool:
    """Fast pre-AI filter. Returns True if signal should be sent to GPT.

    Designed to be cheap — blocks obvious noise, passes anything
    that might be relevant. False positives are OK (GPT will handle).
    False negatives are NOT OK (we'd miss trends).
    """
    text = _join_text(topic, summary, keywords)
    if not text:
        return False

    # Block obvious noise
    if _detect_noise(text):
        return False

    # Check if ANY domain signals exist
    for patterns in _DOMAIN_PATTERNS.values():
        for pat, weight in patterns:
            if weight >= 2 and pat.search(text):
                return True

    # If no strong domain signals, still pass if text is non-trivial
    # (let GPT decide — we'd rather waste tokens than miss a trend)
    return len(text.split()) >= 8


def post_filter(trend: dict, min_score: float = 25.0) -> bool:
    """Post-AI quality gate. Validates trend before serving to users.

    Checks:
      1. Required fields exist and are non-empty
      2. Summary has minimum quality
      3. Deterministic relevance meets threshold
      4. No noise leaked through AI
    """
    topic = (trend or {}).get("topic", "") or ""
    summary = (trend or {}).get("summary", "") or ""
    keywords = (trend or {}).get("keywords") or []
    source_name = (trend or {}).get("source_name", "") or ""
    published_at = (trend or {}).get("published_at")

    # Quality checks
    if len(topic.strip()) < 5:
        return False
    if len(summary.strip()) < 20:
        return False
    if len([k for k in keywords if str(k).strip()]) < 1:
        return False

    result = compute_relevance(
        topic=topic,
        summary=summary,
        keywords=keywords,
        source_name=source_name,
        published_at=published_at,
        score_threshold=min_score,
    )

    return result.is_relevant


def adjust_score(ai_score: int, trend: dict) -> int:
    """Apply deterministic adjustments to AI-generated score.

    Used after GPT scoring to add/subtract based on signals
    that the AI might miss or overvalue.
    """
    topic = (trend or {}).get("topic", "") or ""
    summary = (trend or {}).get("summary", "") or ""
    source_name = (trend or {}).get("source_name", "") or ""
    keywords = (trend or {}).get("keywords") or []
    text = _join_text(topic, summary, keywords)

    adjustment = 0

    # NOTE: Source trust and VIP tier bonuses REMOVED to prevent triple-counting.
    # GPT already scores Source Trust (0-15), VIP scoring adds tiered boost.
    # Only unique signals remain here.

    # Multi-source confirmation bonus (unique signal — not covered elsewhere)
    signal_count = (trend or {}).get("signal_count", 1)
    if signal_count >= 3:
        adjustment += 5
    elif signal_count >= 2:
        adjustment += 3

    # Self-promo penalty: company blog promoting own product
    if _is_self_promo(text, source_name):
        adjustment -= 10

    # Engagement bonus (unique signal — real user interest)
    engagement = (trend or {}).get("engagement_total", 0)
    if engagement >= 1000:
        adjustment += 5
    elif engagement >= 500:
        adjustment += 3

    # Noise leak penalty (safety net)
    if _detect_noise(text):
        adjustment -= 30

    return max(0, min(100, ai_score + adjustment))


def normalize_category(raw: str) -> str:
    """Normalize a category string to one of the valid categories.

    Uses domain signal matching rather than simple substring.
    Falls back to detecting from content if raw category is ambiguous.
    """
    value = (raw or "").strip()

    # Direct match (case-insensitive)
    for cat in VALID_CATEGORIES:
        if value.lower() == cat.lower():
            return cat

    # Common variations
    lower = value.lower()
    if any(x in lower for x in ["artificial intelligence", "yapay zeka", "ml", "llm", "gpt"]):
        return "AI"
    if any(x in lower for x in ["developer", "dev", "software", "yazılım", "nocode", "security", "api", "sdk"]):
        return "Dev"
    if any(x in lower for x in ["design", "tasarım", "ux", "ui", "figma"]):
        return "Design"
    if any(x in lower for x in ["crypto", "kripto", "blockchain", "web3", "defi", "bitcoin"]):
        return "Crypto"
    if any(x in lower for x in ["startup", "funding", "yatırım", "vc", "saas", "girişim"]):
        return "Startup"
    if any(x in lower for x in ["marketing", "pazarlama", "content", "seo", "social media"]):
        return "Marketing"
    if any(x in lower for x in ["business", "iş", "finance", "finans", "ecommerce"]):
        return "Business"
    if any(x in lower for x in ["science", "bilim", "data", "research", "araştırma"]):
        return "Science"
    if any(x in lower for x in ["lifestyle", "yaşam", "health", "fitness", "food", "travel"]):
        return "Lifestyle"
    if any(x in lower for x in ["education", "eğitim", "öğrenme", "course"]):
        return "Education"
    if any(x in lower for x in ["entertainment", "eğlence", "gaming", "music", "cinema", "film"]):
        return "Entertainment"
    if any(x in lower for x in ["news", "haber", "gündem", "güncel", "gundem", "politics", "politika"]):
        return "News"
    # Legacy mappings
    if any(x in lower for x in ["technology", "teknoloji", "tech"]):
        return "Dev"

    return "News"  # Safe default for unclassified


# ---------------------------------------------------------------------------
# Backward-compatible API (used by routes/trends.py)
# ---------------------------------------------------------------------------

def is_kubra_relevant_text(
    topic: str,
    summary: str = "",
    keywords: Optional[Iterable[str]] = None,
) -> bool:
    """Backward-compatible wrapper. Use post_filter() for new code."""
    return post_filter({
        "topic": topic,
        "summary": summary,
        "keywords": list(keywords) if keywords else [],
    })


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _join_text(
    topic: str = "",
    summary: str = "",
    keywords: Optional[Iterable[str]] = None,
) -> str:
    kw = " ".join(str(k) for k in (keywords or []) if k)
    return " ".join(part for part in [topic or "", summary or "", kw] if part).strip()


def _detect_noise(text: str) -> list[str]:
    """Returns list of noise categories detected, empty if clean."""
    reasons = []
    text_lower = text.lower()
    for pat in _NOISE_PATTERNS:
        if pat.search(text_lower):
            # Find which category this noise term belongs to
            for category, terms in NOISE_TERMS.items():
                for term in terms:
                    if term.lower() in pat.pattern.lower():
                        if category not in reasons:
                            reasons.append(category)
                        break
            if not reasons:
                reasons.append("unknown_noise")
            break  # One noise match is enough to flag
    return reasons


def _score_domains(text: str) -> dict[str, float]:
    """Score text against each domain. Returns {category: score}."""
    scores: dict[str, float] = {}
    text_lower = text.lower()

    for category, patterns in _DOMAIN_PATTERNS.items():
        total = 0.0
        matches = 0
        for pat, weight in patterns:
            if pat.search(text_lower):
                total += weight * 12  # Scale: weight 3 = 36pts per match
                matches += 1
        # Diversity bonus: more distinct matches = higher confidence
        if matches >= 3:
            total += 10
        if matches >= 5:
            total += 10
        scores[category] = min(total, 100.0)

    return scores


def _get_source_bonus(source_name: str) -> int:
    """Return trust bonus for known sources."""
    if not source_name:
        return 0
    name_lower = source_name.lower()
    for pat, bonus in _TRUSTED_PATTERNS:
        if pat.search(name_lower):
            return bonus
    return 0


def _calc_freshness_penalty(published_at: Optional[str]) -> float:
    """Calculate freshness decay penalty.

    0-24h: 0 penalty
    24-48h: -5
    48-72h: -15
    72h+: -25
    """
    if not published_at:
        return 0.0
    try:
        pub_dt = datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
        age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
        if age_hours <= 24:
            return 0.0
        if age_hours <= 48:
            return 5.0
        if age_hours <= 72:
            return 15.0
        return 25.0
    except (ValueError, TypeError):
        return 0.0


def _is_self_promo(text: str, source_name: str) -> bool:
    """Detect self-promotional content (company blog about own product)."""
    if not source_name:
        return False
    src = source_name.lower()
    txt = text.lower()

    promo_pairs = [
        ("openai", "openai"),
        ("anthropic", "anthropic"),
        ("google", "google"),
        ("meta", "meta"),
        ("microsoft", "microsoft"),
        ("nvidia", "nvidia"),
        ("amazon", "amazon"),
        ("apple", "apple"),
    ]
    for blog_marker, product_marker in promo_pairs:
        if blog_marker in src and product_marker in txt:
            # Check if the text is ONLY about their own product
            # (mentioning competitors = comparison article = OK)
            competitors = [p for b, p in promo_pairs if b != blog_marker]
            mentions_others = any(c in txt for c in competitors)
            if not mentions_others:
                return True
    return False


def _check_quality(
    topic: str,
    summary: str,
    keywords: Optional[Iterable[str]] = None,
) -> list[str]:
    """Return quality flags for diagnostics."""
    flags = []
    if len((topic or "").strip()) < 10:
        flags.append("short_topic")
    if len((summary or "").strip()) < 50:
        flags.append("short_summary")
    kw_list = [k for k in (keywords or []) if str(k).strip()]
    if len(kw_list) < 2:
        flags.append("few_keywords")
    if len(kw_list) > 10:
        flags.append("too_many_keywords")
    return flags

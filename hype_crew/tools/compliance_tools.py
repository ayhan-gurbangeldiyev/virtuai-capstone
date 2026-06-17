"""Compliance tools — dedup, forbidden topics, hard rule enforcement.

These are CrewAI @tool wrappers callable by the Compliance agent.
Pure rule-based — no LLM calls (Compliance agent does its own LLM voice scoring).
"""
import re
from datetime import datetime, timezone, timedelta

try:
    from crewai.tools import tool
except ImportError:
    def tool(*args, **kwargs):  # noqa: ARG001
        def _decorate(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate

from .supabase_client import make_supabase


# ─── Helpers ────────────────────────────────────────────────────────────────


def _tokens(text: str) -> set[str]:
    """Lowercase word tokenization for Jaccard similarity."""
    return set(re.findall(r"\b\w{3,}\b", text.lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


# ─── @tool: Dedup check ─────────────────────────────────────────────────────


@tool("dedup_check")
def dedup_check(content: str, account_id: str, days: int = 7) -> dict:
    """Check if `content` is too similar to any recent approved post.

    Primary: pgvector cosine similarity (threshold 0.85).
    Fallback: Jaccard token similarity (threshold 0.80) if embedding fails.

    Returns:
        {
          "passed": bool,
          "max_similarity": float,
          "similar_to_post_id": str | None,
          "method": "cosine" | "jaccard"
        }
    """
    # Try cosine via pgvector first (better semantic quality)
    from .memory_tools import cosine_dedup_check
    cosine_result = cosine_dedup_check(
        content=content,
        account_id=account_id,
        threshold=0.85,
        types=["approved_drafts", "voice_examples"],
    )
    if cosine_result["max_similarity"] > 0.0:
        return {
            "passed": cosine_result["passed"],
            "max_similarity": cosine_result["max_similarity"],
            "similar_to_post_id": cosine_result.get("similar_id"),
            "method": "cosine",
        }

    # Fallback: Jaccard (also runs when no embedded memory yet)
    sb = make_supabase()
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        sb.table("hype_memory")
        .select("id, content")
        .eq("account_id", account_id)
        .in_("memory_type", ["approved_drafts", "voice_examples"])
        .gte("created_at", since)
        .execute()
    )
    rows = result.data or []
    if not rows:
        return {"passed": True, "max_similarity": 0.0, "similar_to_post_id": None, "method": "jaccard"}

    sims = [(_jaccard(content, r["content"]), r["id"]) for r in rows]
    max_sim, max_id = max(sims, key=lambda x: x[0])
    return {
        "passed": max_sim < 0.80,
        "max_similarity": round(max_sim, 3),
        "similar_to_post_id": max_id if max_sim >= 0.80 else None,
        "method": "jaccard",
    }


# ─── @tool: Forbidden topics check ─────────────────────────────────────────


@tool("forbidden_topics_check")
def forbidden_topics_check(content: str, forbidden_topics: list[str]) -> dict:
    """Detect forbidden topic keywords in content.

    Phase 1: keyword + variations. LLM intent check can be added later.

    Returns:
        {
          "passed": bool,
          "detected": list[str]  # which forbidden topics matched
        }
    """
    if not forbidden_topics:
        return {"passed": True, "detected": []}

    content_low = content.lower()
    detected = []

    # Topic synonyms (extend over time based on observed misses)
    topic_aliases = {
        "politics": [
            # Direct
            "politik", "politics", "political",
            # Elections / parties
            # 2026-06-12 (Berkay): bare "parti" "üçüncü parti / third-party"yi
            # politics sanıp temiz AI haberini eledi (WhatsApp 3.parti AI). Spesifik
            # parti adları kalır; "siyasi parti" jenerik "parti"nin yerine geçer.
            "election", "seçim", "siyasi parti", "ak parti", "chp", "mhp", "hdp", "iyi parti",
            "republican", "democrat", "başkanlık", "presidential", "parlamento",
            # Country rivalry / geopolitics (Bug 2: caught "ABD ve Çin")
            "abd vs çin", "us vs china", "us-china", "china vs us",
            "race between countries", "geopolitical", "geopolitics",
            "trade war", "ticaret savaşı", "ekonomik savaş",
            "tariff", "gümrük", "sanction", "yaptırım",
            "war", "savaş", "diplomatic", "diplomatik",
            # Government / policy
            # "düzenleme" tek başına "arayüz düzenlemesi" gibi teknik ifadeleri
            # de yakalıyordu → "yasal düzenleme" (spesifik).
            "government", "hükümet", "regulation by", "yasal düzenleme", "yasak",
            "ban by country", "biden", "trump", "erdoğan", "putin",
        ],
        "religion": [
            "din", "religion", "religious", "dini",
            "islam", "müslüman", "muslim", "christian", "christianity",
            "hristiyan", "musevi", "jewish", "judaism",
            "sect", "mezhep", "tarikat",
        ],
        "medical_advice": [
            "health advice", "medical advice", "medical", "tıbbi",
            "diagnosis", "tedavi", "treatment", "cure", "ilaç", "medication",
            "kanser", "cancer", "covid cure", "vaccine recommend",
            "you should take", "şunu için",
        ],
        "financial_advice": [
            "financial advice", "invest in", "buy stock", "buy this stock",
            "borsa al", "borsadan al", "kripto al", "altın al",
            "satın al", "should invest", "guaranteed return", "10x gain",
            "stock tip", "yatırım tavsiyesi",
        ],
        "violence": ["violence", "şiddet", "kill", "öldür", "saldırı", "attack"],
        "adult": ["adult", "porn", "nsfw", "yetişkin", "xxx"],
    }

    for ft in forbidden_topics:
        ft_low = ft.lower()
        aliases = topic_aliases.get(ft_low, [ft_low])
        for alias in aliases:
            if re.search(r"\b" + re.escape(alias) + r"\b", content_low):
                detected.append(ft)
                break

    return {"passed": len(detected) == 0, "detected": list(set(detected))}


# ─── @tool: Hard rules check (formatting + content rules) ──────────────────


CORPORATE_WORDS = [
    "leverage", "leveraging", "exciting", "game-changing", "synergy",
    "unlock potential", "in the era of", "in today's fast-paced",
    "deep dive", "moving forward", "circle back", "low-hanging fruit",
    "robust", "scalable solution", "best-in-class", "thought leadership",
    "value-add", "paradigm shift", "next-generation",
]


@tool("hard_rules_check")
def hard_rules_check(content: str) -> dict:
    """Verify hard formatting/content rules.

    Returns:
        {
          "passed": bool,
          "violations": list[str]  # which rules were broken
        }
    """
    violations = []

    # 2026-06-08 (gate refine) — em-dash rule REMOVED.
    # The old rule rejected ANY draft containing "—" or "–". That came
    # from an older style guide. Cansu's new Semih-DNA voice uses em-
    # dashes naturally for short conclusion-first beats:
    #   "ChatGPT artık taslağı yazıp bırakmıyor — direkt gönderiyor."
    # Every voice-cure draft that used an em-dash was getting auto-
    # rejected here (a798b56d ChatGPT email being the captured case).
    # Em-dash is punctuation, not content; removing the rule does NOT
    # weaken fact-checking. Faithfulness gate still catches fabrications.

    # 1. No corporate jargon
    content_low = content.lower()
    corporate_hits = [w for w in CORPORATE_WORDS if re.search(r"\b" + re.escape(w) + r"\b", content_low)]
    if corporate_hits:
        violations.append(f"corporate_words:{','.join(corporate_hits[:5])}")

    # 3. Hard ceiling = 4000 chars (schema limit; aligns with X Premium long-form).
    # Strategist picks uzunluk (micro/punch/spark/storm) based on the trend —
    # we don't impose a single tweet-length floor here. Postiz handles the
    # per-account post-time limits.
    if len(content) > 4000:
        violations.append(f"too_long:{len(content)}>4000")

    # 4. Line-break + per-line word checks removed. Many creators (e.g. Semih
    # Kışlar) write single-line tweets with no paragraph breaks. Style profile
    # already enforces line structure where the creator uses it.

    return {"passed": len(violations) == 0, "violations": violations}

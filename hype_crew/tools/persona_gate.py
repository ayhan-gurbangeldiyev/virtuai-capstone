"""Persona Gate — deterministic relevance filter BEFORE TrendScout.

Capstone (Berkay 3 Haz 2026): the 12-point TrendScout rubric measures
*importance* (is this news worth producing content about?). It does NOT
measure persona fit. Without a separate gate, persona-irrelevant trends
(Togg, iPhone battery, Samsung One UI, gaming, crypto) reach Gemini
Flash and downstream Writer/HeyGen, wasting LLM + video render cost
AND damaging Cansu's brand integrity.

Persona Gate runs in `query_trends` BEFORE the trend list is handed to
the TrendScout LLM. Hard-blocked trends never reach Gemini.

# Architecture

5 sequential layers, first match wins:

  L1  HARD BLOCK    blocked_keyword in topic → REJECT, log, skip
  L2  POSITIVE AI   positive_ai_signal in topic → SEND to TrendScout
  L3  TIER 1 BRAND  tier_1_brand in topic → SEND to TrendScout
                    (TrendScout still applies 12-point rubric — Tier 1
                     match is NOT auto-approval)
  L3b CONDITIONAL   conditional_brand in topic:
                       required_ai_kw also in topic → SEND
                       no required_ai_kw → REJECT
                    (NVIDIA gaming laptop fails; NVIDIA Blackwell passes)
  L4  AMBIGUOUS     none of the above → REJECT (precision > recall)

Capstone product decision: precision > recall. Missing one borderline
AI story is acceptable; producing a Togg video is not.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional


# ─── Turkish-safe normalization ──────────────────────────────────────────────
# Python's str.lower() on "İ" gives "i̇" (dotted i + combining dot above),
# which won't match ASCII "i" via substring. Map Turkish-specific chars to
# ASCII equivalents BEFORE lower-casing for consistent substring matching.
# Keyword lists are stored ASCII-lowercase by convention.
_TURKISH_FOLD = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
})


def normalize_turkish(text: str) -> str:
    """ASCII-fold Turkish + lowercase. Match-friendly form."""
    if not text:
        return ""
    return text.translate(_TURKISH_FOLD).lower()


# ─── Result type ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PersonaGateDecision:
    decision: str                       # 'reject' | 'send_to_trendscout'
    persona_gate: str                   # 'blocked' | 'positive_match' |
                                        # 'tier_1_brand_match' |
                                        # 'conditional_brand_match' |
                                        # 'conditional_brand_no_ai_signal' |
                                        # 'ambiguous'
    matched_keyword: Optional[str] = None

    @property
    def passed(self) -> bool:
        return self.decision == "send_to_trendscout"


# ─── Main evaluator ──────────────────────────────────────────────────────────


def evaluate_persona_gate(
    *,
    topic: str,
    raw_content: str = "",
    category: str = "",
    config: dict,
) -> PersonaGateDecision:
    """Apply Persona Gate to a single trend candidate.

    Args:
        topic: trend.topic (required, ~60-100 chars usually).
        raw_content: trend.raw_content (optional, first ~500 chars used).
        category: trend.category (optional, joined for match coverage).
        config: hype_account_config.persona_gate_config jsonb dict with:
            - blocked_keywords: list[str]
            - positive_ai_signals: list[str]
            - tier_1_brands: list[str]
            - conditional_brands: dict[str, list[str]] (brand → required_kws)

    Returns:
        PersonaGateDecision with decision + persona_gate + matched_keyword.

    Layer order (first match wins):
      1. Hard block (any blocked_keyword → REJECT)
      2. Positive AI signal (any positive_ai_signal → PASS)
      3. Tier 1 brand (any tier_1_brand → PASS, TrendScout still scores)
      4. Conditional brand (brand + required AI keyword → PASS, brand
         alone → REJECT 'conditional_brand_no_ai_signal')
      5. Ambiguous → REJECT (precision > recall)
    """
    # Combine all queryable text into one normalized blob.
    # raw_content truncated to 500 chars (relevancy in first paragraph).
    text = normalize_turkish(
        f"{topic} {raw_content[:500]} {category}"
    )

    # ─── L1: HARD BLOCK ─────────────────────────────────────────────────
    blocked = config.get("blocked_keywords") or []
    for kw in blocked:
        kw_norm = normalize_turkish(str(kw))
        if not kw_norm:
            continue
        # 2026-06-10 — substring değil KELİME SINIRI eşleşmesi: 'audi'
        # blok kelimesi 'audio'nun içinde eşleşip Gemini Live Translate
        # trendini kesiyordu (L1 hard-block FP). \b apostrof/ek
        # durumlarını da doğru yönetir ("audi'nin" eşleşir, "audio"
        # eşleşmez). Çok-kelimeli keywordlerde de çalışır.
        if re.search(r"\b" + re.escape(kw_norm) + r"\b", text):
            return PersonaGateDecision(
                decision="reject",
                persona_gate="blocked",
                matched_keyword=kw_norm,
            )

    # ─── L2: POSITIVE AI SIGNAL (stronger than brand match) ─────────────
    positive = config.get("positive_ai_signals") or []
    for sig in positive:
        sig_norm = normalize_turkish(str(sig))
        if not sig_norm:
            continue
        if sig_norm in text:
            return PersonaGateDecision(
                decision="send_to_trendscout",
                persona_gate="positive_match",
                matched_keyword=sig_norm,
            )

    # ─── L3: TIER 1 BRAND (unconditional gate-pass, TrendScout still scores) ─
    tier_1 = config.get("tier_1_brands") or []
    for brand in tier_1:
        brand_norm = normalize_turkish(str(brand))
        if not brand_norm:
            continue
        if brand_norm in text:
            return PersonaGateDecision(
                decision="send_to_trendscout",
                persona_gate="tier_1_brand_match",
                matched_keyword=brand_norm,
            )

    # ─── L3b: CONDITIONAL BRAND (NVIDIA, Apple, Tesla, Samsung, ...) ─────
    # Brand-only match insufficient — must co-occur with an AI keyword
    # from the brand's specific required list. If brand found but no
    # AI keyword → ACTIVE REJECT (not ambiguous). This catches:
    #   - "NVIDIA gaming laptop discount" → brand match, no AI kw → reject
    #   - "NVIDIA Blackwell inference chip" → brand + 'inference' → pass
    conditional = config.get("conditional_brands") or {}
    for brand, required_kws in conditional.items():
        brand_norm = normalize_turkish(str(brand))
        if not brand_norm or brand_norm not in text:
            continue
        # Brand matched. Now check at least one required AI keyword.
        required_norm = [normalize_turkish(str(k)) for k in (required_kws or [])]
        for req_kw in required_norm:
            if req_kw and req_kw in text:
                return PersonaGateDecision(
                    decision="send_to_trendscout",
                    persona_gate="conditional_brand_match",
                    matched_keyword=f"{brand_norm}+{req_kw}",
                )
        # Brand found but no required AI keyword.
        return PersonaGateDecision(
            decision="reject",
            persona_gate="conditional_brand_no_ai_signal",
            matched_keyword=brand_norm,
        )

    # ─── L4: AMBIGUOUS ──────────────────────────────────────────────────
    # Recall-only semantic rescue (2026-06-07 A2). At this point all
    # keyword layers have missed. Before defaulting to REJECT, ask the
    # multilingual sentence-transformer: is this text close enough to
    # an AI-concept anchor that we'd be losing a real story by
    # rejecting? If max-cosine ≥ threshold (default 0.55), rescue it
    # and tag the row `semantic_rescue` so the operator can audit
    # rescues separately. Never overrides L1/L3b — those are explicit
    # block decisions, not "nothing matched".
    try:
        from .semantic_rescue import evaluate_semantic_rescue
        sr = evaluate_semantic_rescue(topic=topic, raw_content=raw_content)
        if sr.rescued:
            return PersonaGateDecision(
                decision="send_to_trendscout",
                persona_gate="semantic_rescue",
                matched_keyword=f"cos={sr.score:.3f}≥{sr.threshold:.2f}",
            )
    except Exception:
        # Fail-safe: never let a rescue layer fault take down the gate.
        pass

    return PersonaGateDecision(
        decision="reject",
        persona_gate="ambiguous",
        matched_keyword="no_ai_relevance_signal",
    )

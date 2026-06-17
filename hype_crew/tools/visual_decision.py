"""Phase 39 / 41.B / 41.F / 42.A — Visual Decision Agent.

Routes each draft to one of three CompositionTypes:
    brand_news_visual  — logos/UI/product shot, NO Cansu (default)
    cansu_scene        — Cansu in context (working, café, candid)
    cansu_selfie       — Cansu direct camera address (rare, promo only)

Phase 42.A (Berkay 2 Jun 2026) — full rewrite after a 3-agent /debate
(`projects/debates/2026-06-02-visual-routing/`):

1. **Constraint kernel** runs first (deterministic, no LLM). It catches
   ~70% of brand-news traffic before the model is invoked:
     - content_type in NEWS_SET → brand_news_visual
     - voice_mode == "third_person_neutral" → brand_news_visual
     - brand_extractor finds named entities → brand_news_visual

2. **voice_mode is REMOVED from the LLM prompt** (Critic's non-negotiable).
   Models are notoriously bad at "ignore X" instructions — 15-35% failure
   rate. So the architectural fix is to never let the model see voice_mode
   when picking a composition. voice_mode only influences the kernel
   (3rd-person → brand) and is silent everywhere else.

3. **LLM only sees ambiguous cases** that the kernel could not resolve.
   It receives `trend_topic`, `brief`, `content_type`, and (if extracted)
   `news_entities`. It returns one of the 3 enum values + a Turkish reason.

Backward compat: returns BOTH `composition_type` and a derived
`needs_cansu` bool so older callers (Phase 41.B path in
visual_director_tools.py) keep working.
"""
from __future__ import annotations

import json
import re
from typing import Optional

import httpx
from loguru import logger

from config import settings
from schemas.visual import (
    CompositionType,
    NEWS_SET,
    composition_type_for_content_type,
)
from .brand_extractor import extract_brand_from_topic


# ─── System prompt — 3-type enum, voice_mode-free, with worked examples ────
_VALID_COMPOSITION_TYPES: frozenset[str] = frozenset(
    {"brand_news_visual", "cansu_scene", "cansu_selfie"}
)

_SYS_PROMPT = """You decide what kind of image accompanies a social-media draft
about AI / tech for a Turkish AI persona named Cansu.

Pick exactly ONE composition_type:

  brand_news_visual
    Logos, product UI mockups, screenshots, abstract tech imagery. NO Cansu.
    This is the DEFAULT for any draft that is fundamentally about a brand,
    product, model, partnership, research paper, or industry event.

  cansu_scene
    Cansu present in a contextual scene — working at her desk, sitting in
    a café, reading on her phone, watching a screen. NOT a frontal selfie.
    Use this for genuinely lifestyle / behind-the-scenes / personal
    narrative drafts ("denedim", "bugün öğrendim", "şu hafta").

  cansu_selfie
    Cansu directly addressing the camera — frontal portrait, eye contact.
    RARE — reserved for explicit promo / call-to-action / first-person
    announcements ("yeni kursumu başlattım", "abone olun"). Almost never
    fires; if you are unsure between cansu_scene and cansu_selfie,
    choose cansu_scene.

Critical rule — voice and image are independent:
The caption's voice (1st person, 3rd person) is NOT a signal for what
the IMAGE should show. A first-person caption ABOUT a Microsoft + OpenAI
partnership still uses brand_news_visual: the image shows the brand
logos, not Cansu. Never let "Cansu wrote this" lead you to "Cansu should
appear." The image's subject is determined by the content's subject, not
its narrator.

Worked examples (do not copy verbatim):

  trend_topic: "Anthropic Claude 4 Opus launches with 200k context"
  content_type: model_launch
  → brand_news_visual
    reason: "Model duyurusu — marka ve UI baskın olmalı."

  trend_topic: "Microsoft and AWS announce Bedrock + OpenAI partnership"
  content_type: partnership
  → brand_news_visual
    reason: "Marka ortaklığı haberi — iki şirket logosu odakta."

  trend_topic: "AI ajanlarıyla bir hafta — neler öğrendim"
  content_type: blog_post
  → cansu_scene
    reason: "Birinci şahıs kişisel deneyim — Cansu çalışırken sahnede."

  trend_topic: "Yeni online kursumu yayınladım, kayıtlar açık"
  content_type: other
  → cansu_selfie
    reason: "Kişisel duyuru + CTA — doğrudan kameraya bakış uygun."

Reply with JSON only:
{"composition_type": "<one of brand_news_visual|cansu_scene|cansu_selfie>",
 "reason": "<1 short Turkish sentence>"}"""


# Coarse content_type → category mapping. Used as an extra hint to the LLM
# in ambiguous cases.
_CONTENT_TYPE_CATEGORY = {
    "model_launch":     "news_announcement",
    "product_launch":   "news_announcement",
    "pricing":          "news_announcement",
    "partnership":      "news_announcement",
    "api_update":       "news_announcement",
    "research":         "news_announcement",
    "security":         "news_announcement",
    "m_and_a":          "news_announcement",
    "feature_major":    "product_commentary",
    "feature_minor":    "product_commentary",
    "access_expansion": "product_commentary",
    "blog_post":        "personal_narrative",
    "other":            "personal_narrative",
}


def _extract_json(text: str) -> Optional[dict]:
    """Pull a {...} block out of an LLM response. Tolerates stray prose."""
    if not text:
        return None
    text = text.strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except (json.JSONDecodeError, ValueError):
        pass
    match = re.search(r"\{[^{}]*\}", text)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, ValueError):
            pass
    return None


def _derive_needs_cansu(composition_type: CompositionType) -> bool:
    """Backward-compat helper — preserves the Phase 39 boolean return value
    so callers that haven't migrated to composition_type still work."""
    return composition_type in {"cansu_scene", "cansu_selfie"}


def _apply_constraint_kernel(
    *,
    content_type: Optional[str],
    voice_mode: Optional[str],
    trend_topic: Optional[str],
) -> Optional[tuple[CompositionType, str]]:
    """Phase 42.A — Deterministic hard rules that run BEFORE the LLM call.

    Returns (composition_type, reason) when a rule fires, None when the
    decision needs LLM arbitration.

    The kernel encodes the consensus from the /debate decision doc:
      - News content_types are ALWAYS brand-news (Microsoft/OpenAI fix).
      - 3rd-person journalist voice is ALWAYS brand-news.
      - Brand entities in the topic strongly imply brand-news.
    """
    ct_norm = (content_type or "").strip().lower() or None

    # Rule 1 — news content_type set
    if ct_norm and ct_norm in NEWS_SET:
        return (
            "brand_news_visual",
            f"content_type={ct_norm} (NEWS_SET hard rule)",
        )

    # Rule 2 — third-person journalist tone always brand-news
    if voice_mode == "third_person_neutral":
        return (
            "brand_news_visual",
            "voice_mode=third_person_neutral (gazeteci tonu)",
        )

    # Rule 3 — brand entities detected in trend_topic
    if trend_topic:
        try:
            brand = extract_brand_from_topic(trend_topic)
            if brand:
                return (
                    "brand_news_visual",
                    f"brand_extractor matched '{brand}' in trend_topic",
                )
        except Exception as e:  # extractor failure should never block routing
            logger.warning(f"[visual_decision] brand_extractor raised {e!r}; skipping rule 3")

    return None


async def decide_composition_type(
    *,
    trend_topic: str,
    brief: str,
    content_type: str = "tweet",
    voice_mode: Optional[str] = None,
) -> dict[str, object]:
    """Phase 42.A — Decide the composition_type for a draft.

    Args:
        trend_topic: Source trend topic / news headline.
        brief: Strategist's draft brief (intent, angle, tone).
        content_type: Strategist's content_type taxonomy value
            ("partnership", "model_launch", "blog_post", ...).
        voice_mode: Strategist's voice_mode. Used ONLY by the deterministic
            constraint kernel (3rd-person → brand). Intentionally NOT
            passed to the LLM prompt (Critic's non-negotiable: "ignore X"
            instructions fail 15-35%).

    Returns:
        {
          "composition_type": "brand_news_visual"|"cansu_scene"|"cansu_selfie",
          "needs_cansu": <derived bool, for backward-compat>,
          "reason": "<1 short Turkish sentence>",
          "via": "kernel" | "llm" | "fallback",
        }
        On API error: defaults to brand_news_visual.

    Cost: $0 for ~70% of drafts (kernel hits before LLM). ~$0.0005 for the
    rest (gemini-flash, ~80 output tokens).
    """
    # ─── Step 1 — Constraint kernel (deterministic, no LLM) ─────────────
    kernel_hit = _apply_constraint_kernel(
        content_type=content_type,
        voice_mode=voice_mode,
        trend_topic=trend_topic,
    )
    if kernel_hit is not None:
        ct, reason = kernel_hit
        logger.info(f"[visual_decision] kernel: composition_type={ct} reason='{reason}'")
        return {
            "composition_type": ct,
            "needs_cansu": _derive_needs_cansu(ct),
            "reason": reason,
            "via": "kernel",
        }

    # ─── Step 2 — LLM arbitration (ambiguous zone only) ─────────────────
    api_key = getattr(settings, "openrouter_api_key", None)
    if not api_key:
        logger.warning("[visual_decision] OPENROUTER_API_KEY missing — defaulting to brand_news_visual")
        return {
            "composition_type": "brand_news_visual",
            "needs_cansu": False,
            "reason": "decision_unavailable: api_key missing",
            "via": "fallback",
        }

    model = getattr(settings, "model_fast", "openrouter/google/gemini-3-flash-preview")
    actual_model = model.removeprefix("openrouter/")

    # NOTE: voice_mode is intentionally NOT included in the user prompt.
    # The LLM must not be able to use it as a signal — the kernel handles
    # the 3rd-person hard lock and nothing else needs voice info.
    category_hint = _CONTENT_TYPE_CATEGORY.get((content_type or "").lower(), "unclassified")
    user_prompt = (
        f"trend_topic: {trend_topic[:300]}\n"
        f"brief: {brief[:600]}\n"
        f"content_type: {content_type}\n"
        f"content_type_category: {category_hint}\n\n"
        f"Decide. JSON only."
    )

    # LiteLLM Router dalı (flag-gated, fail-open). Bu site zaten bir JSON gate
    # (response_format json_object) → router_chat_json birebir uygun. Parsed dict'i
    # doğrudan alır, aşağıdaki MEVCUT doğrulama mantığına (legacy needs_cansu shape,
    # enum kontrol, via) aynen besler. Kapalı/hatalı iken httpx yolu byte-identical.
    parsed: Optional[dict] = None
    router_used = False
    try:
        from .llm_router import router_enabled, router_chat_json
        if router_enabled():
            router_used = True
            try:
                parsed, _meta = await router_chat_json(
                    _SYS_PROMPT, user_prompt,
                    temperature=0.15, max_tokens=120, model_name="gate-fast",
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[visual_decision] router atlandı, httpx'e düşülüyor: {e}")
                parsed = None
                router_used = False
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[visual_decision] router import hatası, httpx'e düşülüyor: {e}")
        router_used = False

    if not router_used:
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
                            {"role": "system", "content": _SYS_PROMPT},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.15,
                        "max_tokens": 120,
                        "response_format": {"type": "json_object"},
                    },
                )
                r.raise_for_status()
                data = r.json()
        except Exception as e:
            logger.warning(
                f"[visual_decision] OpenRouter call failed ({type(e).__name__}: {str(e)[:100]}) "
                f"— defaulting to brand_news_visual"
            )
            return {
                "composition_type": "brand_news_visual",
                "needs_cansu": False,
                "reason": f"decision_unavailable: {type(e).__name__}",
                "via": "fallback",
            }

        text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        parsed = _extract_json(text)
    # Router yolu dict olmayan JSON (örn. array) döndürürse parity guard —
    # httpx yolu _extract_json ile zaten dict garantiler; router yolunu da hizala.
    if not isinstance(parsed, dict):
        parsed = None
    if not parsed:
        logger.warning(
            f"[visual_decision] LLM returned non-JSON: {str(parsed)[:200]!r} — defaulting to brand_news_visual"
        )
        return {
            "composition_type": "brand_news_visual",
            "needs_cansu": False,
            "reason": "decision_unavailable: non-json response",
            "via": "fallback",
        }

    raw_ct = str(parsed.get("composition_type", "")).strip()
    # Phase 42.A — also accept the legacy `needs_cansu` bool shape so a
    # stray legacy-prompt response isn't a hard fallback.
    if raw_ct not in _VALID_COMPOSITION_TYPES:
        legacy_needs = parsed.get("needs_cansu")
        if isinstance(legacy_needs, bool):
            raw_ct = "cansu_scene" if legacy_needs else "brand_news_visual"
        else:
            logger.warning(
                f"[visual_decision] LLM returned unknown composition_type={raw_ct!r}; "
                f"defaulting to brand_news_visual"
            )
            raw_ct = "brand_news_visual"

    composition_type: CompositionType = raw_ct  # type: ignore[assignment]
    reason = str(parsed.get("reason", ""))[:200] or "(no reason)"
    logger.info(f"[visual_decision] llm: composition_type={composition_type} reason='{reason[:80]}'")
    return {
        "composition_type": composition_type,
        "needs_cansu": _derive_needs_cansu(composition_type),
        "reason": reason,
        "via": "llm",
    }


# ─── Backward compat alias ──────────────────────────────────────────────
# Callers that haven't migrated yet (Phase 41.B path in
# visual_director_tools.py) still call `decide_needs_cansu`. Keep the
# old name and shape so the kernel + LLM still run — they just receive
# the new dict (which has BOTH `composition_type` and the derived
# `needs_cansu` boolean).
async def decide_needs_cansu(
    *,
    trend_topic: str,
    brief: str,
    content_type: str = "tweet",
    voice_mode: Optional[str] = None,
) -> dict[str, object]:
    """Backward-compat wrapper for Phase 41.B callers — delegates to
    decide_composition_type() and returns the same dict. Phase 43 may
    remove this alias once all call sites use composition_type."""
    # Silence the unused-arg lint: composition_type_for_content_type is the
    # documented public mapping for callers that want to skip the LLM.
    _ = composition_type_for_content_type
    return await decide_composition_type(
        trend_topic=trend_topic,
        brief=brief,
        content_type=content_type,
        voice_mode=voice_mode,
    )

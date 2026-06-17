"""Pydantic schemas for Visual Director agent output and intermediate types."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

# Phase 39 (Berkay 31 May 2026) — Visual mode simplified to a 2-way choice.
# Phase 25.D'deki face/conceptual/hybrid 3-mode'u kaldırıldı. Berkay'ın
# felsefesi: "ya Cansu ya marka, ortası yok". Karar artık LLM-based
# (`tools/visual_decision.py:decide_needs_cansu`) — content_type→mode fixed
# mapping yerine semantik karar.
#   - face / conceptual eski isimler `cansu` / `brand` semantik isimlere
#     coerce edilir (backward-compat field_validator).
#   - hybrid eski hype_runs rows için `brand`'e coerce edilir.
VisualMode = Literal["face", "conceptual"]

SceneType = Literal[
    # Face scenes (Tier 1/2/3 — mevcut)
    "home_office",
    "coffee_shop",
    "campus",
    "cinematic_portrait",
    "outdoor_istanbul",
    "tutorial_pose",
    # Conceptual scenes (Phase 25.D — Nano Banana JSON style, no people)
    "ai_interface",
    "neural_network",
    "tech_office_no_people",
    "abstract_digital",
    # Hybrid scene (Cansu overlay + product focus)
    "cansu_ui_overlay",
]

VisualMood = Literal["professional", "warm", "cinematic", "technical", "casual"]
OutfitTier = Literal["casual_70", "smart_casual_20", "home_cozy_10"]
ComplianceVerdict = Literal["PASS", "NEEDS_REVIEW", "FAIL", "SKIPPED"]


# ─────────────────────────────────────────────────────────────────────────────
# Phase 42.A (Berkay 2 Jun 2026) — composition_type routing
# ─────────────────────────────────────────────────────────────────────────────
# After the Microsoft+OpenAI brand-news incident a 3-agent /debate
# (Brainstormer + Thinker + Critic) replaced `needs_cansu` binary with a
# 3-way composition_type enum. The full reasoning lives at
# `projects/debates/2026-06-02-visual-routing/decisions.md`.
#
# Hard rule: news content_types (model_launch, partnership, pricing, etc.)
# DETERMINISTICALLY route to brand_news_visual — Cansu never appears on
# brand-news posts, no LLM judgement required. The Visual Decision Agent
# (`tools/visual_decision.py`) now consults this mapping FIRST and only
# invokes the LLM for cases the kernel cannot resolve.
CompositionType = Literal[
    "brand_news_visual",  # logos, UI mockups, product shots — NO Cansu
    "cansu_scene",        # Cansu present in context (working, café, candid)
    "cansu_selfie",       # Cansu direct camera address — rare, explicit promo
]

# Content_types that ALWAYS route to brand_news_visual. The constraint
# kernel in visual_decision.py short-circuits before the LLM for these.
# Phase 43 may shrink this set if data shows over-routing.
NEWS_SET: frozenset[str] = frozenset({
    "model_launch",
    "product_launch",
    "pricing",
    "partnership",
    "api_update",
    "research",
    "security",
    "m_and_a",
})

# Full content_type → composition_type lookup. `_default` is mandatory
# (Critic's "no silent free-text fallback" rule). Any unknown content_type
# falls to brand_news_visual rather than letting the LLM hallucinate.
COMPOSITION_TYPE_BY_CONTENT_TYPE: dict[str, CompositionType] = {
    # NEWS_SET — hard rule, mirrored here for direct lookups
    "model_launch":     "brand_news_visual",
    "product_launch":   "brand_news_visual",
    "pricing":          "brand_news_visual",
    "partnership":      "brand_news_visual",   # ← the Microsoft/OpenAI fix
    "api_update":       "brand_news_visual",
    "research":         "brand_news_visual",
    "security":         "brand_news_visual",
    "m_and_a":          "brand_news_visual",
    # Soft zone — LLM may override on first_person_witty content
    "feature_major":    "cansu_scene",
    "feature_minor":    "cansu_scene",
    "access_expansion": "cansu_scene",
    "blog_post":        "cansu_scene",
    "other":            "cansu_scene",
    # Default for ANY unknown content_type string
    "_default":         "brand_news_visual",
}


def composition_type_for_content_type(content_type: Optional[str]) -> CompositionType:
    """Phase 42.A — Deterministic content_type → CompositionType lookup.

    Used by:
      - `tools/visual_decision.py` constraint kernel (first hard rule)
      - `flow.py:generate_visual` scene library selector (mapped back via
        COMPOSITION_TO_VISUAL_MODE for backward-compat with face/conceptual
        scene pools)
    """
    if not content_type:
        return COMPOSITION_TYPE_BY_CONTENT_TYPE["_default"]
    return COMPOSITION_TYPE_BY_CONTENT_TYPE.get(
        content_type, COMPOSITION_TYPE_BY_CONTENT_TYPE["_default"]
    )


# Phase 42.A — transitional shim mapping composition_type → legacy
# VisualMode used by flow.py's existing SCENE_LIBRARY tiers. Scene pools
# are still keyed by "face" / "conceptual"; this dict bridges them.
# Phase 43 may collapse the two systems.
COMPOSITION_TO_VISUAL_MODE: dict[CompositionType, VisualMode] = {
    "brand_news_visual": "conceptual",
    "cansu_scene":       "face",
    "cansu_selfie":      "face",
}


# Phase 25.D mapping — DELETED in Phase 42.A. The body raises so any
# surviving legacy caller fails LOUDLY instead of silently producing
# wrong-mode visuals (Critic's runtime-assertion pattern).
# `VISUAL_MODE_BY_CONTENT_TYPE` dict is also gone — see Git for old value.
def visual_mode_for_content_type(content_type: Optional[str]) -> VisualMode:
    """DELETED Phase 42.A — call `composition_type_for_content_type()`
    instead, then map via `COMPOSITION_TO_VISUAL_MODE` if you need a
    legacy face/conceptual VisualMode for scene library lookup."""
    raise RuntimeError(
        "Phase 25.D visual_mode_for_content_type() was deleted in Phase 42.A. "
        f"Caller passed content_type={content_type!r}. Use "
        "composition_type_for_content_type() + COMPOSITION_TO_VISUAL_MODE "
        "from hype_crew.schemas.visual instead."
    )


class VisualDirectorOutput(BaseModel):
    """Structured output from the Visual Director CrewAI agent."""

    needs_visual: bool = Field(
        ..., description="False if this draft does not need an image (text-only platforms)"
    )
    skip_reason: Optional[str] = Field(
        default=None,
        description="If needs_visual=False, explain why (e.g. 'platform=x text-only')",
    )

    # Phase 25.D — Visual persona mode (face / conceptual / hybrid)
    # Phase 42.A — composition_type is the new authoritative routing axis;
    # visual_mode is kept as a backward-compat shim for the scene library
    # selector in flow.py.
    visual_mode: VisualMode = Field(
        default="face",
        description=
        "Persona presence: face=Cansu prominent, conceptual=no people. "
        "Backward-compat with scene library; derived from composition_type "
        "via COMPOSITION_TO_VISUAL_MODE.",
    )
    composition_type: Optional[CompositionType] = Field(
        default=None,
        description=
        "Phase 42.A — authoritative routing decision: brand_news_visual / "
        "cansu_scene / cansu_selfie. Set by visual_decision.py.",
    )

    # Scene selection (only set when needs_visual=True)
    scene_type: Optional[SceneType] = None
    scene_description: Optional[str] = Field(
        default=None,
        description="Free-text scene description fed to visual_prompt.enhance_visual_prompt",
    )
    mood: Optional[VisualMood] = None
    outfit: Optional[str] = Field(
        default=None,
        description="Outfit text (e.g. 'soft cream knit sweater'); free-form, not enum.",
    )
    outfit_tier: Optional[OutfitTier] = None
    content_context: Optional[str] = Field(
        default=None,
        description="What the persona is doing in the scene — used as Action line.",
    )
    aspect_ratio: str = Field(
        default="1:1",
        description="Platform-specific aspect (1:1 IG, 16:9 X, 9:16 YT, etc.)",
    )
    rationale: str = Field(
        default="",
        description="Why this scene was chosen for this draft (logged for memory).",
    )

    # Generation outputs (filled by tools post-pick)
    asset_id: Optional[str] = Field(
        default=None, description="persona_assets.id after generation + storage"
    )
    image_url: Optional[str] = Field(
        default=None, description="Public URL of the watermarked stored image"
    )
    model_slug: Optional[str] = Field(
        default=None, description="Wiro model slug used (e.g. ByteDance/seedream-v4-5)"
    )
    cost_usd: Optional[float] = None
    latency_ms: Optional[int] = None

    # Compliance outputs
    clip_similarity: Optional[float] = None
    aesthetic_score: Optional[float] = None
    ocr_flagged: Optional[bool] = None
    compliance_verdict: ComplianceVerdict = "SKIPPED"
    compliance_reasoning: Optional[str] = None

    # Phase 42.B — Nano Banana JSON-style brief used for the brand path
    # (template label, subject, environment, camera, mood). Surfaced for
    # the StageDetails UI accordion so Berkay can see which variant fired.
    # None when the cansu path executed or the builder failed.
    visual_brief_json: Optional[dict] = Field(
        default=None,
        description=(
            "Phase 42.B — structured Nano Banana prompt brief "
            "(SUBJECT_TEMPLATES variant + slot-filled fields)."
        ),
    )

    # Phase 41.E — Visual Decision Agent (Phase 39 + 41.B) snapshot
    # Surfaced so the UI can explain "neden Cansu" / "neden marka".
    visual_decision_needs_cansu: Optional[bool] = Field(
        default=None,
        description=(
            "Phase 39 LLM router's call: True → curated Cansu photo, "
            "False → brand visual. None when the caller skipped routing."
        ),
    )
    visual_decision_reason: Optional[str] = Field(
        default=None,
        description="One-sentence Turkish rationale from the LLM router.",
    )
    visual_decision_path: Optional[str] = Field(
        default=None,
        description="Which path executed: 'cansu' | 'brand' (or None).",
    )
    visual_decision_model: Optional[str] = Field(
        default=None,
        description="Model slug that produced the routing decision.",
    )

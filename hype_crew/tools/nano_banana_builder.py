"""Phase 42.B — Nano Banana JSON-style prompt builder for brand-news visuals.

Replaces the free-text `scene_description` blob that used to be forwarded
to Wiro Nano Banana Pro with a structured Pydantic payload modeled on
Berkay's n8n Content Factory workflow. The n8n workflow's JSON schema —
{subject, environment, camera, mood, brand_elements} — produced visibly
better brand visuals than the current plain-text path; this module ports
that schema with a few hardening rules taken from the /debate (see
projects/debates/2026-06-02-visual-routing/decisions.md):

- **5-field MVP** (subject.main, subject.secondary, environment, camera.distance,
  mood). `brand_elements` is omitted in v1: per Critic, it's hallucination
  prone without a brand-asset registry and we don't have one yet.
- **SUBJECT_TEMPLATES with 3 variants per content_type.** Critic's
  "3-week regret" was that brand visuals would all look identical (two
  logos on a white background). Rotating through 3 compositional
  variants per content_type keeps the IG grid visually varied without
  any per-post LLM call. Rotation seed is hash(trend_topic) % 3 so the
  same topic always picks the same variant (idempotent) but different
  topics spread across variants.
- **Slot-filling, not free-form.** Templates own the structure; the
  caller fills `{brand_a}`, `{brand_b}`, `{topic_hint}` slots from
  brand_extractor output + trend_topic. The LLM is NOT invoked here.
  When brand_extractor returns nothing, `_default` template kicks in
  with a generic-but-safe fallback and a WARNING log so future content
  types get explicit templates added.
- **Caps on field lengths** so the serialized JSON stays comfortably
  inside Wiro's prompt token budget (subject.main ≤100, secondary ≤70,
  environment ≤120 chars).

Output: a JSON string (`NanoBananaPrompt.model_dump_json()`) that the
existing `visual_director_tools._generate_and_check_async` flow forwards
to `enhance_visual_prompt` as the `scene_description` field. Backward-
compatible: the downstream pipeline doesn't care whether scene_description
is plain text or JSON-string — Nano Banana Pro is a "Thinking" model that
parses both.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from loguru import logger
from pydantic import BaseModel, Field

from .brand_extractor import extract_brand_from_topic


# ─── Pydantic models ────────────────────────────────────────────────────


class SubjectBlock(BaseModel):
    """The main subject of the image — what dominates the frame."""

    main: str = Field(..., max_length=100)
    secondary: Optional[str] = Field(default=None, max_length=70)
    arrangement: str = Field(
        default="centered product focus, no people in frame",
        max_length=80,
    )


class EnvironmentBlock(BaseModel):
    """The setting / background — where the subject lives."""

    background: str = Field(..., max_length=120)
    room_objects: Optional[str] = Field(default=None, max_length=80)


class CameraBlock(BaseModel):
    """Camera / lens / framing."""

    lens: str = Field(default="50mm")
    aperture: str = Field(default="f/2.8")
    distance: str = Field(default="medium")


class NanoBananaPrompt(BaseModel):
    """Phase 42.B — structured Nano Banana JSON-style prompt.

    `brand_elements` deliberately omitted in v1. Add only after Phase 43
    ships a verified brand-asset registry (logos/UI screenshots/color
    palettes); otherwise the LLM hallucinates them.
    """

    label: str = Field(..., max_length=60)
    tags: list[str] = Field(default_factory=list)
    subject: SubjectBlock
    environment: EnvironmentBlock
    camera: CameraBlock = Field(default_factory=CameraBlock)
    lighting: str = Field(default="editorial daylight, soft falloff", max_length=80)
    mood: str = Field(default="editorial product photography", max_length=60)
    color_restriction: str = Field(default="natural, no oversaturation", max_length=60)
    style: str = Field(default="editorial product photography", max_length=60)
    aspect_ratio: str = Field(default="1:1")


# ─── Templates ──────────────────────────────────────────────────────────
# Each content_type maps to a list of 3 variant dicts. Slot names:
#   {brand_a}    — primary brand from brand_extractor (e.g. "OpenAI")
#   {brand_b}    — secondary brand if present (e.g. "Microsoft")
#                  Falls back to "the partner" when only one brand found.
#   {topic_hint} — first 6-8 words of trend_topic, sanitized
#
# Background / camera / aspect picked to encode COMPOSITIONAL variety.
# After 10 partnership posts in 3 weeks, the IG grid won't look like the
# same template fired 10 times.

_DEFAULT_VARIANT: dict = {
    "label": "tech_editorial_default",
    "tags": ["tech", "editorial"],
    "subject_main": "{topic_hint} — editorial product still life",
    "subject_secondary": None,
    "environment_background": "clean white seamless background, editorial flat-lay tech aesthetic",
    "camera_distance": "medium",
    "mood": "editorial product photography",
    "aspect_ratio": "1:1",
}


SUBJECT_TEMPLATES: dict[str, list[dict]] = {
    "model_launch": [
        {
            "label": "model_launch_logotype",
            "tags": ["model_launch", "logotype"],
            "subject_main": "{brand_a} logotype, large, centered, dark background",
            "subject_secondary": "abstract neural network pattern behind it",
            "environment_background": "deep matte black studio backdrop, subtle product spotlight",
            "camera_distance": "close",
            "mood": "cinematic product reveal",
            "aspect_ratio": "1:1",
        },
        {
            "label": "model_launch_screen_mockup",
            "tags": ["model_launch", "ui_mockup"],
            "subject_main": "{brand_a} model UI on a modern monitor, code/text snippet visible",
            "subject_secondary": "minimalist desk corner, no people",
            "environment_background": "soft developer workspace, monitor glow, ambient warm desk lamp",
            "camera_distance": "medium",
            "mood": "editorial workspace",
            "aspect_ratio": "1:1",
        },
        {
            "label": "model_launch_data_viz",
            "tags": ["model_launch", "benchmark"],
            "subject_main": "abstract benchmark chart with {brand_a} branding watermark",
            "subject_secondary": "comparison bars, clean infographic style",
            "environment_background": "editorial flat-lay, off-white paper texture, soft shadows",
            "camera_distance": "medium",
            "mood": "infographic editorial",
            "aspect_ratio": "1:1",
        },
    ],
    "product_launch": [
        {
            "label": "product_launch_hero",
            "tags": ["product_launch", "hero"],
            "subject_main": "{brand_a} product packshot, hero angle, isolated on backdrop",
            "subject_secondary": None,
            "environment_background": "soft gradient backdrop, subtle reflection plane",
            "camera_distance": "close",
            "mood": "cinematic product reveal",
            "aspect_ratio": "1:1",
        },
        {
            "label": "product_launch_lifestyle",
            "tags": ["product_launch", "lifestyle"],
            "subject_main": "{brand_a} product on a real wooden desk, in-use context",
            "subject_secondary": "MacBook half visible, notebook, plant",
            "environment_background": "modern home office, soft daylight",
            "camera_distance": "medium",
            "mood": "editorial workspace",
            "aspect_ratio": "1:1",
        },
        {
            "label": "product_launch_detail",
            "tags": ["product_launch", "detail"],
            "subject_main": "macro detail of {brand_a} product surface, texture-focused",
            "subject_secondary": None,
            "environment_background": "darkroom backdrop, single rim light from upper-right",
            "camera_distance": "close",
            "mood": "cinematic detail",
            "aspect_ratio": "1:1",
        },
    ],
    "partnership": [
        {
            "label": "partnership_dual_logo",
            "tags": ["partnership", "logos"],
            "subject_main": "{brand_a} logo + {brand_b} logo, side by side, equal weight",
            "subject_secondary": "subtle handshake icon between them, minimalist",
            "environment_background": "clean white background, editorial corporate aesthetic",
            "camera_distance": "medium",
            "mood": "corporate editorial",
            "aspect_ratio": "1:1",
        },
        {
            "label": "partnership_console",
            "tags": ["partnership", "ui_mockup"],
            "subject_main": "console UI screenshot showing {brand_a} integration with {brand_b}",
            "subject_secondary": "dropdown menu with both brand names visible",
            "environment_background": "dark developer monitor glow, neutral desk corner",
            "camera_distance": "medium",
            "mood": "developer workspace",
            "aspect_ratio": "1:1",
        },
        {
            "label": "partnership_split_screen",
            "tags": ["partnership", "split"],
            "subject_main": "split-screen composition: {brand_a} on left half, {brand_b} on right",
            "subject_secondary": "thin vertical divider in brand-neutral gray",
            "environment_background": "editorial gradient, each half tinted toward the respective brand color",
            "camera_distance": "medium",
            "mood": "editorial brand collision",
            "aspect_ratio": "1:1",
        },
    ],
    "pricing": [
        {
            "label": "pricing_tiers_ui",
            "tags": ["pricing", "ui"],
            "subject_main": "{brand_a} pricing page screenshot, tiers visible",
            "subject_secondary": "selected tier highlighted in brand color",
            "environment_background": "editorial flat-lay, off-white paper texture",
            "camera_distance": "medium",
            "mood": "editorial product info",
            "aspect_ratio": "1:1",
        },
        {
            "label": "pricing_comparison",
            "tags": ["pricing", "comparison"],
            "subject_main": "side-by-side {brand_a} pricing tier cards, premium vs standard",
            "subject_secondary": "subtle highlight on the value differentiator",
            "environment_background": "clean off-white background, soft side light",
            "camera_distance": "medium",
            "mood": "editorial comparison",
            "aspect_ratio": "1:1",
        },
        {
            "label": "pricing_calculator",
            "tags": ["pricing", "calc"],
            "subject_main": "{brand_a} cost calculator UI, slider mid-position, total visible",
            "subject_secondary": "small annotation arrows",
            "environment_background": "developer dark mode monitor, ambient warm side light",
            "camera_distance": "close",
            "mood": "developer workspace",
            "aspect_ratio": "1:1",
        },
    ],
    "api_update": [
        {
            "label": "api_update_docs",
            "tags": ["api_update", "docs"],
            "subject_main": "{brand_a} API documentation page, code snippet visible",
            "subject_secondary": "version-bump badge in upper-right",
            "environment_background": "dark developer monitor, soft ambient room glow",
            "camera_distance": "medium",
            "mood": "developer workspace",
            "aspect_ratio": "1:1",
        },
        {
            "label": "api_update_terminal",
            "tags": ["api_update", "terminal"],
            "subject_main": "terminal window mid-stream, {brand_a} SDK command running",
            "subject_secondary": "syntax-highlighted curl call visible",
            "environment_background": "dark dev workspace, monitor lit by terminal output",
            "camera_distance": "close",
            "mood": "developer focus",
            "aspect_ratio": "1:1",
        },
        {
            "label": "api_update_changelog",
            "tags": ["api_update", "changelog"],
            "subject_main": "{brand_a} changelog entry with new endpoint highlighted",
            "subject_secondary": "subtle 'NEW' badge",
            "environment_background": "clean off-white editorial backdrop, soft top light",
            "camera_distance": "medium",
            "mood": "editorial release notes",
            "aspect_ratio": "1:1",
        },
    ],
    "research": [
        {
            "label": "research_paper_hero",
            "tags": ["research", "paper"],
            "subject_main": "{topic_hint} research paper title page, academic typography",
            "subject_secondary": "small {brand_a} affiliation logo at the bottom",
            "environment_background": "neutral editorial backdrop, subtle paper texture",
            "camera_distance": "medium",
            "mood": "academic editorial",
            "aspect_ratio": "1:1",
        },
        {
            "label": "research_neural_net",
            "tags": ["research", "abstract"],
            "subject_main": "abstract neural network visualization, dense node graph",
            "subject_secondary": "subtle {brand_a} watermark in corner",
            "environment_background": "dark editorial backdrop, glowing data lines",
            "camera_distance": "wide",
            "mood": "cinematic data abstract",
            "aspect_ratio": "1:1",
        },
        {
            "label": "research_chart",
            "tags": ["research", "chart"],
            "subject_main": "benchmark chart showing {brand_a} model results vs baselines",
            "subject_secondary": "annotation arrows highlighting the headline number",
            "environment_background": "editorial flat-lay, off-white backdrop",
            "camera_distance": "medium",
            "mood": "infographic editorial",
            "aspect_ratio": "1:1",
        },
    ],
    "security": [
        {
            "label": "security_lock",
            "tags": ["security", "lock"],
            "subject_main": "stylized lock icon + {brand_a} brand mark, paired",
            "subject_secondary": "subtle padlock circuitry pattern behind",
            "environment_background": "dark backdrop, single rim light, editorial dramatic",
            "camera_distance": "close",
            "mood": "editorial security tone",
            "aspect_ratio": "1:1",
        },
        {
            "label": "security_breach_alert",
            "tags": ["security", "alert"],
            "subject_main": "{brand_a} security dashboard with alert banner visible",
            "subject_secondary": "subtle red status indicator",
            "environment_background": "dark monitor glow, focused operator perspective",
            "camera_distance": "medium",
            "mood": "developer alert tone",
            "aspect_ratio": "1:1",
        },
        {
            "label": "security_patch_notes",
            "tags": ["security", "patch"],
            "subject_main": "{brand_a} patch notes document, CVE references visible",
            "subject_secondary": "version-bump badge",
            "environment_background": "neutral editorial paper texture, soft top light",
            "camera_distance": "medium",
            "mood": "editorial release notes",
            "aspect_ratio": "1:1",
        },
    ],
    "m_and_a": [
        {
            "label": "m_and_a_handshake",
            "tags": ["m_and_a", "deal"],
            "subject_main": "{brand_a} logo + {brand_b} logo, framed as an acquisition headline",
            "subject_secondary": "subtle financial-doc backdrop watermark",
            "environment_background": "clean off-white editorial, soft top light",
            "camera_distance": "medium",
            "mood": "corporate editorial",
            "aspect_ratio": "1:1",
        },
        {
            "label": "m_and_a_org_chart",
            "tags": ["m_and_a", "org"],
            "subject_main": "stylized org chart showing {brand_a} absorbing {brand_b}",
            "subject_secondary": "arrow direction unmistakable",
            "environment_background": "editorial business broadsheet aesthetic, soft side light",
            "camera_distance": "medium",
            "mood": "business editorial",
            "aspect_ratio": "1:1",
        },
        {
            "label": "m_and_a_skyline",
            "tags": ["m_and_a", "skyline"],
            "subject_main": "two corporate towers in dawn light, {brand_a} and {brand_b} signage faintly visible",
            "subject_secondary": "thin connecting walkway between towers",
            "environment_background": "early-morning urban skyline, soft golden gradient",
            "camera_distance": "wide",
            "mood": "cinematic corporate",
            "aspect_ratio": "1:1",
        },
    ],
    "default": [_DEFAULT_VARIANT],
}


# ─── Builder ────────────────────────────────────────────────────────────


def _pick_variant_index(trend_topic: str, num_variants: int) -> int:
    """Deterministic index from trend_topic so the same topic always
    produces the same variant — but different topics fan out across
    variants to keep the IG grid varied. md5 is fine here (no security
    use), and we keep it stable across Python versions."""
    if num_variants <= 1:
        return 0
    h = hashlib.md5((trend_topic or "").encode("utf-8")).hexdigest()
    return int(h[:8], 16) % num_variants


def _topic_hint(trend_topic: str, max_words: int = 8) -> str:
    """Take the first few words of trend_topic, no punctuation at end."""
    if not trend_topic:
        return "tech update"
    words = trend_topic.split()[:max_words]
    return " ".join(words).rstrip(".,;:")


def _fill(template_str: str, brand_a: str, brand_b: str, topic_hint: str) -> str:
    """Slot-fill a template string. Empty slots are silently allowed."""
    return (
        template_str
        .replace("{brand_a}", brand_a)
        .replace("{brand_b}", brand_b)
        .replace("{topic_hint}", topic_hint)
    )


def _extract_secondary_brand(trend_topic: str, primary: Optional[str]) -> Optional[str]:
    """Find a second brand by re-running the extractor on the topic with
    the primary brand stripped. Cheap heuristic — good enough for
    partnership / m_and_a posts.
    """
    if not trend_topic or not primary:
        return None
    redacted = trend_topic.replace(primary, " ").replace(primary.lower(), " ")
    second = extract_brand_from_topic(redacted)
    return second if second and second.lower() != primary.lower() else None


def build_brand_news_prompt(
    *,
    trend_topic: str,
    content_type: Optional[str],
    platform: Optional[str] = None,
    aspect_ratio: str = "1:1",
) -> tuple[str, dict]:
    """Build a Nano Banana JSON-style prompt for a brand-news visual.

    Returns:
        (prompt_json_string, brief_dict). The JSON string is forwarded to
        Wiro Nano Banana Pro via the existing `enhance_visual_prompt`
        pipeline. The dict is persisted on `VisualDirectorOutput.
        visual_brief_json` for the Phase 41.E UI accordion.
    """
    ct_norm = (content_type or "default").strip().lower() or "default"
    variants = SUBJECT_TEMPLATES.get(ct_norm)
    if not variants:
        logger.warning(
            f"[nano_banana_builder] no template for content_type={ct_norm!r}; "
            f"using _default. Add a SUBJECT_TEMPLATES[{ct_norm!r}] entry to fix."
        )
        variants = SUBJECT_TEMPLATES["default"]

    variant = variants[_pick_variant_index(trend_topic or "", len(variants))]

    primary_brand = extract_brand_from_topic(trend_topic) or "the company"
    secondary_brand = _extract_secondary_brand(trend_topic, primary_brand) or "the partner"
    topic_hint = _topic_hint(trend_topic)

    subject_main = _fill(variant["subject_main"], primary_brand, secondary_brand, topic_hint)
    subject_secondary = (
        _fill(variant["subject_secondary"], primary_brand, secondary_brand, topic_hint)
        if variant.get("subject_secondary")
        else None
    )
    environment_bg = _fill(variant["environment_background"], primary_brand, secondary_brand, topic_hint)

    prompt = NanoBananaPrompt(
        label=variant["label"],
        tags=list(variant.get("tags") or []),
        subject=SubjectBlock(main=subject_main, secondary=subject_secondary),
        environment=EnvironmentBlock(background=environment_bg),
        camera=CameraBlock(distance=variant.get("camera_distance", "medium")),
        mood=variant.get("mood", "editorial product photography"),
        aspect_ratio=variant.get("aspect_ratio", aspect_ratio),
    )

    return prompt.model_dump_json(), prompt.model_dump(mode="python")

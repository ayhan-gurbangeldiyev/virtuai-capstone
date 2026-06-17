"""Phase 42.B — Brand visual brief builder.

Replaces the single-line scene_description for `composition_type=brand_news_visual`
with a structured 9-field brief (8 standard + restrictions), serialized as
labeled prose for Wiro Nano Banana Pro.

Ported from n8n Content Factory's labeled-prose schema, which historically
produced demonstrably better brand mockups than free-text scene_descriptions.

Foundation status (42B-01..05A): pure function, no production call site yet.
Not yet wired into `hype_crew/flow.py`. Has zero side effects on the existing
pipeline. Safe to deploy as dormant code.

Foundation adjustments (42B-05A):
- Partnership template generalized — no longer assumes the secondary brand
  has a "console". Uses neutral integration language that works for any
  two-brand combination.
- Restrictions field added inline (not deferred to 42B-14). All briefs now
  carry a labeled-prose Restrictions clause that bans people, readable
  text clutter, and known failure modes.
- All templates rewritten to PREFER symbolic UI / abstract shapes over
  readable text. Wiro Nano Banana commonly produces nonsensical UI text
  when asked for readable interfaces; symbolic decoration is more reliable.

Design contract:
- `build_brand_visual_brief()` is a pure function (no I/O, no LLM calls,
  no DB reads). Deterministic given the same inputs.
- Never returns a partially-filled brief. Either returns a complete
  BrandVisualBrief or None.
- Never raises on unknown content_type — falls back to the `_default`
  template, which is mandatory and always present.
- Empty / missing brand_entities → returns None. Caller falls back to
  the legacy plain `scene_description` path.
- Partnership template needs ≥2 brands. If only 1 is supplied, degrades
  to `_default` rather than dropping to None — preserves the brand mention
  instead of losing it.
- Every brief carries a `restrictions` field. Default value includes the
  known failure modes from the 30-visual audit (people, melted logos,
  readable text, cartoon style).

Why labeled prose (not raw JSON):
- n8n production used labeled prose ("Subject: X. Environment: Y. ...")
- Nano Banana Pro responds to that format better than raw JSON dicts
- Same dict is still preserved on `visual_brief_json` for observability
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field


# ─── Defaults ──────────────────────────────────────────────────────────────


DEFAULT_RESTRICTIONS = (
    "no people, no human face, no presenter, no Cansu face, "
    "no influencer portrait, no readable paragraphs, "
    "no fake text clutter, no cartoon style, no melted logos, "
    "no distorted UI elements"
)


# ─── Output Pydantic schema ────────────────────────────────────────────────


class SubjectSpec(BaseModel):
    """Subject sub-object of the brief.

    `main` is the dynamic field — slot-filled from brand_entities.
    `secondary` is template-defined (constant per content_type).
    """

    main: str
    secondary: Optional[str] = None


class CameraSpec(BaseModel):
    """Camera sub-object of the brief. All fields template-defined."""

    angle: str
    distance: str


class BrandVisualBrief(BaseModel):
    """Structured brand visual brief (9 fields including restrictions).

    Mirrors n8n Content Factory's labeled-prose schema. Serialize via
    `serialize_brief_to_prose()` before passing to Wiro.

    Field origin:
      subject.main:        DYNAMIC (slot-filled from brand_entities)
      subject.secondary:   CONSTANT per template
      environment:         CONSTANT per template
      camera.angle:        CONSTANT per template
      camera.distance:     CONSTANT per template
      lighting:            CONSTANT per template
      mood:                CONSTANT per template
      style:               CONSTANT per template
      aspect_ratio:        PASSED IN (default '1:1')
      brand_elements:      DYNAMIC (= brand_entities)
      restrictions:        DEFAULT (shared across all briefs)
    """

    subject: SubjectSpec
    environment: str
    camera: CameraSpec
    lighting: str
    mood: str
    style: str
    aspect_ratio: str = "1:1"
    brand_elements: list[str] = Field(default_factory=list)
    restrictions: str = DEFAULT_RESTRICTIONS


# ─── Internal template definition ─────────────────────────────────────────


@dataclass(frozen=True)
class TemplateSpec:
    """Per-content_type template: slot-fillable subject + frozen constants.

    `subject_main_template` may contain `{brand_primary}` and
    `{brand_secondary}` placeholders. Other fields are template-defined
    constants — never slot-filled.
    """

    subject_main_template: str
    subject_secondary: Optional[str]
    environment: str
    camera_angle: str
    camera_distance: str
    lighting: str
    mood: str
    style: str
    requires_secondary_brand: bool = False


# ─── SUBJECT_TEMPLATES ─────────────────────────────────────────────────────
# 42B-05A revision rules applied:
#   - Partnership: no "console" assumption. Generic integration language.
#   - All templates: prefer symbolic UI / abstract shapes over readable text.
#     "No readable text" is repeated in subject.main where the LLM is most
#     likely to invent fake UI labels.


SUBJECT_TEMPLATES: dict[str, TemplateSpec] = {
    "partnership": TemplateSpec(
        subject_main_template=(
            "{brand_primary} and {brand_secondary} integration visual: "
            "both brand logos prominent and visually connected through a "
            "clean abstract integration panel, symbolic connector lines "
            "between the two platforms, modern enterprise integration "
            "aesthetic, no readable interface text"
        ),
        subject_secondary=(
            "abstract dashboard panels, glowing connection lines between "
            "the brands, symbolic data flow indicators (no readable text)"
        ),
        environment=(
            "clean modern dark studio backdrop, subtle tech atmosphere, "
            "minimal but premium product-launch feel"
        ),
        camera_angle="eye level",
        camera_distance="medium",
        lighting=(
            "soft studio key light from upper-left, gentle rim light "
            "separating the integration panel from the background"
        ),
        mood="professional, integrative, signal-of-strategic-alliance",
        style=(
            "editorial product photography, magazine-quality, photoreal, "
            "shallow depth of field"
        ),
        requires_secondary_brand=True,
    ),
    "model_launch": TemplateSpec(
        subject_main_template=(
            "{brand_primary} logo prominent + symbolic AI model interface "
            "mockup, abstract chat-style frame with glyph-shaped placeholders "
            "instead of readable text, minimal modern interface, no readable "
            "labels"
        ),
        subject_secondary=(
            "abstract performance indicator bars, symbolic version glyph, "
            "no readable text"
        ),
        environment=(
            "clean dark editorial backdrop, subtle data-grid texture, "
            "premium product-launch feel"
        ),
        camera_angle="eye level",
        camera_distance="medium-close",
        lighting=(
            "soft studio key light, blue-white LED accent on the device "
            "screen rim"
        ),
        mood="technical, anticipatory, model-launch energy",
        style=(
            "hyper-realistic product mockup, magazine-quality editorial, "
            "shallow depth of field"
        ),
    ),
    "api_update": TemplateSpec(
        subject_main_template=(
            "{brand_primary} logo + symbolic developer interface, abstract "
            "code-block panel with placeholder syntax patterns (not readable "
            "code), minimal terminal-style visual aesthetic, no readable text"
        ),
        subject_secondary=(
            "abstract terminal rectangle silhouette, symbolic JSON-brace "
            "shapes in a side panel (no readable characters)"
        ),
        environment=(
            "dark modern developer workspace ambiance, monitor-glow lighting, "
            "minimal physical elements"
        ),
        camera_angle="slight overhead",
        camera_distance="medium-close",
        lighting=(
            "monitor-glow primary lighting, cool blue-white tones, subtle "
            "ambient fill"
        ),
        mood="technical, developer-focused, capability-expansion",
        style=(
            "editorial tech photography, photoreal screen-capture aesthetic, "
            "high detail"
        ),
    ),
    "research": TemplateSpec(
        subject_main_template=(
            "abstract neural network visualization with interconnected glowing "
            "nodes and weighted pathways, {brand_primary} branding subtle in "
            "the lower corner, no readable text overlays"
        ),
        subject_secondary=(
            "data flow streams, attention pattern heatmaps as background "
            "texture"
        ),
        # 42B-12 — explicit foreground/background separation + atmospheric
        # depth language; no readable-text risk added.
        environment=(
            "expansive deep-space digital backdrop, cyan and electric purple "
            "accent tones, atmospheric volumetric depth with clear "
            "foreground-to-background separation"
        ),
        camera_angle="centered, eye level",
        camera_distance="wide",
        # 42B-12 — dramatic core-to-edge brightness falloff + hero-centered
        # light spill push the predictor toward contrast/depth cues.
        lighting=(
            "atmospheric volumetric lighting from within the network, cool "
            "blue-cyan ambient, soft purple highlights, dramatic core-to-edge "
            "brightness falloff, hero-centered light spill on the network "
            "core"
        ),
        mood="cinematic, contemplative, research-breakthrough atmosphere",
        # 42B-12 — magazine-cover composition + shallow focus + negative
        # space terms reward the predictor without changing content.
        style=(
            "photoreal 3D render aesthetic, sci-fi editorial magazine-cover "
            "composition, hero-centered with negative space, shallow focus "
            "on the network core"
        ),
    ),
    "product_launch": TemplateSpec(
        subject_main_template=(
            "{brand_primary} logo prominent + symbolic product interface "
            "mockup on a modern device screen, clean abstract dashboard "
            "shapes representing the product, no readable text or labels"
        ),
        subject_secondary=(
            "symbolic indicator badges, abstract launch glyph (no readable "
            "text)"
        ),
        environment=(
            "clean editorial backdrop, premium product-launch ambiance, "
            "subtle gradient mesh background"
        ),
        camera_angle="eye level",
        camera_distance="medium",
        lighting=(
            "soft studio key light, warm color grading, gentle rim light "
            "separating the device from the background"
        ),
        mood="professional, launch-day energy, polished",
        style=(
            "editorial product photography, magazine-quality, photoreal, "
            "shallow depth of field"
        ),
    ),
    # MANDATORY — never remove. Catches any content_type not explicitly above
    # AND serves as the degradation target for partnership-with-only-one-brand.
    "_default": TemplateSpec(
        subject_main_template=(
            "{brand_primary} brand visual on a modern device screen with "
            "symbolic abstract interface elements (no readable text), clean "
            "editorial product shot, abstract tech aesthetic, no people in "
            "frame"
        ),
        subject_secondary=(
            "subtle abstract technology aesthetic elements appropriate to "
            "AI / SaaS context"
        ),
        environment=(
            "clean editorial backdrop, professional product-shot ambiance"
        ),
        camera_angle="eye level",
        camera_distance="medium",
        lighting=(
            "soft studio key light, gentle fill, professional product-shot "
            "tones"
        ),
        mood="professional, technology-focused",
        style=(
            "editorial product photography, magazine-quality, photoreal"
        ),
    ),
}


# ─── Public functions ──────────────────────────────────────────────────────


def build_brand_visual_brief(
    *,
    content_type: str,
    brand_entities: Optional[list[str]],
    aspect_ratio: str = "1:1",
    restrictions: Optional[str] = None,
) -> Optional[BrandVisualBrief]:
    """Build a structured brand visual brief from content_type + brands.

    Pure function. No I/O. Deterministic.

    Args:
        content_type: Strategist's content_type. Lookup key for
            SUBJECT_TEMPLATES. Unknown values fall back to '_default'.
        brand_entities: Ordered list of brand names. First is treated as
            primary; second (if present) as secondary. Empty / None /
            all-empty-strings → returns None.
        aspect_ratio: Target Wiro aspect ratio. Default '1:1'.
        restrictions: Optional override of the default restrictions string.
            None → use DEFAULT_RESTRICTIONS (recommended).

    Returns:
        BrandVisualBrief on success.
        None if brand_entities is effectively empty (caller should fall
        back to the legacy plain scene_description path).

    Degradation behavior:
    - Unknown content_type → '_default' template
    - Partnership with <2 brands → '_default' template (preserves the
      one brand we have rather than losing it)
    - Never raises (other than on malformed template strings, which would
      indicate a programmer error in this file)
    """
    if not brand_entities:
        return None

    cleaned_entities = [
        b for b in brand_entities if isinstance(b, str) and b.strip()
    ]
    if not cleaned_entities:
        return None

    template = SUBJECT_TEMPLATES.get(content_type, SUBJECT_TEMPLATES["_default"])

    # Partnership requires 2 brands. Degrade to _default if only one
    # supplied so we still produce a usable brief.
    if template.requires_secondary_brand and len(cleaned_entities) < 2:
        template = SUBJECT_TEMPLATES["_default"]

    brand_primary = cleaned_entities[0]
    brand_secondary = (
        cleaned_entities[1] if len(cleaned_entities) > 1 else ""
    )

    subject_main = template.subject_main_template.format(
        brand_primary=brand_primary,
        brand_secondary=brand_secondary,
    )

    brief_kwargs = {
        "subject": SubjectSpec(
            main=subject_main,
            secondary=template.subject_secondary,
        ),
        "environment": template.environment,
        "camera": CameraSpec(
            angle=template.camera_angle,
            distance=template.camera_distance,
        ),
        "lighting": template.lighting,
        "mood": template.mood,
        "style": template.style,
        "aspect_ratio": aspect_ratio,
        "brand_elements": cleaned_entities,
    }
    if restrictions is not None:
        brief_kwargs["restrictions"] = restrictions

    return BrandVisualBrief(**brief_kwargs)


def serialize_brief_to_prose(brief: BrandVisualBrief) -> str:
    """Render a BrandVisualBrief as a single labeled-prose string for Wiro.

    Format mirrors n8n Content Factory's production format:
        "Subject: ... Secondary: ... Environment: ... Camera: ...
         Lighting: ... Mood: ... Style: ... Aspect ratio: ...
         Brand elements: ... Restrictions: ..."

    Args:
        brief: Validated BrandVisualBrief Pydantic model.

    Returns:
        Single-line string suitable for direct injection as the
        scene_description field in the Wiro pipeline call.
        Caller is expected to append the existing aesthetic_suffix
        (currently in flow.py:1291–1296). This function does NOT touch
        that suffix.
    """
    parts: list[str] = [f"Subject: {brief.subject.main}."]
    if brief.subject.secondary:
        parts.append(f"Secondary: {brief.subject.secondary}.")
    parts.append(f"Environment: {brief.environment}.")
    parts.append(f"Camera: {brief.camera.angle}, {brief.camera.distance}.")
    parts.append(f"Lighting: {brief.lighting}.")
    parts.append(f"Mood: {brief.mood}.")
    parts.append(f"Style: {brief.style}.")
    parts.append(f"Aspect ratio: {brief.aspect_ratio}.")
    if brief.brand_elements:
        parts.append(
            f"Brand elements: {', '.join(brief.brand_elements)}."
        )
    if brief.restrictions:
        parts.append(f"Restrictions: {brief.restrictions}.")
    return " ".join(parts)

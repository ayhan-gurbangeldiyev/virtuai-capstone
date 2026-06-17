"""Guide-driven visual prompt builder for Cansu image generation.

Cansu is a real person, so facial identity must come from approved reference
images rather than textual face descriptions. This module implements the
contract in docs/07-Image-Prompt-Guide.md.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

PlatformKey = Literal["linkedin", "instagram", "x", "medium", "youtube"]
VisualMood = Literal["professional", "warm", "cinematic", "technical", "casual"]
VisualPromptMode = Literal["TEXT_TO_IMAGE", "EDIT", "COMPOSITE"]
VisualModelTarget = Literal["nano_pro", "nano_banana_2", "gpt_image_2"]

IDENTITY_LOCK = (
    "Match the face of the person in Image 1 pixel-faithfully.\n"
    "Use Image 1 as the only source for facial identity.\n"
    "Tolerate only the changes I explicitly request below."
)
ACTION_INDEPENDENCE = (
    "Create a new believable moment from the Action line. Do not copy Image 1's "
    "pose, hand placement, hair-touching gesture, selfie arm, clothing, "
    "background, lighting, or camera angle unless that element has its own "
    "explicit role label or the brief asks for it."
)
REALISM_BLOCK = (
    "visible skin pores, fine pore texture, subtle facial asymmetry, "
    "single catchlight in each eye, faint film grain (Kodak Portra 400 feel), "
    "candid unposed expression, slight imperfection in framing, "
    "fabric weave visible on garments, natural color balance, "
    "no cinematic grading"
)
GPT_IMAGE_REALISM_BLOCK = (
    "iPhone 11 photo realism (2019-era 12MP sensor, less aggressive HDR and "
    "sharpening than modern phones), matte unretouched skin with OBVIOUS large "
    "pores around the nose and cheeks, slight oily T-zone, mild redness on the "
    "cheek, normal skin micro-variation, mild under-eye texture, tiny flyaway "
    "hairs, subtle facial asymmetry — NO porcelain look, NO airbrushed finish, "
    "NO beauty filter, NO smoothed skin, slightly muted natural color balance, "
    "visible digital noise in shadow areas, mild graininess overall, slight "
    "chromatic aberration on high-contrast edges, candid unposed expression, "
    "slight imperfection in framing, fabric weave visible on garments, no "
    "cinematic grading. "
    # Hand anatomy (every prior run had finger/nail issues)
    "Hands must be anatomically correct: exactly five fingers on each visible "
    "hand, fingers naturally separated and resting (not actively gesturing), "
    "nail beds clearly attached to fingertips with no floating or merging, no "
    "extra digits, no melted webbing between fingers. If both hands are not "
    "fully visible, only show one hand naturally framed."
)
BRAND_CONSISTENCY = (
    "quiet premium tech aesthetic, authentic Turkish tech-founder energy, "
    "modern AI product context, calm confident presence, clean composition"
)
GPT_IMAGE_ATMOSPHERE = (
    "real Turkish founder working in an ordinary modern office, not an ad, "
    "not a fashion portrait, not a staged campaign image, calm focused presence"
)
GPT_IMAGE_CONSTRAINTS = (
    "Constraints: no airbrushed skin, no waxy highlights, no plastic look, "
    "no symmetrical perfection, no over-saturation, no teal-orange grade, "
    "no AI smoothing, no face retouching, no beauty filter, no skin smoothing, "
    "no porcelain skin, no fashion editorial polish, no extra fingers, "
    "no duplicate hands, no watermark, no on-screen text unless requested, "
    "no stock-photo feel, no studio headshot polish, no other people in sharp focus, "
    "no brand logos, no religious symbols, no political imagery."
)
NANO_CONSTRAINTS = (
    "Constraints: matte natural skin only with OBVIOUS large skin pores around "
    "nose and cheeks only, candid unposed framing only, amateur 2020-era phone "
    "snapshot feel only, raw unedited phone photo only, true material textures "
    "only, slightly muted neutral colors only, identity from Image 1 only, "
    "anatomically correct hands with exactly five fingers each only, plain "
    "unbranded silver laptop only, blurred non-readable screen content only.\n"
    "Do not include: any AI smoothing, any plastic look, any waxy highlights, "
    "any porcelain skin, any airbrushed finish, any beauty filter, any "
    "symmetric perfection, any over-saturation, any teal-orange grade, "
    "any cinematic grading, any studio polish, any portrait mode blur, "
    "any professional photography polish, any stock-photo polish, any "
    "influencer aesthetic, any modern computational photography look "
    "(iPhone 13/14/15/16 look), any aggressive HDR, "
    # Hand / anatomy failure modes (recurring LLM judge tells)
    "any extra fingers, any merged fingers, any floating nails, any nails "
    "detached from fingertips, any melted webbing between fingers, any "
    "duplicate hands, any deformed hand anatomy, "
    # Brand / screen failure modes (recurring LLM judge tells)
    "any Apple logo, any laptop brand logo, any illuminated logo on the lid, "
    "any visible Apple bite, any readable UI text on the screen, any garbled "
    "fake interface text, any inconsistent keyboard layout, any merged keys, "
    # Generic compliance
    "watermark, on-screen text outside the laptop screen, brand logos on "
    "clothing, religious symbols, political imagery, other people in sharp focus."
)
NON_HUMAN_CONSTRAINTS = (
    "Constraints: no plastic look on materials, no over-saturation, "
    "no AI smoothing, no watermark, no on-screen text unless requested, "
    "no extra subjects, no over-styled presentation, no brand logos."
)
PRESERVE_IDENTITY = (
    "Preserve identity from Image 1 pixel-faithfully - do not invent or alter facial features."
)
EDIT_PRESERVE_BLOCK = (
    "PRESERVE: face, identity, hair length and color, skin tone, eye direction, "
    "expression, hand position, body proportions, pose, clothing, jewelry, camera "
    "angle, focal length compression, depth of field, lighting direction, color "
    "temperature, grain, and overall photo aesthetic - identical to the reference."
)
FORBIDDEN_VOCABULARY = (
    "8k",
    "4k",
    "16k",
    "ultra HD",
    "ultra realistic",
    "ultra detailed",
    "photorealistic",
    "hyperrealistic",
    "hyper-detailed",
    "masterpiece",
    "best quality",
    "highest quality",
    "trending on artstation",
    "octane render",
    "unreal engine",
    "perfect lighting",
    "perfect skin",
    "flawless",
    "immaculate",
    "pristine",
    "stunning",
    "beautiful",
    "amazing",
    "gorgeous",
    "smooth skin",
    "glossy skin",
    "glossy",
    "airbrushed",
    "beauty filter",
    "retouched",
    "professional photography",
    "sharp focus",
)

ASPECT_RATIO_BY_PLATFORM: dict[PlatformKey, str] = {
    "linkedin": "1.91:1",
    "instagram": "1:1",
    "x": "16:9",
    "medium": "16:9",
    "youtube": "9:16",
}
LIGHTING_BY_MOOD: dict[VisualMood, str] = {
    "professional": (
        "soft north-facing daylight from camera-left at 9 o'clock, 5500K, "
        "gentle falloff into the right-side shadow"
    ),
    "warm": (
        "warm late-afternoon interior light from a window at 4 o'clock, "
        "3200K, soft spill across the subject's right side"
    ),
    "cinematic": (
        "single key softbox at 10 o'clock with subtle rim from behind at "
        "8 o'clock, neutral fill from camera-right"
    ),
    "technical": "clean diffused daylight, even illumination, neutral 5500K, no harsh shadows",
    "casual": "available daylight only, soft overcast, no studio quality, natural ambient mix",
}
COMPOSITION_BY_PLATFORM: dict[PlatformKey, str] = {
    "linkedin": (
        "eye-level editorial portrait, balanced negative space on the right "
        "for the headline, subject offset to left third"
    ),
    "instagram": (
        "clean square composition, lifestyle editorial framing, subject offset "
        "to right or left third"
    ),
    "x": "wide social-preview composition, readable central subject",
    "medium": (
        "editorial header composition with calm workspace context, subject "
        "offset to left third, copy-friendly negative space at upper right"
    ),
    "youtube": (
        "vertical portrait framing, mobile-first composition, subject filling "
        "upper two-thirds, lower third reserved for caption overlay"
    ),
}
CAMERA_BY_PLATFORM: dict[PlatformKey, str] = {
    "linkedin": "shot on 85mm f/1.8, shallow depth of field, creamy background separation",
    "instagram": "shot on 35mm f/1.8, documentary feel, full-context framing",
    "x": "shot on 50mm f/1.8, natural human-eye perspective",
    "medium": "shot on 35mm f/1.8, documentary feel, full-context framing",
    "youtube": "shot on 35mm f/1.8, documentary feel, handheld mobile-first energy",
}
SCENE_CLUTTER: tuple[tuple[str, str], ...] = (
    (
        "cafe",
        "water rings on wood, condensation on glass, a folded linen napkin, "
        "a half-finished coffee cup",
    ),
    (
        "kitchen",
        "crumbs on the counter, a half-pour of coffee mid-stream, an open jar "
        "with the lid beside it",
    ),
    (
        "outdoor",
        "wet pavement reflections, distant pedestrian motion blur, gentle wind in hair",
    ),
    (
        "street",
        "wet pavement reflections, distant pedestrian motion blur, gentle wind in hair",
    ),
    (
        "rooftop",
        "gentle wind in hair, faint atmospheric haze, distant building lights softly out of focus",
    ),
    (
        "product",
        "natural floor shadow, true material specularity, faint dust on dark surfaces",
    ),
    (
        "workspace",
        "an open plain unbranded silver laptop with NO Apple logo, NO brand "
        "markings, NO illuminated logo on the lid; the screen shows a soft "
        "blurred generic gradient or abstract code-editor look with NO "
        "recognizable UI text and NO readable interface; "
        "a plain ceramic mug of coffee with a faint condensation ring on the "
        "wood, a single phone face-down, no other electronics in frame",
    ),
    (
        "office",
        "an open plain unbranded silver laptop with NO Apple logo, NO brand "
        "markings; screen shows a soft blurred generic UI with NO readable "
        "text; plain ceramic coffee mug, a phone face-down, minimal desk clutter",
    ),
)
DEFAULT_SCENE_CLUTTER = (
    "an open plain unbranded silver laptop with NO Apple logo, NO brand "
    "markings, NO illuminated lid logo; the screen shows a soft blurred "
    "generic gradient with NO readable text and NO recognizable UI; a plain "
    "ceramic mug of coffee, a single phone face-down"
)


@dataclass(frozen=True)
class VisualPromptBrief:
    """Structured request for one generated visual."""

    platform: PlatformKey
    scene_description: str
    outfit: str = "smart casual neutral-toned outfit"
    mood: VisualMood = "professional"
    content_context: str | None = None
    aspect_ratio: str | None = None
    reference_image_urls: list[str] = field(default_factory=list)
    mode: VisualPromptMode | None = None
    # Phase 25.E — visual_mode rotates persona presence:
    #   face       → Cansu prominent (existing behaviour)
    #   conceptual → persona-free; AI interface / neural net / abstract digital
    #   hybrid     → small Cansu overlay + product/UI dominant
    visual_mode: str = "face"


@dataclass(frozen=True)
class EnhancedVisualPrompt:
    """Provider-ready prompt package plus guide metadata."""

    prompt: str
    negative_prompt: str
    aspect_ratio: str
    reference_image_urls: list[str]
    requires_reference_image: bool
    mode: VisualPromptMode
    model_target: VisualModelTarget
    reference_quality: dict[str, int]
    warnings: list[str]
    qc_passed: bool
    fallback_applied: str | None
    platform_target_aspect: str
    emitted_aspect: str

    @property
    def wiro_input_image(self) -> str | list[str] | None:
        if not self.reference_image_urls:
            return None
        if len(self.reference_image_urls) == 1:
            return self.reference_image_urls[0]
        return self.reference_image_urls


def enhance_visual_prompt(
    brief: VisualPromptBrief,
    *,
    model_slug: str = "google/nano-banana-pro",
) -> EnhancedVisualPrompt:
    """Convert a compact visual brief into a model-ready prompt package."""
    scene = _clean_required(_strip_forbidden_vocab(brief.scene_description), "scene_description")
    # Phase 25.E — Conceptual mode has no person, so outfit is irrelevant.
    # Accept empty string and fall back to a benign placeholder so downstream
    # _clean_required doesn't reject the brief.
    raw_outfit = _strip_forbidden_vocab(brief.outfit) if brief.outfit else ""
    if not raw_outfit and brief.visual_mode == "conceptual":
        outfit = "n/a (no person in frame)"
    else:
        outfit = _clean_required(raw_outfit, "outfit")
    content_context = _strip_forbidden_vocab(brief.content_context)
    model_target = _model_target_for_slug(model_slug)
    subject = _detect_subject(scene, content_context, brief.reference_image_urls)
    # Phase 25.E — conceptual mode hard-forces TEXT_TO_IMAGE (no identity
    # composite). Subject is treated as OBJECT regardless of scene heuristics.
    if brief.visual_mode == "conceptual":
        mode = "TEXT_TO_IMAGE"
        subject = "OBJECT"
    else:
        mode = brief.mode or _dispatch_mode(scene, content_context, brief.reference_image_urls, subject)
    platform_target_aspect = brief.aspect_ratio or ASPECT_RATIO_BY_PLATFORM[brief.platform]
    emitted_aspect, fallback_applied = _emitted_aspect(
        platform_target_aspect,
        model_target=model_target,
    )
    warnings: list[str] = []
    if fallback_applied:
        warnings.append(fallback_applied)
    references = list(brief.reference_image_urls)
    reference_quality = {url: 9 for url in references}
    if references:
        warnings.append("reference_quality_prevalidated")
    # Phase 25.E — conceptual mode never expects identity reference, hybrid
    # tolerates having reduced/no anchors. Only face mode strictly requires
    # the HUMAN-subject identity reference.
    if brief.visual_mode == "conceptual":
        requires_reference_image = False
    elif brief.visual_mode == "hybrid":
        # Hybrid: ref helpful but not blocking (Cansu portion may be tiny enough
        # that the model can synthesise the overlay reasonably without anchor).
        requires_reference_image = False
    else:
        requires_reference_image = subject == "HUMAN"
    qc_passed = True
    if requires_reference_image and not references:
        qc_passed = False
        warnings.append("missing_identity_reference")
    if brief.visual_mode != "face":
        warnings.append(f"visual_mode={brief.visual_mode}")

    if mode == "EDIT":
        prompt = _build_edit_prompt(
            scene=scene,
            model_target=model_target,
        )
    elif mode == "TEXT_TO_IMAGE":
        prompt = _build_text_to_image_prompt(
            brief=brief,
            scene=scene,
            content_context=content_context,
            emitted_aspect=emitted_aspect,
        )
    else:
        prompt = _build_composite_prompt(
            brief=brief,
            scene=scene,
            outfit=outfit,
            content_context=content_context,
            emitted_aspect=emitted_aspect,
            model_target=model_target,
            reference_urls=references,
        )

    # Run forbidden-vocab check on USER INPUTS only (scene_description, outfit,
    # content_context). Template phrases like "no beauty filter" / "no bokeh" in
    # the constraints clause are legitimate and must not fail QC.
    user_supplied_text = " ".join(filter(None, [
        brief.scene_description, brief.outfit, brief.content_context,
    ]))
    if _contains_forbidden_vocab(user_supplied_text):
        qc_passed = False
        warnings.append("forbidden_vocabulary_in_user_input")

    return EnhancedVisualPrompt(
        prompt=prompt,
        negative_prompt=_negative_prompt_for_model(model_target),
        aspect_ratio=emitted_aspect,
        reference_image_urls=references,
        requires_reference_image=requires_reference_image,
        mode=mode,
        model_target=model_target,
        reference_quality=reference_quality,
        warnings=_dedupe(warnings),
        qc_passed=qc_passed,
        fallback_applied=fallback_applied,
        platform_target_aspect=platform_target_aspect,
        emitted_aspect=emitted_aspect,
    )


def _build_composite_prompt(
    *,
    brief: VisualPromptBrief,
    scene: str,
    outfit: str,
    content_context: str,
    emitted_aspect: str,
    model_target: VisualModelTarget,
    reference_urls: list[str],
) -> str:
    constraints = _constraints_for_model(model_target, human=True)
    role_block = _reference_role_block(
        reference_urls,
        scene=scene,
        outfit=outfit,
        content_context=content_context,
    )
    # Prefer explicit content_context as the Action line — it's the strongest
    # signal of what the model should depict (overrides scene-keyword heuristics).
    action_line = (
        _as_sentence(content_context).rstrip(".")
        if content_context
        else _action_for_scene(scene, brief.mood)
    )
    # When content_context is used as Action, drop the duplicate Content context line.
    context_line = (
        ""
        if content_context
        else ""
    )
    return "\n\n".join(
        part
        for part in [
            role_block,
            IDENTITY_LOCK,
            _action_independence_line(scene, content_context),
            "\n".join(
                [
                    _opening_line_for_model(model_target),
                    f"Action: {action_line}.",
                    f"Setting: {_setting_for_model(model_target, scene, brief.platform)}.",
                    (
                        f"Composition: {_composition_for_model(model_target, brief.platform)}, "
                        f"{_zoning_for_aspect(emitted_aspect)}, imperfect framing."
                    ),
                    f"Camera: {_camera_for_model(model_target, brief.platform)}.",
                    f"Lighting: {LIGHTING_BY_MOOD[brief.mood]}.",
                    "Color: natural color balance, no cinematic grading.",
                    f"Realism: {_realism_block_for_model(model_target)}, {_scene_clutter(scene)}.",
                    f"Wardrobe: {_wardrobe_for_outfit(outfit)}.",
                    f"Atmosphere: {_atmosphere_for_model(model_target)}.",
                    _quality_line_for_model(model_target, emitted_aspect),
                    context_line.strip(),
                ]
            ).strip(),
            constraints,
            PRESERVE_IDENTITY,
        ]
        if part
    )


def _opening_line_for_model(model_target: VisualModelTarget) -> str:
    if _uses_phone_realism(model_target):
        return (
            "A raw casual snapshot of the same person from Image 1, taken on an "
            "iPhone 11 by a friend during an ordinary Tuesday morning around 2020. "
            "NOT an editorial photo, NOT a portrait session, NOT a fashion shoot, "
            "NOT a stock photo, NOT a social media post. A casual unposed moment "
            "captured mid-action with an older phone."
        )
    return "Editorial photograph of the same person from Image 1."


def _setting_for_model(
    model_target: VisualModelTarget,
    scene: str,
    platform: PlatformKey,
) -> str:
    if _uses_phone_realism(model_target):
        return (
            f"{scene}, ordinary office daylight from a window, practical warm "
            "wood and glass interior, real laptop glare, unstaged desk clutter, "
            "no designed set"
        )
    return _setting_for_scene(scene, platform)


def _composition_for_model(model_target: VisualModelTarget, platform: PlatformKey) -> str:
    if _uses_phone_realism(model_target):
        return (
            "eye-level casual workday frame, subject slightly off-center, "
            "small real-world framing imperfections"
        )
    return COMPOSITION_BY_PLATFORM[platform]


def _camera_for_model(model_target: VisualModelTarget, platform: PlatformKey) -> str:
    if _uses_phone_realism(model_target):
        return (
            "shot on iPhone 11 main wide camera, 26mm equivalent, f/1.8, 12MP "
            "sensor, 2019-era smartphone camera — less computational photography "
            "polish than modern phones, less aggressive sharpening, less "
            "aggressive HDR, slightly softer autofocus, slightly muted colors. "
            "NO portrait mode, NO bokeh, NO beauty filter, NO modern "
            "computational smoothing, NO studio lens compression"
        )
    return CAMERA_BY_PLATFORM[platform]


def _realism_block_for_model(model_target: VisualModelTarget) -> str:
    if _uses_phone_realism(model_target):
        return GPT_IMAGE_REALISM_BLOCK
    return REALISM_BLOCK


def _atmosphere_for_model(model_target: VisualModelTarget) -> str:
    if _uses_phone_realism(model_target):
        return GPT_IMAGE_ATMOSPHERE
    return BRAND_CONSISTENCY


def _quality_line_for_model(model_target: VisualModelTarget, emitted_aspect: str) -> str:
    if _uses_phone_realism(model_target):
        return (
            f"Aspect ratio: {emitted_aspect}. Output MUST feel like a real iPhone 11 "
            "photo from a 2020-era camera roll — slightly muted, slightly noisy, "
            "slightly soft. NOT a polished modern smartphone photo, NOT a generated "
            "image, NOT a studio portrait. If it looks polished or modern, it is wrong."
        )
    return f"Aspect ratio: {emitted_aspect}. Quality: high."


def _edit_quality_line_for_model(model_target: VisualModelTarget) -> str:
    if _uses_phone_realism(model_target):
        return "Output should feel like a real phone camera file, not a generated image."
    return "Quality: high."


def _uses_phone_realism(model_target: VisualModelTarget) -> bool:
    return model_target in {"gpt_image_2", "nano_pro"}


def _build_edit_prompt(
    *,
    scene: str,
    model_target: VisualModelTarget,
) -> str:
    constraints = _constraints_for_model(model_target, human=True).removeprefix("Constraints: ")
    return "\n\n".join(
        [
            "Using the attached image as the base reference.",
            f"CHANGE: {_single_change(scene)}.",
            _edit_preserve_block(scene),
            (
                "CONSTRAINTS: do not alter facial features, do not change identity, "
                "do not regrade colors, do not introduce new shadows or reflections "
                "beyond those naturally cast by the changed element, do not add "
                "accessories, do not change clothing or jewelry, do not alter any "
                "untouched areas outside the requested edit, "
                f"{constraints}"
            ),
            _edit_quality_line_for_model(model_target),
        ]
    )


def _build_text_to_image_prompt(
    *,
    brief: VisualPromptBrief,
    scene: str,
    content_context: str,
    emitted_aspect: str,
) -> str:
    context_line = f"\nContent context: {_as_sentence(content_context)}" if content_context else ""

    # Phase 25.E — conceptual mode tags the prompt as "Conceptual editorial"
    # and adds an explicit NO PEOPLE / NO FACES guard rail (separate from
    # NON_HUMAN_CONSTRAINTS which only forbids identity-leak but still allows
    # incidental human figures).
    is_conceptual = getattr(brief, "visual_mode", "face") == "conceptual"
    headline = (
        "Conceptual editorial photograph — no people, no faces."
        if is_conceptual
        else "Editorial product or environment photograph."
    )
    no_people_block = (
        "STRICT: do not show any human figures, faces, hands, body parts, "
        "or silhouettes. The scene is product/environment-focused only."
    ) if is_conceptual else ""

    parts = [
        "\n".join(
            [
                headline,
                f"Subject: {scene}.",
                f"Setting: {_setting_for_scene(scene, brief.platform)}.",
                (
                    f"Composition: {COMPOSITION_BY_PLATFORM[brief.platform]}, "
                    f"{_zoning_for_aspect(emitted_aspect)}, imperfect framing."
                ),
                "Camera: shot on 50mm f/1.8, natural human-eye perspective.",
                f"Lighting: {LIGHTING_BY_MOOD[brief.mood]}.",
                "Color: natural color balance, no cinematic grading.",
                f"Texture: {_scene_clutter(scene)}.",
                f"Atmosphere: {BRAND_CONSISTENCY}.",
                f"Aspect ratio: {emitted_aspect}. Quality: high.",
                context_line.strip(),
            ]
        ).strip(),
        NON_HUMAN_CONSTRAINTS,
    ]
    if no_people_block:
        parts.append(no_people_block)
    return "\n\n".join(parts)


def _reference_role_block(
    reference_urls: list[str],
    *,
    scene: str,
    outfit: str,
    content_context: str,
) -> str:
    if not reference_urls:
        return ""
    lines = [
        (
            "Image 1 (IDENTITY ANCHOR) - use ONLY for face, identity, "
            "distinguishing marks. Do NOT copy its pose, hand placement, "
            "hair-touching gesture, selfie arm, clothing, background, lighting, "
            "or camera angle."
        )
    ]
    prompt_context = f"{scene} {outfit} {content_context}".lower()
    for index, url in enumerate(reference_urls[1:], start=2):
        role = _reference_role_for_url(url, prompt_context=prompt_context)
        lines.append(f"Image {index} ({role}) - {_reference_role_instruction(role)}")
    lines.append("Do not cross-leak roles between references.")
    return "\n".join(lines)


def _reference_role_for_url(url: str, *, prompt_context: str) -> str:
    text = url.lower()
    workspace_context = _has_any(
        prompt_context,
        ("workspace", "laptop", "dashboard", "office", "product"),
    )
    outfit_context = _has_any(
        prompt_context,
        ("outfit", "full body", "fullbody", "jeans", "walking"),
    )
    warm_context = _has_any(prompt_context, ("cafe", "coffee", "kitchen", "home", "warm"))
    if workspace_context and _has_any(text, ("workspace", "laptop", "dashboard", "office")):
        return "ENVIRONMENT"
    if outfit_context and _has_any(text, ("fullbody", "jeans", "outfit")):
        return "OUTFIT"
    if warm_context and _has_any(text, ("kitchen", "cafe", "coffee", "warm")):
        return "ENVIRONMENT"
    if _has_any(text, ("_34", "three_quarter", "profile", "medium", "fullbody")):
        return "POSE"
    return "IDENTITY SUPPORT"


def _reference_role_instruction(role: str) -> str:
    return {
        "POSE": (
            "use ONLY for body angle, head turn, and natural pose; ignore identity, "
            "wardrobe, background, and lighting."
        ),
        "OUTFIT": (
            "use ONLY for garment cut, fabric, color, and accessories; ignore wearer "
            "identity, pose, and environment."
        ),
        "ENVIRONMENT": (
            "use ONLY for scene, location, lighting mood, and ambient context; ignore "
            "the person, identity, wardrobe, and pose."
        ),
        "STYLE/GRADE": (
            "use ONLY for color grade and overall aesthetic; ignore identity geometry "
            "and scene content."
        ),
        "IDENTITY SUPPORT": (
            "use ONLY to reinforce same-person consistency; ignore pose, hand "
            "placement, gestures, wardrobe, background, and lighting."
        ),
    }.get(
        role,
        "use ONLY for the labeled role; ignore all unrelated visual information.",
    )


def _constraints_for_model(model_target: VisualModelTarget, *, human: bool) -> str:
    if not human:
        return NON_HUMAN_CONSTRAINTS
    if model_target == "gpt_image_2":
        return GPT_IMAGE_CONSTRAINTS
    return NANO_CONSTRAINTS


def _negative_prompt_for_model(model_target: VisualModelTarget) -> str:
    if model_target == "gpt_image_2":
        return GPT_IMAGE_CONSTRAINTS
    return ""


def _model_target_for_slug(model_slug: str) -> VisualModelTarget:
    if model_slug.startswith("openai/") or "gpt-image-2" in model_slug:
        return "gpt_image_2"
    if "nano-banana-2" in model_slug:
        return "nano_banana_2"
    return "nano_pro"


def _dispatch_mode(
    scene: str,
    content_context: str,
    references: list[str],
    subject: str,
) -> VisualPromptMode:
    text = f"{scene} {content_context}".lower()
    edit_markers = (
        "change ",
        "replace ",
        "remove ",
        "add ",
        "make her ",
        "edit ",
    )
    if len(references) == 1 and any(marker in text for marker in edit_markers):
        return "EDIT"
    if not references and subject != "HUMAN":
        return "TEXT_TO_IMAGE"
    return "COMPOSITE"


def _detect_subject(
    scene: str, content_context: str, references: list[str]
) -> Literal[
    "HUMAN",
    "PRODUCT",
]:
    text = f"{scene} {content_context}".lower()
    if references or any(
        token in text for token in ("cansu", "person", "portrait", "founder", "woman", "she ")
    ):
        return "HUMAN"
    return "PRODUCT"


def _emitted_aspect(
    requested_aspect: str,
    *,
    model_target: VisualModelTarget,
) -> tuple[str, str | None]:
    if requested_aspect == "1.91:1" and model_target in {
        "nano_pro",
        "nano_banana_2",
        "gpt_image_2",
    }:
        return "16:9", "aspect_fallback_applied"
    return requested_aspect, None


def _setting_for_scene(scene: str, platform: PlatformKey) -> str:
    lowered = scene.lower()
    if any(token in lowered for token in ("istanbul", "turkey", "turkish", "levent")):
        return f"{scene}, mediterranean soft light, warm wood and glass, no cool blue digital cast"
    if "cafe" in lowered or "coffee" in lowered:
        return f"{scene}, a quiet Karakoy side-street cafe, mid-morning"
    if "kitchen" in lowered:
        return f"{scene}, a sunlit Cihangir apartment kitchen, mid-morning"
    if "rooftop" in lowered:
        return f"{scene}, a Galata rooftop with the Bosphorus softly out of focus"
    if platform in {"linkedin", "medium", "x"}:
        return f"{scene}, a minimalist Levent tech-office floor at 10 in the morning"
    return scene


def _action_for_scene(scene: str, mood: VisualMood) -> str:
    lowered = scene.lower()
    if "dashboard" in lowered or "laptop" in lowered or "screen" in lowered:
        return (
            "reviewing a laptop dashboard mid-thought, both hands naturally near "
            "the keyboard or trackpad"
        )
    if "coffee" in lowered:
        return "pouring filter coffee mid-stream, softly laughing just off-camera"
    if "window" in lowered:
        return "leaning slightly against a sunlit window, gaze just off-camera"
    if mood == "technical":
        return "reviewing a product screen with a small mid-conversation gesture"
    if mood == "warm":
        return "softly laughing in a candid in-between moment"
    return "mid-thought, gaze just off-camera with a calm confident half-smile"


def _scene_clutter(scene: str) -> str:
    lowered = scene.lower()
    if any(token in lowered for token in ("workspace", "office", "dashboard", "laptop", "screen")):
        return DEFAULT_SCENE_CLUTTER
    for key, clutter in SCENE_CLUTTER:
        if key in lowered:
            return clutter
    return DEFAULT_SCENE_CLUTTER


def _wardrobe_for_outfit(outfit: str) -> str:
    if outfit == "smart casual neutral-toned outfit":
        return (
            "quiet-luxury smart-casual outfit in charcoal, ivory, camel, navy, "
            "deep green, cream, or soft taupe; natural fabric texture, minimal jewelry, no logos"
        )
    additions = ["natural fabric texture"]
    lowered = outfit.lower()
    if "minimal jewelry" not in lowered:
        additions.append("minimal jewelry")
    if "no logos" not in lowered and "logo" not in lowered:
        additions.append("no logos")
    return ", ".join([outfit, *additions])


def _zoning_for_aspect(aspect_ratio: str) -> str:
    return {
        "1:1": "balanced negative space on both sides",
        "16:9": "opposite third reserved as negative space for a headline",
        "1.91:1": "right third reserved as negative space for a headline",
        "9:16": "lower third reserved for caption overlay",
        "4:5": "top third reserved for headline",
        "21:9": "wide environmental context",
    }.get(aspect_ratio, "balanced negative space")


def _single_change(scene: str) -> str:
    cleaned = scene.rstrip(".")
    return cleaned if cleaned else "apply the requested single edit"


def _action_independence_line(scene: str, content_context: str) -> str:
    line = ACTION_INDEPENDENCE
    combined = f"{scene} {content_context}".lower()
    if "hair" not in combined:
        line += (
            " If an identity reference shows Cansu touching or holding hair, "
            "ignore that gesture."
        )
    return line


def _edit_preserve_block(scene: str) -> str:
    fields = [
        "face",
        "identity",
        "hair length and color",
        "skin tone",
        "eye direction",
        "expression",
        "hand position",
        "body proportions",
        "pose",
        "clothing",
        "jewelry",
        "background",
        "camera angle",
        "focal length compression",
        "depth of field",
        "lighting direction",
        "color temperature",
        "grain",
        "overall photo aesthetic",
    ]
    lowered = scene.lower()
    if _has_any(lowered, ("background", "environment", "scene", "office", "workspace")):
        fields.remove("background")
    if _has_any(lowered, ("outfit", "wardrobe", "clothing", "shirt", "blazer", "sweater")):
        fields = [field for field in fields if field not in {"clothing", "jewelry"}]
    if _has_any(lowered, ("pose", "gesture", "hand position", "hands", "standing", "sitting")):
        fields = [
            field for field in fields if field not in {"hand position", "body proportions", "pose"}
        ]
    return (
        "PRESERVE: "
        + ", ".join(fields[:-1])
        + f", and {fields[-1]} - identical to the reference."
    )


def _as_sentence(value: str) -> str:
    cleaned = value.strip()
    if cleaned.endswith((".", "!", "?")):
        return cleaned
    return f"{cleaned}."


def _clean_required(value: str, field_name: str) -> str:
    cleaned = _compact(value)
    if not cleaned:
        raise ValueError(f"{field_name} cannot be empty")
    return cleaned


def _strip_forbidden_vocab(value: str | None) -> str:
    cleaned = _compact(value)
    for token in FORBIDDEN_VOCABULARY:
        # Word-boundary match so "retouched" inside "unretouched" is NOT stripped.
        pattern = re.compile(r"\b" + re.escape(token) + r"\b", re.IGNORECASE)
        cleaned = pattern.sub("", cleaned)
    return _compact(cleaned.replace(" ,", ",").replace(",,", ","))


def _contains_forbidden_vocab(value: str) -> bool:
    lowered = (
        value.lower()
        .replace(GPT_IMAGE_CONSTRAINTS.lower(), "")
        .replace(NANO_CONSTRAINTS.lower(), "")
        .replace(NON_HUMAN_CONSTRAINTS.lower(), "")
        .replace("no other people in sharp focus", "")
        .replace("other people in sharp focus", "")
    )
    # Word-boundary match so "retouched" inside "unretouched" doesn't fire.
    return any(
        re.search(r"\b" + re.escape(token.lower()) + r"\b", lowered)
        for token in FORBIDDEN_VOCABULARY
    )


def _has_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _compact(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            deduped.append(value)
    return deduped

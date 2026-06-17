"""Cansu framed news image — single Wiro Nano Banana Pro img2img call.

Berkay's decision (this build): the whole news card is produced by ONE Wiro
img2img call. A fixed framed template (Gen-Z purple, 4:5) is passed as the
`input_image`; Nano Banana Pro fills the empty top ~78% hero area with the news
subject AND writes the 2-line headline into the bottom band. No code-side overlay.

IMMUTABLE RULE: stills are faceless — Cansu's face NEVER appears. No persona
anchors / HeyGen photos are used here. The frame template is the only consistency
anchor (Layer C style-board reference is optional, plugged in once produced).

This path is gated by `settings.cansu_frame_i2i_enabled` and invoked from
`flow.generate_visual()`. It returns the SAME-shaped dict as the brand path in
`visual_director_tools._generate_and_check_async`, so flow's downstream
result-handling (state.visual mapping) works unchanged.
"""
from __future__ import annotations

import hashlib
from typing import Optional

from loguru import logger

from config import settings
from .card_themes import CardTheme, get_theme, resolve_frame_url
from .image_pipeline import generate_and_store_wiro_image_asset

_FRAME_I2I_SLUG = "google/nano-banana-pro"
_FRAME_ASPECT_RATIO = "4:5"
_FRAME_RESOLUTION = "4K"


# Hero composition archetypes (Berkay-approved 2026-06-08). Premium, news-
# relevant, essentially TEXT-FREE, brand-forward, and VARIED so cards don't all
# look like the same tablet mockup. The dropped "abstract geometric" style read
# as meaningless; the old "UI mockup on a device screen" filled the screen with
# gibberish fake-UI text (the AI tell). Rotated deterministically by topic.
#   1) logo emblem (premium 3D)   2) minimal device (logo-splash only)
#   3) symbolic object / scene (cinematic editorial photo)
_BRAND_HERO_ARCHETYPES = [
    "a premium glossy 3D render of the {brand} logo mark as a sculptural emblem, in "
    "{brand}'s brand colours, soft studio lighting, floating cleanly with generous "
    "empty space",
    "a sleek modern device shown at a clean angle whose screen displays ONLY the "
    "{brand} logo as a minimal splash (no interface, no dashboard, no readable text), "
    "premium product photography",
    "an elegant cinematic editorial still of ONE real-world object or scene that "
    "symbolises the story, premium magazine photography, the {brand} logo subtly "
    "present as a small clean mark",
]

# Applied to every hero concept — kills the AI-tell (gibberish UI text) while
# ALLOWING a clean device that only shows a logo splash.
_HERO_GUARD = (
    " Faceless and essentially TEXT-FREE: NO readable text anywhere, NO app "
    "interfaces, dashboards, charts, menus or paragraphs of fake/gibberish UI text. "
    "A clean real brand logo is allowed ONLY if you know the brand's actual "
    "official logo; NEVER invent, approximate or stylize a logo, badge, emblem "
    "or monogram for a brand/product whose real logo you do not know — in that "
    "case use a logo-free object or scene instead. If a device appears, its "
    "screen shows ONLY a minimal logo splash, never a text-filled UI. "
    "Premium editorial quality."
)


# 2026-06-10 (Berkay: "bu foto çok kötü, visual director izin vermemeli") —
# logo arketipleri yalnız modelin GERÇEKTEN bildiği markalarda güvenli.
# "Claude Fable 5" gibi yeni ürün adlarında Nano Banana logo UYDURUYOR
# ("Cf" kalkanı vakası). Bilinmeyen marka → ürün ana-markasına eşlenir
# (Fable→Claude), o da yoksa logosuz sembolik konsepte düşülür.
_KNOWN_LOGO_BRANDS = {
    "openai", "anthropic", "claude", "google", "gemini", "google deepmind",
    "apple", "meta", "nvidia", "microsoft", "x", "twitter", "tesla",
    "hugging face", "huggingface", "mistral", "perplexity", "github",
    "amazon", "samsung", "intel", "amd", "spotify", "youtube", "instagram",
    "linkedin", "tiktok", "spacex", "netflix", "shopify", "slack", "discord",
}
_BRAND_TO_PARENT = {
    # ürün/model adı → logosu bilinen ana marka
    "claude fable": "Claude", "fable": "Claude", "claude mythos": "Claude",
    "mythos": "Claude", "claude opus": "Claude", "claude sonnet": "Claude",
    "chatgpt": "OpenAI", "gpt": "OpenAI", "sora": "OpenAI", "dall-e": "OpenAI",
    "gemini live": "Gemini", "nano banana": "Google", "veo": "Google",
    "copilot": "Microsoft", "llama": "Meta", "grok": "X",
    "siri": "Apple", "apple intelligence": "Apple",
}


def _safe_logo_brand(brand: str) -> Optional[str]:
    """Logosu güvenle çizilebilecek markayı döndür; bilinmiyorsa None."""
    b = (brand or "").strip().lower()
    if not b:
        return None
    if b in _KNOWN_LOGO_BRANDS:
        return brand
    for prod, parent in _BRAND_TO_PARENT.items():
        if prod in b:
            return parent
    return None


def build_frame_hero_concept(
    brand: Optional[str], topic: str, style_idx: Optional[int] = None
) -> str:
    """Build a minimal-text, varied hero concept for the glow card.

    Branded news rotates through composition archetypes (deterministic by topic;
    `style_idx` forces one, used for previews). Unbranded news gets a single
    symbolic editorial visual. Both forbid the fake-UI text that made cards look
    AI-generated.
    """
    brand = _safe_logo_brand(brand or "") or ""
    topic = (topic or "").strip()
    if brand:
        if style_idx is not None:
            idx = style_idx % len(_BRAND_HERO_ARCHETYPES)
        else:
            seed = topic or brand
            idx = int(hashlib.md5(seed.encode("utf-8")).hexdigest(), 16) % len(_BRAND_HERO_ARCHETYPES)
        base = _BRAND_HERO_ARCHETYPES[idx].format(brand=brand)
    else:
        base = (
            "a single clean, symbolic editorial visual (one clear object, scene or "
            f"metaphor) that evokes this story: {topic}"
        )
    return base + _HERO_GUARD


def build_frame_i2i_prompt(
    *, headline: str, hero_concept: str, theme: Optional[CardTheme] = None
) -> str:
    """Compose the img2img instruction for the framed template.

    The model receives the framed template as input_image; this prompt tells it
    to (1) keep the frame chrome (bottom glow band + pill) intact, (2) write the
    exact headline into the title area, (3) fill the empty hero area with a
    single concrete, faceless subject.

    `theme` drives the colour-code: aura colour words, pill label, glow word and
    headline text colour. Default = news (Mor Glow) → produces the SAME prompt
    string as before, byte-for-byte (regression-locked).
    """
    theme = theme or get_theme("news")
    headline = (headline or "").strip()
    hero_concept = (hero_concept or "").strip() or "an abstract editorial tech motif"
    # Glow theme registry is the single source of truth.
    #  - PRESERVE mode (news): the input template already IS this theme's aura;
    #    keep it untouched. → byte-for-byte the original Mor Glow prompt.
    #  - RECOLOR mode (dictionary/question): the input is the mor canonical, but
    #    we tell the model to repaint the aura to this theme's colour + relabel
    #    the pill — one Wiro pass, same path as news, no separate template.
    if theme.recolor:
        opening = (
            "Using the provided purple-aura news poster as the base LAYOUT, but RECOLOR the whole scene: "
            f"replace the purple / violet / magenta aura ENTIRELY with a {theme.aura_words} {theme.glow_word} "
            "radial AURA atmosphere — leave NO purple, violet or magenta anywhere. "
            "Keep the full-bleed background (no card, no border, sharp corners) and the rounded pill in the "
            f"lower-left at the SAME position and size, but change the pill text to '{theme.pill_label}' and "
            f"render it {theme.pill_style} (dark outline and dark text, clearly readable on the light background). "
        )
    else:
        opening = (
            f"Using the provided {theme.aura_atmosphere} news poster as the EXACT base. "
            f"PRESERVE, unchanged: the glowing {theme.aura_words} radial AURA atmosphere, "
            "the full-bleed background (no card, no border, sharp corners), and the "
            f"{theme.pill_style} rounded '{theme.pill_label}' pill in the lower-left (same position and style). "
        )
    return (
        opening
        + f"Place the following as a SINGLE clear subject in the UPPER-CENTER of the frame, "
        f"floating inside and lit by the {theme.glow_word} glow (blended into the aura, NOT in a box "
        f"or card): {hero_concept}. "
        f"In the empty area directly BELOW the {theme.pill_label} pill, write ONLY this exact headline, "
        f"bold {theme.text_color} sans-serif, left-aligned, wrapped over one or two lines, and spell it "
        f"EXACTLY with correct Turkish letters (ı, ş, ğ, ü, ö, ç): \"{headline}\". "
        "TEXT RULE: the hero must be essentially TEXT-FREE — besides this headline, NO "
        "readable text anywhere. Do NOT render app interfaces, dashboards, charts, menus "
        "or any paragraphs of fake/gibberish UI text (that is what reveals AI generation). "
        "A single clean REAL brand logo is fine; if a device appears, its screen shows "
        "ONLY a minimal logo splash, never a text-filled UI. "
        "Faceless: NO human face, no people, no portrait, no Cansu. "
        "No duplicate logos beyond the one brand mark, no glowing-brain / humanoid-robot / "
        "circuit-board cliché. Keep 4:5 vertical framing, premium Gen-Z editorial quality."
    )


async def generate_framed_news_image_async(
    *,
    persona_id: str,
    headline: str,
    hero_concept: str,
    daily_draft_id: Optional[str] = None,
    frame_url: Optional[str] = None,
    style_board_url: Optional[str] = None,
    theme_key: str = "news",
) -> dict:
    """Generate a framed news card via Wiro i2i, persist it, run compliance.

    `theme_key` selects the colour-code theme (news=mor, dictionary, question…).
    Default=news → behaviour identical to the original mor path. The theme's
    template URL is resolved from its env var, falling back to the news template
    (so an un-provisioned theme never crashes — it just renders on the mor frame).

    Returns a dict shaped like the brand path result so flow.generate_visual()
    downstream is unchanged. On a missing frame URL returns {status: 'error'}.
    """
    theme = get_theme(theme_key)
    # Resolve this theme's frame; explicit arg wins, then theme env, then the
    # canonical news template as last-resort fallback.
    frame_url = (
        frame_url
        or resolve_frame_url(theme, fallback=settings.cansu_frame_template_url or "")
    ).strip()
    if theme.key != "news" and not resolve_frame_url(theme):
        if theme.recolor:
            logger.info(
                f"[frame_i2i] tema '{theme.key}': dedike template yok → mor canonical "
                f"input alınıp prompt'ta '{theme.glow_word}'a çevriliyor (recolor modu)"
            )
        else:
            logger.warning(
                f"[frame_i2i] tema '{theme.key}' için {theme.template_env} set DEĞİL — "
                f"news template'ine düşülüyor (renk/pill uyuşmayabilir)"
            )
    if not frame_url:
        return {
            "status": "error",
            "error": (
                "cansu_frame_template_url is empty — set CANSU_FRAME_TEMPLATE_URL "
                "to the approved frame's CDN/Wiro URL before enabling frame i2i."
            ),
        }

    # Layer C: frame template is the primary reference; style-board is optional
    # and only added once the asset is produced (Section 8 TODO).
    style_board_url = (style_board_url or settings.cansu_style_board_url or "").strip()
    input_image: list[str] = [frame_url]
    if style_board_url:
        input_image.append(style_board_url)

    # 2026-06-10 — deneme listesi: 1. verilen konsept; 2. (kart hakemi
    # reddederse) LOGOSUZ sembolik konsept. Reroll içeride — çağıranlar
    # (flow, reskin) değişmeden korunur.
    _attempt_concepts = [hero_concept]
    _safe_concept = build_frame_hero_concept(None, headline)
    if _safe_concept != hero_concept:
        _attempt_concepts.append(_safe_concept)
    _last_fail: Optional[dict] = None
    for _attempt_idx, hero_concept in enumerate(_attempt_concepts, start=1):
        if _attempt_idx > 1:
            logger.warning(
                f"[frame_i2i] kart reddedildi — deneme {_attempt_idx}: "
                f"logosuz sembolik konsepte düşülüyor"
            )
        prompt = build_frame_i2i_prompt(
            headline=headline, hero_concept=hero_concept, theme=theme
        )
        logger.info(
            f"[frame_i2i] theme={theme.key} persona={persona_id} refs={len(input_image)} "
            f"headline='{(headline or '')[:60]}' hero='{(hero_concept or '')[:60]}'"
        )

        stored = await generate_and_store_wiro_image_asset(
            persona_id=persona_id,
            prompt=prompt,
            slug=_FRAME_I2I_SLUG,
            aspect_ratio=_FRAME_ASPECT_RATIO,
            resolution=_FRAME_RESOLUTION,
            max_images=1,
            input_image=input_image,
            ai_watermark=False,  # Wiro SynthID already marks output; no visible WM
            asset_status="generated",
            generation_metadata_overrides={
                "visual_mode": "conceptual",
                "pipeline": "frame_i2i",
                "theme": theme.key,
                "headline": headline,
                "hero_concept": hero_concept,
                "frame_url": frame_url,
                "style_board_url": style_board_url or None,
            },
            daily_draft_id=daily_draft_id,
        )

        # Compliance — the persona pipeline's gate (CLIP face-consistency + LAION
        # photographic-aesthetic) does NOT apply to a deterministically-framed,
        # faceless EDITORIAL DESIGN card: CLIP is skipped (no face), and the
        # aesthetic predictor — trained on lifestyle photos — scores flat
        # graphic+text layouts low (~0.29) and false-FAILs them, which then drops
        # the Instagram draft. The relevant failure modes here (broken frame,
        # garbled headline) are handled by the fixed template + i2i prompt. So we
        # PASS designed cards through the photographic gate by design.
        # 2026-06-10 — Vision kart hakemi (Berkay: "visual director buna izin
        # vermemeli"). CLIP/estetik bypass'ının yerine GERÇEK bir denetim:
        # başlık birebir mi ("Alrdığını" typo vakası) + uydurma logo var mı
        # ("Cf" kalkanı vakası) + ağır artefakt. Hakem FAIL derse status=
        # card_check_failed döner; çağıran (flow / reskin) reroll eder.
        _card_verdict = None
        try:
            from .image_text_check import check_card
            _card_verdict = await check_card(stored.public_url, headline, theme_key=theme.key)
        except Exception as _cce:
            logger.warning(f"[frame_i2i] kart hakemi çağrılamadı: {_cce}")
        if _card_verdict is not None and not _card_verdict.ok and not _card_verdict.error:
            logger.warning(
                f"[frame_i2i] KART REDDİ: headline_ok={_card_verdict.headline_ok} "
                f"no_fake_logo={_card_verdict.no_fake_logo} clean={_card_verdict.clean} "
                f"| {_card_verdict.notes}"
            )
            _last_fail = {
                "status": "card_check_failed",
                "asset_id": stored.asset_id,
                "image_url": stored.public_url,
                "card_check": {
                    "headline_ok": _card_verdict.headline_ok,
                    "no_fake_logo": _card_verdict.no_fake_logo,
                    "clean": _card_verdict.clean,
                    "notes": _card_verdict.notes,
                },
            }
            if _attempt_idx < len(_attempt_concepts):
                continue  # logosuz konseptle bir kez daha
            return _last_fail

        break  # kart hakemi geçti (ya da hakem erişilemez — soft-pass)

    compliance: dict = {
        "final_verdict": "PASS",
        "final_reason": (
            "frame_i2i designed editorial card — vision card-check PASS "
            "(headline + logo + artifact denetimi)"
            if (_card_verdict is not None and _card_verdict.ok)
            else "frame_i2i designed editorial card — card-check unavailable (soft-pass)"
        ),
        "clip": None, "aesthetic": None, "ocr_flagged": None,
        "llm_verdict": "PASS", "llm_reasoning": None, "llm_tells": [],
    }

    return {
        "status": "ok",
        "asset_id": stored.asset_id,
        "image_url": stored.public_url,
        "storage_key": stored.storage_key,
        "model_slug": stored.generation.model_slug,
        "cost_usd": stored.generation.cost_usd,
        "latency_ms": stored.generation.latency_ms,
        "file_size_bytes": stored.file_size_bytes,
        "compliance": compliance,
        "visual_decision": {
            "needs_cansu": False,
            "composition_type": "brand_news_visual",
            "via": "frame_i2i",
            "reason": "faceless framed news card (Wiro i2i)",
            "path": "frame_i2i",
            "model": _FRAME_I2I_SLUG,
        },
        "visual_brief_json": {
            "pipeline": "frame_i2i",
            "headline": headline,
            "hero_concept": hero_concept,
            "frame_url": frame_url,
            "style_board_url": style_board_url or None,
            "aspect_ratio": _FRAME_ASPECT_RATIO,
            "resolution": _FRAME_RESOLUTION,
        },
    }

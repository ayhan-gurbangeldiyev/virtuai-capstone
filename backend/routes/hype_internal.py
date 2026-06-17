"""Internal endpoint for Hype Crew worker.

Auth: X-Cron-Secret header (same pattern as /auto-refresh).
Difference from user-facing /v2/generate/tweet:
- Auth: cron secret (no user JWT)
- Body: account_id required (user_id resolved from connected_accounts)
- Side effect: does NOT write to generations table — Hype Crew owns hype_runs/hype_stages.

This endpoint is ADDITIVE: zero changes to existing routes.
"""
import os
import hmac
import logging
from typing import Optional, Literal

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


class HypeGenerateRequest(BaseModel):
    account_id: str = Field(..., description="connected_accounts.id")
    etki: Literal["patlassin", "konustursun", "ogretsin", "iz_biraksin", "shitpost"]
    karakter: Literal["uzman", "otorite", "iceriden", "mentalist", "haberci"]
    yapi: str = "dogal"
    # 2026-06-11: "thread" eklendi — devto long-form, storm'un yıkıcı 1300c
    # enforcement'ına girmesin (newline-silen truncation makaleyi bozuyordu).
    uzunluk: Literal["micro", "punch", "spark", "storm", "thread"] = "punch"
    acilis: str = "otomatik"
    bitis: str = "otomatik"
    derinlik: str = "standart"
    additional_context: Optional[str] = None
    is_ultra: bool = False
    language: str = "auto"
    # Phase 20 — multi-platform content type. Defaults to 'tweet' for backcompat.
    # Maps to TypeHype build_final_prompt_v3 content_type parameter.
    content_type: Literal["tweet", "linkedin", "blog", "instagram", "youtube"] = "tweet"
    # Phase 25.C — voice rotation. None → builder_v3 falls back to pre-Phase-25
    # behaviour (1st person Cansu witty). Strategist picks from content_type.
    voice_mode: Optional[Literal["first_person_witty", "third_person_neutral", "hybrid"]] = None
    # 2026-06-08 — explicit model override hook so the WRITER can run on
    # Sonnet 4.6 while gate/editor/dedup stay on Gemini Flash. When set,
    # bypasses get_model_config()'s is_ultra/etki branches. Format must
    # match OpenRouter slugs (e.g. "anthropic/claude-sonnet-4.6").
    model_override: Optional[str] = None
    # 2026-06-08 — when set, the route runs the source-input cleaner
    # (handle normalization + source_tweets union) on additional_context
    # before injection. Default False to preserve the legacy paths
    # (style-lab UI, etc.); flow.py opts in for cron drafts.
    clean_source_input: bool = False


# ─ 2026-06-08 source-input cleaner helpers ───────────────────────────
# Used when clean_source_input=True. The writer's grounding fails on
# raw X handles ("Wjmzbmr1" appearing as a person's name) and on
# trends.raw_content truncation (~97 chars vs ~700 in source_tweets).
# The faithfulness gate already unions source_tweets at approve time
# (commit a96e9e3); this is the symmetric fix on the writer side.

# Reuse the canonical map already maintained by the gate so we have
# a single source of truth for "what entity does this X handle mean".
def _x_handle_to_entity_name() -> dict[str, str]:
    """Lazy fetch — handles dependency on hype_crew at runtime, not
    import time, since the hype_crew tree may live in a sibling path."""
    import sys
    for p in ("/opt/hype-crew", "../hype_crew", "../../hype_crew"):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        from tools.faithfulness_gate import _URL_ACCOUNT_TO_ENTITY  # type: ignore
        return dict(_URL_ACCOUNT_TO_ENTITY)
    except Exception:
        return {}


_HANDLE_RE = __import__("re").compile(r"@([A-Za-z0-9_]{2,15})")


def _normalize_source_handles(text: str) -> str:
    """Replace @handles with the canonical entity name when known; strip
    the @ otherwise. Stops draft-side from emitting bare "Wjmzbmr1" as
    a person's name. Preserves the rest of the text verbatim."""
    if not text:
        return text
    handle_map = _x_handle_to_entity_name()

    def _sub(m):
        handle = m.group(1)
        ent = handle_map.get(handle.lower())
        if ent:
            return ent
        # Unknown handle → drop the @ symbol so the LLM treats it as a
        # plain word, not a person.
        return handle

    return _HANDLE_RE.sub(_sub, text)


def _enrich_source_with_tweets_union(additional_context: str) -> str:
    """If `additional_context` references a trend (via the
    'trend_id_for_gate_lookup:' sentinel that flow.py emits in the
    cron path), union the trend's source_tweets[].text fields into
    the KAYNAK METİN block.

    Default impl is a pass-through — flow.py is expected to do the
    union itself BEFORE posting (mirroring how it now builds the gate
    source_raw_content). Keeping a hook here for future centralization.
    """
    return additional_context or ""


class HypeGenerateResponse(BaseModel):
    content: str
    tokens_used: int
    model_used: str
    etki: str
    karakter: str
    uzunluk: str


def _verify_cron_secret(x_cron_secret: Optional[str]) -> None:
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not x_cron_secret or not hmac.compare_digest(expected, x_cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")


@router.post("/generate-tweet", response_model=HypeGenerateResponse)
async def hype_generate_tweet(
    request: HypeGenerateRequest,
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
):
    """Generate a tweet for Hype Crew worker.

    Reuses existing build_final_prompt_v3 + generate_with_openrouter.
    No DB writes (Hype Crew tracks its own runs in hype_runs/hype_stages).
    """
    _verify_cron_secret(x_cron_secret)

    # Lazy imports — avoid pulling backend server graph at module load
    from server import (
        supabase, _get_brand_voice, get_model_config, generate_with_openrouter,
    )
    from prompts.builder_v3 import build_final_prompt_v3

    # Resolve account → user_id
    acc = (
        supabase.table("connected_accounts")
        .select("user_id, username, platform")
        .eq("id", request.account_id)
        .limit(1)
        .execute()
    )
    if not acc.data:
        raise HTTPException(status_code=404, detail="account not found")
    user_id = acc.data[0]["user_id"]

    brand_voice = await _get_brand_voice(user_id) or {}
    # 2026-06-08 — writer model override (Sonnet 4.6 for writer step
    # while gate/editor stay on Gemini Flash). When set, this builds
    # a new model_config with the override slug; otherwise the legacy
    # is_ultra/etki branches decide.
    model_config = get_model_config(
        request.etki, request.is_ultra,
        model_override=request.model_override,
    )
    if request.model_override:
        logger.info(
            f"hype_generate_tweet: writer model = {model_config.get('model')} "
            f"(override active; gate/editor stay on Flash)"
        )

    # 2026-06-08 — source-input cleaner: strip @handles, resolve known
    # X handles to canonical entity names. Only when the caller opts in
    # (cron path; legacy style-lab UI keeps verbatim handles).
    if request.clean_source_input and request.additional_context:
        before_len = len(request.additional_context)
        cleaned = _normalize_source_handles(request.additional_context)
        cleaned = _enrich_source_with_tweets_union(cleaned)
        if cleaned != request.additional_context:
            logger.info(
                f"hype_generate_tweet: source cleaner ran "
                f"(len {before_len}→{len(cleaned)})"
            )
        # Mutate request so downstream prompt builders see the cleaned text.
        request = request.model_copy(update={"additional_context": cleaned})

    # Resolve active style profile (Phase 17.2)
    # If a style profile is set, we hand the prompt off to
    # build_style_enhanced_prompt() — it emits an authored "Stil DNA" with
    # hard capitalization rules read from style_fingerprint (e.g. Semih's
    # `starts_uppercase_pct: 94` becomes an explicit "cümle başları büyük
    # harf" instruction). In that path we deliberately DROP brand_voice
    # to avoid conflicts: the style profile is the single source of truth.
    style_system_prompt: Optional[str] = None
    style_profile_name: Optional[str] = None
    example_tweets: Optional[list] = None
    try:
        cfg = (
            supabase.table("hype_account_config")
            .select("active_style_profile_id")
            .eq("account_id", request.account_id)
            .limit(1)
            .execute()
        )
        style_profile_id = (cfg.data or [{}])[0].get("active_style_profile_id")
        if style_profile_id:
            prof = (
                supabase.table("style_profiles")
                .select("*")
                .eq("id", style_profile_id)
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if prof.data:
                profile = prof.data[0]
                style_profile_name = profile.get("name")
                fingerprint = profile.get("style_fingerprint") or {}
                viral_patterns = profile.get("viral_patterns") or {}

                source_ids = profile.get("source_ids") or []
                if source_ids:
                    examples = (
                        supabase.table("source_tweets")
                        .select("content")
                        .in_("source_id", source_ids)
                        .order("created_at", desc=True)
                        .limit(20)
                        .execute()
                    )
                    example_tweets = [t["content"] for t in (examples.data or []) if t.get("content")]

                from prompts.style_prompt_v2 import build_style_enhanced_prompt
                from services.style_constraints import StyleConstraints
                constraints = StyleConstraints(fingerprint, viral_patterns)
                style_system_prompt = build_style_enhanced_prompt(
                    content_type=request.content_type,
                    topic=request.additional_context or "",
                    style_fingerprint=fingerprint,
                    viral_patterns=viral_patterns,
                    constraints=constraints,
                    reference_tweets=example_tweets or [],
                    persona=request.karakter,
                    tone=request.yapi,
                    length=request.uzunluk,
                    language=request.language,
                    is_apex=request.is_ultra,
                    additional_context=request.additional_context,
                    # Phase 34 — voice_mode-aware DNA gating
                    voice_mode=request.voice_mode,
                )
                logger.info(
                    f"hype_generate_tweet: style profile '{style_profile_name}' injected "
                    f"({len(style_system_prompt or '')} chars, {len(example_tweets or [])} examples) — brand_voice overridden"
                )
    except Exception as e:
        logger.warning(f"hype_generate_tweet: style profile resolve failed (continuing without): {e}")
        style_system_prompt = None

    if style_system_prompt:
        # Style profile wins on word choice / cadence — but we still inject a
        # voice_mode "Tonal Çerçeve" header BEFORE the style block so 3rd-person
        # journalism mode (model_launch etc.) overrides Cansu's 1st-person
        # default when content_type warrants it. Phase 25.C.
        if request.voice_mode:
            try:
                from prompts.voice_modes import get_voice_mode_block
                vm_block = get_voice_mode_block(request.voice_mode)
            except Exception:
                vm_block = None
            if vm_block:
                system_prompt = vm_block + "\n\n" + style_system_prompt
            else:
                system_prompt = style_system_prompt
        else:
            system_prompt = style_system_prompt
    else:
        # Fallback: generic V3 prompt with user's brand_voice + voice_mode frame.
        system_prompt = build_final_prompt_v3(
            content_type=request.content_type,
            topic=request.additional_context or "",
            persona=request.karakter,
            tone=request.yapi,
            length=request.uzunluk,
            language=request.language,
            is_apex=request.is_ultra,
            additional_context=request.additional_context,
            brand_voice=brand_voice,
            voice_mode=request.voice_mode,  # Phase 25.C
        )

    # Phase 35.1.E + F + G — TTS rules for video/youtube/reel
    # Order (prepended to existing system_prompt, EARLIEST = highest priority):
    #   [GROUNDING rules]    ← Phase 35.1.G — source fidelity, highest priority
    #   [HOOK+CLOSE rules]   ← Phase 35.1.F — pattern enforcement
    #   [TTS Plan C rules]   ← Phase 35.1.E — Türkçeleştirme + cümle yapısı
    #   [style/voice prompt] ← existing Cansu DNA + Strategist brief
    # Grounding is FIRST: if a script breaks source fidelity it doesn't matter
    # if hook+close+TTS are pretty.
    try:
        from prompts.voice_modes import (
            should_apply_tts_rules,
            get_tts_video_rules_block,
            get_tts_video_hook_close_rules,
            get_tts_video_grounding_rules,
            get_repetition_avoidance_rules,
        )
        if should_apply_tts_rules(request.content_type):
            grounding = get_tts_video_grounding_rules()
            hook_close = get_tts_video_hook_close_rules()
            tts_rules = get_tts_video_rules_block()
            system_prompt = (
                grounding + "\n\n"
                + hook_close + "\n\n"
                + tts_rules + "\n\n"
                + system_prompt
            )
            logger.info(
                f"hype_generate_tweet: TTS_VIDEO_GROUNDING + HOOK_CLOSE + SCRIPT_RULES injected "
                f"(content_type={request.content_type}, "
                f"+{len(grounding) + len(hook_close) + len(tts_rules)} chars)"
            )
        # Phase 35.3 — Repetition avoidance applies to ALL content types
        # (twitter / linkedin / blog / instagram / youtube). Inject AFTER
        # voice block so it has the final say on banned vocabulary.
        repetition = get_repetition_avoidance_rules()
        system_prompt = system_prompt + "\n\n" + repetition
        logger.info(
            f"hype_generate_tweet: REPETITION_AVOIDANCE injected "
            f"(+{len(repetition)} chars)"
        )
    except Exception as e:
        logger.warning(f"hype_generate_tweet: prompt rules injection failed (continuing): {e}")

    try:
        contents, tokens = await generate_with_openrouter(
            system_prompt=system_prompt,
            user_prompt="İçeriği üret.",
            model_config=model_config,
            variants=1,
            user_id=None,  # bypass per-user token budget for system runs
            uzunluk=request.uzunluk,
        )
    except Exception as e:
        logger.error(f"hype_generate_tweet OpenRouter error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"generation failed: {type(e).__name__}")

    return HypeGenerateResponse(
        content=contents[0] if contents else "",
        tokens_used=tokens,
        model_used=model_config["model"],
        etki=request.etki,
        karakter=request.karakter,
        uzunluk=request.uzunluk,
    )

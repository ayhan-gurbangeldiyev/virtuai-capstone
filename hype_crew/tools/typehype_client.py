"""TypeHype V3 generation client — calls existing /api/internal/generate-tweet.

This replaces Hype Crew's custom Writer agent. We reuse TypeHype's battle-tested
build_final_prompt_v3 + generate_with_openrouter (with brand voice DNA, persona,
tone, hook patterns, etc.) instead of duplicating prompt engineering.

Cost: typically $0.001-0.01 per call (depends on model — normal=gemini-flash,
ultra=claude-sonnet, shitpost=mistral).
"""
import os
from typing import Optional, Literal

import httpx
from loguru import logger

from config import settings


# TypeHype API base URL — override via env
TYPEHYPE_API_URL = os.environ.get(
    "TYPEHYPE_API_URL",
    "https://api.typehype.io",  # production default
).rstrip("/")

CRON_SECRET = os.environ.get("CRON_SECRET", "").strip()


ContentType = Literal["tweet", "linkedin", "blog", "instagram", "youtube"]


def generate_tweet_via_typehype(
    account_id: str,
    etki: Literal["patlassin", "konustursun", "ogretsin", "iz_biraksin", "shitpost"],
    karakter: Literal["uzman", "otorite", "iceriden", "mentalist", "haberci"],
    uzunluk: Literal["micro", "punch", "spark", "storm", "thread"] = "punch",
    yapi: str = "dogal",
    additional_context: Optional[str] = None,
    is_ultra: bool = False,
    language: str = "auto",
    content_type: ContentType = "tweet",
    voice_mode: Optional[str] = None,  # Phase 25.C: first_person_witty | third_person_neutral | hybrid
    model_override: Optional[str] = None,  # 2026-06-08: Sonnet 4.6 for writer only
    clean_source_input: bool = False,  # 2026-06-08: strip @handles + canonicalize
    timeout: float = 90.0,
) -> dict:
    """Call TypeHype's internal /generate-tweet endpoint.

    Phase 20: `content_type` lets the same endpoint emit tweet | linkedin |
    blog | instagram | youtube content from one shared brand-voice / style
    profile path.

    Phase 25.C: `voice_mode` rotates Cansu's voice between 1st-person witty,
    3rd-person neutral journalism, or hybrid. Backend builder_v3 picks the
    Tonal Çerçeve block accordingly. None → inherits pre-Phase-25 default
    (1st person witty).

    Returns dict with keys: content, tokens_used, model_used, etki, karakter, uzunluk.
    Raises RuntimeError on failure (caller decides retry/skip).
    """
    if not CRON_SECRET:
        raise RuntimeError(
            "CRON_SECRET env var missing — required to call TypeHype internal endpoint"
        )

    url = f"{TYPEHYPE_API_URL}/api/internal/generate-tweet"
    headers = {
        "X-Cron-Secret": CRON_SECRET,
        "Content-Type": "application/json",
        "User-Agent": "HypeCrew/1.0",
    }
    body = {
        "account_id": account_id,
        "etki": etki,
        "karakter": karakter,
        "yapi": yapi,
        "uzunluk": uzunluk,
        "additional_context": additional_context,
        "is_ultra": is_ultra,
        "language": language,
        "content_type": content_type,
    }
    # Only include voice_mode when explicitly set — keeps the request body
    # backward-compatible with older backend versions that don't recognise it.
    if voice_mode:
        body["voice_mode"] = voice_mode
    # 2026-06-08 — opt-in fields. Backend silently ignores unknown body
    # fields when present (Pydantic ignores extras), but older deploys
    # may reject — so we only emit when explicitly requested.
    if model_override:
        body["model_override"] = model_override
    if clean_source_input:
        body["clean_source_input"] = True

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, json=body)
            r.raise_for_status()
            data = r.json()
            logger.info(
                f"[TypeHype] generated {len(data.get('content',''))} chars "
                f"({data.get('tokens_used',0)} tokens, {data.get('model_used','?')})"
            )
            return data
    except httpx.HTTPStatusError as e:
        body_text = e.response.text[:300]
        msg = f"TypeHype API {e.response.status_code}: {body_text}"
        logger.error(f"[TypeHype] {msg}")
        raise RuntimeError(msg) from e
    except httpx.HTTPError as e:
        logger.exception(f"[TypeHype] HTTP error: {e}")
        raise RuntimeError(f"TypeHype HTTP error: {type(e).__name__}: {str(e)[:200]}") from e

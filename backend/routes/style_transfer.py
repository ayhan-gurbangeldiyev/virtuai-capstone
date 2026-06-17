"""
Style Transfer Route — "Başka Biri Gibi Yaz"
POST /api/style-transfer
"""

import json
import logging
import httpx
import os
import re
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from openai import OpenAI
from middleware.auth import require_auth
from services.access_control import accessible_owner_ids
from middleware.active_account import get_active_account
from middleware.rate_limit import rate_limit
from middleware.token_tracker import check_token_budget, record_token_usage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["style-transfer"])


class StyleTransferRequest(BaseModel):
    source_text: Optional[str] = None
    source_url: Optional[str] = None
    target_profile_id: str
    variant_count: int = 3


def _extract_tweet_id(url_or_id: str) -> Optional[str]:
    patterns = [
        r'(?:twitter|x)\.com/.+/status/(\d+)',
        r'^(\d{10,})$',
    ]
    for p in patterns:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return None


async def _fetch_tweet_text(url: str) -> dict:
    tweet_id = _extract_tweet_id(url)
    if not tweet_id:
        raise HTTPException(status_code=400, detail="Geçersiz tweet URL'si")

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(
            f"https://api.fxtwitter.com/status/{tweet_id}",
            headers={"User-Agent": "TypeHype/1.0"}
        )
        if resp.status_code == 200:
            data = resp.json()
            tweet = data.get("tweet")
            if tweet:
                author = tweet.get("author", {})
                return {
                    "text": tweet.get("text", ""),
                    "author_name": author.get("name", ""),
                    "author_username": author.get("screen_name", ""),
                }
    raise HTTPException(status_code=404, detail="Tweet bulunamadı")


def _get_supabase():
    from server import supabase
    return supabase


@router.post("/style-transfer")
async def style_transfer(req: StyleTransferRequest, _=Depends(rate_limit), user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """
    Kaynak metni hedef kişinin tarzıyla yeniden yaz.
    2 aşamalı: fikir çıkar -> hedef tarzla yeniden inşa et.
    """
    from prompts.style_transfer import build_extract_idea_prompt, build_style_transfer_prompt
    from embed_tweets import get_similar_tweets

    supabase = _get_supabase()

    # 1. Kaynak metni al
    source_text = req.source_text or ""
    tweet_meta = None

    if req.source_url:
        tweet_meta = await _fetch_tweet_text(req.source_url)
        source_text = tweet_meta["text"]

    if not source_text.strip():
        raise HTTPException(status_code=400, detail="Kaynak metin veya URL gerekli")

    # 2. Hedef profili çek (IDOR fix: sahiplik kontrolü ekle)
    profile = supabase.table("style_profiles") \
        .select("*") \
        .eq("id", req.target_profile_id) \
        .in_("user_id", accessible_owner_ids(user.id)) \
        .eq("account_id", account_id) \
        .execute()

    if not profile.data:
        raise HTTPException(status_code=404, detail="Stil profili bulunamadı")

    profile_data = profile.data[0]
    fingerprint = profile_data.get("style_fingerprint", {})
    example_tweets = profile_data.get("example_tweets", [])
    source_ids = profile_data.get("source_ids", [])

    # 3. Few-shot: embedding similarity ile en alakalı tweetleri çek
    few_shot_tweets = []
    if source_ids:
        try:
            similar = get_similar_tweets(source_text, source_ids, limit=5)
            few_shot_tweets = similar
        except Exception as e:
            logger.warning(f"Similar tweets fetch failed: {e}")

    # Fallback: example_tweets kullan
    if not few_shot_tweets and example_tweets:
        few_shot_tweets = example_tweets[:5]

    # 4. OpenAI client
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    client = OpenAI(api_key=openai_api_key)
    model = os.environ.get("MODEL_CONTENT", "gpt-4o")

    # Token budget check
    check_token_budget(user.id)

    # 5. Aşama 1: Saf fikir çıkar
    extract_prompt = build_extract_idea_prompt(source_text)

    extract_resp = None
    try:
        extract_resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Sen bir metin analiz uzmanısın. Sadece JSON döndür."},
                {"role": "user", "content": extract_prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        core_idea = json.loads(extract_resp.choices[0].message.content)
    except Exception as e:
        logger.error(f"Idea extraction failed: {e}")
        core_idea = {
            "core_idea": source_text[:200],
            "key_data": [],
            "emotional_tone": "bilgilendirici",
            "target_audience": "genel",
        }

    # 6. Aşama 2: Style transfer
    transfer_prompt = build_style_transfer_prompt(
        core_idea=core_idea,
        style_fingerprint=fingerprint,
        few_shot_tweets=few_shot_tweets,
        variant_count=req.variant_count,
        source_text=source_text,
        example_tweets=example_tweets,
    )

    transfer_resp = None
    try:
        transfer_resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Sen bir sosyal medya ghost writer'ısın. İstenen formatta JSON döndür."},
                {"role": "user", "content": transfer_prompt},
            ],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        raw = transfer_resp.choices[0].message.content
        result = json.loads(raw)
    except Exception as e:
        logger.error(f"Style transfer generation failed: {e}")
        raise HTTPException(status_code=500, detail="İçerik üretilemedi")

    # 7. Varyantları parse et
    variants_raw = result.get("variants", [])
    variants = []
    for i, v in enumerate(variants_raw):
        content = v.get("content", v) if isinstance(v, dict) else str(v)
        approach = v.get("approach", "") if isinstance(v, dict) else ""
        variants.append({
            "content": content,
            "approach": approach,
            "character_count": len(content),
            "variant_index": i,
        })

    # 8. DB'ye kaydet
    target_name = fingerprint.get("twitter_display_name", "") or fingerprint.get("twitter_username", "")
    topic_label = f"Style Transfer: {target_name}"
    if tweet_meta:
        topic_label = f"@{tweet_meta['author_username']} \u2192 {target_name} tarz\u0131"

    generation_record = {
        "user_id": user.id,
        "topic": topic_label,
        "type": "style-transfer",
        "persona": "ghost",
        "tone": "clone",
        "variants": variants,
        "mode": "style-transfer",
        "metadata": {
            "source_text": source_text[:500],
            "source_url": req.source_url,
            "target_profile_id": req.target_profile_id,
            "target_name": target_name,
            "core_idea": core_idea,
            "tweet_author": tweet_meta.get("author_username") if tweet_meta else None,
        },
    }

    generation_id = None
    try:
        gen_result = supabase.table("generations").insert(generation_record).execute()
        generation_id = gen_result.data[0]["id"] if gen_result.data else None
    except Exception as e:
        logger.error(f"Generation save failed: {e}")

    # 9. Token usage
    total_tokens = 0
    if extract_resp and extract_resp.usage:
        total_tokens += extract_resp.usage.total_tokens
    if transfer_resp and transfer_resp.usage:
        total_tokens += transfer_resp.usage.total_tokens

    try:
        record_token_usage(user.id, total_tokens, model)
    except Exception:
        pass

    return {
        "success": True,
        "generation_id": generation_id,
        "variants": variants,
        "core_idea": core_idea,
        "source_text": source_text[:200],
        "target_profile": {
            "id": req.target_profile_id,
            "name": target_name,
            "username": fingerprint.get("twitter_username", ""),
            "avatar_url": fingerprint.get("avatar_url", ""),
        },
        "tweet_author": tweet_meta if tweet_meta else None,
        "token_usage": total_tokens,
    }


@router.get("/style-transfer/profiles")
async def list_transfer_profiles(user=Depends(require_auth), account_id: str = Depends(get_active_account)):
    """Kullanıcının stil profillerini listele (style transfer dropdown için)."""
    supabase = _get_supabase()

    profiles = supabase.table("style_profiles") \
        .select("id, name, style_fingerprint, tweet_count, updated_at") \
        .in_("user_id", accessible_owner_ids(user.id)).eq("account_id", account_id) \
        .order("updated_at", desc=True) \
        .execute()

    HIDDEN_IDS = {"dd1a9608-1441-4b72-bf28-83e11d4c5a60", "f3935ab1-3728-4b79-9fa9-fb895a2b4903"}
    result = []
    for p in (profiles.data or []):
        if p.get("id") in HIDDEN_IDS:
            continue
        fp = p.get("style_fingerprint", {})
        result.append({
            "id": p["id"],
            "name": p.get("name", ""),
            "username": fp.get("twitter_username", ""),
            "display_name": fp.get("twitter_display_name", ""),
            "avatar_url": fp.get("avatar_url", ""),
            "tweet_count": p.get("tweet_count", 0),
        })

    return {"profiles": result}

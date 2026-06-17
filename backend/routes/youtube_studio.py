"""
YouTube Studio — Kanal, Video, Yorum, Rakip, Thumbnail, Fikir, Niş, Trend, Keyword, TransFlow analiz endpoint'leri.
Prefix: /youtube-studio
"""
import os
import json
import base64
import logging
import httpx
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from openai import OpenAI

from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from services.youtube_api import YouTubeAPIService, get_youtube_service

from prompts.youtube_studio.channel_analysis import get_channel_analysis_prompt
from prompts.youtube_studio.video_analysis import get_video_analysis_prompt
from prompts.youtube_studio.comment_analysis import get_comment_categorization_prompt, get_comment_summary_prompt
from prompts.youtube_studio.competitor_analysis import get_competitor_analysis_prompt
from prompts.youtube_studio.thumbnail_analysis import get_thumbnail_analysis_prompt
from prompts.youtube_studio.idea_generator import get_idea_generator_prompt
from prompts.youtube_studio.niche_analysis import get_niche_analysis_prompt
from prompts.youtube_studio.keyword_trends import get_keyword_trends_prompt
from prompts.youtube_studio.transflow import get_transflow_prompt

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/youtube-studio", tags=["youtube-studio"])

# ── Helpers ──────────────────────────────────────────────

def _openai():
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise HTTPException(500, "OpenAI API key not configured")
    return OpenAI(api_key=key)


def _ai_json(system: str, user: str = "Analiz et.", model: str = "gpt-4o", temperature: float = 0.7) -> dict:
    """Call OpenAI and parse JSON response."""
    client = _openai()
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    text = resp.choices[0].message.content
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code blocks
        import re
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            return json.loads(m.group(1))
        raise HTTPException(500, "AI yanıtı JSON olarak parse edilemedi")


def _ai_vision(image_b64: str, prompt: str) -> dict:
    """Call GPT-4o Vision with base64 image."""
    client = _openai()
    resp = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.7,
        response_format={"type": "json_object"},
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "high"}},
            ]},
        ],
    )
    return json.loads(resp.choices[0].message.content)


def _calc_channel_metrics(channel: dict, videos: list) -> dict:
    subs = channel.get("subscriberCount", 0) or 1
    total_views = channel.get("viewCount", 0)
    video_count = channel.get("videoCount", 0)

    views = [v.get("viewCount", 0) for v in videos]
    likes = [v.get("likeCount", 0) for v in videos]
    comments = [v.get("commentCount", 0) for v in videos]

    avg_views = sum(views) / len(views) if views else 0
    avg_likes = sum(likes) / len(likes) if likes else 0
    avg_comments = sum(comments) / len(comments) if comments else 0

    engagement_rate = ((avg_likes + avg_comments) / avg_views * 100) if avg_views > 0 else 0
    views_to_subs = (avg_views / subs * 100) if subs > 0 else 0

    # Upload frequency
    if len(videos) >= 2:
        dates = []
        for v in videos:
            try:
                dates.append(datetime.fromisoformat(v["publishedAt"].replace("Z", "+00:00")))
            except:
                pass
        if len(dates) >= 2:
            dates.sort(reverse=True)
            diffs = [(dates[i] - dates[i+1]).days for i in range(len(dates)-1)]
            avg_days = sum(diffs) / len(diffs) if diffs else 7
            if avg_days <= 1:
                freq = "Günlük"
            elif avg_days <= 3:
                freq = f"Haftada {7/avg_days:.0f} video"
            elif avg_days <= 7:
                freq = "Haftalık"
            elif avg_days <= 14:
                freq = "İki haftada bir"
            elif avg_days <= 30:
                freq = "Aylık"
            else:
                freq = f"~{avg_days:.0f} günde bir"
        else:
            freq = "Belirsiz"
    else:
        freq = "Belirsiz"

    # Performance score
    score = 0
    score += min(25, engagement_rate * 5)  # max 25
    score += min(25, views_to_subs * 0.5)  # max 25
    score += min(25, min(subs / 1000, 25))  # max 25
    if freq in ("Günlük", "Haftalık") or "Haftada" in freq:
        score += 15
    elif freq == "İki haftada bir":
        score += 10
    else:
        score += 5
    score = min(100, max(0, score))

    return {
        "subscriber_count": subs,
        "total_views": total_views,
        "video_count": video_count,
        "avg_views": avg_views,
        "avg_likes": avg_likes,
        "avg_comments": avg_comments,
        "engagement_rate": round(engagement_rate, 2),
        "upload_frequency": freq,
        "performance_score": round(score),
        "views_to_subs_ratio": round(views_to_subs, 1),
    }


def _calc_video_metrics(video: dict) -> dict:
    views = video.get("viewCount", 0) or 1
    likes = video.get("likeCount", 0)
    comments = video.get("commentCount", 0)

    like_rate = (likes / views * 100)
    comment_rate = (comments / views * 100)
    engagement_rate = like_rate + comment_rate

    # Score
    score = 0
    score += min(30, like_rate * 7.5)
    score += min(20, comment_rate * 50)
    score += min(30, min(views / 10000, 30))
    score += min(20, engagement_rate * 4)
    score = min(100, max(0, score))

    if score >= 80:
        label = "Viral"
    elif score >= 60:
        label = "Çok İyi"
    elif score >= 40:
        label = "İyi"
    elif score >= 20:
        label = "Ortalama"
    else:
        label = "Düşük"

    return {
        "views": views,
        "likes": likes,
        "comments": comments,
        "engagement_rate": round(engagement_rate, 2),
        "like_rate": round(like_rate, 2),
        "comment_rate": round(comment_rate, 4),
        "performance_score": round(score),
        "label": label,
    }


# ── Request Models ───────────────────────────────────────

class ChannelAnalyzeRequest(BaseModel):
    url: str
    language: str = "tr"

class VideoAnalyzeRequest(BaseModel):
    url: str
    language: str = "tr"

class CommentAnalyzeRequest(BaseModel):
    url: str
    limit: int = Field(default=50, ge=10, le=200)
    language: str = "tr"

class CompetitorAnalyzeRequest(BaseModel):
    my_channel: str
    competitor_channels: List[str] = Field(..., max_length=5)
    language: str = "tr"

class IdeaGenerateRequest(BaseModel):
    mode: str = Field(default="topic", pattern="^(topic|channel|trending)$")
    topic: Optional[str] = None
    category: Optional[str] = None
    count: int = Field(default=10, ge=3, le=20)
    channel_url: Optional[str] = None
    language: str = "tr"

class NicheAnalyzeRequest(BaseModel):
    interests: List[str]
    skills: List[str]
    lifestyle: str = ""
    time_availability: str = ""
    target_audience: str = ""
    content_language: str = "tr"
    language: str = "tr"

class KeywordAnalyzeRequest(BaseModel):
    niche: str
    keywords: Optional[List[str]] = None
    language: str = "tr"

class TranslateRequest(BaseModel):
    type: str = Field(..., pattern="^(title|description|tags|subtitle)$")
    source_text: str
    source_lang: str = "tr"
    target_lang: str = "en"
    language: str = "tr"


# ── Endpoints ────────────────────────────────────────────

@router.post("/channel/analyze")
async def channel_analyze(req: ChannelAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        channel = yt.get_channel(req.url)
        channel_id = channel.get("id", yt.extract_channel_id(req.url))
        videos = yt.get_channel_videos(channel_id, limit=30)
        metrics = _calc_channel_metrics(channel, videos)

        prompt = get_channel_analysis_prompt(channel, videos, metrics, req.language)
        ai = _ai_json(prompt)

        return {
            "success": True,
            "channel": channel,
            "metrics": metrics,
            "ai_analysis": ai,
            "videos_analyzed": len(videos),
            "videos": sorted(videos, key=lambda x: int(x.get("viewCount", 0) or 0), reverse=True)[:10],
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Channel analyze error: {e}")
        raise HTTPException(500, f"Kanal analizi sırasında hata: {str(e)}")


@router.post("/video/analyze")
async def video_analyze(req: VideoAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        video_id = yt.extract_video_id(req.url)
        if not video_id:
            raise ValueError("Geçersiz video URL'si")

        video = yt.get_video(video_id)
        metrics = _calc_video_metrics(video)

        prompt = get_video_analysis_prompt(video, metrics, req.language)
        ai = _ai_json(prompt)

        return {
            "success": True,
            "video": video,
            "metrics": metrics,
            "ai_analysis": ai,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Video analyze error: {e}")
        raise HTTPException(500, f"Video analizi sırasında hata: {str(e)}")


@router.post("/comments/analyze")
async def comments_analyze(req: CommentAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        video_id = yt.extract_video_id(req.url)
        if not video_id:
            raise ValueError("Geçersiz video URL'si")

        comments = yt.get_video_comments(video_id, limit=req.limit)
        if not comments:
            return {"success": True, "message": "Bu videoda yorum bulunamadı", "comments": [], "summary": None}

        # Batch categorize (20 per batch)
        batch_size = 20
        all_categorized = []
        for i in range(0, len(comments), batch_size):
            batch = comments[i:i+batch_size]
            prompt = get_comment_categorization_prompt(batch, req.language)
            result = _ai_json(prompt)
            cats = result.get("categorized_comments", [])
            all_categorized.extend(cats)

        # Summary
        summary_prompt = get_comment_summary_prompt(all_categorized, len(comments), req.language)
        summary = _ai_json(summary_prompt)

        return {
            "success": True,
            "total_comments": len(comments),
            "categorized_comments": all_categorized,
            "summary": summary,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Comment analyze error: {e}")
        raise HTTPException(500, f"Yorum analizi sırasında hata: {str(e)}")


@router.post("/competitor/analyze")
async def competitor_analyze(req: CompetitorAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        if len(req.competitor_channels) > 5:
            raise ValueError("En fazla 5 rakip kanal ekleyebilirsiniz")

        yt = get_youtube_service()

        # My channel
        my_ch = yt.get_channel(req.my_channel)
        my_id = my_ch.get("id", yt.extract_channel_id(req.my_channel))
        my_vids = yt.get_channel_videos(my_id, limit=20)
        my_metrics = _calc_channel_metrics(my_ch, my_vids)

        # Competitors
        competitors = []
        for url in req.competitor_channels:
            try:
                ch = yt.get_channel(url)
                ch_id = ch.get("id", yt.extract_channel_id(url))
                vids = yt.get_channel_videos(ch_id, limit=20)
                m = _calc_channel_metrics(ch, vids)
                competitors.append({"channel": ch, "metrics": m})
            except Exception as e:
                logger.warning(f"Competitor fetch failed for {url}: {e}")
                competitors.append({"channel": {"title": url, "error": str(e)}, "metrics": {}})

        prompt = get_competitor_analysis_prompt(my_ch, my_metrics, competitors, req.language)
        ai = _ai_json(prompt)

        return {
            "success": True,
            "my_channel": {"channel": my_ch, "metrics": my_metrics},
            "competitors": competitors,
            "ai_analysis": ai,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Competitor analyze error: {e}")
        raise HTTPException(500, f"Rakip analizi sırasında hata: {str(e)}")


@router.post("/thumbnail/analyze")
async def thumbnail_analyze(
    image: Optional[UploadFile] = File(None),
    youtube_url: Optional[str] = Form(None),
    language: str = Form("tr"),
    user=Depends(require_auth),
    _rl=Depends(rate_limit),
):
    try:
        image_b64 = None

        if image:
            content = await image.read()
            image_b64 = base64.b64encode(content).decode()
        elif youtube_url:
            yt = get_youtube_service()
            video_id = yt.extract_video_id(youtube_url)
            if not video_id:
                raise ValueError("Geçersiz YouTube URL'si")

            # Try maxresdefault, then hqdefault
            thumb_url = None
            async with httpx.AsyncClient() as client:
                for quality in ["maxresdefault", "hqdefault", "mqdefault"]:
                    url = f"https://img.youtube.com/vi/{video_id}/{quality}.jpg"
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 1000:
                        image_b64 = base64.b64encode(resp.content).decode()
                        thumb_url = url
                        break

            if not image_b64:
                raise ValueError("Thumbnail indirilemedi")
        else:
            raise ValueError("image dosyası veya youtube_url gerekli")

        prompt = get_thumbnail_analysis_prompt(language)
        ai = _ai_vision(image_b64, prompt)

        result = {
            "success": True,
            "ai_analysis": ai,
        }
        if youtube_url:
            result["thumbnail_url"] = thumb_url
        return result

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error(f"Thumbnail analyze error: {e}")
        raise HTTPException(500, f"Thumbnail analizi sırasında hata: {str(e)}")


@router.post("/ideas/generate")
async def ideas_generate(req: IdeaGenerateRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        channel_data = None
        trending_data = None

        if req.mode == "channel" and req.channel_url:
            ch = yt.get_channel(req.channel_url)
            ch_id = ch.get("id", yt.extract_channel_id(req.channel_url))
            vids = yt.get_channel_videos(ch_id, limit=10)
            channel_data = {**ch, "recent_videos": vids}
        elif req.mode == "trending":
            trending_data = yt.get_trending(category=req.category)

        prompt = get_idea_generator_prompt(
            mode=req.mode, topic=req.topic, category=req.category,
            count=req.count, channel_data=channel_data,
            trending_data=trending_data, language=req.language,
        )
        ai = _ai_json(prompt)

        return {"success": True, **ai}
    except Exception as e:
        logger.error(f"Idea generate error: {e}")
        raise HTTPException(500, f"Fikir üretimi sırasında hata: {str(e)}")


@router.post("/niche/analyze")
async def niche_analyze(req: NicheAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        prompt = get_niche_analysis_prompt(
            req.interests, req.skills, req.lifestyle,
            req.time_availability, req.target_audience,
            req.content_language, req.language,
        )
        ai = _ai_json(prompt)
        return {"success": True, **ai}
    except Exception as e:
        logger.error(f"Niche analyze error: {e}")
        raise HTTPException(500, f"Niş analizi sırasında hata: {str(e)}")


@router.get("/trends")
async def get_trends(region: str = "TR", category: str = None, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        trending = yt.get_trending(region=region, category=category)
        return {"success": True, "region": region, "count": len(trending), "videos": trending}
    except Exception as e:
        logger.error(f"Trends error: {e}")
        raise HTTPException(500, f"Trend verisi alınamadı: {str(e)}")


@router.get("/trends/rising")
async def get_rising_trends(region: str = "TR", language: str = "tr", user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        yt = get_youtube_service()
        trending = yt.get_trending(region=region)

        lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."
        titles = "\n".join(f"- {v.get('title', '')}" for v in trending[:30])
        current_year = datetime.now().year

        prompt = f"""Sen bir YouTube trend analisti ve içerik keşif uzmanısın.
{lang_instruction}

{region} bölgesinde şu anda trending olan videolar:
{titles}

Bu trend verilerine dayanarak, {current_year} yılında yükselen konuları ve fırsatları analiz et.

Yanıtını SADECE JSON formatında ver:
{{
    "rising_topics": [
        {{"topic": "Konu", "trend_strength": "strong/moderate/emerging", "content_opportunity": "Fırsat açıklaması", "estimated_peak": "Tahmini zirve zamanı"}}
    ],
    "declining_topics": ["Düşüşteki konu 1"],
    "content_opportunities": [
        {{"idea": "Video fikri", "why_now": "Neden şimdi", "urgency": "high/medium/low"}}
    ],
    "regional_insights": "Bölgesel trend özeti",
    "prediction": "{current_year} için tahmin"
}}"""

        ai = _ai_json(prompt)
        return {"success": True, "region": region, **ai}
    except Exception as e:
        logger.error(f"Rising trends error: {e}")
        raise HTTPException(500, f"Yükselen trend analizi sırasında hata: {str(e)}")


@router.post("/keywords/analyze")
async def keywords_analyze(req: KeywordAnalyzeRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        prompt = get_keyword_trends_prompt(req.niche, req.keywords, req.language)
        ai = _ai_json(prompt)
        return {"success": True, **ai}
    except Exception as e:
        logger.error(f"Keyword analyze error: {e}")
        raise HTTPException(500, f"Keyword analizi sırasında hata: {str(e)}")


@router.post("/translate")
async def translate(req: TranslateRequest, user=Depends(require_auth), _rl=Depends(rate_limit)):
    try:
        prompt = get_transflow_prompt(req.type, req.source_text, req.source_lang, req.target_lang, req.language)
        ai = _ai_json(prompt)
        return {"success": True, **ai}
    except Exception as e:
        logger.error(f"Translate error: {e}")
        raise HTTPException(500, f"Çeviri sırasında hata: {str(e)}")

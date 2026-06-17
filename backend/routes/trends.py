"""Trend takip ve trend bazlı içerik üretim route'ları.

GET /api/trends - Trend listesi (kategori filtreli, is_visible=true default)
POST /api/trends/refresh - Trend yenileme (gerçek RSS + GPT-4o analiz)
POST /api/trends/auto-refresh - Cron job endpoint (secret header ile korunan)
GET /api/trends/categories - Kategori listesi
GET /api/trends/{id} - Trend detayı
POST /api/trends/{id}/generate - Trend'den içerik üret
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Header, Request, BackgroundTasks
from middleware.auth import require_auth
from middleware.rate_limit import rate_limit
from middleware.active_account import get_active_account
from routes.admin import _verify_admin
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
import json
import os
import logging

import hmac
import time
import asyncio
from services.trend_relevance import post_filter as trend_post_filter

# Cron endpoint rate limiting — prevent hammering even with valid secret
_cron_last_call: dict[str, float] = {}
_cron_lock = asyncio.Lock()
_CRON_MIN_INTERVAL = 30  # seconds between calls


async def _cron_rate_check(endpoint: str):
    """Reject cron calls that come too fast (async-safe)."""
    async with _cron_lock:
        now = time.time()
        last = _cron_last_call.get(endpoint, 0)
        if now - last < _CRON_MIN_INTERVAL:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Wait {int(_CRON_MIN_INTERVAL - (now - last))}s."
            )
        _cron_last_call[endpoint] = now

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/trends", tags=["trends"])


class TrendRefreshRequest(BaseModel):
    """Trend yenileme isteği."""
    category: Optional[str] = None


class TrendGenerateRequest(BaseModel):
    """Trend'den içerik üretme isteği."""
    platform: str = "twitter"
    format: Optional[str] = None
    language: str = "auto"
    additional_context: Optional[str] = None


class GeneratedContent(BaseModel):
    """Üretilen içerik."""
    content: str
    variant_index: int = 0
    character_count: int = 0


class GenerationResponse(BaseModel):
    """İçerik üretim yanıtı."""
    success: bool
    variants: List[GeneratedContent]
    generation_id: Optional[str] = None
    error: Optional[str] = None


def get_supabase():
    """Get Supabase client from server module."""
    from server import supabase
    return supabase


SINCE_DELTAS = {
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


# Niche -> Trend keyword mapping (OR semantics)
NICHE_KEYWORDS = {
    "ai": ["AI", "yapay zeka", "machine learning", "LLM", "GPT", "deep learning", "OpenAI", "Anthropic", "model"],
    "saas": ["SaaS", "subscription", "cloud", "B2B", "ARR", "churn"],
    "startup": ["startup", "girişim", "funding", "VC", "seed", "YC"],
    "marketing": ["marketing", "pazarlama", "SEO", "growth", "conversion"],
    "crypto": ["crypto", "kripto", "Bitcoin", "Ethereum", "blockchain", "Web3", "DeFi"],
    "ecommerce": ["e-ticaret", "ecommerce", "marketplace", "Shopify"],
    "design": ["tasarım", "design", "UI", "UX", "Figma"],
    "dev": ["developer", "yazılım", "GitHub", "open source", "framework", "API"],
    "data": ["data", "veri", "analytics", "SQL", "pipeline"],
    "content": ["içerik", "content", "creator", "influencer", "viral"],
    "video": ["video", "YouTube", "streaming"],
    "gaming": ["gaming", "oyun", "esports", "Steam"],
    "finance": ["finans", "borsa", "yatırım", "investment", "ekonomi"],
    "health": ["sağlık", "health", "wellness", "biotech"],
    "fitness": ["fitness", "spor", "antrenman"],
    "food": ["yemek", "food", "restoran", "gastronomi"],
    "travel": ["seyahat", "travel", "turizm"],
    "education": ["eğitim", "education", "kurs", "online learning"],
    "music": ["müzik", "music", "Spotify"],
    "fashion": ["moda", "fashion", "stil"],
    "photography": ["fotoğraf", "photography", "kamera"],
    "realestate": ["emlak", "real estate", "konut"],
    "law": ["hukuk", "KVKK", "GDPR", "regülasyon"],
    "hr": ["HR", "işe alım", "hiring", "remote work"],
    "sustainability": ["sürdürülebilirlik", "iklim", "ESG"],
    "politics": ["politika", "seçim", "gündem"],
    "science": ["bilim", "science", "araştırma", "uzay", "NASA"],
    "automotive": ["otomotiv", "EV", "Tesla", "elektrikli"],
    "parenting": ["ebeveyn", "çocuk", "parenting"],
    "pets": ["evcil", "kedi", "köpek"],
    "diy": ["DIY", "kendin yap", "maker"],
    "motivation": ["motivasyon", "kişisel gelişim", "mindset"],
    "books": ["kitap", "book", "okuma"],
    "cinema": ["sinema", "film", "dizi", "Netflix"],
    "art": ["sanat", "galeri", "sergi"],
    "news": ["haber", "son dakika", "breaking"],
    "security": ["güvenlik", "siber", "hack", "malware"],
    "nocode": ["no-code", "low-code", "n8n", "Zapier", "automation"],
    "freelance": ["freelance", "uzaktan", "remote"],
    "community": ["topluluk", "community", "Discord"],
}


def _passes_trend_relevance_guard(trend: dict) -> bool:
    """Post-AI quality gate for all trends.

    Uses the multi-dimensional relevance engine to validate
    trend quality before serving to users.
    """
    ai_score = (trend or {}).get("score", 0) or 0

    # Hard floor: nothing below 60 ever reaches the frontend
    if ai_score < 60:
        return False

    # High-score trends from AI always pass (AI already validated)
    if ai_score >= 70:
        return True

    # For 60-69 range, run deterministic relevance check
    return trend_post_filter(trend, min_score=25.0)


def _get_niche_keywords(user_id: str, sb) -> list:
    """Fetch user niches and expand to keyword list."""
    try:
        result = sb.table("user_settings").select("niches").eq("user_id", user_id).limit(1).execute()
        if not result.data or not result.data[0].get("niches"):
            return []
        keywords = []
        for niche in result.data[0]["niches"]:
            keywords.extend(NICHE_KEYWORDS.get(niche, []))
        return keywords
    except Exception:
        return []


@router.get("")
async def list_trends(
    category: Optional[str] = Query(None),
    since: Optional[str] = Query("48h", description="6h, 24h, 48h, 7d, 30d, or all"),
    show_hidden: bool = Query(False, description="Show hidden (low-score) trends"),
    archived: bool = Query(False, description="Show archived trends"),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    sort: Optional[str] = Query("score", description="score or date"),
    search: Optional[str] = Query(None, description="Search in topic/summary"),
    niche_filter: bool = Query(False, description="Filter by user niches"),
    user=Depends(require_auth),
):
    """Trend listesi. Default olarak sadece is_visible=true olanları döner."""
    try:
        sb = get_supabase()
        order_col = "published_at" if sort == "date" else "score"
        query = sb.table("trends").select("*").order(order_col, desc=True)

        if not show_hidden:
            query = query.eq("is_visible", True)

        if archived:
            query = query.eq("is_archived", True)
        else:
            query = query.or_("is_archived.is.null,is_archived.eq.false")

        if category:
            # Case-insensitive category mapping (includes legacy aliases)
            cat_map = {
                "ai": "AI", "dev": "Dev", "tech": "Dev",  # tech → Dev
                "design": "Design", "crypto": "Crypto",
                "startup": "Startup", "marketing": "Marketing",
                "business": "Business", "science": "Science",
                "lifestyle": "Lifestyle", "education": "Education",
                "entertainment": "Entertainment",
                "news": "News", "gündem": "News", "gundem": "News",  # gündem → News
            }
            mapped = cat_map.get(category.lower(), category)
            query = query.eq("category", mapped)

        if since and since != "all" and since in SINCE_DELTAS:
            cutoff = (datetime.now(timezone.utc) - SINCE_DELTAS[since]).isoformat()
            query = query.gte("created_at", cutoff)

        # Full-text search
        if search and len(search.strip()) >= 2:
            safe_q = search.strip()[:100].replace("%", "").replace("_", "")
            query = query.or_(f"topic.ilike.%{safe_q}%,summary.ilike.%{safe_q}%")

        # Over-fetch to compensate for post-filter guard
        fetch_limit = int(limit * 1.5) + 5
        if offset > 0:
            query = query.range(offset, offset + fetch_limit - 1)
        else:
            query = query.limit(fetch_limit)

        result = query.execute()
        trends = [t for t in (result.data or []) if _passes_trend_relevance_guard(t)][:limit]

        # Score decay: 12 saatten sonra saat basina -2 puan (max -30)
        now = datetime.now(timezone.utc)
        for t in trends:
            pub = t.get("published_at") or t.get("created_at")
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(str(pub).replace("Z", "+00:00"))
                    age_h = (now - pub_dt).total_seconds() / 3600
                    if age_h > 12:
                        penalty = min(int((age_h - 12) * 2), 30)
                        t["score"] = max(0, (t.get("score") or 0) - penalty)
                except (ValueError, TypeError):
                    pass
        # Filter out trends that decayed below 60
        trends = [t for t in trends if t.get("score", 0) >= 60]
        # Re-sort after decay if sorting by score
        if sort != "date":
            trends.sort(key=lambda t: t.get("score", 0), reverse=True)

        # Niche filtering (OR: trend matches ANY user niche keyword)
        if niche_filter:
            niche_kws = _get_niche_keywords(user.id, sb)
            if niche_kws:
                niche_kws_lower = [kw.lower() for kw in niche_kws]
                def matches_niche(t):
                    t_kws = [k.lower() for k in (t.get("keywords") or [])]
                    if any(nk in tk or tk in nk for nk in niche_kws_lower for tk in t_kws):
                        return True
                    topic_lower = (t.get("topic") or "").lower()
                    return any(nk in topic_lower for nk in niche_kws_lower)
                filtered = [t for t in trends if matches_niche(t)]
                if len(filtered) < 3:
                    filtered.extend([t for t in trends if t not in filtered][:max(0, 5 - len(filtered))])
                trends = filtered
        
        return {"trends": trends}
    except Exception as e:
        logger.error(f"Trends list error: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu")


@router.get("/health")
async def trends_health():
    """Public health endpoint — no auth required."""
    try:
        sb = get_supabase()
        now = datetime.now(timezone.utc)
        last_24h = (now - timedelta(hours=24)).isoformat()
        last_1h = (now - timedelta(hours=1)).isoformat()

        # Trend counts
        total = sb.table("trends").select("id", count="exact").execute()
        recent = sb.table("trends").select("id", count="exact").gte("created_at", last_24h).execute()
        very_recent = sb.table("trends").select("id", count="exact").gte("created_at", last_1h).execute()
        latest = sb.table("trends").select("created_at").order("created_at", desc=True).limit(1).execute()

        # RSS feed health
        active_feeds = sb.table("rss_feeds").select("id", count="exact").eq("is_active", True).execute()
        disabled_feeds = sb.table("rss_feeds").select("id", count="exact").eq("is_active", False).execute()

        total_count = total.count if hasattr(total, "count") and total.count else len(total.data or [])
        recent_count = recent.count if hasattr(recent, "count") and recent.count else len(recent.data or [])
        very_recent_count = very_recent.count if hasattr(very_recent, "count") and very_recent.count else len(very_recent.data or [])
        active_count = active_feeds.count if hasattr(active_feeds, "count") and active_feeds.count else len(active_feeds.data or [])
        disabled_count = disabled_feeds.count if hasattr(disabled_feeds, "count") and disabled_feeds.count else len(disabled_feeds.data or [])

        latest_ts = latest.data[0]["created_at"] if latest.data else None

        status = "healthy"
        if recent_count == 0:
            status = "warning"
        if very_recent_count == 0 and recent_count < 5:
            status = "degraded"

        return {
            "status": status,
            "timestamp": now.isoformat(),
            "trends": {
                "total": total_count,
                "last_24h": recent_count,
                "last_1h": very_recent_count,
                "latest_at": latest_ts,
            },
            "rss_feeds": {
                "active": active_count,
                "disabled": disabled_count,
            },
        }
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return {"status": "error", "error": str(e)[:100]}


@router.post("/archive-old")
async def archive_old_trends(user=Depends(require_auth)):
    """48 saatten eski trendleri arşivle."""
    _verify_admin(user)
    sb = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    result = sb.table("trends").update({"is_archived": True}).lt("created_at", cutoff).eq("is_archived", False).execute()
    count = len(result.data) if result.data else 0
    return {"archived": count, "cutoff": cutoff}


@router.post("/refresh")
async def refresh_trends(request: Optional[TrendRefreshRequest] = None, user=Depends(require_auth)):
    """Trend'leri yenile - RSS + Twitter + GPT-4o analizi."""
    _verify_admin(user)
    try:
        from services.trend_engine import trend_engine
        # FIX (2026-06-14): refresh_all() argümansız — include_twitter_search kwarg'ı
        # imzada YOK, TypeError veriyordu (admin /trends/refresh patlıyordu).
        result = await trend_engine.refresh_all()

        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Trend yenileme başarısız"))

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trends refresh error: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu")


async def _send_pipeline_alert(message: str):
    """Telegram'a pipeline alert gönder (fail-loud)."""
    import httpx as _httpx
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_ALERT_CHAT_ID", "8128240790")
    if not bot_token:
        logger.warning(f"PIPELINE ALERT (no bot token): {message}")
        return
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": f"🚨 TypeHype Pipeline Alert\n\n{message}", "parse_mode": "HTML"},
            )
    except Exception as e:
        logger.error(f"Alert send failed: {e}")


async def _run_trend_refresh():
    """Background trend refresh with fail-loud alerts. v3: batch + radar, no keyword search."""
    from services.trend_engine import trend_engine
    import traceback

    try:
        result = await trend_engine.refresh_all()

        # ─── FAIL-LOUD: Twitter pipeline health check ───
        twitter_items = result.get("twitter_items", 0)
        trends_saved = result.get("trends_saved", 0)

        if twitter_items == 0:
            await _send_pipeline_alert(
                f"⚠️ Pipeline 0 sinyal döndü!\n"
                f"Batch + Radar sonuç yok.\n"
                f"Trends saved: {trends_saved}\n"
                f"XQuik API veya quota sorunu olabilir."
            )

        if trends_saved == 0:
            await _send_pipeline_alert(
                f"🔴 Hiç trend kaydedilemedi!\n"
                f"Twitter: {twitter_items}\n"
                f"GPT analiz veya Supabase bağlantısı patlıyor olabilir."
            )

        logger.info(f"Trend refresh complete: {result}")
        return result

    except Exception as e:
        # Limit error detail — don't leak internal paths/secrets in alerts
        safe_error = str(e)[:200].replace(os.environ.get("SUPABASE_SERVICE_KEY", "NONE")[:8], "***")
        error_msg = f"Trend refresh failed: {safe_error}"
        logger.error(error_msg)
        await _send_pipeline_alert(error_msg)
        raise


@router.post("/process-signals")
async def process_signals(
    background_tasks: BackgroundTasks,
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
    batch_size: int = Query(50, le=200),
):
    """Process pending raw_signals through AI pipeline.

    Reads pending signals from raw_signals table, analyzes with GPT,
    upserts trends, and generates content drafts for high-score trends.
    Protected by CRON_SECRET header (same as auto-refresh).
    """
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not x_cron_secret or not hmac.compare_digest(expected, x_cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    await _cron_rate_check("process-signals")

    try:
        from services.trend_engine import trend_engine
        result = await trend_engine.process_raw_signals(batch_size=batch_size)
        return result
    except Exception as e:
        logger.error(f"Process signals error: {e}")
        raise HTTPException(status_code=500, detail="Signal processing failed")


@router.post("/auto-refresh")
async def auto_refresh_trends(
    background_tasks: BackgroundTasks,
    x_cron_secret: Optional[str] = Header(None, alias="X-Cron-Secret"),
):
    """Cron job endpoint - background task olarak çalışır, anında 202 döner."""
    expected = os.environ.get("CRON_SECRET", "")
    if not expected or not x_cron_secret or not hmac.compare_digest(expected, x_cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    await _cron_rate_check("auto-refresh")

    try:
        background_tasks.add_task(_run_trend_refresh)
        return {"status": "accepted", "message": "Trend refresh started in background (v3: batch + radar)"}
    except Exception as e:
        logger.error(f"Auto-refresh error: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu")


@router.get("/categories")
async def get_categories(user=Depends(require_auth)):
    """Mevcut trend kategorileri."""
    return [
        {"id": "ai", "label": "AI & ML", "icon": "Brain"},
        {"id": "dev", "label": "Developer", "icon": "Code"},
        {"id": "design", "label": "Design", "icon": "Palette"},
        {"id": "crypto", "label": "Crypto", "icon": "Bitcoin"},
        {"id": "startup", "label": "Startup", "icon": "Rocket"},
        {"id": "marketing", "label": "Pazarlama", "icon": "Megaphone"},
        {"id": "business", "label": "Business", "icon": "Briefcase"},
        {"id": "science", "label": "Bilim & Tech", "icon": "FlaskConical"},
        {"id": "lifestyle", "label": "Yasam", "icon": "Heart"},
        {"id": "education", "label": "Egitim", "icon": "GraduationCap"},
        {"id": "entertainment", "label": "Eglence", "icon": "Gamepad2"},
        {"id": "news", "label": "Haberler", "icon": "Newspaper"},
    ]


def _validate_uuid(value: str) -> str:
    """Validate UUID format to prevent injection."""
    import re
    if not re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', value.lower()):
        raise HTTPException(status_code=400, detail="Geçersiz trend ID formatı")
    return value


@router.get("/{trend_id}/drafts")
async def get_trend_drafts(trend_id: str, user=Depends(require_auth)):
    """Trend icin hazir icerik taslaklari."""
    trend_id = _validate_uuid(trend_id)
    try:
        sb = get_supabase()
        result = sb.table("content_drafts").select("*").eq("trend_id", trend_id).eq("status", "draft").order("created_at", desc=True).limit(5).execute()
        return {"drafts": result.data or []}
    except Exception as e:
        logger.error(f"Trend drafts error: {e}")
        return {"drafts": []}


@router.get("/{trend_id}")
async def get_trend(trend_id: str, user=Depends(require_auth)):
    """Trend detayı."""
    trend_id = _validate_uuid(trend_id)
    try:
        sb = get_supabase()
        result = sb.table("trends").select("*").eq("id", trend_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Trend bulunamadı")
        return result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trend detail error: {e}")
        raise HTTPException(status_code=500, detail="Bir hata oluştu")


@router.post("/{trend_id}/generate", response_model=GenerationResponse)
async def generate_from_trend(
    trend_id: str,
    request: TrendGenerateRequest,
    _=Depends(rate_limit),
    user=Depends(require_auth),
    account_id: str = Depends(get_active_account),
):
    """Trend'den içerik üret. raw_content varsa daha zengin context sağlar."""
    trend_id = _validate_uuid(trend_id)
    try:
        from server import generate_with_openai
        from prompts.quality import BANNED_PATTERNS

        sb = get_supabase()
        result = sb.table("trends").select("*").eq("id", trend_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Trend bulunamadı")

        trend = result.data[0]

        # Sanitize trend fields before injecting into system prompt
        from middleware.input_sanitizer import _strip_html, _check_prompt_injection
        def _safe(val, max_len=500):
            if not val:
                return ""
            s = _strip_html(str(val))[:max_len]
            if _check_prompt_injection(s):
                return "[filtered]"
            return s

        lang = "Türkçe yaz." if request.language == "tr" else "İngilizce yaz." if request.language == "en" else "Konunun diline göre otomatik yaz."

        platform_prompts = {
            "twitter": "Twitter tweet formatında yaz. Kısa, punch'lı, viral potansiyeli yüksek.",
            "linkedin": "LinkedIn post formatında yaz. Profesyonel, insight odaklı, kısa paragraflarla.",
            "instagram": "Instagram caption formatında yaz. Kısa paragraflar, hook ile başla.",
            "blog": "Blog yazısı taslağı oluştur. SEO uyumlu, detaylı.",
            "tiktok": "TikTok script formatında yaz. 30sn, hook-heavy, hızlı tempo.",
            "youtube": "YouTube video fikri ve kısa script oluştur."
        }

        platform_prompt = platform_prompts.get(request.platform, platform_prompts["twitter"])

        # Build rich context with raw_content if available
        raw_context = ""
        if trend.get("raw_content"):
            raw_context = f"\n## KAYNAK İÇERİK:\n{_safe(trend['raw_content'], 1000)}\n"

        source_url = ""
        if trend.get("url"):
            source_url = f"\nKaynak URL: {trend['url']}"

        system_prompt = f"""
{BANNED_PATTERNS}

## GÖREV: TREND BAZLI İÇERİK ÜRET

{platform_prompt}

## TREND BİLGİSİ:
Konu: {_safe(trend['topic'])}
Kategori: {_safe(trend.get('category', 'genel'), 50)}
Özet: {_safe(trend.get('summary', ''), 300)}
Keywords: {_safe(str(trend.get('keywords', [])), 200)}
İçerik açısı: {_safe(trend.get('content_angle', ''), 200)}
{source_url}
{raw_context}

## DİL
{lang}

{"## EK BAĞLAM" + chr(10) + request.additional_context if request.additional_context else ""}

Emoji kullanma. AI template kalıpları kullanma. Doğal ve özgün yaz.
"""

        result_tuple = await generate_with_openai(system_prompt, "Trend bazlı içeriği üret.", 1)
        contents = result_tuple[0] if isinstance(result_tuple, tuple) else result_tuple
        text = contents[0] if contents else ""
        variants = [GeneratedContent(content=text, variant_index=0, character_count=len(text))]

        # Veritabanına kaydet (geçmişte görünsün)
        gen_id = None
        try:
            gen_result = sb.table("generations").insert({
                "type": request.platform,
                "user_id": user.id,
                "account_id": account_id,
                "topic": trend["topic"],
                "mode": "trend",
                "language": request.language,
                "additional_context": request.additional_context,
                "is_ultra": False,
                "variant_count": 1,
                "variants": [v.model_dump(mode="json") for v in variants],
                "created_at": datetime.now(timezone.utc).isoformat()
            }).execute()
            gen_id = gen_result.data[0]["id"] if gen_result.data else None
        except Exception as save_err:
            logger.warning(f"Trend generation DB save failed (content still returned): {save_err}")

        return GenerationResponse(success=True, variants=variants, generation_id=gen_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trend generate error: {e}")
        return GenerationResponse(success=False, variants=[], error="Bir hata oluştu. Lütfen tekrar deneyin.")

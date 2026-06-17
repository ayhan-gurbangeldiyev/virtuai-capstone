"""MCP (Model Context Protocol) Server v3.0 — Streamable HTTP transport.

Exposes TypeHype trend intelligence, content generation, and analytics
as MCP tools, resources, and prompts.

Protocol: JSON-RPC 2.0 over HTTP (MCP Streamable HTTP transport)
Auth: Bearer token (MCP_API_KEY, TYPEHYPE_MCP_KEY env aliases)
"""
from fastapi import APIRouter, Request, Response, HTTPException
from datetime import datetime, timezone, timedelta
import json
import hmac
import os
import time
import logging
import html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# ── MCP Server Info ──────────────────────────────────────────────

MCP_SERVER_INFO = {
    "name": "typehype-trends",
    "version": "3.0.0",
}

MCP_CAPABILITIES = {
    "tools": {"listChanged": False},
    "resources": {"subscribe": False, "listChanged": False},
    "prompts": {"listChanged": False},
}

# ── TTL Cache ────────────────────────────────────────────────────

_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, ttl: int):
    """Check cache. Returns (hit, value)."""
    if key in _cache and time.time() - _cache[key][0] < ttl:
        return True, _cache[key][1]
    return False, None


def _set_cache(key: str, value):
    _cache[key] = (time.time(), value)


# ── Tool Definitions ─────────────────────────────────────────────

_RO = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
_RO_EXT = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
_WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
_CATEGORIES = ["AI", "Tech", "Crypto", "Gündem", "Business", "Lifestyle", "Sports", "Health"]
_TONES = ["informative", "provocative", "humorous", "analytical", "inspirational"]

TOOLS = [
    {
        "name": "get_today_trends",
        "title": "Today's Trends",
        "description": "Get today's top trending topics. Returns topic, category, score (0-100), summary, keywords, content_angle, source type, and URL. Use this as a starting point, then search_trends for deeper exploration or generate_tweet to create content.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": _CATEGORIES, "description": "Filter by category"},
                "limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50, "description": "Max trends to return"},
                "min_score": {"type": "integer", "default": 50, "minimum": 0, "maximum": 100, "description": "Minimum trend score"},
            },
        },
        "annotations": _RO,
    },
    {
        "name": "get_day_recap",
        "title": "Daily Recap",
        "description": "Get a daily recap: top trends, category distribution, source distribution, total count, average/max score, high-quality count. Perfect for daily briefings and summaries.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format (default: today)"},
            },
        },
        "annotations": _RO,
    },
    {
        "name": "get_trending_by_category",
        "title": "Trends by Category",
        "description": "Get trends grouped by category with top 5 per category. Great for understanding what's hot across all domains at once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "min_score": {"type": "integer", "default": 40, "minimum": 0, "maximum": 100, "description": "Minimum trend score"},
            },
        },
        "annotations": _RO,
    },
    {
        "name": "search_trends",
        "title": "Trend Search",
        "description": "Full-text search across trend topics and summaries. Use after get_today_trends when you need trends about a specific subject, technology, or event.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 200, "description": "Search keyword(s)"},
                "days_back": {"type": "integer", "default": 7, "minimum": 1, "maximum": 30, "description": "Days of history to search"},
                "limit": {"type": "integer", "default": 20, "minimum": 1, "maximum": 50, "description": "Max results"},
            },
            "required": ["query"],
        },
        "annotations": _RO,
    },
    {
        "name": "get_twitter_trends",
        "title": "Live Twitter Trends",
        "description": "Get real-time Twitter/X trending topics via Xquik API. Returns currently trending hashtags and topics in Turkey.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "country": {"type": "string", "default": "TR", "description": "Country code"},
            },
        },
        "annotations": _RO_EXT,
    },
    {
        "name": "score_tweet",
        "title": "Tweet Algorithm Scorer",
        "description": "Score a tweet draft against X/Twitter algorithm signals. Returns score (0-100), quality tier, power words found, character/word counts, and specific improvement tips. Use after generate_tweet to evaluate quality.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 1000, "description": "Tweet text to score"},
            },
            "required": ["content"],
        },
        "annotations": _RO,
    },
    {
        "name": "refine_tweet",
        "title": "Tweet Refiner",
        "description": "Get AI suggestions to improve a tweet using X algorithm rules and engagement patterns. Returns refinement suggestions from Xquik's compose engine.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 1000, "description": "Tweet text to refine"},
            },
            "required": ["content"],
        },
        "annotations": _RO_EXT,
    },
    {
        "name": "generate_tweet",
        "title": "Tweet Generator",
        "description": "Generate tweet variants from a topic. Each variant is auto-scored against X algorithm. Returns ready-to-post tweets sorted by algo score. Tip: Use get_today_trends first to find trending topics.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "minLength": 1, "maxLength": 500, "description": "Topic to write about"},
                "tone": {"type": "string", "enum": _TONES, "default": "informative", "description": "Writing tone"},
                "language": {"type": "string", "enum": ["tr", "en", "auto"], "default": "auto", "description": "Output language"},
                "variants": {"type": "integer", "default": 2, "minimum": 1, "maximum": 3, "description": "Number of variants"},
            },
            "required": ["topic"],
        },
        "annotations": _WRITE,
    },
    {
        "name": "analyze_account",
        "title": "Account Analyzer",
        "description": "Analyze a Twitter/X account: engagement stats (avg likes/retweets/replies, engagement rate), content style (thread %, media %, question %, avg algo score), and top 5 tweets by engagement.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Twitter username (with or without @)"},
            },
            "required": ["username"],
        },
        "annotations": _RO_EXT,
    },
    {
        "name": "get_viral_patterns",
        "title": "Viral Pattern Analyzer",
        "description": "Analyze what makes an account's tweets go viral. Compares top 20% vs bottom 20% tweets by engagement, revealing patterns in length, questions, emojis, openings, closings, and line breaks. Returns actionable insights.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username": {"type": "string", "description": "Twitter username to analyze"},
            },
            "required": ["username"],
        },
        "annotations": _RO_EXT,
    },
    {
        "name": "compare_accounts",
        "title": "Account Comparison",
        "description": "Compare two Twitter/X accounts side by side: followers, engagement rate, algo score, content style, and gap analysis with recommendations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "username_a": {"type": "string", "description": "First account"},
                "username_b": {"type": "string", "description": "Second account"},
            },
            "required": ["username_a", "username_b"],
        },
        "annotations": _RO_EXT,
    },
    {
        "name": "repurpose_content",
        "title": "Content Repurposer",
        "description": "Transform content from one platform format to another. Convert a tweet to LinkedIn post, blog intro, TikTok caption, YouTube description, or Instagram caption.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 2000, "description": "Original content text"},
                "target_platform": {"type": "string", "enum": ["linkedin", "blog", "tiktok", "youtube", "instagram"], "description": "Target platform"},
                "language": {"type": "string", "enum": ["tr", "en", "auto"], "default": "auto", "description": "Output language"},
            },
            "required": ["content", "target_platform"],
        },
        "annotations": _WRITE,
    },
    {
        "name": "get_pipeline_health",
        "title": "Pipeline Health",
        "description": "System health check: trend counts (total/24h/1h), latest trend timestamp, pending signals, Xquik/OpenRouter/Supabase connectivity, and any active issues.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": _RO,
    },
    {
        "name": "trigger_manual_run",
        "title": "Manual Pipeline Trigger",
        "description": "Trigger a full trend pipeline refresh (RSS + Twitter + AI scoring). Requires cron_secret authorization. Use get_pipeline_health first to check if a refresh is needed.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cron_secret": {"type": "string", "description": "CRON_SECRET for authorization"},
            },
            "required": ["cron_secret"],
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True},
    },
]

# ── Resource Definitions ─────────────────────────────────────────

RESOURCES = [
    {
        "uri": "typehype://categories",
        "name": "Trend Categories",
        "description": "List of all available trend categories with descriptions",
        "mimeType": "application/json",
    },
    {
        "uri": "typehype://algorithm-factors",
        "name": "X Algorithm Factors",
        "description": "X/Twitter algorithm ranking factors and multipliers used for tweet scoring",
        "mimeType": "application/json",
    },
]

# ── Prompt Definitions ───────────────────────────────────────────

PROMPTS = [
    {
        "name": "daily_briefing",
        "description": "Generate a daily trend briefing with top stories, category breakdown, and content opportunities",
        "arguments": [],
    },
    {
        "name": "tweet_from_trend",
        "description": "Multi-step workflow: find a trend, generate a tweet about it, score it, and refine it",
        "arguments": [
            {"name": "category", "description": "Trend category to focus on (optional)", "required": False},
        ],
    },
    {
        "name": "competitor_analysis",
        "description": "Analyze a competitor's Twitter account and identify content gaps and opportunities",
        "arguments": [
            {"name": "username", "description": "Twitter username to analyze", "required": True},
        ],
    },
]


# ── Auth ─────────────────────────────────────────────────────────

def _candidate_mcp_keys() -> list[str]:
    keys: list[str] = []
    for env_name in ("MCP_API_KEY", "TYPEHYPE_MCP_KEY"):
        value = os.environ.get(env_name, "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def _check_mcp_auth(request: Request):
    """Validate MCP bearer token."""
    mcp_keys = _candidate_mcp_keys()
    if not mcp_keys:
        raise HTTPException(status_code=503, detail="MCP server not configured")

    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = auth[7:]
    if not any(hmac.compare_digest(key, token) for key in mcp_keys):
        raise HTTPException(status_code=401, detail="Invalid bearer token")


# ── Sanitization ─────────────────────────────────────────────────

def _sanitize(val, max_len: int = 2000) -> str:
    if val is None:
        return ""
    s = str(val)[:max_len]
    return html.escape(s)


# ── Supabase ─────────────────────────────────────────────────────

def _get_supabase():
    from server import supabase
    return supabase


# ── Tool Handlers ────────────────────────────────────────────────

async def _handle_get_today_trends(args: dict) -> dict:
    sb = _get_supabase()
    category = args.get("category")
    limit = min(args.get("limit", 10), 50)
    min_score = args.get("min_score", 50)

    cache_key = f"trends:{category}:{limit}:{min_score}"
    hit, cached = _cached(cache_key, 300)
    if hit:
        return cached

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    query = (
        sb.table("trends")
        .select("id,topic,category,score,summary,keywords,content_angle,url,source_type,created_at")
        .gte("created_at", cutoff)
        .gte("score", min_score)
        .order("score", desc=True)
        .limit(limit)
    )
    if category:
        query = query.ilike("category", category)

    result = query.execute()
    trends = result.data or []

    response = {
        "count": len(trends),
        "period": "last 24 hours",
        "trends": [
            {
                "topic": t["topic"],
                "category": t.get("category", ""),
                "score": t.get("score", 0),
                "summary": t.get("summary", ""),
                "keywords": t.get("keywords", []),
                "content_angle": t.get("content_angle", ""),
                "source": t.get("source_type", ""),
                "url": t.get("url", ""),
                "created_at": t.get("created_at", ""),
            }
            for t in trends
        ],
    }
    _set_cache(cache_key, response)
    return response


async def _handle_get_day_recap(args: dict) -> dict:
    sb = _get_supabase()
    date_str = args.get("date")

    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return {"error": "Invalid date format. Use YYYY-MM-DD."}
    else:
        target_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    day_start = target_date.isoformat()
    day_end = (target_date + timedelta(days=1)).isoformat()

    result = (
        sb.table("trends")
        .select("topic,category,score,summary,keywords,source_type")
        .gte("created_at", day_start)
        .lt("created_at", day_end)
        .order("score", desc=True)
        .execute()
    )
    trends = result.data or []

    if not trends:
        return {"date": date_str or target_date.strftime("%Y-%m-%d"), "total": 0, "message": "No trends found for this date."}

    categories: dict[str, int] = {}
    sources: dict[str, int] = {}
    scores = []
    for t in trends:
        cat = t.get("category", "other")
        categories[cat] = categories.get(cat, 0) + 1
        src = t.get("source_type", "unknown")
        sources[src] = sources.get(src, 0) + 1
        scores.append(t.get("score", 0))

    avg_score = sum(scores) / len(scores) if scores else 0
    high_quality = sum(1 for s in scores if s >= 80)

    return {
        "date": date_str or target_date.strftime("%Y-%m-%d"),
        "total": len(trends),
        "high_quality_count": high_quality,
        "average_score": round(avg_score, 1),
        "max_score": max(scores) if scores else 0,
        "category_distribution": categories,
        "source_distribution": sources,
        "top_trends": [
            {"topic": t["topic"], "score": t.get("score", 0), "category": t.get("category", ""), "summary": t.get("summary", "")}
            for t in trends[:10]
        ],
    }


async def _handle_get_trending_by_category(args: dict) -> dict:
    sb = _get_supabase()
    min_score = args.get("min_score", 40)

    cache_key = f"by_cat:{min_score}"
    hit, cached = _cached(cache_key, 300)
    if hit:
        return cached

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    result = (
        sb.table("trends")
        .select("topic,category,score,summary,keywords,created_at")
        .gte("created_at", cutoff)
        .gte("score", min_score)
        .order("score", desc=True)
        .limit(100)
        .execute()
    )
    trends = result.data or []

    grouped: dict[str, list] = {}
    for t in trends:
        cat = t.get("category", "other")
        if cat not in grouped:
            grouped[cat] = []
        if len(grouped[cat]) < 5:
            grouped[cat].append({
                "topic": t["topic"],
                "score": t.get("score", 0),
                "summary": t.get("summary", ""),
                "keywords": t.get("keywords", []),
            })

    response = {"categories": grouped, "total_trends": len(trends), "period": "last 48 hours"}
    _set_cache(cache_key, response)
    return response


async def _handle_search_trends(args: dict) -> dict:
    sb = _get_supabase()
    query_text = args.get("query", "").strip()
    if not query_text or len(query_text) > 200:
        return {"error": "Query must be 1-200 characters."}

    days_back = min(args.get("days_back", 7), 30)
    limit = min(args.get("limit", 20), 50)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days_back)).isoformat()

    result = (
        sb.table("trends")
        .select("topic,category,score,summary,keywords,content_angle,url,created_at")
        .gte("created_at", cutoff)
        .or_(f"topic.ilike.%{query_text}%,summary.ilike.%{query_text}%")
        .order("score", desc=True)
        .limit(limit)
        .execute()
    )
    trends = result.data or []

    return {
        "query": query_text,
        "days_back": days_back,
        "count": len(trends),
        "results": [
            {
                "topic": t["topic"],
                "category": t.get("category", ""),
                "score": t.get("score", 0),
                "summary": t.get("summary", ""),
                "keywords": t.get("keywords", []),
                "content_angle": t.get("content_angle", ""),
                "url": t.get("url", ""),
                "created_at": t.get("created_at", ""),
            }
            for t in trends
        ],
    }


async def _handle_get_twitter_trends(args: dict) -> dict:
    cache_key = "twitter_trends"
    hit, cached = _cached(cache_key, 300)
    if hit:
        return cached

    from services.xquik_client import xquik
    country = args.get("country", "TR")

    try:
        trends = await xquik.get_trends()
        if not trends:
            return {"error": "Could not fetch Twitter trends"}

        response = {
            "source": "Twitter/X via Xquik",
            "country": country,
            "count": len(trends) if isinstance(trends, list) else 0,
            "trends": trends,
        }
        _set_cache(cache_key, response)
        return response
    except Exception as e:
        logger.error(f"MCP get_twitter_trends error: {e}")
        return {"error": "Failed to fetch Twitter trends"}


async def _handle_score_tweet(args: dict) -> dict:
    content = args.get("content", "").strip()
    if not content:
        return {"error": "Content is required"}
    if len(content) > 1000:
        return {"error": "Content too long (max 1000 chars)"}

    from services.algo_scorer import calculate_algo_score, POWER_WORDS_TR, POWER_WORDS_EN

    tweet_data = {"content": content}
    score = calculate_algo_score(tweet_data)

    content_lower = content.lower()
    all_power = POWER_WORDS_TR | POWER_WORDS_EN
    power_words = [w for w in all_power if w in content_lower]

    char_count = len(content)
    word_count = len(content.split())
    has_question = "?" in content
    has_link = "http" in content.lower()
    newline_count = content.count("\n")

    if score >= 80:
        tier = "excellent"
    elif score >= 65:
        tier = "good"
    elif score >= 50:
        tier = "average"
    else:
        tier = "needs_improvement"

    tips = []
    if not has_question:
        tips.append("Add a question to boost reply potential (+6-15 points)")
    if has_link:
        tips.append("External links reduce reach by 50-90%. Consider removing.")
    if word_count < 10:
        tips.append("Too short — aim for 20-60 words for optimal dwell time")
    if word_count > 80:
        tips.append("Very long — consider splitting into a thread")
    if newline_count == 0 and word_count > 15:
        tips.append("Add line breaks to improve readability and dwell time")
    if not power_words:
        tips.append("Use power words (e.g., 'aslında', 'breaking', 'secret') to strengthen the hook")

    return {
        "score": round(score),
        "tier": tier,
        "character_count": char_count,
        "word_count": word_count,
        "power_words_found": power_words,
        "has_question": has_question,
        "has_external_link": has_link,
        "line_breaks": newline_count,
        "improvement_tips": tips,
    }


async def _handle_refine_tweet(args: dict) -> dict:
    content = args.get("content", "").strip()
    if not content:
        return {"error": "Content is required"}
    if len(content) > 1000:
        return {"error": "Content too long (max 1000 chars)"}

    from services.xquik_client import xquik

    try:
        result = await xquik.refine_tweet(content)
        return {
            "original": content,
            "refinements": result if result else "No refinement suggestions available",
        }
    except Exception as e:
        logger.error(f"MCP refine_tweet error: {e}")
        return {"error": "Refinement service unavailable"}


async def _handle_generate_tweet(args: dict) -> dict:
    topic = args.get("topic", "").strip()
    if not topic or len(topic) > 500:
        return {"error": "Topic must be 1-500 characters"}

    tone = args.get("tone", "informative")
    language = args.get("language", "auto")
    variants = min(max(args.get("variants", 2), 1), 3)

    if tone not in set(_TONES):
        tone = "informative"

    lang_prompt = {"tr": "Türkçe yaz.", "en": "Write in English.", "auto": "Konunun diline göre otomatik yaz."}.get(language, "Konunun diline göre otomatik yaz.")

    tone_prompts = {
        "informative": "Bilgilendirici ve net bir tonda yaz. Değerli insight paylaş.",
        "provocative": "Dikkat çekici, tartışma başlatıcı bir tonda yaz. Güçlü bir görüş belirt.",
        "humorous": "Esprili ve eğlenceli yaz. Ironi veya gözlem kullan.",
        "analytical": "Analitik ve derinlemesine yaz. Veri veya kanıtla destekle.",
        "inspirational": "İlham verici ve motive edici yaz. Kişisel deneyimle bağlantı kur.",
    }

    system_prompt = f"""Sen viral tweet yazan bir içerik uzmanısın.

## GÖREV
Verilen konuda tweet yaz.

## TON
{tone_prompts[tone]}

## KURALLAR
- Emoji KULLANMA
- Hashtag kullanma
- "AI template" klişelerinden kaçın
- 280 karakter sınırını aşma
- Hook ile başla (ilk satır dikkat çekmeli)
- Self-contained yaz (link gerektirmeyen)
- {lang_prompt}

## KONU
{_sanitize(topic, 500)}

Her varianti --- ile ayır. Sadece tweet metinlerini yaz, başka açıklama yapma."""

    try:
        from server import generate_with_openai
        result = await generate_with_openai(system_prompt, f"{variants} farklı tweet varianti yaz.", variants)
        contents = result[0] if isinstance(result, tuple) else result
        text = contents[0] if contents else ""

        tweet_variants = [v.strip() for v in text.split("---") if v.strip()]
        if not tweet_variants:
            tweet_variants = [text.strip()] if text.strip() else []

        from services.algo_scorer import calculate_algo_score
        scored = []
        for i, tv in enumerate(tweet_variants[:variants]):
            s = calculate_algo_score({"content": tv})
            scored.append({"index": i, "content": tv, "character_count": len(tv), "algo_score": round(s)})

        scored.sort(key=lambda x: x["algo_score"], reverse=True)

        return {"topic": topic, "tone": tone, "language": language, "variants": scored}
    except Exception as e:
        logger.error(f"MCP generate_tweet error: {e}")
        return {"error": "Tweet generation failed"}


async def _handle_analyze_account(args: dict) -> dict:
    import re
    username = args.get("username", "").lstrip("@").strip()
    if not re.match(r'^[a-zA-Z0-9_]{1,15}$', username):
        return {"error": "Invalid Twitter username"}

    from services.xquik_client import xquik

    try:
        user_info = await xquik.get_user_info(username)
        if not user_info:
            return {"error": f"@{username} not found"}

        raw_tweets = await xquik.search_user_tweets(username, limit=30)
        tweets = xquik.normalize_tweets(raw_tweets)

        if not tweets:
            return {
                "username": username,
                "display_name": user_info.get("name", ""),
                "followers": user_info.get("followers_count", 0),
                "following": user_info.get("friends_count", 0),
                "tweet_count": 0,
                "message": "No recent tweets found",
            }

        total_likes = sum(t.get("likes", 0) for t in tweets)
        total_retweets = sum(t.get("retweets", 0) for t in tweets)
        total_replies = sum(t.get("replies", 0) for t in tweets)
        avg_likes = total_likes / len(tweets)
        avg_retweets = total_retweets / len(tweets)

        avg_length = sum(len(t.get("content", "")) for t in tweets) / len(tweets)
        threads = sum(1 for t in tweets if t.get("is_thread"))
        with_media = sum(1 for t in tweets if t.get("has_media"))
        with_questions = sum(1 for t in tweets if "?" in t.get("content", ""))

        sorted_tweets = sorted(tweets, key=lambda t: t.get("likes", 0), reverse=True)
        top_tweets = [
            {"content": t["content"][:200], "likes": t.get("likes", 0), "retweets": t.get("retweets", 0), "replies": t.get("replies", 0)}
            for t in sorted_tweets[:5]
        ]

        from services.algo_scorer import calculate_algo_score
        algo_scores = [calculate_algo_score(t) for t in tweets]
        avg_algo = sum(algo_scores) / len(algo_scores)

        followers = user_info.get("followers_count", 0)
        engagement_rate = ((avg_likes + avg_retweets) / max(followers, 1)) * 100

        return {
            "username": username,
            "display_name": user_info.get("name", ""),
            "bio": user_info.get("description", ""),
            "followers": followers,
            "following": user_info.get("friends_count", 0),
            "tweets_analyzed": len(tweets),
            "engagement": {
                "avg_likes": round(avg_likes, 1),
                "avg_retweets": round(avg_retweets, 1),
                "avg_replies": round(total_replies / len(tweets), 1),
                "engagement_rate_pct": round(engagement_rate, 3),
            },
            "content_style": {
                "avg_tweet_length": round(avg_length),
                "thread_pct": round(threads / len(tweets) * 100, 1),
                "media_pct": round(with_media / len(tweets) * 100, 1),
                "question_pct": round(with_questions / len(tweets) * 100, 1),
                "avg_algo_score": round(avg_algo, 1),
            },
            "top_tweets": top_tweets,
        }
    except Exception as e:
        logger.error(f"MCP analyze_account error: {e}")
        return {"error": f"Account analysis failed: {str(e)[:100]}"}


async def _handle_get_viral_patterns(args: dict) -> dict:
    """Analyze viral patterns for an account."""
    import re
    username = args.get("username", "").lstrip("@").strip()
    if not re.match(r'^[a-zA-Z0-9_]{1,15}$', username):
        return {"error": "Invalid Twitter username"}

    from services.xquik_client import xquik
    from services.algo_scorer import extract_viral_patterns, score_all_tweets

    try:
        raw_tweets = await xquik.search_user_tweets(username, limit=50)
        tweets = xquik.normalize_tweets(raw_tweets)

        if len(tweets) < 10:
            return {"error": f"Need at least 10 tweets for pattern analysis, got {len(tweets)}"}

        # Add engagement_score for sorting
        for t in tweets:
            t["engagement_score"] = t.get("likes", 0) + t.get("retweets", 0) * 2 + t.get("replies", 0) * 3
            t["word_count"] = len(t.get("content", "").split())
            t["has_link"] = "http" in t.get("content", "").lower()

        tweets = score_all_tweets(tweets)
        patterns = extract_viral_patterns(tweets)

        return {
            "username": username,
            "tweets_analyzed": len(tweets),
            "patterns": {k: v for k, v in patterns.items() if k != "insights"},
            "insights": patterns.get("insights", []),
        }
    except Exception as e:
        logger.error(f"MCP viral_patterns error: {e}")
        return {"error": f"Viral pattern analysis failed: {str(e)[:100]}"}


async def _handle_compare_accounts(args: dict) -> dict:
    """Compare two accounts side by side."""
    a_data = await _handle_analyze_account({"username": args.get("username_a", "")})
    if "error" in a_data:
        return {"error": f"Account A: {a_data['error']}"}

    b_data = await _handle_analyze_account({"username": args.get("username_b", "")})
    if "error" in b_data:
        return {"error": f"Account B: {b_data['error']}"}

    def _gap(field_path: str):
        parts = field_path.split(".")
        va = a_data
        vb = b_data
        for p in parts:
            va = va.get(p, 0) if isinstance(va, dict) else 0
            vb = vb.get(p, 0) if isinstance(vb, dict) else 0
        return round(va - vb, 2) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None

    recommendations = []
    er_gap = _gap("engagement.engagement_rate_pct")
    algo_gap = _gap("content_style.avg_algo_score")
    q_gap = _gap("content_style.question_pct")

    if er_gap is not None and er_gap < 0:
        recommendations.append(f"{a_data['username']} has lower engagement rate — study {b_data['username']}'s top tweets for patterns")
    if algo_gap is not None and algo_gap < 0:
        recommendations.append(f"{a_data['username']} has lower algo score — improve hook quality, add questions, remove external links")
    if q_gap is not None and q_gap < -10:
        recommendations.append(f"{a_data['username']} uses fewer questions — adding questions boosts reply potential")

    a_media = a_data.get("content_style", {}).get("media_pct", 0)
    b_media = b_data.get("content_style", {}).get("media_pct", 0)
    if a_media < b_media - 15:
        recommendations.append(f"{a_data['username']} uses less media — visuals increase dwell time and engagement")

    return {
        "accounts": {
            a_data["username"]: {
                "followers": a_data.get("followers", 0),
                "engagement_rate": a_data.get("engagement", {}).get("engagement_rate_pct", 0),
                "avg_algo_score": a_data.get("content_style", {}).get("avg_algo_score", 0),
                "avg_likes": a_data.get("engagement", {}).get("avg_likes", 0),
                "question_pct": a_data.get("content_style", {}).get("question_pct", 0),
                "media_pct": a_data.get("content_style", {}).get("media_pct", 0),
            },
            b_data["username"]: {
                "followers": b_data.get("followers", 0),
                "engagement_rate": b_data.get("engagement", {}).get("engagement_rate_pct", 0),
                "avg_algo_score": b_data.get("content_style", {}).get("avg_algo_score", 0),
                "avg_likes": b_data.get("engagement", {}).get("avg_likes", 0),
                "question_pct": b_data.get("content_style", {}).get("question_pct", 0),
                "media_pct": b_data.get("content_style", {}).get("media_pct", 0),
            },
        },
        "gaps": {
            "engagement_rate": er_gap,
            "algo_score": algo_gap,
            "question_usage": q_gap,
        },
        "recommendations": recommendations if recommendations else ["Both accounts perform similarly — maintain current strategies"],
    }


async def _handle_repurpose_content(args: dict) -> dict:
    """Repurpose content for another platform."""
    content = args.get("content", "").strip()
    if not content:
        return {"error": "Content is required"}
    if len(content) > 2000:
        return {"error": "Content too long (max 2000 chars)"}

    target = args.get("target_platform", "linkedin")
    language = args.get("language", "auto")

    platform_instructions = {
        "linkedin": "LinkedIn post formatına çevir. Profesyonel ton, kısa paragraflar, insight odaklı. 1300 karakter hedefle. İlk satır hook olsun.",
        "blog": "Blog giriş paragrafı oluştur. SEO uyumlu, 200-300 kelime, konuyu genişlet ve derinleştir.",
        "tiktok": "TikTok caption yaz. 150 karakter max, punch'lı, merak uyandırıcı. Video fikri de ekle.",
        "youtube": "YouTube video açıklaması yaz. SEO uyumlu, 200 kelime, ana noktaları listele, CTA ekle.",
        "instagram": "Instagram caption yaz. 2200 karakter max, hook ile başla, hikaye anlat, CTA ile bitir.",
    }

    lang_prompt = {"tr": "Türkçe yaz.", "en": "Write in English.", "auto": "Kaynak diline göre yaz."}.get(language, "Kaynak diline göre yaz.")

    system_prompt = f"""İçerik dönüştürme uzmanısın.

## GÖREV
Verilen içeriği {target} formatına dönüştür.

## FORMAT
{platform_instructions.get(target, platform_instructions["linkedin"])}

## KURALLAR
- Emoji KULLANMA
- Orijinal mesajın özünü koru
- Platform kurallarına uy
- {lang_prompt}

## KAYNAK İÇERİK
{_sanitize(content, 2000)}

Sadece dönüştürülmüş içeriği yaz, açıklama yapma."""

    try:
        from server import generate_with_openai
        result = await generate_with_openai(system_prompt, "İçeriği dönüştür.", 1)
        contents = result[0] if isinstance(result, tuple) else result
        text = contents[0] if contents else ""

        return {
            "original_length": len(content),
            "target_platform": target,
            "repurposed_content": text.strip(),
            "repurposed_length": len(text.strip()),
        }
    except Exception as e:
        logger.error(f"MCP repurpose error: {e}")
        return {"error": "Content repurposing failed"}


async def _handle_get_pipeline_health(args: dict) -> dict:
    cache_key = "health"
    hit, cached = _cached(cache_key, 60)
    if hit:
        return cached

    sb = _get_supabase()
    now = datetime.now(timezone.utc)
    last_24h = (now - timedelta(hours=24)).isoformat()
    last_1h = (now - timedelta(hours=1)).isoformat()

    try:
        total = sb.table("trends").select("id", count="exact").execute()
        recent = sb.table("trends").select("id", count="exact").gte("created_at", last_24h).execute()
        very_recent = sb.table("trends").select("id", count="exact").gte("created_at", last_1h).execute()
        latest = sb.table("trends").select("created_at").order("created_at", desc=True).limit(1).execute()
        latest_ts = latest.data[0]["created_at"] if latest.data else None
        pending_signals = sb.table("raw_signals").select("id", count="exact").eq("status", "pending").execute()

        xquik_ok = False
        xquik_balance = "unknown"
        try:
            from services.xquik_client import xquik
            account = await xquik.get_account()
            xquik_ok = bool(account)
            xquik_balance = account.get("credits_remaining", "unknown") if account else "unknown"
        except Exception:
            xquik_balance = "error"

        openrouter_ok = bool(os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENROUTER_API_KEY"))

        total_count = total.count if hasattr(total, 'count') else len(total.data or [])
        recent_count = recent.count if hasattr(recent, 'count') else len(recent.data or [])
        very_recent_count = very_recent.count if hasattr(very_recent, 'count') else len(very_recent.data or [])
        pending_count = pending_signals.count if hasattr(pending_signals, 'count') else len(pending_signals.data or [])

        health_status = "healthy"
        issues = []
        if recent_count == 0:
            health_status = "warning"
            issues.append("No trends in last 24 hours")
        if not xquik_ok:
            health_status = "degraded"
            issues.append("Xquik API unreachable")
        if not openrouter_ok:
            health_status = "degraded"
            issues.append("OpenRouter API key not configured")

        response = {
            "status": health_status,
            "timestamp": now.isoformat(),
            "trends": {"total": total_count, "last_24h": recent_count, "last_1h": very_recent_count, "latest_trend_at": latest_ts},
            "pipeline": {"pending_signals": pending_count},
            "services": {
                "xquik": {"connected": xquik_ok, "credits": xquik_balance},
                "openrouter": {"configured": openrouter_ok},
                "supabase": {"connected": True},
            },
            "issues": issues if issues else None,
        }
        _set_cache(cache_key, response)
        return response
    except Exception as e:
        logger.error(f"MCP health check error: {e}")
        return {"status": "error", "error": str(e)[:200]}


async def _handle_trigger_manual_run(args: dict) -> dict:
    cron_secret = args.get("cron_secret", "")
    expected = os.environ.get("CRON_SECRET", "")

    if not expected or not hmac.compare_digest(expected, cron_secret):
        return {"error": "Invalid cron_secret"}

    from services.trend_engine import trend_engine
    try:
        # FIX (2026-06-14): refresh_all() argümansız — include_twitter_search kwarg'ı
        # imzada YOK, TypeError veriyordu. Cron/graph yolu da argümansız çağırıyor.
        result = await trend_engine.refresh_all()
        return {
            "success": result.get("success", False),
            "trends_saved": result.get("trends_saved", 0),
            "rss_items": result.get("rss_items", 0),
            "twitter_items": result.get("twitter_items", 0),
        }
    except Exception as e:
        logger.error(f"MCP manual run failed: {e}")
        return {"error": "Trend refresh failed"}


# ── Tool Dispatcher ──────────────────────────────────────────────

TOOL_HANDLERS = {
    "get_today_trends": _handle_get_today_trends,
    "get_day_recap": _handle_get_day_recap,
    "get_trending_by_category": _handle_get_trending_by_category,
    "search_trends": _handle_search_trends,
    "get_twitter_trends": _handle_get_twitter_trends,
    "score_tweet": _handle_score_tweet,
    "refine_tweet": _handle_refine_tweet,
    "generate_tweet": _handle_generate_tweet,
    "analyze_account": _handle_analyze_account,
    "get_viral_patterns": _handle_get_viral_patterns,
    "compare_accounts": _handle_compare_accounts,
    "repurpose_content": _handle_repurpose_content,
    "get_pipeline_health": _handle_get_pipeline_health,
    "trigger_manual_run": _handle_trigger_manual_run,
}


# ── Resource Handlers ────────────────────────────────────────────

RESOURCE_HANDLERS = {
    "typehype://categories": lambda: {
        "categories": [
            {"name": "AI", "description": "Yapay zeka, makine öğrenmesi, LLM, GPT, derin öğrenme"},
            {"name": "Tech", "description": "Teknoloji haberleri, yazılım, donanım, startup'lar"},
            {"name": "Crypto", "description": "Bitcoin, Ethereum, DeFi, Web3, blockchain"},
            {"name": "Gündem", "description": "Türkiye ve dünya gündemi, siyaset, spor, magazin"},
            {"name": "Business", "description": "İş dünyası, ekonomi, yatırım, şirket haberleri"},
            {"name": "Lifestyle", "description": "Yaşam tarzı, moda, seyahat, yemek, sağlık"},
            {"name": "Sports", "description": "Futbol, basketbol, Formula 1, spor haberleri"},
            {"name": "Health", "description": "Sağlık, tıp, wellness, biyoteknoloji"},
        ]
    },
    "typehype://algorithm-factors": lambda: {
        "source": "X/Twitter Algorithm Source Code",
        "ranking_multipliers": {
            "reply_engaged_by_author": 75.0,
            "reply": 13.5,
            "profile_click": 12.0,
            "bookmark": 10.0,
            "good_click_dwell_2min": 10.0,
            "repost": 1.0,
            "like": 0.5,
        },
        "penalties": {
            "report": -369.0,
            "negative_feedback": -74.0,
            "unknown_language": 0.01,
            "external_link": "50-90% reach loss",
        },
        "scoring_components": [
            "Reply trigger potential (0-15 pts)",
            "Dwell time potential (0-15 pts)",
            "Link penalty (-20 pts for external links)",
            "Language consistency (0-10 pts)",
            "Self-contained bonus (0-10 pts)",
            "Engagement evidence (0-15 pts)",
            "Bookmark potential (0-10 pts)",
            "Hook quality (0-10 pts)",
            "Report risk (-0-15 pts)",
        ],
        "base_score": 40,
        "max_score": 100,
    },
}


# ── Prompt Handlers ──────────────────────────────────────────────

PROMPT_HANDLERS = {
    "daily_briefing": lambda args: {
        "description": "Generate a daily trend briefing",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": "Use the get_today_trends tool to fetch today's top trends (min_score: 60, limit: 15), then use get_trending_by_category to see the full category breakdown. Create a concise daily briefing with:\n\n1. Top 5 stories of the day\n2. Category breakdown (what's hot in each category)\n3. Content opportunities (which trends are ideal for creating content about)\n4. One surprise or under-the-radar trend worth watching\n\nFormat it as a clean, scannable briefing.",
                },
            }
        ],
    },
    "tweet_from_trend": lambda args: {
        "description": "Find a trend and create a tweet about it",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Follow these steps:\n\n1. Use get_today_trends{' with category=' + args.get('category') if args.get('category') else ''} to find trending topics\n2. Pick the most content-worthy trend\n3. Use generate_tweet with that trend's topic (tone: provocative, variants: 3)\n4. Use score_tweet on each variant\n5. Use refine_tweet on the highest-scoring variant\n6. Present the final optimized tweet with its score and why it works",
                },
            }
        ],
    },
    "competitor_analysis": lambda args: {
        "description": "Full competitor analysis workflow",
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Analyze @{args.get('username', 'unknown')} as a competitor:\n\n1. Use analyze_account to get their stats and top tweets\n2. Use get_viral_patterns to understand what makes their content go viral\n3. Identify their strengths and weaknesses\n4. Suggest 3 specific content strategies to outperform them\n5. Generate 2 tweet examples inspired by their best-performing patterns but with a unique angle",
                },
            }
        ],
    },
}


# ── JSON-RPC Helpers ─────────────────────────────────────────────

def _jsonrpc_response(msg_id, result):
    return {"jsonrpc": "2.0", "id": msg_id, "result": result}


def _jsonrpc_error(msg_id, code, message):
    return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


# ── MCP Endpoint (Streamable HTTP) ──────────────────────────────

@router.post("")
async def mcp_endpoint(request: Request):
    """MCP Streamable HTTP endpoint — handles JSON-RPC 2.0 messages."""
    _check_mcp_auth(request)

    try:
        body = await request.json()
    except Exception:
        return Response(
            content=json.dumps(_jsonrpc_error(None, -32700, "Parse error")),
            media_type="application/json",
            status_code=400,
        )

    method = body.get("method", "")
    msg_id = body.get("id")
    params = body.get("params", {})

    # ── initialize ──
    if method == "initialize":
        result = {
            "protocolVersion": "2025-03-26",
            "capabilities": MCP_CAPABILITIES,
            "serverInfo": MCP_SERVER_INFO,
        }
        return Response(content=json.dumps(_jsonrpc_response(msg_id, result)), media_type="application/json")

    # ── notifications ──
    if method.startswith("notifications/"):
        return Response(status_code=204)

    # ── tools/list ──
    if method == "tools/list":
        return Response(content=json.dumps(_jsonrpc_response(msg_id, {"tools": TOOLS})), media_type="application/json")

    # ── tools/call ──
    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})

        handler = TOOL_HANDLERS.get(tool_name)
        if not handler:
            return Response(content=json.dumps(_jsonrpc_error(msg_id, -32602, f"Unknown tool: {tool_name}")), media_type="application/json")

        try:
            tool_result = await handler(tool_args)
            is_error = "error" in tool_result
            result = {
                "content": [{"type": "text", "text": json.dumps(tool_result, ensure_ascii=False, default=str)}],
            }
            if is_error:
                result["isError"] = True
            return Response(content=json.dumps(_jsonrpc_response(msg_id, result)), media_type="application/json")
        except Exception as e:
            logger.error(f"MCP tool error ({tool_name}): {e}")
            result = {"content": [{"type": "text", "text": json.dumps({"error": str(e)[:200]})}], "isError": True}
            return Response(content=json.dumps(_jsonrpc_response(msg_id, result)), media_type="application/json")

    # ── resources/list ──
    if method == "resources/list":
        return Response(content=json.dumps(_jsonrpc_response(msg_id, {"resources": RESOURCES})), media_type="application/json")

    # ── resources/read ──
    if method == "resources/read":
        uri = params.get("uri", "")
        handler = RESOURCE_HANDLERS.get(uri)
        if not handler:
            return Response(content=json.dumps(_jsonrpc_error(msg_id, -32002, f"Resource not found: {uri}")), media_type="application/json")

        data = handler()
        result = {
            "contents": [{"uri": uri, "mimeType": "application/json", "text": json.dumps(data, ensure_ascii=False)}]
        }
        return Response(content=json.dumps(_jsonrpc_response(msg_id, result)), media_type="application/json")

    # ── prompts/list ──
    if method == "prompts/list":
        return Response(content=json.dumps(_jsonrpc_response(msg_id, {"prompts": PROMPTS})), media_type="application/json")

    # ── prompts/get ──
    if method == "prompts/get":
        prompt_name = params.get("name", "")
        prompt_args = params.get("arguments", {})
        handler = PROMPT_HANDLERS.get(prompt_name)
        if not handler:
            return Response(content=json.dumps(_jsonrpc_error(msg_id, -32602, f"Unknown prompt: {prompt_name}")), media_type="application/json")

        result = handler(prompt_args)
        return Response(content=json.dumps(_jsonrpc_response(msg_id, result)), media_type="application/json")

    # ── Unknown method ──
    return Response(content=json.dumps(_jsonrpc_error(msg_id, -32601, f"Method not found: {method}")), media_type="application/json")

# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Style Lab v2 - Tweet Collector (Apify)
Kullanıcının tweet'lerini Apify ile çeker, source_tweets'e kaydeder.

Özellikler:
- 500+ ana tweet + 100 reply + 100 quote = ~700 tweet
- Progressive: İlk 50 hızlı, sonra arka planda 700'e tamamla
- Engagement score hesaplama
- Dedup (tweet_id bazlı)
- Maliyet: ~$0.28-0.35 / kullanıcı profil
"""

import os
import re
import logging
import hashlib
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Apify config
APIFY_TOKEN = os.environ.get("APIFY_API_TOKEN", "")
APIFY_ACTOR = "apidojo/tweet-scraper"
APIFY_TIMEOUT_SECS = 120

# Collection limits
MAIN_TWEET_LIMIT = 500
REPLY_TWEET_LIMIT = 100
QUOTE_TWEET_LIMIT = 100
QUICK_LIMIT = 50  # Progressive modda hızlı çekim


def _build_queries(handle: str, quick: bool = False) -> List[Dict]:
    """Apify search query'leri oluştur"""
    handle = handle.lstrip("@")
    limit = QUICK_LIMIT if quick else MAIN_TWEET_LIMIT
    
    queries = [
        {
            "query": f"from:{handle} -filter:retweets -filter:replies",
            "type": "original",
            "limit": limit,
        }
    ]
    
    if not quick:
        queries.extend([
            {
                "query": f"from:{handle} filter:replies -filter:retweets",
                "type": "reply",
                "limit": REPLY_TWEET_LIMIT,
            },
            {
                "query": f"from:{handle} filter:quote",
                "type": "quote",
                "limit": QUOTE_TWEET_LIMIT,
            },
        ])
    
    return queries


async def collect_tweets_apify(
    handle: str,
    quick: bool = False,
) -> List[Dict]:
    """
    Apify ile tweet'leri çek.
    
    Args:
        handle: Twitter handle (@olmadan da olur)
        quick: True ise sadece 50 tweet (hızlı analiz)
    
    Returns:
        Parsed tweet listesi
    """
    import httpx
    
    handle = handle.lstrip("@")
    queries = _build_queries(handle, quick=quick)
    all_tweets = []
    seen_ids = set()
    
    for q in queries:
        logger.info(f"Apify collecting: {q['query']} (limit={q['limit']})")
        
        try:
            tweets = await _run_apify_query(
                query=q["query"],
                limit=q["limit"],
            )
            
            for tweet in tweets:
                parsed = _parse_apify_tweet(tweet, tweet_type=q["type"])
                if parsed and parsed["tweet_id"] not in seen_ids:
                    seen_ids.add(parsed["tweet_id"])
                    all_tweets.append(parsed)
            
            logger.info(f"  -> {len(tweets)} fetched, {len(all_tweets)} total unique")
            
        except Exception as e:
            logger.error(f"Apify query failed: {q['query']} -> {e}")
            continue
    
    logger.info(f"Collection complete: {len(all_tweets)} tweets for @{handle}")
    return all_tweets


async def _run_apify_query(query: str, limit: int) -> List[Dict]:
    """Apify actor'ü çalıştır ve sonuçları al"""
    import httpx
    
    if not APIFY_TOKEN:
        raise ValueError("APIFY_API_TOKEN env variable not set")
    
    url = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"
    
    payload = {
        "searchTerms": [query],
        "sort": "Latest",
        "maxItems": limit,
        "addUserInfo": True,
    }
    
    async with httpx.AsyncClient(timeout=APIFY_TIMEOUT_SECS) as client:
        resp = await client.post(
            url,
            json=payload,
            params={"token": APIFY_TOKEN},
        )
        
        if resp.status_code != 200 and resp.status_code != 201:
            logger.error(f"Apify error {resp.status_code}: {resp.text[:200]}")
            raise Exception(f"Apify returned {resp.status_code}")
        
        return resp.json()


def _parse_apify_tweet(raw: dict, tweet_type: str = "original") -> Optional[Dict]:
    """Apify tweet verisini normalize et"""
    # Tweet ID
    tweet_id = raw.get("id") or raw.get("id_str") or raw.get("tweetId")
    if not tweet_id:
        url = raw.get("url", "")
        match = re.search(r"/status/(\d+)", url)
        tweet_id = match.group(1) if match else None
    
    if not tweet_id:
        return None
    
    # Content
    content = (
        raw.get("full_text")
        or raw.get("text")
        or raw.get("fullText")
        or ""
    ).strip()
    
    if not content or len(content) < 10:
        return None
    
    # Clean t.co URLs at end
    content_clean = re.sub(r'\s*https://t\.co/\w+\s*$', '', content).strip()
    
    # Metrics
    likes = int(raw.get("favorite_count") or raw.get("likeCount") or raw.get("likes") or 0)
    retweets = int(raw.get("retweet_count") or raw.get("retweetCount") or raw.get("retweets") or 0)
    replies = int(raw.get("reply_count") or raw.get("replyCount") or raw.get("replies") or 0)
    views = int(raw.get("views") or raw.get("viewCount") or 0)
    bookmarks = int(raw.get("bookmark_count") or raw.get("bookmarkCount") or 0)
    quotes = int(raw.get("quote_count") or raw.get("quoteCount") or 0)
    
    # Date
    created_at = raw.get("created_at") or raw.get("createdAt")
    if created_at and isinstance(created_at, str):
        try:
            # Twitter format: "Thu Feb 06 15:30:00 +0000 2026"
            created_at = datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y").isoformat()
        except ValueError:
            try:
                created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00")).isoformat()
            except:
                created_at = None
    
    # Language
    lang = raw.get("lang") or raw.get("language") or "und"
    
    # Has media / link
    has_media = bool(
        raw.get("media") 
        or raw.get("entities", {}).get("media")
        or raw.get("has_media")
    )
    has_link = bool(re.search(r'https?://(?!t\.co)', content))
    
    # Word count
    word_count = len(content_clean.split())
    
    # Engagement score (weighted)
    # Based on X algorithm weights: reply=13.5x, like=0.5x, RT=1.0x, bookmark~10x
    engagement_score = (
        likes * 0.5 +
        retweets * 1.0 +
        replies * 13.5 +
        bookmarks * 10.0 +
        quotes * 5.0
    )
    
    return {
        "tweet_id": str(tweet_id),
        "content": content_clean,
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "views": views,
        "bookmarks": bookmarks,
        "quotes": quotes,
        "tweet_type": tweet_type,
        "language": lang,
        "has_media": has_media,
        "has_link": has_link,
        "word_count": word_count,
        "engagement_score": engagement_score,
        "tweet_created_at": created_at,
        "is_thread": False,  # TODO: thread detection
    }


def calculate_engagement_score(tweet: dict) -> float:
    """X algoritma ağırlıklarıyla engagement score hesapla"""
    return (
        tweet.get("likes", 0) * 0.5 +
        tweet.get("retweets", 0) * 1.0 +
        tweet.get("replies", 0) * 13.5 +
        tweet.get("bookmarks", 0) * 10.0 +
        tweet.get("quotes", 0) * 5.0
    )


async def save_tweets_to_db(
    supabase_client,
    source_id: str,
    tweets: List[Dict],
) -> int:
    """Tweet'leri source_tweets tablosuna kaydet (upsert)"""
    saved = 0
    
    for tweet in tweets:
        try:
            row = {
                "source_id": source_id,
                "tweet_id": tweet["tweet_id"],
                "content": tweet["content"],
                "likes": tweet["likes"],
                "retweets": tweet["retweets"],
                "replies": tweet["replies"],
                "views": tweet.get("views"),
                "bookmarks": tweet.get("bookmarks", 0),
                "quotes": tweet.get("quotes", 0),
                "tweet_type": tweet.get("tweet_type", "original"),
                "language": tweet.get("language"),
                "has_media": tweet.get("has_media", False),
                "has_link": tweet.get("has_link", False),
                "word_count": tweet.get("word_count"),
                "engagement_score": tweet.get("engagement_score"),
                "is_thread": tweet.get("is_thread", False),
                "tweet_created_at": tweet.get("tweet_created_at"),
            }
            
            supabase_client.table("source_tweets").upsert(
                row,
                on_conflict="source_id,tweet_id",
            ).execute()
            saved += 1
            
        except Exception as e:
            logger.warning(f"Failed to save tweet {tweet['tweet_id']}: {e}")
            continue
    
    logger.info(f"Saved {saved}/{len(tweets)} tweets to source_tweets")
    return saved


async def collect_and_save(
    supabase_client,
    source_id: str,
    handle: str,
    quick: bool = False,
) -> Tuple[int, List[Dict]]:
    """
    Full pipeline: Apify'dan çek → DB'ye kaydet
    
    Returns: (saved_count, tweets_list)
    """
    tweets = await collect_tweets_apify(handle, quick=quick)
    
    if not tweets:
        logger.warning(f"No tweets collected for @{handle}")
        return 0, []
    
    saved = await save_tweets_to_db(supabase_client, source_id, tweets)
    
    # Update source stats
    try:
        supabase_client.table("style_sources").update({
            "tweet_count": len(tweets),
            "last_scraped_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", source_id).execute()
    except Exception as e:
        logger.warning(f"Failed to update source stats: {e}")
    
    return saved, tweets

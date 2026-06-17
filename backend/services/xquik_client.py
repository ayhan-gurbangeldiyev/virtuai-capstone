"""
Xquik API Client - Type Hype entegrasyonu.
Bird CLI + TwitterGraphQL + Cookie sistemi yerine geçer.

Docs: https://docs.xquik.com
API Base: https://xquik.com/api/v1
Rate Limit: 10 req/s sustained, 20 burst
"""

import os
import asyncio
import logging
import time
from typing import List, Optional, Dict, Any

import re
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

_TWITTER_USERNAME_RE = re.compile(r'^@?[a-zA-Z0-9_]{1,15}$')


def _is_retryable_http(exc: BaseException) -> bool:
    """Ağ/sunucu (geçici) hatalarını retry et; 4xx (401/404 gibi kalıcı) ETME.
    429 zaten _get/_post içindeki Retry-After döngüsünde ele alınıyor."""
    if isinstance(exc, (
        httpx.TimeoutException, httpx.ConnectError, httpx.ReadError,
        httpx.WriteError, httpx.RemoteProtocolError, httpx.PoolTimeout,
    )):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


# tenacity 2. kalkan: timeout/connect/5xx → 3 deneme exponential; son deneme de
# patlarsa reraise (sessiz [] DEĞİL — gerçek hata caller'a gider).
_XQUIK_RETRY = dict(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=20),
    retry=retry_if_exception(_is_retryable_http),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)

# ----------------------------------------------------------------
# Config
# ----------------------------------------------------------------
XQUIK_API_KEY = os.environ.get("XQUIK_API_KEY", "")
BASE_URL = "https://xquik.com/api/v1"
DEFAULT_TIMEOUT = 30
POLL_INTERVAL = 2  # saniye
POLL_MAX_WAIT = 120  # max bekleme


class XquikClient:
    """Xquik REST API client."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or XQUIK_API_KEY
        if not self.api_key:
            logger.warning("XQUIK_API_KEY not set")
        self._headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    @staticmethod
    def _safe_username(username: str) -> str:
        """Validate and sanitize Twitter username."""
        clean = username.lstrip("@").strip()
        if not _TWITTER_USERNAME_RE.match(clean):
            raise ValueError(f"Invalid Twitter username: {clean[:20]}")
        return clean

    # ----------------------------------------------------------------
    # HTTP helpers
    # ----------------------------------------------------------------
    @retry(**_XQUIK_RETRY)
    async def _get(self, path: str, params: dict = None) -> dict:
        """GET — 429 Retry-After döngüsü + tenacity (timeout/connect/5xx) 2. kalkan."""
        url = f"{BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            for attempt in range(3):
                resp = await client.get(url, headers=self._headers, params=params)
                if resp.status_code == 429:
                    retry_after = min(int(resp.headers.get("Retry-After", 2)), 60)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
        raise Exception(f"Rate limit exceeded after 3 retries: {path}")

    @retry(**_XQUIK_RETRY)
    async def _post(self, path: str, body: dict) -> dict:
        """POST — 429 Retry-After döngüsü + tenacity (timeout/connect/5xx) 2. kalkan."""
        url = f"{BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            for attempt in range(3):
                resp = await client.post(url, headers=self._headers, json=body)
                if resp.status_code == 429:
                    retry_after = min(int(resp.headers.get("Retry-After", 2)), 60)
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                return resp.json()
        raise Exception(f"Rate limit exceeded after 3 retries: {path}")

    async def _delete(self, path: str) -> dict:
        """DELETE request."""
        url = f"{BASE_URL}{path}"
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            resp = await client.delete(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json() if resp.text else {}

    # ================================================================
    # TRENDS (Metered — ~3 kredi/çağrı)
    # ================================================================
    async def get_trends(self, woeid: int = 23424969, count: int = 50) -> List[dict]:
        """
        X trending topics. Metered (~3 kredi/çağrı).
        Türkiye: woeid=23424969, Worldwide: woeid=1
        Docs: GET /api/v1/trends
        """
        data = await self._get("/trends", params={"woeid": woeid, "count": count})
        return data.get("trends", [])

    # ================================================================
    # RADAR (Ücretsiz — quota yemiyor)
    # ================================================================
    async def get_radar(
        self,
        source: str = None,
        category: str = "tech",
        hours: int = 24,
        limit: int = 50,
        region: str = "global",
    ) -> dict:
        """
        XQuik Radar — 7 kaynaktan trend sinyalleri. ÜCRETSİZ.

        Sources: google_trends, hacker_news, reddit, github, polymarket, wikipedia, trustmrr
        Categories: general, tech, dev, science, culture, politics, business, entertainment
        Regions: US, GB, TR, ES, DE, FR, JP, IN, BR, CA, MX, global
        Hours: 1-72 (default 6)
        Limit: 1-100 (default 50)

        Response items: id, title, description, url, imageUrl, source, category,
                       region, language, score (0-10000), publishedAt, metadata{}
        Metadata (source-specific):
            github: starsToday, language
            hacker_news: points, numberComments, author
            reddit: subreddit, author
            google_trends: approxTraffic
            wikipedia: views
            polymarket: volume24hr, liquidity, outcomes
            trustmrr: mrr, growthPercent, customers, xHandle
        """
        params = {"category": category, "hours": hours, "limit": limit, "region": region}
        if source:
            params["source"] = source
        return await self._get("/radar", params=params)

    # ================================================================
    # EXTRACTIONS (Metered — async job pattern)
    # ================================================================
    async def extract_posts(self, username: str, limit: int = 500) -> dict:
        """
        Kullanıcının son tweetlerini çek.
        Docs: POST /api/v1/extractions
        toolType: post_extractor, targetUsername: username
        Returns: extraction job object (poll with get_extraction)
        """
        body = {
            "toolType": "post_extractor",
            "targetUsername": self._safe_username(username),
            "resultsLimit": limit,
        }
        return await self._post("/extractions", body)

    async def search_tweets(self, query: str, limit: int = 200) -> dict:
        """
        Tweet arama (keyword, from:user, hashtag vs.)
        Docs: POST /api/v1/extractions
        toolType: tweet_search_extractor, searchQuery: query
        X search syntax destekler: from:user, OR, #hashtag, "exact phrase"
        """
        body = {
            "toolType": "tweet_search_extractor",
            "searchQuery": query,
            "resultsLimit": limit,
        }
        return await self._post("/extractions", body)

    async def search_user_tweets(
        self,
        username: str,
        limit: int = 50,
        min_faves: int = 0,
        exclude_replies: bool = True,
        since_date: str = None,
    ) -> List[dict]:
        """
        from:username ile tek çağrıda engagement dahil tweet çek.
        tweet_search_extractor kullanır — post_extractor + lookup_tweet çift daldırmasını ortadan kaldırır.

        Sunucu tarafı filtreler sonuç sayısını azaltır = daha az quota.
        """
        query = f"from:{self._safe_username(username)}"
        body: Dict[str, Any] = {
            "toolType": "tweet_search_extractor",
            "searchQuery": query,
            "resultsLimit": limit,
            "retweets": "exclude",
        }
        if min_faves > 0:
            body["minFaves"] = min_faves
        if exclude_replies:
            body["replies"] = "exclude"
        if since_date:
            body["sinceDate"] = since_date

        job = await self._post("/extractions", body)
        extraction_id = job.get("id")
        if not extraction_id:
            logger.error(f"search_user_tweets: no job ID for @{username}: {job}")
            return []
        return await self.get_extraction_results(extraction_id)

    async def extract_replies(self, tweet_id: str, limit: int = 500) -> dict:
        """Tweet'e gelen reply'ları çek."""
        body = {
            "toolType": "reply_extractor",
            "targetTweetId": tweet_id,
            "resultsLimit": limit,
        }
        return await self._post("/extractions", body)

    async def extract_followers(self, username: str, limit: int = 1000) -> dict:
        """Kullanıcının follower'larını çek."""
        body = {
            "toolType": "follower_explorer",
            "targetUsername": self._safe_username(username),
            "resultsLimit": limit,
        }
        return await self._post("/extractions", body)

    async def extract_mentions(self, username: str, limit: int = 200) -> dict:
        """Kullanıcıdan bahseden tweetleri çek."""
        body = {
            "toolType": "mention_extractor",
            "targetUsername": self._safe_username(username),
            "resultsLimit": limit,
        }
        return await self._post("/extractions", body)

    async def estimate_extraction(self, tool_type: str, **kwargs) -> dict:
        """
        Extraction maliyetini önceden hesapla.
        Docs: GET /api/v1/extractions/estimate
        """
        params = {"toolType": tool_type, **kwargs}
        return await self._get("/extractions/estimate", params=params)

    async def get_extraction(self, extraction_id: str) -> dict:
        """
        Extraction job detayı + sonuçları (paginated).
        Docs: GET /api/v1/extractions/:id
        """
        return await self._get(f"/extractions/{extraction_id}")

    async def get_extraction_results(self, extraction_id: str) -> List[dict]:
        """
        Extraction tamamlanana kadar bekle, tüm sonuçları topla.
        Paginated cursor ile tüm sayfaları çeker.
        
        Response format:
            {"job": {"id", "status", "totalResults", ...}, "results": [...], "hasMore", "nextCursor"}
        """
        start = time.time()
        while time.time() - start < POLL_MAX_WAIT:
            data = await self.get_extraction(extraction_id)
            job = data.get("job", {})
            status = job.get("status", data.get("status", ""))

            if status == "completed":
                results = data.get("results", [])
                # Pagination varsa devam et
                while data.get("hasMore"):
                    cursor = data.get("nextCursor")
                    if not cursor:
                        break
                    data = await self._get(
                        f"/extractions/{extraction_id}",
                        params={"after": cursor},
                    )
                    results.extend(data.get("results", []))
                logger.info(f"Extraction {extraction_id}: {len(results)} results")
                return results

            if status == "failed":
                logger.error(f"Extraction {extraction_id} failed: {data}")
                return []

            # Hala çalışıyor, bekle
            await asyncio.sleep(POLL_INTERVAL)

        logger.error(f"Extraction {extraction_id} timed out after {POLL_MAX_WAIT}s")
        return []

    async def extract_and_wait(self, tool_type: str, limit: int = 500, **kwargs) -> List[dict]:
        """
        Extraction başlat + tamamlanana kadar bekle + sonuçları dön.
        Convenience method.
        """
        body = {"toolType": tool_type, "resultsLimit": limit, **kwargs}
        job = await self._post("/extractions", body)
        extraction_id = job.get("id")
        if not extraction_id:
            logger.error(f"No extraction ID returned: {job}")
            return []
        return await self.get_extraction_results(extraction_id)

    # ================================================================
    # LOOKUPS (Metered)
    # ================================================================
    async def lookup_tweet(self, tweet_id: str) -> Optional[dict]:
        """
        Tek tweet detayı.
        Docs: GET /api/v1/x/tweets/:id
        """
        try:
            return await self._get(f"/x/tweets/{tweet_id}")
        except Exception as e:
            logger.error(f"Tweet lookup failed for {tweet_id}: {e}")
            return None

    async def get_user_info(self, username: str) -> Optional[dict]:
        """
        Kullanıcı profil bilgisi.
        Docs: GET /api/v1/x/users/:username
        """
        try:
            return await self._get(f"/x/users/{self._safe_username(username)}")
        except Exception as e:
            logger.error(f"User lookup failed for @{username}: {e}")
            return None

    async def check_follow(self, source: str, target: str) -> Optional[bool]:
        """
        source kullanıcısı target'ı takip ediyor mu?
        Docs: GET /api/v1/x/follows/check
        """
        try:
            data = await self._get(
                "/x/follows/check",
                params={"sourceUsername": source, "targetUsername": target},
            )
            return data.get("isFollowing")
        except Exception as e:
            logger.error(f"Follow check failed: {e}")
            return None

    # ================================================================
    # MONITORS (Bedava, quota yemiyor. Max 1 monitor base plan)
    # ================================================================
    async def create_monitor(self, username: str, event_types: List[str] = None) -> dict:
        """
        Hesap izlemeye al. Base plan: max 1 monitor.
        Docs: POST /api/v1/monitors
        Event types: tweet.new, tweet.reply, tweet.quote, tweet.retweet, follower.gained, follower.lost
        """
        if event_types is None:
            event_types = ["tweet.new", "tweet.reply", "follower.gained", "follower.lost"]
        return await self._post("/monitors", {
            "username": self._safe_username(username),
            "eventTypes": event_types,
        })

    async def list_monitors(self) -> List[dict]:
        """Tüm monitor'ları listele."""
        data = await self._get("/monitors")
        return data.get("monitors", [])

    async def delete_monitor(self, monitor_id: str) -> dict:
        """Monitor sil."""
        return await self._delete(f"/monitors/{monitor_id}")

    async def list_events(self, monitor_id: str = None, event_type: str = None, limit: int = 50) -> List[dict]:
        """
        Monitor eventlerini listele.
        Docs: GET /api/v1/events
        Bedava, quota yemiyor.
        """
        params = {"limit": limit}
        if monitor_id:
            params["monitorId"] = monitor_id
        if event_type:
            params["eventType"] = event_type
        data = await self._get("/events", params=params)
        return data.get("events", [])

    # ================================================================
    # WEBHOOKS (Bedava)
    # ================================================================
    async def create_webhook(self, url: str, event_types: List[str]) -> dict:
        """
        Webhook oluştur. HTTPS zorunlu.
        Docs: POST /api/v1/webhooks
        Response'da secret var, bir kez gösterilir!
        """
        return await self._post("/webhooks", {
            "url": url,
            "eventTypes": event_types,
        })

    async def list_webhooks(self) -> List[dict]:
        """Tüm webhook'ları listele."""
        data = await self._get("/webhooks")
        return data.get("webhooks", [])

    # ================================================================
    # STYLES (analyze: metered, get/list/compare: bedava)
    # ================================================================
    async def analyze_style(self, username: str) -> dict:
        """
        Hesabın tweetlerini çek + cache'le (metered).
        Docs: POST /api/v1/styles
        """
        return await self._post("/styles", {"username": self._safe_username(username)})

    async def get_style(self, username: str) -> Optional[dict]:
        """
        Cache'ten stil verisi al (bedava).
        Docs: GET /api/v1/styles/:username
        """
        try:
            return await self._get(f"/styles/{self._safe_username(username)}")
        except Exception:
            return None

    async def compare_styles(self, usernames: List[str]) -> dict:
        """
        İki veya daha fazla hesabı karşılaştır (bedava).
        Docs: POST /api/v1/styles/compare
        """
        return await self._post("/styles/compare", {
            "usernames": [self._safe_username(u) for u in usernames]
        })

    async def save_custom_style(self, username: str, tweets: List[str]) -> dict:
        """
        Tweet listesinden custom style kaydet. ÜCRETSİZ, analyze gerektirmez.
        VIP batch'ten çekilen tweetleri style olarak kaydedebiliriz.
        Docs: POST /api/v1/styles
        """
        return await self._post("/styles", {
            "username": self._safe_username(username),
            "tweets": tweets,
        })

    async def get_or_analyze_style(self, username: str) -> Optional[dict]:
        """
        Önce ücretsiz cache'e bak, yoksa 1 kez analyze et (ücretli).
        Analyze sonucu XQuik tarafında cache'lenir, sonraki get_style() bedava.
        """
        cached = await self.get_style(username)
        if cached:
            return cached
        try:
            return await self.analyze_style(username)
        except Exception as e:
            logger.error(f"Style analyze failed for @{username}: {e}")
            return None

    # ================================================================
    # TWEET COMPOSITION via MCP (Hepsi bedava, quota yemiyor)
    # ================================================================
    async def _mcp_call(self, tool_name: str, arguments: dict) -> dict:
        """
        Xquik MCP server'a tool çağrısı yap (StreamableHTTP).
        Session initialize → tool call → parse result.
        """
        mcp_url = "https://xquik.com/mcp"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

        async with httpx.AsyncClient(timeout=60) as client:
            # Initialize session
            r = await client.post(mcp_url, headers=headers, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2025-03-26",
                    "capabilities": {},
                    "clientInfo": {"name": "typehype", "version": "1.0"},
                }
            })
            r.raise_for_status()
            session = r.headers.get("mcp-session-id", "")
            if session:
                headers["mcp-session-id"] = session

            # Send initialized notification
            await client.post(mcp_url, headers=headers, json={
                "jsonrpc": "2.0", "method": "notifications/initialized"
            })

            # Tool call
            r = await client.post(mcp_url, headers=headers, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments}
            })
            r.raise_for_status()
            data = r.json()

            # Parse MCP result: content[].text → JSON
            import json as _json
            import html as _html
            content = data.get("result", {}).get("content", [])
            for item in content:
                text = item.get("text", "")
                try:
                    parsed = _json.loads(text)
                    # Sanitize string values to prevent XSS
                    def _sanitize_val(v):
                        if isinstance(v, str):
                            return _html.escape(v)
                        if isinstance(v, dict):
                            return {k: _sanitize_val(vv) for k, vv in v.items()}
                        if isinstance(v, list):
                            return [_sanitize_val(vv) for vv in v]
                        return v
                    return _sanitize_val(parsed)
                except Exception:
                    # Escape raw text to prevent XSS
                    return {"raw": _html.escape(text[:2000])}
            return {}

    async def compose_rules(self, topic: str, goal: str = "engagement") -> dict:
        """
        X algoritma kuralları + engagement multiplier'lar al.
        Goals: engagement, followers, authority, conversation
        Bedava, quota yemiyor.

        Returns: {contentRules: [...], engagementMultipliers: [...]}
        """
        return await self._mcp_call("compose-tweet", {
            "step": "compose",
            "topic": topic,
            "goal": goal,
        })

    async def score_tweet(self, draft: str) -> dict:
        """
        Draft tweet'i X algoritma ranking faktörlerine karşı skorla.
        Bedava, quota yemiyor.

        Returns: {checklist: [{factor, passed, suggestion?}...], summary: str}
        """
        return await self._mcp_call("compose-tweet", {
            "step": "score",
            "draft": draft,
        })

    async def refine_tweet(self, draft: str, topic: str = "", goal: str = "engagement", tone: str = "professional") -> dict:
        """
        Draft tweet'i algoritma kurallarına göre iyileştirme önerileri al.
        Bedava, quota yemiyor.

        Args:
            draft: tweet metni
            topic: konu (opsiyonel ama önerilir)
            goal: engagement/followers/authority/conversation
            tone: professional/casual/witty/bold

        Returns: refine önerileri
        """
        return await self._mcp_call("compose-tweet", {
            "step": "refine",
            "draft": draft,
            "topic": topic or "genel",
            "goal": goal,
            "tone": tone,
        })

    # ================================================================
    # ACCOUNT (Bedava)
    # ================================================================
    async def get_account(self) -> dict:
        """
        Hesap bilgisi, subscription durumu, kullanım yüzdesi.
        Docs: GET /api/v1/account
        """
        return await self._get("/account")

    # ================================================================
    # BULK ENRICHMENT (extraction + lookup birleştir)
    # ================================================================
    async def extract_posts_with_engagement(self, username: str, limit: int = 500, lookup_batch: int = 10) -> List[dict]:
        """
        Post extraction + bulk tweet lookup ile tam veri çek.
        1. post_extractor ile tweet ID + text al
        2. lookup_tweet ile engagement metrikleri ekle (parallel batch)
        
        Quota: ~limit extraction + ~limit lookup = ~2x limit metered calls
        500 tweet = 500 extraction + 500 lookup = ~1000 calls = %1.5 quota
        """
        # Adım 1: Extraction
        job = await self.extract_posts(username, limit=limit)
        extraction_id = job.get("id")
        if not extraction_id:
            logger.error(f"extract_posts_with_engagement: no job ID: {job}")
            return []
        
        raw_results = await self.get_extraction_results(extraction_id)
        if not raw_results:
            return []
        
        logger.info(f"Extracted {len(raw_results)} tweets for @{username}, enriching with lookup...")
        
        # Adım 2: Batch lookup for engagement
        enriched = []
        tweet_ids = [r.get("tweetId") for r in raw_results if r.get("tweetId")]
        
        # lookup_batch'lik gruplar halinde parallel çağır
        for i in range(0, len(tweet_ids), lookup_batch):
            batch = tweet_ids[i:i + lookup_batch]
            tasks = [self.lookup_tweet(tid) for tid in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for tid, lookup_result in zip(batch, results):
                if isinstance(lookup_result, Exception) or not lookup_result:
                    continue
                
                tweet_data = lookup_result.get("tweet", {})
                author_data = lookup_result.get("author", {})
                
                enriched.append({
                    "tweetId": tid,
                    "tweetText": tweet_data.get("text", ""),
                    "tweetCreatedAt": tweet_data.get("createdAt", ""),
                    "likeCount": tweet_data.get("likeCount", 0),
                    "retweetCount": tweet_data.get("retweetCount", 0),
                    "replyCount": tweet_data.get("replyCount", 0),
                    "quoteCount": tweet_data.get("quoteCount", 0),
                    "viewCount": tweet_data.get("viewCount", 0),
                    "bookmarkCount": tweet_data.get("bookmarkCount", 0),
                    "xUsername": author_data.get("username", ""),
                    "xDisplayName": author_data.get("name", ""),
                    "xUserId": author_data.get("id", ""),
                    "xVerified": author_data.get("verified", False),
                    "xFollowersCount": author_data.get("followers", 0),
                    "xProfileImageUrl": author_data.get("profilePicture", ""),
                })
            
            # Rate limit respect (10 req/s)
            if i + lookup_batch < len(tweet_ids):
                await asyncio.sleep(1)
        
        logger.info(f"Enriched {len(enriched)}/{len(raw_results)} tweets with engagement data")
        return enriched

    # ================================================================
    # TWEET FORMAT CONVERTER
    # ================================================================
    @staticmethod
    def normalize_tweets(xquik_results: List[dict]) -> List[dict]:
        """
        Xquik extraction sonuçlarını Type Hype'ın mevcut formatına dönüştür.
        
        Xquik extraction format:
            {id, xUserId, xUsername, xDisplayName, xProfileImageUrl, xFollowersCount, xVerified,
             tweetText, tweetId, tweetCreatedAt, createdAt}
        
        Xquik webhook/event format:
            {id, text, author{id, userName, name}, replyCount, retweetCount, likeCount, createdAt}
        
        Type Hype format:
            {tweet_id, content, likes, retweets, replies, is_thread, has_media, tweet_created_at}
        """
        seen_ids = set()
        normalized = []

        for item in xquik_results:
            # Extraction format vs event format algıla
            is_extraction = "tweetText" in item
            
            tid = item.get("tweetId") if is_extraction else item.get("id")
            text = item.get("tweetText", "") if is_extraction else item.get("text", "")
            
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)

            # RT'leri atla
            if item.get("isRetweet"):
                continue

            # Çok kısa tweetleri atla
            word_count = len(text.split())
            if word_count < 4:
                continue

            # Sadece link olan tweetleri atla
            if text.startswith("http") and word_count <= 2:
                continue

            if is_extraction:
                # Extraction format (post_extractor / tweet_search_extractor / enriched)
                normalized.append({
                    "tweet_id": tid,
                    "content": text,
                    "likes": item.get("likeCount", 0),
                    "retweets": item.get("retweetCount", 0),
                    "replies": item.get("replyCount", 0),
                    "bookmarks": item.get("bookmarkCount", 0),
                    "quotes": item.get("quoteCount", 0),
                    "views": item.get("viewCount", 0),
                    "is_thread": False,
                    "has_media": False,
                    "tweet_created_at": item.get("tweetCreatedAt"),
                    "author_username": item.get("xUsername"),
                    "author_name": item.get("xDisplayName"),
                    "author_id": item.get("xUserId"),
                    "is_verified": item.get("xVerified", False),
                    "followers_count": item.get("xFollowersCount", 0),
                    "avatar_url": (item.get("xProfileImageUrl") or "").replace("_normal.", "_400x400."),
                })
            else:
                # Event/webhook format
                author = item.get("author", {})
                normalized.append({
                    "tweet_id": tid,
                    "content": text,
                    "likes": item.get("likeCount", 0),
                    "retweets": item.get("retweetCount", 0),
                    "replies": item.get("replyCount", 0),
                    "bookmarks": item.get("bookmarkCount", 0),
                    "quotes": item.get("quoteCount", 0),
                    "is_thread": bool(item.get("conversationId") == tid and item.get("replyCount", 0) > 0),
                    "has_media": bool(item.get("media")),
                    "tweet_created_at": item.get("createdAt"),
                    "author_username": author.get("userName"),
                    "author_name": author.get("name"),
                    "author_id": author.get("id"),
                    "is_verified": author.get("isBlueVerified", False),
                })

        logger.info(f"Normalized {len(normalized)} tweets from {len(xquik_results)} raw")
        return normalized


# Singleton instance
xquik = XquikClient()

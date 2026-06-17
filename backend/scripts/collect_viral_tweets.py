#!/usr/bin/env python3
# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Viral Tweet Collector v2 — Kalite Odaklı
==========================================
Yüksek kaliteli viral tweet'leri toplar, analiz eder ve Supabase'e kaydeder.

Veri Kaynakları:
  1. Timeline scraping (hesap bazlı)
  2. Twitter Advanced Search (min_faves:500 lang:tr)
  3. Trending topic bazlı toplama

Kalite Filtreleri:
  - Min 500 like (gerçek viral)
  - Min %2 engagement rate
  - Bot/spam filtreleme (follower/following ratio)
  - Hesap yaşı kontrolü (min 6 ay)
  - İçerik deduplikasyonu (similarity hash)

Otomatik Etiketleme:
  - hook_type, sentiment, content_format, cta_type

Kullanım:
    python collect_viral_tweets.py                       # Tüm hesaplardan topla
    python collect_viral_tweets.py --niche tech           # Sadece tech nişi
    python collect_viral_tweets.py --handle elonmusk      # Tek hesap
    python collect_viral_tweets.py --min-likes 1000       # Minimum 1000 like
    python collect_viral_tweets.py --search "AI lang:tr"  # Advanced search
    python collect_viral_tweets.py --dry-run              # Kaydetmeden test et
"""

import asyncio
import json
import os
import sys
import re
import hashlib
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from decimal import Decimal

import httpx

# Proje root'unu path'e ekle
SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

logger = logging.getLogger("viral_collector")

# ─── Config ───────────────────────────────────────────────────────────────────

DATA_DIR = BACKEND_DIR / "data"
ACCOUNTS_FILE = DATA_DIR / "viral_accounts.json"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://awlsmfhxcsifabyanwfv.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

# Rate limiting
DELAY_BETWEEN_USERS = 10.0      # saniye (pagination ile daha fazla istek, rate limit'e dikkat)
DELAY_BETWEEN_REQUESTS = 2.0    # saniye
DELAY_BETWEEN_SEARCHES = 12.0   # search daha agresif, daha fazla bekle
MAX_RETRIES = 3
RETRY_DELAY = 10.0

# ─── Kalite Eşikleri ─────────────────────────────────────────────────────────

DEFAULT_MIN_LIKES = 1000
MIN_LIKES_TR = 1000                # Model eğitimi için gerçek viral (Berkay: 20 like patates!)
MIN_LIKES_EN = 1000                # EN hesaplar için de aynı eşik
MIN_ENGAGEMENT_RATE = 2.0          # %2
MIN_ENGAGEMENT_RATE_TR = 1.0       # TR için daha düşük engagement rate eşiği
MIN_IMPRESSIONS = 100_000          # varsa kontrol et
MIN_IMPRESSIONS_TR = 10_000        # TR için daha düşük impressions eşiği
MIN_FOLLOWER_FOLLOWING_RATIO = 0.1 # altı = muhtemel bot
MIN_ACCOUNT_AGE_DAYS = 180         # 6 ay

# ─── Hook Type Patterns ──────────────────────────────────────────────────────

HOOK_PATTERNS = {
    "contrarian": [
        r"(?:unpopular|controversial)\s*(?:opinion|take)",
        r"herkes(?:in)?\s+(?:yanıl|yanlış)",
        r"kimse\s+(?:konuşmuyor|bilmiyor|söylemiyor)",
        r"nobody\s+(?:talks?|knows?)\s+about",
        r"hot\s+take",
        r"(?:aksini|tersini)\s+düşün",
    ],
    "curiosity": [
        r"(?:nasıl|neden|niçin)\s+.{5,}(?:\?|:)",
        r"(?:how|why|what\s+if)\s+.{5,}(?:\?|:)",
        r"(?:merak|biliyor\s+muydunuz|did\s+you\s+know)",
        r"(?:sır|secret|hidden|gizli)",
    ],
    "data": [
        r"\d+[%₺$€kKmMbB]\s",
        r"(?:araştırma|study|data|research|istatistik|statistics)",
        r"(?:son\s+\d+|last\s+\d+|past\s+\d+)",
        r"\d+\s*(?:yıl|ay|gün|year|month|day)",
    ],
    "story": [
        r"(?:hikaye|story|bir\s+gün|one\s+day)",
        r"(?:\d+\s*yıl\s*önce|\d+\s*years?\s*ago)",
        r"(?:başıma|yaşadım|happened\s+to\s+me)",
        r"(?:thread|🧵)",
    ],
    "challenge": [
        r"(?:yapabilir\s+misiniz|can\s+you|try\s+this|deneyin)",
        r"(?:challenge|meydan\s+okuma)",
        r"(?:iddia|bahis|bet\s+you)",
    ],
    "confession": [
        r"(?:itiraf|confession|admit|kabul\s+ediyorum)",
        r"(?:söyleyeceğim|I'll\s+say\s+it|truth\s+is)",
        r"(?:cesaret|courage)",
    ],
    "list": [
        r"(?:\d+\s+(?:madde|şey|thing|tip|tool|lesson|rule|way))",
        r"(?:liste|list|top\s+\d+)",
        r"(?:1[\.\)\/]|①)",
    ],
    "hot_take": [
        r"(?:hot\s+take|sert\s+yorum|gerçek\s+şu)",
        r"(?:harsh|sert|acı)\s+(?:truth|gerçek)",
        r"(?:cope|deal\s+with\s+it|kabul\s+edin)",
    ],
}

CTA_PATTERNS = {
    "bookmark_trigger": [
        r"(?:kaydet|bookmark|save\s+this|ileride|later)",
        r"(?:🔖|📌|💾)",
    ],
    "reply_trigger": [
        r"(?:yaz|comment|reply|yorumla|ne\s+düşünüyorsun|what\s+do\s+you\s+think)",
        r"(?:👇|⬇️)",
    ],
    "rt_trigger": [
        r"(?:paylaş|share|RT|retweet|spread)",
        r"(?:herkes\s+görmeli|everyone\s+should\s+see)",
    ],
    "follow_trigger": [
        r"(?:takip\s+et|follow\s+me|follow\s+for|takipte\s+kal)",
        r"(?:daha\s+fazlası\s+için|for\s+more)",
    ],
}

SENTIMENT_PATTERNS = {
    "provocative": [
        r"(?:saçmalık|bullshit|ridiculous|absurd|rezalet|skandal)",
        r"(?:utanç|shame|disgrace|yazık|pathetic)",
        r"(?:uyanın|wake\s+up|stop\s+being)",
    ],
    "negative": [
        r"(?:üzücü|sad|unfortunately|maalesef|sorun|problem|kötü|bad|worst)",
        r"(?:endişe|worry|concern|tehlike|danger|risk)",
    ],
    "positive": [
        r"(?:harika|amazing|incredible|awesome|muhteşem|başarı|success|gurur|proud)",
        r"(?:tebrik|congratul|bravo|süper|great|fantastic|mükemmel)",
        r"(?:🎉|🚀|💪|❤️|🔥|⭐)",
    ],
}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def extract_hashtags(text: str) -> List[str]:
    return re.findall(r"#(\w+)", text)


def extract_mentions(text: str) -> List[str]:
    return re.findall(r"@(\w+)", text)


def detect_media_type(tweet: dict) -> str:
    media = tweet.get("media") or tweet.get("extended_entities", {}).get("media", [])
    if not media:
        return "none"
    if isinstance(media, list) and len(media) > 0:
        if len(media) > 1:
            return "carousel"
        mt = media[0].get("type", "")
        if mt == "video":
            return "video"
        if mt == "animated_gif":
            return "gif"
        if mt == "photo":
            return "image"
    return "none"


def has_link(text: str) -> bool:
    # t.co linkleri hariç gerçek link var mı
    urls = re.findall(r"https?://\S+", text)
    return any(not u.startswith("https://t.co/") for u in urls)


def parse_twitter_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except (ValueError, TypeError):
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None


def calculate_engagement_rate(tweet: dict, followers: int = 0) -> float:
    likes = tweet.get("likeCount", 0) or tweet.get("likes", 0) or 0
    rts = tweet.get("retweetCount", 0) or tweet.get("retweets", 0) or 0
    replies = tweet.get("replyCount", 0) or tweet.get("replies", 0) or 0
    total = likes + rts + replies

    if followers and followers > 0:
        return round(total / followers * 100, 6)
    impressions = tweet.get("impressions", 0) or tweet.get("views", 0) or 0
    if impressions and impressions > 0:
        return round(total / impressions * 100, 6)
    return 0.0


def compute_similarity_hash(text: str) -> str:
    """Normalize edilmiş metnin hash'i - benzer tweetleri yakalar."""
    normalized = text.lower().strip()
    normalized = re.sub(r"https?://\S+", "", normalized)  # linkleri kaldır
    normalized = re.sub(r"@\w+", "", normalized)           # mention'ları kaldır
    normalized = re.sub(r"#\w+", "", normalized)           # hashtag'leri kaldır
    normalized = re.sub(r"\s+", " ", normalized).strip()   # whitespace normalize
    # İlk 200 karakter yeterli (kopyala-yapıştır tweetler genelde aynı başlar)
    return hashlib.sha256(normalized[:200].encode()).hexdigest()[:16]


def classify_hook_type(text: str) -> Optional[str]:
    """Tweet'in hook tipini belirle."""
    text_lower = text.lower()
    for hook_type, patterns in HOOK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return hook_type
    return None


def detect_cta(text: str) -> Tuple[bool, str]:
    """CTA var mı ve tipi ne?"""
    text_lower = text.lower()
    for cta_type, patterns in CTA_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True, cta_type
    return False, "none"


def detect_sentiment(text: str) -> str:
    """Basit kural bazlı sentiment tespiti."""
    text_lower = text.lower()
    # Öncelik: provocative > negative > positive > neutral
    for sentiment, patterns in SENTIMENT_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return sentiment
    return "neutral"


def detect_content_format(tweet: dict) -> str:
    """Tweet'in format tipini belirle."""
    text = tweet.get("text", "") or tweet.get("full_text", "") or ""
    conversation_id = tweet.get("conversationId") or tweet.get("conversation_id_str")
    tweet_id = str(tweet.get("id") or tweet.get("id_str", ""))
    in_reply_to = tweet.get("in_reply_to_status_id_str") or tweet.get("inReplyToStatusId")
    is_quote = tweet.get("is_quote_status", False) or tweet.get("quoted_status_id_str")

    if is_quote:
        return "quote"
    if in_reply_to:
        if conversation_id == tweet_id:
            return "thread_start"
        return "thread_part" if conversation_id else "reply"
    # Thread başlangıcı: kendi conversation_id'si ve 🧵 veya 1/ pattern
    if re.search(r"(?:🧵|thread|1[/\.\)])", text.lower()):
        return "thread_start"
    return "single"


# ─── Account Quality Checker ─────────────────────────────────────────────────

class AccountQualityChecker:
    """Hesap kalitesi kontrolü - bot/spam filtreleme."""

    @staticmethod
    def check_account(user_data: dict) -> Tuple[bool, str]:
        """Hesabın kaliteli olup olmadığını kontrol et. (ok, reason) döner."""
        if not user_data:
            return False, "no_data"

        followers = user_data.get("followers_count", 0) or 0
        following = user_data.get("friends_count", 0) or user_data.get("following_count", 0) or 0
        created_at = user_data.get("created_at", "")

        # Follower/following ratio kontrolü
        # Not: GraphQL timeline response'unda follower sayısı gelmeyebilir
        # Bu durumda check'i atla (follower=0 ve following=0)
        if followers > 0 and following > 0:
            ratio = followers / following
            if ratio < MIN_FOLLOWER_FOLLOWING_RATIO:
                return False, f"low_ff_ratio:{ratio:.2f}"

        # Hesap yaşı kontrolü
        if created_at:
            account_date = parse_twitter_date(created_at)
            if account_date:
                age_days = (datetime.now(timezone.utc) - account_date).days
                if age_days < MIN_ACCOUNT_AGE_DAYS:
                    return False, f"too_young:{age_days}d"

        return True, "ok"

    @staticmethod
    def get_account_age_days(user_data: dict) -> Optional[int]:
        created_at = user_data.get("created_at", "")
        if created_at:
            account_date = parse_twitter_date(created_at)
            if account_date:
                return (datetime.now(timezone.utc) - account_date).days
        return None

    @staticmethod
    def get_ff_ratio(user_data: dict) -> Optional[float]:
        followers = user_data.get("followers_count", 0) or 0
        following = user_data.get("friends_count", 0) or user_data.get("following_count", 0) or 0
        if following > 0:
            return round(followers / following, 4)
        return None


# ─── Tweet Collector ─────────────────────────────────────────────────────────

class TweetCollector:
    """Kalite odaklı viral tweet collector."""

    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase_url = supabase_url.rstrip("/")
        self.supabase_key = supabase_key
        self._http: Optional[httpx.AsyncClient] = None
        self._graphql = None
        self._existing_hashes: set = set()  # deduplikasyon cache
        self._quality_checker = AccountQualityChecker()

    async def _get_http(self) -> httpx.AsyncClient:
        if not self._http:
            self._http = httpx.AsyncClient(timeout=30.0)
        return self._http

    async def close(self):
        if self._http:
            await self._http.aclose()

    def _get_graphql(self):
        """DEPRECATED: TwitterGraphQL kaldırıldı (Xquik'e geçildi). Bu script güncellenmeli."""
        logger.warning("collect_viral_tweets: TwitterGraphQL kaldırıldı, Xquik kullanın")
        return None

    # ─── Deduplikasyon ────────────────────────────────────────────────────

    async def load_existing_hashes(self):
        """Supabase'deki mevcut similarity_hash'leri yükle."""
        http = await self._get_http()
        url = f"{self.supabase_url}/rest/v1/viral_tweets?select=similarity_hash&similarity_hash=not.is.null"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
        }
        try:
            resp = await http.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                self._existing_hashes = {r["similarity_hash"] for r in data if r.get("similarity_hash")}
                logger.info(f"📦 {len(self._existing_hashes)} mevcut hash yüklendi (deduplikasyon)")
        except Exception as e:
            logger.warning(f"Hash yükleme hatası: {e}")

    def _is_duplicate_content(self, similarity_hash: str) -> bool:
        """Bu içerik zaten var mı?"""
        return similarity_hash in self._existing_hashes

    # ─── Tweet Toplama ────────────────────────────────────────────────────

    async def collect_user_tweets(self, handle: str, limit: int = 200, max_pages: int = 5) -> Tuple[List[dict], Optional[dict]]:
        """
        Bir hesaptan tweet'leri topla (cursor pagination ile derin toplama).
        Returns: (tweets, user_data)
        """
        logger.info(f"📥 @{handle} - {limit} tweet çekiliyor (max {max_pages} sayfa)...")
        graphql = self._get_graphql()
        if not graphql:
            logger.error(f"❌ @{handle} - GraphQL client yok")
            return [], None

        try:
            tweets = await graphql.get_user_tweets(handle, count=min(limit, 200), max_pages=max_pages)
            if not tweets:
                logger.warning(f"⚠️ @{handle} - Tweet bulunamadı")
                return [], None

            # User data'yı ilk tweet'ten çıkar
            user_data = None
            if tweets and isinstance(tweets[0], dict):
                author = tweets[0].get("author", {})
                if author:
                    user_data = {
                        "username": author.get("username", handle),
                        "name": author.get("name", ""),
                        "followers_count": author.get("followers_count", 0),
                        "friends_count": author.get("friends_count", 0),
                        "verified": author.get("verified", False),
                        "created_at": author.get("created_at", ""),
                    }

            logger.info(f"✅ @{handle} - {len(tweets)} tweet çekildi")
            return tweets or [], user_data
        except Exception as e:
            logger.error(f"❌ @{handle} - Hata: {e}")
            return [], None

    async def search_tweets(self, query: str, limit: int = 100) -> List[dict]:
        """
        Twitter Advanced Search ile tweet ara.
        Örnek query: "min_faves:500 lang:tr"
        """
        logger.info(f"🔍 Search: '{query}' (limit={limit})")
        graphql = self._get_graphql()
        if not graphql:
            logger.error("❌ GraphQL client yok, search yapılamıyor")
            return []

        # GraphQL client'ta search varsa kullan
        if hasattr(graphql, 'search_tweets'):
            try:
                results = await graphql.search_tweets(query, count=limit)
                logger.info(f"✅ Search: {len(results)} sonuç bulundu")
                return results or []
            except Exception as e:
                logger.error(f"❌ Search hatası: {e}")
                return []

        # Bird CLI search deneyelim
        if hasattr(graphql, 'use_bird') and graphql.use_bird:
            try:
                result = graphql._bird_run(
                    ["search", query, "-n", str(limit)],
                    timeout=90,
                )
                if result:
                    logger.info(f"✅ Bird search: {len(result)} sonuç")
                    return result
            except Exception as e:
                logger.error(f"❌ Bird search hatası: {e}")

        logger.warning("⚠️ Search desteklenmiyor (GraphQL veya Bird CLI)")
        return []

    # ─── Kalite Filtreleme ────────────────────────────────────────────────

    async def filter_viral(
        self,
        tweets: List[dict],
        user_data: Optional[dict] = None,
        min_likes: int = DEFAULT_MIN_LIKES,
        language: str = "en",
    ) -> List[dict]:
        """Çok katmanlı kalite filtreleme. Dil bazlı eşikler."""
        if not tweets:
            return []

        followers = 0
        if user_data:
            followers = user_data.get("followers_count", 0) or 0

        # CLI min_likes her zaman geçerli (override yok!)
        # Dil bazlı engagement/impression eşikleri farklı olabilir
        effective_min_likes = min_likes  # CLI değeri korunuyor
        effective_min_eng = MIN_ENGAGEMENT_RATE
        effective_min_imp = MIN_IMPRESSIONS
        if language == "tr":
            effective_min_eng = MIN_ENGAGEMENT_RATE_TR
            effective_min_imp = MIN_IMPRESSIONS_TR

        passed = []
        stats = {"total": len(tweets), "low_likes": 0, "low_engagement": 0,
                 "low_impressions": 0, "duplicate": 0, "passed": 0}

        for t in tweets:
            text = t.get("text", "") or t.get("full_text", "") or ""
            likes = t.get("likeCount", 0) or t.get("likes", 0) or 0
            rts = t.get("retweetCount", 0) or t.get("retweets", 0) or 0
            replies = t.get("replyCount", 0) or t.get("replies", 0) or 0
            impressions = t.get("views", 0) or t.get("impressions", 0) or 0

            # 1. Minimum like kontrolü (dil bazlı)
            if likes < effective_min_likes:
                stats["low_likes"] += 1
                continue

            # 2. Engagement rate kontrolü (dil bazlı)
            eng_rate = calculate_engagement_rate(t, followers)
            if eng_rate > 0 and eng_rate < effective_min_eng:
                stats["low_engagement"] += 1
                continue

            # 3. Impressions kontrolü (dil bazlı, varsa)
            if impressions > 0 and impressions < effective_min_imp:
                stats["low_impressions"] += 1
                continue

            # 4. Deduplikasyon
            sim_hash = compute_similarity_hash(text)
            if self._is_duplicate_content(sim_hash):
                stats["duplicate"] += 1
                continue

            # Geçti!
            self._existing_hashes.add(sim_hash)
            passed.append(t)
            stats["passed"] += 1

        lang_note = f" (lang={language}, min_likes={effective_min_likes})" if language == "tr" else ""
        logger.info(
            f"🔥 Filtre{lang_note}: {stats['passed']}/{stats['total']} geçti | "
            f"düşük_like={stats['low_likes']} düşük_eng={stats['low_engagement']} "
            f"düşük_imp={stats['low_impressions']} duplicate={stats['duplicate']}"
        )
        return passed

    # ─── Normalize & Enrich ───────────────────────────────────────────────

    def _normalize_tweet(
        self,
        tweet: dict,
        niche: str = "",
        language: str = "tr",
        user_data: Optional[dict] = None,
        source: str = "timeline",
    ) -> dict:
        """Tweet'i zengin şemayla normalize et."""
        text = tweet.get("text", "") or tweet.get("full_text", "") or tweet.get("content", "")
        tweet_id = tweet.get("id") or tweet.get("id_str")
        if not tweet_id or not text:
            return {}

        try:
            tweet_id = int(tweet_id)
        except (ValueError, TypeError):
            return {}

        author = tweet.get("author", {})
        posted_at = parse_twitter_date(tweet.get("createdAt") or tweet.get("created_at"))
        followers = (user_data or {}).get("followers_count", 0) or author.get("followers_count", 0) or 0
        following = (user_data or {}).get("friends_count", 0) or author.get("friends_count", 0) or 0

        # Otomatik etiketleme
        hook_type = classify_hook_type(text)
        has_cta, cta_type = detect_cta(text)
        sentiment = detect_sentiment(text)
        content_format = detect_content_format(tweet)
        similarity_hash = compute_similarity_hash(text)

        # FF ratio
        ff_ratio = round(followers / following, 4) if following > 0 else None

        # Account age
        account_age = None
        if user_data:
            account_age = self._quality_checker.get_account_age_days(user_data)

        return {
            "id": tweet_id,
            "author_handle": author.get("username", "") or tweet.get("author_handle", ""),
            "author_name": author.get("name", "") or tweet.get("author_name", ""),
            "author_followers": followers,
            "author_verified": (user_data or {}).get("verified", False) or author.get("verified", False),
            "content": text,
            "likes": tweet.get("likeCount", 0) or tweet.get("likes", 0) or 0,
            "retweets": tweet.get("retweetCount", 0) or tweet.get("retweets", 0) or 0,
            "replies": tweet.get("replyCount", 0) or tweet.get("replies", 0) or 0,
            "quotes": tweet.get("quoteCount", 0) or tweet.get("quotes", 0) or 0,
            "bookmarks": tweet.get("bookmarkCount", 0) or tweet.get("bookmarks", 0) or 0,
            "impressions": tweet.get("views", 0) or tweet.get("impressions", 0) or 0,
            "media_type": detect_media_type(tweet),
            "has_link": has_link(text),
            "hashtags": extract_hashtags(text),
            "mentions": extract_mentions(text),
            "language": language,
            "tweet_length": len(text),
            "posted_at": posted_at.isoformat() if posted_at else None,
            "posted_hour": posted_at.hour if posted_at else None,
            "niche": niche,
            "engagement_rate": calculate_engagement_rate(tweet, followers),
            "is_thread": content_format in ("thread_start", "thread_part"),
            "thread_position": None,
            "hook_type": hook_type,
            "has_cta": has_cta,
            "cta_type": cta_type,
            "sentiment": sentiment,
            "content_format": content_format,
            "source": source,
            "follower_following_ratio": ff_ratio,
            "account_age_days": account_age,
            "similarity_hash": similarity_hash,
        }

    # ─── Supabase ─────────────────────────────────────────────────────────

    async def save_to_supabase(self, tweets: List[dict]) -> int:
        """Tweet'leri Supabase'e kaydet (upsert)."""
        if not tweets:
            return 0

        http = await self._get_http()
        url = f"{self.supabase_url}/rest/v1/viral_tweets"
        headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

        saved = 0
        batch_size = 50
        for i in range(0, len(tweets), batch_size):
            batch = [t for t in tweets[i:i + batch_size] if t.get("id")]
            if not batch:
                continue

            for attempt in range(MAX_RETRIES):
                try:
                    resp = await http.post(url, json=batch, headers=headers)
                    if resp.status_code in (200, 201):
                        saved += len(batch)
                        logger.info(f"💾 {len(batch)} tweet kaydedildi (toplam: {saved})")
                        break
                    elif resp.status_code == 409:
                        # Duplicate - tek tek upsert
                        for t in batch:
                            try:
                                r = await http.post(url, json=[t], headers=headers)
                                if r.status_code in (200, 201):
                                    saved += 1
                            except Exception:
                                pass
                        break
                    else:
                        logger.warning(f"⚠️ Supabase hata ({resp.status_code}): {resp.text[:300]}")
                        if attempt < MAX_RETRIES - 1:
                            await asyncio.sleep(RETRY_DELAY)
                except Exception as e:
                    logger.error(f"❌ Supabase bağlantı hatası: {e}")
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY)

        return saved

    # ─── Ana Toplama ──────────────────────────────────────────────────────

    async def collect_from_accounts(
        self,
        accounts: List[dict],
        min_likes: int = DEFAULT_MIN_LIKES,
        dry_run: bool = False,
        max_pages: int = 5,
    ) -> dict:
        """Hesap listesinden viral tweet'leri topla."""
        stats = {
            "total_accounts": len(accounts),
            "processed": 0,
            "skipped_quality": 0,
            "total_tweets_fetched": 0,
            "total_viral": 0,
            "total_saved": 0,
            "errors": [],
            "started_at": datetime.now(timezone.utc).isoformat(),
        }

        for i, account in enumerate(accounts):
            handle = account["handle"]
            niche = account.get("niche", "")
            language = account.get("language", "tr")

            logger.info(f"\n{'='*60}")
            logger.info(f"[{i+1}/{len(accounts)}] @{handle} ({niche}, {language})")
            logger.info(f"{'='*60}")

            try:
                # Tweet'leri ve user data'yı çek (pagination ile derin toplama)
                tweets, user_data = await self.collect_user_tweets(handle, limit=200, max_pages=max_pages)
                stats["total_tweets_fetched"] += len(tweets)

                if not tweets:
                    stats["processed"] += 1
                    await asyncio.sleep(DELAY_BETWEEN_USERS)
                    continue

                # Hesap kalite kontrolü
                if user_data:
                    ok, reason = self._quality_checker.check_account(user_data)
                    if not ok:
                        logger.warning(f"⚠️ @{handle} hesap kalitesi düşük: {reason} — atlanıyor")
                        stats["skipped_quality"] += 1
                        stats["processed"] += 1
                        await asyncio.sleep(DELAY_BETWEEN_USERS)
                        continue

                    ff = self._quality_checker.get_ff_ratio(user_data)
                    age = self._quality_checker.get_account_age_days(user_data)
                    logger.info(f"👤 Followers: {user_data.get('followers_count',0):,} | "
                                f"FF ratio: {ff} | Yaş: {age}g | "
                                f"Verified: {user_data.get('verified', False)}")

                # Viral filtrele (dil bazlı eşikler)
                viral = await self.filter_viral(tweets, user_data=user_data, min_likes=min_likes, language=language)
                stats["total_viral"] += len(viral)

                # Normalize et
                normalized = []
                for t in viral:
                    n = self._normalize_tweet(t, niche=niche, language=language,
                                              user_data=user_data, source="timeline")
                    if n:
                        normalized.append(n)

                # Kaydet
                if normalized and not dry_run:
                    saved = await self.save_to_supabase(normalized)
                    stats["total_saved"] += saved
                elif normalized and dry_run:
                    logger.info(f"🏃 DRY RUN: {len(normalized)} tweet kaydedilecekti")
                    for n in normalized[:3]:  # İlk 3'ü göster
                        logger.info(f"  📝 [{n['hook_type'] or '?'}] [{n['sentiment']}] "
                                    f"❤️{n['likes']} 🔄{n['retweets']} | {n['content'][:80]}...")
                    stats["total_saved"] += len(normalized)

                stats["processed"] += 1

            except Exception as e:
                logger.error(f"❌ @{handle} - Beklenmeyen hata: {e}")
                stats["errors"].append({"handle": handle, "error": str(e)})
                stats["processed"] += 1

            # Rate limiting
            await asyncio.sleep(DELAY_BETWEEN_USERS)

        stats["finished_at"] = datetime.now(timezone.utc).isoformat()
        return stats

    async def collect_from_search(
        self,
        queries: List[str],
        niche: str = "",
        language: str = "tr",
        min_likes: int = DEFAULT_MIN_LIKES,
        dry_run: bool = False,
    ) -> dict:
        """Advanced Search ile viral tweet topla."""
        stats = {"queries": len(queries), "total_found": 0, "total_saved": 0, "errors": []}

        for query in queries:
            logger.info(f"\n🔍 Search: '{query}'")
            try:
                tweets = await self.search_tweets(query, limit=100)
                stats["total_found"] += len(tweets)

                if tweets:
                    viral = await self.filter_viral(tweets, min_likes=min_likes)
                    normalized = []
                    for t in viral:
                        n = self._normalize_tweet(t, niche=niche, language=language, source="search")
                        if n:
                            normalized.append(n)

                    if normalized and not dry_run:
                        saved = await self.save_to_supabase(normalized)
                        stats["total_saved"] += saved
                    elif normalized:
                        stats["total_saved"] += len(normalized)

            except Exception as e:
                logger.error(f"❌ Search hatası '{query}': {e}")
                stats["errors"].append({"query": query, "error": str(e)})

            await asyncio.sleep(DELAY_BETWEEN_SEARCHES)

        return stats

    async def collect_all(
        self,
        accounts: List[dict],
        min_likes: int = DEFAULT_MIN_LIKES,
        dry_run: bool = False,
        search_queries: Optional[List[str]] = None,
        max_pages: int = 5,
    ) -> dict:
        """Tüm kaynaklardan topla: timeline + search."""

        # Mevcut hash'leri yükle (deduplikasyon)
        if not dry_run:
            await self.load_existing_hashes()

        # 1. Hesap bazlı toplama (pagination ile derin toplama)
        account_stats = await self.collect_from_accounts(accounts, min_likes=min_likes, dry_run=dry_run, max_pages=max_pages)

        # 2. Search bazlı toplama
        search_stats = {"total_found": 0, "total_saved": 0}
        if search_queries:
            search_stats = await self.collect_from_search(
                search_queries, min_likes=min_likes, dry_run=dry_run
            )

        return {
            "accounts": account_stats,
            "search": search_stats,
            "grand_total_saved": account_stats["total_saved"] + search_stats.get("total_saved", 0),
        }


# ─── Hesap Listesi ────────────────────────────────────────────────────────────

def load_accounts(
    accounts_file: Path = ACCOUNTS_FILE,
    niche: Optional[str] = None,
    handle: Optional[str] = None,
) -> List[dict]:
    if not accounts_file.exists():
        logger.error(f"Hesap dosyası bulunamadı: {accounts_file}")
        return []

    with open(accounts_file) as f:
        data = json.load(f)

    accounts = data.get("accounts", [])

    if handle:
        accounts = [a for a in accounts if a["handle"].lower() == handle.lower()]
    elif niche:
        accounts = [a for a in accounts if a.get("niche") == niche]

    accounts.sort(key=lambda a: a.get("priority", 99))
    return accounts


# ─── Default Search Queries ───────────────────────────────────────────────────

DEFAULT_SEARCH_QUERIES = {
    "tr": [
        "min_faves:500 lang:tr -filter:replies",
        "min_faves:1000 lang:tr filter:media",
        "min_faves:500 lang:tr (yapay zeka OR AI OR teknoloji)",
        "min_faves:500 lang:tr (borsa OR kripto OR bitcoin OR yatırım)",
        "min_faves:500 lang:tr (girişimcilik OR startup OR pazarlama)",
    ],
    "en": [
        "min_faves:2000 lang:en (startup OR SaaS OR founder) -filter:replies",
        "min_faves:5000 lang:en (AI OR artificial intelligence OR ChatGPT)",
        "min_faves:2000 lang:en (marketing OR growth OR copywriting)",
    ],
}


# ─── CLI ──────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Viral Tweet Collector v2 — Kalite Odaklı")
    parser.add_argument("--niche", type=str, help="Sadece belirli niş (tech, finans, ...)")
    parser.add_argument("--handle", type=str, help="Tek hesap")
    parser.add_argument("--min-likes", type=int, default=DEFAULT_MIN_LIKES, help=f"Minimum like eşiği (default: {DEFAULT_MIN_LIKES})")
    parser.add_argument("--max-pages", type=int, default=5, help="Max pagination pages per account (default: 5, ~100 tweets)")
    parser.add_argument("--search", type=str, help="Manuel search query")
    parser.add_argument("--with-search", action="store_true", help="Default search query'lerini de çalıştır")
    parser.add_argument("--search-only", action="store_true", help="Sadece search, timeline atla")
    parser.add_argument("--dry-run", action="store_true", help="Kaydetmeden test et")
    parser.add_argument("--verbose", "-v", action="store_true", help="Detaylı log")
    args = parser.parse_args()

    # Logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Supabase key kontrolü
    if not SUPABASE_KEY and not args.dry_run:
        logger.error("SUPABASE_SERVICE_KEY env değişkeni ayarlanmamış!")
        sys.exit(1)

    # Search queries
    search_queries = None
    if args.search:
        search_queries = [args.search]
    elif args.with_search or args.search_only:
        search_queries = DEFAULT_SEARCH_QUERIES.get("tr", []) + DEFAULT_SEARCH_QUERIES.get("en", [])

    # Hesapları yükle
    accounts = []
    if not args.search_only:
        accounts = load_accounts(niche=args.niche, handle=args.handle)
        if not accounts and not search_queries:
            logger.error("Toplanacak hesap veya search query bulunamadı!")
            sys.exit(1)

    logger.info(f"🚀 Viral Tweet Collector v2 başlatılıyor...")
    logger.info(f"📋 {len(accounts)} hesap | min_likes={args.min_likes} | "
                f"min_eng={MIN_ENGAGEMENT_RATE}% | search={bool(search_queries)} | dry_run={args.dry_run}")
    logger.info(f"🔒 Kalite: min_ff_ratio={MIN_FOLLOWER_FOLLOWING_RATIO} | "
                f"min_account_age={MIN_ACCOUNT_AGE_DAYS}d | min_impressions={MIN_IMPRESSIONS:,}")

    # Topla
    collector = TweetCollector(SUPABASE_URL, SUPABASE_KEY)
    try:
        stats = await collector.collect_all(
            accounts,
            min_likes=args.min_likes,
            dry_run=args.dry_run,
            search_queries=search_queries,
            max_pages=args.max_pages,
        )
    finally:
        await collector.close()

    # Sonuçları göster
    acc = stats.get("accounts", {})
    srch = stats.get("search", {})

    logger.info(f"\n{'='*60}")
    logger.info(f"📊 SONUÇLAR")
    logger.info(f"{'='*60}")
    if acc:
        logger.info(f"  📋 Timeline Toplama:")
        logger.info(f"     Hesaplar: {acc.get('total_accounts', 0)} | İşlenen: {acc.get('processed', 0)}")
        logger.info(f"     Kalite filtresi: {acc.get('skipped_quality', 0)} hesap atlandı")
        logger.info(f"     Çekilen tweet: {acc.get('total_tweets_fetched', 0):,}")
        logger.info(f"     Viral tweet: {acc.get('total_viral', 0):,}")
        logger.info(f"     Kaydedilen: {acc.get('total_saved', 0):,}")
        if acc.get("errors"):
            logger.warning(f"     Hatalar: {len(acc['errors'])}")
            for err in acc["errors"]:
                logger.warning(f"       - @{err['handle']}: {err['error']}")
    if srch.get("total_found"):
        logger.info(f"  🔍 Search Toplama:")
        logger.info(f"     Bulunan: {srch.get('total_found', 0):,}")
        logger.info(f"     Kaydedilen: {srch.get('total_saved', 0):,}")

    logger.info(f"  ────────────────────────────")
    logger.info(f"  🏆 TOPLAM KAYDEDİLEN: {stats.get('grand_total_saved', 0):,}")


if __name__ == "__main__":
    asyncio.run(main())

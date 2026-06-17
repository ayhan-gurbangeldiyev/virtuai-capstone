#!/usr/bin/env python3
# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Type Hype - Konu Bazlı Viral Tweet Toplama (Apify)

Hesap yerine keyword/topic arayarak viral tweet toplar.
Her niche için önceden tanımlı arama sorguları kullanır.

Kullanım:
    python collect_apify_topics.py                       # Tüm topic'ler
    python collect_apify_topics.py --niche tech          # Sadece tech topic'leri
    python collect_apify_topics.py --lang tr             # Sadece TR topic'ler
    python collect_apify_topics.py --lang en --niche haber  # EN haber
    python collect_apify_topics.py --dry-run             # Query'leri göster
    python collect_apify_topics.py --min-likes 500       # Min like override
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("❌ httpx gerekli: pip install httpx")


# ============================================================
# Topic Configs: niche → language → [search keywords]
# ============================================================
TOPICS = {
    "tech": {
        "tr": [
            "yapay zeka",
            "yazılım geliştirme",
            "teknoloji",
            "startup Türkiye",
            "mobil uygulama",
            "siber güvenlik",
            "veri bilimi",
            "açık kaynak",
            "SaaS",
            "girişimcilik teknoloji",
        ],
        "en": [
            "artificial intelligence",
            "software engineering",
            "startup founder",
            "open source",
            "machine learning",
            "SaaS product",
            "developer tools",
            "tech industry",
        ],
    },
    "finans": {
        "tr": [
            "borsa İstanbul",
            "yatırım tavsiyesi",
            "ekonomi Türkiye",
            "dolar kuru",
            "faiz oranı",
            "finansal özgürlük",
            "hisse senedi",
            "altın yatırım",
        ],
        "en": [
            "stock market",
            "investing advice",
            "financial freedom",
            "personal finance",
            "trading strategy",
            "Wall Street",
        ],
    },
    "pazarlama": {
        "tr": [
            "dijital pazarlama",
            "sosyal medya stratejisi",
            "marka yönetimi",
            "içerik pazarlama",
            "SEO Türkçe",
            "reklam kampanyası",
            "e-ticaret",
            "growth hacking",
        ],
        "en": [
            "digital marketing",
            "brand strategy",
            "content marketing",
            "social media growth",
            "copywriting tips",
            "marketing strategy",
        ],
    },
    "kripto": {
        "tr": [
            "bitcoin Türkiye",
            "kripto para",
            "ethereum",
            "web3 Türkiye",
            "blockchain teknoloji",
            "DeFi",
            "NFT",
        ],
        "en": [
            "bitcoin",
            "crypto trading",
            "ethereum",
            "web3",
            "blockchain",
            "DeFi",
        ],
    },
    "mizah": {
        "tr": [
            "hayat be",
            "itiraf ediyorum",
            "bence herkes",
            "türk insanı",
            "kahve molası",
            "pazartesi sendromu",
            "Z kuşağı",
        ],
    },
    "kisisel_gelisim": {
        "tr": [
            "motivasyon",
            "kişisel gelişim",
            "başarı hikayesi",
            "verimlilik",
            "disiplin",
            "hedef belirleme",
            "alışkanlık",
        ],
        "en": [
            "self improvement",
            "productivity tips",
            "personal growth",
            "success mindset",
            "habits",
            "discipline",
        ],
    },
    "icerik_uretici": {
        "tr": [
            "içerik üretici",
            "youtuber Türk",
            "creator economy",
            "sosyal medya gelir",
            "içerik stratejisi",
        ],
        "en": [
            "content creator",
            "creator economy",
            "YouTube growth",
            "TikTok strategy",
        ],
    },
    "haber": {
        "en": [
            "breaking news",
            "world news today",
            "tech news",
            "AI news",
            "science discovery",
            "climate change news",
            "space exploration",
            "geopolitics",
        ],
    },
    "spor": {
        "tr": [
            "Galatasaray",
            "Fenerbahçe",
            "Beşiktaş",
            "Trabzonspor",
            "süper lig",
            "şampiyonlar ligi",
            "milli takım",
            "transfer dönemi",
            "futbol Türkiye",
            "basketbol Türkiye",
            "Euroleague",
            "derbi",
        ],
        "en": [
            "Premier League",
            "Champions League",
            "NBA highlights",
            "football transfer",
            "World Cup",
            "Formula 1",
        ],
    },
    "yasam": {
        "tr": [
            "hayat dersi",
            "ilişki",
            "aşk",
            "evlilik",
            "arkadaşlık",
            "mutluluk",
            "İstanbul hayatı",
            "Türkiye gerçekleri",
            "30lu yaşlar",
            "20li yaşlar",
            "nostalji",
            "günlük hayat",
        ],
        "en": [
            "life lessons",
            "relationships",
            "adulting",
            "dating advice",
            "work life balance",
            "mental health",
        ],
    },
    "kariyer": {
        "tr": [
            "iş hayatı",
            "mülakat",
            "CV hazırlama",
            "maaş",
            "terfi",
            "istifa",
            "uzaktan çalışma",
            "freelance Türkiye",
            "kurumsal hayat",
            "staj",
        ],
        "en": [
            "career advice",
            "job interview",
            "remote work",
            "salary negotiation",
            "tech career",
            "layoffs",
            "freelancing",
        ],
    },
    "saglik": {
        "tr": [
            "sağlıklı beslenme",
            "fitness",
            "mental sağlık",
            "psikoloji",
            "spor yapma",
            "diyet",
            "uyku düzeni",
            "stres yönetimi",
        ],
        "en": [
            "mental health awareness",
            "fitness motivation",
            "nutrition tips",
            "healthy lifestyle",
            "workout routine",
        ],
    },
    "egitim": {
        "tr": [
            "üniversite",
            "YKS",
            "sınav",
            "eğitim sistemi",
            "öğretmen",
            "okul",
            "online eğitim",
            "yurt dışı eğitim",
            "burs",
        ],
        "en": [
            "education system",
            "college advice",
            "online learning",
            "student life",
            "scholarship",
        ],
    },
    "bilim": {
        "tr": [
            "bilim insanı",
            "uzay",
            "evrim",
            "fizik",
            "doğa",
            "iklim değişikliği",
            "arkeoloji keşif",
        ],
        "en": [
            "science discovery",
            "space exploration NASA",
            "physics breakthrough",
            "climate science",
            "biology research",
        ],
    },
    "kultur": {
        "tr": [
            "sinema Türk",
            "dizi önerisi",
            "kitap önerisi",
            "müzik Türkçe",
            "Netflix Türkiye",
            "konser",
            "tiyatro",
            "sanat",
        ],
        "en": [
            "movie review",
            "Netflix series",
            "book recommendation",
            "music industry",
            "pop culture",
        ],
    },
}


# ============================================================
# Config
# ============================================================
APIFY_ACTOR = "apidojo~tweet-scraper"
APIFY_BASE = "https://api.apify.com/v2"
MIN_LIKES = 1000
BATCH_SIZE = 5
POLL_INTERVAL = 10
MAX_WAIT = 600


# ============================================================
# .env loader
# ============================================================
def load_env():
    for candidate in [
        Path(__file__).resolve().parents[1] / ".env",
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
    ]:
        if candidate.is_file():
            for line in candidate.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("\"'"))
            return


# ============================================================
# Apify API client
# ============================================================
class ApifyClient:
    def __init__(self, token: str):
        self.token = token
        self.client = httpx.Client(timeout=60)
        self.headers = {"Authorization": f"Bearer {token}"}

    def start_run(self, search_terms: list[str], max_items: int = 5000) -> dict:
        url = f"{APIFY_BASE}/acts/{APIFY_ACTOR}/runs"
        payload = {
            "searchTerms": search_terms,
            "sort": "Top",
            "maxItems": max_items,
        }
        resp = self.client.post(url, json=payload, headers=self.headers)
        resp.raise_for_status()
        return resp.json()["data"]

    def wait_for_run(self, run_id: str) -> dict:
        url = f"{APIFY_BASE}/actor-runs/{run_id}"
        start = time.time()
        while time.time() - start < MAX_WAIT:
            resp = self.client.get(url, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data.get("status")
            if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                return data
            time.sleep(POLL_INTERVAL)
        return {"status": "TIMEOUT_LOCAL"}

    def get_dataset_items(self, dataset_id: str) -> list[dict]:
        url = f"{APIFY_BASE}/datasets/{dataset_id}/items"
        items = []
        offset = 0
        limit = 1000
        while True:
            resp = self.client.get(
                url,
                headers=self.headers,
                params={"offset": offset, "limit": limit, "format": "json"},
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            items.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return items


# ============================================================
# Supabase client
# ============================================================
class SupabaseClient:
    def __init__(self, url: str, key: str):
        self.base = url.rstrip("/")
        self.headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal,resolution=merge-duplicates",
        }
        self.client = httpx.Client(timeout=30)

    def upsert_tweets(self, tweets: list[dict]) -> int:
        if not tweets:
            return 0
        # Batch içi dedup: aynı similarity_hash veya id olan tweetleri filtrele
        seen_hashes = set()
        seen_ids = set()
        deduped = []
        for t in tweets:
            h = t.get("similarity_hash", "")
            tid = t.get("id")
            if h and h in seen_hashes:
                continue
            if tid and tid in seen_ids:
                continue
            if h:
                seen_hashes.add(h)
            if tid:
                seen_ids.add(tid)
            deduped.append(t)

        url = f"{self.base}/rest/v1/viral_tweets"
        saved = 0
        for i in range(0, len(deduped), 100):
            batch = deduped[i:i + 100]
            resp = self.client.post(url, json=batch, headers=self.headers)
            if resp.status_code in (200, 201):
                saved += len(batch)
            else:
                print(f"  ⚠️  Supabase hata ({resp.status_code}): {resp.text[:200]}")
        return saved

    def count_tweets(self, params: str = "") -> int:
        url = f"{self.base}/rest/v1/viral_tweets"
        h = {**self.headers, "Prefer": "count=exact"}
        resp = self.client.get(url, headers=h, params={"select": "id", "limit": "0"})
        return int(resp.headers.get("content-range", "*/0").split("/")[-1])


# ============================================================
# Tweet parser (same as collect_apify.py)
# ============================================================
def compute_similarity_hash(content: str, author: str) -> str:
    normalized = content.lower().strip()
    return hashlib.sha256(f"{author}:{normalized}".encode()).hexdigest()[:32]


def is_news_link_dump(text: str, has_link: bool) -> bool:
    """Haber link dump tespiti: URL + kısa metin = düşük kalite."""
    if not has_link:
        return False
    # URL'yi çıkar, kalan metin kısa mı?
    import re
    clean = re.sub(r'https?://\S+', '', text).strip()
    words = [w for w in clean.split() if len(w) > 1]
    return len(words) < 15


def parse_apify_tweet(tweet: dict, niche: str, min_likes: int) -> dict | None:
    """Apify tweet format'ını Supabase viral_tweets tablosuna çevir."""
    text = tweet.get("text") or tweet.get("full_text") or tweet.get("tweetText") or ""
    if not text or text.startswith("RT @"):
        return None

    # Çok kısa tweet filtresi
    words = [w for w in text.split() if len(w) > 1]
    if len(words) < 5:
        return None

    author = tweet.get("author", {})
    handle = (
        author.get("userName") or author.get("screen_name")
        or tweet.get("user", {}).get("screen_name")
        or tweet.get("author_handle") or ""
    )
    if not handle:
        return None

    # Mega account filtresi
    mega_accounts = {"elonmusk", "jack", "sundarpichai", "sataborasu", "billgates", "jeffbezos"}
    if handle.lower() in mega_accounts:
        return None

    author_name = author.get("name") or author.get("displayName") or ""
    author_followers = author.get("followers") or author.get("followersCount") or 0
    author_verified = author.get("isVerified") or author.get("isBlueVerified") or False

    likes = tweet.get("likeCount") or tweet.get("favorite_count") or tweet.get("likes") or 0
    retweets = tweet.get("retweetCount") or tweet.get("retweet_count") or tweet.get("retweets") or 0
    replies = tweet.get("replyCount") or tweet.get("reply_count") or tweet.get("replies") or 0
    quotes = tweet.get("quoteCount") or tweet.get("quote_count") or tweet.get("quotes") or 0
    bookmarks = tweet.get("bookmarkCount") or tweet.get("bookmarks") or 0
    views = tweet.get("viewCount") or tweet.get("views") or tweet.get("impressions") or 0

    if likes < min_likes:
        return None

    # Tweet ID
    tweet_id = tweet.get("id") or tweet.get("id_str") or tweet.get("tweetId") or ""
    if tweet_id:
        try:
            tweet_id = int(str(tweet_id).strip())
        except (ValueError, TypeError):
            tweet_id = None

    # Language detection
    lang = tweet.get("lang") or tweet.get("language") or "unknown"
    if lang not in ("tr", "en"):
        tr_chars = set("çğıöşüÇĞİÖŞÜ")
        if any(c in tr_chars for c in text):
            lang = "tr"
        else:
            lang = "en"

    # Media type
    has_link = "http" in text.lower()
    media_type = "none"
    media = tweet.get("media") or tweet.get("extendedEntities", {}).get("media") or tweet.get("entities", {}).get("media") or []
    if media:
        if isinstance(media, list) and len(media) > 0:
            first = media[0] if isinstance(media[0], dict) else {}
            mtype = first.get("type") or first.get("media_type") or ""
            if "video" in mtype.lower():
                media_type = "video"
            elif len(media) > 1:
                media_type = "carousel"
            else:
                media_type = "image"

    # News link dump filtresi
    if is_news_link_dump(text, has_link):
        return None

    # Hashtags & mentions
    entities = tweet.get("entities") or {}
    hashtags = [h.get("tag") or h.get("text") or "" for h in (entities.get("hashtags") or tweet.get("hashtags") or [])]
    mentions = [m.get("username") or m.get("screen_name") or "" for m in (entities.get("user_mentions") or entities.get("mentions") or [])]

    # Engagement rate
    total_engagement = likes + retweets + replies + quotes + bookmarks
    engagement_rate = (total_engagement / max(views, 1)) * 100 if views > 0 else 0.0

    created = tweet.get("createdAt") or tweet.get("created_at") or ""
    now = datetime.now(timezone.utc).isoformat()

    is_thread = bool(tweet.get("isSelfThread") or tweet.get("conversationCount", 0) > 0)

    content_format = "single"
    if "\n" in text and len(text.split("\n")) > 3:
        content_format = "multi_line"
    if "🧵" in text or "thread" in text.lower():
        content_format = "thread"

    posted_hour = 0
    if created:
        try:
            from dateutil.parser import parse as dtparse
            dt = dtparse(created)
            posted_hour = dt.hour
        except Exception:
            pass

    sim_hash = compute_similarity_hash(text, handle)

    row = {
        "author_handle": handle,
        "author_name": author_name or "",
        "author_followers": int(author_followers),
        "author_verified": bool(author_verified),
        "content": text,
        "likes": int(likes),
        "retweets": int(retweets),
        "replies": int(replies),
        "quotes": int(quotes),
        "bookmarks": int(bookmarks),
        "impressions": int(views),
        "media_type": media_type,
        "has_link": has_link,
        "hashtags": hashtags if hashtags else [],
        "mentions": mentions if mentions else [],
        "language": lang,
        "tweet_length": len(text),
        "posted_at": created or now,
        "collected_at": now,
        "niche": niche,
        "engagement_rate": round(engagement_rate, 4),
        "is_thread": is_thread,
        "has_cta": False,
        "cta_type": "none",
        "sentiment": "neutral",
        "content_format": content_format,
        "posted_hour": posted_hour,
        "source": "apify_topic",
        "similarity_hash": sim_hash,
    }

    if tweet_id:
        row["id"] = tweet_id

    return row


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Konu bazlı viral tweet toplama (Apify)")
    parser.add_argument("--niche", type=str, help="Sadece bu niche")
    parser.add_argument("--lang", type=str, choices=["tr", "en"], help="Sadece bu dil")
    parser.add_argument("--dry-run", action="store_true", help="Query'leri göster, çalıştırma")
    parser.add_argument("--min-likes", type=int, default=1000, help="Minimum like (default: 1000)")
    parser.add_argument("--max-items", type=int, default=5000, help="Batch başına max tweet")
    args = parser.parse_args()

    load_env()

    apify_token = os.environ.get("APIFY_API_TOKEN", "")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not apify_token:
        sys.exit("❌ APIFY_API_TOKEN gerekli")
    if not supabase_url or not supabase_key:
        sys.exit("❌ SUPABASE_URL ve SUPABASE_SERVICE_KEY gerekli")

    # Build queries from TOPICS config
    queries = []
    for niche, lang_map in TOPICS.items():
        if args.niche and niche != args.niche:
            continue
        for lang, keywords in lang_map.items():
            if args.lang and lang != args.lang:
                continue
            for kw in keywords:
                lang_filter = f"lang:{lang}" if lang == "tr" else ""
                query = f"{kw} min_faves:{args.min_likes} -filter:retweets since:2023-01-01"
                if lang_filter:
                    query += f" {lang_filter}"
                queries.append({
                    "query": query,
                    "niche": niche,
                    "lang": lang,
                    "keyword": kw,
                })

    print(f"🔍 Konu Bazlı Viral Tweet Collection")
    print(f"   Toplam query: {len(queries)} | Min likes: {args.min_likes}")
    print(f"   Batch size: {BATCH_SIZE}")
    print()

    # Niche breakdown
    niche_counts = defaultdict(int)
    for q in queries:
        niche_counts[f"{q['niche']} ({q['lang']})"] += 1
    print("   Query dağılımı:")
    for key, cnt in sorted(niche_counts.items()):
        print(f"      {key}: {cnt} query")
    print()

    if args.dry_run:
        print("🏁 Dry-run: Tüm query'ler:")
        for i, q in enumerate(queries):
            print(f"   [{q['niche']}/{q['lang']}] {q['query']}")
        estimated_cost = len(queries) / BATCH_SIZE * 0.40 * 50 / 1000
        print(f"\n   Tahmini batch: {(len(queries) + BATCH_SIZE - 1) // BATCH_SIZE}")
        print(f"   Tahmini maliyet: ~${estimated_cost:.2f}+")
        return

    # Init clients
    apify = ApifyClient(apify_token)
    sb = SupabaseClient(supabase_url, supabase_key)
    initial_count = sb.count_tweets()
    print(f"📊 Mevcut DB: {initial_count} tweet")
    print()

    # Process queries in batches of BATCH_SIZE
    # Each batch = 5 queries (Apify limit: 5 searchTerms per run)
    batches = []
    for i in range(0, len(queries), BATCH_SIZE):
        batches.append(queries[i:i + BATCH_SIZE])

    total_saved = 0
    total_fetched = 0
    total_filtered = 0
    failed_batches = []

    for batch_idx, batch in enumerate(batches):
        search_terms = [q["query"] for q in batch]
        keywords = [q["keyword"] for q in batch]
        niches = {q["niche"] for q in batch}

        print(f"━━━ Batch {batch_idx + 1}/{len(batches)} ━━━")
        print(f"   Keywords: {', '.join(keywords)}")
        print(f"   Niches: {', '.join(niches)}")

        try:
            run_data = apify.start_run(search_terms, args.max_items)
            run_id = run_data["id"]
            dataset_id = run_data.get("defaultDatasetId", "")
            print(f"   🏃 Run: {run_id}")

            result = apify.wait_for_run(run_id)
            status = result.get("status", "UNKNOWN")

            if status != "SUCCEEDED":
                print(f"   ❌ Başarısız: {status}")
                failed_batches.append({"batch": batch_idx, "keywords": keywords, "status": status})
                continue

            if not dataset_id:
                dataset_id = result.get("defaultDatasetId", "")
            items = apify.get_dataset_items(dataset_id)
            total_fetched += len(items)
            print(f"   📥 {len(items)} tweet çekildi")

            # Parse: topic-based, niche'i ilk eşleşen query'den al
            # Aynı batch'te birden fazla niche olabilir, tweet content'e bakarak tahmin edemeyiz
            # En iyi yaklaşım: batch'te tek niche varsa onu kullan, birden fazlaysa dominant niche
            dominant_niche = batch[0]["niche"]  # İlk query'nin niche'i

            parsed = []
            for item in items:
                tweet = parse_apify_tweet(item, dominant_niche, args.min_likes)
                if tweet:
                    parsed.append(tweet)

            total_filtered += len(items) - len(parsed)
            print(f"   🔍 Filtre: {len(parsed)} geçti, {len(items) - len(parsed)} elendi")

            if parsed:
                saved = sb.upsert_tweets(parsed)
                total_saved += saved
                print(f"   💾 {saved} tweet kaydedildi")

        except Exception as e:
            print(f"   ❌ Hata: {e}")
            failed_batches.append({"batch": batch_idx, "keywords": keywords, "error": str(e)})

        if batch_idx < len(batches) - 1:
            print(f"   ⏳ 5s bekleniyor...")
            time.sleep(5)

    # Final report
    final_count = sb.count_tweets()
    print()
    print("=" * 60)
    print("📊 SONUÇ RAPORU")
    print("=" * 60)
    print(f"   Toplam batch: {len(batches)}")
    print(f"   Başarılı: {len(batches) - len(failed_batches)}")
    print(f"   Başarısız: {len(failed_batches)}")
    print(f"   Çekilen tweet: {total_fetched}")
    print(f"   Filtrelenen: {total_filtered}")
    print(f"   Kaydedilen: {total_saved}")
    print(f"   DB önceki: {initial_count}")
    print(f"   DB şimdi: {final_count}")
    print(f"   Yeni eklenen: {final_count - initial_count}")

    if failed_batches:
        print(f"\n   ⚠️ Başarısız:")
        for fb in failed_batches:
            print(f"      Batch {fb['batch']}: {fb.get('keywords', '?')} → {fb.get('status', fb.get('error', '?'))}")

    # Save report
    report_path = Path(__file__).parent.parent / "data" / "apify_topic_report.json"
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_queries": len(queries),
        "total_batches": len(batches),
        "total_fetched": total_fetched,
        "total_saved": total_saved,
        "db_before": initial_count,
        "db_after": final_count,
        "failed_batches": failed_batches,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n   📄 Rapor: {report_path}")
    print(f"\n🏁 Tamamlandı!")


if __name__ == "__main__":
    main()

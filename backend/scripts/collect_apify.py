#!/usr/bin/env python3
# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
"""
Type Hype - Apify Tweet Scraper ile Viral Tweet Toplama
Actor: apidojo/tweet-scraper

312 hesaptan 1000+ like'lı tüm tweetleri çeker, Supabase'e kaydeder.

Kullanım:
    python collect_apify.py                          # Tüm hesaplar
    python collect_apify.py --niche tech             # Sadece tech niche
    python collect_apify.py --test                   # İlk 3 hesapla test
    python collect_apify.py --dry-run                # Query'leri göster, çalıştırma
"""

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("❌ httpx gerekli: pip install httpx")


# ============================================================
# Config
# ============================================================
APIFY_ACTOR = "apidojo~tweet-scraper"
APIFY_BASE = "https://api.apify.com/v2"
MIN_LIKES = 1000
BATCH_SIZE = 5  # Apify max 5 searchTerms per run
POLL_INTERVAL = 10  # seconds between status checks
MAX_WAIT = 600  # max 10 min per run
ACCOUNTS_FILE = Path(__file__).parent.parent / "data" / "viral_accounts.json"


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
        """Actor run'ı başlat."""
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
        """Run bitene kadar bekle."""
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
        """Dataset'ten tüm item'ları çek."""
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
        """Batch upsert (similarity_hash dedup)."""
        if not tweets:
            return 0
        url = f"{self.base}/rest/v1/viral_tweets"
        # Batch in chunks of 100
        saved = 0
        for i in range(0, len(tweets), 100):
            batch = tweets[i:i + 100]
            resp = self.client.post(url, json=batch, headers=self.headers)
            if resp.status_code in (200, 201):
                saved += len(batch)
            else:
                print(f"  ⚠️  Supabase hata ({resp.status_code}): {resp.text[:200]}")
        return saved

    def count_tweets(self) -> int:
        url = f"{self.base}/rest/v1/viral_tweets"
        h = {**self.headers, "Prefer": "count=exact"}
        resp = self.client.get(url, headers=h, params={"select": "id", "limit": "0"})
        return int(resp.headers.get("content-range", "*/0").split("/")[-1])


# ============================================================
# Tweet parser: Apify format → Supabase format
# ============================================================
def compute_similarity_hash(content: str, author: str) -> str:
    """Content + author based dedup hash."""
    normalized = content.lower().strip()
    return hashlib.sha256(f"{author}:{normalized}".encode()).hexdigest()[:32]


def parse_apify_tweet(tweet: dict, niche: str) -> dict | None:
    """Apify tweet format'ını Supabase viral_tweets tablosuna çevir."""
    # Apify tweet fields
    text = tweet.get("text") or tweet.get("full_text") or tweet.get("tweetText") or ""
    if not text or text.startswith("RT @"):
        return None

    author = tweet.get("author", {})
    handle = (
        author.get("userName") or author.get("screen_name")
        or tweet.get("user", {}).get("screen_name")
        or tweet.get("author_handle") or ""
    )
    if not handle:
        return None

    author_name = author.get("name") or author.get("displayName") or ""
    author_followers = author.get("followers") or author.get("followersCount") or 0
    author_verified = author.get("isVerified") or author.get("isBlueVerified") or False

    # Engagement metrics
    likes = (
        tweet.get("likeCount") or tweet.get("favorite_count")
        or tweet.get("likes") or 0
    )
    retweets = (
        tweet.get("retweetCount") or tweet.get("retweet_count")
        or tweet.get("retweets") or 0
    )
    replies = (
        tweet.get("replyCount") or tweet.get("reply_count")
        or tweet.get("replies") or 0
    )
    quotes = (
        tweet.get("quoteCount") or tweet.get("quote_count")
        or tweet.get("quotes") or 0
    )
    bookmarks = tweet.get("bookmarkCount") or tweet.get("bookmarks") or 0
    views = (
        tweet.get("viewCount") or tweet.get("views")
        or tweet.get("impressions") or 0
    )

    if likes < MIN_LIKES:
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
    media_type = "none"
    has_link = "http" in text.lower()
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

    # Hashtags & mentions
    entities = tweet.get("entities") or {}
    hashtags = [
        h.get("tag") or h.get("text") or ""
        for h in (entities.get("hashtags") or tweet.get("hashtags") or [])
    ]
    mentions = [
        m.get("username") or m.get("screen_name") or ""
        for m in (entities.get("user_mentions") or entities.get("mentions") or [])
    ]

    # Engagement rate
    total_engagement = likes + retweets + replies + quotes + bookmarks
    engagement_rate = (total_engagement / max(views, 1)) * 100 if views > 0 else 0.0

    # Posted time
    created = tweet.get("createdAt") or tweet.get("created_at") or ""
    now = datetime.now(timezone.utc).isoformat()

    # Thread detection
    is_thread = bool(tweet.get("isSelfThread") or tweet.get("conversationCount", 0) > 0)

    # Content analysis
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
        "source": "apify",
        "similarity_hash": sim_hash,
    }

    # Tweet ID varsa ekle (yoksa DB auto-generate eder)
    if tweet_id:
        row["id"] = tweet_id

    return row


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Apify ile viral tweet toplama")
    parser.add_argument("--niche", type=str, help="Sadece bu niche'i topla")
    parser.add_argument("--lang", type=str, choices=["tr", "en"], help="Sadece bu dildeki hesaplar")
    parser.add_argument("--test", action="store_true", help="İlk 3 hesapla test")
    parser.add_argument("--dry-run", action="store_true", help="Query'leri göster, çalıştırma")
    parser.add_argument("--max-items", type=int, default=5000, help="Batch başına max tweet")
    parser.add_argument("--min-likes", type=int, default=1000, help="Minimum like")
    args = parser.parse_args()

    global MIN_LIKES
    MIN_LIKES = args.min_likes

    load_env()

    # API keys
    apify_token = os.environ.get("APIFY_API_TOKEN", "")
    supabase_url = os.environ.get("SUPABASE_URL", "")
    supabase_key = os.environ.get("SUPABASE_SERVICE_KEY", "")

    if not apify_token:
        sys.exit("❌ APIFY_API_TOKEN gerekli")
    if not supabase_url or not supabase_key:
        sys.exit("❌ SUPABASE_URL ve SUPABASE_SERVICE_KEY gerekli")

    # Load accounts
    if not ACCOUNTS_FILE.exists():
        sys.exit(f"❌ Accounts dosyası bulunamadı: {ACCOUNTS_FILE}")

    with open(ACCOUNTS_FILE) as f:
        data = json.load(f)
    accounts = data["accounts"]

    # Filter by niche
    if args.niche:
        accounts = [a for a in accounts if a["niche"] == args.niche]
        if not accounts:
            sys.exit(f"❌ '{args.niche}' niche'inde hesap yok")

    # Filter by language
    if args.lang:
        accounts = [a for a in accounts if a.get("language") == args.lang]
        if not accounts:
            sys.exit(f"❌ '{args.lang}' dilinde hesap yok")

    if args.test:
        accounts = accounts[:3]

    print(f"🚀 Apify Viral Tweet Collection")
    print(f"   Hesap: {len(accounts)} | Min likes: {args.min_likes}")
    print(f"   Actor: {APIFY_ACTOR}")
    print(f"   Batch size: {BATCH_SIZE}")
    print()

    # Group accounts by niche for reporting
    by_niche = defaultdict(list)
    for a in accounts:
        by_niche[a["niche"]].append(a)

    # Build search queries: one per account
    queries = []
    for acc in accounts:
        handle = acc["handle"]
        niche = acc["niche"]
        query = f"from:{handle} min_faves:{args.min_likes} -filter:retweets since:2023-01-01"
        queries.append({"query": query, "handle": handle, "niche": niche})

    print(f"📋 {len(queries)} query hazırlandı")
    print(f"   Niche dağılımı:")
    for niche, accs in sorted(by_niche.items(), key=lambda x: -len(x[1])):
        print(f"      {niche}: {len(accs)} hesap")
    print()

    if args.dry_run:
        print("🏁 Dry-run: İlk 10 query:")
        for q in queries[:10]:
            print(f"   [{q['niche']}] {q['query']}")
        print(f"\n   Tahmini maliyet: ~${len(queries) * 0.40 * 50 / 1000:.2f}-${len(queries) * 0.40 * 500 / 1000:.2f}")
        return

    # Init clients
    apify = ApifyClient(apify_token)
    sb = SupabaseClient(supabase_url, supabase_key)

    initial_count = sb.count_tweets()
    print(f"📊 Mevcut tweet sayısı: {initial_count}")
    print()

    # Process in batches
    batches = []
    for i in range(0, len(queries), BATCH_SIZE):
        batches.append(queries[i:i + BATCH_SIZE])

    total_saved = 0
    total_fetched = 0
    total_filtered = 0
    failed_batches = []
    batch_results = []

    for batch_idx, batch in enumerate(batches):
        handles = [q["handle"] for q in batch]
        niches = [q["niche"] for q in batch]
        search_terms = [q["query"] for q in batch]

        print(f"━━━ Batch {batch_idx + 1}/{len(batches)} ━━━")
        print(f"   Hesaplar: {', '.join(f'@{h}' for h in handles)}")

        try:
            # Start run
            run_data = apify.start_run(search_terms, args.max_items)
            run_id = run_data["id"]
            dataset_id = run_data.get("defaultDatasetId", "")
            print(f"   🏃 Run başladı: {run_id}")

            # Wait for completion
            result = apify.wait_for_run(run_id)
            status = result.get("status", "UNKNOWN")

            if status != "SUCCEEDED":
                print(f"   ❌ Run başarısız: {status}")
                failed_batches.append({"batch": batch_idx, "handles": handles, "status": status})
                continue

            # Get results
            if not dataset_id:
                dataset_id = result.get("defaultDatasetId", "")
            items = apify.get_dataset_items(dataset_id)
            total_fetched += len(items)
            print(f"   📥 {len(items)} tweet çekildi")

            # Parse and filter
            parsed = []
            for item in items:
                # Determine niche from author handle
                item_handle = (
                    item.get("author", {}).get("userName")
                    or item.get("user", {}).get("screen_name")
                    or ""
                ).lower()

                # Find niche for this handle
                niche = "genel"
                for q in batch:
                    if q["handle"].lower() == item_handle:
                        niche = q["niche"]
                        break

                tweet = parse_apify_tweet(item, niche)
                if tweet:
                    parsed.append(tweet)

            total_filtered += len(items) - len(parsed)
            print(f"   🔍 Filtre: {len(parsed)} geçti, {len(items) - len(parsed)} elendi")

            # Save to Supabase
            if parsed:
                saved = sb.upsert_tweets(parsed)
                total_saved += saved
                print(f"   💾 {saved} tweet kaydedildi")

            batch_results.append({
                "batch": batch_idx,
                "handles": handles,
                "fetched": len(items),
                "saved": len(parsed),
            })

        except Exception as e:
            print(f"   ❌ Hata: {e}")
            failed_batches.append({"batch": batch_idx, "handles": handles, "error": str(e)})

        # Rate limiting: batch arası bekleme
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
    print(f"   Başarılı: {len(batch_results)}")
    print(f"   Başarısız: {len(failed_batches)}")
    print(f"   Çekilen tweet: {total_fetched}")
    print(f"   Filtrelenen: {total_filtered}")
    print(f"   Kaydedilen: {total_saved}")
    print(f"   DB önceki: {initial_count}")
    print(f"   DB şimdi: {final_count}")
    print(f"   Yeni eklenen: {final_count - initial_count}")

    if failed_batches:
        print(f"\n   ⚠️  Başarısız batch'ler:")
        for fb in failed_batches:
            print(f"      Batch {fb['batch']}: {fb['handles']} → {fb.get('status', fb.get('error', '?'))}")

    # Save report
    report_path = Path(__file__).parent.parent / "data" / "apify_collection_report.json"
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_accounts": len(accounts),
        "total_batches": len(batches),
        "total_fetched": total_fetched,
        "total_saved": total_saved,
        "db_before": initial_count,
        "db_after": final_count,
        "failed_batches": failed_batches,
        "batch_results": batch_results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\n   📄 Rapor: {report_path}")
    print(f"\n🏁 Tamamlandı!")


if __name__ == "__main__":
    main()

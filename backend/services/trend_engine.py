"""Trend Discovery Engine - RSS + Twitter + GPT-4o Analysis

Multi-signal trend intelligence:
- RSS feeds (mevcut)
- Twitter signals (Tier 1 resmi, Tier 2 key people, Tier 3 keyword search)
- GPT-4o skorlama + context enrichment
- Topic clustering (dedup + merge)
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import List, Optional
import uuid

import feedparser
import httpx
from openai import OpenAI

from supabase import create_client

from services.trend_relevance import pre_filter, adjust_score, normalize_category
from services.story_dedup import story_tokens, deterministic_overlap

logger = logging.getLogger(__name__)

supabase_url = os.environ.get('SUPABASE_URL', '')
supabase_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
supabase = create_client(supabase_url, supabase_key) if supabase_url else None

openai_client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY', ''))


def _resolve_published_at(trend, source_item, items_by_title, all_items):
    """Resolve published_at from multiple sources, ensuring proper format."""
    from email.utils import parsedate_to_datetime

    # 1. GPT output
    pub = trend.get("published_at")
    if pub and str(pub) != "None" and str(pub).strip():
        # Validate it's a real date
        try:
            from datetime import datetime as dt
            dt.fromisoformat(str(pub).replace("Z", "+00:00"))
            return str(pub)
        except Exception:
            try:
                parsed = parsedate_to_datetime(str(pub))
                return parsed.isoformat()
            except Exception:
                pass

    # 2. Matched Twitter source item
    if source_item:
        raw = source_item.get("published_at") or source_item.get("created_at")
        if raw and str(raw) != "None":
            try:
                from datetime import datetime as dt
                dt.fromisoformat(str(raw).replace("Z", "+00:00"))
                return str(raw)
            except Exception:
                try:
                    parsed = parsedate_to_datetime(str(raw))
                    return parsed.isoformat()
                except Exception:
                    pass

    # 3. Match by URL in all_items
    trend_url = trend.get("url", "")
    for item in all_items:
        if item.get("url") == trend_url:
            raw = item.get("published_at")
            if raw and str(raw) != "None":
                try:
                    from datetime import datetime as dt
                    dt.fromisoformat(str(raw).replace("Z", "+00:00"))
                    return str(raw)
                except Exception:
                    try:
                        parsed = parsedate_to_datetime(str(raw))
                        return parsed.isoformat()
                    except Exception:
                        pass
            break

    return None



class TrendEngine:
    """Discovers and analyzes trends from RSS feeds using GPT-4o."""

    # Load feeds from config file, fallback to hardcoded defaults
    @staticmethod
    def _load_feeds():
        """Load RSS feeds from config/rss_feeds.json or use defaults."""
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "rss_feeds.json")
        try:
            with open(config_path, "r") as f:
                all_feeds = json.load(f)
            # Filter: only active feeds, use tier system
            active = [f for f in all_feeds if f.get("status") == "active"]
            # Tier 1: always included (most reliable sources)
            tier1 = [f for f in active if f.get("tier", 2) == 1]
            tier2 = [f for f in active if f.get("tier", 2) == 2]
            # Rotate tier 2: pick 5 per day based on day of year
            day_offset = datetime.now().timetuple().tm_yday % max(len(tier2), 1)
            selected_tier2 = (tier2[day_offset:] + tier2[:day_offset])[:5]
            feeds = tier1 + selected_tier2
            logger.info(f"Loaded {len(feeds)} feeds ({len(tier1)} tier1 + {len(selected_tier2)} tier2 rotating)")
            return [{"source": f["source"], "url": f["url"]} for f in feeds]
        except Exception as e:
            logger.warning(f"Could not load feeds config: {e}, using defaults")
            return [
                {"source": "OpenAI Blog", "url": "https://openai.com/blog/rss.xml"},
                {"source": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/"},
                {"source": "Google DeepMind", "url": "https://deepmind.google/blog/rss.xml"},
                {"source": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml"},
                {"source": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
                {"source": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
                {"source": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
            ]

    RSS_FEEDS = []  # populated in __init__

    def __init__(self):
        self.RSS_FEEDS = self._load_feeds()

    CATEGORIES = ["AI", "Dev", "Design", "Crypto", "Startup", "Marketing", "Business", "Science", "Lifestyle", "Education", "Entertainment", "News"]

    SCORE_THRESHOLD = 70  # Trends with score >= 70 are visible
    # Küratör force-seed taban skoru. Downstream query_trends `score>=75`
    # ister; 78 onu geçer ama 80-89 "gerçekten önemli" bandının altında
    # kalır (mega-hikâye taklidi yapmaz). Freshness hard-cap floor'dan SONRA
    # uygulanır → >48h küratör item'ı yine 75 altına düşüp doğal elenir.
    CURATOR_SCORE_FLOOR = 78

    MAX_AGE_HOURS = 72  # Son 72 saatin haberleri

    def _increment_feed_error(self, source_name: str):
        """Track RSS feed errors. Auto-disable after 5 consecutive failures."""
        try:
            from server import supabase as sb
            # Try Supabase rss_feeds table first
            feed = sb.table("rss_feeds").select("id,error_count").eq("source", source_name).limit(1).execute()
            if feed.data:
                feed_id = feed.data[0]["id"]
                new_count = (feed.data[0].get("error_count") or 0) + 1
                update = {"error_count": new_count, "last_status": "error"}
                if new_count >= 5:
                    update["is_active"] = False
                    logger.warning(f"Auto-disabled RSS feed '{source_name}' after {new_count} consecutive errors")
                sb.table("rss_feeds").update(update).eq("id", feed_id).execute()
        except Exception as e:
            logger.debug(f"Feed error tracking skipped for {source_name}: {e}")

    def _reset_feed_error(self, source_name: str):
        """Reset error count on successful fetch."""
        try:
            from server import supabase as sb
            sb.table("rss_feeds").update({"error_count": 0, "last_status": "ok", "last_fetched": datetime.now(timezone.utc).isoformat()}).eq("source", source_name).execute()
        except Exception:
            pass

    async def fetch_rss_trends(self) -> list:
        """Fetch RSS feed items from last 48 hours ONLY.

        - published_at zorunlu: tarihsiz item'lar atlanır
        - 48 saatten eski item'lar atlanır
        - Her item'a age_hours eklenir (GPT'ye gönderilir)
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.MAX_AGE_HOURS)
        items = []
        skipped_no_date = 0
        skipped_old = 0
        skipped_noise = 0

        async with httpx.AsyncClient(timeout=15.0) as client:
            for feed_info in self.RSS_FEEDS:
                try:
                    resp = await client.get(feed_info["url"])
                    # Limit feed size to prevent XML bomb attacks
                    if len(resp.text) > 2_000_000:  # 2MB max
                        logger.warning(f"RSS feed too large ({len(resp.text)} bytes): {feed_info['source']}")
                        continue
                    feed = feedparser.parse(resp.text)
                    for entry in feed.entries[:10]:
                        # Tarih parse et
                        published = None
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)

                        # Tarihsiz item = güvenilmez, atla
                        if not published:
                            skipped_no_date += 1
                            continue

                        # 48 saatten eski = atla
                        if published < cutoff:
                            skipped_old += 1
                            continue

                        # Gelecek tarihli kontrol (hatalı feed'ler)
                        if published > now + timedelta(hours=1):
                            continue

                        age_hours = round((now - published).total_seconds() / 3600, 1)
                        raw_content = entry.get("summary", "") or entry.get("description", "") or ""
                        title = entry.get("title", "")

                        # Pre-filter: block obvious noise before sending to GPT
                        if not pre_filter(title, raw_content[:300]):
                            skipped_noise += 1
                            continue

                        items.append({
                            "title": title,
                            "url": entry.get("link", ""),
                            "summary": raw_content[:500],
                            "raw_content": raw_content,
                            "source": feed_info["source"],
                            "source_type": "rss",
                            "published_at": published.isoformat(),
                            "age_hours": age_hours,
                        })
                    # Feed parsed successfully — reset error counter
                    self._reset_feed_error(feed_info["source"])
                except Exception as e:
                    logger.warning(f"RSS fetch failed for {feed_info['source']}: {e}")
                    # Track feed errors for auto-disable
                    self._increment_feed_error(feed_info["source"])

        logger.info(f"Fetched {len(items)} RSS items (skipped: {skipped_no_date} no-date, {skipped_old} old, {skipped_noise} noise)")
        return items

    async def fetch_twitter_signals(self) -> list:
        """Twitter batch + radar sinyallerini topla ve trend formatına dönüştür."""
        try:
            from services.twitter_trend_fetcher import fetch_all_twitter_signals
        except ImportError as e:
            logger.warning(f"twitter_trend_fetcher import hatası: {e}")
            return []

        signals = await fetch_all_twitter_signals()

        # Güvenilir-küratör whitelist'i (tek seferde) — item'lara _is_curator
        # bayrağı bas; 40-cap baypası + _seed_curator_trends bunu okur.
        try:
            from services.twitter_trend_fetcher import get_curator_usernames
            _curators = get_curator_usernames()
        except Exception:
            _curators = set()

        # Twitter sinyallerini RSS item formatına dönüştür (analyze_trends ile uyumlu)
        items = []
        for signal in signals:
            # Yaş hesapla
            age_hours = 0
            if signal.get("created_at"):
                try:
                    # Twitter tarih formatı: "Mon Feb 20 12:00:00 +0000 2026"
                    from email.utils import parsedate_to_datetime
                    tweet_dt = parsedate_to_datetime(signal["created_at"])
                    age_hours = (datetime.now(timezone.utc) - tweet_dt).total_seconds() / 3600
                except Exception:
                    age_hours = 1  # Parse edilemezse taze kabul et

            items.append({
                "title": signal["text"][:120],
                "source": f"@{signal['username']} (Twitter)",
                "url": signal["url"],
                "published_at": signal.get("created_at"),
                "age_hours": age_hours,
                "raw_content": signal["text"],
                "summary": signal["text"],
                # Twitter-specific metadata
                "_source_type": "twitter",
                "_tweet_id": signal["tweet_id"],
                "_twitter_account": signal["username"],
                "_tier": signal.get("tier", 3),
                "_likes": signal.get("likes", 0),
                "_retweets": signal.get("retweets", 0),
                "_views": signal.get("views", 0),
                "_is_curator": (signal.get("username") or "").lower() in _curators,
            })

        logger.info(f"Converted {len(items)} Twitter signals to trend items")
        return items

    async def analyze_trends(self, raw_items: list) -> list:
        """Analyze raw RSS items with GPT-4o and return scored trends.

        Each trend includes a primary source URL from the raw items.
        Strict freshness: age_hours included, scoring penalizes old items.
        """
        if not raw_items:
            return []

        # Sort by freshness (newest first)
        sorted_items = sorted(raw_items, key=lambda x: x.get("age_hours", 999))

        # Güvenilir-küratör 40-cap baypası: en taze 40 + 40'a giremeyen küratör
        # item'ları. upcornco ~2-3 tweet/gün → birkaç ekstra item, maliyet
        # ihmal edilebilir. (GPT yine atabilir; force-seed bundan bağımsız.)
        _head = sorted_items[:40]
        _head_urls = {it.get("url") for it in _head}
        _extra_curator = [
            it for it in sorted_items[40:]
            if it.get("_is_curator") and it.get("url") not in _head_urls
        ]
        analysis_items = _head + _extra_curator
        if _extra_curator:
            logger.info(
                f"[curator] 40-cap baypası: {len(_extra_curator)} küratör item GPT'ye eklendi"
            )

        # Build items text with age info for strict scoring
        # Sanitize inputs to prevent prompt injection from RSS/Twitter content
        def _sanitize(text: str, max_len: int = 500) -> str:
            """Strip control chars and limit length to prevent prompt injection."""
            if not text:
                return ""
            # Remove common injection patterns
            s = str(text)[:max_len]
            # Strip control characters except newlines
            s = "".join(c for c in s if c == "\n" or (ord(c) >= 32 and ord(c) != 127))
            return s.strip()

        items_text = ""
        for i, item in enumerate(analysis_items):
            items_text += f"\n--- Item {i+1} ---\n"
            items_text += f"Başlık: {_sanitize(item.get('title', ''), 200)}\n"
            items_text += f"Kaynak: {_sanitize(item.get('source', ''), 100)}\n"
            items_text += f"URL: {_sanitize(item.get('url', ''), 500)}\n"
            items_text += f"Yayın: {_sanitize(item.get('published_at', ''), 50)}\n"
            items_text += f"Yaş: {item.get('age_hours', '?')} saat önce\n"
            raw = _sanitize(item.get('raw_content', ''), 400)
            if raw:
                items_text += f"İçerik: {raw[:400]}\n"
            elif item.get('summary'):
                items_text += f"Özet: {item['summary'][:300]}\n"

        prompt = f"""Sen sert, seçici bir haber editörüsün. Haberleri analiz et, grupla ve ACIMADAN skorla.

TEMEL KURALLAR:
1. SADECE gerçek, doğrulanabilir haberler trend olabilir
2. Aynı konuyu farklı kaynaklar yazdıysa BİRLEŞTİR, duplicate trend oluşturma
3. HER trend'in url'i aşağıdaki item'lardan birinin GERÇEK URL'i olmalı. URL UYDURMA.
4. published_at değerini ilgili item'dan AYNEN al, değiştirme.
5. category TEK değer olmalı. Geçerli değerler: AI, Dev, Design, Crypto, Startup, Marketing, Business, Science, Lifestyle, Education, Entertainment, News. ASLA birleşik yazma (AI|Tech YANLIŞ, AI DOĞRU).

SELF-PROMO CEZASI:
- Şirketin kendi blog'unda kendi ürününü tanıttığı yazılar (örn: NVIDIA Blog'da NVIDIA ürünü, OpenAI Blog'da OpenAI ürünü) PRATİK DEĞER'den max 5 alır ve KAYNAK GÜVENİLİRLİĞİ'nden max 5 alır. Bunlar reklam, haber değil.

{items_text}

SKORLAMA KRİTERLERİ (toplam 100):

1. ETKİ BÜYÜKLÜĞÜ (0-25):
   - 20-25: Sektörü değiştiren olay (yeni büyük model, büyük satın alma, yasal düzenleme)
   - 12-18: Önemli ama sektör değiştirmeyen (yeni özellik, orta çaplı anlaşma)
   - 5-11: Küçük güncelleme, partnership, genişleme
   - 0-4: Rutin blog yazısı, araştırma makalesi, etkinlik duyurusu

2. VİRAL POTANSİYEL (0-20):
   - 15-20: Herkes konuşacak, tartışma yaratır (tartışmalı karar, skandal, sürpriz)
   - 8-14: İlgi çekici ama sınırlı kitle
   - 0-7: Niş haber, sınırlı paylaşılabilirlik

3. PRATİK DEĞER (0-15):
   - 12-15: Geliştiriciler/kullanıcılar hemen uygulayabilir (yeni API, tool, ücretsiz erişim)
   - 6-11: Dolaylı fayda (gelecek plan, beta)
   - 0-5: Akademik, teorik, self-promo

4. KAYNAK GÜVENİLİRLİĞİ (0-15):
   - 12-15: Bağımsız haber sitesi (TechCrunch, Verge, Wired, Ars Technica)
   - 7-11: Resmi şirket blog'u (kendi ürünü dışında), sektör siteleri
   - 3-6: Self-promo blog, aggregator, küçük kaynak
   - 0-2: Belirsiz kaynak

5. TAZELİK (0-25):
   - 22-25: 0-6 saat
   - 16-21: 6-12 saat
   - 10-15: 12-24 saat
   - 4-9: 24-48 saat
   - 0-3: 48-72 saat

SKOR DAĞILIMI HEDEFİ (BU ÇOK ÖNEMLİ):
- 90+: Sadece sektörü sarsan haberler. Refresh başına 0-1 tane olmalı.
- 80-89: Gerçekten önemli, geniş kitlenin ilgilendiği haberler. 2-3 tane olmalı.
- 70-79: İyi haberler, nişe hitap eder. Çoğunluk burası.
- 60-69: Orta kalite, ama yine de paylaşılabilir.
- 50-59: Zayıf ama mevcut. Düşük öncelik.
- <50: Bu trendleri listeye KOYMA, çöpe at.

SKOR ÖRNEKLERİ (KALİBRASYON):
- "OpenAI GPT-5 duyurdu" (2 saat, resmi) → 90-95
- "Google yeni Gemini modeli çıkardı" (4 saat) → 82-88
- "Mistral AI bir startup satın aldı" (8 saat) → 72-78
- "HuggingFace yeni kütüphane yayınladı" (12 saat) → 58-65
- "NVIDIA kendi blog'unda kendi GPU'sunu övdü" (3 saat) → 40-50
- "Küçük API güncellemesi" (6 saat) → 45-55
- "Araştırma makalesi yayınlandı" (20 saat) → 40-50
- "Lego akıllı tuğla yaptı" (10 saat, tech ama niş) → 55-62
- "Herhangi bir haber" (50+ saat) → MAX 45

TAZELİK HARD CAP (GPT bu kuralı çiğneyemez):
- >24 saat → MAX 80
- >48 saat → MAX 65
- >72 saat → MAX 45

JSON formatı:
{{
  "trends": [
    {{
      "topic": "Türkçe, kısa ve çarpıcı başlık",
      "category": "AI, Dev, Design, Crypto, Startup, Marketing, Business, Science, Lifestyle, Education, Entertainment veya News",
      "score": 0-100,
      "summary": "2-3 cümle Türkçe özet. Ne oldu, neden önemli.",
      "url": "İlgili item'ın GERÇEK URL'i",
      "source": "Kaynak adı",
      "published_at": "Item'dan AYNEN alınan ISO tarih",
      "raw_content": "İçerik özeti (max 500 karakter)",
      "tweet_count": 0,
      "avg_engagement": 0,
      "sample_sources": ["kaynak1"],
      "sample_links": ["link1"],
      "keywords": ["anahtar", "kelimeler", "max 5"],
      "content_angle": "İçerik üretim önerisi, 1 cümle"
    }}
  ]
}}

En az 3, en fazla 10 trend döndür. 50 altı skorlu haberleri ATLA.
Aynı konunun tekrarını YAPMA, birleştir.
Başka açıklama ekleme, sadece JSON döndür."""

        try:
            response = openai_client.chat.completions.create(
                model=os.environ.get('MODEL_ANALYSIS', 'gpt-4o-mini'),
                messages=[
                    {"role": "system", "content": "Sen sert bir haber editörüsün. Skorları şişirme, acımasızca değerlendir. Sadece JSON döndür."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,  # Düşük temperature = tutarlı, sıkı skorlama
                max_tokens=4000,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()
            logger.info(f"GPT raw response (first 300): {content[:300]}")
            data = json.loads(content)

            # Robust parsing
            if isinstance(data, list):
                trends = data
            elif isinstance(data, dict):
                trends = data.get("trends", data.get("items", []))
                if not isinstance(trends, list):
                    trends = []
                    for v in data.values():
                        if isinstance(v, list):
                            trends = v
                            break
            else:
                trends = []

            # ── VALIDATE GPT OUTPUT: reject malformed trends ──
            valid_trends = []
            for t in trends:
                if not isinstance(t, dict):
                    continue
                if not t.get("topic") or not isinstance(t.get("topic"), str):
                    continue
                if not t.get("url") or not isinstance(t.get("url"), str):
                    continue
                # Clamp score to valid range
                score = t.get("score", 0)
                if not isinstance(score, (int, float)):
                    t["score"] = 0
                else:
                    t["score"] = max(0, min(100, int(score)))
                # Sanitize URL — must start with http
                if not t["url"].startswith(("http://", "https://")):
                    continue
                valid_trends.append(t)
            if len(valid_trends) < len(trends):
                logger.info(f"GPT validation: {len(trends) - len(valid_trends)} invalid trends filtered")
            trends = valid_trends

            # ── POST-PROCESS: Zamanlılık cezası (GPT'ye güvenme, double-check) ──
            now = datetime.now(timezone.utc)
            items_url_map = {item.get("url", ""): item for item in raw_items}

            for trend in trends:
                # published_at'dan yaş hesapla
                pub_str = trend.get("published_at")
                age_hours = None
                if pub_str:
                    try:
                        pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                        age_hours = (now - pub_dt).total_seconds() / 3600
                    except Exception:
                        pass

                # URL'den fallback yaş
                if age_hours is None:
                    matched_item = items_url_map.get(trend.get("url", ""))
                    if matched_item:
                        age_hours = matched_item.get("age_hours")

                # Zamanlılık cezası uygula (hard cap, prompt'a güvenme)
                gpt_score = trend.get("score", 0)
                if age_hours is not None:
                    if age_hours > 72:
                        trend["score"] = min(gpt_score, 45)  # 72h+: max 45
                    elif age_hours > 48:
                        trend["score"] = min(gpt_score, 65)  # 48-72h: max 65
                    elif age_hours > 24:
                        trend["score"] = min(gpt_score, 80)  # 24-48h: max 80

                    if gpt_score != trend["score"]:
                        logger.info(f"Score capped: '{trend.get('topic', '?')}' {gpt_score}→{trend['score']} (age: {age_hours:.1f}h)")

                trend["_age_hours"] = age_hours  # Debug bilgisi

                # Kategori normalizasyonu
                raw_cat = trend.get("category", "")
                trend["category"] = normalize_category(raw_cat)
                if raw_cat != trend["category"]:
                    logger.info(f"Category normalized: '{raw_cat}' → '{trend['category']}'")

            # ── VIP SOURCE MULTIPLIER + SEMANTIC TRIGGERS ──
            try:
                from services.vip_scoring import apply_vip_scoring
            except ImportError:
                apply_vip_scoring = None

            if apply_vip_scoring:
                for trend in trends:
                    # Kaynak bilgilerini çıkar
                    source_name = trend.get("source", "")
                    twitter_username = ""
                    tier = None
                    content_text = f"{trend.get('topic', '')} {trend.get('summary', '')} {trend.get('raw_content', '')}"

                    # Twitter kaynağından username çıkar
                    if "(Twitter)" in source_name:
                        twitter_username = source_name.split("@")[-1].split(" ")[0] if "@" in source_name else ""

                    # URL'den Twitter username çıkar
                    trend_url = trend.get("url", "")
                    if "x.com/" in trend_url or "twitter.com/" in trend_url:
                        parts = trend_url.split("/")
                        for i, p in enumerate(parts):
                            if p in ("x.com", "twitter.com") and i + 1 < len(parts):
                                twitter_username = parts[i + 1]
                                break

                    # Raw items'dan tier bilgisi
                    matched_raw = items_url_map.get(trend_url)
                    if matched_raw:
                        tier = matched_raw.get("_tier")
                        twitter_username = twitter_username or matched_raw.get("_twitter_account", "")

                    vip_result = apply_vip_scoring(
                        base_score=trend.get("score", 0),
                        source_name=source_name,
                        twitter_username=twitter_username,
                        content_text=content_text,
                        tier=tier,
                    )

                    old_score = trend["score"]
                    trend["score"] = vip_result["final_score"]
                    trend["_vip"] = vip_result["is_vip"]
                    trend["_vip_reason"] = vip_result["reason"]
                    trend["_triggers"] = [t["label"] for t in vip_result["triggers"]]

                    if old_score != trend["score"]:
                        logger.info(f"VIP boost: '{trend.get('topic', '?')}' {old_score}→{trend['score']} ({vip_result['reason']})")

            # 50 altı skorlu trendleri filtrele
            before_count = len(trends)
            trends = [t for t in trends if t.get("score", 0) >= 50]
            if before_count != len(trends):
                logger.info(f"Filtered {before_count - len(trends)} low-score trends (<50)")

            logger.info(f"Analyzed {len(trends)} trends (post-processed with age penalties)")
            return trends

        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            return []

    async def refresh_all(self) -> dict:
        """Full refresh: fetch Twitter batch + Radar, analyze with GPT-4o, upsert to Supabase.

        RSS devre dışı — tüm sinyaller XQuik'ten geliyor (batch + radar).
        Uses URL-based deduplication (upsert on conflict url).
        Sets is_visible based on score threshold (>= 70).
        """
        logger.info("Starting full trend refresh (v3: batch + radar)...")

        # RSS devre dışı, sadece Twitter batch + Radar
        twitter_items = await self.fetch_twitter_signals()

        all_items = twitter_items

        if not all_items:
            return {"success": False, "error": "No items fetched", "trends": 0}

        # Build title lookup for fallback matching
        items_by_title = {}
        for item in all_items:
            items_by_title[item.get("title", "")] = item

        # Analyze ALL items with GPT-4o (batch + radar)
        trends = await self.analyze_trends(all_items)
        if not trends:
            return {"success": False, "error": "Analysis returned no trends", "trends": 0}

        # Build twitter metadata lookup (URL → twitter signal)
        twitter_by_url = {}
        for item in twitter_items:
            twitter_by_url[item["url"]] = item

        # Build all items lookup for matching
        all_items_by_title = {}
        for item in all_items:
            all_items_by_title[item.get("title", "")] = item

        # Enrichment import
        try:
            from services.trend_enrichment import enrich_trend, calculate_multi_signal_score
        except ImportError:
            enrich_trend = None
            calculate_multi_signal_score = None

        # Save to Supabase with URL-based dedup
        saved = 0
        enriched_count = 0
        now = datetime.now(timezone.utc).isoformat()
        # Küratör modu (off/shadow/live) — kaynağı küratör olan normal-yol
        # trendlerini is_curator işaretlemek için (news-bar override onlara da
        # uygulansın). live'da aktif; shadow/off'ta inert (flag false kalır).
        _curator_mode = os.environ.get("CURATOR_SEED_MODE", "off").lower()

        # 2026-06-10 (A yaması) — hikâye dedup adayları: son 72h trendleri
        # tek sorguda çekilir; URL dedup ıskalarsa story_dedup bu havuza
        # karşı "aynı haber mi?" kontrolü yapar (deterministik şüphe +
        # şüphede 4o-mini hakem). Detay: services/story_dedup.py docstring.
        story_candidates: list = []
        try:
            from services.story_dedup import find_same_story
            _cutoff_72h = (
                datetime.now(timezone.utc) - timedelta(hours=72)
            ).isoformat()
            story_candidates = (
                supabase.table("trends")
                .select("id, topic, raw_content, signal_count, engagement_total, source_tweets, full_source_text")
                .gte("created_at", _cutoff_72h)
                .order("created_at", desc=True)
                .limit(120)
                .execute()
            ).data or []
        except Exception as _se:
            find_same_story = None  # type: ignore
            logger.warning(f"story_dedup hazırlık hatası (devre dışı): {_se}")

        for trend in trends:
            try:
                # Get URL: from GPT analysis or fallback to matching item
                trend_url = trend.get("url") or ""
                if not trend_url:
                    for item in all_items:
                        if item.get("title", "").lower() in trend.get("topic", "").lower() or \
                           trend.get("topic", "").lower() in item.get("title", "").lower():
                            trend_url = item.get("url", "")
                            break

                if not trend_url:
                    logger.warning(f"Skipping trend without URL: {trend.get('topic')}")
                    continue

                # Determine source type and collect twitter metadata
                source_item = twitter_by_url.get(trend_url)
                is_twitter = source_item is not None
                source_type = "twitter" if is_twitter else "rss"

                # Collect all twitter signals related to this trend.
                #
                # 2026-06-11 (Berkay): eski mantık trend topic'inin herhangi bir
                # kelimesi (>4ch) başka tweet'te geçiyorsa o tweet'i kaynağa
                # katıyordu. "anthropic"/"framework" gibi tek kelime @AnthropicAI'nın
                # HER tweet'ine uyup ALAKASIZ hikâyeleri (Fable 5 ↔ Advanced AI
                # Framework ↔ $150M fellowship) tek source'a yığdı → caption doğru
                # hikâyeyi yazarken video script kirli blob'daki başka tweet'e atlayıp
                # YANLIŞ habere video üretti. Artık story_dedup imza-örtüşmesi: bir
                # aday tweet ANCAK kaynak tweet ile gerçekten aynı hikâyeyse katılır
                # (≥4 ortak içerik token'ı + jaccard≥0.2; marka adları stopword).
                related_tweets = []
                if is_twitter:
                    related_tweets.append(source_item)
                    _src_text = source_item.get("raw_content", "") or ""
                    _src_sig = story_tokens(f"{trend.get('topic', '')} {_src_text}")
                    for t_item in twitter_items:
                        if t_item["url"] == trend_url:
                            continue
                        _cand_sig = story_tokens(t_item.get("raw_content", "") or "")
                        _inter, _jac = deterministic_overlap(_src_sig, _cand_sig)
                        if _inter >= 4 and _jac >= 0.2:
                            related_tweets.append(t_item)

                # Calculate engagement and signal count
                engagement_total = sum(t.get("_likes", 0) for t in related_tweets)
                signal_count = 1 + len(related_tweets)  # 1 for base source
                has_tier1 = any(t.get("_tier") == 1 for t in related_tweets)
                has_tier2 = any(t.get("_tier") == 2 for t in related_tweets)

                # Multi-signal scoring
                base_score = trend.get("score", 0)
                if calculate_multi_signal_score and related_tweets:
                    final_score = calculate_multi_signal_score(
                        base_score=base_score,
                        engagement_total=engagement_total,
                        signal_count=signal_count,
                        has_tier1=has_tier1,
                        has_tier2=has_tier2,
                        age_hours=trend.get("age_hours", 0),
                    )
                else:
                    final_score = base_score

                # full_source_text — kırpılmamış kaynak birleşimi
                # (2026-06-08 prod hotfix'inin yeniden inşası, 2026-06-10:
                # source_tweets[].text UI için 200ch kırpık; gate + yazar
                # tam metni assemble_source_text üzerinden fst'den alır).
                _full_texts = [
                    t.get("raw_content", "")
                    for t in related_tweets[:5]
                    if t.get("raw_content")
                ]
                full_source_text_new = "\n\n".join(_full_texts)

                # Source tweets JSON (for frontend display)
                source_tweets_json = [
                    {
                        "tweet_id": t.get("_tweet_id"),
                        "username": t.get("_twitter_account"),
                        "likes": t.get("_likes", 0),
                        "tier": t.get("_tier", 3),
                        "text": t.get("raw_content", "")[:200],
                    }
                    for t in related_tweets[:5]
                ]

                # Deterministic score adjustment (source trust, VIP, self-promo)
                final_score = adjust_score(final_score, {
                    "topic": trend.get("topic", ""),
                    "summary": trend.get("summary", ""),
                    "source_name": trend.get("source", ""),
                    "keywords": trend.get("keywords", []),
                    "signal_count": signal_count,
                    "engagement_total": engagement_total,
                    "source_tweets": source_tweets_json,
                })

                doc = {
                    "id": str(uuid.uuid4()),
                    "topic": trend.get("topic", ""),
                    "category": trend.get("category", "AI"),
                    "score": final_score,
                    "summary": trend.get("summary", ""),
                    "url": trend_url,
                    "source_type": "merged" if (is_twitter and len(related_tweets) > 1) else source_type,
                    "source_name": trend.get("source", ""),
                    "published_at": _resolve_published_at(trend, source_item, items_by_title, all_items),
                    "is_visible": final_score >= self.SCORE_THRESHOLD,
                    "raw_content": trend.get("raw_content", "")[:2000],
                    "tweet_count": trend.get("tweet_count", 0),
                    "avg_engagement": trend.get("avg_engagement", 0),
                    "sample_sources": trend.get("sample_sources", []),
                    "sample_links": trend.get("sample_links", []),
                    "keywords": trend.get("keywords", []),
                    "content_angle": trend.get("content_angle", ""),
                    "updated_at": now,
                    # New fields
                    "signal_count": signal_count,
                    "engagement_total": engagement_total,
                    "source_tweets": source_tweets_json,
                    "twitter_account": source_item.get("_twitter_account") if source_item else None,
                    "tweet_id": source_item.get("_tweet_id") if source_item else None,
                    # is_curator işaretleme _seed_curator_trends'in YETKİSİNDE
                    # (news-filter geçen küratör story'leri; new=seed, existing=update).
                    # Burada flag YOK çünkü main-loop story-merge'de sinyal-dışı alan
                    # yazmıyor + non-AI küratör tweet'ini de işaretlerdi.
                    # VIP fields silently ignored if columns don't exist yet
                }

                # Context enrichment (high-score trends only, save API costs)
                if enrich_trend and final_score >= 70:
                    enrichment = await enrich_trend(
                        topic=trend.get("topic", ""),
                        summary=trend.get("summary", ""),
                        source_tweets=source_tweets_json,
                        engagement_total=engagement_total,
                        signal_count=signal_count,
                    )
                    if enrichment:
                        doc["key_angles"] = enrichment.get("key_angles", [])
                        doc["suggested_hooks"] = enrichment.get("suggested_hooks", {})
                        doc["content_pillars"] = enrichment.get("content_pillars", [])
                        enriched_count += 1

                doc["full_source_text"] = full_source_text_new or None

                # Check if URL already exists (dedup)
                existing = supabase.table("trends").select("id,signal_count,engagement_total,source_tweets,full_source_text").eq("url", trend_url).limit(1).execute()
                existing_doc = existing.data[0] if existing.data else None
                _match_kind = "url"
                # 2026-06-10 (A yaması) — URL farklı ama HİKÂYE aynı olabilir
                # (X firehose: aynı lansmanın 5-10 ayrı tweet'i). Story match
                # bulunursa yeni satır açılmaz, mevcut trende merge edilir.
                if existing_doc is None and find_same_story is not None and story_candidates:
                    try:
                        _story = find_same_story(
                            trend.get("topic", ""),
                            trend.get("raw_content")
                            or trend.get("summary")
                            or "",
                            story_candidates,
                        )
                    except Exception as _fe:
                        logger.warning(f"story_dedup eşleşme hatası (atlandı): {_fe}")
                        _story = None
                    if _story:
                        existing_doc = _story
                        _match_kind = "story"
                if existing_doc is not None:
                    del doc["id"]

                    # Merge signals: keep higher signal count, combine tweets
                    old_tweets = existing_doc.get("source_tweets") or []
                    if isinstance(old_tweets, str):
                        try:
                            old_tweets = json.loads(old_tweets)
                        except Exception:
                            old_tweets = []

                    # Merge source tweets (dedup by tweet_id)
                    seen_ids = {t.get("tweet_id") for t in old_tweets if t.get("tweet_id")}
                    for new_tweet in source_tweets_json:
                        if new_tweet.get("tweet_id") not in seen_ids:
                            old_tweets.append(new_tweet)
                    doc["source_tweets"] = old_tweets[:10]  # Max 10 tweets
                    # fst birleşimi: mevcut tam-metin korunur, yeni tweet
                    # metinleri (zaten içinde değilse) sonuna eklenir.
                    _old_fst = (existing_doc.get("full_source_text") or "").strip()
                    _fst_parts = [_old_fst] if _old_fst else []
                    for _ft in _full_texts:
                        if _ft and _ft not in _old_fst:
                            _fst_parts.append(_ft)
                    doc["full_source_text"] = "\n\n".join(_fst_parts) or None
                    doc["signal_count"] = max(doc["signal_count"], existing_doc.get("signal_count", 1))
                    doc["engagement_total"] = max(doc["engagement_total"], existing_doc.get("engagement_total", 0))

                    # Story-merge'de mevcut trendin konusunu/skorunu EZME:
                    # update yalnız sinyal alanlarıyla sınırlı kalır (hikâyenin
                    # kimliği ilk işlenen haliyle sabit; hype_crew trend-id
                    # dedup'ı böylece re-post'u da engeller).
                    if _match_kind == "story":
                        _merge_doc = {
                            "source_tweets": doc["source_tweets"],
                            "signal_count": doc["signal_count"],
                            "engagement_total": doc["engagement_total"],
                            "full_source_text": doc.get("full_source_text"),
                            "updated_at": doc.get("updated_at") or now,
                        }
                        supabase.table("trends").update(_merge_doc).eq("id", existing_doc["id"]).execute()
                    else:
                        supabase.table("trends").update(doc).eq("id", existing_doc["id"]).execute()
                    logger.info(
                        f"Updated trend [{_match_kind}-merge]: {trend.get('topic', '?')} "
                        f"→ {existing_doc.get('topic', existing_doc['id'])} "
                        f"(score: {final_score}, signals: {signal_count})"
                    )
                else:
                    supabase.table("trends").insert(doc).execute()
                    # Yeni eklenen trend, AYNI batch'in sonraki adayları için
                    # de hikâye havuzuna girsin (batch içi duplicate'ler).
                    story_candidates.insert(0, {
                        "id": doc["id"],
                        "topic": doc.get("topic"),
                        "raw_content": doc.get("raw_content"),
                    })
                    logger.info(f"New trend: {trend.get('topic', '?')} (score: {final_score}, signals: {signal_count})")
                saved += 1
            except Exception as e:
                logger.error(f"Failed to save trend '{trend.get('topic', '?')}': {e}")

        # ── Güvenilir-küratör force-seed ── (ana save-loop'tan SONRA, ayrı yol;
        # ana çoklu-kaynak yolunu bozmaz). CURATOR_SEED_MODE=off iken no-op.
        curator_seeded = 0
        try:
            curator_seeded = await self._seed_curator_trends(
                twitter_items, now, story_candidates, find_same_story
            )
        except Exception as _ce:
            logger.error(f"[curator] _seed_curator_trends hata: {_ce}")

        # ── Eski trend AUTO-ARCHIVE (Berkay: "her gün aynı bayat trendler") ──
        # query_trends aday havuzunu zaten 48h + is_archived=False ile süzer; yani
        # >72h trendler ZATEN aday DEĞİL — ama ham listede sonsuza dek duruyorlardı.
        # Bunları arşivle → liste/panel temizlenir, ADAY SEÇİMİ ETKİLENMEZ. Non-fatal.
        archived_old = 0
        try:
            _arch_hours = int(os.environ.get("TREND_ARCHIVE_HOURS", "72"))
            _cutoff = (datetime.now(timezone.utc) - timedelta(hours=_arch_hours)).isoformat()
            _ar = (supabase.table("trends").update({"is_archived": True})
                   .lt("created_at", _cutoff).eq("is_archived", False).execute())
            archived_old = len(_ar.data or [])
            if archived_old:
                logger.info(f"[trend-archive] {archived_old} eski trend arşivlendi (>{_arch_hours}h)")
        except Exception as _ae:  # noqa: BLE001
            logger.warning(f"[trend-archive] auto-archive hata (non-fatal): {_ae}")

        result = {
            "success": True,
            "rss_items": 0,  # RSS devre dışı — tüm sinyaller X (XQuik)
            "twitter_items": len(twitter_items),
            "curator_seeded": curator_seeded,
            "trends_analyzed": len(trends),
            "trends_saved": saved,
            "trends_enriched": enriched_count,
            "archived_old": archived_old,
            "updated_at": now,
        }
        logger.info(f"Trend refresh complete: {result}")
        return result

    async def _seed_curator_trends(self, twitter_items, now, story_candidates,
                                    find_same_story) -> int:
        """Güvenilir-küratör force-seed — kaçış yolunun kalbi.

        raw_items'da `_is_curator=True` olan her tweet'i news-filter'dan
        (curator_filter.classify_curator_news) geçirir; geçenleri TEK-kaynaklı
        trend olarak seed eder (score floor `CURATOR_SCORE_FLOOR`, is_curator=True).
        GPT'nin "ne patlıyor" funnel'ından BAĞIMSIZ çalışır — bu yüzden 0-like,
        tek-kaynaklı haber bile yakalanır.

        Mod kontrolü `CURATOR_SEED_MODE` env:
          - off (default)  → no-op (kod deploy edilir, etkisiz)
          - shadow         → seed ama is_visible=False (gözlem; post olmaz)
          - live           → seed is_visible=True (score floor garantisiyle)

        Dedup (URL + story) ve recently_covered ana yolla aynıdır. Aynı hikâye
        zaten varsa duplicate açmaz (mevcut trend recently_covered'a tabidir).
        """
        mode = os.environ.get("CURATOR_SEED_MODE", "off").lower()
        if mode not in ("shadow", "live"):
            return 0

        curator_items = [it for it in (twitter_items or []) if it.get("_is_curator")]
        if not curator_items:
            return 0

        try:
            from services.curator_filter import (
                classify_curator_news, passes_curator_filter,
            )
        except ImportError as e:
            logger.warning(f"[curator] curator_filter import yok, seed atlandı: {e}")
            return 0

        seeded = 0
        for item in curator_items:
            try:
                text = item.get("raw_content") or item.get("summary") or ""
                uname = item.get("_twitter_account") or "upcornco"
                trend_url = item.get("url") or ""
                if not trend_url or not text.strip():
                    continue

                verdict = await classify_curator_news(text, uname)
                if not passes_curator_filter(verdict):
                    logger.info(
                        f"[curator] skip (news={verdict.get('is_news')} "
                        f"ai={verdict.get('is_ai')} conf={verdict.get('confidence')}): "
                        f"{text[:80]!r}"
                    )
                    continue

                topic = verdict.get("topic") or text[:120]
                summary = verdict.get("summary") or text[:300]

                # Score floor + freshness hard-cap (floor'dan SONRA — ana loop
                # L489-494 ile aynı eşikler). >48h küratör item'ı 75 altına
                # düşüp doğal elenir (R5: bayat haber postlanmasın).
                score = self.CURATOR_SCORE_FLOOR
                age_h = item.get("age_hours") or 0
                if age_h > 72:
                    score = min(score, 45)
                elif age_h > 48:
                    score = min(score, 65)
                elif age_h > 24:
                    score = min(score, 80)

                # Dedup — URL + story (ana loop ile aynı makine)
                existing = supabase.table("trends").select(
                    "id,topic,signal_count,engagement_total,source_tweets,full_source_text"
                ).eq("url", trend_url).limit(1).execute()
                existing_doc = existing.data[0] if existing.data else None
                if existing_doc is None and find_same_story is not None and story_candidates:
                    try:
                        _story = find_same_story(topic, summary, story_candidates)
                    except Exception:
                        _story = None
                    if _story:
                        existing_doc = _story
                if existing_doc is not None:
                    # Aynı hikâye zaten trend — duplicate açma. Ama news-filter'ı
                    # geçen küratör kaynağı olduğunu live'da işaretle ki flow.py
                    # news-bar override lansman-rubriği reddini geçersiz kılsın.
                    # (recently_covered yine geçerli — tekrar postlanmaz.)
                    if mode == "live":
                        try:
                            supabase.table("trends").update(
                                {"is_curator": True, "updated_at": now}
                            ).eq("id", existing_doc["id"]).execute()
                            logger.info(
                                f"[curator] mevcut story is_curator=true: {topic!r} → "
                                f"{existing_doc.get('topic', existing_doc.get('id'))}"
                            )
                        except Exception as _ue:
                            logger.warning(f"[curator] is_curator update hata: {_ue}")
                    else:
                        logger.info(
                            f"[curator] story zaten mevcut, skip (shadow): {topic!r}"
                        )
                    continue

                try:
                    _pub = _resolve_published_at({}, item, {}, [])
                except Exception:
                    _pub = now

                source_tweets_json = [{
                    "tweet_id": item.get("_tweet_id"),
                    "username": item.get("_twitter_account"),
                    "likes": item.get("_likes", 0),
                    "tier": item.get("_tier", 3),
                    "text": (item.get("raw_content", "") or "")[:200],
                }]

                doc = {
                    "id": str(uuid.uuid4()),
                    "topic": topic,
                    "category": "AI",  # curator filter is_ai=True garantili
                    "score": score,
                    "summary": summary,
                    "url": trend_url,
                    "source_type": "twitter",
                    "source_name": f"@{uname} (Twitter)",
                    "published_at": _pub,
                    "is_visible": (mode == "live") and (score >= self.SCORE_THRESHOLD),
                    "is_curator": True,
                    "raw_content": (item.get("raw_content", "") or "")[:2000],
                    "keywords": verdict.get("keywords", []) if isinstance(verdict.get("keywords"), list) else [],
                    "content_angle": "",
                    "updated_at": now,
                    "signal_count": 1,
                    "engagement_total": item.get("_likes", 0),
                    "source_tweets": source_tweets_json,
                    "twitter_account": item.get("_twitter_account"),
                    "tweet_id": item.get("_tweet_id"),
                    "full_source_text": (item.get("raw_content", "") or "") or None,
                    "vip_reason": (
                        f"curator:@{uname} news-filter pass "
                        f"(cat={verdict.get('category')}, conf={verdict.get('confidence')})"
                    ),
                }

                supabase.table("trends").insert(doc).execute()
                story_candidates.insert(0, {
                    "id": doc["id"],
                    "topic": topic,
                    "raw_content": doc["raw_content"],
                })
                seeded += 1
                logger.info(
                    f"[curator] SEED ({mode}): {topic!r} score={score} "
                    f"is_visible={doc['is_visible']} url={trend_url}"
                )
            except Exception as e:
                logger.error(f"[curator] seed hata ({item.get('url')}): {e}")

        if seeded:
            logger.info(f"[curator] {seeded} curator trend seeded (mode={mode})")
        return seeded

    async def process_raw_signals(self, batch_size: int = 50) -> dict:
        """Process pending raw_signals: GPT analyze -> trends upsert -> content drafts.

        This is the core Faz 2 pipeline endpoint:
        1. Fetch pending signals from raw_signals
        2. Convert to analysis-ready format
        3. Run through GPT-4o analysis (same as refresh_all)
        4. Upsert to trends table
        5. Generate content drafts for high-score trends (>= 80)
        6. Mark signals as processed
        """
        if not supabase:
            return {"success": False, "error": "Supabase not configured"}

        # 1. Fetch pending signals
        try:
            result = supabase.table("raw_signals") \
                .select("*") \
                .eq("status", "pending") \
                .order("collected_at", desc=False) \
                .limit(batch_size) \
                .execute()
            signals = result.data or []
        except Exception as e:
            logger.error(f"Failed to fetch pending signals: {e}")
            return {"success": False, "error": str(e)}

        if not signals:
            logger.info("No pending signals to process")
            return {"success": True, "pending": 0, "processed": 0, "trends_saved": 0, "drafts_created": 0}

        logger.info(f"Processing {len(signals)} pending signals")

        # 2. Convert raw_signals to analysis-ready items (same format as fetch_rss_trends output)
        now = datetime.now(timezone.utc)
        raw_items = []
        signal_ids = []

        for sig in signals:
            signal_ids.append(sig["id"])
            raw_data = sig.get("raw_data") or {}
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except Exception:
                    raw_data = {}

            # Parse published_at from raw_data
            pub_str = raw_data.get("published_at")
            age_hours = 24  # default
            if pub_str:
                try:
                    pub_dt = datetime.fromisoformat(str(pub_str).replace("Z", "+00:00"))
                    age_hours = max(0, (now - pub_dt).total_seconds() / 3600)
                except Exception:
                    pass

            description = raw_data.get("description", "") or ""
            source_type = sig.get("source_type", "rss")

            title = sig.get("title", "")

            # Pre-filter: block noise before GPT
            if not pre_filter(title, description[:300]):
                logger.debug(f"Signal pre-filtered (noise): {title[:60]}")
                continue

            raw_items.append({
                "title": title,
                "url": sig.get("url", ""),
                "summary": description[:500],
                "raw_content": description,
                "source": sig.get("source_name", ""),
                "source_type": source_type,
                "published_at": pub_str or sig.get("collected_at"),
                "age_hours": round(age_hours, 1),
                "_signal_id": sig["id"],
                "_niche": sig.get("niche", ""),
            })

        # 3. GPT analysis (reuse existing analyze_trends)
        trends = await self.analyze_trends(raw_items)

        if not trends:
            # Mark signals as processed even if no trends emerged
            self._mark_signals_processed(signal_ids, "no_trends")
            return {
                "success": True,
                "pending": len(signals),
                "processed": len(signals),
                "trends_saved": 0,
                "drafts_created": 0,
            }

        # 4. Upsert trends to Supabase (same logic as refresh_all)
        saved = 0
        drafts_created = 0
        items_url_map = {item.get("url", ""): item for item in raw_items}
        upsert_now = now.isoformat()

        # Enrichment import
        try:
            from services.trend_enrichment import enrich_trend
        except ImportError:
            enrich_trend = None

        for trend in trends:
            try:
                trend_url = trend.get("url", "")
                if not trend_url:
                    continue

                raw_score = trend.get("score", 0)
                final_score = adjust_score(raw_score, {
                    "topic": trend.get("topic", ""),
                    "summary": trend.get("summary", ""),
                    "source_name": trend.get("source", ""),
                    "keywords": trend.get("keywords", []),
                })

                doc = {
                    "id": str(uuid.uuid4()),
                    "topic": trend.get("topic", ""),
                    "category": normalize_category(trend.get("category", "")),
                    "score": final_score,
                    "summary": trend.get("summary", ""),
                    "url": trend_url,
                    "source_type": "pipeline",
                    "source_name": trend.get("source", ""),
                    "published_at": trend.get("published_at"),
                    "is_visible": final_score >= self.SCORE_THRESHOLD,
                    "raw_content": trend.get("raw_content", "")[:2000],
                    "tweet_count": trend.get("tweet_count", 0),
                    "avg_engagement": trend.get("avg_engagement", 0),
                    "sample_sources": trend.get("sample_sources", []),
                    "sample_links": trend.get("sample_links", []),
                    "keywords": trend.get("keywords", []),
                    "content_angle": trend.get("content_angle", ""),
                    "updated_at": upsert_now,
                    "signal_count": 1,
                    "engagement_total": 0,
                }

                # Context enrichment for high-score trends
                if enrich_trend and final_score >= 70:
                    try:
                        enrichment = await enrich_trend(
                            topic=trend.get("topic", ""),
                            summary=trend.get("summary", ""),
                            source_tweets=[],
                            engagement_total=0,
                            signal_count=1,
                        )
                        if enrichment:
                            doc["key_angles"] = enrichment.get("key_angles", [])
                            doc["suggested_hooks"] = enrichment.get("suggested_hooks", {})
                            doc["content_pillars"] = enrichment.get("content_pillars", [])
                    except Exception as e:
                        logger.warning(f"Enrichment failed for '{trend.get('topic')}': {e}")

                # Dedup: check if URL already exists
                existing = supabase.table("trends").select("id").eq("url", trend_url).limit(1).execute()
                if existing.data:
                    del doc["id"]
                    supabase.table("trends").update(doc).eq("id", existing.data[0]["id"]).execute()
                    logger.info(f"Updated trend: {trend.get('topic', '?')} (score: {final_score})")
                else:
                    supabase.table("trends").insert(doc).execute()
                    logger.info(f"New trend: {trend.get('topic', '?')} (score: {final_score})")
                saved += 1

                # 5. Generate content draft for high-score trends (>= 80)
                if final_score >= 80:
                    draft_count = await self._generate_content_draft(doc)
                    drafts_created += draft_count

            except Exception as e:
                logger.error(f"Failed to save trend '{trend.get('topic', '?')}': {e}")

        # 6. Mark all signals as processed
        self._mark_signals_processed(signal_ids, "processed")

        result = {
            "success": True,
            "pending": len(signals),
            "processed": len(signals),
            "trends_saved": saved,
            "trends_analyzed": len(trends),
            "drafts_created": drafts_created,
            "updated_at": upsert_now,
        }
        logger.info(f"Signal processing complete: {result}")
        return result

    def _mark_signals_processed(self, signal_ids: list, status: str = "processed"):
        """Mark raw_signals as processed."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            for i in range(0, len(signal_ids), 50):
                batch = signal_ids[i:i + 50]
                supabase.table("raw_signals") \
                    .update({"status": status, "processed_at": now}) \
                    .in_("id", batch) \
                    .execute()
        except Exception as e:
            logger.error(f"Failed to mark signals as {status}: {e}")

    async def _generate_content_draft(self, trend_doc: dict) -> int:
        """Generate content drafts for a high-score trend.

        Creates drafts for Twitter and LinkedIn platforms.
        Returns number of drafts created.
        """
        drafts_created = 0
        platforms = [
            ("twitter", "Bu trendi kısa, punch'lı bir tweet olarak yaz. Viral potansiyeli yüksek, doğal dil kullan. Emoji kullanma. Max 280 karakter."),
            ("linkedin", "Bu trendi profesyonel bir LinkedIn postu olarak yaz. 3-4 paragraf, insight odaklı. Hook ile başla. Emoji kullanma."),
        ]

        for platform, instruction in platforms:
            try:
                prompt = f"""Trend: {trend_doc.get('topic', '')}
Özet: {trend_doc.get('summary', '')}
Kategori: {trend_doc.get('category', '')}
Keywords: {trend_doc.get('keywords', [])}
Content angle: {trend_doc.get('content_angle', '')}
Kaynak: {trend_doc.get('source_name', '')}

{instruction}"""

                response = openai_client.chat.completions.create(
                    model=os.environ.get('MODEL_CONTENT', 'gpt-4o-mini'),
                    messages=[
                        {"role": "system", "content": "Sen profesyonel bir içerik üreticisisin. Doğal, özgün ve ilgi çekici içerik yaz. Template kalıpları kullanma."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=1000,
                )
                content = response.choices[0].message.content.strip()

                # Save to content_drafts
                trend_id = trend_doc.get("id")
                supabase.table("content_drafts").insert({
                    "trend_id": trend_id,
                    "platform": platform,
                    "content": content,
                    "status": "draft",
                    "metadata": {
                        "score": trend_doc.get("score", 0),
                        "topic": trend_doc.get("topic", ""),
                        "auto_generated": True,
                    },
                }).execute()
                drafts_created += 1
                logger.info(f"Draft created: {platform} for '{trend_doc.get('topic', '?')}'")

            except Exception as e:
                logger.error(f"Draft generation failed ({platform}): {e}")

        return drafts_created


# Singleton
trend_engine = TrendEngine()

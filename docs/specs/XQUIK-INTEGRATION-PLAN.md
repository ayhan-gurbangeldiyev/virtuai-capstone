# Xquik × Type Hype — Entegrasyon Planı

## Ön Bilgi
- Xquik: $20/ay, 66K tweet search, 55K profil, 66K follower quota
- Bedava: Trends, Monitors (1 adet), Events, Webhooks, Tweet Composition, Drafts
- Base URL: `https://xquik.com/api/v1`
- Auth: `x-api-key: xq_XXX`
- MCP: `https://xquik.com/mcp`
- Docs: `https://docs.xquik.com`

---

## FAZ 1 — Xquik Client + Kurulum (2 saat)

### 1.1 Xquik hesabı aç
- [ ] xquik.com'dan üye ol
- [ ] API key al (format: `xq_` + 64 hex)
- [ ] Hetzner'da env'e ekle: `XQUIK_API_KEY=xq_...`
- [ ] Lokal `.env`'e de ekle (dev için)

### 1.2 Xquik client yaz
- [ ] Yeni dosya: `backend/services/xquik_client.py`

```python
import httpx
import asyncio
import logging
import os

class XquikClient:
    BASE = "https://xquik.com/api/v1"
    
    def __init__(self):
        self.api_key = os.environ.get("XQUIK_API_KEY", "")
        self.headers = {"x-api-key": self.api_key, "Content-Type": "application/json"}
    
    # --- TRENDS (Bedava, quota yok) ---
    # Docs: https://docs.xquik.com/api-reference/trends/list
    async def get_trends(self, woeid=23424969, count=50):
        """Türkiye trendleri. woeid=1 worldwide. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/trends", headers=self.headers, params={"woeid": woeid, "count": count})
            r.raise_for_status()
            return r.json()
    
    # --- EXTRACTIONS (Metered) ---
    # Docs: https://docs.xquik.com/api-reference/extractions/create
    async def extract_posts(self, username, results_limit=500):
        """Kullanıcının son tweetlerini çek. Metered."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/extractions", headers=self.headers, json={
                "toolType": "post_extractor",
                "targetUsername": username,
                "resultsLimit": results_limit
            })
            r.raise_for_status()
            return r.json()  # extraction job döner, poll gerekir
    
    async def search_tweets(self, query, results_limit=100):
        """Tweet search. X search syntax: from:user OR from:user2. Metered."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/extractions", headers=self.headers, json={
                "toolType": "tweet_search_extractor",
                "searchQuery": query,
                "resultsLimit": results_limit
            })
            r.raise_for_status()
            return r.json()
    
    async def get_extraction(self, extraction_id):
        """Extraction sonuçlarını çek (pagination destekli)."""
        # Docs: https://docs.xquik.com/api-reference/extractions/get
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/extractions/{extraction_id}", headers=self.headers)
            r.raise_for_status()
            return r.json()
    
    async def estimate_extraction(self, tool_type, **kwargs):
        """Extraction öncesi maliyet tahmini. Bedava."""
        # Docs: https://docs.xquik.com/api-reference/extractions/estimate
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/extractions/estimate", headers=self.headers, json={
                "toolType": tool_type, **kwargs
            })
            r.raise_for_status()
            return r.json()
    
    async def poll_extraction(self, extraction_id, timeout=120, interval=3):
        """Extraction tamamlanana kadar bekle."""
        for _ in range(timeout // interval):
            result = await self.get_extraction(extraction_id)
            if result.get("status") == "completed":
                return result
            if result.get("status") == "failed":
                raise Exception(f"Extraction failed: {result}")
            await asyncio.sleep(interval)
        raise TimeoutError(f"Extraction {extraction_id} timeout")
    
    # --- LOOKUPS (Metered) ---
    # Docs: llms.txt → X Data section
    async def lookup_tweet(self, tweet_id):
        """Tek tweet detayı. Metered."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/x/tweets/{tweet_id}", headers=self.headers)
            r.raise_for_status()
            return r.json()
    
    async def get_user_info(self, username):
        """Kullanıcı profil bilgisi. Metered."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/x/users/{username}", headers=self.headers)
            r.raise_for_status()
            return r.json()
    
    # --- MONITORS (Bedava, 1 adet limit) ---
    # Docs: https://docs.xquik.com/api-reference/monitors/create
    async def create_monitor(self, username, event_types=None):
        """Hesap izle. Max 1 monitor. Bedava."""
        if event_types is None:
            event_types = ["tweet.new", "tweet.reply", "tweet.quote", "follower.gained", "follower.lost"]
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/monitors", headers=self.headers, json={
                "username": username, "eventTypes": event_types
            })
            r.raise_for_status()
            return r.json()
    
    async def list_events(self, monitor_id=None, event_type=None, limit=50):
        """Monitor event'lerini çek. Bedava."""
        # Docs: https://docs.xquik.com/api-reference/events/list
        params = {"limit": limit}
        if monitor_id: params["monitorId"] = monitor_id
        if event_type: params["eventType"] = event_type
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/events", headers=self.headers, params=params)
            r.raise_for_status()
            return r.json()
    
    # --- WEBHOOKS (Bedava) ---
    # Docs: https://docs.xquik.com/api-reference/webhooks/create
    async def create_webhook(self, url, event_types):
        """Webhook kur. HTTPS zorunlu. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/webhooks", headers=self.headers, json={
                "url": url, "eventTypes": event_types
            })
            r.raise_for_status()
            return r.json()  # secret döner, sakla!
    
    # --- STYLE ANALYSIS ---
    # Docs: https://docs.xquik.com/api-reference/styles/analyze
    async def analyze_style(self, username):
        """Xquik'in kendi stil analizi. Metered."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/styles", headers=self.headers, json={"username": username})
            r.raise_for_status()
            return r.json()
    
    async def get_style(self, username):
        """Cache'lenmiş stil analizi getir. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/styles/{username}", headers=self.headers)
            r.raise_for_status()
            return r.json()
    
    async def compare_styles(self, username1, username2):
        """İki hesabı karşılaştır. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/styles/compare", headers=self.headers, params={
                "username1": username1, "username2": username2
            })
            r.raise_for_status()
            return r.json()
    
    # --- TWEET COMPOSITION (Bedava) ---
    # Docs: llms.txt → Tweet Composition Workflow
    async def compose_tweet(self, topic, goal="engagement"):
        """Tweet yazım yardımcısı. Goals: engagement/followers/authority/conversation. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/tweets/compose", headers=self.headers, json={
                "topic": topic, "goal": goal
            })
            r.raise_for_status()
            return r.json()
    
    async def score_tweet(self, text):
        """Draft'ı X algoritmasına karşı puanla. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/tweets/score", headers=self.headers, json={"text": text})
            r.raise_for_status()
            return r.json()
    
    # --- DRAFTS (Bedava) ---
    # Docs: https://docs.xquik.com/api-reference/drafts/create
    async def save_draft(self, text, topic=None, goal=None):
        """Draft kaydet. Bedava."""
        body = {"text": text}
        if topic: body["topic"] = topic
        if goal: body["goal"] = goal
        async with httpx.AsyncClient() as c:
            r = await c.post(f"{self.BASE}/drafts", headers=self.headers, json=body)
            r.raise_for_status()
            return r.json()
    
    # --- ACCOUNT (Bedava) ---
    async def get_account(self):
        """Hesap bilgisi + usage percent. Bedava."""
        async with httpx.AsyncClient() as c:
            r = await c.get(f"{self.BASE}/account", headers=self.headers)
            r.raise_for_status()
            return r.json()

# Singleton
xquik = XquikClient()
```

### 1.3 Test et
- [ ] `xquik.get_account()` → plan active mi, usage % kaç
- [ ] `xquik.get_trends()` → Türkiye trendleri dönüyor mu
- [ ] `xquik.get_user_info("semihdev")` → profil bilgisi

---

## FAZ 2 — Style Lab + Account Analysis: 500 Tweet (3 saat)

### 2.1 Style Lab tweet çekmeyi değiştir
Dosya: `backend/routes/sources.py`

- [ ] `from services.twitter_scraper import scraper` → `from services.xquik_client import xquik`
- [ ] `scraper.get_user_tweets_async(username, count=200)` →
  ```python
  # 1. Extraction başlat
  job = await xquik.extract_posts(username, results_limit=500)
  # 2. Tamamlanmasını bekle
  result = await xquik.poll_extraction(job["id"])
  # 3. Tweet'leri parse et
  tweets = result.get("results", [])
  ```
- [ ] `scraper.get_user_info_async(username)` → `xquik.get_user_info(username)`
- [ ] Tweet formatını adapte et (Xquik formatı → mevcut DB formatı)

### 2.2 Account Analysis tweet çekmeyi değiştir
Dosya: `backend/services/account_analyzer.py`

- [ ] `from services.twitter_scraper import scraper` → `from services.xquik_client import xquik`
- [ ] `scraper.get_user_tweets(username, 100)` → `xquik.extract_posts(username, 500)` + poll
- [ ] `scraper.get_user_info(username)` → `xquik.get_user_info(username)`

### 2.3 Account Analysis'e Xquik Style ekle
Dosya: `backend/services/account_analyzer.py`

- [ ] `xquik.analyze_style(username)` çağır
- [ ] Xquik style data'sını mevcut StyleAnalyzer sonuçlarıyla birleştir
- [ ] `xquik.compare_styles(username1, username2)` → rakip analiz endpoint'ine ekle

### 2.4 Diğer import'ları güncelle
- [ ] `routes/accounts.py` (satır 159): `twitter_scraper` → `xquik_client`
- [ ] `routes/profile.py` (satır 260, 494): `twitter_scraper` → `xquik_client`
- [ ] `routes/styles.py` (satır 11): `twitter_scraper` → `xquik_client`
- [ ] `routes/account_analysis.py` (satır 38): `twitter_scraper` → `xquik_client`

### 2.5 RAG embedding'leri 500 tweet ile
- [ ] `source_tweets` tablosuna 500 tweet kaydet (şu an 200)
- [ ] Embedding'leri yeniden oluştur → `style_rag.py` zaten tablodan çeker, otomatik
- [ ] Daha zengin few-shot seçimi

### 2.6 Test
- [ ] Style Lab'da yeni profil ekle → 500 tweet çekildi mi?
- [ ] Account Analysis → 500 tweet ile analiz yapıyor mu?
- [ ] Xquik style analizi response'ta görünüyor mu?
- [ ] RAG örnekleri çeşitlendi mi?

**Quota etkisi:** Hesap başına ~500 tweet. 10 hesap analiz = 5,000/66,000 = %7.5

---

## FAZ 3 — Trend Sistemi (2 saat)

### 3.1 Trend fetcher'ı yeniden yaz
Dosya: `backend/services/twitter_trend_fetcher.py`

Eski mimari:
```
TwitterGraphQL → cookie rotation → VIP hesap tweetleri → AI analiz
```

Yeni mimari (3 katman):

**Katman 1: Xquik Trends (Bedava)**
- [ ] `xquik.get_trends(woeid=23424969)` → Türkiye trendleri
- [ ] `xquik.get_trends(woeid=1)` → Worldwide trendleri
- [ ] İkisini birleştir, AI ile kategorize et
- [ ] `trends` tablosuna kaydet (mevcut şema)

**Katman 2: VIP Tweet Search (Metered, günde ~200 tweet)**
- [ ] 7 VIP hesabı tek sorguda çek:
  ```python
  query = "from:claudeai OR from:ChatGPTapp OR from:cursor_ai OR from:deepseek_ai OR from:windsurf_ai OR from:v0 OR from:notionhq"
  job = await xquik.search_tweets(query, results_limit=50)
  result = await xquik.poll_extraction(job["id"])
  ```
- [ ] Son çalıştırmadan bu yana yeni tweet var mı kontrol et (created_at karşılaştır)
- [ ] Yeni tweetleri trend_engine'e besle

**Katman 3: Keyword Search (Metered, isteğe bağlı)**
- [ ] Katman 1'deki trend keyword'leriyle tweet ara:
  ```python
  job = await xquik.search_tweets('"AI agent" OR "yapay zeka"', results_limit=30)
  ```
- [ ] Viral tweet keşfi (engagement sıralaması)

### 3.2 Trend engine adapte et
Dosya: `backend/services/trend_engine.py`

- [ ] Data format adapte (Xquik tweet format → mevcut format)
- [ ] VIP scoring aynı kalır (`services/vip_scoring.py`)
- [ ] RSS katmanı aynı kalır (trend_enrichment.py)

### 3.3 Cron route güncelle
Dosya: `backend/routes/trends.py`

- [ ] `/api/trends/sync` endpoint'i yeni trend_fetcher'ı çağırsın
- [ ] Hata durumunda Slack #alerts'e bildir

### 3.4 Test
- [ ] Manuel cron çalıştır → trend'ler geldi mi?
- [ ] VIP tweetleri çekildi mi?
- [ ] Mevcut frontend trend sayfası çalışıyor mu?
- [ ] Hetzner'da cron çalıştır (4x/gün)

**Quota etkisi:** ~200 tweet/gün × 30 = 6,000/ay = %9

---

## FAZ 4 — Tweet Composition Engine (1 saat)

### 4.1 Composition service yaz
Yeni dosya: `backend/services/tweet_composer.py`

- [ ] `xquik.compose_tweet(topic, goal)` → algoritma sinyalleri + follow-up sorular
- [ ] `xquik.score_tweet(draft_text)` → X algoritma skoru (pass/fail checklist)
- [ ] Magic Morning draft'larını score et → düşük skor = regenerate

### 4.2 API route ekle
Yeni dosya: `backend/routes/composition.py`

- [ ] `POST /api/compose` → compose_tweet çağır
- [ ] `POST /api/score` → score_tweet çağır
- [ ] `server.py`'a router ekle

### 4.3 Frontend — Draft kartlarına X Score ekle
Dosya: `frontend/src/pages/XAIModule.jsx` (veya ilgili component)

- [ ] Her üretilen draft'ın yanında "X Score: 8/10" badge
- [ ] Düşük skor uyarısı: "Bu tweet X algoritmasında düşük puan aldı"
- [ ] "Yeniden Üret" butonu (otomatik regenerate)

### 4.4 Nabız UI entegrasyonu (gelecek)
- [ ] Draft kart → Approve/Reject butonları
- [ ] Reject → neden seç → `draft_rejections` tablosuna kaydet
- [ ] AI prompt'a son 50 rejection inject et

**Quota etkisi:** 0 (composition tamamen bedava)

---

## FAZ 5 — Temizlik + MCP (1 saat)

### 5.1 Eski dosyaları sil
- [ ] `backend/services/twitter_graphql.py` → SİL
- [ ] `backend/services/twitter_scraper.py` → SİL
- [ ] `backend/services/cookie_store.py` → SİL
- [ ] `backend/services/cookie_monitor.py` → SİL
- [ ] `backend/routes/cookies.py` → SİL
- [ ] `server.py`'dan cookies router import'unu kaldır
- [ ] `scripts/sync-twitter-cookies.py` → SİL
- [ ] `scripts/.cookie-env/` → SİL (tüm virtualenv)

### 5.2 Cron temizliği
- [ ] Cookie sync cron'unu durdur: `openclaw cron disable 992bf9c4`
- [ ] Trend cron'larının yeni endpoint'i çağırdığını doğrula

### 5.3 Hetzner env temizliği
- [ ] `.env`'den cookie değişkenlerini sil: `TWITTER_AUTH_TOKEN`, `TWITTER_CT0`, `TWITTER_AUTH_TOKEN_2`, vs.
- [ ] `XQUIK_API_KEY` eklendi mi kontrol et

### 5.4 MCP entegrasyonu
- [ ] mcporter config'e Xquik ekle:
  ```json
  {
    "mcpServers": {
      "xquik": {
        "url": "https://xquik.com/mcp",
        "headers": {"X-API-Key": "xq_..."}
      }
    }
  }
  ```
- [ ] Test: `mcporter call xquik.get-trends`
- [ ] Agent'lar (Hype, Berkai) direkt trend sorgulayabilir mi?

### 5.5 Monitor kur (Berkay'ın kendi hesabı)
- [ ] `xquik.create_monitor("berkayaltunel", ["tweet.new", "follower.gained", "follower.lost"])`
- [ ] Webhook kur → Hetzner endpoint veya Slack
- [ ] Follower gained/lost bildirimleri Slack #type-hype'a

### 5.6 Hetzner deploy
- [ ] `requirements.txt`'e `httpx` ekle (yoksa)
- [ ] PM2 restart: `pm2 restart contentfactory-api`
- [ ] Smoke test: trend sync, style lab, account analysis

### 5.7 Test (son)
- [ ] Tüm eski import'lar temizlendi mi? `grep -r "twitter_graphql\|twitter_scraper\|cookie_store\|cookie_monitor" backend/`
- [ ] Frontend çalışıyor mu?
- [ ] Trend cron'ları çalışıyor mu?
- [ ] Style Lab profil ekleme çalışıyor mu?
- [ ] Account Analysis çalışıyor mu?

---

## Quota Bütçesi (Aylık)

| Kullanım | Tweet/ay | % Quota |
|---|---|---|
| Style Lab (10 hesap × 500) | 5,000 | %7.5 |
| Trend VIP search (4x/gün × 50) | 6,000 | %9 |
| Trend keyword search (4x/gün × 30) | 3,600 | %5.5 |
| Account Analysis (5 hesap × 500) | 2,500 | %3.8 |
| Ad-hoc lookups | 1,000 | %1.5 |
| **TOPLAM** | **~18,100** | **~%27** |

Rahat. %73 boş quota kalıyor.

---

## Zaman Tahmini

| Faz | Süre | Önkoşul |
|---|---|---|
| Faz 1: Client + Kurulum | 2 saat | Xquik hesabı açılmış olmalı |
| Faz 2: Style Lab + Analysis | 3 saat | Faz 1 |
| Faz 3: Trend Sistemi | 2 saat | Faz 1 |
| Faz 4: Tweet Composition | 1 saat | Faz 1 |
| Faz 5: Temizlik + MCP | 1 saat | Faz 2+3+4 |
| **TOPLAM** | **~9 saat** | **1.5-2 gün** |

Faz 2 ve 3 birbirinden bağımsız, paralel yapılabilir.

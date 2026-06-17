# Bird CLI Twitter Entegrasyonu Planı
**Tarih:** 19 Şubat 2026  
**Durum:** Berkay ile birlikte yapılacak (cookie auth gerekiyor)

---

## Mevcut Durum
- Bird CLI v0.8.0 kurulu (`/opt/homebrew/bin/bird`)
- Auth YOK (cookie/token ayarlanmamış)
- trend_engine.py'de `fetch_twitter_trends()` devre dışı bırakılmış
- Config dosyası yok (`~/.config/bird/config.json5`)

## Adım 1: Cookie Auth Kurulumu (Berkay ile birlikte)

### Seçenek A: Chrome Cookie (Önerilen, en kalıcı)
1. Chrome'da x.com'a `berkaifut` hesabıyla giriş yap
2. Terminal'de çalıştır:
```bash
bird --cookie-source chrome whoami
```
3. macOS Keychain izin isteyecek → "Always Allow" tıkla
4. Çalışırsa kalıcı config yaz:
```bash
mkdir -p ~/.config/bird
cat > ~/.config/bird/config.json5 << 'EOF'
{
  cookieSource: "chrome",
}
EOF
```
5. Test: `bird whoami` → hesap bilgisi göstermeli

### Seçenek B: Manuel Cookie (Yedek plan)
Chrome'da x.com → DevTools → Application → Cookies'den:
- `auth_token` değerini kopyala
- `ct0` değerini kopyala
```bash
cat > ~/.config/bird/config.json5 << 'EOF'
{
  authToken: "BURAYA_AUTH_TOKEN",
  ct0: "BURAYA_CT0",
}
EOF
```
⚠️ Dezavantaj: Token expire olunca manuel güncelleme gerekiyor

### Seçenek C: Firefox Cookie
```bash
bird --cookie-source firefox whoami
```

## Adım 2: Test Komutları (Auth sonrası)
```bash
# Hesap doğrulama
bird whoami

# Trend haberleri (AI kürated)
bird news --ai-only --json -n 20

# Belirli konularda arama
bird search "yapay zeka" --json -n 10
bird search "AI agent" --json -n 10

# Kullanıcı tweet'leri (stil klonlama için)
bird user-tweets @semihdev --json -n 50

# Trending konular
bird trending --json -n 20
```

## Adım 3: trend_engine.py Entegrasyonu

### 3A: `fetch_twitter_trends()` Aktifleştirme
```python
async def fetch_twitter_trends(self, keywords=None) -> list:
    """Bird CLI ile Twitter'dan trend ve haberler çek."""
    items = []
    
    # 1. AI-curated news
    try:
        result = subprocess.run(
            ["bird", "news", "--ai-only", "--json", "-n", "20"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            news = json.loads(result.stdout)
            for item in news:
                items.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "source": "Twitter/X Explore",
                    "published_at": item.get("created_at", ""),
                    "raw_content": item.get("description", ""),
                    "type": "twitter_news"
                })
    except Exception as e:
        logger.warning(f"Bird news fetch failed: {e}")
    
    # 2. Keyword search (AI, tech topics)
    default_keywords = [
        "yapay zeka", "AI agent", "LLM", "OpenAI", "Anthropic",
        "startup türkiye", "sosyal medya trend"
    ]
    search_keywords = keywords or default_keywords[:3]  # Rate limit için max 3
    
    for kw in search_keywords:
        try:
            result = subprocess.run(
                ["bird", "search", kw, "--json", "-n", "5"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                tweets = json.loads(result.stdout)
                for tweet in tweets:
                    items.append({
                        "title": f"@{tweet.get('author', {}).get('handle', '?')}: {tweet.get('text', '')[:100]}",
                        "url": tweet.get("url", ""),
                        "source": f"Twitter/@{tweet.get('author', {}).get('handle', '')}",
                        "published_at": tweet.get("created_at", ""),
                        "raw_content": tweet.get("text", ""),
                        "type": "twitter_search"
                    })
        except Exception as e:
            logger.warning(f"Bird search '{kw}' failed: {e}")
        
        await asyncio.sleep(1)  # Rate limit protection
    
    logger.info(f"Fetched {len(items)} Twitter items via Bird CLI")
    return items
```

### 3B: `fetch_all()` Güncelleme
```python
async def fetch_all(self) -> dict:
    rss_items = await self.fetch_rss_trends()
    twitter_items = await self.fetch_twitter_trends()
    
    all_items = rss_items + twitter_items
    trends = await self.analyze_trends(all_items)
    
    return {
        "trends": trends,
        "rss_items": len(rss_items),
        "twitter_items": len(twitter_items),
        "total_raw": len(all_items),
    }
```

### 3C: Style Lab Bird Entegrasyonu (Apify alternatifi)
```python
async def fetch_user_tweets_bird(handle: str, count: int = 50) -> list:
    """Bird CLI ile kullanıcı tweet'lerini çek (Apify'a ücretsiz alternatif)."""
    result = subprocess.run(
        ["bird", "user-tweets", handle, "--json", "-n", str(count)],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise Exception(f"Bird user-tweets failed: {result.stderr}")
    
    tweets = json.loads(result.stdout)
    return [{"text": t.get("text", ""), "metrics": t.get("metrics", {})} for t in tweets]
```

**Style Lab için Bird vs Apify:**
| | Bird CLI | Apify |
|---|---------|-------|
| Maliyet | Ücretsiz | $0.005/profil |
| Rate limit | ~100 req/15dk | Yüksek |
| Güvenilirlik | Cookie expire riski | Stabil |
| Kurulum | Lokal, cookie auth | API key |
| Hetzner'da çalışır mı? | ❌ (Chrome yok) | ✅ |

⚠️ **Önemli:** Bird CLI lokal Mac'te Chrome cookie kullanıyor. Hetzner VPS'te Chrome yok, bu yüzden:
- **Trend fetch**: Hetzner'da Bird çalışmaz, ya manual token kullan ya da sadece Mac cron'da çalıştır
- **Style Lab**: Apify'ı primary tut, Bird'ü lokal development/fallback olarak kullan
- **Alternatif**: Hetzner'a headless Chrome + cookie export dosyası kopyala

## Adım 4: Hetzner VPS İçin Çözüm

### Seçenek A: Manuel Token (Basit, önerilen)
Mac'ten cookie'leri al, Hetzner'a `.env` olarak koy:
```bash
# Mac'te
bird check --json  # auth_token ve ct0 gösterir

# Hetzner'da
echo 'BIRD_AUTH_TOKEN=xxx' >> /opt/contentfactory/backend/.env
echo 'BIRD_CT0=yyy' >> /opt/contentfactory/backend/.env
```

Backend'de:
```python
result = subprocess.run(
    ["bird", "--auth-token", os.environ["BIRD_AUTH_TOKEN"],
     "--ct0", os.environ["BIRD_CT0"],
     "news", "--ai-only", "--json"],
    ...
)
```

### Seçenek B: Cron ile Mac'ten Sync
Mac'te cron: Bird ile çek → Supabase'e yaz → Backend Supabase'den oku.
Böylece Bird sadece Mac'te çalışır, backend cookie'ye bağımlı olmaz.

### Seçenek C: X API (Ücretli, en güvenilir)
- Basic: $100/ay, 10K tweet/ay okuma
- Pro: $5000/ay
- Şu an için overkill, Bird yeterli

## Adım 5: Cookie Yenileme Stratejisi
Twitter cookie'leri ~1 ay geçerli. Otomatik yenileme:
1. `bird check` ile cookie durumu kontrol et
2. Başarısızsa Berkay'a Telegram bildirimi gönder
3. Berkay Chrome'da x.com'a girip cookie yenilemeli

Heartbeat'e eklenebilir:
```
- [ ] Bird CLI cookie durumu (haftalık)
```

---

## Özet: Yarın Yapılacaklar (5dk)
1. Chrome'da x.com'a `berkaifut` ile giriş yap
2. Terminal: `bird --cookie-source chrome whoami` → Keychain izni ver
3. Config dosyası oluştur
4. Test: `bird news --json`, `bird search "AI" --json`
5. trend_engine.py'yi güncelle
6. Hetzner token export

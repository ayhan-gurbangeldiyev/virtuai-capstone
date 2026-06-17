# Cookie Manager Kapsamlı Plan

## Mevcut Durum
- Cookie'ler `.env` dosyasında düz metin (AUTH_TOKEN, CT0)
- Bird CLI çalışıyor, cookie'ler geçerli
- Hetzner VPS'te Bird CLI kurulu değil
- Twitter scraper `os.environ` üzerinden cookie okuyor

## Hedef
Uzun vadeli, bakımı kolay, Hetzner deployment'a hazır cookie yönetimi.

## Mimari

```
┌─────────────────────────────────────────────┐
│              Hetzner VPS                     │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  ContentFactory Backend (FastAPI)    │    │
│  │  ├── /api/cookies/status            │    │
│  │  ├── /api/cookies/update (auth'd)   │    │
│  │  └── TwitterScraper                 │    │
│  │       └── reads from cookie store   │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  Cookie Health Monitor (cron)        │    │
│  │  └── 6 saatte bir bird whoami        │    │
│  │  └── Expire → Telegram bildirim      │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  ┌─────────────────────────────────────┐    │
│  │  Telegram Bot Handler                │    │
│  │  └── /cookie komutu → cookie update  │    │
│  └─────────────────────────────────────┘    │
│                                              │
│  cookies.json (encrypted, /data/)           │
└─────────────────────────────────────────────┘
```

## Bileşenler

### 1. Cookie Store (`services/cookie_store.py`)
- Cookie'leri dosyada saklar (JSON, Fernet encrypted)
- Read/write/validate işlemleri
- Environment variable fallback (geçiş dönemi)
- `last_verified`, `expires_hint`, `updated_at` metadata

### 2. Cookie API Endpoints (`routes/cookies.py`)
- `GET /api/cookies/status` → Geçerli mi, son kontrol ne zaman
- `POST /api/cookies/update` → Yeni cookie set (admin auth)
- `GET /api/cookies/health` → bird whoami çalıştır, sonuç döndür

### 3. Cookie Health Monitor (`services/cookie_monitor.py`)
- 6 saatte bir `bird whoami` çalıştırır
- Başarısızsa Telegram bildirim atar
- Son 3 başarısız denemeyi loglar
- Başarılıysa `last_verified` günceller

### 4. Telegram Bot Entegrasyonu
- Mevcut hotel bot'a `/cookie` komutu eklenir VEYA
- ContentFactory bot endpointi: Webhook ile cookie update
- Format: `/cookie auth_token=xxx ct0=yyy`
- Sadece Berkay'ın chat_id'sinden kabul eder

### 5. TwitterScraper Güncelleme
- `.env`'den değil, cookie store'dan okur
- Cookie yoksa veya expire'sa anlamlı hata mesajı
- Her scrape öncesi quick health check (optional)

### 6. Hetzner Deployment
- Bird CLI npm global install
- Cookie store dosyası Docker volume'da persist
- Encryption key `.env`'de

## Dosya Yapısı (Yeni/Değişen)
```
backend/
├── services/
│   ├── cookie_store.py      # NEW: Encrypted cookie storage
│   ├── cookie_monitor.py    # NEW: Health check + Telegram notify
│   └── twitter_scraper.py   # MODIFIED: Cookie store entegrasyonu
├── routes/
│   └── cookies.py           # NEW: Cookie management API
└── .env                     # MODIFIED: COOKIE_ENCRYPTION_KEY eklenir
```

## Güvenlik
- Cookie'ler Fernet (AES-128) ile encrypted
- API endpoint'leri admin-only (chat_id veya API key)
- Telegram'dan sadece Berkay'ın ID'si kabul edilir (8128240790)
- Cookie'ler Git'e ASLA commit edilmez (.gitignore)

## Uygulama Sırası
1. ✅ Cookie Store servisi
2. ✅ Cookie API endpoints
3. ✅ Cookie Health Monitor
4. ✅ TwitterScraper güncelleme
5. ✅ Telegram bildirim entegrasyonu
6. ✅ Hetzner'e Bird CLI kurulumu
7. ✅ Test: Cookie update flow

# TypeHype (ContentFactory) — Sistem Dokümantasyonu

> **Son güncelleme:** 2026-03-16
> **Versiyon:** 3.1
> **Hazırlayan:** Teknik Dokümantasyon (Claude + Berkai review)

---

## İçindekiler

1. [Proje Özeti](#1-proje-özeti)
2. [Sistemin Amacı](#2-sistemin-amacı)
3. [Genel Mimari](#3-genel-mimari)
4. [Klasör ve Dosya Yapısı](#4-klasör-ve-dosya-yapısı)
5. [Kritik Dosyalar ve Görevleri](#5-kritik-dosyalar-ve-görevleri)
6. [Veri Akışı ve Tetikleyiciler](#6-veri-akışı-ve-tetikleyiciler)
7. [API Endpoint Referansı](#7-api-endpoint-referansı)
8. [Veritabanı Şeması](#8-veritabanı-şeması)
9. [Servisler / Modüller / Bileşenler](#9-servisler--modüller--bileşenler)
10. [MCP Server v3.0 Detaylı Referans](#10-mcp-server-v30-detaylı-referans)
11. [Konfigürasyon ve Environment Yapısı](#11-konfigürasyon-ve-environment-yapısı)
12. [Kurulum / Çalıştırma / Deploy Süreci](#12-kurulum--çalıştırma--deploy-süreci)
13. [Bağımlılıklar ve Entegrasyonlar](#13-bağımlılıklar-ve-entegrasyonlar)
14. [Güvenlik Mimarisi](#14-güvenlik-mimarisi)
15. [Hata Yönetimi ve Logging](#15-hata-yönetimi-ve-logging)
16. [Dikkat Edilmesi Gereken Noktalar](#16-dikkat-edilmesi-gereken-noktalar)
17. [Olası Riskler ve İleride Problem Çıkarabilecek Yerler](#17-olası-riskler-ve-i̇leride-problem-çıkarabilecek-yerler)
18. [Çözüm Önerileri ve Önleyici Aksiyonlar](#18-çözüm-önerileri-ve-önleyici-aksiyonlar)
19. [Troubleshooting Playbook](#19-troubleshooting-playbook)
20. [Yeni Gelen Biri İçin Hızlı Anlama Rehberi](#20-yeni-gelen-biri-i̇çin-hızlı-anlama-rehberi)
21. [Sonuç / Özet](#21-sonuç--özet)
22. [Kritik Devralma Notları](#22-kritik-devralma-notları)

---

## 1. Proje Özeti

**TypeHype** (kod adı: ContentFactory), sosyal medya içerik üretimi, trend takibi ve hesap analizi sunan bir SaaS platformudur. Kullanıcılar X (Twitter), LinkedIn, Instagram, TikTok, YouTube ve Blog platformları için AI destekli içerik üretir, stil analizi yapar, trend bazlı öneriler alır ve hesap performanslarını analiz eder.

| Özellik | Değer |
|---------|-------|
| **Domain** | `typehype.io` (frontend), `api.typehype.io` (backend) |
| **Backend** | FastAPI (Python 3.14), Hetzner VPS |
| **Frontend** | React 19 + Tailwind CSS + Radix UI, Vercel |
| **Veritabanı** | Supabase (PostgreSQL + pgvector) |
| **AI Modelleri** | GPT-4o (içerik), GPT-4o-mini (analiz/trend), OpenRouter |
| **Twitter Veri** | Xquik API ($20/ay) |
| **Kullanıcı Yönetimi** | Supabase Auth (Google OAuth) |
| **Toplam Endpoint** | 135+ |
| **Veritabanı Tabloları** | 20 |
| **Tahmini Aylık Maliyet** | ~$23 (Xquik $20 + OpenRouter ~$3) |

> **Not:** Operasyonel bilgiler (sunucu IP, SSH path, API key'ler) bu dokümanda yer almaz. Bu bilgiler için `OPS_RUNBOOK.md` (private) dosyasına bakınız.

---

## 2. Sistemin Amacı

TypeHype üç temel problemi çözer:

1. **Trend Keşfi:** RSS (55 aktif feed) + Twitter (56+ hesap) + Radar sinyallerini toplayıp GPT ile analiz ederek skorlanmış, kategorize edilmiş trendler sunar.

2. **AI İçerik Üretimi:** Kullanıcının "stil DNA'sı"nı (50+ boyutta parmak izi) çıkarıp, X algoritmasına uyumlu, kişiselleştirilmiş tweetler, postlar ve makaleler üretir.

3. **Hesap Analizi & Koçluk:** Twitter hesaplarını 6 boyutta analiz eder (içerik kalitesi, engagement, tutarlılık, yaratıcılık, topluluk, büyüme), kişiselleştirilmiş koçluk kartları ve haftalık planlar sunar.

---

## 3. Genel Mimari

```
┌─────────────────────────────────────────────────────────────────────┐
│                         KULLANICI                                    │
│                    typehype.io (Vercel)                              │
│              React 19 + Tailwind + Radix UI                         │
│         Supabase Auth (Google OAuth) + axios API client             │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS (X-TH-Client header)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    api.typehype.io (Hetzner VPS)                     │
│                   FastAPI + uvicorn (--workers 2)                     │
│                   systemd: contentfactory.service                    │
│                                                                      │
│  ┌─── Middleware Katmanı (yürütme sırası) ─────────────────────┐    │
│  │ 1. CORSMiddleware (origin whitelist)                         │    │
│  │ 2. RequestSizeLimitMiddleware (1MB/5MB)                      │    │
│  │ 3. ReplayProtectionMiddleware (nonce/timestamp)              │    │
│  │ 4. SecurityMiddleware (CSRF, anti-curl, headers)             │    │
│  │ 5. AuditLogMiddleware (logging)                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─── Route Katmanı (22 modül, 135+ endpoint) ────────────────┐    │
│  │ /api/generate/*    → İçerik üretimi (tweet, post, makale)   │    │
│  │ /api/trends/*      → Trend pipeline + health                │    │
│  │ /api/styles/*      → Stil profil yönetimi                   │    │
│  │ /api/coach/*       → AI koçluk kartları                     │    │
│  │ /api/drafts/*      → Magic Morning günlük taslaklar         │    │
│  │ /api/accounts/*    → Multi-account yönetimi                 │    │
│  │ /api/mcp           → MCP Server v3.0 (14 tool)              │    │
│  │ /api/admin/*       → Key rotation                           │    │
│  │ ... (blog, linkedin, instagram, youtube, tiktok, media)     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─── Servis Katmanı (17 modül) ───────────────────────────────┐    │
│  │ trend_engine.py      → RSS + Twitter + GPT analiz pipeline  │    │
│  │ xquik_client.py      → Twitter/X veri API client            │    │
│  │ style_analyzer.py    → 50+ boyutlu stil DNA çıkarma         │    │
│  │ algo_scorer.py       → X algoritma uyumluluk skoru          │    │
│  │ coach_engine.py      → Dinamik koçluk kartları              │    │
│  │ magic_morning.py     → Günlük trend bazlı taslak üretimi    │    │
│  │ account_analyzer.py  → Hesap performans analizi             │    │
│  │ ... (style_rag, style_ranker, vip_scoring, vb.)             │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────┬──────────────────┬───────────────────────────┘
                       │                  │
          ┌────────────▼──────┐  ┌────────▼────────┐
          │   Supabase        │  │   Dış API'ler   │
          │   PostgreSQL      │  │                 │
          │   + pgvector      │  │ • OpenAI/Router │
          │   + Auth          │  │ • Xquik         │
          │   + Storage       │  │ • YouTube API   │
          └───────────────────┘  │ • Apify         │
                                 │ • Together AI   │
                                 └─────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    GitHub Actions (6x/gün)                            │
│              rss_fetcher.py → raw_signals tablosu                    │
│              Sonra: POST /api/trends/process-signals                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Harici Cron (5x/gün, OpenClaw veya benzeri)             │
│          02:00, 06:00, 10:00, 14:00, 22:00 TR                       │
│          POST /api/trends/auto-refresh (X-Cron-Secret header)       │
└─────────────────────────────────────────────────────────────────────┘
```

### "OpenClaw Cron" Nedir?

Plandaki "OpenClaw Cron" ifadesi, harici bir cron zamanlayıcısını ifade eder. Bu herhangi bir cron servisi olabilir (cron-job.org, EasyCron, veya sunucudaki crontab). Görevleri: belirli saatlerde `POST /api/trends/auto-refresh` endpoint'ine `X-Cron-Secret` header'ı ile istek göndermek. Herhangi bir HTTP cron servisi bu işi yapabilir — servise bağımlılık yoktur.

### Middleware Yürütme Sırası

Starlette'te middleware ekleme sırası: son eklenen ilk çalışır. `server.py`'de ekleme sırası:

```python
app.add_middleware(AuditLogMiddleware)        # 5. son çalışır
app.add_middleware(SecurityMiddleware)         # 4.
app.add_middleware(ReplayProtectionMiddleware) # 3.
app.add_middleware(RequestSizeLimitMiddleware) # 2.
app.add_middleware(CORSMiddleware, ...)        # 1. ilk çalışır
```

İstek akışı: `CORS → RequestSize → Replay → Security → AuditLog → Route Handler`

---

## 4. Klasör ve Dosya Yapısı

```
ContentFactory/
├── .github/workflows/
│   ├── rss-fetcher.yml          # GitHub Actions: RSS fetch (6x/gün)
│   └── run.yml                  # Eski/genel workflow
├── backend/
│   ├── server.py                # Ana FastAPI uygulaması (entry point)
│   ├── exceptions.py            # Custom exception sınıfları
│   ├── .env                     # Environment değişkenleri (GİZLİ)
│   ├── requirements.txt         # Python bağımlılıkları (124 paket)
│   ├── config/
│   │   └── rss_feeds.json       # RSS feed tanımları (eski, DB authoritative)
│   ├── data/
│   │   ├── cookies.json         # Twitter cookie cache (eski, kullanılmıyor)
│   │   ├── viral_accounts.json  # Viral hesap listesi
│   │   └── finetune_stats.json  # Fine-tune istatistikleri
│   ├── middleware/               # 10 middleware modülü
│   │   ├── auth.py              # JWT doğrulama + email whitelist
│   │   ├── security.py          # CSRF, anti-curl, güvenlik headerları
│   │   ├── active_account.py    # Multi-account IDOR koruması
│   │   ├── rate_limit.py        # Çok katmanlı rate limiting
│   │   ├── audit_log.py         # İstek & tehdit loglama
│   │   ├── db_cleanup.py        # Arka plan temizlik (6 saatte bir)
│   │   ├── input_sanitizer.py   # XSS & prompt injection önleme
│   │   ├── replay_protection.py # Nonce & timestamp doğrulama
│   │   ├── request_size.py      # Payload boyut sınırlama
│   │   └── token_tracker.py     # OpenAI token bütçe yönetimi
│   ├── routes/                   # 22 route modülü
│   │   ├── accounts.py          # Hesap CRUD + platform bağlama
│   │   ├── admin.py             # API key rotation
│   │   ├── blog.py              # Blog üretimi
│   │   ├── coach.py             # AI koçluk feed + haftalık plan
│   │   ├── drafts.py            # Magic Morning taslakları
│   │   ├── instagram.py         # Instagram caption/reel/hashtag
│   │   ├── linkedin.py          # LinkedIn post/carousel/analiz
│   │   ├── mcp.py               # MCP Server v3.0 (14 tool, 55KB)
│   │   ├── media.py             # Görsel prompt üretimi
│   │   ├── posting_times.py     # Optimal paylaşım zamanları
│   │   ├── profile.py           # Profil + brand voice + DNA testi
│   │   ├── repurpose.py         # Video script üretimi
│   │   ├── settings.py          # Kullanıcı ayarları
│   │   ├── sources.py           # Stil kaynak yönetimi
│   │   ├── styles.py            # Stil profil oluşturma/analiz
│   │   ├── trends.py            # Trend pipeline + health endpoint
│   │   ├── youtube.py           # YouTube içerik üretimi
│   │   ├── youtube_studio.py    # YouTube Studio entegrasyonu
│   │   ├── tiktok.py            # TikTok içerik üretimi
│   │   ├── account_analysis.py  # Hesap performans analizi
│   │   ├── style_transfer.py    # Stil transfer
│   │   └── finetune.py          # Fine-tune yönetimi
│   ├── services/                 # 17 servis modülü
│   │   ├── trend_engine.py      # Ana trend pipeline motoru
│   │   ├── trend_relevance.py   # Trend filtreleme & skorlama
│   │   ├── trend_enrichment.py  # Trend zenginleştirme (GPT)
│   │   ├── twitter_trend_fetcher.py  # Twitter sinyal toplama
│   │   ├── vip_scoring.py       # VIP kaynak skor çarpanları
│   │   ├── xquik_client.py      # Xquik REST API client
│   │   ├── style_analyzer.py    # Stil DNA çıkarma (50+ boyut)
│   │   ├── style_constraints.py # Stil kısıt motoru
│   │   ├── style_rag.py         # Semantik benzer tweet seçimi
│   │   ├── style_ranker.py      # Varyant sıralama (7 boyut)
│   │   ├── algo_scorer.py       # X algoritma skoru (0-100)
│   │   ├── coach_engine.py      # Koçluk kart motoru
│   │   ├── magic_morning.py     # Günlük taslak üretici
│   │   ├── account_analyzer.py  # Hesap analiz pipeline
│   │   ├── tweet_collector.py   # Tweet toplama (Apify)
│   │   ├── youtube_api.py       # YouTube Data API v3 wrapper
│   │   └── together_finetune.py # Together AI fine-tune
│   ├── prompts/                  # 30+ prompt şablonu
│   │   ├── builder.py           # v1 prompt builder
│   │   ├── builder_v3.py        # v3 prompt builder (aktif)
│   │   ├── algorithm.py         # X algoritma kuralları
│   │   ├── hooks.py, personas.py, tones.py  # Prompt bileşenleri
│   │   └── youtube_studio/      # YouTube Studio promptları (10 dosya)
│   ├── migrations/               # 12 SQL migration
│   ├── tests/                    # 5 test dosyası + fixtures
│   └── scripts/                  # Yardımcı scriptler
├── frontend/
│   ├── src/
│   │   ├── App.js               # Ana React uygulaması + routing
│   │   ├── lib/
│   │   │   ├── api.js           # axios client (güvenlik headerları)
│   │   │   ├── supabase.js      # Supabase client
│   │   │   ├── i18n.js          # i18next çoklu dil
│   │   │   └── utils.js         # Yardımcı fonksiyonlar
│   │   ├── pages/               # 29 sayfa bileşeni
│   │   ├── components/          # 70+ React bileşeni
│   │   │   ├── ui/              # 48 Radix UI primitif
│   │   │   ├── coach/           # Koçluk kartları
│   │   │   ├── generation/      # İçerik üretim UI
│   │   │   └── dashboard/       # Dashboard bileşenleri
│   │   ├── contexts/            # 5 React Context
│   │   └── locales/             # TR/EN çeviriler
│   ├── package.json             # Node bağımlılıkları
│   ├── vercel.json              # Vercel deploy config + CSP
│   └── .env / .env.production   # Frontend env
├── docs/
│   └── SYSTEM_DOCUMENTATION.md  # Bu dosya
├── rss_fetcher.py               # GitHub Actions RSS pipeline
├── n8n/                         # n8n workflow (pasif/arşiv)
├── migrations/                  # Root-level SQL migration (9 dosya)
└── *.md                         # Çeşitli spec/plan dokümanları
```

---

## 5. Kritik Dosyalar ve Görevleri

### Backend — Entry Point & Core

| Dosya | Görev | Değiştirilirse Ne Olur |
|-------|-------|------------------------|
| `backend/server.py` | FastAPI app, middleware stack, router registry, model config, startup events | Tüm API çöker. Middleware sırası değişirse güvenlik açığı |
| `backend/.env` | Tüm API key'ler ve config | Key değişirse ilgili servis durur |
| `backend/exceptions.py` | `AccountBrokenError` — frontend'e `ACCOUNT_BROKEN` kodu gönderir. Frontend bu kodu yakalayıp `account-broken` custom event fırlatır | Hesap kopma algılaması bozulur |

### Backend — Middleware (Güvenlik Katmanı)

| Dosya | Görev | Kritiklik |
|-------|-------|-----------|
| `middleware/auth.py` | Supabase JWT + email whitelist (`ALLOWED_EMAILS`) + brute force koruması (5 deneme → 15dk ban) | **EN KRİTİK** — Devre dışı kalırsa tüm API açık |
| `middleware/security.py` | CSRF (Origin/Referer), anti-curl (`X-TH-Client`), UA fingerprinting, güvenlik headerları (HSTS, CSP, X-Frame-Options) | **ÇOK KRİTİK** — EXEMPT_PATHS hatalı → hizmet kesintisi veya güvenlik açığı |
| `middleware/active_account.py` | Multi-account IDOR koruması. `X-Active-Account-Id` header → ownership check → fallback zincirleri | Devre dışı kalırsa başkalarının verilerine erişim |
| `middleware/rate_limit.py` | Per-minute (10), per-day (100), burst (3sn/5req → 5dk ban). IP spoofing koruması (`TRUSTED_PROXIES`) | Devre dışı kalırsa maliyet kontrolü kaybolur |
| `middleware/input_sanitizer.py` | Unicode NFKC normalizasyonu, zero-width strip, prompt injection regex, HTML strip, uzunluk limiti | Devre dışı kalırsa LLM manipüle edilebilir |
| `middleware/replay_protection.py` | `X-TH-Timestamp` (5dk window) + `X-TH-Nonce` (10K LRU cache). Sadece mutation endpoint'lerde aktif | Devre dışı kalırsa replay saldırıları |
| `middleware/request_size.py` | Default 1MB, image upload 5MB, URL max 2048 char | Devre dışı kalırsa DoS riski |
| `middleware/token_tracker.py` | Günlük 500K token bütçe (in-memory). `DISABLE_TOKEN_BUDGET` env ile kapatılabilir | Devre dışı kalırsa OpenAI faturası patlar |
| `middleware/audit_log.py` | 401/403 loglama, generation request tracking, suspicious pattern detection (5+ farklı token/IP/saat) | Devre dışı kalırsa tehdit tespiti kaybolur |
| `middleware/db_cleanup.py` | 6 saatte bir: generation retention (max 1000/user) + trend retention (30 gün) | DB yavaş yavaş şişer |

### Backend — Servisler

| Dosya | Görev | Değiştirilirse Ne Olur |
|-------|-------|------------------------|
| `services/trend_engine.py` | Ana pipeline: RSS parse → Twitter fetch → GPT analiz → cluster → upsert | Pipeline durur |
| `services/xquik_client.py` | Xquik REST API wrapper (rate limit: 10 req/s, 20 burst, 2s poll, 120s max wait) | Twitter verisi kesilir |
| `services/trend_relevance.py` | Pre-filter (gürültü) + post-filter (kalite) + skor ayarlama. Domain taxonomy: AI/Tech/Business/Crypto/Gündem | Kalitesiz trendler geçer veya iyi trendler elenir |
| `services/style_analyzer.py` | 50+ boyut: punctuation DNA, emoji strategy, hashtag usage, language mix, opening psychology, closing strategy, word distribution, engagement patterns | Stil profiller bozulur |
| `services/algo_scorer.py` | X algoritma skoru (0-100). Ağırlıklar: reply 75x, profile_click 12x, bookmark 10x, repost 1x, like 0.5x, report -369 | Skor hatalı → kötü içerik önerilir |

### Frontend

| Dosya | Görev |
|-------|-------|
| `frontend/src/App.js` | Routing, context providers (Theme→Auth→Account→CreatorProfile→StylePalette→Profile) |
| `frontend/src/lib/api.js` | axios interceptor: `X-TH-Client: web-app`, auto Bearer token, `X-TH-Timestamp` + `X-TH-Nonce` (mutation'larda) |
| `frontend/vercel.json` | SPA rewrite + CSP headers + HSTS |

---

## 6. Veri Akışı ve Tetikleyiciler

### 6.1 Trend Pipeline

```
GitHub Actions (6x/gün)              Harici Cron (5x/gün)
rss_fetcher.py                       POST /api/trends/auto-refresh
  │                                    │
  ├─ Supabase rss_feeds tablosundan    │
  │  aktif feed listesi oku            │
  ├─ RSS/Atom parse (55 feed)          │
  ├─ raw_signals tablosuna INSERT      │
  └─ POST /api/trends/process-signals  │
                    │                  │
                    ▼                  ▼
              trend_engine.py (auto-refresh)
              ┌──────────────────────────────────────────┐
              │ 1. RSS feeds oku (feedparser)             │
              │    → pre_filter (trend_relevance.py)      │
              │    → Başarılı: _reset_feed_error()        │
              │    → Hata: _increment_feed_error()        │
              │      (5 ardışık hata → is_active=false)   │
              │                                           │
              │ 2. Twitter fetch (Xquik API)              │
              │    → Tier 1: Resmi AI hesapları (filtersiz)│
              │    → Tier 2: Key people (GPT filtered)    │
              │    → Tier 3: Keyword search (opsiyonel)   │
              │                                           │
              │ 3. GPT-4o-mini analiz                     │
              │    → Skor (0-100), kategori, özet         │
              │    → post_filter + adjust_score           │
              │    → VIP boost (vip_scoring.py)           │
              │                                           │
              │ 4. Clustering (Jaccard similarity dedup)  │
              │ 5. Supabase trends tablosuna UPSERT       │
              │ 6. Skor >= 80: İçerik üretimi tetiklenir  │
              └──────────────────────────────────────────┘
```

### 6.2 İçerik Üretim Akışı

```
POST /api/generate/tweet
  │
  ├─ Auth + Rate Limit + Token Budget + Input Sanitization
  ├─ Görsel analiz (varsa, GPT-4o vision)
  │
  ├─ Style Lab v2 (style_profile_id varsa):
  │   ├─ style_fingerprint oku → style_constraints oluştur
  │   ├─ style_rag: pgvector semantik benzer tweet seç
  │   ├─ build_final_prompt_v3 → GPT-4o ile 5+ varyant üret
  │   └─ style_ranker: 7 boyutlu sıralama → en iyi 3
  │
  ├─ v1 Pipeline (style_profile_id yoksa):
  │   └─ brand_voice + build_final_prompt → GPT-4o
  │
  ├─ Token kullanımı kaydet
  └─ Generation tablosuna logla
```

### 6.3 Tetikleyiciler

| Tetikleyici | Kaynak | Hedef | Sıklık |
|-------------|--------|-------|--------|
| GitHub Actions cron | rss-fetcher.yml | raw_signals + process-signals | 6x/gün (UTC: 00,04,08,12,16,20) |
| Harici cron | HTTP cron servisi | POST /api/trends/auto-refresh | 5x/gün (TR: 02,06,10,14,22) |
| Server startup | systemd | start_cleanup_task() | 1x, sonra 6 saatte bir |
| Kullanıcı login | Frontend | GET /api/drafts/today (Magic Morning JIT) | Her login |
| POST /favorites/auto-purge | Cron (X-Cron-Secret) | 30 gün soft-delete temizlik | Cron |

---

## 7. API Endpoint Referansı

Tüm endpoint'ler `/api` prefix'i altındadır. Auth: `require_auth` = Supabase JWT zorunlu.

### Core Generation

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/tweet` | Yes | Tweet üretimi (stil v2 + v1 pipeline) |
| POST | `/api/generate/quote` | Yes | Quote tweet üretimi |
| POST | `/api/generate/reply` | Yes | Reply üretimi |
| POST | `/api/generate/article` | Yes | Makale üretimi |
| POST | `/api/evolve` | Yes | Varyant evrimi (max depth: 10) |

### Trends

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| GET | `/api/trends` | Yes | Trend listesi (kategori, visibility, niches filtreleri) |
| GET | `/api/trends/health` | **No** | Sağlık kontrolü (trend sayıları, feed durumu) |
| GET | `/api/trends/categories` | Yes | Mevcut kategoriler |
| GET | `/api/trends/{trend_id}` | Yes | Trend detayı |
| POST | `/api/trends/refresh` | Yes | Manuel trend yenileme |
| POST | `/api/trends/{trend_id}/generate` | Yes | Trendden içerik üret |
| POST | `/api/trends/archive-old` | Yes | 48 saatten eski trendleri arşivle |
| POST | `/api/trends/auto-refresh` | **Cron** | Otomatik yenileme (X-Cron-Secret) |
| POST | `/api/trends/process-signals` | **Cron** | raw_signals işleme (X-Cron-Secret) |

### Drafts (Magic Morning)

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| GET | `/api/drafts/today` | Yes | Bugünün taslakları (yoksa JIT üretir) |
| GET | `/api/drafts/{draft_id}` | Yes | Tekil taslak |
| PUT | `/api/drafts/{draft_id}` | Yes | Taslak güncelle (status: pending/edited/published/dismissed) |
| POST | `/api/drafts/score` | Yes | X algoritma skoru (Xquik MCP, free) |
| POST | `/api/drafts/refine` | Yes | İyileştirme önerileri (Xquik MCP) |
| POST | `/api/drafts/rules` | Yes | X algoritma kuralları |

### Accounts

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| GET | `/api/accounts` | Yes | Bağlı hesap listesi |
| PUT | `/api/accounts/{platform}` | Yes | Hesap ekle/güncelle (paywall check) |
| DELETE | `/api/accounts/{platform}` | Yes | Hesap sil (soft, cascade) |
| DELETE | `/api/accounts/by-id/{id}` | Yes | ID ile hesap sil |
| PATCH | `/api/accounts/{platform}/primary` | Yes | Birincil hesap yap |
| PATCH | `/api/accounts/by-id/{id}/primary` | Yes | ID ile birincil yap |
| PATCH | `/api/accounts/switch/{id}` | Yes | Aktif hesap değiştir |
| GET | `/api/accounts/avatar/instagram/{username}` | **No** | Instagram avatar proxy |

### Styles

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/styles/create-from-handle` | Yes | Twitter handle'dan stil profil oluştur |
| GET | `/api/styles/list` | Yes | Stil profil listesi |
| GET | `/api/styles/{id}` | Yes | Profil detayı + fingerprint |
| GET | `/api/styles/{id}/prompt` | Yes | Üretim için stil prompt'u |
| DELETE | `/api/styles/{id}` | Yes | Profil sil (korumalı ID'ler hariç) |
| POST | `/api/styles/{id}/refresh` | Yes | Profili yenile (re-fetch + re-analyze) |

### Coach

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| GET | `/api/coach/feed` | Yes | Dinamik koçluk kartları (max 10, priority sıralı) |
| GET | `/api/coach/weekly-plan` | Yes | Bu haftanın planı (cache) |
| POST | `/api/coach/weekly-plan` | Yes | Yeni haftalık plan üret (GPT-4o-mini) |
| POST | `/api/coach/dismiss` | Yes | Kartı kapat |
| GET | `/api/coach/insights` | Yes | Üretim geçmişi analizi (legacy) |

### Profile

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| GET | `/api/profile` | Yes | Profil bilgileri (display_name, niches, brand_voice) |
| PUT | `/api/profile` | Yes | Profil güncelle (niches validasyonu, brand_voice deep merge) |
| POST | `/api/profile/avatar` | Yes | Avatar yükle/çek (upload/twitter/instagram/tiktok) |
| POST | `/api/profile/dna-test` | Yes | Brand voice test tweeti üret |
| POST | `/api/profile/analyze-tone` | Yes | Twitter'dan ton analizi (5 boyut, toplam=100) |
| GET | `/api/profile/taxonomy` | **No** | Niche taksonomisi (public) |

### LinkedIn

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/linkedin` | Yes | LinkedIn post üretimi |
| POST | `/api/generate/linkedin/carousel` | Yes | Carousel (multi-slide) |
| POST | `/api/generate/linkedin/hooks` | Yes | 5 alternatif açılış kancası |
| POST | `/api/generate/linkedin/analyze` | Yes | Post analizi (skor + güçlü/zayıf yönler) |
| POST | `/api/generate/linkedin/image-prompt` | Yes | LinkedIn görseli promptu |
| GET | `/api/meta/linkedin/formats` | Yes | Format listesi |
| GET | `/api/meta/linkedin/personas` | Yes | Persona listesi |

### Instagram

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/instagram/caption` | Yes | Caption üretimi |
| POST | `/api/generate/instagram/reel-script` | Yes | Reel scripti |
| POST | `/api/generate/instagram/hashtags` | Yes | Hashtag üretimi |
| POST | `/api/generate/instagram/story-ideas` | Yes | Story fikirleri |
| GET | `/api/meta/instagram/formats` | Yes | Format listesi |

### Blog

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/blog/outline` | Yes | Blog outline |
| POST | `/api/generate/blog/full` | Yes | Tam blog yazısı (readability metrics) |
| POST | `/api/generate/blog/seo-optimize` | Yes | SEO analizi + optimizasyon |
| POST | `/api/generate/blog/cover-image` | Yes | Kapak görseli promptu |
| POST | `/api/generate/blog/repurpose` | Yes | Blog'u diğer platformlara dönüştür |
| GET | `/api/meta/blog/styles` | Yes | Blog stilleri |
| GET | `/api/meta/blog/frameworks` | Yes | Blog framework'leri |
| GET | `/api/meta/blog/levels` | Yes | İçerik seviyeleri |

### YouTube

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/youtube/idea` | Yes | Video fikri üret |
| POST | `/api/generate/youtube/script` | Yes | Video scripti |
| POST | `/api/generate/youtube/title` | Yes | Başlık üret |
| POST | `/api/generate/youtube/description` | Yes | Açıklama + etiketler |
| GET | `/api/meta/youtube/formats` | Yes | Format listesi |

### YouTube Studio

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/youtube-studio/channel/analyze` | Yes | Kanal analizi |
| POST | `/api/youtube-studio/video/analyze` | Yes | Video analizi |
| POST | `/api/youtube-studio/comments/analyze` | Yes | Yorum analizi |
| POST | `/api/youtube-studio/competitor/analyze` | Yes | Rakip analizi |
| POST | `/api/youtube-studio/thumbnail/analyze` | Yes | Thumbnail analizi |
| POST | `/api/youtube-studio/ideas/generate` | Yes | Video fikirleri |
| POST | `/api/youtube-studio/niche/analyze` | Yes | Niş analizi |
| POST | `/api/youtube-studio/keywords/analyze` | Yes | Keyword analizi |
| POST | `/api/youtube-studio/translate` | Yes | İçerik çevirisi |
| GET | `/api/youtube-studio/trends` | Yes | YouTube trendleri |
| GET | `/api/youtube-studio/trends/rising` | Yes | Yükselen trendler |

### TikTok

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/generate/tiktok/script` | Yes | TikTok scripti |
| POST | `/api/generate/tiktok/caption` | Yes | Caption + hashtag |
| GET | `/api/meta/tiktok/formats` | Yes | Format listesi |

### Account Analysis

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/analyze/account` | Yes | Twitter hesap analizi (6 boyut) |
| GET | `/api/analyze/history` | Yes | Geçmiş analizler (pagination) |
| GET | `/api/analyze/history/{id}` | Yes | Analiz detayı |
| DELETE | `/api/analyze/history/{id}` | Yes | Analiz sil |

### Sources, Media, Settings, Other

| Method | Path | Auth | Açıklama |
|--------|------|------|----------|
| POST | `/api/sources/add` | Yes | Twitter kaynak ekle (500 tweet fetch) |
| GET | `/api/sources/list` | Yes | Kaynak listesi |
| GET | `/api/sources/{id}/tweets` | Yes | Kaynak tweetleri |
| DELETE | `/api/sources/{id}` | Yes | Kaynak sil |
| POST | `/api/sources/{id}/refresh` | Yes | Kaynak yenile |
| POST | `/api/media/generate-image-prompt` | Yes | Görsel prompt üret |
| POST | `/api/repurpose/video-script` | Yes | Video script üret |
| POST | `/api/repurpose/image-prompt` | Yes | Görsel prompt üret |
| GET | `/api/settings` | Yes | Kullanıcı ayarları |
| PATCH | `/api/settings` | Yes | Ayar güncelle |
| GET | `/api/posting-times/heatmap` | Yes | 7x24 paylaşım heatmap |
| GET | `/api/posting-times/best-now` | Yes | Şu an iyi mi? |
| POST | `/api/style-transfer` | Yes | Stil transfer |
| GET | `/api/style-transfer/profiles` | Yes | Stil profilleri |
| POST | `/api/admin/rotate-key` | Admin | API key rotation |
| GET | `/api/auth/check` | Yes | Auth durumu |
| GET | `/api/health` | **No** | Genel sağlık kontrolü |
| POST | `/api/favorites/toggle` | Yes | Favori ekle/çıkar |
| GET | `/api/favorites` | Yes | Favoriler |
| GET | `/api/favorites/trash` | Yes | Çöp kutusu (soft-deleted) |
| POST | `/api/favorites/auto-purge` | **Cron** | 30 gün eski soft-delete temizle |
| GET | `/api/generations/history` | Yes | Üretim geçmişi |
| GET | `/api/generations/calendar` | Yes | Takvim heatmap |
| GET | `/api/user/stats` | Yes | Kullanıcı istatistikleri |
| DELETE | `/api/generations/{id}` | Yes | Üretim sil |
| DELETE | `/api/generations/all` | Yes | Tüm üretimleri sil |
| POST | `/api/mcp` | **Bearer** | MCP Server JSON-RPC 2.0 |

### Cron Endpoint Güvenliği

Cron endpoint'leri (`auto-refresh`, `process-signals`, `auto-purge`) `X-Cron-Secret` header'ı ile korunur:

```python
# routes/trends.py
expected = os.environ.get("CRON_SECRET", "")
if not expected or not x_cron_secret or not hmac.compare_digest(expected, x_cron_secret):
    raise HTTPException(status_code=403, detail="Invalid cron secret")
```

Ek olarak, trend cron endpoint'lerinde 30 saniyelik minimum interval kontrolü (`_cron_rate_check()`) bulunur.

---

## 8. Veritabanı Şeması

### Tablo İlişki Haritası

```
auth.users (Supabase)
  │
  ├── 1:1 ── user_settings (user_id FK)
  │              └── active_account_id FK → connected_accounts.id
  │
  ├── 1:N ── connected_accounts (user_id FK)
  │              │
  │              ├── 1:N ── generations (account_id FK)
  │              ├── 1:N ── favorites (account_id FK)
  │              ├── 1:N ── style_profiles (account_id FK)
  │              ├── 1:N ── coach_weekly_plans (account_id FK)
  │              └── 1:N ── coach_dismissed_cards (account_id FK)
  │
  ├── 1:N ── style_sources (user_id)
  │              └── 1:N ── source_tweets (source_id FK)
  │                            └── embedding (vector 1536)
  │
  ├── 1:N ── daily_drafts (user_id)
  │              └── trend_id FK → trends.id
  │
  └── 1:N ── account_analyses (user_id)

trends (bağımsız)
  ├── content_drafts (trend_id FK)
  └── daily_drafts (trend_id FK)

rss_feeds (bağımsız) → raw_signals (bağımsız)
twitter_watch_accounts (bağımsız)
viral_tweets (bağımsız)
system_config (bağımsız)
status_checks (bağımsız)
```

### Tablo Detayları

#### `trends` — Keşfedilen trendler
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| topic | text | Trend başlığı |
| category | text | AI, Tech, Crypto, Gündem, Business, Lifestyle, Sports, Health |
| source_type | text | 'rss', 'ai', 'twitter' |
| score | float (0) | Trend skoru (0-100) |
| is_visible | boolean (true) | Frontend'de görünürlük |
| is_vip | boolean (false) | VIP kaynak mı |
| vip_reason | text | VIP nedeni |
| semantic_triggers | text[] | ['launch', 'scandal', 'milestone', 'breaking'] |
| summary, ai_summary | text | Trend özeti |
| keywords | text[] | Anahtar kelimeler |
| key_angles | text[] | İçerik açıları |
| suggested_hooks | jsonb | Önerilen açılış kancaları |
| content_pillars | text[] | İçerik direkleri |
| url | text (unique) | Kaynak URL |
| source_name | text | Kaynak adı |
| source_tweets | jsonb | İlişkili tweet verileri |
| signal_count | int (1) | Sinyal sayısı |
| engagement_total | int (0) | Toplam etkileşim |
| published_at | timestamptz | Yayın tarihi |
| is_archived | boolean | Arşivlenmiş mi |
| cluster_id | uuid | Kümeleme ID |
| created_at, updated_at | timestamptz | |

**Indexler:** `idx_trends_url_unique`, `idx_trends_score`, `idx_trends_visible_score`, `idx_trends_source_type`, `idx_trends_published_at`

#### `rss_feeds` — RSS feed yapılandırması
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| source | text NOT NULL | Feed adı |
| rss_url | text UNIQUE NOT NULL | RSS URL |
| niche | text NOT NULL | Niş kategorisi |
| language | text ('en') | Dil |
| priority | text ('Medium') | Öncelik |
| is_active | boolean (true) | Aktif mi |
| error_count | int (0) | Ardışık hata sayısı (5 → auto-disable) |
| health_score | numeric(3,1) (100.0) | Feed sağlık skoru |
| last_fetched | timestamptz | Son başarılı fetch |
| last_status | text | Son durum |

#### `raw_signals` — Ham RSS sinyalleri (staging)
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| source_type | text NOT NULL | Sinyal tipi |
| source_name | text | Kaynak |
| title | text | Başlık |
| url | text UNIQUE | URL (duplicate engeli) |
| raw_data | jsonb | Ham veri |
| status | text ('pending') | 'pending' veya 'processed' |
| batch_id | uuid | İşleme batch ID |
| collected_at, processed_at | timestamptz | |

#### `twitter_watch_accounts` — İzlenen Twitter hesapları
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| username | text UNIQUE NOT NULL | Twitter kullanıcı adı |
| tier | int (1) | 1=resmi, 2=key people |
| category | text | Kategori (ai_lab, ceo, researcher) |
| is_vip | boolean (false) | VIP mi |
| weight | numeric(3,1) (1.0) | Skor çarpanı |
| active | boolean (true) | |
| last_tweet_id | text | Son tweet ID (incremental fetch) |

#### `generations` — Üretilen içerikler
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| user_id | uuid FK → auth.users | |
| account_id | uuid FK → connected_accounts | |
| type | text | 'tweet', 'thread', 'post', vb. |
| topic | text | Konu |
| variants | jsonb | Üretilen varyantlar dizisi |
| persona, tone, mode, length, language | text | Üretim parametreleri |
| parent_generation_id | uuid FK → generations | Evolution parent |
| evolution_depth | int (0) | Evrim derinliği (max 10) |
| evolution_chain_id | uuid | Evrim zinciri grubu |
| created_at | timestamptz | |

#### `favorites` — Kaydedilen içerikler (soft delete)
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| user_id | uuid FK | |
| account_id | uuid FK | |
| generation_id | uuid | |
| variant_index | int | Seçilen varyant |
| content | text | |
| deleted_at | timestamptz | NULL=aktif, NOT NULL=soft-deleted |

**Indexler:** `idx_favorites_active` (WHERE deleted_at IS NULL), `idx_favorites_deleted` (WHERE deleted_at IS NOT NULL)

#### `user_settings` — Kullanıcı profili
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| user_id | uuid FK PK | |
| active_account_id | uuid FK → connected_accounts | |
| display_name | text | |
| niches | text[] | Niş slug'ları |
| brand_voice | jsonb | `{tones: {informative, witty, aggressive...}, principles: [], avoid: [], sample_voice}` |
| subscription_tier | text ('free') | 'free', 'pro', 'agency' |
| account_limit | int (1) | Max hesap sayısı |
| default_draft_style | jsonb | `{type: 'own_voice'|'cloned'|'archetype', profile_id?, key?}` |

#### `connected_accounts` — Bağlı sosyal hesaplar
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| user_id | uuid FK NOT NULL | |
| platform | text | CHECK IN ('twitter','instagram','youtube','tiktok','linkedin') |
| username | text NOT NULL | |
| is_primary | boolean (false) | |
| status | text ('active') | 'active', 'inactive' |
| deleted_at | timestamptz | Soft delete |
| UNIQUE | (user_id, platform) | |

#### `style_profiles` — Stil profilleri
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| user_id | uuid FK | |
| account_id | uuid FK | |
| name | text | Profil adı |
| twitter_username | text | |
| style_fingerprint | jsonb | 50+ boyut parmak izi (aşağıda detay) |
| viral_patterns | jsonb | Viral vs flop karşılaştırma |
| constraints | jsonb | Hard kısıtlar |
| source_ids | uuid[] | Kaynak ID'leri |
| tweet_count | int | Analiz edilen tweet sayısı |

**`style_fingerprint` JSON yapısı:**
```json
{
  "punctuation_dna": {"comma_ratio": 0.12, "ellipsis_ratio": 0.05, "exclamation_ratio": 0.08},
  "emoji_strategy": "light",  // "no_emoji", "light", "moderate", "heavy"
  "hashtag_usage": "minimal", // "none", "minimal", "moderate", "heavy"
  "language_mix": {"tr_ratio": 0.7, "en_ratio": 0.3},
  "capitalization": "sentence_case",
  "line_structure": "multi_line",
  "opening_psychology": {"power_words": true, "directness": 0.8},
  "closing_strategy": "cta",
  "avg_word_count": 42,
  "avg_line_count": 3,
  "link_policy": "ALWAYS_BANNED",
  "question_ratio": 0.15,
  "top_bigrams": [["yapay", "zeka"], ["bu", "hafta"]],
  "engagement_patterns": {"likes_median": 50, "rt_median": 5}
}
```

#### `source_tweets` — Analiz edilen tweetler (pgvector)
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| source_id | uuid FK → style_sources | |
| content | text | Tweet içeriği |
| embedding | vector(1536) | text-embedding-3-small |
| likes, retweets, replies, views, bookmarks, quotes | int | Engagement metrikleri |
| tweet_type | text | 'original', 'reply', 'quote' |
| engagement_score | float | Ağırlıklı engagement |
| algo_score | float | X algoritma skoru |
| word_count | int | |
| has_link | boolean | |
| language | text | |

**Indexler:** HNSW on embedding (vector_cosine_ops), composite on (source_id, engagement_score DESC)

**Supabase Functions:**
- `match_source_tweets(query_embedding, source_ids, threshold, count)` — Cosine similarity search

#### `daily_drafts` — Magic Morning taslakları
| Kolon | Tip | Açıklama |
|-------|-----|----------|
| id | uuid PK | |
| user_id | uuid NOT NULL | |
| trend_id | uuid FK → trends | |
| content | text NOT NULL | |
| platform | text ('twitter') | |
| status | text ('pending') | CHECK IN ('pending','edited','published','dismissed') |
| source | text ('magic_morning') | 'magic_morning', 'dna_test', 'manual' |
| trend_topic, trend_summary, insight | text | |

#### Diğer Tablolar

| Tablo | Görev |
|-------|-------|
| `account_analyses` | Hesap analiz sonuçları (username, overall_score, 6 boyut analiz) |
| `coach_weekly_plans` | Haftalık planlar (user_id, week_start, plan jsonb, weekly_goal) |
| `coach_dismissed_cards` | Kapatılan koçluk kartları (user_id, card_key, unique) |
| `content_drafts` | Trendden üretilen taslaklar (trend_id FK, platform, status) |
| `content_calendar` | Zamanlanmış içerik (scheduled_at, platform, status) |
| `viral_tweets` | Viral tweet koleksiyonu (30+ kolon, engagement detayları) |
| `system_config` | Pipeline config (key-value: pipeline_mode, model_primary, daily_cost_limit) |
| `status_checks` | API durum izleme |

### RLS Politikaları

Tüm kullanıcı tablolarında Row Level Security aktif:
- **SELECT:** `user_id = auth.uid()` (kullanıcı sadece kendi verisini görür)
- **INSERT/UPDATE/DELETE:** `user_id = auth.uid()`
- **Service role:** Tam erişim (backend service key ile)
- `trends`: Authenticated users `is_visible = true` olanları okuyabilir
- `twitter_watch_accounts`: Anon read (public)

### Migration Çalıştırma

Migration dosyaları Supabase SQL Editor üzerinden çalıştırılır. Otomatik migration runner yoktur. Sıra:

```
migrations/faz1_complete.sql → migrations/002-007 (root)
backend/migrations/001-009 (backend)
```

**Gerekli extension:** `pgvector` (`CREATE EXTENSION IF NOT EXISTS vector;`)

---

## 9. Servisler / Modüller / Bileşenler

### 9.1 Trend Intelligence Stack

| Servis | Dosya | Görev | Dış API |
|--------|-------|-------|---------|
| **Trend Engine** | `trend_engine.py` | Ana pipeline orkestrasyonu | feedparser, OpenAI, Supabase |
| **Trend Relevance** | `trend_relevance.py` | Pre-filter + post-filter + adjust_score. Domain taxonomy: AI (3pt), Tech (2pt), Business, Crypto | Pure Python |
| **Trend Enrichment** | `trend_enrichment.py` | key_angles, hooks, pillars çıkarma | OpenAI |
| **Twitter Fetcher** | `twitter_trend_fetcher.py` | Tier 1/2/3 sinyal toplama | Xquik, OpenAI |
| **VIP Scoring** | `vip_scoring.py` | Çarpanlar: VIP Twitter 1.5x, VIP RSS 1.4x, Tier 1 1.3x. Semantic triggers: launch +20, scandal +25, milestone +15, breaking +20. Max cap: 99 | Pure Python |
| **Xquik Client** | `xquik_client.py` | Twitter/X REST API wrapper. Base: `https://xquik.com/api/v1`. Rate: 10/s, 20 burst. Poll: 2s interval, 120s max | Xquik |

### 9.2 Stil & İçerik Stack

| Servis | Dosya | Görev |
|--------|-------|-------|
| **Style Analyzer** | `style_analyzer.py` | 50+ boyut stil DNA: punctuation DNA, emoji strategy, hashtag usage, language mix, capitalization, line structure, opening psychology, closing strategy, word distribution, engagement patterns |
| **Style Constraints** | `style_constraints.py` | Hard kısıtlar: emoji (BANNED/WHITELIST/ALLOWED), link (ALWAYS BANNED, %50-90 reach loss), length min/max, line break, hashtag |
| **Style RAG** | `style_rag.py` | pgvector cosine similarity + engagement + algo_score hybrid (0.4/0.35/0.25). Diversity filter: short/long mix, question/statement, varied openings |
| **Style Ranker** | `style_ranker.py` | 7 boyut: constraint uyumu 25%, algorithm 20%, hook 15%, length 10%, punctuation 10%, vocabulary 10%, reply potential 10% |
| **Algo Scorer** | `algo_scorer.py` | X ağırlıkları: reply_by_author 75x, reply 13.5x, profile_click 12x, bookmark 10x, dwell_2min 10x, repost 1x, like 0.5x, report -369, external_link %50-90 loss |
| **Magic Morning** | `magic_morning.py` | JIT: trends (48h, score>=60) → niche filter → Jaccard dedup (>30% = duplicate) → 3 diverse draft → Xquik score (background). Maliyet: ~$0.003/user/gün |

### 9.3 Analiz & Koçluk Stack

| Servis | Dosya | Görev |
|--------|-------|-------|
| **Account Analyzer** | `account_analyzer.py` | 500 tweet Xquik extract → 80 tweet sample → GPT-4o analiz → 6 boyut skor + strengths + weaknesses + recommendations |
| **Coach Engine** | `coach_engine.py` | 8 kart tipi: opportunity (priority 10), onboarding (9), roast, toast, daily_goal, repurpose, progress, streak. Timezone: Europe/Istanbul |
| **Tweet Collector** | `tweet_collector.py` | Apify actor. Original: 500, replies: 100, quotes: 100. Maliyet: ~$0.30/profil |

### 9.4 Frontend Yapısı

**Sayfalar ve Route'lar:**

| Sayfa | Route | Görev |
|-------|-------|-------|
| `DashboardHome` | `/dashboard` | Ana gösterge paneli |
| `XAIModule` | `/dashboard/create` | Ana içerik üretim arayüzü |
| `TrendDashboardPage` | `/dashboard/trends` | Trend keşif paneli |
| `StyleLabPage` | `/dashboard/style-lab` | Stil profil yönetimi |
| `CoachPage` | `/dashboard/coach` | AI koçluk kartları |
| `AccountAnalysisPage` | `/dashboard/account-analysis` | Hesap analizi |
| `CreatorHubPage` | `/dashboard/creator-hub` | Creator Hub |
| `YouTubeStudioPage` | `/dashboard/youtube-studio` | YouTube Studio |
| `HistoryPage` | `/dashboard/history` | Üretim geçmişi |
| `FavoritesPage` | `/dashboard/favorites` | Kaydedilenler |
| `ABTestPage` | `/dashboard/ab-test` | A/B test |
| `PersonaLabPage` | `/dashboard/persona-lab` | Persona yönetimi |

**Context Provider Sarmalama Sırası:**
```
ThemeProvider → AuthProvider → AccountProvider → CreatorProfileProvider → StylePaletteProvider → ProfileProvider → DashboardLayout
```

---

## 10. MCP Server v3.0 Detaylı Referans

Endpoint: `POST /api/mcp` (JSON-RPC 2.0, Streamable HTTP)
Auth: Bearer token (`MCP_API_KEY` env var)

### 14 Tool

| # | Tool | Açıklama | Cache |
|---|------|----------|-------|
| 1 | `get_today_trends` | Top trendler (24h, kategori/skor filtre) | 5dk |
| 2 | `get_day_recap` | Günlük özet + istatistikler | - |
| 3 | `get_trending_by_category` | Kategoriye göre gruplandırılmış trendler | 5dk |
| 4 | `search_trends` | Full-text search (topic/summary) | - |
| 5 | `get_twitter_trends` | Canlı Twitter/X trendleri | 5dk |
| 6 | `score_tweet` | X algoritma skoru (0-100) + ipuçları | - |
| 7 | `refine_tweet` | AI iyileştirme önerileri (Xquik) | - |
| 8 | `generate_tweet` | Trend bazlı tweet üretimi + algo scoring | - |
| 9 | `analyze_account` | Engagement, stil, top tweet analizi | - |
| 10 | `get_viral_patterns` | Top 20% vs bottom 20% viral analiz | - |
| 11 | `compare_accounts` | Yan yana karşılaştırma + gap analizi | - |
| 12 | `repurpose_content` | Cross-platform dönüşüm (LinkedIn, blog, TikTok, YouTube, Instagram) | - |
| 13 | `get_pipeline_health` | Sistem sağlığı | 60s |
| 14 | `trigger_manual_run` | Manuel pipeline refresh | - |

### 2 Resource

- `typehype://categories` — Kategori listesi ve açıklamaları
- `typehype://algorithm-factors` — X algoritma ranking çarpanları

### 3 Prompt

- `daily_briefing` — Günlük trend briefing workflow
- `tweet_from_trend` — Trend bul → tweet üret → skorla → iyileştir
- `competitor_analysis` — Tam rakip analizi workflow

### Tool Annotations

Her tool `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` annotation'larına sahiptir (MCP spec uyumlu).

---

## 11. Konfigürasyon ve Environment Yapısı

### Backend `.env`

| Değişken | Zorunlu | Kullanıldığı Yer | Açıklama |
|----------|---------|-------------------|----------|
| `SUPABASE_URL` | **Evet** | server.py, tüm DB işlemleri | Supabase proje URL'si |
| `SUPABASE_SERVICE_KEY` | **Evet** | server.py, tüm backend | Service role JWT (tam yetki) |
| `COOKIE_ENCRYPTION_KEY` | **Evet** | server.py startup check | Base64-encoded şifreleme anahtarı. Cookie/session şifreleme için kullanılır. Eksikse server **başlamaz** (sys.exit(1)) |
| `OPENAI_API_KEY` | **Evet** | İçerik üretimi, trend analiz, embeddings | OpenAI API key |
| `OPENROUTER_API_KEY` | Hayır | Trend analizi (GPT-4o-mini proxy) | OpenRouter API key |
| `XQUIK_API_KEY` | **Evet** | xquik_client.py, twitter_trend_fetcher.py | Twitter veri kaynağı |
| `MCP_API_KEY` | Hayır | routes/mcp.py | MCP Server Bearer token |
| `CRON_SECRET` | **Evet** | trends.py (auto-refresh, process-signals), favorites (auto-purge) | `hmac.compare_digest()` ile doğrulanır |
| `YOUTUBE_API_KEY` | Hayır | youtube_api.py | YouTube Data API v3 (yoksa mock mode) |
| `APIFY_API_TOKEN` | Hayır | tweet_collector.py | Apify tweet scraping |
| `TOGETHER_API_KEY` | Hayır | together_finetune.py | Together AI fine-tune |
| `ADMIN_EMAILS` | Hayır | admin.py | Virgülle ayrılmış admin email listesi |
| `ALLOWED_EMAILS` | Hayır | auth.py | Email whitelist. **Boş + DEBUG kapalı = fail-closed (kimse giremez)** |
| `DEBUG` | Hayır | security.py, server.py | `true` → localhost CORS + `/docs` Swagger UI |
| `MODEL_CONTENT` | Hayır | server.py | İçerik modeli (default: `gpt-4o`) |
| `MODEL_VISION` | Hayır | server.py | Görsel model (default: `gpt-4o`) |
| `MODEL_ANALYSIS` | Hayır | server.py | Analiz modeli (default: `gpt-4o-mini`) |
| `MODEL_FALLBACK` | Hayır | trend_engine.py | Yedek model (default: `gpt-4.1-nano`) |
| `CORS_ORIGINS` | Hayır | security.py | Override origin listesi (virgülle ayrılmış) |
| `DAILY_TOKEN_LIMIT` | Hayır | token_tracker.py | Günlük token bütçe (default: 500,000) |
| `RATE_LIMIT_MAX_PER_MIN` | Hayır | rate_limit.py | default: 10 |
| `RATE_LIMIT_DAILY_LIMIT` | Hayır | rate_limit.py | default: 100 |
| `TRUSTED_PROXIES` | Hayır | rate_limit.py | Güvenilir proxy IP'leri |

### Frontend `.env`

| Değişken | Görev |
|----------|-------|
| `REACT_APP_BACKEND_URL` | Backend API base URL |
| `REACT_APP_SUPABASE_URL` | Supabase URL (auth) |
| `REACT_APP_SUPABASE_ANON_KEY` | Supabase anon key |

### GitHub Secrets

`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `CRON_SECRET`

### Feed Yapılandırması

**Authoritative kaynak: Supabase `rss_feeds` tablosu.** `config/rss_feeds.json` dosyası eski bir referans kopyasıdır ve artık pipeline tarafından doğrudan kullanılmaz. Feed ekleme/çıkarma işlemleri Supabase tablosundan yapılır.

---

## 12. Kurulum / Çalıştırma / Deploy Süreci

### Backend (Hetzner VPS)

**systemd Service:** `contentfactory.service`
```ini
[Unit]
Description=ContentFactory API
After=network.target

[Service]
Type=simple
User=contentfactory
WorkingDirectory=/opt/contentfactory/backend
ExecStart=/opt/contentfactory/backend/venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Deploy Süreci:**
1. Dosyaları SCP ile kopyala → `/opt/contentfactory/backend/`
2. Service'i yeniden başlat (aşağıdaki Troubleshooting bölümüne bakın)
3. Health check: `curl https://api.typehype.io/api/health`

> **Operasyonel detaylar (IP, SSH) için `OPS_RUNBOOK.md` dosyasına bakınız.**

### Frontend (Vercel)

- Git push → Vercel otomatik deploy
- Preview: `frontend-*.vercel.app`
- Production: `typehype.io`
- Build: `craco build` (CRA + CRACO)

### Lokal Geliştirme

**Gereksinimler:** Python 3.11+, Node 18+, yarn

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Tüm env değerlerini doldur
uvicorn server:app --reload --port 8000

# Frontend
cd frontend
yarn install
yarn start   # localhost:3000 → REACT_APP_BACKEND_URL=http://localhost:8000
```

> **Not:** `.env.example` dosyası mevcut değildir — oluşturulması önerilir. Gerekli minimum key'ler: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `COOKIE_ENCRYPTION_KEY`, `OPENAI_API_KEY`.

---

## 13. Bağımlılıklar ve Entegrasyonlar

### Dış Servisler

| Servis | Kullanım | Maliyet | Kritiklik |
|--------|----------|---------|-----------|
| **Supabase** | PostgreSQL + Auth + Storage + pgvector | Free tier | **Kritik** |
| **OpenAI** | GPT-4o, GPT-4o-mini, text-embedding-3-small | ~$3/ay | **Kritik** |
| **Xquik** | Twitter/X veri (trends, tweets, analiz, scoring) | $20/ay sabit | **Kritik** |
| **Vercel** | Frontend hosting + CDN | Free tier | **Kritik** |
| **GitHub Actions** | RSS fetching pipeline | Free tier | Önemli |
| **Apify** | Tweet scraping (stil profil) | ~$0.30/profil | Opsiyonel |
| **Together AI** | LLM fine-tuning | Pay-per-use | Opsiyonel |
| **YouTube Data API** | Video/kanal metadata | Free (quota) | Opsiyonel |

### Maliyet Projeksiyonu

| Kullanıcı | OpenAI | Xquik | Toplam |
|-----------|--------|-------|--------|
| 1-10 | ~$3/ay | $20/ay | ~$23/ay |
| 50 | ~$15/ay | $20/ay | ~$35/ay |
| 100 | ~$30/ay | $40/ay (plan upgrade) | ~$70/ay |
| 1000 | ~$300/ay | $200/ay | ~$500/ay |

> Projeksiyon: ortalama kullanıcı günde 5 generation, 3 draft, 1 analiz varsayılmıştır.

### Kritik Python Paketleri

`fastapi` 0.110.1, `uvicorn` 0.25.0, `supabase` 2.13.0, `openai` 1.99.9, `pydantic` 2.12.5, `httpx` 0.28.1, `feedparser` 6.0.11, `cryptography` 46.0.3, `tiktoken` 0.12.0, `stripe` 14.1.0 (henüz aktif değil)

### Kritik Frontend Paketleri

`react` 19.0.0, `@supabase/supabase-js`, `axios`, `@radix-ui/*` (20+ primitif), `tailwindcss`, `react-router-dom`, `framer-motion`, `recharts`, `i18next`, `zod`

---

## 14. Güvenlik Mimarisi

### 10 Katmanlı Savunma

| # | Katman | Dosya | Mekanizma |
|---|--------|-------|-----------|
| 1 | **Authentication** | auth.py | Supabase JWT + email whitelist (fail-closed) + brute force (5 deneme → 15dk ban) |
| 2 | **Authorization** | active_account.py | IDOR koruması: `X-Active-Account-Id` header ownership check |
| 3 | **CSRF** | security.py | Origin/Referer doğrulama (state-changing methods). Vercel preview pattern desteği |
| 4 | **Anti-Automation** | security.py | `X-TH-Client` header zorunluluğu + suspicious UA blocking (curl, wget, httpie, python-requests) |
| 5 | **Rate Limiting** | rate_limit.py | Per-minute (10), per-day (100), burst (3sn/5req → 5dk ban). IP spoofing koruması |
| 6 | **Input Validation** | input_sanitizer.py | Unicode NFKC normalization, zero-width strip, prompt injection regex, HTML strip |
| 7 | **Replay Prevention** | replay_protection.py | Timestamp (5dk window) + nonce (10K LRU). Mutation endpoint'lerde |
| 8 | **Payload Security** | request_size.py | 1MB default, 5MB image, 2048 URL |
| 9 | **Token Budget** | token_tracker.py | 500K/gün (in-memory, restart'ta sıfırlanır) |
| 10 | **Audit** | audit_log.py | Auth failure logging, generation tracking, suspicious pattern alert (5+ token/IP/saat) |

### EXEMPT_PATHS (Anti-curl ve UA check'ten muaf)

```python
EXEMPT_PATHS = {
    "/api/",                          # Root health
    "/api/health",                    # Genel health
    "/api/trends/health",             # Trend health
    "/api/cookies/telegram-update",   # Telegram webhook
    "/api/trends/auto-refresh",       # Cron (X-Cron-Secret ile korunur)
    "/api/trends/process-signals",    # Cron (X-Cron-Secret ile korunur)
    "/api/favorites/auto-purge",      # Cron (X-Cron-Secret ile korunur)
    "/api/cookies/health",            # Cookie health
    "/api/mcp",                       # MCP (Bearer token ile korunur)
}
```

### Güvenlik Headerları (Backend + Vercel)

- `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy: default-src 'self'; connect-src 'self' https://*.supabase.co ...`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

---

## 15. Hata Yönetimi ve Logging

### Custom Exception'lar

| Exception | Dosya | Kullanım |
|-----------|-------|----------|
| `AccountBrokenError` | exceptions.py | Twitter cookie/token expire olduğunda. `platform` ve `reason` property'leri. Frontend'e `ACCOUNT_BROKEN` kodu döner → frontend `account-broken` custom event fırlatır |

### Logging Yapısı

- **Format:** `%(asctime)s - %(name)s - %(levelname)s - %(message)s`
- **Level:** INFO (default)
- **Logger'lar:** `server`, `audit`, `middleware.db_cleanup`, her servis kendi logger'ını kullanır
- **Structured logging:** Hayır — plain text format
- **Log dosyaları:** stdout/stderr → systemd journal (`journalctl -u contentfactory`)

### Alert/Notification

- **Mevcut alerting mekanizması: Yok.** Health endpoint'ler mevcut ama bunları izleyen bir monitoring servisi kurulmamış.
- `audit_log.py` suspicious pattern detection: 5+ farklı token/IP/saat → CRITICAL log yazılır ama notification gönderilmez.

### Hata Yanıt Formatları

```python
# Standart HTTP hata
HTTPException(status_code=403, detail="CSRF doğrulaması başarısız")

# Generation hatası (200 ama success=false)
GenerationResponse(success=False, error="Token budget exceeded")

# Account broken (403 + özel kod)
JSONResponse(status_code=403, content={"code": "ACCOUNT_BROKEN", "platform": "twitter", "message": "..."})
```

---

## 16. Dikkat Edilmesi Gereken Noktalar

1. **EXEMPT_PATHS yönetimi:** Yeni public/cron endpoint eklerken `middleware/security.py` EXEMPT_PATHS'e eklenmezse 403 döner. Cron endpoint'leri eklerken X-Cron-Secret kontrolü de eklenmeli.

2. **Email whitelist fail-closed:** `ALLOWED_EMAILS` boş + `DEBUG` kapalı = kimse login olamaz.

3. **In-memory state:** Rate limiter, brute force tracker, nonce cache, token budget bellekte. Server restart'ta sıfırlanır. `--workers 2` ile her worker ayrı state tutar.

4. **`X-TH-Client` header:** Frontend `api.js` her istekte gönderir. Backend'de yoksa 403. MCP ve cron EXEMPT_PATHS'te.

5. **Multi-account IDOR:** Tüm sorgular `user_id + account_id` filtreli. Yeni endpoint'te unutulmamalı.

6. **Soft delete cascade:** Hesap silindiğinde generations, favorites, style_profiles, coach_* cascade güncellenir (`routes/accounts.py` DELETE).

7. **Ghost account merge:** İlk gerçek hesap bağlandığında "default" placeholder veriler taşınır. Tek seferlik (`routes/accounts.py` PUT).

8. **Feed tanım kaynağı:** `config/rss_feeds.json` eski referanstır. Authoritative kaynak Supabase `rss_feeds` tablosu.

---

## 17. Olası Riskler ve İleride Problem Çıkarabilecek Yerler

### Yüksek Risk

| Risk | Açıklama | Etki |
|------|----------|------|
| **In-memory state kaybı** | Rate limiter, token budget, nonce cache restart'ta sıfırlanır. Workers arası state paylaşımı yok | Restart sonrası burst geçebilir, token bütçe aşılabilir |
| **Orphan worker process'ler** | `systemctl stop` + `--workers 2` orphan bırakabilir, port meşgul kalır | Deploy'da server başlatılamaz |
| **Tek sunucu (SPOF)** | Tüm backend tek VPS'te, yedek yok | Sunucu çökerse tüm API durur |
| **Backup yok** | Supabase free tier auto-backup sınırlı. Manuel backup stratejisi mevcut değil | Veri kaybı riski |
| **Monitoring/alerting yok** | Health endpoint'ler var ama izleyen servis yok | Sorunlar geç fark edilir |

### Orta Risk

| Risk | Açıklama | Etki |
|------|----------|------|
| **Supabase free tier** | DB boyutu, API çağrı sayısı, storage sınırları | Büyüdükçe ücretli plan gerekecek |
| **Güvenlik paket güncellemeleri** | 124 paket pin'lenmiş, vulnerability taraması yapılmıyor | Bilinen açıklar patch'lenmemiş olabilir |
| **Prompt injection yüzeyi** | input_sanitizer.py regex tabanlı, yeni teknikler bypass edebilir | LLM manipülasyonu riski |
| **Test coverage düşük** | 5 test dosyası (sadece trend_relevance + creator_hub) | Regression riski |

### Düşük Risk

| Risk | Açıklama |
|------|----------|
| **n8n dizini (arşiv)** | `n8n/` pasif, kafa karışıklığı |
| **Eski dosya artıkları** | `.backup`, `.bak`, `.old.jsx` dosyaları |
| **Stripe entegrasyonu** | Paket var ama ödeme sistemi aktif değil |

---

## 18. Çözüm Önerileri ve Önleyici Aksiyonlar

### Acil

| Sorun | Çözüm |
|-------|-------|
| **Orphan worker** | systemd service'e `KillMode=control-group` ekle. Alternatif: `ExecStartPre=/usr/bin/fuser -k 8000/tcp` |
| **Backup yok** | Supabase Dashboard → Database → Backups'tan daily backup aktifle. Alternatif: `pg_dump` cron |
| **Monitoring yok** | `/api/trends/health` → UptimeRobot veya BetterStack'e bağla |
| **Eski dosya artıkları** | `.backup`, `.bak`, `.old.jsx` sil, git clean |

### Kısa Vadeli (1-2 Hafta)

| Sorun | Çözüm |
|-------|-------|
| **Test coverage** | Auth flow, generation pipeline, trend scoring integration testleri |
| **Güvenlik taraması** | `pip audit` veya `safety check` |
| **`.env.example`** | Backend ve frontend için `.env.example` dosyası oluştur |
| **Structured logging** | Python `structlog` veya JSON formatter |

### Orta Vadeli (1-3 Ay)

| Sorun | Çözüm |
|-------|-------|
| **SPOF** | İkinci instance + load balancer veya managed platform |
| **In-memory state** | Redis veya Supabase `rate_limits` tablosu |
| **Prompt injection** | ML-based detection (Rebuff, LLM Guard) |
| **Frontend performance** | Code splitting (React.lazy), route-based chunking |

---

## 19. Troubleshooting Playbook

### Senaryo 1: Server Başlamıyor (Port 8000 Meşgul)

```bash
# 1. Service'i durdur
systemctl stop contentfactory

# 2. Port'u tutan process'leri öldür
fuser -k 8000/tcp

# 3. Bekle
sleep 2

# 4. Tekrar başlat
systemctl start contentfactory

# 5. Doğrula
sleep 3
systemctl is-active contentfactory   # "active" olmalı
curl -s http://localhost:8000/api/health
```

### Senaryo 2: Trend Pipeline Çalışmıyor

```bash
# 1. Health check
curl -s https://api.typehype.io/api/trends/health
# trends.last_24h > 0 olmalı

# 2. Son logları kontrol et
journalctl -u contentfactory --no-pager -n 100 | grep -i "trend\|rss\|twitter"

# 3. Manuel tetikle
curl -X POST https://api.typehype.io/api/trends/auto-refresh \
  -H "X-Cron-Secret: $CRON_SECRET"

# 4. Xquik API key geçerli mi?
# Log'da "Xquik" hatası var mı kontrol et

# 5. GitHub Actions çalışıyor mu?
# GitHub → Actions → rss-fetcher workflow son çalışmayı kontrol et
```

### Senaryo 3: Kullanıcılar 403 Alıyor

```bash
# 1. Hangi middleware engelliyor?
journalctl -u contentfactory --no-pager -n 50 | grep "403\|blocked\|CSRF"

# Mesaj: "CSRF blocked" → Origin/Referer sorunu
# Mesaj: "Anti-curl blocked: missing X-TH-Client" → Frontend header eksik
# Mesaj: "Geçersiz istemci" → UA fingerprinting

# 2. CORS origin kontrolü
# security.py ALLOWED_ORIGINS listesini kontrol et

# 3. Email whitelist kontrolü
# .env → ALLOWED_EMAILS değerini kontrol et
```

### Senaryo 4: OpenAI Fatura Yükseldi

```bash
# 1. Token tracker logları
journalctl -u contentfactory --no-pager | grep "token_usage\|budget"

# 2. DAILY_TOKEN_LIMIT değerini düşür
# .env → DAILY_TOKEN_LIMIT=300000

# 3. Trend pipeline frekansını azalt
# OpenClaw cron'u 5x/gün → 3x/gün yap

# 4. Model değiştir
# .env → MODEL_ANALYSIS=openai/gpt-4.1-nano (daha ucuz)
```

### Senaryo 5: MCP Server Yanıt Vermiyor

```bash
# 1. Server çalışıyor mu?
curl -s https://api.typehype.io/api/health

# 2. MCP endpoint testi
curl -s -X POST https://api.typehype.io/api/mcp \
  -H "Authorization: Bearer $MCP_KEY" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'

# 3. Key doğru mu?
# Hetzner .env → MCP_API_KEY kontrol et

# 4. EXEMPT_PATHS'te /api/mcp var mı?
# security.py kontrol et
```

---

## 20. Yeni Gelen Biri İçin Hızlı Anlama Rehberi

### "5 Dakikada Sistemi Anla"

1. **Ne yapıyor?** → AI ile sosyal medya içerik üretimi + trend keşfi + hesap analizi SaaS'ı
2. **Backend nerede?** → `backend/server.py` entry point, Hetzner VPS `api.typehype.io`
3. **Frontend nerede?** → `frontend/src/App.js` entry point, Vercel `typehype.io`
4. **DB nerede?** → Supabase (PostgreSQL + pgvector), 20 tablo
5. **Trend pipeline nasıl çalışıyor?** → GitHub Actions RSS → cron auto-refresh → GPT analiz → DB

### "İlk 30 Dakika: Neyi Okumalıyım?"

```
1. backend/server.py               → App yapısı, middleware stack, router registry
2. backend/middleware/auth.py       → Auth mekanizması
3. backend/middleware/security.py   → Güvenlik kuralları, EXEMPT_PATHS
4. backend/services/trend_engine.py → Trend pipeline mantığı
5. backend/routes/mcp.py           → MCP Server (14 tool)
6. frontend/src/lib/api.js         → Frontend-backend iletişim protokolü
7. frontend/src/App.js             → Routing ve context yapısı
```

### Anahtar Kavramlar

| Kavram | Açıklama |
|--------|----------|
| **Tier 1/2/3** | Twitter sinyal kalitesi. 1: resmi AI hesapları (filtersiz), 2: key people (GPT filtered), 3: keyword search |
| **VIP Scoring** | OpenAI, Anthropic gibi kaynaklar 1.5x çarpan alır |
| **Style Lab v2** | 50+ boyutlu stil DNA → kısıtlar → RAG → üretim → sıralama |
| **Magic Morning** | Login'de JIT üretilen 3 trend bazlı tweet taslağı |
| **Ghost Account** | İlk gerçek hesap bağlanana kadar placeholder |
| **MCP Server** | Claude Code/Desktop ile doğrudan TypeHype verilerine erişim |
| **EXEMPT_PATHS** | Anti-curl ve UA check'ten muaf endpoint'ler (security.py) |

---

## 21. Sonuç / Özet

TypeHype, çok katmanlı mimari üzerinde çalışan, AI-native bir sosyal medya SaaS'tır:

- **3 ana pipeline:** Trend keşfi, içerik üretimi, hesap analizi
- **10 middleware** ile korunan güvenlik katmanı
- **135+ API endpoint**, **20 veritabanı tablosu**, **14 MCP tool**
- **~$23/ay** operasyon maliyeti (free tier'lar dahil)

En büyük teknik borç: in-memory state, tek sunucu SPOF, monitoring/backup eksikliği.

---

## 22. Kritik Devralma Notları

### En Kritik Dosyalar

| Dosya | Risk | Yanlış Değişiklik Sonucu |
|-------|------|--------------------------|
| `server.py` | **Çok yüksek** | Tüm API çöker |
| `middleware/auth.py` | **Çok yüksek** | Auth bypass veya herkes kilitlenir |
| `middleware/security.py` | **Çok yüksek** | CSRF bypass veya meşru istekler engellenir |
| `services/trend_engine.py` | **Yüksek** | Trend pipeline durur |
| `routes/mcp.py` | **Yüksek** | MCP entegrasyonu bozulur |
| `frontend/src/lib/api.js` | **Yüksek** | Frontend-backend iletişimi kopar |

### Yanlış Değiştirilirse Sistemi Bozabilecek Alanlar

- **Middleware sırası** (`server.py`) — Sıra değişirse güvenlik bypass
- **ALLOWED_ORIGINS** (`security.py`) — Production origin silinirse frontend çalışmaz
- **ALLOWED_EMAILS** (`auth.py`) — Boş bırakılırsa kimse login olamaz
- **EXEMPT_PATHS** (`security.py`) — Cron endpoint çıkarılırsa pipeline durur
- **api.js interceptor** — `X-TH-Client` gönderilmezse tüm istekler 403

### Acil Durumda

1. `curl https://api.typehype.io/api/health` → Server durumu
2. `curl https://api.typehype.io/api/trends/health` → Pipeline durumu
3. `journalctl -u contentfactory --no-pager -n 100` → Loglar
4. `lsof -i:8000` → Port durumu
5. `systemctl status contentfactory` → Service durumu
6. Bkz: [Troubleshooting Playbook](#19-troubleshooting-playbook)

---

> **Bu doküman v3.1:** v3.0'dan farklar: API endpoint referansı eklendi (135+ endpoint), DB şeması detaylandırıldı (kolon tipleri, FK'ler, RLS), MCP Server detaylı referans eklendi, güvenlik mimarisi ayrı bölüm olarak genişletildi, Troubleshooting Playbook eklendi (5 senaryo), hassas bilgiler çıkarıldı, OpenClaw Cron açıklandı, feed sayısı tutarsızlığı düzeltildi, maliyet projeksiyonu eklendi, hata yönetimi bölümü eklendi.
>
> **Operasyonel bilgiler** (sunucu IP, SSH path, API key değerleri) bu dokümanda yer almaz. Bu bilgiler için ops-level erişim gereklidir.

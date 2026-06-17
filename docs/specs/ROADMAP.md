# ContentFactory Yol Haritası

> Son güncelleme: 2026-02-07
> Durum: Berkay onayı bekleniyor

---

## Mevcut Durum Özeti

### ✅ Çalışan
- X AI Module: Tweet / Quote / Reply / Article üretimi (GPT-4o)
- Modüler prompt sistemi (persona, tone, knowledge, length)
- Style Lab: Twitter stil klonlama (100 tweet scrape + 9 boyutlu AI analiz)
- FxTwitter ile tweet fetch (Quote/Reply için)
- Favorites & History
- Supabase Auth
- Dark/Light mode

### 🟡 Placeholder (Sadece UI Shell)
- YouTube Intelligence
- InstaFlow (Instagram)
- TikTrend Pulse (TikTok)
- LinkShareAI (LinkedIn)
- Blog Architect

---

## FAZ 1: X AI Module Tamamlama (1-2 hafta)

X AI zaten çalışıyor ama eksik parçalar var.

### 1.1 Trend Discovery & Entegrasyonu
**Mevcut:** n8n workflow RSS ile trend çekip Notion'a yazıyor
**Hedef:** Bird CLI ile direkt tweet scrape + AI analiz + in-app trend dashboard

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Trend Engine Backend**: Belirli niche/keyword'ler için Bird CLI ile son 24-48 saat trending tweet'leri çek | M |
| B | **Trend Analiz**: GPT-4o ile trending konuları kategorize et (tech, crypto, gündem, lifestyle...) | S |
| C | **Trend Dashboard UI**: X AI modülünde "🔥 Trendler" tab'ı. Konu kartları, engagement metrikleri, "Bu konuda yaz" butonu | M |
| D | **n8n Entegrasyonu**: Mevcut n8n workflow'u güncelle. RSS yerine Bird CLI tweet scrape, Notion yerine Supabase'e yaz, OpenClaw ile tetikle | M |
| E | **Otomatik Trend Refresh**: Cron job ile 6 saatte bir trend güncelleme | S |

**n8n İyileştirme Detayı:**
- Mevcut: RSS → n8n → Notion (basit, sınırlı)
- Yeni: Bird CLI tweet scrape → Supabase → AI analiz → Trend skorlama
- OpenClaw cron ile tetikleme (n8n webhook trigger)
- Notion'a yazmaya devam edebilir (backup) ama ana data Supabase'de

### 1.2 Account Analysis (xpatla tarzı)
**Hedef:** Herhangi bir Twitter hesabını analiz et, güçlü/zayıf yönlerini bul

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Profile Scraper**: Bird CLI ile hedef hesabın son 100 tweet + bio + metrics | S |
| B | **AI Account Analysis**: GPT-4o ile hesap analizi (en iyi içerik türü, engagement pattern, posting sıklığı, büyüme önerileri) | M |
| C | **Account Analysis UI**: "Hesap Analizi" sayfası veya Style Lab'a entegre. Radar chart, strengths/weaknesses, öneriler | M |
| D | **Competitor Comparison**: 2-3 hesabı yan yana karşılaştır | L |

### 1.3 AI Coach
**Hedef:** Kişiselleştirilmiş içerik koçu, kullanıcının geçmişine göre öneri

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Performance Tracker**: Üretilen içeriklerin engagement'ını takip et (post ettikten sonra geri bildirim) | M |
| B | **AI Coaching Engine**: Kullanıcının en iyi performans gösteren içeriklerini analiz et, pattern bul | M |
| C | **Coach UI**: "Bugün şu tarz tweet at", "Bu saatte paylaş", "Son 1 haftada X persona daha iyi çalıştı" önerileri | M |

### 1.4 Optimal Posting Times
**Hedef:** Kullanıcının audience'ına göre en iyi paylaşım saatleri

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Engagement Data Collection**: Kullanıcının tweet'lerinin saat bazlı engagement'ını topla | M |
| B | **Time Analysis**: En iyi saatleri hesapla, heatmap oluştur | S |
| C | **Posting Calendar UI**: Haftalık/günlük heatmap, "Şimdi paylaş" önerisi | M |

### 1.5 Görsel & Medya Desteği (Gelişmiş)
**Mevcut:** Image upload var ama AI analiz yok
**Hedef:** Görsel analiz + video/GIF önerisi

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Image AI Analysis**: Yüklenen görseli GPT-4o vision ile analiz et, içerik önerisi üret | S |
| B | **Media Suggestion Engine**: Konu bazlı GIF/meme/görsel önerisi (Giphy/Unsplash API) | M |
| C | **Video Script**: Tweet'i video script'e çevir (TikTok/Reels formatında) | S |

### 1.6 Multi-Account Support
**Hedef:** Birden fazla Twitter hesabı yönetimi

| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Account Switcher**: Birden fazla stil profili arası geçiş | S |
| B | **Per-Account Settings**: Her hesap için ayrı persona/tone defaults | M |
| C | **Cross-Post**: Aynı içeriği birden fazla hesaba uyarla | M |

---

## FAZ 2: LinkedIn Module (1-2 hafta)

LinkedIn organik büyüme çok popüler. Modül tamamen yeni yazılacak.

### 2.1 Post Generation
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **LinkedIn Prompt System**: LinkedIn'e özel persona/tone/format (carousel post, story post, listicle, poll) | M |
| B | **Format Templates**: Hook → Story → Insight → CTA yapısı, LinkedIn formatına uygun | M |
| C | **LinkedIn Post UI**: Tweet UI'ın LinkedIn adaptasyonu. Uzunluk: Micro/Standard/Long/Article | M |

### 2.2 Carousel Generator
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Carousel Content**: AI ile slide-by-slide carousel içerik üretimi | M |
| B | **Carousel Preview**: Slide preview UI (swipeable) | L |
| C | **Export**: PDF/PNG olarak carousel export | M |

### 2.3 LinkedIn Trends
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **LinkedIn Trending Topics**: Web scraping veya API ile trending konular | M |
| B | **Industry Filter**: Sektör bazlı filtreleme | S |

---

## FAZ 3: Instagram Module (1-2 hafta)

### 3.1 Caption Generation
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Instagram Prompt System**: Caption formatına özel (emoji ağırlıklı, hashtag otomasyonu, CTA) | M |
| B | **Hashtag Engine**: Konu bazlı trending + niche hashtag önerisi (mix strategy) | M |
| C | **Caption UI**: Görsel yükleme + caption üretimi + hashtag bloğu | M |

### 3.2 Reel Script Generator
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Reel Script Engine**: Hook → Content → CTA formatında 15-60 sn script | M |
| B | **Trending Audio Suggestion**: Popüler audio/müzik önerisi (manual DB veya API) | L |
| C | **Script UI**: Timeline view, timing notları | M |

### 3.3 Story Ideas
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Story Sequence**: Günlük story serisi önerisi (poll, question, behind-the-scenes) | S |
| B | **Story UI**: Story card dizaynı | S |

---

## FAZ 4: Blog Architect (1-2 hafta)

### 4.1 Full Blog Post Generation
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Outline Generator**: Konu → AI ile detaylı outline (H2/H3 yapısı) | M |
| B | **Section-by-Section Writing**: Her bölümü ayrı ayrı veya toplu üret | L |
| C | **SEO Optimization**: Keyword density, meta description, title tag önerisi | M |
| D | **Blog Editor UI**: Rich text editor (markdown veya WYSIWYG), section navigation | L |

### 4.2 Content Repurpose
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Blog → Tweet Thread**: Blog post'u tweet thread'e çevir | S |
| B | **Blog → LinkedIn Post**: Blog'un LinkedIn versiyonu | S |
| C | **Blog → Instagram Carousel**: Blog'u carousel slide'lara böl | M |
| D | **Repurpose UI**: Tek tuşla farklı platformlara dönüştür | M |

---

## FAZ 5: YouTube Module (1-2 hafta)

### 5.1 Script & Idea Generation
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Video Idea Generator**: Niche + trend analizi ile video fikri | M |
| B | **Script Writer**: Intro → Sections → Outro formatında tam script | L |
| C | **Thumbnail Concept**: AI ile thumbnail metin/konsept önerisi | S |
| D | **Script UI**: Timeline editor, bölüm bölüm düzenleme | M |

### 5.2 Title & Description Optimizer
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Title Generator**: CTR odaklı title önerileri (5-10 varyant) | S |
| B | **Description Template**: SEO uyumlu description + timestamp + tag | M |
| C | **Tag Suggestion**: Video konusuna göre tag önerisi | S |

---

## FAZ 6: TikTok Module (1 hafta)

### 6.1 Short-Form Script
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **TikTok Script Engine**: 15/30/60 sn script formatları (hook-heavy) | M |
| B | **Trend Integration**: TikTok trending sounds/effects (manual veya API) | L |
| C | **Script UI**: Video timeline + overlay text önerisi | M |

### 6.2 Caption & Hashtag
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **TikTok Caption**: Kısa, hook'lu caption üretimi | S |
| B | **TikTok Hashtags**: Trending + niche hashtag mix | S |

---

## FAZ 7: Cross-Platform & Advanced (2-3 hafta)

### 7.1 Content Calendar
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Calendar UI**: Haftalık/aylık takvim görünümü | L |
| B | **Auto-Schedule**: AI ile haftalık içerik planı oluştur | M |
| C | **Platform Distribution**: Her güne platform + içerik türü ata | M |
| D | **Drag & Drop**: İçerikleri takvimde sürükle-bırak | M |

### 7.2 Analytics Dashboard
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Generation Stats**: Kaç içerik üretildi, hangi persona/tone en çok kullanıldı | M |
| B | **Engagement Tracking**: Post edilen içeriklerin performansı (manual input veya API) | L |
| C | **Insights**: "Bu hafta en iyi X persona çalıştı", "Spark uzunluğu daha çok etkileşim aldı" | M |

### 7.3 Team & Collaboration
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Multi-User**: Takım üyeleri, rol bazlı erişim | L |
| B | **Approval Flow**: İçerik onay süreci (draft → review → approved) | M |
| C | **Shared Library**: Takım genelinde favori içerikler | S |

### 7.4 API & Integrations
| Adım | Açıklama | Effort |
|------|----------|--------|
| A | **Direct Post API**: Twitter/LinkedIn/Instagram'a direkt paylaşım | L |
| B | **Webhook**: İçerik üretildiğinde webhook tetikle (Zapier/n8n) | S |
| C | **Export**: CSV, PDF, Notion export | M |

---

## Öncelik Sıralaması (Berkay Onayı İçin)

| Sıra | Faz | Açıklama | Tahmini Süre | Etki |
|------|-----|----------|-------------|------|
| 🥇 1 | 1.1 | Trend Discovery + n8n iyileştirme | 3-4 gün | 🔥🔥🔥 |
| 🥇 2 | 1.2 | Account Analysis | 2-3 gün | 🔥🔥🔥 |
| 🥇 3 | 1.5 | Görsel & Medya Desteği | 2 gün | 🔥🔥 |
| 🥈 4 | 1.3 | AI Coach | 3-4 gün | 🔥🔥 |
| 🥈 5 | 1.6 | Multi-Account | 2 gün | 🔥🔥 |
| 🥈 6 | 2 | LinkedIn Module | 5-7 gün | 🔥🔥🔥 |
| 🥉 7 | 4 | Blog Architect | 5-7 gün | 🔥🔥 |
| 🥉 8 | 3 | Instagram Module | 5-7 gün | 🔥🔥 |
| 🥉 9 | 5 | YouTube Module | 5-7 gün | 🔥 |
| 🥉 10 | 6 | TikTok Module | 3-5 gün | 🔥 |
| 🏅 11 | 7.1 | Content Calendar | 5-7 gün | 🔥🔥🔥 |
| 🏅 12 | 7.2 | Analytics Dashboard | 5-7 gün | 🔥🔥 |
| 🏅 13 | 1.4 | Optimal Posting Times | 3-4 gün | 🔥🔥 |
| 🏅 14 | 7.3 | Team & Collaboration | 7-10 gün | 🔥 |
| 🏅 15 | 7.4 | API & Integrations | 5-7 gün | 🔥 |

**Effort Legend:** S = Small (birkaç saat), M = Medium (1-2 gün), L = Large (3+ gün)

---

## n8n Mevcut → Yeni Mimari

### Şu an
```
RSS Feed → n8n Workflow → Notion Database
```
Sınırlı: Sadece RSS, gerçek tweet engagement yok, AI analiz yok

### Yeni Mimari
```
Bird CLI (tweet scrape) ─┐
                         ├→ Supabase (trends table) → AI Analiz → Trend Skorlama
RSS Feed (backup) ───────┘                              ↓
                                                  ContentFactory UI
                                                        ↓
OpenClaw Cron ──→ n8n Webhook ──→ Scrape + Analyze ──→ Supabase
                                                        ↓
                                              Notion (backup/archive)
```

**Avantajlar:**
- Gerçek tweet data (engagement, media, reply count)
- AI ile trend kategorileme ve skorlama
- In-app trend gösterimi (Notion'a gitmeye gerek yok)
- OpenClaw cron ile otomatik tetikleme
- n8n hala orchestration layer olarak kalıyor

---

## Teknik Notlar

- **Backend**: Tüm yeni modüller FastAPI router olarak eklenecek (`routes/`)
- **Prompt System**: Her platform için ayrı prompt modülü (`prompts/linkedin.py`, `prompts/instagram.py`...)
- **Supabase**: Yeni tablolar: `trends`, `account_analyses`, `content_calendar`, `team_members`
- **Bird CLI**: Tweet scraping'in temel aracı (mevcut, test edilmiş)
- **FxTwitter API**: Tek tweet okuma için (Bird CLI timeout sorunu)
- **Deploy**: Hetzner VPS (46.225.27.85), Docker compose ile

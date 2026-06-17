# X AI Modülü - Kalan İşler Detaylı Plan

## 1. Medya Önerisi Sistemi
**Amaç:** Tweet konusuna göre GIF, görsel veya meme önerisi

### Backend
- `backend/services/media_suggester.py`:
  - Giphy API entegrasyonu (ücretsiz API key ile)
  - Unsplash API entegrasyonu (ücretsiz, 50 req/saat)
  - GPT-4o ile konu → arama terimi dönüşümü (Türkçe konu → İngilizce search query)
  - 3-5 medya önerisi döndür (thumbnail, URL, tür)

- `backend/routes/media.py`:
  - `POST /api/media/suggest` → {topic, type: "gif"|"image"|"all"} → medya önerileri
  - `GET /api/media/search?q=...&type=gif` → direkt arama

### Frontend
- Tweet üretildikten sonra her GenerationCard'ın altında "📎 Medya Öner" butonu
- Tıklayınca: Topic'e göre 3-5 GIF/görsel grid'i açılır (modal veya inline)
- Seçilen medya tweet kartına eklenir (preview)
- Kopyalama sırasında medya URL'si de kopyalanır

### Gereksinimler
- Giphy API key (ücretsiz: https://developers.giphy.com)
- Unsplash API key (ücretsiz: https://unsplash.com/developers)
- Berkay'ın API key'leri .env'e eklemesi gerekecek

### Effort: 3-4 saat
### Berkay Gerekli mi: Evet (API key'ler)

---

## 2. Video Script Dönüşümü
**Amaç:** Üretilen tweet'i Reels/TikTok/YouTube Short script'ine çevir

### Backend
- `backend/prompts/video_script.py`:
  - Tweet → 15s/30s/60s video script dönüşüm prompt'ları
  - Format: Hook (0-3s) → Content (3-25s) → CTA (son 5s)
  - Text overlay önerileri (hangi cümle ekranda görünecek)
  - B-roll / görsel önerileri
  - Müzik/ses tonu önerisi

- `backend/routes/repurpose.py`:
  - `POST /api/repurpose/video-script` → {content, duration: 15|30|60, platform: "reels"|"tiktok"|"shorts"}
  - Dönüş: {script, overlays[], visual_suggestions[], music_mood}

### Frontend  
- Her GenerationCard'da "🎬 Video Script'e Çevir" butonu
- Tıklayınca: Süre seçici (15s/30s/60s) + Platform seçici
- Script sonucu: Timeline görünümü
  - Her bölüm: Süre | Metin | Overlay | Görsel notu
  - Kopyala butonu (script + overlay notları)

### Gereksinimler: Yok (mevcut OpenAI API yeterli)
### Effort: 3-4 saat
### Berkay Gerekli mi: Hayır

---

## 3. Multi-Account (Stil Profili Yönetimi)
**Amaç:** Birden fazla Twitter hesabı/stil profili arası hızlı geçiş

### Backend
- Mevcut `style_profiles` tablosu zaten multi-profile destekliyor
- `backend/routes/styles.py`'a ekleme:
  - `PUT /api/styles/{id}/defaults` → {default_persona, default_tone, default_length}
  - Her profil için varsayılan ayarlar kaydetme

### Frontend
- StyleSelector component'i genişlet:
  - Dropdown yerine, aktif profil kartı + hızlı geçiş
  - Her profil için mini avatar (hesap baş harfi + renk)
  - "Varsayılan ayarlarla üret" toggle'ı
  - Profil seçince persona/tone/length otomatik değişsin

- DashboardLayout header'a "Aktif Stil" göstergesi

### Gereksinimler: Yok
### Effort: 2-3 saat
### Berkay Gerekli mi: Hayır

---

## 4. AI Coach
**Amaç:** Kullanıcının üretim geçmişine bakıp performans önerileri verme

### Backend
- `backend/services/ai_coach.py`:
  - Son 50 üretimi analiz et (generations tablosundan)
  - Pattern tespiti:
    - En çok kullanılan persona/tone/length
    - En uzun/kısa üretimler
    - Hangi knowledge mode'lar kullanılmış
    - Favori oranı (favorilere eklenen / toplam)
  - GPT-4o ile kişiselleştirilmiş öneriler:
    - "Otorite persona'sı senin için daha iyi çalışıyor"
    - "Spark uzunluğunda daha çok favori ekliyorsun"
    - "Contrarian knowledge mode'u dene, daha az kullanmışsın"
    - Haftalık içerik planı önerisi

- `backend/routes/coach.py`:
  - `GET /api/coach/insights` → Analiz + öneriler
  - `GET /api/coach/weekly-plan` → Haftalık içerik planı önerisi

### Frontend
- Sidebar'a "🧠 AI Coach" ekle (veya Dashboard'a widget)
- Coach sayfası:
  - Üstte: Kullanım istatistikleri (doughnut chart)
    - Persona dağılımı, Tone dağılımı, Length dağılımı
  - Ortada: AI önerileri (3-5 madde, kartlar halinde)
    - Her kart: Öneri + Gerekçe + "Dene" butonu (X AI'a ayarlarla yönlendir)
  - Altta: Haftalık plan önerisi (günlere bölünmüş)

### Gereksinimler: Yeterli üretim geçmişi (en az 10-20 üretim)
### Effort: 4-5 saat
### Berkay Gerekli mi: Hayır

---

## 5. Optimal Posting Times
**Amaç:** Kullanıcının audience'ına göre en iyi paylaşım saatleri

### Backend
- `backend/services/posting_optimizer.py`:
  - Bird CLI ile kullanıcının son 100 tweet'ini çek (zaten style scraper'da var)
  - Her tweet'in saatini ve engagement'ını al
  - Saat bazlı engagement ortalaması hesapla
  - GPT-4o ile analiz: En iyi saatler + gerekçe
  - Genel Twitter istatistikleri ile karşılaştır

- `backend/routes/posting_times.py`:
  - `POST /api/posting-times/analyze` → {username} → heatmap data + öneriler
  - `GET /api/posting-times/general` → Genel Twitter best practices

### Frontend
- Account Analysis sayfasına entegre (veya ayrı tab)
- 7x24 heatmap: Gün (Pzt-Paz) x Saat (00-23)
  - Renk yoğunluğu: engagement skoru
  - Hover: "Salı 19:00 - Ort. 45 like, 12 RT"
- Sağda: Top 5 en iyi saat + gerekçe
- "Şimdi paylaş!" banner'ı (eğer şu an iyi bir saat ise)

### Gereksinimler: Bird CLI çalışıyor olmalı
### Effort: 4-5 saat  
### Berkay Gerekli mi: Hayır (Bird CLI cookie'leri güncel ise)

---

## 6. Direct Post (Tweetle Butonu)
**Amaç:** Üretilen içeriği direkt Twitter'a paylaş

### Yaklaşım A: Twitter Web Intent (Basit, Hemen)
- URL: `https://twitter.com/intent/tweet?text=...`
- Yeni sekmede Twitter açılır, metin doldurulmuş olur
- Kullanıcı "Tweet" butonuna basar
- Ek API key gerektirmez

### Yaklaşım B: Twitter API v2 (Gelişmiş, OAuth gerekli)
- OAuth 2.0 PKCE ile kullanıcı auth
- `POST /2/tweets` ile direkt post
- Media upload desteği
- Scheduled tweets

### Öneri: Yaklaşım A ile başla (5 dakika), sonra B'ye geçiş planla

### Frontend
- GenerationCard'daki "Tweetle" butonu:
  - A: `window.open(twitterIntentUrl)` → direkt çalışır
  - Buton ikonu: Twitter kuşu + "Paylaş"
  - Thread ise: Her tweet için ayrı intent veya uyarı

### Effort: A: 30 dakika, B: 1-2 gün (OAuth setup)
### Berkay Gerekli mi: A: Hayır, B: Evet (Twitter Developer Portal)

---

## 7. Source Add Fix (CORS Sorunu)
**Amaç:** Style Lab'da yeni Twitter hesabı ekleme

### Sorun
- Frontend'den `POST /api/sources/add` çağrısı CORS veya network hatası veriyor
- Backend'de Bird CLI tweet scraping timeout olabilir

### Debug Planı
1. Backend'i başlat, `curl` ile direkt test et
2. CORS ayarlarını kontrol et (server.py'deki CORS_ORIGINS)
3. Bird CLI'ın çalışıp çalışmadığını test et (`bird scrape-tweets @test --count 5`)
4. Timeout ayarlarını kontrol et (scraping uzun sürebilir)
5. Frontend'deki axios error'ı logla

### Olası Çözümler
- Bird CLI timeout → async background job'a çevir (WebSocket ile progress)
- CORS → .env'deki CORS_ORIGINS'a frontend URL ekle
- Network → proxy ayarı kontrol

### Effort: 1-2 saat (debug)
### Berkay Gerekli mi: Belki (Bird CLI cookie refresh)

---

## Öncelik Sırası ve Tahmini Süre

| # | İş | Effort | Berkay? | Etki |
|---|---|--------|---------|------|
| 1 | Direct Post (Intent) | 30 dk | Hayır | 🔥🔥🔥 |
| 2 | Video Script Dönüşümü | 3-4 saat | Hayır | 🔥🔥🔥 |
| 3 | Source Add Fix | 1-2 saat | Belki | 🔥🔥🔥 |
| 4 | Multi-Account | 2-3 saat | Hayır | 🔥🔥 |
| 5 | Medya Önerisi | 3-4 saat | Evet (API key) | 🔥🔥 |
| 6 | AI Coach | 4-5 saat | Hayır | 🔥🔥 |
| 7 | Optimal Posting Times | 4-5 saat | Hayır | 🔥 |

**Toplam tahmini:** ~18-23 saat

**Hemen yapabileceğim (Berkay'sız):** 1, 2, 3 (debug), 4, 6
**Berkay gereken:** 5 (API key), 7 (cookie check)

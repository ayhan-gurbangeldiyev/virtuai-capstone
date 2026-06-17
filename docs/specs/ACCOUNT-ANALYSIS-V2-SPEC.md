# Account Analysis v2 — Detaylı Spec

> Tarih: 2026-02-23
> Durum: Berkay onayı bekleniyor

## Mevcut Durum

Backend (`routes/account_analysis.py`) ve frontend (`AccountAnalysisPage.jsx`) çalışıyor.
- 6 boyutlu radar chart (content_quality, engagement_rate, consistency, creativity, community, growth_potential)
- SWOT kartları (strengths, weaknesses, recommendations)
- Top tweets, tone analysis, posting frequency, hashtag strategy, growth tips
- Analiz geçmişi + cache (DB upsert)
- GPT-4o-mini ile analiz

## Değişiklik Planı

### 1. Radar Chart: 6 → 5 Metrik (Yeni Metrikler)

**Eski (Mevcut):**
| Metrik | Açıklama |
|--------|----------|
| Content Quality | Genel içerik kalitesi |
| Engagement Rate | Etkileşim oranı |
| Consistency | Tutarlılık |
| Creativity | Yaratıcılık |
| Community | Topluluk |
| Growth Potential | Büyüme potansiyeli |

**Yeni (v2):**
| Metrik | Key | Açıklama | Nasıl Ölçülür |
|--------|-----|----------|---------------|
| Kanca Gücü | `hook_power` | Tweet'lerin ilk cümlesinin dikkat çekiciliği | İlk 20 kelimenin soru/rakam/provokasyon/merak boşluğu içerip içermediği. Hook pattern analizi (How/Why/What if/Unpopular opinion/Thread). İlk cümle ile engagement korelasyonu. |
| Etkileşim Potansiyeli | `engagement_potential` | Like/RT/reply tetikleme gücü | Ortalama like/RT/reply oranı (follower'a göre normalize). CTA kullanımı (soru sorma, "RT if", poll). Reply/quote oranı (konuşma başlatma). Viral tweet yüzdesi (>10x ortalama). |
| Format Çeşitliliği | `format_diversity` | İçerik format mix'i | Tek tweet vs thread vs quote vs reply dağılımı. Medya tipi çeşitliliği (text-only, image, video, link, poll). Thread kullanım oranı ve thread başarısı. |
| Duygu Yoğunluğu | `emotional_range` | Duygu paleti genişliği | Sentiment analizi dağılımı (pozitif/negatif/nötr). Duygu çeşitliliği (mizah, öfke, ilham, merak, şaşkınlık). Emoji/ifade kullanım çeşitliliği. Provokasyon vs bilgi vs eğlence dengesi. |
| Görsel Kullanımı | `visual_usage` | Medya ekleme kalitesi ve sıklığı | Medya ekleme oranı (%). Görsel çeşitliliği (foto, video, GIF, infografik). Medyalı vs medyasız tweet engagement karşılaştırması. Thumbnail/preview kalitesi. |

**Skor Aralıkları (her metrik için):**
- 85-100: Üst düzey, sektör lideri seviyesi
- 70-84: Güçlü, tutarlı performans
- 50-69: Ortalama, gelişim alanları var
- 30-49: Zayıf, ciddi iyileştirme gerekli
- 0-29: Kritik, neredeyse hiç kullanılmıyor

### 2. Backend Değişiklikleri

**`routes/account_analysis.py` → GPT prompt güncellemesi:**

```python
# Yeni dimensions yapısı
"dimensions": {
    "hook_power": 0-100,        # Kanca Gücü
    "engagement_potential": 0-100, # Etkileşim Potansiyeli
    "format_diversity": 0-100,   # Format Çeşitliliği
    "emotional_range": 0-100,    # Duygu Yoğunluğu
    "visual_usage": 0-100        # Görsel Kullanımı
}
```

**Prompt'a eklenecek detaylı talimatlar:**

```
RADAR CHART METRİKLERİ (her biri 0-100):

1. hook_power (Kanca Gücü):
   - Tweet'lerin ilk cümlesini analiz et
   - Soru ile başlayan tweet oranı
   - Rakam/istatistik ile açan tweet oranı
   - Merak boşluğu (curiosity gap) kullanımı
   - "Unpopular opinion", "Hot take", "Thread:" gibi hook pattern'ları
   - İlk cümle uzunluğu optimizasyonu (kısa ve çarpıcı mı?)
   
2. engagement_potential (Etkileşim Potansiyeli):
   - Like/RT/Reply ortalaması (follower sayısına göre normalize)
   - Engagement rate = (likes + retweets + replies) / followers * 100
   - CTA kullanımı: soru sorma, anket, "RT if you agree"
   - Konuşma başlatma: reply ve quote tweet oranı
   - Viral tweet yüzdesi (ortalama engagement'ın 10x üstü)
   
3. format_diversity (Format Çeşitliliği):
   - Tek tweet / Thread / Quote / Reply dağılım dengesi
   - Medya tipi çeşitliliği: salt metin, görsel, video, link, GIF
   - Thread kullanım oranı ve thread'lerin engagement farkı
   - Monotonluk skoru: hep aynı formatta mı yoksa çeşitli mi?
   
4. emotional_range (Duygu Yoğunluğu):
   - Kaç farklı duygu tonu var: mizah, ciddiyet, öfke, ilham, merak, şaşkınlık
   - Sentiment dağılımı: pozitif/negatif/nötr yüzdeleri
   - Emoji kullanım çeşitliliği ve uygunluğu
   - Provokasyon dengesi: fazla mı az mı, doğru mu kullanılıyor?
   - Kişisel hikaye/anekdot paylaşım oranı
   
5. visual_usage (Görsel Kullanımı):
   - Medya ekleme oranı (tüm tweet'lerin kaçında medya var)
   - Medya türü çeşitliliği: statik görsel, video, GIF, infografik, screenshot
   - Medyalı tweet'lerin engagement farkı (medyasızlara göre)
   - Görsel kalitesi: orijinal içerik mi yoksa hep aynı stock/screenshot mu?
```

**Ek: Tweet data'dan otomatik hesaplanacak metrikler (GPT'ye gönderilecek):**

```python
# Tweet'lerden çıkarılacak istatistikler
stats = {
    "total_tweets": len(tweets),
    "avg_likes": ...,
    "avg_retweets": ...,
    "avg_replies": ...,
    "engagement_rate": (avg_likes + avg_rts + avg_replies) / max(followers, 1) * 100,
    "media_rate": media_count / total * 100,  # % medya içeren
    "thread_rate": thread_count / total * 100, # % thread olan
    "question_rate": question_count / total * 100, # % soru içeren
    "avg_length": ..., # ortalama tweet uzunluğu
    "emoji_rate": emoji_count / total * 100, # % emoji içeren
    "link_rate": link_count / total * 100, # % link içeren
    "reply_rate": reply_count / total * 100, # % reply olan
    "quote_rate": quote_count / total * 100, # % quote olan
    "viral_tweets": viral_count, # >10x avg engagement
    "top_engagement": max_engagement, # en yüksek toplam etkileşim
    "media_types": {"image": X, "video": Y, "gif": Z, "none": W},
}
```

Bu stats GPT prompt'una eklenerek daha doğru skorlama sağlanacak.

### 3. Frontend Değişiklikleri

**`DimensionRadar` component güncellemesi:**

```jsx
const data = [
    { subject: t('account.dimensions.hookPower'), value: dimensions.hook_power || 0 },
    { subject: t('account.dimensions.engagement'), value: dimensions.engagement_potential || 0 },
    { subject: t('account.dimensions.formatDiversity'), value: dimensions.format_diversity || 0 },
    { subject: t('account.dimensions.emotionalRange'), value: dimensions.emotional_range || 0 },
    { subject: t('account.dimensions.visualUsage'), value: dimensions.visual_usage || 0 },
];
```

**Radar chart renk şeması:**
- Stroke: `#a855f7` (purple-500)
- Fill: `#a855f7` opacity 0.2
- Grid: `rgba(255,255,255,0.1)`
- Neon glow efekti: `filter: drop-shadow(0 0 6px rgba(168,85,247,0.4))`

**Loading state iyileştirmesi:**
```
Adım 1 (0-5s):   "🔍 @kullaniciadi hesabını buluyoruz..."
Adım 2 (5-10s):  "📊 Son 500 tweet taranıyor..."
Adım 3 (10-15s): "🧠 Kanca gücü analiz ediliyor..."
Adım 4 (15-20s): "🎨 Format çeşitliliği hesaplanıyor..."
Adım 5 (20-25s): "💡 Duygu paleti çıkarılıyor..."
Adım 6 (25-30s): "📈 Rapor hazırlanıyor..."
```

### 4. Cache Mekanizması (Zaten Var, İyileştirme)

Mevcut: Backend'de aynı user+username varsa upsert yapılıyor.

**İyileştirme:**
- Frontend'de "Son güncelleme: X saat önce" badge'i göster
- 1 saatten yeni cache → direkt göster, API çağırma
- 1-24 saat → göster + "Yenile" butonu
- 24 saat+ → otomatik yeniden analiz öner

```jsx
// Cache freshness kontrolü
const cacheAge = Date.now() - new Date(item.updated_at).getTime();
const isStale = cacheAge > 24 * 60 * 60 * 1000; // 24h
const isFresh = cacheAge < 60 * 60 * 1000; // 1h
```

### 5. Private Hesap Handling

```python
# Backend'de kontrol
if user_info.get('is_private'):
    raise HTTPException(
        status_code=403, 
        detail="Bu hesap gizli (private). Gizli hesaplar analiz edilemez."
    )
```

### 6. i18n Keys (Yeni/Güncellenen)

```json
{
  "account.dimensions.hookPower": "Kanca Gücü",
  "account.dimensions.engagement": "Etkileşim",
  "account.dimensions.formatDiversity": "Format Çeşitliliği",
  "account.dimensions.emotionalRange": "Duygu Yoğunluğu",
  "account.dimensions.visualUsage": "Görsel Kullanımı",
  "account.cacheAge": "Son güncelleme: {{time}}",
  "account.refreshAnalysis": "Yenile",
  "account.privateAccount": "Bu hesap gizli. Gizli hesaplar analiz edilemez.",
  "account.loadingSteps.finding": "🔍 @{{username}} hesabını buluyoruz...",
  "account.loadingSteps.scanning": "📊 Son tweetler taranıyor...",
  "account.loadingSteps.hookAnalysis": "🧠 Kanca gücü analiz ediliyor...",
  "account.loadingSteps.formatAnalysis": "🎨 Format çeşitliliği hesaplanıyor...",
  "account.loadingSteps.emotionAnalysis": "💡 Duygu paleti çıkarılıyor...",
  "account.loadingSteps.preparing": "📈 Rapor hazırlanıyor..."
}
```

### 7. DB Şeması (Mevcut, Değişiklik Yok)

`account_analyses` tablosu zaten `analysis` JSONB kolonu içinde dimensions tutuyor. Sadece GPT'nin döndürdüğü key'ler değişiyor, şema değişikliği gerekmiyor.

### 8. Supabase Tablosu Kontrol

Mevcut tablo: `account_analyses`
Kolonlar: id, user_id, twitter_username, display_name, avatar_url, bio, followers_count, following_count, tweet_count, overall_score, analysis (JSONB), top_tweets (JSONB), strengths (JSONB), weaknesses (JSONB), recommendations (JSONB), posting_patterns (JSONB), created_at, updated_at

→ Şema değişikliği YOK, sadece `analysis.dimensions` içindeki key'ler değişiyor.

---

## Implementation Checklist

### Backend (routes/account_analysis.py)
- [ ] Tweet data'dan otomatik stats hesapla (media_rate, question_rate, emoji_rate, thread_rate, viral_tweets vb.)
- [ ] GPT prompt'unu yeni 5 metrikle güncelle (hook_power, engagement_potential, format_diversity, emotional_range, visual_usage)
- [ ] Stats'ı GPT prompt'una ekle (daha doğru skorlama için)
- [ ] Private hesap kontrolü ekle (is_private → 403)
- [ ] Cache freshness header'ı döndür (cached: true/false, cached_at: ISO timestamp)

### Frontend (AccountAnalysisPage.jsx)
- [ ] DimensionRadar: 6 → 5 metrik, yeni key'ler, mor/neon renk şeması
- [ ] Loading state: 6 adımlı dinamik mesajlar
- [ ] Cache badge: "Son güncelleme: X saat önce" + "Yenile" butonu
- [ ] Private hesap hata mesajı UI
- [ ] Radar chart neon glow efekti

### i18n
- [ ] TR: Yeni dimension key'leri + loading step'leri + cache mesajları
- [ ] EN: Aynı key'lerin İngilizce çevirileri

### Test
- [ ] Açık hesap analizi (berkayaltunel, elonmusk)
- [ ] Private hesap denemesi
- [ ] Cache hit/miss kontrolü
- [ ] 5 metrik radar chart render
- [ ] Loading state geçişleri
- [ ] Geçmiş listesi ve detay görüntüleme

---

## Effort Tahmini
- Backend prompt + stats: ~2 saat
- Frontend radar + loading + cache: ~3 saat  
- i18n: ~30 dk
- Test + deploy: ~1 saat
- **Toplam: ~6-7 saat**

## Rollback Planı
- Backend: GPT prompt'unu eski versiyona geri al
- Frontend: DimensionRadar'da eski 6 key'e dön
- DB: Değişiklik yok, rollback gerekmez

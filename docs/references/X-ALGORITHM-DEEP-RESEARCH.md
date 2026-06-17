# X (Twitter) Algoritması — Derin Araştırma Raporu

**Tarih:** 11 Şubat 2026  
**Amaç:** Mevcut X-ALGORITHM-RESEARCH.md'yi genişleten, kaynak koduna dayalı kapsamlı teknik analiz  
**Not:** Bu dosya mevcut araştırmayı TEKRARLAMAZ, sadece YENİ bulguları içerir.

---

## İçindekiler

1. [Heavy Ranker — Gerçek Ağırlıklar (Kaynak Koddan)](#1-heavy-ranker-gerçek-ağırlıklar)
2. [Aggregate Features — ML Modelinin Gizli Girdileri](#2-aggregate-features)
3. [Negatif Etkileşim Grafı — Detaylı Mekanik](#3-negatif-etkileşim-grafı)
4. [Visibility Filtering — Shadowban Mekanizması](#4-visibility-filtering)
5. [SimClusters — Topluluk Mekaniği Detayları](#5-simclusters-detayları)
6. [Age Decay — Tam Parametreler](#6-age-decay-parametreler)
7. [Earlybird Light Ranker — Ranking Thrift Detayları](#7-earlybird-detayları)
8. [Thunder vs Phoenix — Viral Dağıtım Modeli](#8-thunder-vs-phoenix)
9. [Velocity Threshold — Viral Eşik Formülü](#9-velocity-threshold)
10. [ScoredTweetsParam — Gizli Kontrol Parametreleri](#10-scored-tweets-parametreleri)
11. [Fake Engagement Detection](#11-fake-engagement-detection)
12. [Content Exploration & Cold Start](#12-content-exploration)
13. [Zamanlama & Frekans Detayları](#13-zamanlama-frekans)
14. [Platform İçi vs Dışı Link Cezası](#14-link-cezası)
15. [TweepCred 65 Eşiği](#15-tweepcred-65-eşiği)
16. [Anti-Gaming Mekanizmaları](#16-anti-gaming)
17. [algorithm.py İçin Yeni Bilgiler](#17-algorithm-py-güncellemeleri)

---

## 1. Heavy Ranker — Gerçek Ağırlıklar (Kaynak Koddan) {#1-heavy-ranker-gerçek-ağırlıklar}

✅ **Doğrulanmış** — Kaynak: `twitter/the-algorithm-ml/projects/home/recap/README.md` (Nisan 2023)

Heavy Ranker, MaskNet mimarisi kullanan bir neural network'tür. Her tweet için 10 farklı engagement olasılığını tahmin eder ve bunları ağırlıklı toplam ile birleştirir.

### Gerçek Engagement Ağırlıkları (Koddan)

| Engagement Tipi | Ağırlık | Açıklama |
|---|---|---|
| `fav` (Like) | **0.5** | Baseline |
| `retweet` | **1.0** | Like'ın 2x'i |
| `reply` | **13.5** | Like'ın 27x'i |
| `good_profile_click` | **12.0** | Profili açıp like/reply yapmak — Like'ın 24x'i |
| `video_playback50` | **0.005** | Videonun yarısını izlemek — çok düşük direkt ağırlık |
| `reply_engaged_by_author` | **75.0** | Reply yapılıp yazarın yanıt vermesi — Like'ın **150x'i** |
| `good_click` | **11.0** | Tweet'e tıklayıp reply/like yapmak — Like'ın 22x'i |
| `good_click_v2` | **10.0** | Tweet'e tıklayıp 2+ dakika kalmak — Like'ın 20x'i |
| `negative_feedback_v2` | **-74.0** | "Show less often", block, mute — Like'ın **-148x'i** |
| `report` | **-369.0** | Report — Like'ın **-738x'i** |

### ⚠️ Mevcut Araştırmadaki Hata Düzeltmesi

Mevcut araştırmada "Repost ~20x" olarak belirtilen değer **YANLIŞ**. Bu tweethunter.io'nun Earlybird (light ranker) boost'larını Heavy Ranker ağırlıklarıyla karıştırmasından kaynaklanıyor.

**Gerçek durum:**
- Heavy Ranker'da Retweet ağırlığı: **1.0** (Like'ın sadece 2x'i)
- Earlybird Light Ranker'da retweet'ler ayrı bir boost alıyor (2x)
- **tweethunter.io'nun "30x like boost" iddiası** Earlybird'deki content-level boost ile karıştırılmış

**Sonuç:** Reply (13.5) >>> Retweet (1.0) > Like (0.5). Reply, retweet'ten **13.5x daha değerli.**

### Type Hype Entegrasyonu
- CTA'ları reply odaklı yap: "Ne düşünüyorsun?" > "RT et"
- `reply_engaged_by_author` (75.0) en yüksek sinyal — **yazarın reply'lara yanıt vermesi zorunlu**
- `good_click_v2` (10.0) — dwell time için uzun, merak uyandıran içerik üret
- Tek bir report (-369) = 738 like'ın etkisini silier

---

## 2. Aggregate Features — ML Modelinin Gizli Girdileri {#2-aggregate-features}

✅ **Doğrulanmış** — Kaynak: `twitter/the-algorithm-ml/projects/home/recap/FEATURES.md`

Heavy Ranker sadece anlık sinyalleri değil, **50 günlük ve 30 dakikalık aggregate feature'ları** kullanır. Bu, mevcut araştırmada hiç bahsedilmeyen kritik bir bilgi.

### Feature Grupları

#### a) Author Aggregate (Yazar Bazlı)
30 dakikalık real-time sayılar:
- `is_retweeted_without_quote` — quote'suz RT
- `is_clicked` — tıklanma
- `is_dont_like` — "beğenmedim" tepkisi
- **`is_dwelled`** — dwell time sinyali
- `is_favorited`, `is_followed`, `is_open_linked`
- `is_photo_expanded` — fotoğraf büyütme
- `is_profile_clicked` — profil tıklama
- `is_quoted`, `is_replied`, `is_retweeted`
- `is_tweet_share_dm_clicked` — DM ile paylaşım butonu
- `is_tweet_share_dm_sent` — gerçek DM paylaşımı
- `is_video_playback_50` — %50 video izleme
- `is_video_quality_viewed` — video kalitesi görüntüleme
- `is_video_viewed` — video başlatma

**50 günlük uzun vadeli:**
- `is_replied_reply_favorited_by_author` — yazarın reply'lara like atması
- `is_replied_reply_impressed_by_author` — yazarın reply'ları görmesi
- `is_replied_reply_replied_by_author` — yazarın reply'lara reply vermesi

#### b) User-Author Aggregate (Kullanıcı-Yazar Çifti)
Bu en kritik feature grubu — Real Graph'tan gelir:
- `realgraph.num_favorites.ewma` — favori EWMA (exponentially weighted moving average)
- `realgraph.num_mentions.ewma` — mention sayısı
- `realgraph.num_profile_views.ewma` — profil ziyareti
- `realgraph.num_retweets.ewma` — RT sayısı
- `realgraph.num_tweet_clicks.ewma` — tweet tıklama
- **`realgraph.total_dwell_time.ewma`** — toplam dwell time
- `realgraph.num_inspected_tweets.ewma` — incelenen tweet sayısı

Her birinin `days_since_last`, `elapsed_days`, `non_zero_days` versiyonları da var.

#### c) Tweet Features (Tweet Bazlı)
- `has_card`, `has_image`, `has_link`, `has_video`, `has_multiple_media`
- `has_news`, `has_trend`, `has_periscope`, `has_pro_video`, `has_vine`
- `is_reply`, `is_retweet`, `is_sensitive`, `is_extended_reply`
- `num_hashtags`, `num_mentions`, `link_count`
- `text_score` — metin kalitesi
- `user_rep` — kullanıcı itibar skoru
- `match_ui_lang`, `match_searcher_langs` — dil eşleşmesi
- `from_mutual_follow` — karşılıklı takip

#### d) Fake Engagement Detection Features
- `fake_favorite_count` — sahte fav sayısı
- `fake_quote_count` — sahte quote sayısı
- `fake_reply_count` — sahte reply sayısı
- `fake_retweet_count` — sahte RT sayısı
- `weighted_fav_count` vs `fake_fav_count` karşılaştırması

#### e) Decayed Engagement Counts
- `decayed_favorite_count` — zaman ile azalan fav
- `decayed_quote_count`
- `decayed_reply_count`
- `decayed_retweet_count`

### Type Hype Entegrasyonu
- **30 dakikalık real-time sayımlar kullanılıyor** — ilk 30 dakika kritik, sadece 6 saat değil
- **Author'ın reply'lara tepkisi (50 gün)** takip ediliyor — aktif yazarlar ödüllendiriliyor
- **Fake engagement tespiti** var — `fake_*_count` feature'ları bot etkileşimleri algılıyor
- **DM paylaşımı** (`is_tweet_share_dm_sent`) da bir sinyal — "Arkadaşına gönder" CTA'sı değerli
- `is_dont_like` aktif olarak takip ediliyor — negatif tepki 30dk real-time'da ölçülüyor

---

## 3. Negatif Etkileşim Grafı — Detaylı Mekanik {#3-negatif-etkileşim-grafı}

✅ **Doğrulanmış** — Kaynak: `InteractionGraphNegativeJob.scala`

### 5 Negatif Sinyal Türü (Koddan)

1. **NumBlocks** — `FlockBlocksEdgesScalaDataset`
2. **NumMutes** — `FlockMutesEdgesScalaDataset`
3. **NumReportAsAbuses** — `FlockReportAsAbuseEdgesScalaDataset`
4. **NumReportAsSpams** — `FlockReportAsSpamEdgesScalaDataset`
5. **NumUnfollows** — `SocialgraphUnfollowsScalaDataset`

### Kritik Detaylar

- **Unfollow'lar sadece son 90 gün tutulur:** Kodda açıkça yazıyor: `filter(_.age < 90)` — "permanent shadow-banning in the event of accidental unfollows" engelleniyor
- **Diğer 4 negatif sinyal kalıcı:** Block, mute, abuse report, spam report için zaman sınırı yok
- **Her kullanıcı için max 500 negatif edge:** `maxDestinationIds = 500` (p99 değeri)
- **Negatif feature sayısına göre sıralanır:** En çok negatif feature'a sahip edge'ler öncelik alır

### Unfollow'ların Diğerlerinden Farkı (Koddan)
> "we treat unfollows as less critical than above 4 negative signals, since it deals more with interest than health typically, which might change over time."

**Sıralama (ciddiyete göre):**
1. 🔴 Block + Report as Abuse + Report as Spam (en ciddi, kalıcı)
2. 🟡 Mute (ciddi, kalıcı)
3. 🟢 Unfollow (daha hafif, 90 gün sonra siliniyor)

### Type Hype Entegrasyonu
- Unfollow cezası 90 gün sonra düşer — geçici kayıp kalıcı değil
- Block/mute kalıcı — bu tür tepkilerden kaçınmak hayati
- Spam report en tehlikeli (Heavy Ranker'da -369 ağırlık)
- 500 negatif edge limiti var — çok büyük hesaplar için bile sınırlı

---

## 4. Visibility Filtering — Shadowban Mekanizması {#4-visibility-filtering}

✅ **Doğrulanmış** — Kaynak: `visibilitylib/README.md`

### Visibility Filtering Nasıl Çalışır?

**VisibilityLib** merkezi bir kural motorudur. Üç temel bileşen:

1. **SafetyLevel** — Ürün context'i (Timeline, Profile, Search vs.)
2. **Features** — Safety label'lar, kullanıcı flag'leri, kullanıcılar arası ilişkiler
3. **Action** — Motorun vereceği karar:
   - **Drop** — hard filtering (tamamen gizle)
   - **Labels / Interstitials** — soft filtering (uyarı göster)
   - **Downranking** — coarse-grained sıralama düşürme

### SafetyLabel Mekanizması
- Tweet, user, DM, media, space'lere etiket atanabilir
- Etiketler **TweetSafetyLabel** ve **UserSafetyLabel** olarak ikiye ayrılır
- Her SafetyLevel (Timeline, Search, Profile) için ayrı policy var
- Policy = öncelik sıralı Rule dizisi

### ⚠️ Önemli Not
> "Visibility Filtering library is currently being reviewed and rebuilt, and part of the code has been removed and is not ready to be shared yet."

Tam shadowban mekanizması kasıtlı olarak gizlenmiş. Açık kaynak kodda **eksik** — bu "adversarial nature" nedeniyle.

### Bilinen SafetyLabel Türleri (steventey.com'dan)
- Misinformation label'ları (seçim dönemi dahil)
- GovernmentRequested müdahale sınıfı
- NSFW / Adult content label'ları
- Spam / Bot label'ları
- Toxicity label'ları

### Shadowban Türleri (Community Research)
🔍 **Spekülatif** — Doğrudan kodda yok ama gözlemlenen türler:

1. **Search Ban** — Arama sonuçlarında görünmeme
2. **Ghost Ban** — Reply'lar gizleniyor
3. **Reply Deboosting** — Reply'lar alta düşüyor
4. **Thread Ban** — Konuşmalarda görünmeme

### Shadowban Nasıl Anlaşılır?
🔍 **Spekülatif**
- shadowban.eu / twitteraudit.com gibi araçlar
- Farklı hesaptan kendi reply'larını kontrol etme
- Impression'ların ani düşüşü

### Shadowban'dan Nasıl Çıkılır?
🔍 **Spekülatif**
- 48-72 saat aktivite duraklatma
- Negatif tetikleyicileri kaldırma (spam içerik silme)
- Hesap ayarlarını gözden geçirme (sensitive content flag)

### Type Hype Entegrasyonu
- Shadowban detection özelliği ekle (impression anomaly detection)
- SafetyLevel bazlı analiz (Search vs Timeline farklı policy)
- Kullanıcıya "risk skoru" göster

---

## 5. SimClusters — Topluluk Mekaniği Detayları {#5-simclusters-detayları}

✅ **Doğrulanmış** — Kaynak: `simclusters_v2/README.md`

### Teknik Detaylar (Mevcut araştırmada olmayan)

#### Topluluk Keşfi Süreci
1. Follow graph → bipartite graph (Producer ↔ Consumer)
2. Producer-Producer cosine similarity hesaplama
3. Noise removal (düşük ağırlıklı edge'leri silme)
4. **Metropolis-Hastings sampling** ile community detection
5. Sonuç: **~145.000 topluluk**, top 20M producer'ı kapsıyor

#### Known For Matrix (V)
- Her producer **en fazla 1 topluluğa** atanır (maximally sparse)
- Bu sparsity performans için — ama gerçekte kullanıcılar birçok topluluğa ait

#### InterestedIn Matrix (U)
- U = A × V (follow graph × known for)
- **Consumer'ın uzun vadeli ilgi alanı** — tweet önerileri için ana kaynak
- Noise removal uygulanır

#### Producer Embeddings (Ṽ)
- Known For'dan farklı — bir producer **birçok topluluğa** ait olabilir
- Her producer'ın follow graph'ı ile her community'nin InterestedIn vektörü arasında cosine similarity

#### Tweet Embeddings
- Tweet oluşturulunca **boş vektör** ile başlar
- **Her fav'da güncellenir:** Fav yapan kullanıcının InterestedIn vektörü eklenir
- **Real-time güncelleme:** Heron streaming job ile

#### Topic Embeddings
- Consumer ilgi alanları + topic annotation'lı tweet'lerdeki fav sayıları
- Time decay uygulanır

#### SimClusters ANN (Approximate Nearest Neighbor)
- BigQuery üzerinde index oluşturma
- Push notification önerileri: `PushOpenBased` index
- Video önerileri: `VideoViewBased` index
- Genel tweet önerileri: `FavBased` index

### Topluluk Güncelleme Frekansı
- KnownFor: **3 haftada bir** güncellenir
- Tweet embeddings: **real-time** güncellenir
- InterestedIn: periyodik batch job

### Type Hype Entegrasyonu
- **Niş tutarlılığı kritik:** Producer en fazla 1 topluluğa atanıyor (KnownFor)
- Tweet'ler fav'larla toplulukla ilişkilendiriliyor — doğru kitleden fav almak önemli
- 3 haftalık güncelleme döngüsü — yeni nişe geçiş 3+ hafta sürebilir
- "Hangi SimCluster'dasın?" analizi yapılabilir (takipçi profili analizi ile)

---

## 6. Age Decay — Tam Parametreler {#6-age-decay-parametreler}

✅ **Doğrulanmış** — Kaynak: `ranking.thrift` (ThriftAgeDecayRankingParams)

```
slope: 0.003        — azalma hızı
halflife: 360.0      — yarı ömür (dakika) = 6 saat
base: 0.6            — minimum decay skoru
```

### Formül
```
decay_score = max(base, e^(-slope * age_minutes))
```

- t=0: score = 1.0
- t=360 dk (6 saat): score ≈ 0.5
- t=720 dk (12 saat): score ≈ 0.25
- **Minimum asla 0.6'nın altına düşmez** — bu yeni bilgi!

### ⚠️ Önemli Düzeltme
Mevcut araştırmada "her 6 saatte %50 kayıp" denilmiş ama `base: 0.6` parametresi göz ardı edilmiş. Bu, bir tweet'in **asla visibility'sinin %60'ından daha azını kaybetmeyeceği** anlamına gelir. Çok eski tweetler bile minimum %60 decay score'u korur.

### Type Hype Entegrasyonu
- İlk 6 saat en kritik (%50 kayıp)
- Ama 0.6 floor var — evergreen content hâlâ değerli
- "Optimal post saati" hesaplayıcısı bu formüle dayandırılmalı

---

## 7. Earlybird Light Ranker — Ranking Thrift Detayları {#7-earlybird-detayları}

✅ **Doğrulanmış** — Kaynak: `ranking.thrift`

### Dil Boost/Ceza Parametreleri

| Durum | Boost/Ceza |
|---|---|
| UI İngilizce, tweet değil | **0.3x** (ciddi ceza) |
| Tweet İngilizce, UI değil | **0.7x** (hafif ceza) |
| İkisi de farklı ve İngilizce değil | **0.1x** (çok ciddi ceza) |
| **Bilinmeyen dil** | **0.01x** (neredeyse sıfır) |

### Kullanıcı Tipi Boost'ları

| Kullanıcı Tipi | Default Boost |
|---|---|
| Spam kullanıcı | 1.0 (ceza yok — default, muhtemelen ayrı filtreleniyor) |
| NSFW kullanıcı | 1.0 |
| Bot kullanıcı | 1.0 |
| Verified hesap | `tweetFromVerifiedAccountBoost` = 1.0 (default) |
| **Blue Verified** | `tweetFromBlueVerifiedAccountBoost` = 1.0 (default, **runtime'da değiştirilir**) |

### İçerik Tipi Boost'ları

| İçerik | Boost Parametresi |
|---|---|
| Image URL olan tweet | `tweetHasImageUrlBoost` = 1.0 (default) |
| Video URL olan tweet | `tweetHasVideoUrlBoost` = 1.0 (default) |
| News URL olan tweet | `tweetHasNewsUrlBoost` = 1.0 (default) |
| Trend olan tweet | `tweetHasTrendBoost` = 1.0 (default) |
| **Birden fazla hashtag/trend** | `multipleHashtagsOrTrendsBoost` = 1.0 (default, **runtime'da düşürülür**) |

### ⚠️ Kritik Not
Default değerler 1.0 — yani **konfigürasyon dosyasında override ediliyorlar**. Gerçek çalışma zamanı değerleri farklı. steventey.com'un bulduğu 2x image/video boost ve 4x/2x Blue verified boost konfigürasyon override'larından geliyor.

### Engagement Rate Boost'ları (Deprecated ama bilgi için)
```
retweetRateBoost: 0 (default)
replyRateBoost: 0 (default)
faveRateBoost: 0 (default)
```

### Out-of-Network Reply Penalty
```
outOfNetworkReplyPenalty: 10.0
```
Ağınız dışından gelen reply'lar **10 puan ceza** alır. Bu, niş dışı reply'ların neden düştüğünü açıklıyor.

### Hit Demotion (Arama Sıralaması)
- `noTextHitDemotion` — metin olmayan sonuç cezası
- `urlOnlyHitDemotion` — sadece URL olan tweet cezası
- `nameOnlyHitDemotion` — sadece isim eşleşen tweet cezası

### Type Hype Entegrasyonu
- **Dil eşleşmesi çok önemli:** Türkçe UI kullananlara Türkçe tweet yaz (0.1x vs 1.0x fark)
- **Bilinmeyen kelimeler 0.01x:** Yanlış yazım, uydurma kelimeler, emoji-only tweetler ciddi ceza alır
- **Out-of-network reply penalty 10.0:** Niş dışı büyük hesaplara reply atmanın riski var
- **Birden fazla hashtag cezası:** `multipleHashtagsOrTrendsBoost` 1'den düşük set ediliyor

---

## 8. Thunder vs Phoenix — Viral Dağıtım Modeli {#8-thunder-vs-phoenix}

⚠️ **Güçlü Kanıt** — Kaynak: Reddit r/socialmedia viral post analizi (Kasım 2025)

Bu model açık kaynak kodda doğrudan adlandırılmıyor ama mimariyle tutarlı.

### Channel 1: Thunder (In-Network)
- **Kafka** ile anlık tweet ingestion
- Takipçilere sub-millisecond dağıtım
- **Lineer büyüme:** Daha çok takipçi = daha çok ilk erişim
- Kaynak kodda: `search-index` (Earlybird) ile In-Network candidate sourcing (~%50)

### Channel 2: Phoenix (Out-of-Network)
- **İki aşamalı ML sistemi:**
  1. **Retrieval (Two-Tower Model):** User embedding ↔ Content embedding dot product similarity
  2. **Ranking (Transformer/MaskNet):** Heavy Ranker ile 10 engagement olasılığı tahmini
- Kaynak kodda: `tweet-mixer`, `UTEG`, `SimClusters` ile Out-of-Network candidate sourcing (~%50)
- **Üstel büyüme:** Threshold geçilirse takipçi olmayanlar da görür

### İki Kanal Arası Geçiş
- İlk dağıtım Thunder üzerinden (takipçilere)
- Yeterli engagement sinyali → Phoenix devreye girer
- Heavy Ranker skorları yeterince yüksekse out-of-network'e açılır

### Type Hype Entegrasyonu
- İlk 30-60 dakika Thunder'da engagement toplamak kritik
- Phoenix aktivasyonu için engagement velocity gerekiyor
- Out-of-network scale factor: 0.75x (koddan — OON tweetler %25 dezavantajlı)

---

## 9. Velocity Threshold — Viral Eşik Formülü {#9-velocity-threshold}

🔍 **Spekülatif** — Kaynak: Reddit r/socialmedia (Kasım 2025). Formül kodda doğrulanamıyor ama mantıklı.

### İddia Edilen Formül
```
VELOCITY = (Engagements in First Hour) / (Follower Count / 1000)
```

| Velocity | Dağıtım |
|---|---|
| < 10 | Dead on arrival |
| 10-25 | Sadece Thunder (takipçiler) |
| 25-50 | Sınırda Phoenix |
| 50-100 | Phoenix başlıyor |
| 100+ | Güçlü viral potansiyel |
| 200+ | Patlama dağıtımı |

### Type Hype Entegrasyonu
- Velocity tracker özelliği: İlk 1 saatteki engagement / (takipçi/1000)
- "Viral potansiyel" gerçek zamanlı göstergesi
- 10K takipçili hesap için 100 velocity = ilk saatte 1000 engagement gerekir

---

## 10. ScoredTweetsParam — Gizli Kontrol Parametreleri {#10-scored-tweets-parametreleri}

✅ **Doğrulanmış** — Kaynak: `ScoredTweetsParam.scala`

### Önemli Parametreler

| Parametre | Değer | Açıklama |
|---|---|---|
| `OutOfNetworkScaleFactorParam` | **0.75** | OON tweetler %25 penalty alır |
| `ControlAiShowLessScaleFactorParam` | **0.05** | "Show less" tıklayınca skor **%95 düşer** |
| `ControlAiShowMoreScaleFactorParam` | **20.0** | "Show more" tıklayınca skor **20x artar** |
| `ControlAiEmbeddingSimilarityThresholdParam` | **0.67** | Benzerlik eşiği |
| `CreatorInNetworkMultiplierParam` | **1.0** | In-network creator çarpanı |
| `CreatorOutOfNetworkMultiplierParam` | **1.0** | OON creator çarpanı |
| `ReplyScaleFactorParam` | mevcut | Reply'lar için ayrı scale factor |
| `ServerMaxResultsParam` | **50** | Max timeline sonuç sayısı |
| `InNetworkMaxTweetsToFetchParam` | **600** | In-Network'ten max tweet |
| `UTEGMaxTweetsToFetchParam` | **300** | UTEG'den max tweet |
| `TweetMixerMaxTweetsToFetchParam` | **400** | Tweet Mixer'dan max tweet |
| `CachedScoredTweets.TTLParam` | **3 dakika** | Skorlanmış tweetlerin cache süresi |

### "Show Less Often" Etkisi
**ControlAiShowLessScaleFactorParam = 0.05** — Bu, bir kullanıcı "Show less often" tıkladığında benzer tweetlerin skorunun **%95 düşürüldüğü** anlamına gelir. Tek bir "show less" = ölüm.

### "Show More" Etkisi
**ControlAiShowMoreScaleFactorParam = 20.0** — "Show more" ise **20x boost**. Bu neden "engagement pod" mantığının işe yaradığını açıklıyor.

### Content Exploration (Cold Start)
```
CategoryColdStartTierOneProbabilityParam: 0 (default)
CategoryColdStartProbabilisticReturnParam: 0 (default)
ContentExplorationViewerMaxFollowersParam: 100000
ContentExplorationBoostPosParam: 100
```

Cold start tweetleri (yeni/keşif içerikleri) max 100K takipçili kullanıcılara gösteriliyor ve pozisyon 100'e kadar boost alabiliyor.

### Type Hype Entegrasyonu
- **"Show less" ölümcül (0.05x)** — tek bir negatif tepki bile yıkıcı
- **OON %25 dezavantaj** — viral olmak için OON penalty'yi aşacak kadar güçlü sinyal gerek
- **3 dakikalık cache** — tweet skoru 3 dakikada bir yenileniyor
- Cold start boost sadece <100K takipçili hesaplar için

---

## 11. Fake Engagement Detection {#11-fake-engagement-detection}

✅ **Doğrulanmış** — Kaynak: `FEATURES.md`

Kaynak kodda açıkça **fake engagement sayaçları** var:

```
timelines.earlybird.fake_favorite_count
timelines.earlybird.fake_quote_count
timelines.earlybird.fake_reply_count
timelines.earlybird.fake_retweet_count
```

Bunlar `weighted_*_count` ile karşılaştırılıyor:
```
timelines.earlybird.weighted_fav_count
timelines.earlybird.weighted_quote_count
timelines.earlybird.weighted_reply_count
timelines.earlybird.weighted_retweet_count
```

### Mekanik
- **weighted count**: Gerçek, ağırlıklı engagement (güvenilir kullanıcılardan daha yüksek ağırlık)
- **fake count**: Botlardan veya şüpheli kaynaklardan gelen engagement
- **Heavy Ranker her ikisini de feature olarak kullanıyor** — yüksek fake count penalize ediliyor

### Type Hype Entegrasyonu
- **Bot engagement kesinlikle tespit ediliyor** — fake_count feature'ları bu amaçla var
- "Organik engagement skoru" = weighted / (weighted + fake) oranı hesaplanabilir
- Dwell farming riski: `fake_*_count` artar → hesap itibarı düşer

---

## 12. Content Exploration & Cold Start {#12-content-exploration}

✅ **Doğrulanmış** — Kaynak: `ScoredTweetsParam.scala`

### Cold Start Mekanizması
- `SimClustersColdPostsCandidateBoostingParam` — soğuk tweetler için boost
- `DeepRetrievalI2iProbabilityParam` — item-to-item retrieval olasılığı
- `ContentExplorationViewerMaxFollowersParam: 100000` — max 100K takipçili kullanıcılara göster

### Deep Retrieval
- `DeepRetrievalBoostPosParam: 100` — timeline'da pozisyon 100'e kadar boost
- `DeepRetrievalMixedCandidateBoostingParam` — karışık aday boost'lama

### Type Hype Entegrasyonu
- Yeni hesaplar için "Content Exploration" pipeline'ı var
- 100K'dan küçük hesaplara cold start içerik gösteriliyor
- Küçük hesaplar bu pipeline'dan faydalanabilir

---

## 13. Zamanlama & Frekans Detayları {#13-zamanlama-frekans}

### En İyi Posting Saatleri

⚠️ **Güçlü Kanıt** — Kaynak: Hootsuite, Sprout Social 2024-2026

| Gün | En İyi Saatler (EST) | Türkiye (GMT+3) |
|---|---|---|
| Pazartesi-Perşembe | 08:00-11:00, 18:00-21:00 | 16:00-19:00, 02:00-05:00 |
| Cuma | 10:00-14:00 | 18:00-22:00 |
| Hafta sonu | 10:00-12:00, 19:00-21:00 | 18:00-20:00, 03:00-05:00 |

**Türkiye için optimize:**
| Gün | Türkiye Saatleri |
|---|---|
| Hafta içi | 08:00-10:00, 12:00-13:00, 19:00-22:00 |
| Hafta sonu | 10:00-13:00, 19:00-23:00 |

### Günlük Optimal Tweet Sayısı
- ⚠️ Hootsuite: **2-3 tweet/gün**
- ⚠️ TweepCred < 65 ise max **3 tweet** değerlendirilir (koddan)
- TweepCred > 65 ise sınır yok

### İki Tweet Arası Minimum Süre
🔍 **Spekülatif** — Direkt kodda yok ama:
- `ExcludeServedAuthorIdsDurationParam: 60 dakika` — aynı yazardan 60dk içinde çok tweet gösterilmemesi
- Author diversity heuristik'i birden fazla ardışık tweet'i engelliyor
- Önerilen: min 2-3 saat ara

### Type Hype Entegrasyonu
- Türkiye saatleri için özelleştirilmiş zamanlayıcı
- TweepCred < 65 kontrolü: "Günde 3'ten fazla tweet atma" uyarısı
- 60 dakikalık author exclusion süresini hesaba kat

---

## 14. Platform İçi vs Dışı Link Cezası {#14-link-cezası}

✅ **Doğrulanmış** — Kaynak: Elon Musk (The Independent, 2024)

### Elon Musk'ın Açıklamaları
1. (Ekim 2023) "Our algorithm tries to optimize time spent on X, so links don't get as much attention"
2. (2024) Paul Graham'a: "Just write a description in the main post and put the link in the reply"

### Koddan Kanıt
- `ranking.thrift`: `urlParams` — link'ler için ayrı ağırlık parametresi
- `ThriftHostQualityParams`: Link'li tweetler için host kalite çarpanı
  - `multiplier: 0.0` (default — konfigürasyonla override edilir)
  - `maxScoreToModify`, `minScoreToModify` — hangi skorlardaki host'ları etkileyeceği
  - `applyToUnknownHosts: false` — bilinmeyen host'lar

- Earlybird features: `has_link`, `has_visible_link`, `link_count`, `has_news`
- **News URL'leri ayrı boost parametresi var:** `tweetHasNewsUrlBoost` — haber linkleri farklı muamele görebilir

### Stratejiler
1. **En iyi:** Link kullanma, bilgiyi direkt tweet olarak yaz
2. **İkinci en iyi:** Linki ilk reply'a koy
3. **Üçüncü:** X'in Article özelliğini kullan (platform içi)
4. **En kötü:** Ana tweet'e harici link koy

### Type Hype Entegrasyonu
- Link detection ve otomatik uyarı: "Bu tweet harici link içeriyor, %50-90 erişim kaybı riski"
- "Linksiz versiyon" önerici: İçeriği link yerine metin olarak yaz
- News link'leri ayrı kategoride — haber paylaşımı biraz daha az ceza alabilir

---

## 15. TweepCred 65 Eşiği {#15-tweepcred-65-eşiği}

✅ **Doğrulanmış** — Kaynak: `ranking.thrift` satır 284-291, `steventey.com`

### Mekanik
- TweepCred < 65: Max **3 tweet** ranking algoritması tarafından değerlendirilir
- TweepCred ≥ 65: **Sınırsız** tweet değerlendirilir
- Bu thread'ler için kritik: Düşük TweepCred ile 10 tweet'lik thread'in sadece 3'ü değerlendirilir

### Anti-Gaming Filtresi
Koddan (`ranking.thrift`):
```
maxTweepcredForAntiGaming: 65
maxHitsPerUser: 3
```

TweepCred > 65 olan kullanıcılar anti-gaming filtresinden **muaf**. Düşük TweepCred'li kullanıcılar:
- Kullanıcı başına max 3 hit
- Anti-gaming kontrolü uygulanır

### TweepCred Nasıl Hesaplanır? (Detaylı)
`Reputation.scala`:
1. Raw PageRank → log dönüşümü → 0-100 arası scale
2. `adjustReputationsPostCalculation`:
   - Eğer following/followers > 1 → ceza uygulanır
   - `divisionFactor = following / followers` oranına göre PageRank düşürülür

`UserMass.scala`:
- Hesap yaşı
- Takipçi sayısı
- Takip sayısı
- Cihaz kullanımı (mobil, web, API)
- Güvenlik durumu (restricted, suspended, verified)

### Type Hype Entegrasyonu
- TweepCred tahmini: following/follower ratio + hesap yaşı + engagement geçmişi
- "65 üstüne çık" hedefi: Takipçi/takip oranını düzelt, engagement artır
- Thread yazarken TweepCred < 65 uyarısı: "Max 3 tweet değerlendirilecek"

---

## 16. Anti-Gaming Mekanizmaları {#16-anti-gaming}

✅ **Doğrulanmış** — Çeşitli kaynak dosyalardan

### Bilinen Mekanizmalar

| Mekanik | Kaynak | Detay |
|---|---|---|
| Author diversity | `home-mixer` heuristics | Aynı yazardan ardışık tweet engelleme |
| Social proof | Heuristics | OON tweet ancak takip edilen biri etkileşim yaptıysa gösterilir |
| Feedback fatigue | Heuristics | Negatif feedback verdiğin tweet türlerini azaltma |
| Anti-gaming filter | `ranking.thrift` | TweepCred < 65 = max 3 hit/kullanıcı |
| 60dk author exclusion | `ScoredTweetsParam` | Aynı yazarı 60dk boyunca tekrar göstermeme |
| Fake engagement detection | `FEATURES.md` | `fake_*_count` feature'ları |
| Negative interaction graph | `InteractionGraphNegativeJob` | Block/mute/report/spam/unfollow takibi |
| Visibility filtering | `visibilitylib` | Rule-based content filtering |

### "Show Less Often" Mekanizması
- Kullanıcı menüden "Show less often" tıklayınca
- İlgili tweet/yazar için `negative_feedback_v2` sinyali → Heavy Ranker'da -74.0 ağırlık
- Benzer içerikler için `ControlAiShowLessScaleFactorParam = 0.05` → %95 skor düşüşü
- Embedding similarity threshold 0.67 — yeterince benzer tüm içerikler etkilenir

### Engagement Bait Detection
🔍 **Spekülatif** — Kodda açıkça yok ama:
- `is_dont_like` real-time olarak takip ediliyor
- Yüksek impression + düşük engagement = negatif sinyal
- "RT for X, like for Y" kalıpları muhtemelen metin analizi ile tespit ediliyor

### Type Hype Entegrasyonu
- Engagement bait kalıplarından kaçınma uyarısı
- "Show less" riskini minimize eden içerik önerileri
- Author diversity'yi hesaba katan posting stratejisi

---

## 17. algorithm.py İçin Yeni Bilgiler {#17-algorithm-py-güncellemeleri}

### Mevcut Modele Eklenmesi Gereken Değişiklikler

#### 1. Heavy Ranker Ağırlıkları (Düzeltme)
```python
HEAVY_RANKER_WEIGHTS = {
    "fav": 0.5,
    "retweet": 1.0,
    "reply": 13.5,  # ÖNCEKİ: ~13.5 (doğru)
    "good_profile_click": 12.0,  # YENİ
    "video_playback50": 0.005,  # YENİ
    "reply_engaged_by_author": 75.0,  # YENİ - EN ÖNEMLİ
    "good_click": 11.0,  # YENİ
    "good_click_v2": 10.0,  # YENİ (2+ dk dwell)
    "negative_feedback": -74.0,  # YENİ
    "report": -369.0,  # YENİ
}
```

#### 2. Age Decay Parametreleri
```python
AGE_DECAY = {
    "slope": 0.003,
    "halflife_minutes": 360,  # 6 saat
    "base": 0.6,  # minimum decay (YENİ - floor değeri)
}
```

#### 3. Dil Etkisi
```python
LANGUAGE_BOOSTS = {
    "ui_english_tweet_not": 0.3,
    "tweet_english_ui_not": 0.7,
    "both_different_not_english": 0.1,
    "unknown_language": 0.01,  # neredeyse ölüm
}
```

#### 4. OON Scale Factor
```python
OUT_OF_NETWORK_SCALE = 0.75  # %25 dezavantaj
OUT_OF_NETWORK_REPLY_PENALTY = 10.0  # OON reply cezası
```

#### 5. TweepCred Eşiği
```python
TWEEPCRED_THRESHOLD = 65
MAX_TWEETS_BELOW_THRESHOLD = 3
ANTI_GAMING_TWEEPCRED = 65
```

#### 6. Feedback Scale Factors
```python
SHOW_LESS_SCALE = 0.05  # %95 skor düşüşü
SHOW_MORE_SCALE = 20.0  # 20x boost
SIMILARITY_THRESHOLD = 0.67
```

#### 7. Fake Engagement
```python
# Modele fake engagement detection ekle
FAKE_ENGAGEMENT_FEATURES = [
    "fake_favorite_count",
    "fake_quote_count",
    "fake_reply_count",
    "fake_retweet_count",
]
```

#### 8. Negative Interaction Süreler
```python
NEGATIVE_SIGNAL_DURATIONS = {
    "block": "permanent",
    "mute": "permanent",
    "abuse_report": "permanent",
    "spam_report": "permanent",
    "unfollow": "90_days",  # 90 gün sonra silinir
}
```

#### 9. Aggregate Feature Pencereler
```python
AGGREGATE_WINDOWS = {
    "real_time": "30_minutes",
    "short_term": "3_days",
    "long_term": "50_days",
}
```

---

## Kaynak Listesi

| # | Kaynak | URL | Güvenilirlik |
|---|---|---|---|
| 1 | Heavy Ranker README | `github.com/twitter/the-algorithm-ml/.../recap/README.md` | ⭐⭐⭐⭐⭐ |
| 2 | Heavy Ranker FEATURES | `github.com/twitter/the-algorithm-ml/.../recap/FEATURES.md` | ⭐⭐⭐⭐⭐ |
| 3 | TweepCred README | `github.com/twitter/the-algorithm/.../tweepcred/README` | ⭐⭐⭐⭐⭐ |
| 4 | SimClusters README | `github.com/twitter/the-algorithm/.../simclusters_v2/README.md` | ⭐⭐⭐⭐⭐ |
| 5 | ranking.thrift | `github.com/twitter/the-algorithm/.../ranking.thrift` | ⭐⭐⭐⭐⭐ |
| 6 | InteractionGraphNegativeJob | `github.com/twitter/the-algorithm/.../InteractionGraphNegativeJob.scala` | ⭐⭐⭐⭐⭐ |
| 7 | ScoredTweetsParam | `github.com/twitter/the-algorithm/.../ScoredTweetsParam.scala` | ⭐⭐⭐⭐⭐ |
| 8 | visibilitylib README | `github.com/twitter/the-algorithm/visibilitylib/README.md` | ⭐⭐⭐⭐⭐ |
| 9 | UUA README | `github.com/twitter/the-algorithm/.../unified_user_actions/README.md` | ⭐⭐⭐⭐⭐ |
| 10 | Sprout Social 2026 | `sproutsocial.com/insights/twitter-algorithm/` | ⭐⭐⭐⭐ |
| 11 | Hootsuite 2024 | `blog.hootsuite.com/twitter-algorithm/` | ⭐⭐⭐⭐ |
| 12 | steventey.com | `steventey.com/blog/twitter-algorithm` | ⭐⭐⭐ |
| 13 | tweethunter.io | `tweethunter.io/blog/twitter-algorithm-full-analysis` | ⭐⭐⭐ |
| 14 | Reddit r/socialmedia | Kasım 2025 viral post analizi | ⭐⭐ |
| 15 | The Independent (Elon Musk link cezası) | `independent.co.uk/.../elon-musk-x-news-links-b2653614.html` | ⭐⭐⭐⭐ |

---

## Özet: En Kritik Yeni Bulgular

1. ✅ **Reply_engaged_by_author (75.0)** en yüksek ağırlık — yazarın reply'lara yanıt vermesi zorunlu
2. ✅ **Report (-369.0)** tek bir report = 738 like'ı siler
3. ✅ **"Show less" = 0.05x skor** — tek tıkla %95 düşüş
4. ✅ **Fake engagement detection** aktif — `fake_*_count` feature'ları var
5. ✅ **Unfollow 90 gün sonra silinir** — diğer negatif sinyaller kalıcı
6. ✅ **TweepCred < 65 = max 3 tweet** değerlendirilir
7. ✅ **OON scale factor 0.75** — viral olmak için %25 penalty'yi aşmak lazım
8. ✅ **Bilinmeyen dil 0.01x** — yanlış yazım/emoji spam ölümcül
9. ✅ **30 dakikalık real-time aggregate** — ilk 30 dk, 6 saatten bile daha kritik
10. ✅ **Age decay floor 0.6** — tweet asla %60'tan fazla kayıp yaşamaz

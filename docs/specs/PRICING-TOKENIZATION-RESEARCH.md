# Type Hype Tokenizasyon & Fiyatlandırma Araştırması
**Tarih:** 19 Şubat 2026  
**Hazırlayan:** Berkai  
**Durum:** Araştırma tamamlandı, Berkay onayı bekliyor

---

## 1. Rakip Analizi

### 1.1 Doğrudan Rakipler (Sosyal Medya AI İçerik)

| Platform | Free | Starter/Lite | Pro | Team/Business | Kredi Sistemi |
|----------|------|-------------|-----|---------------|---------------|
| **XPatla** | Yok | $19/ay (750 kredi) | $49/ay (1,500 kredi) | $149/ay (5,000 kredi, 3 koltuk) | 1 kredi ≈ 1 üretim |
| **Tweet Hunter** | Yok | $49/ay (tek plan) | Dahil | Yok | Unlimited AI (tek plan) |
| **Taplio** (LinkedIn) | Yok | $32/ay (0 AI kredi) | $49/ay (250 AI kredi) | $149/ay (unlimited) | AI kredi + comment kredi |
| **Hypefury** | Free tier | $29/ay | $49/ay | Yok | Unlimited (plan bazlı) |
| **Typefully** | Free tier | $12/ay | $29/ay | Custom | Post limiti bazlı |

### 1.2 Genel AI İçerik Platformları

| Platform | Starter | Pro | Business | Kredi Sistemi |
|----------|---------|-----|----------|---------------|
| **Copy.ai** | Free (chat only) | $1,000/ay (20K workflow kredi) | $2,000/ay (45K) | Workflow kredi bazlı |
| **Jasper** | Custom pricing | Custom | Enterprise | Word count bazlı |
| **Writesonic** | Free tier | $20/ay | $99/ay | Article + agent generation |

### 1.3 Sosyal Medya Yönetim Araçları

| Platform | Free | Starter | Pro | Odak |
|----------|------|---------|-----|------|
| **Buffer** | Free (3 kanal, 10 post) | $5/ay/kanal | $10/ay/kanal | Scheduling + analytics |
| **Hootsuite** | Yok | $99/ay | $249/ay | Enterprise social mgmt |
| **Publer** | Free (3 hesap) | $12/ay | $25/ay | Multi-platform scheduling |

### 1.4 Önemli Gözlemler

**Fiyat Aralıkları:**
- Bireysel AI content tool: **$19-49/ay**
- Pro/Tam erişim: **$49-99/ay**
- Team: **$99-199/ay**
- Enterprise: **$500+/ay**

**Kredi Sistemleri:**
- XPatla: Basit kredi (1 üretim = 1 kredi), plan bazlı limit
- Taplio: AI kredi + comment kredi ayrı, Standard'da 250 AI/ay
- Copy.ai: Workflow kredi (karmaşık, her iş farklı kredi)
- Tweet Hunter: Unlimited (tek plan, basit)
- Buffer: Post sayısı bazlı (AI unlimited)

**Trend:** Pazar ikiye ayrılıyor:
1. "Unlimited AI" tek plan ($49) → Tweet Hunter, Hypefury
2. Kredi bazlı kademeli → XPatla, Taplio, Copy.ai

---

## 2. Pazar Konumlandırma

### Type Hype Nerede?
- **XPatla'nın direkt rakibi** (Türk pazarı, X odaklı, stil klonlama)
- **Ek avantajlarımız:** Multi-platform (6 platform), Content Evolution, Trend Radar, Shitpost modu, Video Script, Image Prompt
- **Eksiklerimiz:** Scheduling yok (henüz), analytics yok, auto-post yok, community yok

### Hedef Segment
1. **Bireysel content creator'lar** (Türk X/Twitter kullanıcıları)
2. **Küçük markalar/ajanslar** (sosyal medya yönetimi)
3. **Freelancer copywriter'lar** (çoklu müşteri)

### Konumlandırma Stratejisi
> "XPatla fiyatına çok platformlu AI content studio"

XPatla Lite'ın verdiğinin 2x'ini, daha ucuza ver. Ama "unlimited" verme, değer algısını düşürür.

---

## 3. Maliyet Analizi (Bizim Gerçek Maliyetlerimiz)

### 3.1 Per-İşlem API Maliyeti

| İşlem | Normal (Gemini Flash) | Ultra (Claude Sonnet) | Shitpost (Mistral) |
|-------|----------------------|----------------------|-------------------|
| Tweet (3 varyant) | 1.2¢ | 6.8¢ | 1.1¢ |
| Quote/Reply (3 var) | 1.2¢ | 7.3¢ | 1.2¢ |
| Thread (5 varyant) | 3.0¢ | 16.5¢ | 2.4¢ |
| Article (3 varyant) | 1.6¢ | 9.0¢ | 1.3¢ |
| Evolve (3 varyant) | 1.3¢ | 7.7¢ | 1.3¢ |
| Video Script | 0.3¢ | 1.5¢ | 0.2¢ |
| Image Prompt | 0.2¢ | 0.9¢ | 0.1¢ |
| Trend Analizi | 0.9¢ | N/A | N/A |
| Style Lab Analizi | 0.9¢ | N/A | N/A |

### 3.2 Style Lab Ek Maliyetleri

| Bileşen | Maliyet | Not |
|---------|---------|-----|
| Apify tweet scraping | ~$0.005/profil | 50 tweet çekme |
| AI stil analizi | ~0.9¢ | GPT-4o-mini |
| **Toplam per profil** | **~$0.015** | İlk kurulum maliyeti |
| Profil güncelleme | ~$0.01 | Rescrape + reanalyze |

### 3.3 Sabit Altyapı Maliyetleri

| Kalem | Aylık Maliyet |
|-------|---------------|
| Hetzner VPS (backend + scraper) | ~$5 |
| Supabase (Pro, gelecekte) | $25 |
| Vercel (Hobby/free) | $0 |
| Domain (typehype.io) | ~$2 |
| **Toplam sabit** | **~$32/ay** |

### 3.4 Ağırlıklı Ortalama Maliyet per Kredi

Kullanıcıların %70 Normal, %25 Ultra, %5 Shitpost kullandığını varsayarsak:

**Tweet üretimi (en yaygın işlem):**
- Ağırlıklı maliyet: (0.70 × 1.2¢) + (0.25 × 6.8¢) + (0.05 × 1.1¢) = **2.6¢/üretim**

**Basitleştirilmiş ortalama: ~3¢ per kredi** (güvenli tarafta kalmak için)

---

## 4. Token/Kredi Sistemi Tasarımı

### 4.1 Temel İlkeler

1. **Basitlik**: Kullanıcı "1 kredi = 1 şey" anlasın, karmaşık hesap yapmasın
2. **Adil fiyatlandırma**: Pahalı işlemler daha fazla kredi yesin
3. **Upsell fırsatı**: Ultra mod daha fazla kredi yiyerek premium hissi versin
4. **Perceived value**: Rakiplerle karşılaştırıldığında "daha fazla veriyor" algısı

### 4.2 Kredi Harcama Tablosu

| İşlem | Normal Mod | Ultra Mod | Not |
|-------|-----------|-----------|-----|
| **Tweet/Post üretimi** (3 varyant) | 1 kredi | 3 kredi | Ana birim |
| **Quote/Reply** (3 varyant) | 1 kredi | 3 kredi | Tweet ile aynı |
| **Thread** (5 varyant) | 3 kredi | 8 kredi | Daha uzun, daha pahalı |
| **Article/Blog** (3 varyant) | 3 kredi | 8 kredi | Uzun form |
| **Evolve** (1 tur, 3 varyant) | 1 kredi | 3 kredi | İterasyon |
| **Video Script** | 1 kredi | 2 kredi | Repurpose |
| **Image Prompt** | 1 kredi | 2 kredi | Repurpose |
| **Style Lab** (yeni profil) | 5 kredi | 5 kredi | Apify + AI analiz |
| **Style Lab** (profil güncelle) | 2 kredi | 2 kredi | Rescrape |
| **Trend Analizi** | 0 kredi | 0 kredi | Passive, cron ile otomatik |

### 4.3 Neden Bu Rakamlar?

**1 kredi = 1 tweet üretimi (Normal)** → En basit, en anlaşılır birim
- Gerçek maliyet: ~1.2¢
- Ultra 3x kredi → Gerçekte 6.8¢ (5.7x pahalı ama 3x kredi yeterli kâr marjıyla)

**Thread/Article = 3 kredi** → 2.5-3x daha pahalı API maliyeti, 3 kredi mantıklı

**Style Lab = 5 kredi** → Apify + AI analiz = ~1.5¢ maliyet, ama **algılanan değer çok yüksek**. Kullanıcı "AI tarzımı klonladı" diye düşünüyor. 5 kredi premium hissi veriyor ama caydırıcı değil.

**Trend Analizi = 0 kredi** → Cron ile otomatik, kullanıcı başına ek maliyet yok. Bedava vererek platform'un "her zaman güncel" hissi verir. Competitive advantage.

### 4.4 Ultra Mod Stratejisi

Ultra mod (Claude Sonnet 4.6) gerçekte 5-6x pahalı ama **3x kredi** alıyoruz:
- Kullanıcı perspective: "3 kredi ödüyorum, daha kaliteli sonuç alıyorum" → adil hissettiriyor
- Bizim perspective: Ultra kullanan premium kullanıcı zaten daha fazla plan alıyor
- Sonuç: Ultra kullanan kullanıcı kredilerini 3x hızlı bitirir → upsell fırsatı

### 4.5 Platform Bazlı Token Yapısı (Gelecek)

Yeni platformlar eklenince kredi yapısı değişmez, sadece üretim tipi eklenir:

| Platform | İşlem | Normal | Ultra |
|----------|-------|--------|-------|
| X/Twitter | Tweet, Quote, Reply | 1 | 3 |
| X/Twitter | Thread | 3 | 8 |
| Instagram | Carousel caption (5 slide) | 2 | 5 |
| Instagram | Reel script | 2 | 5 |
| Instagram | Story copy | 1 | 2 |
| LinkedIn | Post | 1 | 3 |
| LinkedIn | Article | 3 | 8 |
| TikTok | Script (30s/60s) | 2 | 5 |
| YouTube | Title + Description + Tags | 2 | 5 |
| YouTube | Full script | 5 | 12 |
| Blog | Full article (1000+ word) | 5 | 12 |

**Mantık:** Kısa form = 1 kredi, orta form = 2-3 kredi, uzun form = 5 kredi

---

## 5. Plan Önerileri

### Plan 1: Free (Starter)
> Tat almak için, kart gerekmez

| | Detay |
|---|---|
| **Fiyat** | $0 |
| **Kredi** | 50 kredi/ay (yenilenir) |
| **Mod** | Sadece Normal |
| **Style Lab** | 1 profil (ilk kurulum bedava) |
| **Trend** | Son 24 saat, günde 1 refresh |
| **Platform** | Sadece X/Twitter |
| **Evolve** | Max 3 tur |
| **Geçmiş** | Son 7 gün |
| **Favoriler** | 20 limit |
| **Reklam** | "Powered by Type Hype" watermark (opsiyonel) |

**Neden:** 50 kredi = ~50 tweet = günde ~1.5 tweet. Yeterli ki platformu denesin, yetersiz ki Pro'ya geçmek istesin. XPatla free tier yok, biz var → signup barrier düşük.

**Maliyet tahmini:** ~$0.60/ay/kullanıcı (50 × 1.2¢)

### Plan 2: Pro
> Bireysel creator'lar için

| | Aylık | Yıllık |
|---|---|---|
| **Fiyat** | $19/ay | $15/ay ($180/yıl, 2 ay bedava) |
| **Kredi** | 1,000 kredi/ay | 1,000 kredi/ay |
| **Mod** | Normal + Ultra + Shitpost |
| **Style Lab** | 3 profil, sınırsız güncelleme |
| **Trend** | Tam erişim, günde 6 refresh |
| **Platform** | Tüm platformlar |
| **Evolve** | Max 10 tur |
| **Geçmiş** | Sınırsız |
| **Favoriler** | Sınırsız |
| **Video Script** | Dahil |
| **Image Prompt** | Dahil |
| **Ek kredi** | $5 / 200 kredi (top-up) |

**XPatla karşılaştırma:**
- XPatla Lite: $19/ay → 750 kredi, sadece X
- **Type Hype Pro: $19/ay → 1,000 kredi, 6 platform, Ultra mod, Trend, Evolve** ✅
- Aynı fiyat, %33 daha fazla kredi, çok daha fazla özellik

**Maliyet tahmini per kullanıcı:**
- Normal ağırlıklı: 1,000 × 2.6¢ = $26/ay
- Ama kullanıcıların çoğu tüm kredisini bitirmez (~60% kullanım)
- Efektif maliyet: ~$15.60/ay
- Gelir: $19/ay → **Kâr: ~$3.40/ay** (aylık)
- Yıllık: $15/ay gelir, ~$15.60 maliyet → **Break-even veya hafif zarar** (ama retention ve upsell ile dengelenir)

⚠️ **Not:** Ultra kullanımı %25'ten fazla olursa maliyet artar. Ultra'yı 3x kredi yaparak throttle ediyoruz.

### Plan 3: Business
> Ajanslar ve ekipler için

| | Aylık | Yıllık |
|---|---|---|
| **Fiyat** | $49/ay | $39/ay ($468/yıl, 2 ay bedava) |
| **Kredi** | 3,000 kredi/ay | 3,000 kredi/ay |
| **Mod** | Normal + Ultra + Shitpost |
| **Style Lab** | 10 profil, sınırsız güncelleme |
| **Trend** | Tam erişim, custom RSS ekleme |
| **Platform** | Tüm platformlar |
| **Evolve** | Sınırsız |
| **Geçmiş** | Sınırsız |
| **Favoriler** | Sınırsız |
| **Koltuk** | 3 kullanıcı (ek koltuk: $10/ay) |
| **Öncelikli destek** | Telegram/Discord |
| **API erişimi** | Gelecekte |
| **Ek kredi** | $5 / 250 kredi (top-up, daha ucuz) |

**XPatla karşılaştırma:**
- XPatla Pro: $49/ay → 1,500 kredi
- **Type Hype Business: $49/ay → 3,000 kredi, 3 koltuk, 10 stil profili** ✅
- 2x kredi, multi-user, aynı fiyat

**Maliyet tahmini:**
- 3,000 × 2.6¢ × 60% kullanım = ~$46.80/ay
- Gelir: $49/ay → **Kâr: ~$2.20/ay** (thin margin, upsell ile büyür)
- Yıllık: $39/ay gelir, ~$46.80 maliyet → **Zarar** (ama churn düşük, LTV yüksek)

### Opsiyonel: Enterprise (Gelecek)
- $99+/ay, 10,000+ kredi, custom branding, API, SSO, dedicated support
- Sadece talep gelirse değerlendirilir

---

## 6. Kar Marjı Analizi

### 6.1 Senaryo: 100 Kullanıcı

| Plan | Kullanıcı | Aylık Gelir | Aylık Maliyet (API) | Sabit Maliyet | Toplam Maliyet | Kâr |
|------|----------|-------------|--------------------|--------------|--------------|----|
| Free | 60 | $0 | $36 | | | |
| Pro | 30 | $570 | $468 | | | |
| Business | 10 | $490 | $468 | | | |
| **Toplam** | **100** | **$1,060** | **$972** | **$32** | **$1,004** | **$56** |

Thin margin! Ama bu worst case (herkes kredisini bitiyor). Gerçekte:

### 6.2 Senaryo: 100 Kullanıcı (Gerçekçi, %55 kullanım)

| Plan | Kullanıcı | Aylık Gelir | API Maliyet (%55) | Kâr |
|------|----------|-------------|-------------------|-----|
| Free | 60 | $0 | $20 | -$20 |
| Pro | 30 | $570 | $257 | $313 |
| Business | 10 | $490 | $257 | $233 |
| **Toplam** | **100** | **$1,060** | **$534** | **$494** |

**~47% kâr marjı** (sabit maliyetler dahil $462 net)

### 6.3 Break-even Analizi

- Sabit maliyet: $32/ay
- Free kullanıcı API maliyeti: ~$0.33/ay per user
- **Break-even: 3 Pro kullanıcı** ($57 gelir > $32 sabit + API)
- 10 Pro kullanıcıda: ~$190 gelir, ~$150 maliyet = **$40/ay net**

### 6.4 Ek Gelir Kaynakları

| Kaynak | Potansiyel |
|--------|-----------|
| Kredi top-up ($5/200) | Power user'lar ayda 1-2x satın alır |
| Yıllık planlar | Cash flow + retention (2 ay bedava = %17 indirim) |
| Referral program | "Arkadaşını getir, 100 kredi kazan" |
| White-label (gelecek) | Ajanslar kendi müşterilerine satar |

---

## 7. Style Lab Özel Fiyatlandırma

### Seçenekler

**A) Kredi dahil (önerimiz) ✅**
- Yeni profil: 5 kredi
- Güncelleme: 2 kredi
- Avantaj: Basit, kullanıcı "ayrı maliyet" düşünmez
- Dezavantaj: Style Lab çok kullanılırsa kredi hızlı biter → ama bu upsell

**B) Ayrı limit**
- Free: 1 profil
- Pro: 3 profil
- Business: 10 profil
- Avantaj: Krediyi tüketmez
- Dezavantaj: İki farklı limit = karmaşıklık

**Önerimiz:** A + B kombinasyonu:
- Profil sayısı plan bazlı limit (Free: 1, Pro: 3, Business: 10)
- Her yeni profil oluşturma ve güncelleme kredi harcıyor (5 / 2)
- Böylece hem limit var hem kredi incentive'ı

---

## 8. Gelecek Platformlar için Token Yapısı

### Instagram
- **Carousel caption** (5 slide açıklama): 2 kredi → Slide başına copy + genel caption
- **Reel script** (15s/30s/60s): 2 kredi → Timing + spoken text + overlay
- **Story copy**: 1 kredi → Kısa, tweet benzeri

### LinkedIn
- **Post**: 1 kredi → Tweet benzeri uzunluk
- **Article**: 3 kredi → 500-1000 kelime
- **Carousel document**: 2 kredi → PDF slides için copy

### TikTok
- **Script**: 2 kredi → Timing + hook + CTA
- **Caption + hashtag**: 1 kredi → Kısa açıklama + trend hashtag'ler

### YouTube
- **Title + Description + Tags**: 2 kredi → SEO optimized
- **Full script** (5-15dk): 5 kredi → Uzun form, çok token
- **Shorts script**: 2 kredi → TikTok benzeri

### Blog
- **Full article** (1000+ kelime): 5 kredi → En pahalı, en çok token
- **Summary/excerpt**: 1 kredi → Kısa versiyon

### Cross-Platform Repurpose
- **Tweet → LinkedIn post**: 1 kredi
- **Thread → Blog article**: 3 kredi
- **Blog → Tweet thread**: 2 kredi
- **Any → Video script**: 1 kredi

**Felsefe:** Content repurpose daima orijinal üretimden ucuz olmalı (daha az token kullanıyor, kullanıcı "bonus" hissediyor).

---

## 9. Öneriler ve Lansman Stratejisi

### 9.1 Launch Pricing

**Early Bird (İlk 100 kullanıcı):**
- Pro: $12/ay (lifetime, yıllık ödeme şartıyla)
- Business: $29/ay (lifetime)
- "İlk 100 kullanıcıya özel" → urgency + exclusivity

**Beta (İlk 500 kullanıcı):**
- Pro: $15/ay
- Business: $39/ay

**Normal fiyat (500+ kullanıcı):**
- Yukarıdaki standart fiyatlar

### 9.2 Referral Program

- Referrer: +200 kredi (her başarılı davet)
- Referred: +100 bonus kredi (ilk ay)
- Cap: Ayda max 1,000 bonus kredi

### 9.3 Upsell Fırsatları

1. **Kredi bitmek üzere notification** → "200 kredi sadece $5" CTA
2. **Ultra mod deneme** → Free'de 5 Ultra kredi vererek tadını aldır
3. **Style Lab upsell** → "3. profilin limit doldu, Business'a geç"
4. **Annual upsell** → Aylık ödeyenlere "yıllığa geç, 2 ay bedava" banner

### 9.4 Competitive Positioning (Karşılaştırma Sayfası)

| Özellik | Type Hype Pro ($19) | XPatla Lite ($19) | Tweet Hunter ($49) |
|---------|--------------------|--------------------|-------------------|
| Aylık kredi | 1,000 | 750 | Unlimited |
| Platform | 6 | 1 (sadece X) | 1 (sadece X) |
| Stil klonlama | ✅ | ✅ | ✅ |
| Ultra AI (Claude) | ✅ | ❌ | ❌ |
| Trend radar | ✅ | ❌ | Sınırlı |
| Content Evolution | ✅ | ❌ | ❌ |
| Video Script | ✅ | ❌ | ❌ |
| Image Prompt | ✅ | ❌ | ❌ |
| Shitpost modu | ✅ | ❌ | ❌ |

→ "Tweet Hunter'ın yarı fiyatına daha fazla özellik"
→ "XPatla ile aynı fiyat, %33 daha fazla kredi + 5 ekstra platform"

### 9.5 Risk ve Önlemler

| Risk | Önlem |
|------|-------|
| Ultra kullanımı beklenenden yüksek → maliyet patlar | Ultra'yı 3x kredi tutarak doğal throttle, gerekirse 4x'e çık |
| Free kullanıcılar dönüşüm yapmıyor | Free limiti düşür (50 → 30), Ultra erişimi kaldır |
| Style Lab abuse (çok profil scrape) | Per-profil kredi + plan bazlı profil limiti |
| Kredi top-up satmıyor | Bundle paketler ($9/500 kredi), "Black Friday" kampanyaları |
| XPatla fiyat düşürürse | Value proposition özellik bazlı, fiyat savaşına girme |

---

## 10. Özet: 3 Plan Finali

```
╔══════════════════════════════════════════════════════════╗
║                    TYPE HYPE PLANS                       ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  FREE          PRO              BUSINESS                ║
║  $0/ay         $19/ay           $49/ay                  ║
║                ($15/ay yıllık)  ($39/ay yıllık)         ║
║                                                          ║
║  50 kredi      1,000 kredi      3,000 kredi             ║
║  Normal only   Normal+Ultra+S   Normal+Ultra+S          ║
║  1 stil        3 stil           10 stil                 ║
║  1 platform    6 platform       6 platform              ║
║  3 tur evolve  10 tur evolve    Sınırsız evolve         ║
║  7 gün geçmiş  Sınırsız         Sınırsız               ║
║                                 3 koltuk                ║
║                                 Öncelikli destek        ║
║                                                          ║
║  Top-up: $5/200 kredi  |  $5/250 kredi (Business)      ║
╚══════════════════════════════════════════════════════════╝
```

### Kredi Harcama Özeti

```
1 kredi  = Tweet / Post / Quote / Reply / Evolve / Video Script / Image Prompt (Normal)
3 kredi  = Thread / Article / Blog (Normal) — veya Tweet/Post (Ultra)  
5 kredi  = Yeni Style Lab profili — veya YouTube full script (Normal)
8 kredi  = Thread / Article (Ultra)
12 kredi = YouTube full script / Blog article (Ultra)
0 kredi  = Trend Analizi (otomatik, herkes için)
```

---

## 11. Sonraki Adımlar

1. [ ] Berkay review & feedback
2. [ ] Kredi sistemi backend implementasyonu (user_credits tablosu, middleware)
3. [ ] Stripe entegrasyonu (subscription + top-up)
4. [ ] Frontend pricing sayfası
5. [ ] Plan kısıtlamaları (limit check middleware)
6. [ ] Admin dashboard (kullanıcı/kredi/gelir metrikleri)

---

*Bu doküman Type Hype'ın ilk fiyatlandırma çalışmasıdır. Pazar koşullarına, kullanıcı feedback'ine ve maliyet değişikliklerine göre güncellenmelidir.*

# ContentFactory - X Algorithm Knowledge
# X/Twitter algoritma bilgileri, hook formülleri, CTA stratejileri ve içerik kuralları
# Kaynak: Twitter açık kaynak kodu (github.com/twitter/the-algorithm) + Deep Research 2026

ALGORITHM_KNOWLEDGE = """
## 🧠 X ALGORİTMA BİLGİSİ (Kaynak Kod Doğrulanmış - 2026)

Bu bilgileri içerik üretirken arka planda kullan. Kullanıcıya "algoritma" deme, sadece daha etkili içerik üret.

### Heavy Ranker Engagement Ağırlıkları (Kaynak koddan doğrulanmış)
- **reply_engaged_by_author:** 75.0x 🔥 (EN YÜKSEK! Tweet'ine gelen reply'a cevap verirsen)
- **Reply:** 13.5x (konuşma başlatmak çok değerli)
- **Profile click:** ~12.0x (profil ziyareti tetikleyen içerik)
- **Favorite on reply (good_click):** 11.0x (reply'a like atmak)
- **Good click v2:** 10.0x (2+ dakika dwell time)
- **Bookmark:** ~10x (sessiz ama güçlü sinyal, kodda yok ama güçlü kanıt)
- **Repost/RT:** 1.0x (ÖNCEKİ BİLGİ YANLIŞ: 20x DEĞİL, sadece 1.0x!)
- **Like/Fav:** 0.5x (en düşük ağırlık)
- **Video %50 izlenme:** 0.005x (çok düşük)

### ⚠️ Penalty Ağırlıkları (ÖLÜMCÜL!)
- **Report:** -369.0 💀 (TEK BİR REPORT = 738 like'ı siler! Kesinlikle kaçın!)
- **Negative feedback (Show less):** -74.0 (ağır ceza)
- **"Show less" / "Not interested":** 0.05x (%95 skor düşüşü! Benzer tüm içerikler etkilenir)
- **Bilinmeyen dil:** 0.01x (neredeyse ölüm! Dil tutarlılığı zorunlu)
- **OON Reply Penalty:** 10.0 (Out of Network reply cezası)
- **Fake engagement detection:** Aktif! fake_favorite, fake_reply, fake_retweet sayılıyor

### Dwell Time (Okuma Süresi)
- Kullanıcı tweet'i 3 saniyeden az incelerse → negatif sinyal
- İlk cümle okuyucuyu YAKALAMALI — scroll durdurucu olmalı
- Uzun ama değerli içerik → yüksek dwell time → algoritmik boost
- Thread formatı dwell time'ı doğal olarak artırır
- 2+ dakika dwell = "good_click_v2" (10.0x ağırlık!)

### ⏱️ Velocity Window (İlk 30 Dakika KRİTİK!)
- **Real-time aggregate penceresi: 30 dakika** — ilk yarım saat her şeyi belirler
- Short-term pencere: 3 gün
- Long-term pencere: 50 gün
- İlk 30 dakikadaki engagement velocity, tweet'in tüm ömrünü şekillendirir
- 6 saatlik halflife — ama ilk 30 dk bundan bile önemli

### Age Decay (Yaşlanma)
- Halflife: 360 dakika (6 saat)
- **Floor: 0.6** — tweet ASLA %60'tan fazla değer kaybetmez
- Slope: 0.003 — kademeli düşüş
- Kaliteli evergreen içerik uzun süre yaşar

### Harici Link Cezası
- Harici link içeren tweet'ler %50-90 erişim kaybeder (Elon Musk doğruladı)
- Self-contained içerik yaz: Bilgiyi direkt tweet'e koy
- Link paylaşmak zorundaysan → reply'a koy, ana tweet'e değil

### Hesap Otoritesi (TweepCred - PageRank tabanlı)
- **TweepCred > 65 ZORUNLU!** (< 65 = anti-gaming filtresi, max 3 tweet gösterilir)
- Tutarlı niş içerik: SimClusters seni belirli topluluklara atıyor
- Karışık konular algoritmayı şaşırtır → tek alanda derinleş
- Kaliteli etkileşim alan hesaplar daha fazla dağıtım alır
- Takip/takipçi oranı önemli: Çok fazla takip = düşük otorite

### 🌐 Dil Etkisi
- UI İngilizce + tweet değil: 0.3x boost
- Tweet İngilizce + UI değil: 0.7x boost
- İkisi de farklı, İngilizce değil: 0.1x
- **Bilinmeyen dil: 0.01x** (neredeyse ölüm! Emoji spam, karışık dil = tehlike)
- Hedef kitle diliyle TUTARLI yaz

### Out of Network (OON) Dağıtım
- OON scale factor: 0.75 (%25 dezavantaj)
- OON reply penalty: 10.0
- Viral olmak için bu %25 cezayı aşacak kadar güçlü engagement lazım
- OON tweet ancak takip edilen biri etkileşim yaptıysa gösterilir

### Grok AI Sentiment Analizi
- Grok her postu semantik olarak analiz ediyor
- Pozitif, yapıcı, bilgi veren içerikler tercih ediliyor
- Negatif, troll, saldırgan içerikler penalize ediliyor
- Constructive disagreement OK, toxic olmamak şartıyla

### Premium/Verified Boost
- Premium hesaplar 2-4x erişim avantajı alıyor
- Premium reply'lar thread'de üstte gösteriliyor
- Organik erişim non-premium için ciddi ölçüde düşük

### Negatif Sinyal Süreleri
- Block, mute, abuse/spam report: KALICI
- Unfollow: 90 gün sonra silinir
- Negative interaction graph sürekli güncelleniyor
"""

ALGORITHM_KNOWLEDGE_COMPACT = """
## 🧠 İÇERİK OPTİMİZASYON STRATEJİSİ

- İlk cümle scroll durdurucu olmalı (3 saniye kuralı)
- Değer ver: Okuyucu bir şey öğrenmeli veya hissetmeli
- Self-contained yaz: Tüm bilgiyi içeriğin içinde ver
- **Reply'lara MUTLAKA cevap ver** (75.0x ağırlık — en yüksek sinyal!)
- Reply çekecek sorular sor (13.5x)
- Bookmark'a teşvik et (~10x)
- RT abartma, sadece 1.0x — reply çok daha değerli
- Pozitif ve yapıcı ton tercih et (report = -369.0, tek report bile yıkıcı!)
- İlk 30 dakika KRİTİK — hemen engagement al
- Dil tutarlılığı zorunlu (0.01x ceza!)
"""

CTA_STRATEGIES = """
## 💬 DOĞAL CTA STRATEJİLERİ

İçeriğin sonuna veya içine doğal şekilde yerleştir. "Beğen ve RT yap" gibi engagement bait YASAK.

### 🔥 Reply Tetikleyiciler (13.5x + reply'a cevap = 75.0x — EN DEĞERLİ!)
Reply çekmek ve sonra o reply'lara cevap vermek EN GÜÇLÜ strateji.
Soru sorarak, fikir isteyerek veya tartışma başlatarak reply'ı tetikle:
- "Sen ne düşünüyorsun?" yerine → "Senin deneyimin ne oldu?"
- "Katılıyor musun?" yerine → "Hangi noktada farklı düşünüyorsun?"
- "Bu sektörde çalışıyorsan bilirsin — en büyük yanılgı ne?"
- "What's been your experience with this?"
- "Where do you disagree?"
- "Drop your take below."

### 🔁 Reply Döngüsü Stratejisi (75.0x tetikleyici)
**Altın formül:** Soru sor → cevap gelsin → cevaba SEN DE reply at → 75.0x boost!
- "Bunu deneyen var mı? Sonuçlarınızı merak ediyorum." (sonra gelen her cevaba yanıt ver)
- "En son ne zaman [X] yaptın? Ben dün denedim ve..." (hikaye + soru = reply mıknatısı)
- Thread sonunda: "Eklemek istediğin bir şey var mı?" (sonra aktif reply ver)
- "I tried this last week — anyone else seeing similar results?" (sonra her cevaba engage ol)

### Bookmark Tetikleyiciler (~10x değerli):
- "Kaydet, lazım olacak."
- "Bookmark'la, tekrar döneceksin."
- "Kenara not al."
- "Bunu bir yere yaz."
- "Save this. You'll need it."
- "Bookmark for later."
- "Keep this one handy."

### RT/Repost Tetikleyiciler (1.0x — düşük ama yine faydalı):
Değer paylaşarak doğal paylaşımı tetikle:
- "Bunu bilen birini etiketle." (doğal, zorlama değil)
- "Takımınla paylaş."
- Thread sonunda: "Faydalı olduysa yay, başkalarının da görmesi lazım."
- "Share this with someone who needs to hear it."
- "Send this to your founder friend."

### YASAK CTA'LAR (bunları ASLA kullanma):
❌ "Beğen ve RT yap"
❌ "Like for X, RT for Y"
❌ "Follow for more"
❌ "Retweet if you agree"
❌ Herhangi bir engagement bait (fake engagement detection aktif!)
"""

HOOK_FORMULAS = """
## 🎣 HOOK FORMÜLLERİ (3 Saniye Kuralı)

İlk cümle okuyucuyu 3 saniye içinde yakalamalı. Aşağıdaki kalıpları kullan ama her seferinde farklı varyasyon üret.

### 1. Contrarian Hook (Herkesin inandığının tersini söyle)
**TR:**
- "Herkes X diyor. Gerçek tam tersi."
- "X'in en büyük yalanı: [yaygın inanış]."
- "[Yaygın tavsiye] diyorlar. Yapma."
- "X hakkında kimsenin söylemediği şey..."
- "[Popüler görüş]? Hayır. İşte neden."

**EN:**
- "Everyone says X. The opposite is true."
- "The biggest lie about X: [common belief]."
- "They tell you to [common advice]. Don't."
- "What nobody tells you about X..."
- "Unpopular opinion: [contrarian take]."

### 2. Curiosity Gap (Merak boşluğu yarat)
**TR:**
- "X yaptım. Sonucu beklemiyordum."
- "Bir şeyi değiştirdim ve her şey değişti."
- "3 ay önce bir karar verdim. Şimdi..."
- "Bunu keşfetmem X yılımı aldı."
- "Kimse bahsetmiyor ama..."

**EN:**
- "I did X. Didn't expect the result."
- "I changed one thing and everything changed."
- "3 months ago I made a decision. Now..."
- "It took me X years to figure this out."
- "Nobody talks about this but..."

### 3. Data Hook (Veriyle şok et)
**TR:**
- "X kişiden Y'si bunu bilmiyor."
- "X sektöründe %Y'lik bir değişim yaşandı."
- "Son X ayda Y oldu. Veriler ortada."
- "X rakamına bak ve söyle: Normal mi bu?"
- "[Şaşırtıcı istatistik]. Evet, doğru okudun."

**EN:**
- "X out of Y people don't know this."
- "X industry saw a Y% shift."
- "In the last X months, Y happened. The data speaks."
- "Look at this number: [stat]. Still think it's fine?"
- "[Surprising stat]. Yes, you read that right."

### 4. Story Hook (Hikayeyle çek)
**TR:**
- "Dün bir şey oldu."
- "Geçen hafta bir mail aldım..."
- "2 yıl önce bu konuda hiçbir şey bilmiyordum."
- "Bir arkadaşım aradı. Sesi titriyordu."
- "Toplantıdaydım. Biri bir şey söyledi ve..."

**EN:**
- "Something happened yesterday."
- "Last week I got an email..."
- "2 years ago I knew nothing about this."
- "A friend called me. Their voice was shaking."
- "I was in a meeting when someone said..."

### 5. Challenge Hook (Meydan oku)
**TR:**
- "Bunu yapamıyorsan, X'i hiç anlamamışsın."
- "X'te ciddi misin? O zaman şunu sor kendine."
- "Bu listedeki 5 şeyin 3'ünü yapıyorsan iyisin."
- "Çoğu kişi bunu yanlış yapıyor. Sen de muhtemelen."
- "Test et kendini: [soru veya senaryo]."

**EN:**
- "If you can't do this, you don't understand X."
- "Serious about X? Then ask yourself this."
- "If you're doing 3 of these 5, you're ahead."
- "Most people get this wrong. You probably do too."
- "Test yourself: [question or scenario]."

### 6. Reply-Bait Hook (Tartışma başlatıcı — reply çekmek için) 🔥 YENİ
**TR:**
- "İki kamp var: [A] diyenler ve [B] diyenler. Hangisi haklı?"
- "Bence [güçlü görüş]. Değiştirecek bir argümanın var mı?"
- "Bu konuda %90'ınız yanılıyor. Kanıtlayayım."
- "[X] hakkında en tartışmalı fikrim: [cesur iddia]."
- "Bir tek ben mi böyle düşünüyorum: [beklenmedik görüş]?"
- "Eğer [X] diyorsan, şunu açıkla: [zor soru]."

**EN:**
- "Two camps: [A] vs [B]. Which side are you on?"
- "I believe [strong take]. Change my mind."
- "90% of you get this wrong. Let me prove it."
- "My most controversial take on [X]: [bold claim]."
- "Am I the only one who thinks [unexpected view]?"
- "If you say [X], explain this: [hard question]."

### ⚠️ Reply-Bait KURALLARI:
- Gerçek düşündüren sorular sor, "sen ne düşünüyorsun?" tarzı boş sorular YASAK
- Tartışma başlat ama toxic olma (report = -369.0!)
- Gelen reply'lara MUTLAKA cevap ver (75.0x boost!)
- Polarize et ama hakaret etme
"""

CONTENT_RULES = """
## 📐 ALGORİTMA DOSTU İÇERİK KURALLARI

### 🔥 Reply Kuralı (EN ÖNEMLİ — 75.0x!)
- Tweet'ine gelen reply'lara MUTLAKA cevap ver!
- reply_engaged_by_author = 75.0 → algoritmadaki EN YÜKSEK ağırlık
- Soru sor → cevap gelsin → cevaba reply at = altın döngü
- Reply'ları görmezden gelmek = en büyük fırsat kaybı

### ⚠️ Report Riski (ÖLÜMCÜL: -369.0!)
- Tek bir report bile -369.0 ceza = 738 like'ı siler!
- Report tetikleyecek içerikten MUTLAKA kaçın
- Provoke et ama sınırı aşma: tartışma OK, hakaret/tehdit ÖLÜM
- Spam report da kalıcı negatif sinyal

### 🌐 Dil Tutarlılığı (ZORUNLU!)
- Bilinmeyen/karışık dil = 0.01x ceza (neredeyse sıfır görünürlük!)
- Hedef kitlenin diliyle TUTARLI yaz
- Aynı tweet'te dil karıştırma (emoji spam, rastgele karakterler = tehlike)
- İngilizce ve Türkçe ayrı tweet'lerde kullan, karıştırma

### Link Kuralı
- Harici link ana tweet'e KOYMA → %50-90 erişim kaybı
- Link paylaşmak zorundaysan → thread aç, linki reply'a koy
- En iyisi: Bilgiyi direkt tweet'e yaz, self-contained

### Medya Kuralı
- Görsel (resim/video/GIF) eklemek ~%40 daha fazla erişim sağlar
- Medya önerisi yap: "Bu tweet'e [şu tarz] bir görsel ekle" gibi

### Hashtag Kuralı
- Maximum 2 hashtag
- 3+ hashtag = spam sinyali, erişim düşer
- Hashtag kullanmasan da olur, içerik kalitesi > hashtag

### Thread Optimizasyonu
- İlk tweet bağımsız değer vermeli (tek başına da çalışmalı)
- Her tweet kendi başına okunabilir olsun
- Son tweet'te CTA veya özet ver
- Numaralandır: 1/, 2/, 3/

### Optimal Uzunluk
- 70-100 karakter: En çok etkileşim (like/RT)
- 200-280 karakter: En çok dwell time (algoritmik boost)
- Konuya göre seç: Hızlı punch → kısa, derinlik → uzun

### Büyük Harf Kullanımı
- TAMAMI BÜYÜK HARF = "shout score" cezası
- Vurgu için MAX 1-2 kelime büyük harf OK
- Doğal yazım her zaman daha iyi performans gösterir

### Sentiment
- Pozitif, yapıcı, bilgi veren içerik algoritmik avantaj sağlar
- Constructive criticism OK, toxic olmamak şart
- "Şikayet tweet'i" yerine "çözüm tweet'i" yaz

### ⏱️ Zamanlama (İlk 30 Dakika!)
- İlk 30 dakika KRİTİK — hemen engagement gelmeli
- Takipçilerin aktif olduğu saatte paylaş
- Paylaşım sonrası ilk gelen reply'lara HEMEN cevap ver (75.0x!)
- Aynı yazardan 60 dk içinde tekrar tweet gösterilmez — spam yapma

### Fake Engagement Uyarısı
- Sahte engagement detection AKTIF (fake_fav, fake_reply, fake_rt sayılıyor)
- Bot/sahte hesap etkileşimleri tespit ediliyor ve cezalandırılıyor
- Organik büyüme her zaman daha güvenli
"""

# Export
__all__ = [
    'ALGORITHM_KNOWLEDGE',
    'ALGORITHM_KNOWLEDGE_COMPACT',
    'CTA_STRATEGIES',
    'HOOK_FORMULAS',
    'CONTENT_RULES',
]

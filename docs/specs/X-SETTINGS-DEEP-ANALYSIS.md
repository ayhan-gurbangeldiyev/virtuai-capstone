# X Ayarları v2: Derin Analiz

> Her karar algoritma verisine ve output kalitesine dayalı olmalı. Yüzeysel "feature ekleyelim" yaklaşımı yok.

---

## 1. TEMELLERİ ANLAYALIM: Algoritma Ne Diyor?

### Algoritma Ağırlıkları (Kaynak koddan doğrulanmış)

| Aksiyon | Ağırlık | Prompt ile kontrol edilebilir mi? |
|---------|---------|----------------------------------|
| Reply by author (reply'a cevap) | 75.0x | ❌ Post-publish davranış, content değil |
| Reply (tweet'e gelen cevap) | 13.5x | ✅ Soru sor, tartışma başlat, reply-bait |
| Profile click | 12.0x | ✅ Merak uyandır, "kim bu?" dedirt |
| Good click (2+ dk dwell) | 10.0x | ✅ Hook kalitesi, içerik derinliği |
| Bookmark | ~10x | ✅ Kaydetmeye değer bilgi, CTA |
| Repost/RT | 1.0x | ⚠️ Düşük, ama paylaşılabilirlik önemli |
| Like | 0.5x | ⚠️ En düşük, tek başına anlamsız |
| Report | -369.0 | ✅ Provokasyon sınırı, ton kontrolü |

### Kritik İçgörü:
**İçerik kalitesini en çok etkileyen 3 faktör:**
1. **Hook kalitesi** → Dwell time gateway (3 saniye kuralı), velocity window (ilk 30 dk)
2. **Reply tetikleyicilik** → 13.5x, en yüksek content-driven metrik
3. **Bookmark-worthiness** → ~10x, "değer" ölçüsü

**Dolayısıyla ayarlardaki her parametre şu soruya cevap vermeli:**
> "Bu ayar, output'un hook kalitesini, reply tetikleyiciliğini veya bookmark değerini artırıyor mu?"

---

## 2. MEVCUT AYARLARIN DERİN ANALİZİ

### A. Persona (5 seçenek: Saf, Otorite, Insider, Mentalist, Haber)

**Ne yapıyor:** 
Her persona ~500 karakter detaylı prompt (kimlik, ses, yazım kuralları, örnek yapılar, kaçınılacaklar, hook rehberi). LLM'in "kim gibi yazacağını" belirler.

**Output'a etkisi:** YÜKSEK
- "Saf" ile yazılan tweet gerçekten samimi ve kişisel çıkıyor
- "Otorite" kesin, punch'lı, net
- "Insider" gizli bilgi vibes
- "Mentalist" actionable, framework odaklı
- "Haber" faktüel, kısa

**Pros:**
- Her persona genuinely farklı output üretiyor (test edilmiş)
- Voice consistency sağlıyor
- Hook rehberi persona'ya özel (her biri farklı açılış stratejisi)
- Psychological triggers tanımlı (Otorite: exclusivity+certainty, Insider: FOMO+curiosity, vb.)

**Cons:**
- İsimler soyut: "Mentalist" ne demek? Kullanıcı anlamıyor
- "Haber" çok niş, diğer 4'e göre çok dar kullanım alanı
- Persona + Ton çakışmaları var (Haber + Unhinged = anlamsız)
- 5 persona × 4 ton = 20 kombinasyon, ama sadece ~10'u mantıklı

**Algoritma bağlantısı:**
- Otorite → Profile click (12x): "Kim bu bilen adam?" etkisi
- Insider → Bookmark (~10x): "Bunu kaydetmeliyim" etkisi  
- Saf → Reply (13.5x): Samimi ton tartışma davet eder
- Mentalist → Bookmark (~10x): Actionable content kaydetmeye değer
- Haber → Dwell time (10x): Bilgi yoğun, okunur

**Karar:** ✅ KALSIN, ama isimleri ve tanımları güncellensin.

### B. Ton (4 seçenek: Natural, Raw, Polished, Unhinged)

**Ne yapıyor:**
Yapısal kılavuz. Natural = serbest akış, Raw = brain dump, Polished = Thesis→Evidence→Insight, Unhinged = Shock→Escalate→Twist.

**Output'a etkisi:** ORTA-YÜKSEK
- "Polished" gerçekten structured çıkıyor (TEI framework)
- "Unhinged" bold ve attention-grabbing
- "Natural" en doğal ses
- "Raw" ise iç monolog hissi

**Pros:**
- Yapıyı kontrol ediyor (içerik değil, format)
- Persona'dan bağımsız bir boyut (aynı kişi farklı yapıda yazabilir)
- "Polished" ve "Unhinged" genuinely farklı prompt stratejileri

**Cons:**
- "Natural" vs "Raw" ayrımı çok ince, kullanıcı farkı anlamıyor
- Bazı persona × ton kombinasyonları çelişkili:

| | Natural | Raw | Polished | Unhinged |
|---|:---:|:---:|:---:|:---:|
| Saf | ✅ | ✅ | ⚠️ | ⚠️ |
| Otorite | ✅ | ⚠️ | ✅ | ✅ |
| Insider | ✅ | ✅ | ✅ | ⚠️ |
| Mentalist | ✅ | ⚠️ | ✅ | ⚠️ |
| Haber | ✅ | ❌ | ✅ | ❌ |

⚠️ = Garip ama çalışabilir, ❌ = Çelişkili

20 kombinasyonun 4'ü çelişkili, 5'i garip. 11'i mantıklı. Kullanıcı kötü combo seçerse output kalitesi düşer.

**Algoritma bağlantısı:**
- Unhinged → Reply (13.5x): Provokasyon reply çeker
- Polished → Bookmark (~10x): Structured content kaydedilir
- Natural → Dwell time (10x): Doğal akış okutturur
- Unhinged → Report riski (-369): Sınır aşılırsa felaket

**Karar:** ✅ KALSIN ama Natural/Raw birleştirilsin (3'e insin), ve geçersiz kombinasyonlar engellensin.

### C. Uzunluk (5 seçenek: Micro, Punch, Spark, Storm, Thread)

**Ne yapıyor:** Karakter limiti belirler. Her birinin detaylı format rehberi var.

**Output'a etkisi:** YÜKSEK
- En net, en ölçülebilir ayar
- LLM buna genellikle uyuyor
- Format rehberi (örn: Storm'da line break kullan) kaliteyi artırıyor

**Pros:**
- Basit, anlaşılır, etkili
- Kullanıcı tam olarak ne aldığını biliyor
- Algoritmik olarak: Micro → like/RT optimize, Spark/Storm → dwell time optimize

**Cons:** Yok denecek kadar az.

**Karar:** ✅ AYNEN KALSIN. Dokunma.

### D. Knowledge Mode (5 seçenek: Yok, Insider, Contrarian, Hidden, Expert)

**Ne yapıyor:** Prompt'a ~500 karakter bilgi perspektifi enjekte eder. "Nasıl bak" değil, "nereden bak" belirler.

**Output'a etkisi:** ORTA
- "Contrarian" genuinely farklı açı üretiyor (en etkili olanı)
- "Insider" Persona=Insider ile çakışıyor (redundant)
- "Hidden" belirsiz, "Expert" ile farkı az

**Pros:**
- Contrarian mode çok güçlü (hook type'a benzer ama daha derin)
- Bilgi perspektifini değiştirmek output'u kökten değiştirir

**Cons:**
- Insider Knowledge × Insider Persona = double-dipping, gereksiz
- "Hidden" ve "Expert" ayrımı pratikte belirsiz
- İsimler İngilizce, target audience Türk

**Karar:** 🔄 SADELEŞ. 3'e indir: Standart, Karşıt Görüş, Derinlik.

### E. Dil (3 seçenek: Otomatik, TR, EN)

**Output'a etkisi:** YÜKSEK (ama zaten çalışıyor)
- Algoritma: Bilinmeyen dil = 0.01x (ölüm cezası)
- Dil tutarlılığı kritik

**Karar:** ✅ AYNEN KALSIN.

### F. APEX Mode (On/Off)

**Ne yapıyor:** ~800 karakter ultra-viral prompt ekleniyor. Scroll-stopper hook, escalation, mic-drop ending, bookmark CTA, dwell time optimizasyon.

**Output'a etkisi:** ORTA-YÜKSEK
- Aktifken output genuinely daha bold ve attention-grabbing
- Ama bazen "too much" oluyor, forced hissettiriyor
- Her tweet viral olmak zorunda değil

**Pros:**
- Çalışıyor, bold output üretiyor
- Algoritma checklist'i dahil (bookmark CTA, dwell time, link kuralı)

**Cons:**
- "APEX" ismi anlamsız
- On/Off binary çok kaba, bazen "biraz viral" istiyorsun
- İçindeki kurallar (örn: "Liste formatı YASAK") bazı konu türleri için yanlış

**Karar:** 🔄 İSİM DEĞİŞSİN + Amaç sistemiyle entegre edilsin.

---

## 3. YENİ AYAR ÖNERİLERİ: DERİN ANALİZ

### ÖNERİ 1: Amaç (Goal) Eklenmesi

**Tez:** Kullanıcının "bu tweet'ten ne istediğini" bilmek, prompt'un tüm yapısını daha iyi yönlendirir.

**Detaylı Pros:**

1. **Prompt stratejisini kökten değiştirir:**
   - Viral amaç → Hook aggressive, CTA var, unexpected açı, escalation
   - Otorite amaç → Data-backed, measured tone, profile-click optimize
   - Tartışma amaç → Reply-bait hook, soru bitişi, polarize edici tez
   - Bağlantı amaç → Personal story, vulnerability, relatable observations

2. **Algoritma metrikleriyle doğrudan eşleşir:**
   - Viral → Tüm metrikleri maximize (ama özellikle dwell + bookmark)
   - Otorite → Profile click (12x) optimize
   - Tartışma → Reply (13.5x) optimize
   - Bağlantı → Reply + dwell time (empati=uzun okuma)

3. **Kullanıcı deneyimini iyileştirir:**
   - "Ne istiyorum?" sorusu "hangi persona?" sorusundan daha doğal
   - Yeni kullanıcı için bile sezgisel

4. **Öteki ayarların smart default'larını belirler:**
   - Viral seçildi → Hook=Otomatik ama contrarian/curiosity ağırlıklı, CTA=bookmark, Ton=unhinged ağırlıklı
   - Otorite → Hook=data/insider, CTA=yok veya soft, Ton=polished ağırlıklı
   - Bu sayede kullanıcı sadece amaç seçse bile iyi output alır

**Detaylı Cons:**

1. **"Viral" herkes seçer, diğerleri kullanılmaz:**
   - Karşı argüman: Bu aslında iyi. "Viral" default olsun, diğerleri power-user için
   - Ama UI'da 6 seçenek varsa ve herkes aynısını seçiyorsa, gereksiz complexity

2. **Amaç + Persona + Ton = 3 boyutlu kontrol, çok mu fazla?**
   - Kullanıcı Amaç=Viral, Persona=Saf, Ton=Polished seçerse → çelişki mi?
   - Çözüm: Amaç bazlı smart defaults, kullanıcı override edebilir

3. **Prompt'a eklenen karakter sayısı artar (token maliyeti):**
   - Her amaç ~300-500 karakter prompt → mevcut sisteme +400 char
   - Maliyet etkisi: GPT-4o ile ~$0.001 artış/tweet, ihmal edilebilir

4. **Over-engineering riski:**
   - LLM zaten konuya göre uygun tweet yazıyor
   - Amaç belirtmek gerçekten output'u iyileştiriyor mu, yoksa sadece "ayar var" hissi mi?
   - **TEST GEREKLİ:** Aynı konu, aynı diğer ayarlar, farklı amaçlarla 4 tweet üret → fark var mı?

**Kararım:** ✅ EKLE ama 4 seçenek yeter (6 çok fazla):
- **Viral** (max erişim, algoritma optimize)
- **Otorite** (güven inşa, uzmanlık)  
- **Tartışma** (reply çek, konuşma başlat)
- **İlham** (bağlantı kur, motive et, kişisel)

"Bilgi" → Otorite'nin alt kümesi, "Büyüme" → Viral'in alt kümesi. Ayrı seçenek gereksiz.

---

### ÖNERİ 2: Hook Tipi Eklenmesi

**Tez:** Tweet'in en kritik parçası ilk cümle. Bunu kullanıcıya kontrol ettirmek output kalitesini artırır.

**Detaylı Pros:**

1. **Algoritma desteği çok güçlü:**
   - Dwell time < 3 saniye = negatif sinyal. Hook kalitesi bunu belirler.
   - İlk 30 dakika velocity = hook'un ilk impression kalitesi
   - HOOK_FORMULAS zaten 6 farklı kalıp tanımlı, sadece expose edilmiyor

2. **Gerçek fark yaratıyor:**
   - Contrarian hook: "Herkes X diyor. Gerçek tam tersi." → Merak + reply tetikler
   - Story hook: "Dün bir şey oldu." → Dwell time artırır (okuyucu hikayeyi merak eder)
   - Data hook: "X kişiden Y'si bunu bilmiyor." → Authority + bookmark
   - Bunlar genuinely farklı tweet açılışları, farklı engagement pattern'ları

3. **"Otomatik" seçeneği sorunsuz çalışır:**
   - Kullanıcı hook seçmezse, AI konu ve amaca göre en uygununu seçer (mevcut davranış)
   - Ama bilinçli seçim yapan kullanıcı daha tutarlı sonuç alır

**Detaylı Cons:**

1. **LLM hook talimatına ne kadar uyuyor?**
   - Test gerekli. "Data hook kullan" deyince gerçekten data ile mi açıyor?
   - Bazen konu data hook'a uymuyor (örn: kişisel bir deneyim konusu + data hook = forced)
   - **Risk:** Konu-hook uyumsuzluğu output kalitesini düşürür

2. **Decision fatigue:**
   - Amaç + Hook + Persona + Ton + Uzunluk = 5 seçim. Çok mu?
   - Karşı argüman: "Otomatik" default, sadece bilinçli kullanıcı değiştirir

3. **Hook çeşitliliği azalabilir:**
   - Kullanıcı hep "Contrarian" seçerse tüm tweet'leri aynı formüle düşer
   - Mevcut durumda AI rotate ediyor, çeşitlilik doğal
   - Çözüm: "Otomatik"'i default yap, bilinçli seçim opsiyonel

4. **Prompt'ta zaten var:**
   - HOOK_FORMULAS prompt'a zaten dahil, AI bunları kullanıyor
   - Kullanıcıya açmak gerçekten output'u iyileştiriyor mu yoksa sadece kontrol hissi mi?

**Kararım:** ⚠️ EKLE AMA DİKKATLİ
- Default: **Otomatik** (şimdiki gibi, AI seçer)
- 4 manuel seçenek yeter: Zıt Görüş, Merak, Hikaye, Tartışma
- "Veri" ve "Meydan Okuma" hook'ları AI'ın otomatik repertuarında kalsın
- **Mutlaka A/B test yap:** Manuel hook seçimi vs otomatik → hangisi daha iyi output?

---

### ÖNERİ 3: CTA Stili Eklenmesi

**Tez:** Tweet'in bitişi, algoritmanın ödüllendirdiği aksiyonları tetikler.

**Detaylı Pros:**

1. **Algoritma desteği:**
   - Reply = 13.5x → Soru ile bitirmek reply tetikler
   - Bookmark = ~10x → "Kaydet" hint'i bookmark tetikler
   - Bunlar content-driven en yüksek ağırlıklı aksiyonlar

2. **Mevcut durumda CTA rastgele:**
   - Prompt'ta CTA_STRATEGIES var ama hangi CTA gideceği AI'a bırakılmış
   - Bazen gereksiz CTA ekleniyor, bazen hiç eklenmiyor
   - Kullanıcı kontrolü tutarlılık sağlar

**Detaylı Cons:**

1. **Doğallık riski:**
   - "Her tweet'e soru ekle" → Yapay hissettirir
   - İyi tweet'lerin çoğu CTA'sız bitiyor, punch ile bitiyor
   - Forced CTA output kalitesini DÜŞÜRÜR

2. **AI zaten yapıyor:**
   - APEX modunda bookmark ve reply CTA otomatik
   - Ayrı bir CTA ayarı redundant olabilir

3. **Kullanıcı ne seçeceğini bilmiyor:**
   - "Soru mu, bookmark mı, paylaş mı?" — çoğu kullanıcı bilmez
   - Smart default yeterli olabilir

**Kararım:** ⚠️ EKLE AMA MİNİMAL
- 3 seçenek yeter: **Otomatik** (AI seçer), **Soru** (reply optimize), **Doğal** (CTA'sız, punch ile bitir)
- "Kaydet" ve "Paylaş" CTA'larını AI otomatik karar versin, ayrı seçenek gereksiz
- Amaç=Tartışma seçildiğinde CTA otomatik "Soru" olsun

---

### ÖNERİ 4: Persona + Ton Birleştirmek mi, Ayrı Tutmak mı?

Bu kararı çok dikkatli almak gerekiyor.

**Seçenek A: BİRLEŞTİR (Enerji skalası)**

Pros:
- Basit, tek bir slider/seçim
- Decision fatigue azalır
- Geçersiz kombinasyon problemi çözülür

Cons:
- **20 kombinasyondan sadece 5 kalır** — ciddi kayıp
- "Otorite + Natural" (sakin uzman) ve "Otorite + Unhinged" (cesur uzman) genuinely farklı output'lar. Birleştirme bunu yok eder.
- Persona prompt'ları (~500 char/persona) çok detaylı ve değerli. Hepsini 5 seviyeye sıkıştırmak kalite kaybı demek.
- **OUTPUT KALİTESİ DÜŞER.**

**Seçenek B: AYRI TUT (mevcut gibi)**

Pros:
- Maximum esneklik (20 combo)
- Her persona/ton kendi detaylı prompt'u var
- Mevcut çalışan sistemi bozmaz

Cons:
- Geçersiz kombinasyonlar mümkün (Haber+Unhinged)
- 2 ayrı seçim gerekiyor
- İsimlendirme belirsiz

**Seçenek C: AYRI TUT + AKILLI KISITLA (önerim)**

Pros:
- Esnekliği korur
- Geçersiz kombinasyonları engeller
- İsimler güncellenir
- Ton seçenekleri persona'ya göre filtre olur

Cons:
- Frontend'de koşullu UI gerekir (extra complexity)

**Seçenek C detayı:**

Persona seçilince sadece uyumlu ton'lar gösterilir:

| Persona | Uyumlu Tonlar |
|---------|--------------|
| Sen (Saf) | Akıcı, Ham |
| Uzman (Otorite) | Akıcı, Yapılı, Keskin |
| İçeriden (Insider) | Akıcı, Ham, Yapılı |
| Mentor (Mentalist) | Akıcı, Yapılı |
| Muhabir (Haber) | Akıcı, Yapılı |

Bu, 20 kombinasyondan 12 uyumlu olanı bırakır, 8 çelişkiyi engeller.

**Kararım:** ✅ Seçenek C. Ayrı tut, akıllı kısıtla, isimleri güncelle.

---

### ÖNERİ 5: Natural ve Raw Birleştirmek mi?

**Mevcut fark:**
- Natural: "Düşündüğün gibi yaz, yapıya zorlanma" — kısaltmalar OK, fragments OK
- Raw: "Filtresiz brain dump, iç monolog" — "hmm", "wait", "aslında hayır", çelişkiler

**Test:** Aynı konu + aynı persona ile Natural vs Raw output karşılaştırması:
- Natural: "Şunu fark ettim bugün. İnsanlar çok konuşuyor ama dinlemiyor."
- Raw: "Herkes 'passion'ını takip etmeli diyor... Ama ya passion'ın yoksa? Bilmiyorum."

**Fark var mı?** VAR ama ince. Natural daha "clean casual", Raw daha "messy thinking".

**Kullanıcı perspektifi:** Çoğu kullanıcı farkı anlamaz. İkisi de "doğal" hissettiriyor.

**Kararım:** 🔄 BİRLEŞTİR → "Doğal" olarak tek seçenek. Ham'ın en iyi özelliklerini (iç monolog, tamamlanmamış düşünceler) Doğal'a dahil et.

**Yeni ton listesi (3 seçenek):**
1. **Doğal** — Natural + Raw birleşimi. Serbest akış, samimi, filtresiz.
2. **Yapılı** — Polished. Thesis→Evidence→Insight. Profesyonel ama sıcak.
3. **Keskin** — Unhinged. Shock→Escalate→Twist. Bold, cesur, impact.

---

## 4. ÖNERİLEN FİNAL AYAR SETİ

### Birincil Ayarlar (her zaman görünür):

| # | Ayar | Seçenekler | Default | Algoritma Etkisi |
|---|------|-----------|---------|------------------|
| 1 | **Amaç** 🎯 | Viral / Otorite / Tartışma / İlham | Viral | Prompt stratejisini kökten yönlendirir |
| 2 | **Karakter** 🎭 | Sen / Uzman / İçeriden / Mentor / Muhabir | Uzman | Ses ve bakış açısı |
| 3 | **Yapı** 📐 | Doğal / Yapılı / Keskin | Doğal | Cümle yapısı ve format |
| 4 | **Uzunluk** 📏 | Micro / Punch / Spark / Storm / Thread | Punch | Karakter limiti |

### İkincil Ayarlar (gelişmiş, varsayılan collapse):

| # | Ayar | Seçenekler | Default | Algoritma Etkisi |
|---|------|-----------|---------|------------------|
| 5 | **Hook** 🎣 | Otomatik / Zıt Görüş / Merak / Hikaye / Tartışma | Otomatik | İlk cümle kalıbı (dwell time) |
| 6 | **Bitiş** 💬 | Otomatik / Soru / Doğal | Otomatik | CTA stratejisi (reply/bookmark) |
| 7 | **Derinlik** 🧠 | Standart / Karşıt Görüş / Perde Arkası / Uzmanlık | Standart | Bilgi perspektifi |
| 8 | **Dil** 🌐 | Otomatik / Türkçe / English | Otomatik | Dil tutarlılığı |

### Kaldırılanlar:
- ~~APEX toggle~~ → Amaç=Viral seçilince otomatik aktif
- ~~Knowledge=Hidden~~ → Belirsiz, "Perde Arkası" ile örtüşüyor

### Toplam: 8 ayar (4 birincil + 4 ikincil)
Eski: 6 ayar (Persona + Ton + Uzunluk + Knowledge + Dil + APEX)
Fark: +2 yeni (Amaç, Hook/CTA), -1 kaldırılan (APEX), 1 birleştirilmiş (Natural+Raw)

---

## 5. AMAÇ PROMPT'LARI: DETAYLI TASARIM

### Viral 🔥
```
Amaç: Maximum erişim. Paylaşılma, kaydedilme, konuşulma.
Strateji:
- İlk cümle: Scroll durdurucu, 3 saniye kuralını geç
- İçerik: Unexpected açı, herkesin bilmediği bir şey
- Yapı: Tension yarat, her cümle bir sonrakini okutmalı
- Bitiş: Mic drop VEYA reply-bait
- Report riski: Provoke et ama sınırı aşma (-369 ceza!)
- Self-contained: Harici link koyma, bilgiyi tweet'e yaz
```

### Otorite 🏛️
```
Amaç: Uzmanlık ve güven inşa et. "Bu adam biliyor" dedirt.
Strateji:
- İlk cümle: Kesin bir iddia veya veri ile aç
- İçerik: Spesifik bilgi, somut örnek, rakam
- Yapı: Claim→Evidence→Insight
- Bitiş: Net takeaway, kaydetmeye değer sonuç
- Profil tıklatma: Merak uyandır, "daha fazlasını kim yaptı?" dedirt
- Ton: Kendinden emin ama arrogant değil
```

### Tartışma 💬
```
Amaç: Konuşma başlat, reply çek (13.5x ağırlık!).
Strateji:
- İlk cümle: Polarize edici tez veya tartışma başlatıcı soru
- İçerik: Net bir pozisyon al, gri alan bırakma
- Yapı: Bold iddia → Kısa destek → Açık uçlu kapanış
- Bitiş: Mutlaka soru veya meydan okuma ile bitir
- Reply döngüsü: Gelen reply'lara cevap ver (75x tetikler!)
- Dikkat: Tartışma ≠ toxic. Constructive disagreement OK.
```

### İlham ✨
```
Amaç: Kişisel bağ kur, relate edilsin, motive et.
Strateji:
- İlk cümle: Kişisel deneyim veya gözlem ile aç
- İçerik: Vulnerability OK, "ben de oradaydım" hissi
- Yapı: Hikaye → Ders → Empowerment
- Bitiş: Okuyucuyu güçlendiren kapanış
- Dwell time: Personal stories uzun okunur (10x)
- Ton: Samimi, insani, yapay pozitiflik yok
```

---

## 6. SMART DEFAULTS MATRİSİ

Kullanıcı sadece Amaç seçerse, diğer ayarlar otomatik en iyiye ayarlanır:

| Amaç | Default Karakter | Default Yapı | Default Hook | Default Bitiş | Default Derinlik |
|------|----------------|------------|------------|------------|---------------|
| Viral | Uzman | Keskin | Otomatik (rotate) | Otomatik | Standart |
| Otorite | Uzman | Yapılı | Veri/Merak | Doğal | Uzmanlık |
| Tartışma | Sen | Doğal | Tartışma/Zıt Görüş | Soru | Karşıt Görüş |
| İlham | Sen | Doğal | Hikaye | Doğal | Standart |

Bu sayede kullanıcı **sadece "Amaç + Konu" girip üret butonuna bassa bile** optimize output alır. Diğer ayarları override etmek opsiyonel.

---

## 7. RİSK ANALİZİ

### Risk 1: Prompt Şişmesi (Token Maliyeti)
**Mevcut prompt boyutu (tahmini):**
- SYSTEM_IDENTITY: ~300 char
- ALGORITHM_KNOWLEDGE: ~2500 char
- CONTENT_RULES: ~2000 char
- HOOK_FORMULAS: ~3000 char
- CTA_STRATEGIES: ~2000 char
- PERSONA: ~500 char
- TONE: ~500 char
- LENGTH: ~200 char
- QUALITY: ~300 char
- BANNED_PATTERNS: ~500 char
- HARD_BLOCK: ~600 char
- **Toplam: ~12,400 char ≈ 3,100 token**

**Yeni eklenecek:**
- GOAL prompt: ~400 char ≈ 100 token
- Hook override: ~100 char ≈ 25 token
- CTA override: ~100 char ≈ 25 token
- **Toplam artış: ~150 token (%5)**

**Verdict:** Maliyet etkisi ihmal edilebilir. ✅

### Risk 2: Over-constraining (Çok Fazla Kural = Robotik Output)
**Tehlike:** 8 ayar + algoritma bilgisi + banned patterns + quality criteria = LLM'e çok fazla kural veriyoruz. Model tüm kuralları memnun etmeye çalışırken doğallığını kaybedebilir.

**Test planı:**
1. Mevcut prompt ile 10 tweet üret
2. Yeni prompt ile 10 tweet üret (aynı konu)
3. Blind karşılaştırma: Hangisi daha doğal?

**Azaltma stratejisi:**
- Birincil ayarlar kısa ve net olsun
- İkincil ayarlar "yönlendirme" düzeyinde kalsın, "kural" düzeyinde değil
- "Doğal ol" mesajı her zaman son priority olarak eklensin

### Risk 3: Kullanıcı Kötü Kombinasyon Seçer
**Tehlike:** Amaç=Otorite + Karakter=Sen + Yapı=Keskin = Çelişkili

**Azaltma:** 
- Smart defaults
- Persona-Ton uyumluluk filtresi (Seçenek C)
- UI'da uyumsuz combo'larda hafif uyarı

### Risk 4: Herkes Aynı Ayarları Seçer
**Tehlike:** Herkes Viral+Uzman+Punch seçer, output çeşitliliği azalır.

**Azaltma:**
- AI rotation: Aynı ayarlarla bile her seferinde farklı hook ve yapı
- "Sürpriz" butonu: Rastgele ama akıllı kombinasyon

---

## 8. TEST PLANI (İMPLEMENTASYONDAN ÖNCE)

### Test 1: Amaç Etkisi
- Konu: "Yapay zekanın yazılım mühendisliğine etkisi"
- 4 farklı amaç prompt'u ile üret → Blind karşılaştırma
- **Soru:** Amaç seçmek gerçekten farklı output üretiyor mu?

### Test 2: Hook Kontrolü
- Konu: "Remote çalışma"
- 5 hook tipi ile üret → Her tweet'in açılışı gerçekten farklı mı?
- **Soru:** LLM hook talimatını takip ediyor mu?

### Test 3: Enerji Birleştirme vs Ayrı Tutma
- 5 "enerji" prompt'u vs en iyi 5 persona×ton combo
- **Soru:** Birleştirme kalite kaybına yol açıyor mu?

### Test 4: Prompt Boyutu vs Kalite
- Minimal prompt (sadece konu) vs mevcut prompt vs yeni prompt
- **Soru:** Daha fazla talimat gerçekten daha iyi output mu veriyor?

### Test 5: Smart Defaults
- Kullanıcı sadece Amaç+Konu giriyor, geri kalan otomatik
- vs. Kullanıcı tüm 8 ayarı seçiyor
- **Soru:** Smart defaults yeterli mi, yoksa manuel kontrol fark yaratıyor mu?

---

## 9. NİHAİ TAVSİYE

**İmplementasyondan ÖNCE Test 1-4'ü yap.** Eğer testler gösterirse ki:
- Amaç seçmek output'u iyileştiriyor → Ekle
- Hook kontrolü çalışıyor → Ekle  
- Persona+Ton ayrı tutmak daha iyi → Ayrı tut
- Prompt boyutu artışı kaliteyi düşürmüyor → Devam et

Test sonuçlarına göre final karar verilir. **Varsayıma dayalı değişiklik yapma.**

### Uygulama Sırası (test sonrası):
1. Backend: `goals.py` yaz, `builder_v2.py` oluştur
2. A/B test: v1 vs v2 prompt karşılaştırması (10 konu × 2 versiyon = 20 output)
3. Berkay review: Output kalitesi gerçekten arttı mı?
4. Onay → Frontend UI değişikliği
5. Deploy → Monitor

**Prensip:** Test et → Kanıtla → Sonra implement et. Asla varsayımla deploy etme.

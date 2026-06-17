# X Ayarları v2: Mevcut Formattan Çıkış Planı

## 🔍 Mevcut Durum Analizi

### Şu an X ayarlarında ne var:
| Ayar | Seçenekler | Sorun |
|------|-----------|-------|
| Karakter (Persona) | Saf, Otorite, Insider, Mentalist, Haber | Soyut, output'a etkisi belirsiz |
| Ton | Natural, Raw, Polished, Unhinged | İyi ama yeterli değil |
| Uzunluk | Micro, Punch, Spark, Storm, Thread | ✅ İyi çalışıyor |
| Knowledge Mode | Yok, Insider, Contrarian, Hidden, Expert | Faydalı ama gizli kalmış |
| Dil | Otomatik, TR, EN | ✅ Sorunsuz |
| APEX | On/Off | ✅ İyi ama anlaşılmıyor |

### Temel Sorunlar:
1. **Persona + Ton ayrımı kafa karıştırıyor**: "Otorite persona + Unhinged ton" ne demek? Kullanıcı için net değil.
2. **Hook/format kontrolü yok**: En etkili ayar aslında tweet'in nasıl açılacağı ve yapısı, ama kullanıcı bunu kontrol edemiyor.
3. **Amaç/hedef yok**: "Viral olmak", "tartışma başlatmak", "bilgi vermek" çok farklı tweet'ler gerektirir ama hepsi aynı ayarlarla üretiliyor.
4. **Algoritma bilgisi prompt'ta var ama kullanıcı yönlendiremiyor**: Reply-bait, bookmark-bait gibi stratejiler otomatik, kullanıcı seçemiyor.
5. **XPatla'nın 8 format'ı var**, bizde sadece uzunluk var.

---

## 🆚 Rakip Analizi

### XPatla
- **Format odaklı**: Micro, Short, Standard, Long, Thunder + Thread, Quote, Reply
- **Style cloning**: Username gir, tweet'lerini öğren
- **AI Coach**: Strateji danışmanlığı
- **Fiyat**: $16-41/ay

### Tweet Hunter
- **İlham kütüphanesi**: 3M+ viral tweet arasında arama
- **AI rewrite**: Beğendiğin tweet'i kendi stilinde yeniden yaz
- **Scheduling**: Zamanlama
- **Auto DM**: Otomatik DM gönderimi

### Postwise
- **Minimal yaklaşım**: Konunu yaz, biz yapalım
- **Engagement-optimized**: Etkileşim için eğitilmiş AI

### Type Hype'ın Avantajı
- Algoritma bilgisi derinliği (kaynak koddan)
- 13,653 viral tweet veritabanı
- Fine-tuned model
- Çoklu platform desteği
- **Eksik olan: Bu bilgiyi kullanıcıya açmak**

---

## 💡 Yeni Ayar Sistemi Önerisi

### Felsefe Değişikliği:
**Eski**: "Nasıl yazılsın?" (persona, ton, uzunluk)
**Yeni**: "Ne elde etmek istiyorsun?" (amaç, strateji, etki)

### Önerilen Yeni Ayarlar:

#### 1. 🎯 Amaç (Goal) — YENİ, EN ÖNEMLİ
Kullanıcının tweet'ten ne beklediğini belirler. Prompt'u kökten değiştirir.

| Seçenek | Açıklama | Prompt Etkisi |
|---------|----------|---------------|
| **Viral** | Maximum erişim, paylaşılma | Reply-bait hook, kontroversiyel açı, bookmark CTA |
| **Otorite** | Uzmanlık göster, güven inşa et | Data hook, detaylı bilgi, profil tıklaması tetikle |
| **Tartışma** | Konuşma başlat, reply çek | Reply-bait, polarize edici açı, soru bitişi |
| **Bağlantı** | Kişisel bağ kur, relate edilsin | Story hook, vulnerability, samimi ton |
| **Bilgi** | Değer ver, öğret, kaydet | Listicle/how-to yapı, bookmark-bait |
| **Büyüme** | Takipçi kazan, profil ziyareti | Teaser, "daha fazlası profilimde" hint, thread stratejisi |

#### 2. 🎣 Hook Tipi — YENİ
Mevcut HOOK_FORMULAS'ı kullanıcıya açar. Tweet'in açılışını belirler.

| Seçenek | Örnek |
|---------|-------|
| **Otomatik** | AI en uygununu seçer |
| **Zıt Görüş** | "Herkes X diyor. Gerçek tam tersi." |
| **Merak** | "Bir şeyi değiştirdim ve her şey değişti." |
| **Veri** | "X kişiden Y'si bunu bilmiyor." |
| **Hikaye** | "Dün bir şey oldu." |
| **Meydan Okuma** | "Bunu yapamıyorsan, X'i hiç anlamamışsın." |
| **Tartışma** | "İki kamp var. Hangisi haklı?" |

#### 3. 🔥 Enerji Seviyesi — Persona + Ton'un birleşimi
Mevcut 5 persona × 4 ton = 20 kombinasyon çok karmaşık. Bunları tek bir sezgisel skalaya indirge:

| Seviye | Eski Karşılığı | Açıklama |
|--------|----------------|----------|
| **Sakin** | Saf + Natural | Düşünceli, samimi, sessiz güç |
| **Normal** | Otorite + Natural | Profesyonel, güvenilir, net |
| **Enerjik** | Otorite + Polished | Punch'lı, vurgulu, etkili |
| **Agresif** | Insider + Raw | Keskin, direkt, cesur |
| **Çılgın** | Mentalist + Unhinged | No filter, provokasyon, shock |

#### 4. 📏 Uzunluk — AYNI KALSIN
Micro, Punch, Spark, Storm, Thread — iyi çalışıyor, değişmesin.

#### 5. 🧠 Bilgi Derinliği — Knowledge Mode güncelleme
Mevcut "insider/contrarian/hidden/expert" isimlerini daha anlaşılır yap:

| Yeni İsim | Eski | Açıklama |
|-----------|------|----------|
| **Standart** | Yok | Ekstra bilgi yok |
| **Perde Arkası** | Insider | Sektör iç bilgisi |
| **Karşıt Görüş** | Contrarian | Herkesin tersini savun |
| **Derinlik** | Expert | Teknik uzmanlık |

"Hidden" çıkarılabilir, "contrarian" zaten hook tipiyle çakışıyor ama farklı işlev görüyor.

#### 6. 🌐 Dil — AYNI KALSIN
Otomatik, Türkçe, English.

#### 7. ⚡ APEX Mode — İSİM DEĞİŞSİN
"APEX" kimseye bir şey ifade etmiyor. Öneriler:
- **Ultra Mod** (daha anlaşılır)
- **Viral Boost** (daha açık)
- veya sadece Goal="Viral" seçildiğinde otomatik aktif olsun

#### 8. 💬 CTA Stili — YENİ
Reply ve bookmark çok değerli. Kullanıcı bunu kontrol edebilsin:

| Seçenek | Açıklama |
|---------|----------|
| **Yok** | CTA olmadan bitir |
| **Soru** | Soru ile bitir (reply çeker) |
| **Kaydet** | Bookmark tetikleyici |
| **Paylaş** | Repost tetikleyici |
| **Otomatik** | Amaca göre AI seçer |

#### 9. 🎭 Yazım Stili (Style Profile) — MEVCUT, GELİŞTİRİLECEK
Style Lab zaten var. Ama ayarlar panelinde daha görünür olmalı. Aktif stil profili varsa üstte gösterilmeli.

---

## 🗑️ ÇIKARILACAKLAR

| Çıkarılan | Neden |
|-----------|-------|
| **Persona (5 seçenek)** | Enerji Seviyesi ile birleşti |
| **Ton (4 seçenek)** | Enerji Seviyesi ile birleşti |
| **APEX toggle** | Goal="Viral" + Enerji="Çılgın" ile aynı etki |

---

## 📐 Yeni vs Eski Karşılaştırma

### Eski Ayarlar (6 boyut, 23 seçenek):
```
Persona (5) + Ton (4) + Uzunluk (5) + Knowledge (5) + Dil (3) + APEX (2) = 6 kontrol
```

### Yeni Ayarlar (7 boyut, 30 seçenek):
```
Amaç (6) + Hook (7) + Enerji (5) + Uzunluk (5) + Bilgi (4) + CTA (5) + Dil (3) = 7 kontrol
```

### Fark:
- **Daha sezgisel**: "Ne elde etmek istiyorsun?" > "Hangi persona kullanılsın?"
- **Daha etkili**: Hook tipi ve CTA stili direkt algoritmik performansı etkiler
- **Daha basit**: 20 persona×ton kombinasyonu yerine 5 enerji seviyesi
- **Daha stratejik**: Amaç seçimi prompt'un tüm yapısını yönlendirir

---

## 🛠️ Backend Değişiklikleri

### Yeni prompt akışı:
```
1. Amaç → Ana strateji ve yapı belirlenir
2. Hook Tipi → İlk cümle kalıbı seçilir
3. Enerji → Ses tonu ve kelime seçimi
4. Uzunluk → Karakter limitleri
5. Bilgi Derinliği → Ekstra bilgi enjeksiyonu
6. CTA → Bitiş stratejisi
7. Stil Profili → Kişisel dokunuş (varsa)
8. Algoritma Bilgisi → Arka planda her zaman aktif
```

### Yeni dosyalar:
- `backend/prompts/goals.py` — 6 amaç tanımı (detaylı prompt parçaları)
- `backend/prompts/hooks_v2.py` — Hook kalıpları (mevcut algorithm.py'den refactor)
- `backend/prompts/energy.py` — 5 enerji seviyesi (persona+ton birleşimi)
- `backend/prompts/cta_v2.py` — CTA stratejileri (mevcut algorithm.py'den refactor)
- `backend/prompts/builder_v2.py` — Yeni prompt builder

### API değişikliği:
```python
class TweetGenerateRequestV2(BaseModel):
    topic: str
    goal: str = "viral"       # viral, otorite, tartisma, baglanti, bilgi, buyume
    hook: str = "auto"        # auto, contrarian, curiosity, data, story, challenge, debate
    energy: str = "normal"    # sakin, normal, enerjik, agresif, cilgin
    length: str = "punch"     # micro, punch, spark, storm, thread
    knowledge: str = None     # perde_arkasi, karsi_gorus, derinlik
    cta: str = "auto"         # yok, soru, kaydet, paylas, auto
    language: str = "auto"    # auto, tr, en
    variants: int = 3
```

### Geriye uyumluluk:
Eski endpoint (`/generate/tweet`) aynen çalışmaya devam eder. Yeni endpoint `/v2/generate/tweet` olarak eklenir. Frontend geçiş yapınca eski kaldırılır.

---

## 🎨 UI Önerisi

### Mevcut UI (pill seçiciler popup):
```
[Ayar ⚙️] butonuna tıkla → popup açılır → pill'ler seç
```

### Önerilen UI:
**Seçenek A — Inline ayarlar (input altında)**
```
[Konu gir...]
─────────────────────
🎯 Viral  Otorite  Tartışma  Bağlantı  Bilgi  Büyüme
🎣 Oto  Zıt Görüş  Merak  Veri  Hikaye  Meydan Oku
🔥 ●●●○○ (slider: Sakin → Çılgın)
📏 Micro  Punch  Spark  Storm  Thread
```
İkincil ayarlar (Knowledge, CTA, Dil) → küçük ⚙️ butonuyla açılan mini popup.

**Seçenek B — Smart defaults (minimal)**
```
[Konu gir...]
🎯 Amaç: Viral ▾    📏 Uzunluk: Punch ▾    🔥 Enerji: ●●●○○
```
Sadece 3 ana ayar görünür. Hook, CTA, Knowledge → AI otomatik seçer.

**Seçenek C — XPatla tarzı (mevcut popup ama yenilenmiş)**
```
[Ayar ⚙️] → Popup:
  Amaç: [pill seçiciler]
  Hook: [pill seçiciler]  
  Enerji: [slider]
  Uzunluk: [pill seçiciler]
  — Gelişmiş —
  Bilgi: [pill]
  CTA: [pill]
  Dil: [pill]
```

---

## 📊 A/B Test Planı

Yeni ayarları yapmadan önce mevcut sistemle test:

### Test 1: Goal etkisi
Aynı konu ("Yapay zekanın yazılım mühendisliğine etkisi") ile 6 farklı goal prompt'u → hangisi daha iyi output veriyor?

### Test 2: Hook etkisi
Aynı konu + aynı ayar, sadece hook tipi değişiyor → 7 varyant karşılaştır.

### Test 3: Enerji etkisi
Aynı konu, 5 enerji seviyesi → output kalitesi ve çeşitlilik.

### Test 4: CTA etkisi
Aynı tweet, farklı CTA stratejileri → doğallık ve etki.

---

## 📋 Sprint Planı

### Sprint 1: Backend prompt'ları (1 gün)
- [ ] `goals.py` yaz (6 amaç, detaylı prompt parçaları)
- [ ] `energy.py` yaz (5 seviye, persona+ton birleşimi)
- [ ] `hooks_v2.py` yaz (7 hook kalıbı, örneklerle)
- [ ] `cta_v2.py` yaz (5 CTA stratejisi)
- [ ] `builder_v2.py` yaz (yeni prompt builder)

### Sprint 2: API + test (1 gün)
- [ ] `/v2/generate/tweet` endpoint ekle
- [ ] A/B test: eski vs yeni prompt karşılaştırması
- [ ] Fine-tune: Goal/Hook/Energy testleri

### Sprint 3: Frontend UI (1 gün)
- [ ] SettingsPopup v2 (seçilen UI formatına göre)
- [ ] Yeni param'ları API'ye gönder
- [ ] Default değerleri akıllı seç

### Sprint 4: Deploy + iterate (yarım gün)
- [ ] Hetzner'a deploy
- [ ] Berkay ile test
- [ ] Feedback'e göre iterate

---

## ⚠️ Riskler & Dikkat Edilecekler

1. **Geriye uyumluluk**: Mevcut kullanıcılar etkilenmemeli. v1 endpoint korunmalı.
2. **Prompt uzunluğu**: Çok fazla ayar prompt'u şişirirr → token maliyeti artar. Akıllı birleştirme gerekli.
3. **Decision fatigue**: 7 ayar çok mu? Smart defaults ile çözülür (Seçenek B).
4. **Test**: Yeni prompt'ların gerçekten daha iyi output verdiğinden emin ol.

---

## 🏁 Sonuç

Bu plan mevcut "persona + ton" formatından çıkıp **amaç-odaklı, strateji-odaklı** bir sisteme geçişi hedefliyor. Kullanıcı "ne istediğini" söylüyor, sistem "nasıl yapılacağını" biliyor. Algoritma bilgisi ve hook formülleri artık kullanıcının elinde.

**Berkay'dan beklenen karar:**
1. Önerilen 7 ayar seti OK mi? Çıkarılacak/eklenecek var mı?
2. UI formatı: A (inline), B (minimal), C (popup)?
3. Sprint planı OK mi? Öncelik sırası?

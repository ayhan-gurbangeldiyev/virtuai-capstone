"""Phase 25.C — Voice mode blocks for content_type-aware tone rotation.

Used by `builder_v3._build_ses` when called from Hype Crew Strategist path.
Three modes:
  - first_person_witty   (default — Cansu kendi sesi)
  - third_person_neutral (n8n Content Factory stili — tarafsız gazeteci)
  - hybrid               (3. şahıs fakta + 1. şahıs reaksiyon)

Voice mode is an ADDITIONAL layer on top of (not a replacement for):
  - Stil DNA (highest priority — style profile / Style Lab clone)
  - Persona essence (uzman/otorite/iceriden/mentalist/haberci)
  - Brand voice DNA (background layer)

Hence the section title "Tonal Çerçeve" — it frames the voice without
overriding it.
"""

FIRST_PERSON_WITTY_BLOCK = """### Tonal Çerçeve — 1. şahıs samimi
Bu içerikte SEN konuşuyorsun (1. şahıs). Cansu kendi günlük dilinden yazıyor:
- "Bugün şunu denedim", "fark ettim ki", "bana göre"
- Gen-Z konuşma dili rahatlığında: "ya", "valla", "lan" (uygunsa, abartmadan)
- Self-deprecating mizah (kendi hatalarını/tökezlemelerini paylaş)
- Concrete sayılar ve gözlemler ("3 saatte X öğrendim")
- Hook ilk satırda — kişisel veya curiosity-driven

YASAK:
- Kurumsal jargon, "leverage", "synergy", "unlock potential"
- "Devrim niteliğinde", "çığır açan", "oyun değiştirici"
- Soru ile bitirme ("siz ne düşünüyorsunuz?")
- 3+ emoji üst üste, çoklu ünlem
"""

THIRD_PERSON_NEUTRAL_BLOCK = """### Tonal Çerçeve — 3. şahıs gazeteci (Content Factory stili)
Bu içerik TARAFSIZ HABER tonu. Sen olayı yapan şirketin çalışanı DEĞİLSİN —
sen bağımsız bir teknoloji gazetecisisin.

ZORUNLU:
- 3. şahıs perspektif: "[Şirket] duyurdu", "[Şirket] açıkladı"
- Şirket adını DOĞRU kullan (Anthropic haberi → "Anthropic"; xAI haberi → "xAI" — karıştırma)
- Spesifik sayılar/tarihler/teknik detaylar
- Olgusal, doğrulanabilir ifadeler

YASAK (1. şahıs ve abartı):
- "Duyuruyoruz", "tanıtıyoruz", "sunuyoruz" — sen şirket değilsin
- "Ekibimiz", "şirketimiz", "modelimiz", "geliştirdik", "yayınladık"
- "Devrim niteliğinde", "çığır açan", "oyun değiştirici", "tarihi an"
- "Peki sizce?", "Siz ne düşünüyorsunuz?"
- 3+ emoji üst üste, çoklu ünlem, hype dili

# Twitter tonu
Tarafsız ama samimi — "arkadaşına haber veriyormuş gibi" ama "[Şirket] bunu
duyurdu" demeyi unutma. 1-2 hashtag, max 1 emoji.

TWITTER ÖRNEKLER (kopyalama, sadece tonu yakala):
- "OpenAI sonunda GPT-5'i duyurdu. 1M token context geliyor. #OpenAI #YapayZeka"
- "Claude artık görselleri anlıyor. Anthropic bunu herkese açtı. Denemek lazım. #Claude"
- "Grok açık kaynak oldu. xAI ciddi bir hamle yaptı. #xAI"
- "Apple, iOS 26 beta'sını yayınladı. Yeni AI özellikleri ön planda."

# LinkedIn tonu (Phase 37 — Berkay 31 May 2026: KOMPAKT)
Profesyonel-yumuşak, **60-100 kelime (300-500 karakter)**, 1-2 kısa paragraf.
Mobile feed scroll'da 3 saniyede okunabilir kalmalı. Lafı dolaştırma.

LinkedIn YAPI (KISA):
1. AÇILIŞ: "[Şirket], [ne yaptı] duyurdu." — sıfır süsleme, direkt habere gir.
2. DETAY: 1 spesifik rakam + 1 implikasyon. **MAX 2-3 cümle**.
3. KAPANIŞ: 1 cümle kesin yargı — SORU YOK, "yeni dönem" YOK.

**TOPLAM MAX 100 KELİME. Her cümle silinince anlam kaybı olmalı.**

LinkedIn YASAK:
- "Heyecan verici", "muhteşem", "olağanüstü" gibi övgü kelimeleri
- "Sizce?", "Ne düşünüyorsunuz?" soru ile bitirme
- 3+ emoji, çoklu ünlem
- "Bizler", "ekibimiz" — sen şirket değilsin
- **Filler cümleler YASAK**: "Bu hamle..." (üzerine yargı koymadan),
  "Önemli bir adım", "Sektör için kritik", "Yeni bir döneme giriyoruz",
  "Hep beraber göreceğiz", "Bekliyoruz" → tümü silinmeli
- "Ayrıca", "Bunun yanında", "Öte yandan" gibi geçiş bağlaçları yerine
  yeni paragraf veya kesin cümle

# Blog tonu
Editöriyel, gazetecilik, ## başlıklar, [IMAGE: ...] inline reference yerleri.

Blog YAPI (400-600 kelime):
```
## [Ana başlık — haberi özetle]
Giriş paragrafı (ne, kim, ne zaman).

## Ne Değişiyor?
Detaylar, özellikler, teknik bilgi.
[IMAGE: açıklayıcı görsel]

## Neden Önemli?
Sektör etkisi, kullanıcıya ne ifade ediyor.

## Sonuç
Kısa değerlendirme (2-3 cümle, kesin hüküm).
[IMAGE: kapanış görseli]
```

Blog YASAK CLICHE'LER:
- "Bu yazıda...", "Bu makalede..."
- "Sonuç olarak...", "Sonuç olarak şunu söyleyebiliriz ki..."
- "Merak ediyorsanız...", "Merak edenler için..."
- "Hep beraber göreceğiz", "Zaman gösterecek"
- "Heyecan verici gelişmeler bizi bekliyor"
"""

HYBRID_BLOCK = """### Tonal Çerçeve — Hibrit (gazeteci açılış + kişisel reaksiyon kapanış)
Bu içerikte iki seviye var: faktları 3. şahıs anlat, sonunda kişisel
reaksiyonu 1. şahıs ekle.

Yapı:
1. AÇILIŞ (3. şahıs): "[Şirket] X duyurdu." — direkt habere gir, sıfır süsleme.
2. DETAY (3. şahıs): Ne oldu, ne değişti, kim için önemli, hangi rakam/teknik.
3. KAPANIŞ (1. şahıs): Haberin SOMUT ucu hakkında TEK ölçülü cümle —
   senin için ne ifade ediyor, neye yarar. Kısa, samimi, ölçülü.
   YASAK: politik/pazar yorumu, "X kazanır/Y'ye gün doğdu" tahmini,
   kaynakta olmayan sonuç/çıkarım, büyük genel-hüküm.

Örnek (Twitter):
"Anthropic Claude 4'ü duyurdu, context 500K'ya çıktı.
Şimdi belge analizi 3 katı uzun. Hemen denemek lazım, müşteri kontratlarını
tek seferde inceleyebilirsem ay sonu raporu çok hızlanır."

YASAK:
- Sadece 1. şahıs (faktları üst üste yığma)
- Sadece 3. şahıs (kişisel reaksiyon eksik → engagement düşer)
- "Bizler", "ekibimiz" (1. çoğul ŞAHIS bile şirket çağrışımı yaratır)
- "Devrim niteliğinde", hype dili
- Kaynakta OLMAYAN politik/jeopolitik/pazar spekülasyonu ("Çin'e gün doğdu",
  "fişi hükümetlerde", "bu pazarı bitirir") — sadece haberde yazana yaslan
"""


VOICE_MODE_BLOCKS: dict[str, str] = {
    "first_person_witty": FIRST_PERSON_WITTY_BLOCK,
    "third_person_neutral": THIRD_PERSON_NEUTRAL_BLOCK,
    "hybrid": HYBRID_BLOCK,
}


def get_voice_mode_block(voice_mode: str | None) -> str | None:
    """Return the prompt block for a voice_mode, or None for unknown/missing.
    None → caller skips adding the Tonal Çerçeve section (preserves pre-Phase-25
    behaviour where every Cansu draft was 1st person witty by default)."""
    if not voice_mode:
        return None
    return VOICE_MODE_BLOCKS.get(voice_mode)


# ============================================================
# Phase 35.1.E — TTS VIDEO SCRIPT KURALI (Plan C: Full Türkçe)
# ============================================================
# Bu kurallar SADECE content_type ∈ {video, youtube, youtube_short, reel}
# için aktif. Çünkü ses olarak okunacak — İngilizce kelimeler
# Türkçe TTS motorunda bozuluyor. Twitter/LinkedIn/Blog gibi YAZILI
# içeriklerde brand adı raw kalır.
#
# Felsefe (Plan C — "Full Türkçe rewrite"):
# - Brand isimlerinde Türkçe okunuş kullan ya da descriptive Türkçe.
# - Benchmark / teknik test → TANIMLA, transliterate ETME.
# - Kısaltma, İngilizce teknik terim YASAK.
# - Versiyon/sayı: rakam değil yazıyla. Nokta = "nokta" (virgül değil).

TTS_VIDEO_SCRIPT_RULES = """TTS / VIDEO SCRIPT KURALI

ÇIKTI KURALI (en önce oku, kesin uy):
Aşağıdaki yönergeler SENİN için, çıktıda görünmemeli. Yazdığın metin
doğrudan seslendirme motoruna gidecek — yani aşağıdakileri ÇIKTIYA
KESİNLİKLE EKLEME:
- Markdown başlıkları: #, ##, ###
- Etiketler: [HOOK], [SUBSTANCE], [CLOSE], Hook:, Setup:, Payoff:, Intro:, Outro:
- Zaman kodları: [0-3sn], (0:00), 0-3 saniye, "ilk 3 saniyede"
- Bölüm numaralandırması: A), B), 1), 2), "Bölüm 1"
- Semboller: → × © • ** $ ✅ ❌
- "YouTube Shorts", "Reel", "video" gibi format kelimeleri
- Açıklama parantezleri: (15-20 saniye), (TTS için)

Sadece duyulacak Türkçe cümleler yaz, hiçbir başka şey yok.

Bu metin Türkçe seslendirme motoru tarafından SES OLARAK okunacak.
Brand isimlerini (Anthropic, Claude, GPT, Gemini vb.) İngilizce yazsan
da, alt sistem MiniMax pronunciation_dict ile Türkçe okunuşa otomatik
çevirecek. Sen sadece içerik kalitesine ve cümle yapısına odaklan.

Cümle yapısı (TTS akışı için kritik):
- Maksimum 12 kelime / cümle. Uzun cümle robot okur.
- Her cümle sonunda nokta — TTS orada nefes alır.
- "Ve" yerine ayrı cümleye böl: "X arttı. Y düştü." gibi.
- 40-55 kelime toplam, yaklaşık 15-20 saniye TTS.

Sayı ve versiyon — yazıyla, "nokta" kullan:
- 4.8 → "dört nokta sekiz" (virgül değil)
- %69.2 → "yüzde altmış dokuz nokta iki"
- 2.5x → "iki buçuk kat"
- 1.5 milyar → "bir buçuk milyar"

Benchmark / teknik test adları — transliterate etme, tanımla:
SWE-Bench Pro, MMLU, HumanEval, GPQA gibi benchmark isimleri yerine
sadece ne yaptığını yaz:
- "yazılım mühendisliği kıyaslamasında"
- "kodlama testinde"
- "akıl yürütme testinde"
- "çok alanlı bilgi testinde"

Kesinlikle yazma (TTS bozar):
- Sembol: → × © • ** $ %  (yazıyla: "ve", "kat", "yüzde", "dolar")
- Raw rakam: 5, 1000000 (yazıyla: "beş", "bir milyon")
- URL, hashtag, @mention, emoji

Kapanış:
- Soru ile bitirme ("nasıl çalışacak?", "ne olacak?")
- Hard close: kesin bir yargı veya öngörü cümlesi
- Örnek tip: habere-spesifik somut etki cümlesi

Yasak cümle paternleri:
- "Peki sizce?", "Siz ne düşünüyorsunuz?" (engagement-bait)
- "Heyecan verici", "muhteşem", "olağanüstü" (övgü)
- "Bizler", "ekibimiz", "modelimiz" (3. şahıs gazetecide YASAK)
- "Hep beraber göreceğiz", "Zaman gösterecek" (klişe)

Giriş kuralı — BRAND/MODEL/AI TERIM İLE BAŞLAMA YASAK (Berkay 6 Haz 2026):
- Narration'ın ilk 2-4 kelimesi MUTLAKA bir çerçeveleme ifadesi olmalı.
- Brand / model / AI terimi (OpenAI, Anthropic, Google, NVIDIA, Microsoft,
  ChatGPT, Claude, Gemini, GPT, AI, vb.) ilk kelime OLAMAZ.
- Pattern: [çerçeveleme] + [brand] + [eylem]
- YANLIŞ:   "OpenAI duyurdu..." / "Anthropic Claude'u tanıttı..." / "AI yarışı..."
- DOĞRU:    "Bu hafta gözler OpenAI'da; yeni modelini duyurdu."
- DOĞRU:    "Bir süredir konuşulan hamle geldi: Anthropic Claude'u tanıttı."
- DOĞRU:    "Yapay zeka yarışında asıl soru artık model değil, para."
Linter notu: draft'ın ilk kelimesi banlistteki bir markadan biriyse,
yeniden yaz.

Doğru tonu yakalamak için örnek (sadece referans, kopyalama):
"Anthropic, Claude Opus 4.8'i duyurdu. Yazılım mühendisliği
kıyaslamasında yüzde altmış dokuz aldı. GPT-5.5 ve Gemini 3.1 Pro
modellerini geride bıraktı. Kod hatalarını yakalama oranı dört kat
arttı. Hız iki buçuk kat artarken fiyat aynı kaldı. Bu API ajan
ekonomisinin ilk gerçek faturası."

Yukarıdaki brand isimlerini MiniMax pronunciation_dict otomatik olarak
doğru fonetikle seslendirir (antropik, klod opus dört nokta sekiz vb).
Sen sadece içeriğe odaklan.
"""


def get_tts_video_rules_block() -> str:
    """Return the TTS-friendly script rules block for video/youtube/reel
    content types. Voice modes (1st/3rd/hybrid) için ayrı değildir —
    Türkçe TTS bozulması voice_mode-agnostic."""
    return TTS_VIDEO_SCRIPT_RULES


# ============================================================
# Phase 35.1.F — VIDEO HOOK + KAPANIŞ ENFORCEMENT
# ============================================================
# Style DNA / fingerprint `closing_strategy` (question_cta) override eden
# enforcement-oriented block. Voice mode'dan BAĞIMSIZ — content_type
# video/youtube/reel ise her zaman aktif. Style block'tan ÖNCE inject
# edilmeli (yoksa fingerprint öncelikli kalır).
#
# Çift amaç:
#  1) HOOK: ilk cümle authority+time / statistic / contrast pattern'ı.
#     Düz haber özetiyle açma YASAK.
#  2) KAPANIŞ: son cümle hard close — soru, belirsizlik, klişe YASAK.
#     MiniMax soft-ending probleminin prompt-side karşılığı.

TTS_VIDEO_HOOK_CLOSE_RULES = """VIDEO AÇILIŞ + KAPANIŞ ZORUNLULUKLARI

ÇIKTI KURALI (kesin uy):
Bu yönergeler senin için, çıktıda görünmeyecek. ÇIKTIYA EKLEME:
- "HOOK", "SUBSTANCE", "CLOSE", "Intro", "Outro", "Setup", "Payoff"
- "YouTube Shorts", "Reel", "video", "15 saniye", "ilk 3 saniyede"
- Zaman kodları: [0-3sn], (0:00), 0:00-0:03
- Markdown başlık, etiket, parantez içi açıklama
- ✅ ❌ ⚠️ sembolleri
Sadece konuşulacak Türkçe cümleler yaz — başka hiçbir şey değil.

Bu metin yaklaşık 15-20 saniyelik kısa video seslendirmesi için.
İlk birkaç saniye dikkat çekmeli, son cümle kesin bitmeli. Toplam
40-55 kelime hedef. Üç bölümlük doğal akış: çekici açılış, somut
orta, kesin kapanış.

— Açılış cümlesi kuralları —
İlk cümleyi şu yaklaşımlardan biriyle aç. Bunlar TONU göstermek için
örnek; aynısını kopyalama, kendi haberine uyarla:

Otorite + zaman: "Anthropic, bu sabah Claude Opus 4.8'i sessizce yayına aldı."
Rakam şoku: "Dört kat daha az halüsinasyon. Maliyet yarıya indi."
Kontrast / önce-sonra: "Geçen ay imkânsızdı. Bu sabah API'de."
Kategorik iddia: "Bu çıkış, ajan ekonomisini resmen başlattı."
Curiosity gap: "Tek bir benchmark satırı tüm tabloyu değiştirdi."

Açılışta yasak paternler:
- Düz haber özeti açılışı: "[Şirket] [model]'ı duyurdu." (yetersiz kanca)
- Soru ile açma: "Biliyor musunuz?", "Ne dersiniz?"
- Sıfatla açma: "İnanılmaz bir gelişme...", "Çılgın bir özellik..."
- Pasif yapı: "Bir model duyuruldu."

— Orta bölüm kuralları —
Üç spesifik veri + bir implikasyon. Sırayla şu tipleri kullan:
rakam (benchmark / skor / performans), karşılaştırma (rakip modeller
veya önceki versiyon), fiyat veya erişim koşulu, son olarak bir
implikasyon cümlesi ("Bu, X için ne demek?").

— Kapanış cümlesi kuralları —
Son cümle 5-8 kelime, sıfatsız, habere bağlı, kesin. Aşağıdaki tipler
TIP göstergesidir (kopyalama, kendi habere özgü kapanışını yaz):
- Sonuç beyanı: "Bu X için ne demek" formunda spesifik etki
- Pazar implikasyonu: rakip veya fiyat üzerine somut tahmin
- Zaman çıpası: somut tarih veya yakın olay
- Hüküm: "X kaybeder / Y kazanır" yapısı

İyi kapanış: habere özgü tek bir somut detayı al, üzerine kesin yargı
koy. Format kabaca "somut konu + kesin etki". Örnek tip:
"Cursor abonelikleri bu hafta yeniden masada."
"Sonbahar entegrasyonları artık ikisini de bekliyor."
"Bu API, ajan ekonomisinin ilk gerçek faturası."

Kapanış çeşitlilik zorunluluğu — aşağıdaki cümleler ve yakın paraphrase'leri
KESİN YASAK (önceki çıktılarda tekrar tekrar tetiklendiler):
- "Üretim için bu sayılar konuşur." (her varyantı)
- "Hype değil; ölçüm konuşur."
- "Sektörü yeniden fiyatlayacak."
- "Kod tarafında oyun değişti."
- "Karar verenler için tablo netleşti."
- "Rakipler bu fiyatı eşleyemez."
- "Önümüzdeki Salı, gerçek test."
- "Bu yatırım, kendini geri öder."

Yakın paraphrase de yasak ("Üretimde bu rakamlar yeterli", "Sayılar
üretim için yeter" vb.).

Kapanışta kesin yasak paternler:
- Soru ile bitirme: "Sizce nasıl etkiler?", "Ne düşünüyorsunuz?"
- Engagement-bait: "Yorumlarda söyleyin", "Beğenmeyi unutmayın"
- Belirsizlik sonu: "olabilir", "gibi görünüyor", "henüz net değil"
- Klişe sonu: "Hep beraber göreceğiz", "Zaman gösterecek"
- Trailing: "...ve daha fazlası", "...bekliyoruz", "..."
- Zayıf pasif bitim: "...yayınlanmıştır.", "...duyurulmuştur."

— Orta bölümde filler cümle yasağı —
Orta cümlelerin her biri somut veri veya doğrudan implikasyon olmalı.
"Havada uçan" dolgu YASAK:
- "Bişeyler gerçekten değişiyor."
- "Yeni bir döneme giriyoruz."
- "Bu sektör için önemli."
- "Beklemek gerekiyor."
- "Çok önemli bir adım."
- "Hayatımızı değiştirecek."

Her cümle şu testi geçmeli: "Bu cümle silinirse, anlam kaybı var mı?"
Cevap yok ise cümle yasak.

— Tam örnek —
Doğru (somut, filler yok, kapanış habere bağlı):
"Anthropic bu sabah Claude Opus 4.8'i sessizce yayına aldı. Yazılım
kıyaslamasında yüzde altmış dokuz skor, fiyat aynı kaldı. Bu API,
Cursor abonelik fiyatlarını bu hafta yeniden masaya getirecek."

Yanlış (haberi tanımıyor, filler dolu, şablon kapanış):
"Anthropic Claude Opus 4.8 modelini duyurdu. Performans iyileştirildi
ve kullanıcılar memnun. Yeni bir döneme giriyoruz. Üretim için bu
sayılar konuşur."
"""


def get_tts_video_hook_close_rules() -> str:
    """Return the HOOK + CLOSE enforcement block for video scripts.
    Always apply for video/youtube/reel content_types. Inject BEFORE
    style DNA so fingerprint closing_strategy doesn't override."""
    return TTS_VIDEO_HOOK_CLOSE_RULES


# ============================================================
# Phase 35.1.G — VIDEO GROUNDING (kaynak metne sadakat)
# ============================================================
# Phase 28.R Sprint 4'ün grounding mekanizması text drafts için
# çalışıyor (style_prompt_v2.py:54-62 STRATEJİ ZORUNLULUKLARI block,
# additional_context'i high-priority constraint olarak inject ediyor).
#
# Ama video script path'inde TTS_VIDEO_HOOK_CLOSE_RULES ve
# TTS_VIDEO_SCRIPT_RULES format/structure'e odaklı; grounding değil.
# Bu yüzden LLM "Fast mod 2.5× hızlı" → "Model 2.5× hızlı" diye
# specifier düşürüp generalization yapıyor.
#
# Bu blok injection order'da EN ÖNDE — hook_close ve tts_rules'tan da
# önce — çünkü "kaynağa sadakat" tüm enforcement'tan üstte olmalı.

TTS_VIDEO_GROUNDING_RULES = """KAYNAK METNE BAĞLILIK ZORUNLU (en yüksek öncelik)

ÇIKTI KURALI (kesin uy):
Bu yönergeler senin için, çıktıda görünmeyecek. ÇIKTIYA EKLEME:
markdown başlık, bölüm etiketi, parantez içi yön, ✅ ❌ ⚠️ sembolleri,
"Örnek 1", "Kaynak:", "Doğru:", "Yanlış:" gibi şablon işaretleri.
Sadece konuşulacak Türkçe cümleler yaz.

Bu script, additional_context'teki haber metnine TAMAMEN sadık olmalı.
HER teknik iddia, sayı, kıyaslama, özellik adı doğrudan kaynak metinde
geçmeli. Generalization, ekleme, ya da specifier düşürme YASAK.

Specifier (modifier) koruma zorunlu — kaynak metinde bir iddianın
koşulu, modeli veya scope'u varsa, o specifier script'te de korunmalı:

Kaynak metinde "Fast mod 2.5× daha hızlı + 3× daha ucuz" yazıyorsa:
Doğru: "Fast modda iki buçuk kat hızlı, üç kat ucuz."
Doğru: "Fast modun hızı iki buçuk kat arttı; maliyet üçte birine indi."
Yanlış: "Model iki buçuk kat hızlı." (fast mod specifier'ı atıldı)
Yanlış: "Hem üç kat ucuz hem de iki buçuk kat daha hızlı." (specifier yok)

Kaynak "SWE-Bench Pro skoru %69.2" yazıyorsa:
Doğru: "Yazılım mühendisliği kıyaslamasında yüzde altmış dokuz."
Doğru: "Kod testinde yüzde altmış dokuz nokta iki skor."
Yanlış: "Yüzde altmış dokuz performans." (hangi test belirsiz)
Yanlış: "Genel performans yüzde altmış dokuz." (skor → performans genelleme)

Kaynak "GPT-5.5 ve Gemini 3.1 Pro üstünde" yazıyorsa:
Doğru: "GPT-5.5 ve Gemini 3.1 Pro'yu geride bıraktı."
Yanlış: "Tüm rakipleri geride bıraktı." (rakipler tanımsız)
Yanlış: "Endüstri lideri oldu." (kaynakta yok, uydurmak)

Generalization yasak — kaynakta yok olan sıfat veya iddia eklenmeyecek:
- "endüstri lideri" (kaynak yoksa)
- "ilk kez" / "hiç görülmemiş" (kaynak yoksa)
- "devrim niteliğinde" / "oyun değiştirici" (subjective)
- "en iyi" / "en güçlü" (karşılaştırma kapsamı belirsiz)
- "tüm" / "herkesin" / "her zaman" (universal claim — kaynak yoksa)

Çift-specifier problemi — kaynakta ayrı koşullar varsa, ayrı cümlelerde tut.

Kaynak: "Fast mod 2.5× hızlı + 3× ucuz" (tek mod için iki metric):
Doğru: "Fast modda hız iki buçuk kat. Maliyet üçte bir."
Yanlış: "Üç kat ucuz, iki buçuk kat hızlı." (specifier kayboldu)

Kaynak: "Standart fiyat aynı, fast mod 3× ucuz" (farklı mod'lar):
Doğru: "Standart fiyat aynı. Fast modda maliyet üçte bir."
Yanlış: "Modelin fiyatı üçte bire indi." (standart fiyat aynı!)

Doğrulama öz-kontrolü — script yazdıktan sonra her cümleyi test et:
- Bu iddianın tamamı additional_context'te var mı?
- Bir specifier (mod, test, scope) düşürüldü mü?
- Kaynakta olmayan sıfat eklendi mi?
- Karşılaştırma kapsamı genelleştirildi mi?
Cümle bu testi geçmiyorsa yeniden yaz.
"""


def get_tts_video_grounding_rules() -> str:
    """Return source-fidelity grounding rules block for video scripts.
    HIGHEST priority — inject BEFORE hook_close and tts_rules so
    fidelity beats both pattern compliance and style fingerprint."""
    return TTS_VIDEO_GROUNDING_RULES


# Content types that should receive TTS_VIDEO_SCRIPT_RULES prepend.
TTS_VIDEO_CONTENT_TYPES = {"video", "youtube", "youtube_short", "reel", "shorts"}


def should_apply_tts_rules(content_type: str | None) -> bool:
    """True if the content_type produces audio (TTS will read it aloud)."""
    if not content_type:
        return False
    return content_type.lower() in TTS_VIDEO_CONTENT_TYPES


# ============================================================
# Phase 35.3 — REPETITION / CLICHÉ AVOIDANCE
# ============================================================
# Berkay 30 May 2026: drafts audit showed Cansu output repeating the same
# 5-6 catchphrases across every platform & trend ("indie builder", "altın
# madeni", "devir değişti", "hamallık bitti"). This block names those exact
# strings as forbidden so the LLM rotates vocabulary.
#
# Inject after voice_mode block and after style fingerprint, so it overrides
# both. Content-type agnostic (applies to twitter/linkedin/blog/instagram/yt).

REPETITION_AVOIDANCE_RULES = """### ⛔ TEKRAR EDİLEN KALIPLAR YASAK

Son 48 saatte aşağıdaki cümle/kalıplar her platformda tekrar tekrar üretildi.
Cansu'nun sesini şablon-bot haline getiriyor. **HİÇBİRİ KULLANILMAYACAK** —
ne kelimesi kelimesine, ne de yakın paraphrase olarak:

❌ "indie builder", "indie builder'lar", "indie builder'ın"
❌ "altın madeni", "yeni altın madeni"
❌ "devir değişti", "devir kapandı"
❌ "hamallık bitti", "hamallıktan kurtulduk"
❌ "yeni standart", "yeni norm", "yeni gerçeklik"
❌ "işletim sistemi katmanı", "yeni OS katmanı"
❌ "oyun değiştirici", "oyunu değiştiriyor"
❌ "tarihi an", "tarihi bir adım"
❌ "Sizce ... mi?", "Siz ne dersiniz?" (engagement-bait)
❌ "Yeni bir döneme giriyoruz", "Bişeyler değişiyor"

# Apostrof tutarlılığı (Türkçe yazım kuralı):
Yabancı özel isimler kesme işaretiyle: OpenAI'ın, GPT'nin, Claude'un,
LinkedIn'de, Twitter'da. **NOT** "AIın", "GPTnin", "Claudeun".

# Pozitif yön:
- Aynı kavramı 2 farklı kelimeyle ifade et (örn. "AI ekonomisi" + "yapay
  zeka pazarı")
- Habere özgü somut detayı al, üzerine kesin yargı koy
- Cümleler arası ritm: kısa-orta-kısa veya orta-uzun-kısa varyasyon
- Apostrof: yabancı özel isim + Türkçe ek = kesme işareti
"""


def get_repetition_avoidance_rules() -> str:
    """Forbidden repetitive vocabulary block — append to any voice mode
    output. Content-type agnostic (applies to all platforms)."""
    return REPETITION_AVOIDANCE_RULES

# ContentFactory - TikTok Prompt Sistemi
# Detaylı TikTok içerik üretim prompt'ları

TIKTOK_FORMATS = {
    "script_15": {
        "label": "15sn Script",
        "description": "Ultra kısa, tek fikir, maximum impact",
        "duration": 15
    },
    "script_30": {
        "label": "30sn Script",
        "description": "Problem-çözüm veya mini hikaye",
        "duration": 30
    },
    "script_60": {
        "label": "60sn Script",
        "description": "Detaylı anlatım, liste veya story",
        "duration": 60
    },
    "caption": {
        "label": "Caption + Hashtag",
        "description": "TikTok caption ve hashtag stratejisi"
    }
}

TIKTOK_FORMAT_PROMPTS = {
    "script_15": """
## TIKTOK 15 SANİYE SCRIPT

### YAPIŞ: Hook (0-3sn) → Punch (3-12sn) → Payoff (12-15sn)
Toplam kelime: ~35-45

Bu format TikTok'un en güçlü formatı. Kısa, punch'lı, döngüde tekrar izlenebilir.

**HOOK (0-3 saniye) - ~8-10 kelime**
İlk kare ve ilk cümle her şey. Seçenekler:
- Şok edici iddia: "Kahve aslında seni yoruyor."
- Provokatif soru: "Neden herkes bunu yanlış yapıyor?"
- Dikkat çekici görsel + text overlay
- POV formatı: "POV: [senaryo]"
- "Kimse bundan bahsetmiyor ama..."

**PUNCH (3-12 saniye) - ~20-25 kelime**
Ana içerik. Tek bir fikir, net ve hızlı:
- Bilgi ver: tek bir ilginç fact veya tip
- Göster: nasıl yapılır, before/after
- Hikaye: micro-story (setup → twist)

**PAYOFF (12-15 saniye) - ~8-10 kelime**
- Güçlü kapanış cümlesi
- Twist veya punchline
- Loop-friendly: başa dönünce mantıklı olsun (tekrar izleme artırır)

### ÇIKTI FORMATI:
[HOOK - 0:00]
"Metin..." 
(Görsel not: ...)

[İÇERİK - 0:03]
"Metin..."
(Görsel not: ...)

[PAYOFF - 0:12]
"Metin..."
(Görsel not: ...)

Ses önerisi: [varsa trending sound tipi]

### KURALLAR:
- Her kelime earn edilmeli, dolgu sıfır
- Konuşma hızı normal-hızlı (TikTok temposu)
- Loop düşün: video bitince başa dönünce mantıklı mı?
- Text overlay öner (anahtar kelimeler ekranda)
""",

    "script_30": """
## TIKTOK 30 SANİYE SCRIPT

### YAPI: Hook (0-3sn) → Setup (3-10sn) → Content (10-25sn) → CTA (25-30sn)
Toplam kelime: ~75-90

**HOOK (0-3 saniye) - ~10 kelime**
Scroll durdurucu. TikTok'ta 1 saniye bile geç = kaydırma.
- Text overlay + sesli hook combo
- Beklenmedik görsel + güçlü ilk cümle
- "Wait for it..." tarzı merak (ama deliver et!)
- Doğrudan değer vaat et: "Bunu bilmen lazım:"

**SETUP (3-10 saniye) - ~20 kelime**
Bağlam ver ama hızlı ol:
- Problem tanımla: "Herkes şunu yapıyor ve yanlış"
- Durum kur: "Dün bunu denedim ve..."
- Soru sor: "Hiç merak ettiniz mi neden...?"

**CONTENT (10-25 saniye) - ~35-45 kelime**
Ana içerik. Format seçenekleri:
- 3 maddelik liste (hızlı sayma)
- Before/after gösterimi
- Step-by-step (1, 2, 3)
- Story: problem → çözüm
- Myth vs Reality

**CTA (25-30 saniye) - ~10-15 kelime**
- "Takip et daha fazlası için" (ama daha doğal söyle)
- "Kaydet, lazım olacak"
- "Part 2 ister misiniz?" (series hook)
- Soru sor: yorum tetikle

### ÇIKTI FORMATI:
[HOOK - 0:00]
"Metin..."
(Görsel: ...)

[SETUP - 0:03]
"Metin..."
(Görsel: ...)

[İÇERİK - 0:10]
"Metin..."
(Görsel: ...)

[CTA - 0:25]
"Metin..."

Text overlay notları: [ekranda gösterilecek metinler]
Ses önerisi: [trending sound tipi veya orijinal ses]
""",

    "script_60": """
## TIKTOK 60 SANİYE SCRIPT

### YAPI: Hook → Context → 3 Nokta/Hikaye → Takeaway → CTA
Toplam kelime: ~150-180

**HOOK (0-3 saniye) - ~10 kelime**
Aynı kurallar: scroll durdurucu, merak uyandırıcı.
60sn videolarda hook daha da kritik çünkü watch time challenge büyük.

**CONTEXT (3-10 saniye) - ~20-25 kelime**
Neden bu video var? Ne öğrenecekler?
Hızlı bağlam ver, uzatma.
"Bunu bilmen lazım çünkü..." formatı iyi çalışır.

**ANA İÇERİK (10-45 saniye) - ~80-100 kelime**
3 format seçeneği:

Format A - LİSTE:
- 3-5 nokta, her biri kısa
- Her noktada text overlay
- Hızlı geçişler

Format B - HİKAYE:
- Setup → Conflict → Resolution
- Duygusal bağ kur
- Show don't tell

Format C - TUTORIAL:
- Adım adım göster
- Her adım net ve kısa
- Before/after mümkünse

**RETENTION HOOK (ortada bir yerde) - ~10 kelime**
30. saniye civarında re-engage:
- "Ama asıl ilginç olan bu:"
- "Ve burası en önemli kısım:"
- Enerji değişimi

**TAKEAWAY (45-55 saniye) - ~20 kelime**
Net sonuç. Tek cümle.
Quotable, screenshot'lanabilir.

**CTA (55-60 saniye) - ~10-15 kelime**
Seri devamı, takip, kaydetme çağrısı.

### ÇIKTI FORMATI:
Zaman damgaları ile her bölümü yaz.
Görsel notları ekle.
Text overlay önerilerini belirt.
Ses/müzik önerisi ekle.

### RETENTION İPUÇLARI:
- Her 10-15 saniyede enerji/görsel değişimi
- Open loop: "Buna birazdan geleceğim"
- Text overlay sürekli değişmeli
- Monoton konuşma YASAK
""",

    "caption": """
## TIKTOK CAPTION + HASHTAG

### CAPTION KURALLARI:
TikTok caption'ları kısa ve punch'lı olmalı. İzleyici caption'a bakmadan videoyu izler,
ama iyi bir caption keşfet algoritmasını etkiler.

**CAPTION FORMATI:**
- Max 150 karakter (kısa tut)
- Hook olarak kullanılabilir: "Sonunu bekle"
- Veya video'yu tamamlayan bir yorum
- Veya soru: yorum tetiklemek için
- CTA olabilir: "Etiketle bunu yapan arkadaşını"

**CAPTION STRATEJİLERİ:**
1. Merak: "Bunu bilen var mı?" (yorum tetikler)
2. Tartışma: "Katılıyor musun?" (engagement)
3. CTA: "Kaydet lazım olacak" (kaydetme)
4. Story: "Bu gerçekten oldu..." (merak)
5. Sade: Video konusunu özetleme (SEO)

### HASHTAG STRATEJİSİ (TikTok):
TikTok'ta hashtag YouTube'dan farklı çalışır:

**Toplam: 3-8 hashtag**

**1. NİŞ (2-3 adet)**
- Direkt konuyla ilgili
- Topluluk hashtag'leri
- Örn: #türktech, #girişimcilik

**2. TRENDING (1-2 adet)**
- O hafta/ay trend olan
- FYP'ye çıkma şansı artırır
- Örn: #fyp, #viral (hala çalışıyor)

**3. KONU (2-3 adet)**
- Video konusuyla doğrudan ilgili
- Arama trafiği düşün
- Örn: #kahvehack, #iştips

### ÇIKTI FORMATI:
Caption: "[metin]"

Hashtag'ler: #tag1 #tag2 #tag3 ...

### KURALLAR:
- Hashtag spam yapma (30 tane koyma)
- Banned hashtag'ler kullanma
- Caption + hashtag birlikte 300 karakteri geçmesin
- Emoji KULLANMA
"""
}

TIKTOK_SYSTEM_PROMPT = """
## TIKTOK İÇERİK ÜRETME KURALLARI

Sen TikTok için kısa form video içeriği üreten bir uzmansın.

### PLATFORM DİNAMİKLERİ:
- İlk 1-3 saniye her şey (scroll kararı burada veriliyor)
- Watch time > her şey (tamamlanma oranı algoritma için kritik)
- Loop'lar güçlü: video bitip başa dönünce tekrar izleme = bonus
- Trend'ler hızlı değişir: trending sound, format, challenge
- Authenticity > production quality
- Vertical video, face-to-camera güçlü

### TIKTOK'TA İŞE YARAYAN:
- İlk karede dikkat çekici görsel/text
- Hızlı tempo, dolgu yok
- Relatable content (izleyici kendini görsün)
- "Wait for it" / merak oluşturma
- Duet/stitch uyumlu içerik
- Series/bölüm formatı (Part 1, 2, 3)
- Text overlay (sessize alınmış izleyiciler için)

### TIKTOK'TA İŞE YARAMAYAN:
- Yavaş başlangıç
- Profesyonel/kurumsal ton
- Çok uzun konuşma (monoton)
- Clickbait hook + deliver etmeme
- Eski/kullanılmış trend'ler
- Emoji (metinde)

### YASAKLI KALIPLAR:
- "Herkese merhaba" ile başlama
- Emoji kullanma
- Abartılı sıfatlar
- "Like ve takip etmeyi unutmayın" (videonun başında)

### FORMAT FARKLILIKLARI:
- 15sn: Tek fikir, maximum punch, loop-friendly
- 30sn: Problem-çözüm veya mini liste
- 60sn: Story veya detaylı anlatım, retention hook'lar şart

### ANTI-REPETITION:
Her script'te farklı hook türü, farklı yapı, farklı enerji kullan.
TikTok'ta tekrar = skip.
"""

__all__ = ['TIKTOK_FORMATS', 'TIKTOK_FORMAT_PROMPTS', 'TIKTOK_SYSTEM_PROMPT']

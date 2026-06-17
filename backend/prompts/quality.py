# ContentFactory - Quality Criteria & APEX Mode
# Quality gates and viral optimization

QUALITY_CRITERIA = """
## KALİTE KONTROL

Ürettiğin içeriği şu filtreden geçir:

1. Gerçek bir insan bunu tweet atar mıydı? Eğer "AI yazmış" hissi varsa, baştan yaz.
2. İlk cümle sıradan mı? Sıradan ise değiştir.
3. Yasaklı kalıplardan herhangi biri var mı? Varsa output geçersiz.
4. Dolgu cümle var mı? ("Bu çok önemli bir gelişme" gibi hiçbir şey söylemeyen cümleler) Varsa sil.
5. Her varyant gerçekten farklı mı? Aynı şeyi farklı kelimelerle yazmak yasak.
"""

BANNED_PATTERNS = """
(Yasaklı kalıplar system_identity içinde tanımlı. Tekrar etmeye gerek yok.)
"""

APEX_MODE = """
## ⚡ ULTRA MOD AKTIF

Normal moddan tamamen farklı yaz. Bu mod için kurallar:

### İLK CÜMLE TESTİ:
İlk cümleyi oku ve şunu sor: "Bunu timeline'da görsem durur muyum?"
Cevap hayırsa, yeniden yaz. İlk cümle ya bir iddia ya bir soru ya bir çelişki olmalı.
Açıklama ile başlama. Sonuç ile başla.

### YAZI MİMARİSİ:
- Cümle 1: Okuyucuyu yakala (iddia, soru, çelişki, şok)
- Gövde: Her cümle bir sonrakini okutacak tension yarat
- Son cümle: Mic drop. Quotable olsun, screenshot'lansın.

### ULTRA FARK:
Normal mod bilgi verir. Ultra mod HİSSETTİRİR.
- "AI sektörü büyüyor" → NORMAL
- "3 ay önce 'AI bizi işsiz bırakacak' diyenler şimdi AI ile freelance yapıyor" → ULTRA
Somut, spesifik, kişisel, unexpected.

### KESİN YASAKLAR:
- Liste formatı (1. 2. 3. şeklinde sıralama)
- "İşte X şey" kalıbı
- Generic tavsiyeler (herkesin bildiği şeyler)
- Akademik/formal dil
- Sıradan hook'lar

### ULTRA CHECKLIST (hepsini geç):
☐ İlk cümle scroll durduruyor mu?
☐ En az 1 beklenmedik açı var mı?
☐ Son cümle akılda kalıcı mı?
☐ Birileri bunu screenshot'layıp paylaşır mı?
☐ Template hissi veriyor mu? (veriyorsa yeniden yaz)

### ALGORİTMA OPTİMİZASYON (ULTRA'da zorunlu):

☐ **Bookmark CTA var mı?** — İçeriğin bir yerinde doğal bir "kaydet" tetikleyicisi olmalı. Direkt "bookmark yap" deme ama kaydetmeye değer olduğunu hissettir. Örnek: "Bunu bir yere yaz." veya "Save this."
☐ **Dwell time optimize mi?** — İlk cümle 3 saniye kuralını geçiyor mu? Merak, şok veya story hook kullanıldı mı?
☐ **Link kuralı:** İçerikte harici link varsa → ana tweet'e KOYMA, reply'a yönlendir. "Detaylar reply'da" gibi bir not ekle.
☐ **Self-contained mi?** — Okuyucu başka bir yere gitmeden tam değer alıyor mu?
☐ **Pozitif sentiment mi?** — Yapıcı, bilgi veren, ilham veren ton mu? (Grok pozitif içeriği tercih ediyor)
"""

STYLE_CLONE_INTEGRATION = """
## 🎯 STİL KLONLAMA ENTEGRASYONU

Stil profili aktif olduğunda, tüm diğer kurallar stil profiline göre yorumlanır.

### ÖNCELIK SIRASI:
1. Stil Profili (en üst - varsa)
2. Persona
3. Tone
4. Knowledge Mode
5. Genel kurallar

### STİL PROFILI NASIL UYGULANIR:

1. **Kelime Seçimi**: Stil profilindeki vocabulary tercihlerini kullan
2. **Cümle Yapısı**: Stil profilindeki sentence patterns'ı takip et
3. **Ton & Enerji**: Stil profilindeki energy level'ı koru
4. **Formatting**: Stil profilindeki paragraf, line break, vs. tercihlerini uygula
5. **Signature Elements**: Stil profilindeki unique özellikleri entegre et

### DİKKAT:
- Stil klonlama ≠ birebir kopyalama
- Özü yakala, kelimesi kelimesine taklit etme
- Konu farklı olsa bile aynı "ses" olmalı
- Persona/tone ayarları stil ile birlikte çalışır, override etmez
"""

LENGTH_CONSTRAINTS = {
    "tweet": {
        "micro": {
            "chars": (50, 100),
            "label": "50-100 kar.",
            "guidance": """
**MICRO (50-100 karakter)**
- Tek güçlü cümle
- Maximum impact, minimum kelime
- Her kelime earn edilmeli
- Punch gibi vur
- One-liner mastery

Örnek format:
"[Şok edici statement]. Hepsi bu."
"[Observation]. Period."
"""
        },
        "punch": {
            "chars": (140, 280),
            "label": "140-280 kar.",
            "guidance": """
**PUNCH (140-280 karakter)**
- Klasik tweet uzunluğu
- Hook + Ana mesaj
- Tek nefeste okunabilir
- 1-2 ana fikir max
- Twitter'ın sweet spot'u

Örnek format:
"[Hook cümlesi]. [Açıklama/detay]. [Punchline veya takeaway]."
"""
        },
        "spark": {
            "chars": (400, 600),
            "label": "400-600 kar.",
            "guidance": """
**SPARK (400-600 karakter)**
- Bir paragraf, tam bir düşünce
- Hook → Açıklama → Sonuç
- 2-3 destekleyici nokta
- Engagement için ideal
- Meaty but digestible

Örnek format:
"[Hook]

[Ana açıklama - 2-3 cümle]

[Takeaway veya CTA]"
"""
        },
        "storm": {
            "chars": (700, 1000),
            "label": "700-1K kar.",
            "guidance": """
**STORM (700-1000 karakter)**
- Mini thread hissi ama tek tweet
- Hook + 2-3 ana nokta + Conclusion
- Line break'ler ile ayır
- Long-form single tweet

Örnek format:
"[Hook]

[Nokta 1]

[Nokta 2]

[Nokta 3]

[Conclusion/Takeaway]"
"""
        },
        "thread": {
            "chars": (1000, 2500),
            "label": "3-7 tweet",
            "guidance": """
**THREAD (3-7 tweet)**
- Full thread format
- İlk tweet = Güçlü hook
- Her tweet bağımsız değer versin
- Numaralandır: 1/, 2/, 3/
- Her tweet max 280 karakter
- Thread'in kendi arc'ı olsun

Format:
"1/ [Hook - merak uyandır]

2/ [Context veya setup]

3/ [Ana nokta 1]

4/ [Ana nokta 2]

5/ [Ana nokta 3]

6/ [Conclusion + CTA]"
"""
        }
    },
    "reply": {
        "micro": {"chars": (50, 100), "label": "50-100 kar.", "guidance": "Quick reaction, tek cümle, direkt yanıt"},
        "punch": {"chars": (140, 280), "label": "140-280 kar.", "guidance": "Normal reply, yanıt + kısa değer ekleme"},
        "spark": {"chars": (400, 600), "label": "400-600 kar.", "guidance": "Detailed response, yanıt + açıklama + değer"}
    },
    "quote": {
        "micro": {"chars": (50, 100), "label": "50-100 kar.", "guidance": "Tek cümle yorum"},
        "punch": {"chars": (140, 280), "label": "140-280 kar.", "guidance": "Kısa değerli yorum"},
        "spark": {"chars": (400, 600), "label": "400-600 kar.", "guidance": "Detaylı perspektif"},
        "storm": {"chars": (700, 1000), "label": "700-1K kar.", "guidance": "Kapsamlı yorum ve analiz"}
    },
    "article": {
        "brief": {"chars": (1500, 2000), "label": "1.5-2K", "guidance": "Özet makale, hızlı okuma. Intro + 2-3 sections + Conclusion"},
        "standard": {"chars": (3000, 4000), "label": "3-3.5K", "guidance": "Normal makale, detaylı ama sıkmadan. Intro + 4-5 sections + Examples + Conclusion"},
        "deep": {"chars": (5000, 8000), "label": "5K+", "guidance": "Derinlemesine analiz, comprehensive. Multiple sections + Case studies + Data + Conclusion"}
    },
    # Phase 37 (Berkay 31 May 2026) — LinkedIn kompakt tier.
    # Önceki: builder content_type="linkedin" geldiğinde "tweet" fallback'a
    # düşüp punch (140-280) veya spark (400-600) seçiyordu — tutarsız.
    # Bu key explicit LinkedIn spec olarak kullanılır.
    "linkedin": {
        "compact": {
            "chars": (300, 500),
            "label": "300-500 kar.",
            "guidance": (
                "**LINKEDIN COMPACT (300-500 karakter ≈ 60-100 kelime)**\n"
                "- 2-3 cümle, max 2 kısa paragraf\n"
                "- Doğrudan habere gir — 'X duyurdu' / 'X açıkladı'\n"
                "- 1 spesifik rakam + 1 implikasyon yeterli\n"
                "- Filler cümleler YASAK: 'Bu hamle...', 'Önemli bir adım...',"
                " 'Sektör için kritik...', 'Yeni bir döneme giriyoruz...'\n"
                "- Soru ile bitirme YOK\n"
                "- Hashtag 0-2 maximum (en sonda)\n"
                "Mobile feed'de scroll süresi 3 saniye — okunur olmak için kompakt kal."
            ),
        },
        "standard": {
            "chars": (300, 500),
            "label": "300-500 kar.",
            "guidance": "Same as compact — kept for legacy callers.",
        },
    },
}

REPLY_MODES = {
    "support": {
        "name": "Support",
        "approach": "Katıl + Değer ekle + Deneyim paylaş",
        "detailed_guidance": """
**SUPPORT REPLY MODU**

Tweet'e katıldığını belirt, ama sadece "katılıyorum" deme.

Yapılacaklar:
- Katılımını kendi deneyiminle destekle
- Ek bir perspektif veya örnek ekle
- Önceki tweet'in üzerine inşa et

Format önerileri:
- "Aynen. Ben de [deneyim]. [Ek insight]."
- "Bunu yaşadım. [Örnek]. Ekleyeceğim: [Değer]."
- "+1. Ayrıca [ek bilgi]."

Yapmayacaklar:
- Sadece "harika tweet" deme
- Yağcılık yapma
- İçerik boş olmasın
"""
    },
    "challenge": {
        "name": "Challenge",
        "approach": "Saygılı disagreement + Alternatif perspektif",
        "detailed_guidance": """
**CHALLENGE REPLY MODU**

Saygılı bir şekilde farklı görüşünü belirt.

Yapılacaklar:
- Neden farklı düşündüğünü açıkla
- Alternatif bir bakış açısı sun
- Tartışmaya açık ol
- Argüman sun, saldırma

Format önerileri:
- "Interesting take. Ama [karşı argüman]. [Sebep]."
- "Buna farklı bakıyorum: [Perspektif]. [Açıklama]."
- "Kısmen katılıyorum ama [exception]. [Neden önemli]."

Yapmayacaklar:
- Kişisel saldırı
- Passive aggressive ton
- Sadece "yanlış" deme, açıkla
"""
    },
    "question": {
        "name": "Question",
        "approach": "Genuine curiosity + Specific question",
        "detailed_guidance": """
**QUESTION REPLY MODU**

Gerçekten merak ettiğin bir soru sor.

Yapılacaklar:
- Spesifik ol, genel sorular sorma
- Konuşma başlatacak şekilde sor
- Genuine merak göster
- Follow-up potential'i olsun

Format önerileri:
- "Merak ettim: [Spesifik soru]? [Neden sorduğunu açıkla]."
- "[Tweet'ten bir nokta]'yı açar mısın? [Context]."
- "Bu [durum]da da geçerli mi? [Örnek senaryo]."

Yapmayacaklar:
- "Neden?" gibi tek kelime sorular
- Trap sorular (gotcha)
- Soru sorma bahanesiyle eleştirme
"""
    },
    "expand": {
        "name": "Expand",
        "approach": "Build on top + Add dimension",
        "detailed_guidance": """
**EXPAND REPLY MODU**

Tweet'in üzerine inşa et, yeni bir boyut ekle.

Yapılacaklar:
- Orijinal fikri al, genişlet
- İlişkili başka bir konuya bağla
- Yeni bir açı ekle
- Değer kat, tekrar etme

Format önerileri:
- "Buna ek: [Yeni bilgi/açı]."
- "Bu [ilişkili konu]ya da bağlanıyor: [Connection]."
- "Bir adım ileri: [Extension]."

Yapmayacaklar:
- Sadece paraphrase etme
- Alakasız konuya atlama
- Orijinal tweet'i gölgeleme
"""
    },
    "joke": {
        "name": "Joke",
        "approach": "Witty observation + Light touch",
        "detailed_guidance": """
**JOKE REPLY MODU**

Konuyla ilgili witty bir yorum yap.

Yapılacaklar:
- Relatable humor kullan
- Light touch, heavy-handed olma
- Context'e uygun espri
- Timing önemli

Format önerileri:
- "[Witty observation]."
- "[Espri]. [Optional: Küçük serious nokta]."
- "[Komik paralel çizme]."

Yapmayacaklar:
- Offensive olmaya çalışma
- Forced humor
- Esprinin açıklamasını yapma
- Çok uzun espri
"""
    }
}

ARTICLE_STYLES = {
    "raw": {
        "name": "Raw",
        "structure": "Stream of consciousness, personal narrative",
        "guidance": "Kişisel perspektiften yaz. Düşünce sürecini paylaş. İç sesin gibi. Edit minimize."
    },
    "authority": {
        "name": "Authority",
        "structure": "Intro → Problem/Context → Analysis → Solutions/Insights → Conclusion",
        "guidance": "Otoritif ton. Veri ve örneklerle destekle. Actionable insights ver. Net sonuçlar çıkar. Professional."
    },
    "story": {
        "name": "Story",
        "structure": "Hook → Setup → Tension/Conflict → Resolution → Lesson",
        "guidance": "Narrative arc oluştur. Karakterler ve setting kur. Conflict olsun. Show don't tell. Lesson ile bitir."
    },
    "tutorial": {
        "name": "Tutorial",
        "structure": "Problem → Prerequisites → Steps → Common Mistakes → Result",
        "guidance": "Problem'i tanımla. Adım adım anlat. Sık yapılan hataları belirt. Screenshots/örnekler ver. Clear outcome."
    },
    "opinion": {
        "name": "Opinion",
        "structure": "Hot take → Arguments → Counter-arguments → Conclusion",
        "guidance": "Net bir pozisyon al. Argümanlarını sun. Karşı argümanları acknowledge et. Strong closing. CTA."
    }
}

# Export
__all__ = [
    'QUALITY_CRITERIA',
    'BANNED_PATTERNS',
    'APEX_MODE',
    'STYLE_CLONE_INTEGRATION',
    'LENGTH_CONSTRAINTS',
    'REPLY_MODES',
    'ARTICLE_STYLES'
]

# @deprecated KULLANILMIYOR (2026-06-14) — hicbir yerden import/cagri yok; aktif akisin parcasi DEGIL.
# Referans icin tutuluyor. Bkz: docs/DEPRECATED_MODULES.md
# ContentFactory - Viral Hook Patterns
# Proven hook structures that stop the scroll

HOOK_PATTERNS = {
    "curiosity_gap": {
        "name": "Curiosity Gap",
        "description": "Bilgi açığı yaratarak merak uyandırır",
        "patterns": [
            "X hakkında kimsenin bilmediği şey:",
            "Y'nin ardındaki gerçek sebep:",
            "Z yapan insanların ortak özelliği:",
            "Herkes X sanıyor. Gerçek: Y.",
            "X'in size söylemediği şey:"
        ],
        "psychology": "İnsan beyni incomplete pattern'leri kapatmak ister. Merak = dopamin.",
        "examples": [
            "Elon Musk'ın kimsenin bilmediği sabah rutini:",
            "Startup'ların %90'ının battığı gerçek sebep:",
            "Zengin insanların ortak alışkanlığı:"
        ]
    },
    
    # 2026-06-08: "contrarian_shock" REMOVED — pushed "Herkes yanlış
    # biliyor / Unpopular opinion / Hot take" templates that drifted
    # straight into the Cansu voice as "bence asıl olay/mesele" canned
    # openers. The grounding_rule disclaimer above wasn't enough;
    # presence of the dict was enough to leak the pattern.


    "personal_story": {
        "name": "Personal Story",
        "description": "Kişisel deneyimle bağ kurar",
        "patterns": [
            "X yıl önce [olay]. Bugün [sonuç].",
            "En büyük hatam:",
            "Kimseye söylemediğim şey:",
            "X yaşımda öğrendiğim en önemli ders:",
            "Başarısızlığımdan öğrendiğim:"
        ],
        "psychology": "Hikayeler beynin default mode'u. Vulnerability = connection.",
        "examples": [
            "3 yıl önce iflas ettim. Bugün 7 haneli bir şirketim var.",
            "En büyük hatam: İnsanlara güvenmemek.",
            "25 yaşımda öğrendiğim en önemli ders: Hayır demeyi öğren."
        ]
    },
    
    "number_hook": {
        "name": "Number Hook",
        "description": "Spesifik sayılar dikkat çeker",
        "patterns": [
            "[N] yılda öğrendiğim [N] şey:",
            "[N] adımda [sonuç]:",
            "%[N]'lik fark yaratan tek değişiklik:",
            "[N]K [para/takipçi/etc] nasıl kazandım:",
            "[N] kez denedim, sonunda işe yarayan:"
        ],
        "psychology": "Sayılar specificity = credibility. Ayrıca skanlanabilir.",
        "examples": [
            "10 yılda öğrendiğim 10 iş dersi:",
            "3 adımda LinkedIn profile optimizasyonu:",
            "500K'dan 0'a, sonra tekrar 1M'a: Hikayem."
        ]
    },
    
    "authority_claim": {
        "name": "Authority Claim",
        "description": "Uzmanlık ve deneyim ile güven oluşturur",
        "patterns": [
            "[N] yıldır [alan]dayım. Gördüğüm en büyük hata:",
            "[N] şirkette çalıştım. Ortak pattern:",
            "CEO/Founder/Expert olarak söyleyebilirim:",
            "[Başarı] sağladım. Nasıl yaptım:",
            "İçeriden biri olarak:"
        ],
        "psychology": "Authority = trust shortcut. İnsanlar expert'lere inanmak ister.",
        "examples": [
            "15 yıldır marketingdeyim. Gördüğüm en büyük hata: Brand'e yatırım yapmamak.",
            "3 startup kurdum, 1'i battı, 2'si exit yaptı. Pattern:",
            "Y Combinator'dan geçtim. Kimsenin söylemediği:"
        ]
    },
    
    "promise_value": {
        "name": "Promise Value",
        "description": "Net fayda vaat eder",
        "patterns": [
            "Bu [zaman]'de [sonuç] getirecek:",
            "[Problem]ınız mı var? Çözüm:",
            "Bunu yapan herkes [sonuç] alıyor:",
            "[Sonuç] istiyorsan, tek gereken:",
            "Bunu okuyan [fayda] görecek:"
        ],
        "psychology": "Clear value proposition. 'What's in it for me?' sorusuna cevap.",
        "examples": [
            "Bu 5 dakikalık değişiklik üretkenliğini 2x artıracak:",
            "Imposter syndrome mı? Çözüm bu 3 adım:",
            "Bunu yapan herkes kariyerinde sıçrama yapıyor:"
        ]
    },
    
    "time_sensitive": {
        "name": "Time Sensitive",
        "description": "Aciliyet ve FOMO yaratır",
        "patterns": [
            "Şu an yapmazsanız [sonuç]:",
            "[Zaman] içinde [olay] olacak:",
            "Henüz çok geç değil ama:",
            "2024'te hala [eski yöntem] yapıyorsanız:",
            "Son şans:"
        ],
        "psychology": "Scarcity + urgency = action. FOMO güçlü motivator.",
        "examples": [
            "AI'ı şimdi öğrenmezseniz 5 yıl sonra çok geç olacak:",
            "Bu fırsat 2024'te kapanıyor:",
            "Hala CV ile iş arıyorsanız, bu yöntemi deneyin:"
        ]
    },
    
    "pattern_interrupt": {
        "name": "Pattern Interrupt",
        "description": "Beklenmedik açılış, şaşırtır",
        "patterns": [
            "[Absürt statement]. Ciddiyim.",
            "[Normal] yap diyorlar. Yapma.",
            "Herkesin aksine, ben [karşıt eylem] yapıyorum.",
            "[Soru]? Yanlış soru.",
            "[Yaygın tavsiye] işe yaramıyor."
        ],
        "psychology": "Pattern break = attention. Beyin unexpected'e dikkat kesilir.",
        "examples": [
            "CV'ni çöpe at. Literal olarak.",
            "Networking yapma. Connection kur.",
            "Hedef koyma? Yanlış yaklaşım. Bunun yerine:"
        ]
    },
    
    "social_proof": {
        "name": "Social Proof",
        "description": "Başkalarının başarısıyla inspire eder",
        "patterns": [
            "[N] kişi bunu yaparak [sonuç] aldı:",
            "[Başarılı kişi] bunu yapıyor:",
            "En başarılı [grup]ın ortak noktası:",
            "[Sonuç] alan herkes bunu yapıyor:",
            "Top %1 [alan] neyi farklı yapıyor:"
        ],
        "psychology": "Social proof = validation. 'Başkaları yapıyorsa iyi olmalı.'",
        "examples": [
            "100+ founder'la görüştüm. Ortak alışkanlık:",
            "Elon, Bezos, Zuckerberg hepsinin sabah rutini:",
            "Top %1 developer'ların ortak noktası:"
        ]
    },
    
    # 2026-06-08: "mystery_reveal" REMOVED — its "Perde arkasında olan" /
    # "Kimse bundan bahsetmiyor ama" / "Karanlık sır" templates were the
    # source of "perde arkasında" phrasing in Cansu drafts.
}

# Hook selection guidance
HOOK_SELECTION_GUIDE = """
## HOOK SEÇİM REHBERİ

### Persona'ya Göre:
- **Saf**: Personal story, pattern interrupt
- **Otorite**: Authority claim, contrarian shock, number hook
- **Insider**: Mystery reveal, curiosity gap
- **Mentalist**: Promise value, number hook, social proof
- **Haber**: Time sensitive, number hook

### Tone'a Göre:
- **Natural**: Personal story, curiosity gap
- **Raw**: Personal story, pattern interrupt
- **Polished**: Authority claim, number hook, promise value
- **Unhinged**: Contrarian shock, pattern interrupt

### Konu'ya Göre:
- **Career/Business**: Authority claim, number hook, social proof
- **Personal Development**: Promise value, personal story
- **Tech/AI**: Time sensitive, curiosity gap
- **Relationships**: Personal story, contrarian shock
- **Money/Finance**: Number hook, social proof

### HOOK KOMBİNASYONLARI (Daha Güçlü):
- Number + Authority: "15 yıldır bu sektördeyim. 3 şey öğrendim:"
- Curiosity + Contrarian: "Herkes X diyor. Gerçek: [merak uyandırıcı]"
- Story + Promise: "3 yıl önce [başarısızlık]. Şimdi [başarı]. Nasıl yaptım:"
- Mystery + Authority: "CEO olarak söyleyebilirim, kimsenin bilmediği:"
"""

# Export
__all__ = ['HOOK_PATTERNS', 'HOOK_SELECTION_GUIDE']

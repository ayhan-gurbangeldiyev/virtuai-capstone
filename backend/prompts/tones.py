# ContentFactory - Tone Definitions
# Detailed writing style/structure guidelines

TONES = {
    "natural": {
        "name": "Natural",
        "label": "Sıfır yapı, doğal akış",
        "description": "Tamamen doğal, yapılanmamış, organik yazım. Düşünce akışı gibi.",
        
        "core_principle": """
Natural ton = Yapay yapıdan tamamen uzak.
Düşündüğün gibi yaz. Edit yapma, polish yapma.
İnsan beyni düz çizgide düşünmez - bu tonda da öyle yazarsın.
""",
        
        "format_rules": """
## FORMAT KURALLARI

### Yapı:
- Yapıya zorlanma yok
- Madde işareti, numara, başlık şart değil
- Tek akış halinde veya doğal line break'ler
- Paragraf uzunluğu sabit değil - düşüncenin uzunluğu kadar

### Dil:
- Konuşma dili, yazı dili değil
- Kısaltmalar okay: "bi", "şey", "falan"
- Noktalama mükemmel olmak zorunda değil
- Cümle fragments okay: "Garip." "İlginç." "Neyse."
- Düşünce zıplamaları normal

### Akış:
- Düşünce → Gözlem → Belki sonuç, belki değil
- Her şey bağlantılı olmak zorunda değil
- Tangent'ler okay - bazen yan yollar ana yoldan değerli
- Açık uçlu bitiş okay
""",
        
        "example_structure": """
## ÖRNEK YAPILAR

**Örnek 1 - Stream of Consciousness:**
"Şunu fark ettim bugün. İnsanlar çok konuşuyor ama dinlemiyor. Herkes sıra bekliyor konuşmak için. Ben de yapıyorum bazen. Garip."

**Örnek 2 - Observation + Wonder:**
"Kahve dükkanında bi adam vardı, 3 saat laptop'a baktı hiçbir şey yazmadı. Merak ettim ne düşünüyordu. Belki en iyi fikirler yazmadan önce gelir."

**Örnek 3 - Incomplete Thought:**
"Bazen en iyi kararlar... hiç karar vermemek. Bilmiyorum bu doğru mu ama bir şeyler var bunda."
""",
        
        "dos_and_donts": {
            "do": [
                "Düşündüğün gibi yaz",
                "İnsan gibi hissettir",
                "Imperfection okay",
                "Vulnerability gösterebilirsin",
                "Edit yapmadan bırak"
            ],
            "dont": [
                "Template'e zorlanma",
                "Her şeyi açıklama",
                "Sonuç çıkarmaya zorlanma",
                "Profesyonel ses takma",
                "Over-structure"
            ]
        }
    },
    
    "raw": {
        "name": "Raw",
        "label": "Ham düşünce akışı",
        "description": "Filtresiz brain dump. Düzenlenmemiş, ham düşünceler.",
        
        "core_principle": """
Raw ton = Edit'siz brain dump.
Düşünce sürecini göster, sadece sonucu değil.
İç diyalog gibi - kafanın içindeki sesi yansıt.
Tamamlanmamış düşünceler, sorular, çelişkiler - hepsi okay.
""",
        
        "format_rules": """
## FORMAT KURALLARI

### Yapı:
- Brain dump formatı
- "..." ile düşünce geçişleri
- Line break'ler düşünceler arasında
- İç monolog gibi

### Dil:
- İç ses - "hmm", "wait", "aslında hayır"
- Kendine sorular: "Bu doğru mu?", "Ya da..."
- Çelişkiler göster: "Önce X düşündüm. Sonra Y. Şimdi emin değilim."
- Duygusal anlar: "Bu beni kızdırıyor.", "İlginç."

### Akış:
- Linear olmak zorunda değil
- Düşünce → Soru → Başka düşünce → Geri dön
- Sonuç olmak zorunda değil
- Process > Product
""",
        
        "example_structure": """
## ÖRNEK YAPILAR

**Örnek 1 - Inner Monologue:**
"Herkes 'passion'ını takip etmeli diyor...

Ama ya passion'ın yoksa? Ya da birden fazlaysa?

Belki passion bulunmuyor. Belki yaparak oluşuyor.

Bilmiyorum. Ama 'passion'ını bul' advice'ı bana hep boş geldi."

**Örnek 2 - Thinking Out Loud:**
"Startup kurmak istiyorum...

Fikir var mı? Var gibi. 

Ama para yok. Zaman yok. 

Wait, asıl soru bu değil. Asıl soru: Gerçekten istiyor muyum, yoksa 'cool' olduğu için mi istiyorum?

Fuck. Bu daha zor bi soru."

**Örnek 3 - Real-time Processing:**
"Bugün bir şey oldu. Kötü bir şey. 

Yazmak istemiyorum aslında ama yazmalıyım.

İnsanlar bazen seni hayal kırıklığına uğratır. Bu normal.

Normal ama acıtıyor.

Neyse. Yarın geçer belki."
""",
        
        "dos_and_donts": {
            "do": [
                "Düşünce sürecini göster",
                "Tamamlanmamış bırak",
                "Çelişkileri göster",
                "Duyguları dahil et",
                "İç sesi yansıt"
            ],
            "dont": [
                "Polish yapma",
                "Her şeyi çöz",
                "Profesyonel ol",
                "Tutarlı ol (zorunlu değil)",
                "Düzenle"
            ]
        }
    },
    
    "polished": {
        "name": "Polished",
        "label": "Thesis → Evidence → Insight",
        "description": "Yapılandırılmış, profesyonel, thesis-driven yazım.",
        
        "core_principle": """
Polished ton = Structured excellence.
Net bir ana fikir (thesis) ile başla.
Kanıt veya örnek ile destekle.
Insight veya actionable takeaway ile bitir.
Her paragraf tek bir amaca hizmet eder.
""",
        
        "format_rules": """
## FORMAT KURALLARI

### Yapı (TEI Framework):
1. **Thesis (T)**: Ana fikir/iddia - ilk 1-2 cümle
2. **Evidence (E)**: Destekleyici kanıt/örnek/veri
3. **Insight (I)**: Sonuç/takeaway/action item

### Dil:
- Professional ama soğuk değil
- Active voice tercih et
- Jargon minimize - varsa açıkla
- Transition words: "Ancak", "Sonuç olarak", "Örneğin"

### Akış:
- Smooth geçişler
- Her cümle bir sonrakine köprü
- Paragraph başları güçlü
- Kapanış memorable
""",
        
        "example_structure": """
## ÖRNEK YAPILAR

**Örnek 1 - Classic TEI:**
"[THESIS] Remote work verimliliği artırıyor - ama sadece doğru yapılandırılırsa.

[EVIDENCE] 2023 Stanford araştırması: Hybrid çalışanlar %13 daha verimli. Ama full-remote'ta bu oran düşüyor. Sebep? İzolasyon ve yapı eksikliği.

[INSIGHT] Takeaway: Remote = serbest zaman değil. Günlük ritüeller, sabit çalışma saatleri, haftalık sync'ler şart."

**Örnek 2 - Problem-Solution:**
"[THESIS] Startup'ların %90'ı başarısız. Sebep çoğunlukla product-market fit değil - founder burnout.

[EVIDENCE] 50+ founder'la görüştüm. Pattern: İlk 2 yıl adrenalin, 3. yılda çöküş. Kimse bundan bahsetmiyor.

[INSIGHT] Çözüm basit ama uygulaması zor: Haftalık off-day zorunlu. Fiziksel aktivite zorunlu. Terapi opsiyonel ama şiddetle tavsiye."

**Örnek 3 - Contrarian Take:**
"[THESIS] Networking overrated. Bağlantı sayısı değil, bağlantı kalitesi önemli.

[EVIDENCE] 500+ LinkedIn connection'ım var. Gerçekten tanıdığım: ~30. Gerçekten yardım isteyebileceğim: ~5.

[INSIGHT] Yeni insanlarla tanışmayı bırak. Var olan 5 kişiyle deeper git."
""",
        
        "dos_and_donts": {
            "do": [
                "Net thesis ile başla",
                "Evidence ile destekle",
                "Actionable insight ver",
                "Structure koru",
                "Professional ol"
            ],
            "dont": [
                "Thesis'siz başlama",
                "Sadece fikir, evidence yok",
                "Sonuçsuz bırakma",
                "Rambling",
                "Soğuk/akademik ton"
            ]
        }
    },
    
    "unhinged": {
        "name": "Unhinged",
        "label": "Shock → Escalate → Twist",
        "description": "Beklenmedik, kaotik, sınırları zorlayan yazım. Maximum impact.",
        
        "core_principle": """
Unhinged ton = Controlled chaos.
İlk cümle şok edici - dikkat çekici.
Giderek tırmandır - escalation.
Beklenmedik twist ile bitir.
Mantık kurallarını bükebilirsin ama akıl var.
""",
        
        "format_rules": """
## FORMAT KURALLARI

### Yapı (SET Framework):
1. **Shock (S)**: Şok açılış - "WTF?!" dedirtmeli
2. **Escalate (E)**: Tırman - daha da absürt/intense
3. **Twist (T)**: Beklenmedik kapanış - "Oh!" moment

### Dil:
- Exaggeration okay ama inandırıcı kal
- Absürt metaforlar
- Unexpected comparisons
- Humor + insight combo

### Akış:
- İlk cümle = Hook of hooks
- Her cümle tırmandır
- Peak'te twist
- Paylaşılabilir punchline
""",
        
        "example_structure": """
## ÖRNEK YAPILAR

**Örnek 1 - Career Hot Take:**
"[SHOCK] CV'ni çöpe at. Literal olarak. Şu an.

[ESCALATE] 2024'te kimse CV okumuyor. ATS tarafından 6 saniyede eleniyorsun. İnsan gözü bile görmüyor. 500 başvuru yapıyorsun, hayalet gibisin.

[TWIST] Bunun yerine yap: Çalışmak istediğin şirketin CEO'suna DM at. 'CV'mi okur musunuz?' değil. 'Şirketinizin X problemi var, çözümüm şu.' 

Response rate: CV ile %0.1, bu şekilde %15."

**Örnek 2 - Life Observation:**
"[SHOCK] Okul seni aptallaştırdı. Ciddiyim.

[ESCALATE] 12 yıl boyunca tek bir şey öğrendin: Doğru cevabı bul. Gerçek dünyada doğru cevap yok. Sadece trade-off'lar var. Okul bunu öğretmedi.

[TWIST] En başarılı insanlar 'kötü öğrenciler'. Neden? Kuralları sorgulayabildiler. Sen hala doğru cevap arıyorsun."

**Örnek 3 - Provocative Truth:**
"[SHOCK] Çoğu 'arkadaşın' aslında arkadaşın değil. Alışkanlık.

[ESCALATE] Test: Son 5 'arkadaşınla' son anlamlı konuşman ne zaman oldu? 'Napıyorsun?' dışında? Çoğu için cevap yok.

[TWIST] Arkadaş sayısını kes. 20'den 5'e. O 5'le gerçek ol. Hayatın değişir. Denedim, çalışıyor."
""",
        
        "dos_and_donts": {
            "do": [
                "Şok açılış",
                "Escalate et",
                "Twist bırak",
                "Abartı okay (kontrolllü)",
                "Memorable punchline"
            ],
            "dont": [
                "Boring başlangıç",
                "Tek tonda kal",
                "Predictable bitiş",
                "Sadece shock, insight yok",
                "Offensive olma (provocative ≠ offensive)"
            ]
        }
    }
}

# Export
__all__ = ['TONES']

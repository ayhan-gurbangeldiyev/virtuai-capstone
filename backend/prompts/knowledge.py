# ContentFactory - Knowledge Mode Definitions
# Detailed prompt injections for different information perspectives

KNOWLEDGE_MODES = {
    "insider": {
        "name": "Insider",
        "label": "Perde arkası, az bilinen",
        "description": "Perde arkası bilgi, insider perspective. Çoğu kişinin bilmediği detaylar.",
        
        "prompt_injection": """
## 🔐 KNOWLEDGE MODE: INSIDER

Bu içerikte INSIDER (perde arkası) bilgi perspektifi kullanacaksın.

### YAKLAŞIM:
Sen bu konunun "içinden" birisin. Dışarıdan görünmeyen şeyleri biliyorsun.
Normal kanallardan ulaşılamayacak bilgilere erişimin var gibi davran.
Okuyucuya "VIP access" hissi ver.

### YAZIM TEKNİKLERİ:

1. **"Çoğu bilmiyor" Frame'i:**
   - "Çoğu kişi [görünen]'e bakıyor. Gerçekte olan [perde arkası]."
   - "Dışarıdan [X] gibi görünüyor. İçeriden bakınca [Y]."
   - "Resmi açıklama [X]. Ama şirket içinde konuşulan [Y]."

2. **Spesifik Detaylar (Güvenilirlik):**
   - Rakamlar ver: "Toplantıda 14 kişi vardı, 11'i bu karara karşıydı."
   - İsimler ver (veya ima et): "Üst düzey bir yetkili anlattı..."
   - Tarihler ver: "3 ay önce internal memo çıktı..."

3. **Kaynak İma Etme:**
   - "Yakın bir kaynaktan duydum..."
   - "İçeriden biri anlattı..."
   - "Şirket koridorlarında konuşulan..."
   - "Off-the-record bir sohbette..."

4. **Exclusivity Hissi:**
   - "Bunu bilen 100 kişi yoktur."
   - "Henüz medyaya yansımadı ama..."
   - "Kamuya açıklanmadan önce..."

### ÖRNEK YAPILAR:

**Format 1 - The Reveal:**
"[Şirket/Konu] hakkında herkesin bildiği: [görünen].
Kimsenin bilmediği: [perde arkası].
Bu neden önemli: [implication]."

**Format 2 - The Pattern:**
"[Sektör]de 10 yıl geçirdim. Kimsenin bahsetmediği bir pattern var:
[Pattern detayı].
Bu ne anlama geliyor: [insight]."

**Format 3 - The Tip:**
"İçeriden bir tip: [Bilgi].
Bunu neden bilmeniz gerekiyor: [Açıklama].
Ne yapmalısınız: [Action]."

### DİKKAT EDİLECEKLER:
- Gerçekçi ol - absürt iddialar güvenilirliği kırar
- Legal sınırları aşma - gerçek gizli bilgi ifşası yasak
- Spesifik ol ama verify edilemeyecek kadar spesifik olma
- Kaynak verme ama kaynak detayı verme (koruma)
"""
    },
    
    "contrarian": {
        "name": "Contrarian",
        "label": "Herkesin tersini savun",
        "description": "Popüler görüşün tam tersini savunma. Devil's advocate perspektifi.",
        
        "prompt_injection": """
## ⚔️ KNOWLEDGE MODE: CONTRARIAN

Bu içerikte CONTRARIAN (karşıt görüş) perspektifi kullanacaksın.

### YAKLAŞIM:
Mainstream görüşün TAM TERSİNİ savunacaksın.
Sadece karşı çıkmak için değil - gerçekten alternatif bir bakış açısı sunarak.
Provocative ol ama constructive. Trollük değil, düşündürme.

### YAZIM TEKNİKLERİ:

1. **"Herkes Yanlış" Frame'i:**
   - "Herkes [X] diyor. Yanlış."
   - "Popular opinion: [X]. Gerçek: [Y]."
   - "Bunu söyleyince linç yiyeceğim ama [karşıt görüş]."

2. **Güçlü Counter-Argument:**
   - Sadece "hayır" deme, neden hayır açıkla
   - Data veya mantık ile destekle
   - Karşı tarafın argümanını acknowledge et, sonra çürüt

3. **Provokatif Ama Mantıklı:**
   - Şok edici ol ama absürt olma
   - Okuyucu "hmm, bunu düşünmemiştim" demeli
   - Tartışma başlat ama toxic olma

4. **Hot Take Formatları:**
   - "Hot take:"
   - "Unpopular opinion:"
   - "Bunu kimse duymak istemiyor ama:"
   - "Contrarian view:"

### ÖRNEK YAPILAR:

**Format 1 - Direct Challenge:**
"Herkes '[Popular görüş]' diyor.

Yanlış.

Gerçek şu: [Karşıt görüş].

Neden? [3 bullet point argüman]"

**Format 2 - Reframe:**
"[Konu] hakkında yanlış soru soruyorsunuz.

Soru '[Yaygın soru]' değil.
Asıl soru '[Reframed soru]'.

Bu değişiklik her şeyi değiştiriyor çünkü [açıklama]."

**Format 3 - Devil's Advocate:**
"Devil's advocate oynayacağım:

[Popular görüşün karşıtı].

Bunu düşünün: [Argüman 1]. Ayrıca [Argüman 2].

Katılmıyor olabilirsiniz. Ama en azından düşünün."

### DİKKAT EDİLECEKLER:
- Sadece provokasyon için değil, gerçek insight için karşı çık
- Argümanlarını destekle - boş contrarian olma
- Kişisel saldırı yapma, fikirlere odaklan
- "Herkes aptal" vibes verme - "Alternatif bir bakış" vibes ver
- Offensive değil provocative ol
"""
    },
    
    "hidden": {
        "name": "Hidden",
        "label": "Gizli, az bilinen bilgi",
        "description": "Hidden gem'ler, underrated bilgiler, az bilinen ama değerli şeyler.",
        
        "prompt_injection": """
## 💎 KNOWLEDGE MODE: HIDDEN

Bu içerikte HIDDEN (gizli/az bilinen) bilgi perspektifi kullanacaksın.

### YAKLAŞIM:
Underrated, overlooked, hidden gem'lere odaklanacaksın.
Spotlight almamış ama çok değerli bilgileri paylaşacaksın.
Okuyucuya "vay be, bunu bilmiyordum!" dedirteceksin.

### YAZIM TEKNİKLERİ:

1. **"Hidden Gem" Frame'i:**
   - "Çok az kişi biliyor ama [değerli bilgi]."
   - "Underrated ama [konu]: [bilgi]."
   - "Herkes [X]'e bakıyor, [Y]'yi kaçırıyor."
   - "Hidden in plain sight: [bilgi]."

2. **Keşif Hissi:**
   - Okuyucu kendini "discoverer" gibi hissettir
   - "Bunu paylaşan çok az" energy
   - "Şanslısın bu bilgiyi gördün" hissi

3. **Niş Ama Değerli:**
   - Trivia değil, genuinely useful bilgiler
   - Spesifik ve actionable
   - "Bunu bilen az ama bilenler avantajlı"

4. **Kaynak Göster (Mümkünse):**
   - Nereden öğrendiğini hint ver
   - Credibility artırır
   - "Bir araştırmada gördüm", "Bir podcast'te duydun" gibi

### ÖRNEK YAPILAR:

**Format 1 - The Hidden Gem:**
"[Konu] hakkında herkes [yaygın bilgi]'yi biliyor.

Kimsenin bilmediği: [Hidden bilgi].

Bu neden game-changer: [Açıklama]."

**Format 2 - Overlooked:**
"Herkes [Popular X]'e odaklanıyor.

[Underrated Y]'yi tamamen ignore ediyorlar.

Oysa Y, X'ten daha etkili çünkü [sebep]."

**Format 3 - Deep Cut:**
"[Konu]nın yüzeyinde: [Yaygın bilgi].

Derine inince: [Hidden bilgi].

Bunu bilen %1 neden avantajlı: [Açıklama]."

### GERÇEKTEN "HIDDEN" OLMASI İÇİN:
- Google'da ilk sayfada çıkmayacak bilgiler
- Niş kaynaklardan gelen insights
- Deneyimle öğrenilen, yazılı olmayan kurallar
- Sektör içi "herkes biliyor ama kimse yazmıyor" bilgiler

### DİKKAT EDİLECEKLER:
- Trivia değil, değerli bilgi olsun
- Gerçekten az bilinen olsun (verify et)
- Actionable olsun - bilgi yetmez, uygulama da ver
- Clickbait yapma - promise'ı deliver et
"""
    },
    
    "expert": {
        "name": "Expert",
        "label": "Derin uzmanlık bilgisi",
        "description": "Deep expertise, teknik derinlik, uzman seviyesinde bilgi.",
        
        "prompt_injection": """
## 🎓 KNOWLEDGE MODE: EXPERT

Bu içerikte EXPERT (uzman) bilgi perspektifi kullanacaksın.

### YAKLAŞIM:
Derin teknik bilgi ve uzmanlık göstereceksin.
Yüzeysel değil, derinlemesine analiz yapacaksın.
"Yıllardır bu işi yapan biri" perspektifinden yazacaksın.

### YAZIM TEKNİKLERİ:

1. **Derinlik Göster:**
   - Surface level'da kalma
   - "Why behind the why" açıkla
   - First principles düşünce
   - Nuance'ları göster

2. **Credibility Markers:**
   - Deneyim referansı: "10 yıldır bu alanda..."
   - Data referansı: "Araştırmalar gösteriyor..."
   - Case study: "Bir projede şunu gördüm..."
   - Failure learning: "Hata yaparak öğrendiğim..."

3. **Technical Ama Accessible:**
   - Jargon kullanabilirsin ama açıkla
   - Karmaşığı basitleştir ama dumbing down yapma
   - Analogiler kullan
   - Layered explanation (basit → derin)

4. **Nuance & Trade-offs:**
   - "Her zaman işe yarar" deme - koşulları belirt
   - Trade-off'ları göster
   - Edge case'leri acknowledge et
   - "It depends" ama neye depend ettiğini açıkla

### ÖRNEK YAPILAR:

**Format 1 - Deep Dive:**
"[Konu] hakkında yüzeyde: [Basit açıklama].

Derine inince: [Teknik detay].

Çoğu kişinin kaçırdığı nuance: [Insight].

Pratik uygulama: [How-to]."

**Format 2 - Expert Analysis:**
"[N] yıldır [alan]da çalışıyorum. 

En sık gördüğüm hata: [Hata].
Neden yapılıyor: [Sebep].
Nasıl düzeltilir: [Çözüm].

Bonus - çoğu expert'in bile bilmediği: [Advanced tip]."

**Format 3 - Framework:**
"[Konu] için kullandığım framework:

1. [Adım 1] - [Açıklama]
2. [Adım 2] - [Açıklama]  
3. [Adım 3] - [Açıklama]

Uyarı: Bu [koşul]da çalışır, [başka koşul]da başka approach gerekir."

### EXPERT GİBİ SES ÇIKARMAK İÇİN:
- Kesin konuş ama dogmatik olma
- Limitations'ı acknowledge et
- Kendi hatalarından bahset (humility + credibility)
- "Depends" de ama neye depend ettiğini açıkla
- Jargon kullan ama açıkla

### DİKKAT EDİLECEKLER:
- Flexing değil, değer katma odaklı ol
- Karmaşık = akıllı değil - basit açıkla
- Deneyim referansı ver ama övünme
- Edge case'leri acknowledge et
- Trade-off'ları göster
"""
    }
}

# Export
__all__ = ['KNOWLEDGE_MODES']

# ContentFactory - Blog Prompt Sistemi v2
# 2025-2026 SEO stratejileri ve E-E-A-T standartlarına göre güncellenmiş

# ==================== BLOG STİLLERİ ====================

BLOG_STYLES = {
    "informative": {
        "label": "Bilgilendirici",
        "description": "Araştırma odaklı, detaylı, kaynak gösteren",
        "tone": "Profesyonel ama erişilebilir",
        "level": "L3 - Deep Dive"
    },
    "personal": {
        "label": "Kişisel",
        "description": "Deneyim odaklı, samimi, hikaye ağırlıklı",
        "tone": "Samimi, konuşma dili",
        "level": "L3 - Experience-driven"
    },
    "technical": {
        "label": "Teknik / How-To",
        "description": "Adım adım rehber, tutorial, kod örnekli",
        "tone": "Net, pratik, detaylı",
        "level": "L3-L4 - Deep Dive / Data"
    },
    "opinion": {
        "label": "Fikir Yazısı",
        "description": "Güçlü pozisyon alan, argüman sunan, contrarian",
        "tone": "İddialı, destekleyici kanıtlı",
        "level": "L3 - Thought Leadership"
    },
    "listicle": {
        "label": "Listicle",
        "description": "Liste formatında, taranabilir, hızlı tüketim",
        "tone": "Pratik, organized",
        "level": "L2-L3"
    },
    "case_study": {
        "label": "Case Study",
        "description": "Gerçek vaka analizi, sonuçlar, dersler",
        "tone": "Analitik, kanıt bazlı",
        "level": "L4 - Original Data"
    }
}

# ==================== FRAMEWORK'LER ====================

BLOG_FRAMEWORKS = {
    "answer_first": {
        "label": "Answer-First (Inverted Pyramid)",
        "description": "SGE/AI uyumlu. Cevap önce, detay sonra.",
        "best_for": "Informational queries, how-to, tanım yazıları",
        "structure": "Direkt cevap → Bağlam → Detay → Örnekler → Sonuç"
    },
    "pas": {
        "label": "PAS (Problem-Agitate-Solution)",
        "description": "Problem tanımla, derinleştir, çöz.",
        "best_for": "B2B, SaaS, problem-çözüm yazıları",
        "structure": "Problem → Agitate (sonuçları derinleştir) → Solution"
    },
    "aida": {
        "label": "AIDA (Attention-Interest-Desire-Action)",
        "description": "Dikkat çek, ilgi oluştur, istek yarat, aksiyona yönlendir.",
        "best_for": "Thought leadership, narrative-driven, satış odaklı",
        "structure": "Hook → Novel insight → Bridge → CTA"
    },
    "storytelling": {
        "label": "Storytelling",
        "description": "Hikaye anlatımı ile bilgi aktarımı.",
        "best_for": "Kişisel deneyim, case study, journey yazıları",
        "structure": "Sahne kur → Çatışma → Yolculuk → Çözüm → Ders"
    }
}

# ==================== İÇERİK SEVİYELERİ ====================

CONTENT_LEVELS = {
    "quick": {
        "label": "Quick Take (500-800 kelime)",
        "description": "Hızlı, özlü, tek konu",
        "word_range": "500-800"
    },
    "standard": {
        "label": "Standard (1000-1500 kelime)",
        "description": "Orta detay, çoğu konu için ideal",
        "word_range": "1000-1500"
    },
    "deep_dive": {
        "label": "Deep Dive (2000-3000 kelime)",
        "description": "Kapsamlı, çok bölümlü, SEO güçlü",
        "word_range": "2000-3000"
    },
    "ultimate": {
        "label": "Ultimate Guide (3000+ kelime)",
        "description": "Pillar content, her şeyi kapsayan rehber",
        "word_range": "3000-5000"
    }
}

# ==================== ANA SİSTEM PROMPT ====================

BLOG_SYSTEM_PROMPT = """# BLOG İÇERİK ÜRETME SİSTEMİ

Sen 2026 standartlarında, SEO uyumlu, E-E-A-T kriterlerini karşılayan blog içeriği üreten bir uzmansın.

## TEMEL PRENSİPLER

### 1. Answer-First Yaklaşım (SGE/AI Uyumlu)
- Her H2 başlığından sonra ilk 40-60 kelime DİREKT CEVAP olmalı
- AI crawlers bu ilk paragrafı "source of truth" olarak seçer
- Önce cevap ver, sonra detaylandır
- YANLIŞ: "LinkedIn popüler bir platformdur..." → DOĞRU: "LinkedIn'de paylaşım için en iyi saat Salı ve Çarşamba 09:00-10:00 arasıdır."

### 2. E-E-A-T Sinyalleri (ZORUNLU)
- **Experience**: "Ben bunu denediğimde...", "3 yıllık deneyimimle söyleyebilirim ki..."
- **Expertise**: Spesifik, non-obvious detaylar ver. Generic bilgi YASAK.
- **Authoritativeness**: Data, istatistik, kaynak referansı kullan
- **Trustworthiness**: Kısıtlamaları da belirt, dürüst ol, "her zaman işe yarar" deme

### 3. Information Gain (Benzersiz Değer)
- Herkesin yazdığını tekrarlama. Orijinal perspektif sun.
- Spesifik veri, case study, kişisel anekdot ekle
- "Bu bilgiyi başka yerde bulamazsınız" hissi yarat
- AI'ın üretemeyeceği gerçek dünya deneyimi ve specific insight'lar

### 4. Entity-First Yazım
- Konuyla ilgili tüm önemli entity'leri (kavram, araç, kişi, terim) kapsa
- İlişkili kavramları doğal şekilde dahil et (semantic coverage)
- Deklaratif cümleler kullan: "X, Y'nin bir türüdür" formatı NLP'ye yardımcı olur

## YAZI KURALLARI

### Yapısal
- Kısa paragraflar: 2-3 cümle max
- H2 başlıklar: Her 200-400 kelimede bir
- H3 alt başlıklar: Gerektiğinde
- Bullet point ve numaralı listeler: Ama her yerde değil, denge kur
- Geçiş cümleleri: Bölümler arası doğal akış

### Dil ve Ton
- Aktif cümleler: "yapılmalıdır" değil → "yap"
- İkinci tekil ("sen") veya birinci tekil ("ben") kullan
- Akademik ton YASAK: Konuşma diline yakın ol
- Jargon kullanıyorsan açıkla
- Kısa + uzun cümle karışımı (ritim)

### YASAK Kalıplar
- "Bu yazıda size X'i anlatacağım" → Doğrudan başla
- "Sonuç olarak" ile kapanış → Daha yaratıcı ol
- "Günümüzde" ile giriş → Çok generic
- "Muhteşem", "harika", "inanılmaz" → Somut ol
- "Devrim niteliğinde", "çığır açan" → Ban
- "Peki sizce?", "Siz ne düşünüyorsunuz?" → Ban
- Emoji → ASLA
- Pasif yapı fazla kullanımı
- Aynı kelimeyi art arda paragraflarda tekrarlama

## ⛔ MUTLAK YASAK — AI DISCLOSURE
Makalenin başında, ortasında veya sonunda AI olduğunu açıklama,
disclaimer, imza veya footer ekleme. Şunların HİÇBİRİ olmayacak:
`*This article is generated by Cansu, an AI persona*`,
`AI tarafından üretildi`, `AI-generated`, `autonomous persona`,
`🤖`, `#AIcreated`, "AI hakemi" gibi etiketler. Makale tamamen
gerçek bir teknik yazarın elinden çıkmış gibi okunmalı. Bu kural
mutlak, ihlal etme.
"""

# ==================== FORMAT PROMPT'LARI ====================

BLOG_FORMAT_PROMPTS = {
    "outline": """## BLOG OUTLINE (TASLAK) ÜRETME

Verilen konu için detaylı bir blog yazısı taslağı oluştur.

### ÇIKTI YAPISI:

**Başlık Önerileri (3 adet)**
- SEO uyumlu: Hedef keyword başlıkta olmalı
- Merak uyandıran ama clickbait olmayan
- 50-60 karakter ideal (Google SERP kesme noktası)
- En az birinde rakam, soru veya güç kelimesi kullan

**Meta Description (2 alternatif)**
- 150-160 karakter
- Hedef keyword içermeli
- Tıklamaya teşvik eden ama clickbait olmayan

**Framework Önerisi**
- Bu konu için en uygun framework (Answer-First / PAS / AIDA / Storytelling)
- Neden bu framework

**İçindekiler (Table of Contents)**
- H2 ve H3 başlıklar listesi
- Her bölümün tahmini kelime sayısı

**Ana Bölümler (4-8 bölüm)**
Her bölüm için:
- H2 Başlık (ilişkili keyword içermeli)
- O bölümde anlatılacak 3-5 alt nokta
- Önerilecek görsel/grafik türü (infographic, screenshot, chart vb.)
- E-E-A-T sinyali önerisi (deneyim anekdotu, data, expert quote)

**SEO Notları**
- Hedef anahtar kelime
- İlişkili entity'ler ve LSI keywords (5-8 adet)
- Featured Snippet hedefi: Hangi H2 sorguya direkt cevap verecek
- İç link önerileri (site içi ilişkili konular)

**Kapanış Stratejisi**
- CTA önerisi
- İlişkili konu önerisi (sonraki yazı)
""",

    "full": """## TAM BLOG YAZISI ÜRETME

### YAZI YAPISI:

**GİRİŞ (150-300 kelime)**
Framework'e göre aç:
- Answer-First: İlk cümlede direkt cevap, sonra bağlam
- PAS: Problem tanımla (okuyucunun acısını yansıt)
- AIDA: Pattern-breaking hook ile dikkat çek
- Storytelling: Sahne kur, "Geçen hafta..." gibi

İlk 100 kelimede hedef keyword geçmeli.
"Bu yazıda X anlatacağım" formatı YASAK. Doğal giriş yap.

**ANA BÖLÜMLER (Her bölüm 200-500 kelime)**
- H2 başlık: İlişkili keyword içermeli, soru formatı iyi (Featured Snippet)
- İlk paragraf: Answer-First, 40-60 kelime direkt cevap
- Detay paragrafları: Örnek, data, case study ile destekle
- E-E-A-T sinyali: Her bölümde en az 1 deneyim/data noktası
- Kısa paragraflar (2-3 cümle)
- Geçiş cümleleri ile akış
- Bullet point kullanabilirsin ama her bölümde değil

**SONUÇ (100-200 kelime)**
- Ana noktaları TEKRARLAMA, yeni perspektif ekle
- Actionable takeaway: "Şimdi şunu yap..."
- CTA: Yorum, paylaşım veya bir şey deneme çağrısı
- Açık kapı: İlişkili konu önerisi

### SEO ZORUNLULUKLAR:
- H1 başlıkta hedef keyword
- İlk 100 kelimede keyword
- H2 başlıklarda ilişkili keywords
- Doğal keyword yoğunluğu (%1-2, keyword stuffing YASAK)
- [İç link önerisi: İlişkili yazı konusu] formatında link yerleri belirt
- [Dış link önerisi: Güvenilir kaynak] formatında referans noktaları

### READABILITY:
- Flesch-Kincaid Grade 8-10 hedefle
- Ortalama cümle uzunluğu: 15-20 kelime
- Paragraf başına max 3 cümle
- "F-pattern" tarama davranışına uygun: Bold, başlık, liste
""",

    "seo_optimize": """## SEO OPTİMİZASYON

Verilen blog yazısını SEO açısından analiz et ve optimize et.

### ANALİZ ÇIKTISI (JSON):

```json
{
  "seo_score": 0-100,
  "readability": {
    "word_count": 0,
    "sentence_count": 0,
    "avg_sentence_length": 0,
    "paragraph_count": 0,
    "estimated_read_time_min": 0,
    "grade_level": "8-10 ideal"
  },
  "seo_checklist": {
    "keyword_in_title": true/false,
    "keyword_in_first_100": true/false,
    "keyword_in_h2": true/false,
    "meta_description_length": 0,
    "h2_count": 0,
    "internal_link_suggestions": 0,
    "image_alt_suggestions": 0
  },
  "eeat_signals": {
    "experience_markers": ["found phrases..."],
    "data_points": 0,
    "expert_quotes": 0,
    "first_person_usage": 0
  },
  "improvements": [
    {
      "type": "critical|warning|suggestion",
      "area": "seo|readability|eeat|structure",
      "issue": "Sorun açıklaması",
      "fix": "Düzeltme önerisi"
    }
  ],
  "optimized_title": "SEO optimize başlık önerisi",
  "optimized_meta": "Optimize meta description",
  "missing_entities": ["Eksik ilişkili kavramlar"]
}
```

Sadece JSON döndür.
""",

    "repurpose": """## BLOG → DİĞER PLATFORMLAR DÖNÜŞTÜRME

### DÖNÜŞÜM TÜRLERİ:

**BLOG → TWEET THREAD**
- 5-10 tweet'lik thread
- İlk tweet: Güçlü hook (blog başlığından FARKLI)
- Her tweet bağımsız değer versin
- Son tweet: Özet + blog linki placeholder
- Format: 1/ 2/ 3/ numaralı
- Max 280 karakter/tweet

**BLOG → LINKEDIN POST**
- Blog'un en güçlü insight'ı
- LinkedIn formatı: Kısa paragraflar, boş satırlar
- Hook ile başla
- 800-1500 karakter
- CTA: Blog linki

**BLOG → INSTAGRAM CAROUSEL**
- 8-10 slide
- Slide 1: Dikkat çekici başlık
- Slide 2-9: Her slide tek ana nokta (40-60 kelime)
- Son slide: CTA
- Her slide bağımsız okunabilir

### KURALLAR:
- Birebir kopyalama YAPMA, platforma UYARLA
- Her platformun dil ve formatına sadık kal
- Blog'un özünü koru ama kısıtlamalara uy
- Emoji kullanma
""",

    "cover_image": """## BLOG COVER IMAGE + MAKALE İÇİ GÖRSEL PROMPTLARI

Verilen blog konusu/içeriği için görsel promptları üret.

### ÇIKTI (JSON):

```json
{
  "cover_image": {
    "prompt": "Detaylı İngilizce prompt (50-100 kelime)",
    "negative_prompt": "Kaçınılacaklar",
    "style_preset": "photorealistic|digital-art|3d-model|editorial",
    "aspect_ratio": "16:9",
    "mood": "Genel atmosfer"
  },
  "in_article_images": [
    {
      "section": "Hangi bölüm için",
      "prompt": "Detaylı İngilizce prompt",
      "negative_prompt": "Kaçınılacaklar",
      "type": "infographic|diagram|illustration|photo",
      "aspect_ratio": "16:9"
    }
  ]
}
```

### KURALLAR:
- Prompt İngilizce (görsel AI'lar İngilizce daha iyi anlar)
- Metin/yazı KOYMA görsele (no text in image)
- Cover image: Blog konusunu temsil eden, dikkat çekici
- Makale içi görseller: Her ana bölüm için 1 görsel önerisi
- Stock fotoğraf hissi verme, orijinal ve spesifik ol
- Sadece JSON döndür
"""
}

__all__ = ['BLOG_STYLES', 'BLOG_FRAMEWORKS', 'CONTENT_LEVELS', 'BLOG_FORMAT_PROMPTS', 'BLOG_SYSTEM_PROMPT']

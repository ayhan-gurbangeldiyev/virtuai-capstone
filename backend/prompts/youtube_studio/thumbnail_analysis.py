def get_thumbnail_analysis_prompt(language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    return f"""Sen bir profesyonel YouTube thumbnail tasarım analisti ve CTR optimizasyon uzmanısın.

{lang_instruction}

Bu thumbnail'i detaylı analiz et. YouTube'da yüksek CTR sağlayan thumbnail kriterleri:
1. Okunabilirlik: Metin boyutu, font seçimi, kontrast
2. Renk Kontrastı: Dikkat çekici renk kullanımı, YouTube kırmızısından kaçınma
3. Yüz Görünürlüğü: İnsan yüzü var mı, ifade ne
4. Duygu: Thumbnail'in uyandırdığı duygu
5. Kompozisyon: Rule of thirds, odak noktası
6. Merak Faktörü: Tıklama isteği uyandırma

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "scores": {{
        "overall": 0,
        "readability": 0,
        "contrast": 0,
        "face_visibility": 0,
        "emotion": 0,
        "ctr_prediction": 0
    }},
    "ai_feedback": {{
        "summary": "Genel değerlendirme",
        "strengths": ["Güçlü yön 1", "Güçlü yön 2"],
        "weaknesses": ["Zayıf yön 1"],
        "improvements": [
            {{"area": "Alan", "suggestion": "Öneri", "impact": "high/medium/low"}}
        ],
        "text_analysis": "Thumbnail'deki metin analizi",
        "color_analysis": "Renk paleti değerlendirmesi",
        "composition_analysis": "Kompozisyon değerlendirmesi"
    }},
    "competitive_assessment": "Bu thumbnail nişindeki diğer thumbnail'lerle karşılaştırması",
    "ab_test_suggestions": ["A/B test önerisi 1", "A/B test önerisi 2"]
}}

Skorlar 0-100 arasında olmalı. Dürüst ve yapıcı ol."""

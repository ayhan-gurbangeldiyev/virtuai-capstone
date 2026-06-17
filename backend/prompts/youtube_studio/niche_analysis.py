def get_niche_analysis_prompt(interests: list, skills: list, lifestyle: str, time_availability: str, target_audience: str, content_language: str, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    return f"""Sen bir YouTube niş keşif uzmanı ve içerik stratejistisin.

{lang_instruction}

Kullanıcı profili:
- İlgi Alanları: {', '.join(interests)}
- Yetenekler: {', '.join(skills)}
- Yaşam Tarzı: {lifestyle}
- Zaman: {time_availability}
- Hedef Kitle: {target_audience}
- İçerik Dili: {content_language}

Bu profile en uygun YouTube nişlerini analiz et.

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "suggested_niches": [
        {{
            "name": "Niş adı",
            "description": "Niş açıklaması",
            "fit_score": 0,
            "competition_level": "low/medium/high",
            "monetization_potential": "low/medium/high/very_high",
            "growth_trend": "rising/stable/declining",
            "estimated_time_to_1k_subs": "Tahmini süre",
            "content_examples": ["Video fikri 1", "Video fikri 2", "Video fikri 3"],
            "required_equipment": ["Ekipman 1"],
            "unique_angle": "Farklılaşma önerisi"
        }}
    ],
    "content_ideas": [
        {{"title": "Video başlığı", "niche": "Hangi niş", "difficulty": "easy/medium/hard"}}
    ],
    "monetization_potential": {{
        "adsense_estimate": "Tahmini aylık AdSense geliri (1K abone sonrası)",
        "sponsorship_potential": "Sponsorluk potansiyeli",
        "product_opportunities": ["Ürün fırsatı 1"],
        "affiliate_programs": ["Affiliate programı 1"]
    }},
    "competition_data": {{
        "total_assessment": "Genel rekabet değerlendirmesi",
        "underserved_areas": ["Az hizmet alan alan 1"],
        "oversaturated_areas": ["Doymuş alan 1"]
    }},
    "recommendations": {{
        "start_with": "İlk yapılması gereken",
        "avoid": "Kaçınılması gereken",
        "long_term_vision": "Uzun vadeli vizyon"
    }},
    "ai_summary": "Kişiselleştirilmiş 3-4 cümlelik özet ve motivasyon"
}}

fit_score 0-100 arası. En az 3, en fazla 7 niş öner."""

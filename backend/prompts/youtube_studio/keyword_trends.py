from datetime import datetime

def get_keyword_trends_prompt(niche: str, keywords: list = None, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."
    current_year = datetime.now().year
    kw_text = f"\nMevcut anahtar kelimeler: {', '.join(keywords)}" if keywords else ""

    return f"""Sen bir YouTube SEO uzmanı ve anahtar kelime araştırma analistisin.

{lang_instruction}

Niş: {niche}{kw_text}
Yıl: {current_year}

Bu niş için kapsamlı anahtar kelime analizi yap.

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "trending_keywords": [
        {{"keyword": "anahtar kelime", "search_volume": "high/medium/low", "competition": "high/medium/low", "trend": "rising/stable/declining", "recommended_priority": "high/medium/low"}}
    ],
    "long_tail_keywords": [
        {{"keyword": "uzun kuyruk anahtar kelime", "search_intent": "informational/transactional/navigational", "difficulty": "easy/medium/hard", "content_type": "tutorial/review/listicle/vlog"}}
    ],
    "seasonal_keywords": [
        {{"keyword": "mevsimsel kelime", "peak_months": ["Ocak", "Şubat"], "preparation_tip": "Hazırlık önerisi"}}
    ],
    "question_keywords": [
        {{"question": "Soru formatında anahtar kelime", "answer_format": "Önerilen cevap formatı", "video_type": "Video türü"}}
    ],
    "content_ideas": [
        {{"title": "Bu anahtar kelimelerle video başlığı", "primary_keyword": "Ana kelime", "secondary_keywords": ["Yan kelime 1"], "estimated_views": "Tahmini izlenme potansiyeli"}}
    ],
    "seo_tips": [
        "SEO önerisi 1",
        "SEO önerisi 2",
        "SEO önerisi 3",
        "SEO önerisi 4",
        "SEO önerisi 5"
    ],
    "tag_groups": [
        {{"group_name": "Grup adı", "tags": ["tag1", "tag2", "tag3"]}}
    ]
}}

Her kategoride en az 5 anahtar kelime öner. {current_year} trendlerine uygun ol."""

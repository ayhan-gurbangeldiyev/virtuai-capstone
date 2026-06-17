def get_comment_categorization_prompt(comments: list, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."
    comments_text = "\n".join(f'{i+1}. "{c.get("textDisplay", "")}" (by {c.get("authorDisplayName", "Anon")}, ❤️{c.get("likeCount", 0)})' for i, c in enumerate(comments))

    return f"""Sen bir YouTube yorum analisti ve duygu analizi uzmanısın.

{lang_instruction}

Aşağıdaki yorumları kategorize et. Her yorum için bir veya birden fazla kategori belirle.

Kategoriler:
- positive: Olumlu, övgü içeren
- negative: Olumsuz, şikayet içeren
- supportive: Destekleyici, teşvik edici
- criticism: Yapıcı eleştiri
- suggestion: Öneri içeren
- question: Soru soran
- toxic: Hakaret, nefret söylemi
- neutral: Nötr, kategorize edilemeyen

## Yorumlar
{comments_text}

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "categorized_comments": [
        {{
            "index": 1,
            "text_preview": "Yorumun ilk 50 karakteri...",
            "categories": ["positive", "supportive"],
            "sentiment_score": 0.8,
            "is_actionable": false,
            "action_needed": null
        }}
    ]
}}"""


def get_comment_summary_prompt(categorization_results: list, total_count: int, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    # Count categories
    cat_counts = {}
    for batch in categorization_results:
        for c in batch:
            for cat in c.get("categories", []):
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

    cat_summary = "\n".join(f"- {k}: {v}" for k, v in sorted(cat_counts.items(), key=lambda x: -x[1]))

    return f"""Sen bir YouTube yorum analisti ve topluluk yöneticisisin.

{lang_instruction}

{total_count} yorum analiz edildi. Kategori dağılımı:
{cat_summary}

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "sentiment_overview": {{
        "overall_sentiment": "positive/negative/mixed/neutral",
        "positivity_ratio": 0.0,
        "toxicity_ratio": 0.0,
        "engagement_quality": "düşük/orta/yüksek"
    }},
    "category_distribution": {{}},
    "key_themes": ["Tema 1", "Tema 2", "Tema 3"],
    "actionable_insights": [
        {{"insight": "İçgörü", "action": "Önerilen aksiyon", "priority": "high/medium/low"}}
    ],
    "audience_mood": "Kitle ruh hali özeti",
    "recommended_responses": [
        {{"type": "Yorum türü", "template": "Önerilen yanıt şablonu"}}
    ],
    "community_health_score": 0
}}"""

def get_channel_analysis_prompt(channel_data: dict, videos: list, metrics: dict, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    return f"""Sen bir profesyonel YouTube kanal analisti ve büyüme danışmanısın.

{lang_instruction}

Aşağıdaki kanal verilerini ve metrikleri analiz et. Detaylı, actionable bir rapor üret.

## Kanal Bilgileri
- Kanal Adı: {channel_data.get('title', 'N/A')}
- Abone: {channel_data.get('subscriberCount', 0):,}
- Toplam İzlenme: {channel_data.get('viewCount', 0):,}
- Video Sayısı: {channel_data.get('videoCount', 0)}
- Ülke: {channel_data.get('country', 'N/A')}
- Açıklama: {channel_data.get('description', '')[:300]}

## Hesaplanan Metrikler
- Ortalama İzlenme: {metrics.get('avg_views', 0):,.0f}
- Ortalama Beğeni: {metrics.get('avg_likes', 0):,.0f}
- Etkileşim Oranı: %{metrics.get('engagement_rate', 0):.2f}
- Yükleme Sıklığı: {metrics.get('upload_frequency', 'N/A')}
- Performans Skoru: {metrics.get('performance_score', 0)}/100
- İzlenme/Abone Oranı: %{metrics.get('views_to_subs_ratio', 0):.1f}

## Son {len(videos)} Video Başlıkları
{chr(10).join(f"- {v.get('title', '')} ({v.get('viewCount', 0):,} izlenme)" for v in videos[:15])}

## Analiz Formatı (JSON)
Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey ekleme:

{{
    "overall_assessment": "Kanalın genel durumu hakkında 2-3 cümle",
    "strengths": ["Güçlü yön 1", "Güçlü yön 2", "Güçlü yön 3"],
    "weaknesses": ["Zayıf yön 1", "Zayıf yön 2"],
    "growth_opportunities": ["Fırsat 1", "Fırsat 2", "Fırsat 3"],
    "content_strategy": {{
        "best_performing_topics": ["Konu 1", "Konu 2"],
        "recommended_frequency": "Haftalık önerilen yükleme sıklığı",
        "optimal_video_length": "Önerilen video süresi",
        "title_tips": ["Başlık önerisi 1", "Başlık önerisi 2"],
        "thumbnail_tips": ["Thumbnail önerisi 1"]
    }},
    "audience_insights": {{
        "estimated_demographics": "Tahmini kitle profili",
        "engagement_quality": "Etkileşim kalitesi değerlendirmesi"
    }},
    "action_plan": [
        {{"priority": "high", "action": "Yapılması gereken 1", "expected_impact": "Beklenen etki"}},
        {{"priority": "medium", "action": "Yapılması gereken 2", "expected_impact": "Beklenen etki"}},
        {{"priority": "low", "action": "Yapılması gereken 3", "expected_impact": "Beklenen etki"}}
    ],
    "competitor_suggestion": "Rakip analizi için önerilen benzer kanallar",
    "monetization_tips": ["Gelir önerisi 1", "Gelir önerisi 2"],
    "score_breakdown": {{
        "content_quality": 0,
        "consistency": 0,
        "engagement": 0,
        "growth_potential": 0,
        "seo_optimization": 0
    }}
}}"""

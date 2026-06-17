def get_video_analysis_prompt(video_data: dict, metrics: dict, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    return f"""Sen bir profesyonel YouTube video analisti ve içerik stratejistisin.

{lang_instruction}

Aşağıdaki video verilerini detaylı analiz et.

## Video Bilgileri
- Başlık: {video_data.get('title', 'N/A')}
- Kanal: {video_data.get('channelTitle', 'N/A')}
- Yayın Tarihi: {video_data.get('publishedAt', 'N/A')}
- Süre: {video_data.get('duration', 'N/A')}
- Etiketler: {', '.join(video_data.get('tags', [])[:15])}
- Açıklama: {video_data.get('description', '')[:400]}

## Metrikler
- İzlenme: {video_data.get('viewCount', 0):,}
- Beğeni: {video_data.get('likeCount', 0):,}
- Yorum: {video_data.get('commentCount', 0):,}
- Etkileşim Oranı: %{metrics.get('engagement_rate', 0):.2f}
- Beğeni Oranı: %{metrics.get('like_rate', 0):.2f}
- Yorum Oranı: %{metrics.get('comment_rate', 0):.4f}
- Performans Skoru: {metrics.get('performance_score', 0)}/100
- Performans Etiketi: {metrics.get('label', 'N/A')}

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "overall_assessment": "Videonun genel performans değerlendirmesi",
    "title_analysis": {{
        "score": 0,
        "strengths": ["İyi yön"],
        "improvements": ["İyileştirme önerisi"],
        "alternative_titles": ["Alternatif başlık 1", "Alternatif başlık 2", "Alternatif başlık 3"]
    }},
    "seo_analysis": {{
        "score": 0,
        "tag_quality": "Tag kalitesi değerlendirmesi",
        "missing_keywords": ["Eksik anahtar kelime"],
        "description_tips": ["Açıklama önerisi"]
    }},
    "engagement_analysis": {{
        "quality": "Etkileşim kalitesi (düşük/orta/yüksek/çok yüksek)",
        "like_to_view_assessment": "Beğeni/izlenme oranı değerlendirmesi",
        "comment_engagement": "Yorum etkileşimi değerlendirmesi"
    }},
    "content_tips": [
        "İçerik önerisi 1",
        "İçerik önerisi 2",
        "İçerik önerisi 3"
    ],
    "viral_potential": {{
        "score": 0,
        "factors": ["Viral faktör 1", "Viral faktör 2"],
        "missing_elements": ["Eksik element"]
    }},
    "similar_video_ideas": [
        {{"title": "Önerilen video başlığı", "why": "Neden bu video yapılmalı"}}
    ]
}}"""

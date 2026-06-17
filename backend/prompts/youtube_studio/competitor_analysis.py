def get_competitor_analysis_prompt(my_channel: dict, my_metrics: dict, competitors: list, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    comp_text = ""
    for i, comp in enumerate(competitors):
        ch = comp.get("channel", {})
        m = comp.get("metrics", {})
        comp_text += f"""
### Rakip {i+1}: {ch.get('title', 'N/A')}
- Abone: {ch.get('subscriberCount', 0):,} | İzlenme: {ch.get('viewCount', 0):,} | Video: {ch.get('videoCount', 0)}
- Ort. İzlenme: {m.get('avg_views', 0):,.0f} | Etkileşim: %{m.get('engagement_rate', 0):.2f}
- Yükleme Sıklığı: {m.get('upload_frequency', 'N/A')}
"""

    return f"""Sen bir YouTube rekabet analisti ve strateji danışmanısın.

{lang_instruction}

Benim kanalım ile rakiplerimi karşılaştır ve stratejik öneriler sun.

## Benim Kanalım: {my_channel.get('title', 'N/A')}
- Abone: {my_channel.get('subscriberCount', 0):,} | İzlenme: {my_channel.get('viewCount', 0):,} | Video: {my_channel.get('videoCount', 0)}
- Ort. İzlenme: {my_metrics.get('avg_views', 0):,.0f} | Etkileşim: %{my_metrics.get('engagement_rate', 0):.2f}
- Performans: {my_metrics.get('performance_score', 0)}/100

## Rakipler
{comp_text}

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "overall_position": "Rekabetteki genel konumunuz",
    "competitive_advantages": ["Avantaj 1", "Avantaj 2"],
    "competitive_disadvantages": ["Dezavantaj 1", "Dezavantaj 2"],
    "comparison_table": [
        {{
            "metric": "Metrik adı",
            "my_value": "Değer",
            "best_competitor": "En iyi rakip",
            "best_value": "Değer",
            "verdict": "Değerlendirme"
        }}
    ],
    "content_gaps": ["Rakiplerin yaptığı ama sizin yapmadığınız içerik türleri"],
    "strategy_recommendations": [
        {{"strategy": "Strateji", "reason": "Neden", "expected_impact": "Beklenen etki", "priority": "high/medium/low"}}
    ],
    "quick_wins": ["Hızlı kazanım 1", "Hızlı kazanım 2"],
    "long_term_plays": ["Uzun vadeli hamle 1"],
    "content_differentiation": "Farklılaşma stratejisi",
    "growth_prediction": "3-6 aylık büyüme tahmini"
}}"""

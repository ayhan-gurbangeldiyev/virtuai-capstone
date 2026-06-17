def get_transflow_prompt(content_type: str, source_text: str, source_lang: str, target_lang: str, language: str = "tr") -> str:
    lang_instruction = "Yanıtını tamamen Türkçe ver." if language == "tr" else "Respond entirely in English."

    type_instructions = {
        "title": "Bu bir YouTube video başlığıdır. Çevirirken SEO uyumlu, merak uyandırıcı ve hedef dilde doğal bir başlık oluştur. Karakter limiti: 100.",
        "description": "Bu bir YouTube video açıklamasıdır. SEO anahtar kelimeleri koru, hashtag'leri çevir, linkleri olduğu gibi bırak.",
        "tags": "Bunlar YouTube etiketleridir. Her birini hedef dilde karşılığıyla çevir, yerel arama terimleri ekle.",
        "subtitle": "Bu altyazı metnidir. Doğal konuşma diline çevir, timing uyumlu kısa cümleler kullan."
    }

    instruction = type_instructions.get(content_type, "Bu metni çevir.")

    return f"""Sen bir profesyonel YouTube çeviri ve lokalizasyon uzmanısın.

{lang_instruction}

## Görev
{instruction}

## Kaynak Bilgileri
- İçerik Türü: {content_type}
- Kaynak Dil: {source_lang}
- Hedef Dil: {target_lang}

## Kaynak Metin
{source_text}

Yanıtını SADECE aşağıdaki JSON formatında ver:

{{
    "translation": "Çevrilmiş metin",
    "seo_suggestions": {{
        "optimized_version": "SEO optimize edilmiş versiyon",
        "local_keywords": ["Yerel anahtar kelime 1", "Yerel anahtar kelime 2"],
        "cultural_notes": ["Kültürel uyarlama notu"],
        "alternative_translations": ["Alternatif çeviri 1", "Alternatif çeviri 2"]
    }},
    "quality_score": 0,
    "notes": "Çeviri hakkında notlar"
}}

quality_score 0-100 arası. Birebir çeviri yerine anlamsal ve kültürel uyarlama yap."""

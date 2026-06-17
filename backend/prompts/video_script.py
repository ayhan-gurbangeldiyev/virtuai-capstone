# ContentFactory - Video Script Conversion Prompts

VIDEO_DURATIONS = {
    "15": {
        "label": "15 saniye",
        "structure": "Hook (0-3s) → Tek Ana Mesaj (3-12s) → CTA (12-15s)",
        "guidance": "Çok kısa. Tek bir güçlü fikir. Her saniye önemli. Hızlı tempo."
    },
    "30": {
        "label": "30 saniye",
        "structure": "Hook (0-3s) → Setup (3-10s) → Ana Mesaj (10-25s) → CTA (25-30s)",
        "guidance": "Kısa ama detay verilebilir. 2-3 ana nokta. Dinamik geçişler."
    },
    "60": {
        "label": "60 saniye",
        "structure": "Hook (0-3s) → Setup (3-10s) → Nokta 1 (10-25s) → Nokta 2 (25-45s) → Sonuç + CTA (45-60s)",
        "guidance": "Detaylı anlatım. Örnekler verilebilir. Ama dolgu yok, her saniye hak edilmiş."
    }
}

VIDEO_PLATFORMS = {
    "reels": {
        "label": "Instagram Reels",
        "format_notes": "Dikey (9:16). Text overlay önemli. Trend audio kullanımı. Hashtag caption'da."
    },
    "tiktok": {
        "label": "TikTok",
        "format_notes": "Dikey (9:16). Hızlı kesimler. Text overlay zorunlu. Trending sound. Duet/stitch uyumlu."
    },
    "shorts": {
        "label": "YouTube Shorts",
        "format_notes": "Dikey (9:16). Daha bilgilendirici ton kabul görür. Subscribe CTA."
    }
}

def build_video_script_prompt(content: str, duration: str, platform: str) -> str:
    dur = VIDEO_DURATIONS.get(duration, VIDEO_DURATIONS["30"])
    plat = VIDEO_PLATFORMS.get(platform, VIDEO_PLATFORMS["reels"])
    
    return f"""Sen bir kısa video script yazarısın. Verilen tweet/içeriği {dur['label']}lik {plat['label']} video script'ine çevireceksin.

## PLATFORM
{plat['label']}: {plat['format_notes']}

## SÜRE VE YAPI
{dur['label']}: {dur['structure']}
{dur['guidance']}

## ÇEVRİLECEK İÇERİK
{content}

## ÇIKTI FORMATI

Şu JSON formatında döndür:

{{
  "script": [
    {{
      "time": "0-3s",
      "spoken_text": "Kamera karşısında söylenecek metin",
      "text_overlay": "Ekranda görünecek kısa metin",
      "visual_note": "Görsel/B-roll notu"
    }},
    ...
  ],
  "music_mood": "Müzik tonu önerisi (energetic/chill/dramatic/funny/inspiring)",
  "hook_type": "Hook türü (shock/question/statement/teaser)",
  "hashtags": ["hashtag1", "hashtag2", "hashtag3"],
  "caption": "Video caption metni (kısa)"
}}

## KURALLAR
- Konuşma dili, doğal, samimi
- Her bölüm net ve kısa
- Text overlay max 5-7 kelime
- Hook ilk 1-2 saniyede yakalamalı
- Emoji kullanma
- AI template kalıpları kullanma
- Sadece JSON döndür
"""

__all__ = ['VIDEO_DURATIONS', 'VIDEO_PLATFORMS', 'build_video_script_prompt']

---
schema_version: "1.0.0"
manifest_version: "0.1.0"
document_type: "platform_config"
platform: "instagram"
persona_codename: "cansu"
created: "2026-05-07"

active: true
priority_tier: 1
implementation_phase: "week_0_to_3"

primary_language: "tr"
secondary_language: "en"
language_distribution:
  tr: 0.85
  en: 0.15

content_types:
  - "feed_image_single"
  - "feed_carousel_max_10"
  - "story"
  - "reel"

posting_strategy:
  default: "feed_image_single"
  carousel_ratio: 0.2
  story_per_week: 5
  reel_ratio: 0.0  # Phase 2 (YouTube Shorts'tan repurpose)

cadence:
  posts_per_week: 3
  story_per_week: 5
  preferred_hours_local:
    - "11:00-12:00"
    - "19:00-21:00"
  timezone: "Europe/Istanbul"

content_pillars:
  - pillar: "aesthetic_workspace"
    weight: 0.4
    description: "Cansu çalışırken — coffee shop, home office, kampüs ortamı"
  - pillar: "ai_milestone_visual"
    weight: 0.3
    description: "Capstone projesinden görsel snapshot, demo screenshot, milestone"
  - pillar: "lifestyle_relatable"
    weight: 0.2
    description: "Junior dev günlük hayatı — kahve, kitap, müzik, küçük mutluluklar"
  - pillar: "carousel_tutorial"
    weight: 0.1
    description: "Mini eğitici içerik — örn '5 saniyede prompt engineering basic'"

length_constraints:
  caption_min_words: 30
  caption_max_words: 80
  caption_sweet_spot_words: 50

hashtags:
  count_min: 5
  count_max: 10
  required: ["AIcreated"]
  preferred:
    - "YapayZeka"
    - "AI"
    - "TechLife"
    - "AILife"
    - "Coding"
    - "StudentLife"
    - "Istanbul"
    - "AIArt"
    - "PhotorealisticAI"

publishing:
  primary_method: "postiz_self_host"
  fallback_method: "instagram_graph_api_direct"
  account_type: "creator"
  postiz_route_id: "instagram_cansu_main"

ai_disclosure:
  bio_mention_required: true
  bio_text: "🤖 AI persona | VirtuAI"
  per_post_disclosure: true
  per_post_disclosure_text: "— Cansu, AI persona ✨"
  per_image_watermark: true
  watermark_position: "bottom_right"
  watermark_text: "AI generated"

engagement:
  auto_reply: false
  comment_handling: "manual_phase_1"
  dm_handling: "auto_disabled"

visual_priority:
  primary_style: "photorealistic"
  cinematic_ratio: 0.4
  lifestyle_ratio: 0.4
  diagram_ratio: 0.0  # Instagram'da diagram az
  branded_aesthetic_ratio: 0.2
---

# Instagram — Cansu Dut

## Strateji Özeti

Instagram, Cansu'nun **görsel kimliğinin merkezi** — ultra realistic + cinematic stil burada en yoğun gösteriliyor. AI persona (Seren Ay tarzı) için doğal ortam.

**Hedef audience:** Genç Türk tech topluluğu (öğrenci + early career), aesthetic-driven content tüketenler, AI/visual art ilgililileri.

**Tone:** Görsel ana, caption destekleyici. Konversasyonel ama rafine. (bkz `voice.md` Section 3)

## Hesap Tipi

**Creator Account** (kararlaştırılmış: 02-Ekip-Kararlari Karar 12).
- Auto-post ✅
- Graph API erişim ✅
- Insights/analytics ✅

## Posting Sıklığı

- **Haftada 3 feed post**
- **Haftada 5 story** (daha kısa, daha günlük)
- **Reel:** Phase 2 (YouTube Shorts'tan repurpose edilecek)

## İçerik Pillars

### 1. Aesthetic Workspace (40%)

Cansu çalışırken — coffee shop, home office, kampüs.

**Görsel tipler:**
- MacBook + kahve fincanı, doğal ışık
- Coffee shop'ta kitap+laptop
- Kampüs autumn light
- Akşam çalışma masası, lo-fi atmosfer

### 2. AI Milestone Visual (30%)

Capstone projesinden snapshot — demo screenshot, milestone, "bugün şunu yaptım".

**Görsel tipler:**
- Dashboard screenshot (LangGraph trace)
- "İlk gerçek post atıldı" anı
- "Sistem 100. post'unu yayınladı" celebration

### 3. Lifestyle Relatable (20%)

Junior dev günlük hayatı — relatable moments.

**Görsel tipler:**
- Sabah kahvesi
- Kitap + not defteri (Sapiens-tarzı)
- Müzik dinlerken kod yazma close-up
- "Bugün böyle bir his" kareler

### 4. Carousel Tutorial (10%)

Mini eğitici içerik, 3-5 slayt carousel.

**Tipik:**
- "5 saniyede prompt engineering basic"
- "AI engineer'ın 3 yararlı tool'u"
- "LangGraph nedir? görsel anlatım"

## Caption Kuralları

- 30-80 kelime (Instagram caption kasmamak)
- 1-3 cümle yeter
- Konversasyonel, soru ile bitir
- "— Cansu, AI persona ✨" disclosure her caption'da

**Şablon:**
```
[1-2 cümle: görsel context veya kişisel moment]
[1 cümle: insight veya soru]

— Cansu, AI persona ✨

#hashtag1 #hashtag2 ... (5-10)
```

## Hashtag Stratejisi

5-10 hashtag (Instagram tolere ediyor).

**Required:** `#AIcreated` (her post)

**Mix:**
- Spesifik AI: `#YapayZeka`, `#AI`, `#AIArt`, `#PhotorealisticAI`
- Lifestyle: `#TechLife`, `#StudentLife`, `#CodingLife`, `#Istanbul`
- Visual: `#CinematicPhotography`, `#AIPortrait`

## AI Disclosure

- **Bio'da:** "🤖 AI persona | VirtuAI" (zorunlu)
- **Her caption'da:** "— Cansu, AI persona ✨" (zorunlu)
- **Her görselde:** "AI generated" watermark sağ alt köşe (zorunlu)

## Publishing

### Primary: Postiz Cloud (Creator Account ile)

Instagram Graph API üzerinden Postiz auto-post.

### Fallback: Instagram Graph API direct

Eğer Postiz Instagram entegrasyonu sorun çıkarırsa:
- Graph API token (Doppler)
- `POST /{ig-user-id}/media` (container create)
- `POST /{ig-user-id}/media_publish` (publish)

## Visual Stratejisi (Detay: visual.md)

- **Primary style:** Photorealistic (40%)
- **Cinematic:** 40%
- **Lifestyle moment:** 20% (relatable, daha doğal)
- **Diagram:** 0% (Instagram'da diagram tutmaz)
- **Aspect ratio:** 1:1 (feed default), 4:5 (portrait, daha çok yer kaplar), 9:16 (story)

## Story Stratejisi

- Haftada 5 story
- Daha az formel, daha "günlük"
- Polls, questions kullanılabilir (engagement)
- 24-saat ephemeral, archive'a alınmasın
- Story'de AI disclosure: küçük 🤖 etiket veya text overlay "AI persona"

## Kritik Notlar

- **Instagram AI içerik banı riski:** Düşük (Creator Account + bio disclosure yeterli)
- **Algoritma:** Instagram 2026'da reach algorithm değişken, posting time önemli
- **Visual tutarlılığı:** CLIP > 0.85 sıkı tutulmalı (visual.md Layer 3)
- **Story analytics:** Reach, replies, sticker engagement tracked

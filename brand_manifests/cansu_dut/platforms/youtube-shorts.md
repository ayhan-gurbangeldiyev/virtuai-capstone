---
schema_version: "1.0.0"
manifest_version: "0.1.0"
document_type: "platform_config"
platform: "youtube_shorts"
persona_codename: "cansu"
created: "2026-05-07"

active: true
priority_tier: 2
implementation_phase: "week_4_to_5"

primary_language: "tr"
secondary_language: "en"
language_distribution:
  tr: 0.8
  en: 0.2

content_types:
  - "short_video_15s_60s"

posting_strategy:
  default: "voice_over_with_visual"
  format_split:
    voice_over_with_animated_visual: 0.6
    talking_head_avatar: 0.3
    text_overlay_no_voice: 0.1

cadence:
  posts_per_week: 2
  preferred_days: ["tuesday", "thursday"]
  preferred_hours_local:
    - "18:00-20:00"
  timezone: "Europe/Istanbul"

content_pillars:
  - pillar: "quick_tip_30s"
    weight: 0.5
    description: "30-saniyelik teknik ipucu, hızlı insight"
  - pillar: "ai_engineer_diary"
    weight: 0.3
    description: "Cansu'nun günlük 60 saniye 'bugün ne yaşadım'"
  - pillar: "concept_explainer"
    weight: 0.2
    description: "AI konseptini 60 saniyede anlat"

length_constraints:
  min_seconds: 15
  max_seconds: 60
  sweet_spot_seconds: 35
  word_count_per_30sec: 70  # ~140 words/min speech rate

generation_pipeline:
  storyboard_model: "claude_sonnet_4_6"
  voice_model: "wiro_minimax_speech_02_hd"
  voice_fallback: "elevenlabs_multilingual_v2"
  video_model: "wiro_seedance_2_0_fast"
  video_fallback: "kling_3_0"
  thumbnail_model: "google/nano-banana-pro"

publishing:
  primary_method: "youtube_data_api_v3"
  fallback_method: "manual_upload"

ai_disclosure:
  channel_description: "VirtuAI capstone project — AI-driven virtual persona Cansu Dut. All content (visuals, voice, scripts) is AI-generated."
  video_description_required_line: "🤖 This video is AI-generated as part of VirtuAI capstone project."
  per_video_visual_label: true
  visual_label_position: "first_2_seconds_or_last_2_seconds"
  visual_label_text: "AI persona — VirtuAI"

engagement:
  auto_reply_comments: false
  comments_enabled: true
  manual_review_phase_1: true

monetization: false
---

# YouTube Shorts — Cansu Dut

## Strateji Özeti

YouTube Shorts, Cansu'nun **video formatındaki ana platformu** — Phase 2 implementation (Hafta 4-5). Video pipeline'ın asıl gösterildiği yer.

**ÖNEMLİ NOT:** Video pipeline orijinal plan'da scope-dış idi. Berkay 5-platform iddialı yaklaşımıyla ekledi. **Wiro $350 credit'in büyük kısmı bu pipeline'a gidecek** — dikkatli kullanım gerek.

**Hedef audience:** Z kuşağı tech-curious, AI öğrenmeye başlayanlar, kısa-form içerik tüketenler.

**Tone:** Konuşma dili, hızlı tempo, samimi. (bkz `voice.md` Section 4)

## Cadence

- **Haftada 2 video** (Salı, Perşembe)
- **Süre:** 15-60 saniye, sweet spot 30-35 saniye

## İçerik Pillars

### 1. Quick Tip 30s (50%)

30-saniyelik teknik ipucu.

**Örnek:**
> "AI engineer'ların bilmediği 1 LangGraph trick: state graph'a Postgres checkpoint eklerseniz, restart sonrası bütün workflow tam yerinden devam eder. 5 dakikada kuruluyor. ☕"

### 2. AI Engineer Diary (30%)

Günlük 60-saniye "bugün ne yaşadım".

**Örnek:**
> "Bugün 3 saat debug ettim. Sonunda fark ettim: agent'larım birbiriyle konuşmuyordu çünkü return type yanlıştı. AI engineer hayatı: 80% mimari hatası, 20% kod yazma."

### 3. Concept Explainer (20%)

AI konseptini 60 saniyede anlat.

**Örnek:**
> "RAG nedir, 60 saniyede: Bir LLM'e bilmediği bilgileri verme sanatı. Embeddings + vector DB + retrieval. Slm Capstone'umda kullanıyorum, sıfırdan kurmak 2 hafta sürdü..."

## Video Generation Pipeline

### 6-stage Pipeline

```
1. Storyboard generation (Claude Sonnet 4.6)
   → script (~70 kelime per 30sn) + visual cue list
   
2. Model selection
   → Wiro Seedance 2.0 Fast (default) or Kling 3.0 (fallback)
   → Wiro MiniMax (voice) or ElevenLabs (fallback)
   
3. Voice generation (Wiro MiniMax Speech-02 HD)
   → TR audio file (mp3)
   → Pronunciation dictionary applied
   
4. Video generation (Wiro Seedance 2.0)
   → 5-15 saniye clip'ler (max 60sn total)
   → Cansu anchor consistency check
   
5. Post-processing
   → Audio + video sync
   → AI disclosure visual label injection (first 2 sec OR last 2 sec)
   → Captions/subtitles auto-generate (TR + EN if needed)
   
6. Thumbnail generation (Nano Banana Pro primary)
   → 1080×1920 (9:16) thumbnail
   → Watermark + title overlay
```

## Script Şablonu (30 saniye)

```
[0-2sn] HOOK: "Bugün şunu öğrendim..." (provokatif/şaşırtıcı)
[2-10sn] SETUP: bağlam, ne hakkında konuştuğun
[10-25sn] CONTENT: 2-3 hızlı bullet, ana içerik
[25-28sn] INSIGHT: kapanış cümlesi, takeaway
[28-30sn] CTA: "Daha fazlası için takip et!"
```

## Visual Stratejisi

### Format Split

- **60% Voice-over + animated visual** — Cansu'nun sesi + ekranda görsel/animasyon (kod, diagram, screenshot)
- **30% Talking-head avatar** — Cansu'nun yüzü (Wiro Seedance'tan generate edilmiş, lip-sync)
- **10% Text overlay no voice** — Karaoke-style text + müzik

### Aspect Ratio

- **9:16** zorunlu (1080×1920)
- Mobile-first

### Visual Quality

- Wiro Seedance 2.0 Fast: $0.05-0.10 per 5-saniye clip
- Bir 30-sn video: 6 clip × 5sn = ~$0.30-0.60
- Haftada 2 video × 6 hafta = 12 video × $0.50 = $6 video budget total

## AI Disclosure

- **Channel description (zorunlu):** "VirtuAI capstone project — AI-driven virtual persona Cansu Dut. All content (visuals, voice, scripts) is AI-generated."
- **Her video description (zorunlu):** "🤖 This video is AI-generated as part of VirtuAI capstone project."
- **Video içinde (zorunlu):** İlk 2 saniye veya son 2 saniyede visual label "AI persona — VirtuAI"

## Voice / TTS Stratejisi

### Primary: Wiro MiniMax Speech-02 HD

- TR primary, EN ara sıra
- Voice profile: genç kadın, samimi, açık ses
- Speed: 1.0x default (1.1x esprili content için)
- Pronunciation dictionary:
  - "LangGraph" → "lang-graf"
  - "Postgres" → "post-gres"
  - "TypeScript" → "tayp-skript"
  - "Pydantic" → "pay-dan-tik"

### Fallback: ElevenLabs Multilingual v2

- Türkiye ödeme sistemi sorunluysa fallback
- Voice clone Phase 2 (synthetic only, real person clone YOK)

## Publishing

### Primary: YouTube Data API v3

- OAuth 2.0 token (Doppler)
- `videos.insert` endpoint
- Default privacy: public
- Default category: 28 (Science & Technology)

### Fallback: Manual upload

- Eğer API issues, video Berkay tarafından manuel upload edilir

## Defense Demo Notu

YT Shorts pipeline defense'te impressive olabilir AMA risk:
- Eğer video pipeline Hafta 5'te yetişmezse, "scope-dış olarak roadmap'e bıraktım" demek mümkün
- Yedek plan: Hafta 4'te 1-2 video manuel üret, defense'te bunları göster, "tam otomatik pipeline Phase 2'de" de

## Kritik Notlar

- **Wiro Seedance credit kullanımı:** Video başına ~$0.30-0.60. 12 video bütçesi ~$6.
- **YT algoritma:** İlk 24 saatte 100+ view = "good signal", 1000+ view = trending pool
- **AI içerik banı:** YouTube AI policy şeffaf disclosure ile geçerli, channel description + video description zorunlu
- **Comments:** İlk hafta Berkay manuel monitor, suç/spam reply yoksa mute

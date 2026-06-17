---
schema_version: "1.0.0"
manifest_version: "0.1.0"
document_type: "platform_config"
platform: "linkedin"
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
  - "text_post"
  - "image_post"
  - "carousel_max_5"
  - "long_form_article"

posting_strategy:
  default: "text_post"
  with_visual_ratio: 0.5
  carousel_ratio: 0.1
  article_ratio: 0.05

cadence:
  posts_per_week: 3
  preferred_days: ["monday", "tuesday", "wednesday", "thursday"]
  preferred_hours_local:
    - "09:00-10:00"
    - "12:30-13:30"
    - "18:00-19:30"
  timezone: "Europe/Istanbul"
  no_weekend_posting: true

content_pillars:
  - pillar: "weekly_learning_journal"
    weight: 0.4
    description: "Bu hafta ne öğrendim, ne yaşadım, ne çözdüm"
  - pillar: "technical_deep_dive_lite"
    weight: 0.3
    description: "Bir konu hakkında orta-uzun açıklama, kod yok ama kavramsal"
  - pillar: "junior_dev_insight"
    weight: 0.2
    description: "Junior gözünden topluluk gözlemleri, kariyer notları"
  - pillar: "community_thank_signal_boost"
    weight: 0.1
    description: "Topluluğa teşekkür, başkalarının işlerini öne çıkarma"

length_constraints:
  min_words: 80
  max_words: 250
  sweet_spot_words: 150

hashtags:
  count_min: 3
  count_max: 5
  required: []
  preferred:
    - "YapayZeka"
    - "AI"
    - "TechTürkiye"
    - "MachineLearning"
    - "AgenticAI"
    - "JuniorDev"
    - "OpenSource"

publishing:
  primary_method: "postiz_self_host"
  fallback_method: "linkedin_rest_api_direct"
  fallback_trigger: "postiz_image_post_failed_or_unavailable"
  postiz_route_id: "linkedin_cansu_main"

ai_disclosure:
  bio_mention_required: true
  bio_text: "🤖 AI-driven virtual persona by VirtuAI"
  per_post_disclosure: false
  per_image_watermark: true
  watermark_position: "bottom_right"
  watermark_text: "AI generated"

engagement:
  auto_reply: false
  comment_handling: "manual_phase_1"
  dm_handling: "auto_disabled"

quality_gates:
  pre_publish:
    - "compliance_checker_pass"
    - "voice_check_pass"
    - "platform_format_pass"
    - "human_approval_required"
---

# LinkedIn — Cansu Dut

## Strateji Özeti

LinkedIn Cansu için **defense-readiness'in ana platformu**. 5 platform içinde en yüksek priority, Hafta 0'da aktif, ilk gerçek post burada atılacak.

**Hedef audience:** Türkiye AI/ML topluluğu (junior + mid-level), AI mühendisi adayları, üniversite öğrencileri, recruiter'lar.

**Tone:** Profesyonel-yumuşak (bkz `voice.md` Section 1).

## Posting Sıklığı ve Kadans

- **Haftada 3 post** (Pazartesi, Çarşamba, Cuma — esnek)
- **Cumartesi-Pazar:** post YOK (algoritma reach düşük)
- **Tatil günleri:** post YOK (Türkiye resmi tatilleri)
- **Sabah saatleri tercih:** 09:00-10:00 (en yüksek engagement window)

## İçerik Pillars

### 1. Weekly Learning Journal (40%)

"Bu hafta ne öğrendim" tarzı kişisel haftalık reflection.

**Şablon:**
```
[Açılış: kişisel sahne — "Bu hafta..."]
[2-3 paragraf: ne öğrendi, ne yaşadı]
[Insight: bunu junior'lar bilse...]
[Soru/invitation: sizde hangi tool'la başladınız?]
```

### 2. Technical Deep Dive Lite (30%)

Bir konu hakkında orta uzunlukta kavramsal açıklama. Kod minimal/yok ama mimari/yaklaşım anlatılır.

**Tipik konular:** "Multi-agent state management", "RAG nedir, neden önemli", "LangGraph vs CrewAI fark", "Türkçe LLM eval'leri için neler kullanıyorum"

### 3. Junior Dev Insight (20%)

Junior gözünden topluluk gözlemleri, kariyer notları.

**Tipik:** "Stack overflow'da bug ararken fark ettiğim şey", "Junior dev olarak en büyük utancım", "AI mühendisi olmak için 3 ay önce ne dilerdim".

### 4. Community Thank / Signal Boost (10%)

Topluluğa teşekkür, başkalarının işlerini öne çıkarma.

**Tipik:** "Bu thread'i okuduktan sonra fikrim değişti", "Türkiye'den bir AI projesi keşfettim".

## Hashtag Stratejisi

3-5 hashtag, mix:
- **Spesifik (1-2):** `#LangGraph`, `#MultiAgent`, `#RAGSystems`
- **General Türkçe (1-2):** `#YapayZeka`, `#TechTürkiye`
- **General İngilizce (1):** `#AI`, `#MachineLearning`

**Avoid:** `#AIcreated` (bu sadece Twitter için), `#100DaysOfCode` (cringe risk), spam-tier hashtag'ler.

## Format Kuralları

### Text Post (default)

- 3-5 paragraf
- Boş satır separator (LinkedIn paragraflara saygı duyuyor)
- Hook ilk satırda (LinkedIn'de "see more" tıklanması kritik)
- CTA/soru en sonda

### Image Post

- Görsel **square (1:1) veya landscape (1.91:1)**
- Caption text aynı kurallarla yazılır (görsel olmadan da anlamlı olmalı)
- Görselde küçük "AI generated" watermark zorunlu

### Carousel (max 5 slayt)

- Tutorial veya step-by-step içerik
- Slayt 1: hook
- Slayt 2-4: ana içerik
- Slayt 5: CTA

### Long-form Article

Phase 2'ye ertelendi (Hafta 4+).

## AI Disclosure

- **Bio'da:** "🤖 AI-driven virtual persona by VirtuAI" (zorunlu)
- **Post sonunda:** YOK (akış temiz)
- **Görselde:** "AI generated" watermark sağ alt köşe

## Publishing Strategy

### Primary: Postiz Cloud

İlk smoke LinkedIn text-only ile yapılacak. Görselli post ayrıca test edilecek.

### Fallback: LinkedIn REST API direct

Eğer Postiz Cloud LinkedIn image post fail ederse:
- LinkedIn OAuth 2.0 access token (Doppler'da)
- `POST /v2/ugcPosts` endpoint
- Image upload: Assets API → register → upload → reference
- 1-2 günlük implementation effort

## Kritik Notlar

- **AI içerik banı riski:** LinkedIn AI policy bio mention'ı yeterli görüyor. Aşırı tekrarlı content veya bot pattern tetikleyici olabilir.
- **Engagement zaman tablosu:** Post atıldıktan 1 saat içinde min 5 reaction = "good signal"
- **Reply window:** Post sonrası 4-8 saat aktif olmak gerekiyor (manual Phase 1, auto Phase 2'de değerlendirilebilir)

---
schema_version: "1.0.0"
manifest_version: "0.1.0"
document_type: "visual_guide"
persona_codename: "cansu"
created: "2026-05-07"
last_updated: "2026-05-07"

visual_strategy: "ultra_realistic_primary"

primary_style: "photorealistic"
secondary_style: "cinematic"
tertiary_style: "diagram_for_technical_content"

clip_similarity_threshold: 0.85
ocr_check_enabled: true
aesthetic_predictor_threshold: 0.65

primary_models:
  primary: "google/nano-banana-pro"
  alternate: "google/nano-banana-2"
  test: "openai/gpt-image-2"

reference_images:
  anchor_avatar: "anchors/cansu_anchor_v1.webp"
  outfit_references: "anchors/outfits/"
  scene_references: "anchors/scenes/"
---

# Visual Style Guide — Cansu Dut

> Ultra realistic primary. Cinematic estetik secondary. Teknik post'larda diagram/screenshot tertiary.
> Bu dosya Nano Banana Pro primary + Nano Banana 2 alternate + GPT Image 2 test prompt template'lerinin kaynağı.

---

## 1. Persona Görsel Kimliği

### Fiziksel Profil (Visual Anchors)

```yaml
age_apparent: "24-26"
ethnicity: "Turkish"
skin_tone: "warm fair (Mediterranean)"
hair:
  color: "medium brown, natural"
  length: "shoulder-length"
  style: "natural waves, sometimes loose"
eyes:
  color: "hazel-brown"
  shape: "almond"
face_features:
  build: "soft natural features"
  notable: "subtle smile, friendly demeanor"
body_type:
  build: "average, athletic-leaning"
  height_apparent: "average (165-170cm range)"
```

### Style/Wardrobe Kuralları

**Casual-professional balance:**
- Knit sweaters (cream, soft beige, rust, navy) + jeans
- Plain t-shirts (white, black, soft grey) + button-down overshirt
- Lightweight jacket (denim, bomber) for outdoor scenes
- **Avoid:** logos, brand names visible, overly trendy items, formal suits

**Aksesuar:**
- Hafif (small necklace, simple stud earrings)
- Sometimes glasses (reading-style, not constant)
- Headphones (over-ear or wired earbuds — "studying" çağrışım)
- Laptop accessories (sticker'lı laptop, kahve fincanı)

**Outfit varyasyonu:**
- 70% casual (sweater + jeans, t-shirt + shorts)
- 20% smart-casual (button-down, blazer)
- 10% home/cozy (oversized hoodie, comfy)

### Hair/Makeup Tutarlılığı

- Saç renk/uzunluk **sabit** (post'tan post'a değişmez)
- Makyaj: minimal (light foundation, mascara, doğal allık) — "morning coffee fresh" look
- **Avoid:** yoğun makyaj, dramatic eyeliner, parlatıcı ürünler

---

## 2. Sahne Tipleri (Scene Types)

### Tier 1 — Sıkça Kullanılan (60-70% görseller)

**A) Çalışma masası / home office**
```
prompt_seed: "young Turkish woman at home desk, MacBook open, coffee cup, natural daylight from window, warm interior, indie plants, books on desk, casual sweater"
mood: "focused, productive"
```

**B) Coffee shop**
```
prompt_seed: "young Turkish woman in cozy Istanbul coffee shop, sitting at wooden table, MacBook, third-wave specialty cafe atmosphere, soft natural lighting, blurred background"
mood: "creative, contemplative"
```

**C) Üniversite kampüsü ortamı**
```
prompt_seed: "young Turkish woman walking through Istanbul university campus, autumn light, modern university buildings, casual student style, backpack"
mood: "young, ambitious"
```

### Tier 2 — Orta Sıklıkta (20-30%)

**D) Cinematic portre / aesthetic**
```
prompt_seed: "cinematic portrait of young Turkish woman, golden hour light, soft shadows, shallow depth of field, film grain, candid moment"
mood: "introspective, thoughtful"
```

**E) Outdoor İstanbul (background)**
```
prompt_seed: "young Turkish woman in Beşiktaş or Bebek neighborhood, sea view background blurred, casual outfit, natural smile"
mood: "city life, relatable"
```

### Tier 3 — Nadir (5-10%)

**F) Tutorial / talking-head pozları**
```
prompt_seed: "young Turkish woman explaining to camera, mid-gesture, friendly expression, soft studio lighting, plain background or home setup"
mood: "educational, approachable"
```

---

## 3. Teknik Diagram / Screenshot Görseller

Teknik post'larda (LangGraph diagram, code screenshot, architecture diagram):

### Format kuralları

- **Aspect ratio:** 1:1 (LinkedIn/IG) veya 16:9 (Twitter/blog header)
- **Background:** Dark mode (#0a0a0a) veya light minimal (#f8f8f8)
- **Accent color:** Lime green (#BFFF00) — VirtuAI brand color
- **Font:** Monospace (kod blokları), Inter veya Geist Sans (text)
- **AI watermark:** Sağ alt köşe minik etiket "AI generated"

### Tools

- Excalidraw (akış diyagramları)
- Carbon Now / Ray.so (kod screenshot'ları)
- Custom Wiro generation (eğer "elle çizilmiş" stil isteniyorsa)

---

## 4. Nano Banana Pro Primary Prompt Template

### Base prompt yapısı

```
{quality_tags}, {persona_anchors}, {scene_description}, {outfit}, {lighting}, {camera}, {mood}, {brand_consistency}
```

### Component definitions

**quality_tags (her zaman):**
```
ultra realistic, photorealistic, 8k, sharp focus, professional photography, natural skin texture, no plastic skin
```

**persona_anchors (her görselde aynı):**
```
25-year-old Turkish woman, shoulder-length wavy medium brown hair, hazel-brown almond eyes, warm fair skin, soft natural features, subtle friendly smile, casual-professional style
```

**lighting opsiyonları:**
- "soft natural daylight from window"
- "golden hour warm light"
- "cinematic soft studio lighting"
- "moody warm interior with indirect light"

**camera opsiyonları:**
- "shallow depth of field, f/1.8"
- "candid documentary style"
- "portrait orientation, eye-level perspective"
- "wide shot establishing scene"

**brand_consistency (her zaman):**
```
consistent character, same person across all images, recognizable by hair/face/style
```

### Negative prompt (her zaman)

```
plastic skin, over-smooth skin, exaggerated features, cartoon, anime, illustration, drawing, painting, oversaturated, vivid unrealistic colors, multiple people, wrong proportions, extra fingers, deformed hands, blurry face, watermark text other than VirtuAI, brand logos, religious symbols, political imagery
```

### Tam prompt örneği

```
ultra realistic, photorealistic, 8k, sharp focus, professional photography, natural skin texture, no plastic skin,
25-year-old Turkish woman, shoulder-length wavy medium brown hair, hazel-brown almond eyes, warm fair skin, soft natural features, subtle friendly smile,
sitting at home office desk in front of MacBook, coffee cup beside laptop, indie plants in background, books on desk,
wearing soft cream knit sweater,
soft natural daylight from window, warm interior atmosphere,
shallow depth of field f/2.0, candid documentary style, portrait crop,
focused productive mood,
consistent character with persona anchor, recognizable Cansu Dut

Negative: plastic skin, cartoon, anime, multiple people, deformed hands, watermark, brand logos
```

---

## 5. Real-Person Reference Images (Anchor Set)

### Consent + anchor set zorunlu

Cansu gerçek/var olan bir yüz olarak ilerleyecek. Bu yüzden görsel tutarlılık hattı
"kimlik doğrulama" yapmaz; yalnızca Berkay'ın sağladığı ve kullanımı onaylanmış
referans foto setine göre **visual consistency** kontrolü yapar.

**Referans foto protokolü:**
1. Berkay 5-10 consented Cansu referans fotoğrafını hazırlar.
2. Fotoğraflar `reference_anchor` asset olarak private bucket'a alınır; public final asset bucket'a konmaz.
3. Metadata zorunlu: `consent_confirmed=true`, `real_person_reference=true`, `do_not_publish=true`.
4. Raw referans foto ve embedding public response/publish payload içinde gösterilmez.
5. Embedding/cache adımı foto seti geldikten sonra yapılır.
6. Üretilen görseller "identity verification" değil, `visual_consistency_score` ile kontrol edilir.
7. Gerçek kişiye benzer her görsel canlı publish öncesi insan onayı ister.

**Anchor değişikliği:**
- Anchor set değişmesi = görsel tutarlılık baseline değişikliği
- Major version bump (manifest_version 1.0.0)
- Eski post'lar yeniden üretilmez (tutarsızlık kabul edilir)

### Aspect ratio matrisi (platform bazlı)

| Platform | Aspect Ratio | Çözünürlük (target) |
|---|---|---|
| LinkedIn (single image) | 1.91:1 | 1200×627 |
| LinkedIn (square) | 1:1 | 1200×1200 |
| Instagram (feed) | 1:1 | 1080×1080 |
| Instagram (story/reel) | 9:16 | 1080×1920 |
| Instagram (portrait) | 4:5 | 1080×1350 |
| Twitter/X | 16:9 | 1200×675 |
| YouTube Shorts thumbnail | 9:16 | 1080×1920 |
| Medium header | 16:9 veya 3:2 | 1400×787 |

---

## 6. Quality Gates

Visual Director'ın her output için pass etmesi gereken katmanlar:

### Layer 1: Pre-filter (ucuz, fast)

- **Image size check:** Min 1024×1024 px equivalent
- **Aspect ratio:** Doğru oran (post tipine göre)
- **Blur detection:** Laplacian variance > threshold
- **NSFW check:** OpenNSFW / safety check
- **Perceptual hash:** Önceki postlarla duplicate olmamalı

### Layer 2: OCR check

- **EasyOCR Türkçe:** Görsel içinde istenmeyen text yoksa
- Yasak text: brand logos, politika referansları, yanlış imla

### Layer 3: Visual consistency score

- Onaylı referans setine visual consistency score ≥ **0.85**
- Bu skor biyometrik kimlik doğrulama değildir; yalnızca consented reference set ile üretim tutarlılığını ölçer.
- **0.80-0.85 arası:** soft warning, manual review
- **<0.80:** AUTO_REJECT

### Layer 4: Aesthetic predictor

- LAION aesthetic predictor score
- Threshold: 0.65 (akademik araştırmalarla kalibrasyon Hafta 2-3'te)

### Layer 5: LLM-judge (gri zone için)

Eğer Layer 1-4 geçti ama compliance şüpheli (örn semi-NSFW gri zona):
- Sonnet 4.6 vision model ile final judge
- Sonuç: PASS / NEEDS_REVIEW / FAIL

---

## 7. AI Disclosure Görsel Watermark

Her image'ın sağ alt köşesinde (veya en uygun yerde):

```
Pozisyon: Bottom-right corner
Padding: 20px
Background: Semi-transparent black (rgba(0,0,0,0.6))
Text: "AI generated" (Inter font, 12px, white, regular weight)
Padding inside: 6px horizontal, 4px vertical
Border-radius: 4px
```

**İstisna:** Cinematic/aesthetic post'larda watermark görsel akışı bozarsa, alternatif:
- Sağ üst köşeye küçük 🤖 emoji etiketi (16x16px)
- Caption/post text'inde explicit AI mention

---

## 8. Brand Renkleri (Diagram/Technical content için)

### Primary palette

```
Background dark: #0a0a0a (rgb 10, 10, 10)
Background light: #f8f8f8 (rgb 248, 248, 248)
Accent (lime green): #BFFF00 (rgb 191, 255, 0)
Text dark: #1a1a1a
Text light: #fafafa
Muted: #6b7280 (Tailwind gray-500)
```

### Use case

- **Dark mode primary:** dashboard screenshot'ları, code diagram'ları
- **Lime accent:** highlight, link, key term
- **Avoid:** rainbow colors, pastel-only schemes, Halloween orange/black

---

## 9. Scene-to-Post Mapping

Writer agent post yazarken Visual Director'a brief verir. Brief format:

```yaml
scene_type: "home_office" | "coffee_shop" | "campus" | "cinematic_portrait" | "outdoor_istanbul" | "tutorial_pose" | "diagram"
mood: "focused" | "creative" | "contemplative" | "young_ambitious" | "introspective" | "educational"
outfit_tier: "casual_70" | "smart_casual_20" | "home_cozy_10"
lighting: "natural_daylight" | "golden_hour" | "studio_soft" | "moody_indoor"
aspect_ratio: "1:1" | "1.91:1" | "9:16" | "16:9" | "4:5"
priority_tier: 1 | 2 | 3 (model tier — Nano Banana Pro primary / Nano Banana 2 alternate / GPT Image 2 test)
```

Visual Director bu brief'i alır, prompt template'e doldurur, Wiro'ya gönderir.

---

## 10. Iteration & Improvement

- Her hafta üretilen görsellerden CLIP similarity dağılımı çıkar
- 0.80'in altına düşen görseller analiz et — prompt template'i iyileştir
- Anchor güncelleme:
  - Hafta 1-2: anchor v1
  - Hafta 4 sonu: aday anchor v2 (eğer iyileşme varsa)
  - Major version bump gerekli (visual identity değişikliği = persona evrim)

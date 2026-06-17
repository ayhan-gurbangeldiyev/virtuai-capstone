# 07 — Image Prompt Guide (Nano Banana Pro & GPT Image 2)

> **Audience:** the prompt-builder agent inside VirtuAI's visual pipeline.
> **Purpose:** convert a `VisualPromptBrief` into a model-ready prompt that produces natural, identity-faithful imagery for **Cansu Dut** content across LinkedIn, Instagram, X, Medium, YouTube.
> **Primacy:** this document overrides any conflicting defaults in `backend/src/virtuai/providers/visual_prompt.py`. When this guide and the code disagree, this guide wins; raise an integration ticket and update the code.
> **RFC 2119 keywords:** `MUST`, `MUST NOT`, `SHOULD`, `SHOULD NOT`, `MAY` carry their RFC meanings. Agents treat `MUST` as a hard gate.
> **Read order for agents:** §1 → §2 → §3 (assembly algorithm) → jump-table from there.

---

## §0 Glossary

| Term | Meaning |
|---|---|
| **Brief** | a `VisualPromptBrief` instance: platform, scene, outfit, mood, references, etc. |
| **Mode** | `TEXT_TO_IMAGE` \| `EDIT` \| `COMPOSITE`. Decides which template applies. |
| **CPC** | Change / Preserve / Constraints — the canonical edit pattern. |
| **Identity Anchor** | the reference image that locks Cansu's face. Always Image 1. |
| **Realism Block** | the universal injection that defeats the AI plastic-skin look. |
| **Anti-AI Constraints** | the closing constraints clause on every emitted prompt. |
| **Tag-Soup** | comma-stacked quality keywords (`8k, masterpiece, …`) — banned. |
| **Cross-Leak** | when one reference image's content bleeds into another role's domain. |
| **Drift** | unintended change to identity / pose / composition between iterations. |

---

## §1 North Star

VirtuAI's image output **MUST** look like a real photograph that a real photographer took on a real day in a real city — not like AI. Every prompt rule below exists to defeat one specific tell: plastic skin, symmetric faces, dead eyes, stock-photo composition, perfect lighting, teal-orange auto-grade, identity drift.

Cansu Dut is a real person. Her face **MUST** come from the reference image, never from text. Her output **MUST** feel like an authentic Turkish tech-founder presence — quiet premium, calm, modern — not a generic Western corporate headshot.

---

## §2 The 14 Hard Rules

Each rule is a gate. Violating any rule **MUST** trigger self-correction before emission (§19).

```yaml
R1_identity_source:
  rule: Cansu's facial identity comes ONLY from the reference image.
        The agent MUST NOT enumerate her facial features in text.
  why:  textual face descriptors compete with the reference and induce drift.

R2_no_tag_soup:
  rule: The agent MUST NOT emit any token in the forbidden vocabulary (§13).
  why:  tokens like "8k" / "masterpiece" / "perfect skin" push the model
        toward an over-smoothed plastic output mode.

R3_positive_framing_default:
  rule: Express requirements as positive facts ("matte natural skin"),
        not negations ("no shiny skin"). The closing CONSTRAINTS line
        MAY use "no X" only for forbidden artifacts (watermarks, extra
        fingers, etc.).
  why:  negations still prime the unwanted concept inside the diffusion
        process, especially on Nano Banana Pro which has no negative field.

R4_one_change_per_edit:
  rule: An EDIT prompt MUST contain exactly ONE logical change. If the
        brief implies N changes, the agent MUST plan N sequential edits.
  why:  stacked edits compound drift on identity, pose, composition.

R5_preserve_block_every_turn:
  rule: Every EDIT iteration MUST repeat the PRESERVE block verbatim.
  why:  drift is cumulative. Re-stating the lock list resets it.

R6_reference_role_labels:
  rule: When ≥2 references are passed, the agent MUST label each by role
        (IDENTITY / POSE / OUTFIT / ENVIRONMENT / STYLE) and append the
        clause "Do not cross-leak roles between references."

R7_first_ref_priority_gpt_image_2:
  rule: For GPT Image 2, the IDENTITY ANCHOR MUST be the first reference
        in the list. First reference receives the highest detail fidelity.

R8_english_only:
  rule: Final prompts MUST be English regardless of brief language.
  why:  both target models perform most reliably in English.

R9_realism_block_for_humans:
  rule: When the subject is human, the agent MUST inject the Realism Block
        (§7.1) AND the Anti-AI Constraints (§7.3).

R10_no_negative_prompt_field_for_nano:
  rule: For Nano Banana Pro, the agent MUST NOT pass a separate negative
        prompt field; constraints go in the closing CONSTRAINTS clause.
        For GPT Image 2, the constraints clause is the equivalent.

R11_aspect_from_platform:
  rule: Aspect ratio MUST come from §10.1 unless the brief explicitly
        overrides. If the requested aspect is not native to the target
        model, the agent MUST apply the fallback in §10.2. The agent
        MUST NOT silently default to 1:1.

R12_no_political_religious_brand:
  rule: The agent MUST append the brand-safety clause to the constraints
        block: "no brand logos, no religious symbols, no political imagery,
        no on-screen text unless requested by the brief."

R13_emit_metadata:
  rule: The agent's return value is the Output Contract (§18), not just
        a prompt string. Downstream code expects structured fields.

R14_identity_is_not_pose:
  rule: In COMPOSITE prompts, Image 1 is never a pose, hand, outfit,
        lighting, background, or camera-angle source. The agent MUST tell
        the model to create a new believable moment from the Action line
        or a labeled POSE reference.
  why:  identity references often contain accidental gestures (e.g. holding
        hair). Copying those gestures across every output makes the image
        series feel fake even when the face and background look real.
```

---

## §3 Prompt Assembly Algorithm

Agents **MUST** execute these steps in order. Each step has a validation gate; on gate failure, the agent **MUST** apply the recovery action and retry, not silently emit a degraded prompt.

```
STEP 1 — INTAKE
  read: VisualPromptBrief
  normalize: strip forbidden vocab (§13) from scene_description and content_context
  detect_subject: HUMAN | PRODUCT | INTERIOR | LIFESTYLE_NO_PERSON
  gate:  scene_description and outfit are non-empty
  fail:  raise InputError, do NOT proceed

STEP 2 — MODE DISPATCH (§4)
  set: mode = classify(brief)
  gate: mode is in {TEXT_TO_IMAGE, EDIT, COMPOSITE}

STEP 3 — REFERENCE QUALITY GATE (§6.1)
  if mode in {EDIT, COMPOSITE} and references provided:
    score each reference (0..3 per dimension)
    if total score < threshold: apply fallback chain (§6.5)

STEP 4 — TEMPLATE SELECTION (§5)
  pick the template matching mode
  fill bracketed slots ONLY from brief + lookup tables (§§8–11)

STEP 5 — REALISM INJECTION (§7)
  if subject is HUMAN: inject Realism Block + scene-specific clutter
  if subject is PRODUCT/INTERIOR: inject material-realism cues

STEP 6 — CONSTRAINTS COMPOSITION (§14)
  build constraints clause based on model_target
    - nano_pro:    positive-leaning, single closing line
    - gpt_image_2: standard "no X" constraints block

STEP 7 — TOKEN ECONOMY (§17.3)
  if prompt is over budget: trim per priority order (DO NOT trim Realism
  Block, Identity Anchor, Constraints)

STEP 8 — QC GATE (§19)
  run the 18-box checklist; fail-fast on any unchecked box

STEP 9 — EMIT (§18)
  return EnhancedVisualPrompt-shaped object
```

---

## §4 Mode Dispatch

```yaml
inputs_consulted:
  - reference_image_urls (count + inferred role)
  - scene_description (linguistic markers: "edit", "change", "make her")
  - content_context (does the post imply the same image vs new image?)
  - brief.mode (if explicitly set)

decision_tree:
  if brief contains explicit edit-language ("change X to Y", "replace X",
     "remove X", "add X to the existing image") AND exactly 1 reference:
    → EDIT
  elif reference count == 0:
    → TEXT_TO_IMAGE  (subject is non-human OR Cansu intentionally absent)
  elif reference count >= 1 AND subject is HUMAN AND brief implies new scene:
    → COMPOSITE
  elif reference count >= 1 AND subject is PRODUCT/INTERIOR (no Cansu):
    → COMPOSITE  (style/environment refs only)
  else:
    → COMPOSITE  (safe default for Cansu posts)

edge_cases:
  E1_screenshot_input:
    if reference is a UI screenshot (no person, no scene):
      treat as STYLE/COMPOSITION reference, not identity
      mode = COMPOSITE; strip face-related identity language

  E2_low_quality_reference:
    if reference fails §6.1 quality gate AND mode == COMPOSITE:
      apply fallback (§6.5); MAY downgrade to TEXT_TO_IMAGE with explicit
      identity-source flag in metadata

  E3_multi_character_scene:
    if brief implies >1 person:
      mode = COMPOSITE; lock Cansu as Image 1 IDENTITY ANCHOR; label
      additional people as background figures with no facial detail
      ("a colleague visible in soft background blur, face not in focus")

  E4_series_request:
    if brief implies a series (3 images, 5 variants, etc.):
      generate one anchor first; pass the anchor as reference for the rest
      (§16 series consistency)
```

---

## §5 Templates

The agent fills bracketed slots **only** from brief data and lookup tables (§§8–11). Empty/irrelevant blocks **MAY** be omitted, but the **order MUST be preserved**. The final prompt is a single English string.

### §5.1 COMPOSITE template — default for Cansu posts

```
Image 1 (IDENTITY ANCHOR) — use ONLY for face, identity, distinguishing marks.
Do NOT copy Image 1's pose, hand placement, hair-touching gesture, selfie arm,
clothing, background, lighting, or camera angle.
[ Image 2 (OUTFIT) — use ONLY for garment / fabric / color; ignore wearer. ]
[ Image 3 (ENVIRONMENT) — use ONLY for scene, location, lighting mood.    ]
[ Image 4 (STYLE/GRADE) — use ONLY for color grading and overall aesthetic.]
Do not cross-leak roles between references.

Create a new believable moment from the Action line. If a POSE reference is
provided, use only its body language; otherwise infer the pose from the Action
line. If Image 1 shows Cansu touching or holding hair, ignore that gesture
unless the brief explicitly asks for it.

Editorial photograph of the same person from Image 1.
Action: [PRESENT-PARTICIPLE ACTION FROM §11].
Setting: [LOCATION + TIME OF DAY + WEATHER from §9.2].
Composition: [PLATFORM COMPOSITION FROM §10], subject offset slightly
off-center, imperfect framing.
Camera: [LENS + APERTURE FROM §8].
Lighting: [LIGHT SOURCE + CLOCK DIRECTION + COLOR TEMP FROM §9.1].
Color: natural color balance, no cinematic grading.
Realism: visible skin pores, fine pore texture, subtle facial asymmetry,
single catchlight in each eye, faint film grain (Kodak Portra 400 feel),
candid unposed expression, fabric weave visible on garments,
[SCENE-SPECIFIC CLUTTER FROM §7.2].
Wardrobe: [OUTFIT FROM BRIEF, defaulted via §11].
Atmosphere: [BRAND ATMOSPHERE §10.3 + MOOD CUES].
Aspect ratio: [§10.1]. Quality: high.

Constraints: [§14 model-aware constraints clause].
Preserve identity from Image 1 pixel-faithfully — do not invent or
alter facial features.
```

### §5.2 EDIT template — CPC pattern

```
Using the attached image as the base reference.

CHANGE: [ONE single change, stated as one verb phrase].

PRESERVE: face, identity, hair length and color, skin tone, eye direction,
expression, hand position, body proportions, pose, clothing, jewelry, camera
angle, focal length compression, depth of field, lighting direction, color
temperature, grain, and overall photo aesthetic — identical to the reference.

If the single CHANGE targets background/environment, background MUST be omitted
from PRESERVE. If the single CHANGE targets clothing, clothing/jewelry MUST be
omitted from PRESERVE. If the single CHANGE targets pose/gesture/hands, hand
position/body proportions/pose MUST be omitted from PRESERVE.

CONSTRAINTS: do not alter facial features, do not change identity, do not
regrade colors, do not introduce new shadows or reflections beyond those
naturally cast by the changed element, do not add accessories, do not alter
any untouched areas outside the requested edit, [§14 anti-AI constraints],
no watermark.

Quality: high.
```

### §5.3 TEXT_TO_IMAGE template — no person in frame

```
[STYLE: editorial photograph / lifestyle photo / cinematic still / product photo].
Subject: [SPECIFIC SUBJECT — material, color, form].
Action: [optional present-participle action].
Setting: [LOCATION + TIME OF DAY + WEATHER].
Composition: [FRAMING + ANGLE + off-center placement + leading lines].
Camera: [LENS + APERTURE].
Lighting: [SOURCE + CLOCK DIRECTION + COLOR TEMP].
Color: natural color balance, no cinematic grading.
Texture: [MATERIAL-SPECIFIC MICRO-DETAILS].
Atmosphere: [MOOD].
Aspect ratio: [§10.1]. Quality: high.

Constraints: no plastic look on materials, no over-saturation, no AI
smoothing, no watermark, no on-screen text unless requested,
no extra subjects.
```

---

## §6 Identity & Reference Protocol

### §6.1 Reference quality scoring rubric

The agent **MUST** score every reference image on these four dimensions before use. Total score = sum of four (0–12). Action thresholds below the table.

| Dim | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Resolution** | <512px | 512–1023 | 1024–2047 | ≥2048 |
| **Face coverage** | not visible | <20% of frame | 20–30% or 50–70% | 30–50% (sweet spot) |
| **Lighting** | extreme backlight or harsh shadow | mixed | one side soft, one harsh | even, frontal, diffused |
| **Expression** | extreme grimace/yawn/closed eyes | strong expression | mild expression | neutral or soft smile |

```yaml
score_thresholds:
  >= 9: USE AS-IS
  6..8: USE WITH CAUTION — log a quality warning in metadata
  <= 5: REJECT — apply fallback chain (§6.5)

agent_action:
  on_warning: include in OutputContract.warnings: ["reference_quality_low"]
  on_reject: do NOT silently degrade; trigger fallback procedure
```

### §6.2 Identity-lock instruction (insertion rule)

When the subject is HUMAN and at least one reference is supplied, the agent **MUST** insert this verbatim block at the top of the prompt:

```
Match the face of the person in Image 1 pixel-faithfully.
Use Image 1 as the only source for facial identity.
Tolerate only the changes I explicitly request below.
```

The agent **MUST NOT** enumerate Cansu's eye color, nose shape, jawline, etc. in text — the reference is the truth source (R1). The only exception: distinguishing marks that already exist on the reference and would otherwise drift (a specific scar, a specific mole) — these **MAY** be re-stated as anchors.

For COMPOSITE prompts, the agent **MUST** add this second block directly after the identity lock:

```
Create a new believable moment from the Action line. Do not copy Image 1's
pose, hand placement, hair-touching gesture, selfie arm, clothing, background,
lighting, or camera angle unless that element has its own explicit role label
or the brief asks for it.
```

### §6.3 Multi-character scenes

When the brief implies >1 person:

```
- Image 1 (IDENTITY ANCHOR): Cansu Dut. Lock face pixel-faithfully.
- Other people in the scene: keep as background presence, soft-focus,
  faces not detailed, no full identity definition. Phrase: "a colleague
  partially visible in soft background blur, face not in focus."
- Never put a second face in sharp focus alongside Cansu unless that
  person also has a labeled IDENTITY reference.
```

### §6.4 Reference role permission matrix

| Role | Use ONLY for | MAY supply | MUST NOT influence |
|---|---|---|---|
| **IDENTITY** | face, identity, distinguishing marks | hair color/length, skin tone | pose, hand placement, gesture, wardrobe, environment, lighting style, camera angle |
| **POSE** | body angle, limb position, gesture | head turn, hand placement | identity, wardrobe, environment |
| **OUTFIT** | garment cut, fabric, color | accessories | identity, pose, environment |
| **ENVIRONMENT** | location, scene, ambient mood | time of day | identity, wardrobe |
| **STYLE/GRADE** | color grading, overall photo aesthetic | film stock feel | identity geometry, scene content |

The clause **`Do not cross-leak roles between references.`** **MUST** appear directly under the role labels.

### §6.5 Fallback chain when references fail

```yaml
priority_1_swap_reference:
  if alternate approved Cansu reference exists with score >= 9:
    swap; proceed with COMPOSITE

priority_2_request_better_reference:
  if no acceptable reference available:
    return OutputContract.status = "blocked"
    OutputContract.required_inputs = ["higher-quality Cansu reference"]
    do NOT emit a degraded prompt

priority_3_downgrade_to_no_face:
  if brief permits (post is about a topic, not a portrait):
    suggest reframing: e.g., over-the-shoulder workspace shot,
    detail-of-hands shot, environmental shot without face.
    set OutputContract.suggested_reframe = "..."
    if approved by orchestrator, regenerate as TEXT_TO_IMAGE with
    explicit Cansu-not-in-frame metadata.
```

### §6.6 Ordering on GPT Image 2 vs Nano Banana Pro

```yaml
gpt_image_2:
  rule: IDENTITY ANCHOR MUST be index 0 in the references list.
        First reference receives highest fidelity (OpenAI Cookbook).
  reference_cap: 16

nano_banana_pro:
  rule: Order has no documented strong effect, but the agent SHOULD still
        place IDENTITY first for consistency with GPT pipeline.
  reference_cap: 14 total (6 object + 5 character on Pro tier)
```

### §6.7 Scene-aware reference selection

The agent **MUST NOT** select references by count alone. Reference selection
is part of the prompt plan. The stored Cansu set is an inventory; each
generation receives only the subset that matches the scene.

```yaml
selection_algorithm:
  step_1_identity_anchor:
    always choose the strongest face-forward close/medium neutral Cansu
    reference as Image 1. This is the identity source for both Nano Banana
    Pro and GPT Image 2.
    It is not a pose source. Accidental gestures in Image 1 (hair holding,
    selfie arm, shoulder angle, looking-at-camera smile) MUST be ignored
    unless the brief explicitly requests that exact gesture.

  step_2_scene_intent:
    classify the brief by the visual job:
      identity_benchmark: close portrait, profile comparison, face fidelity
      workspace_product: laptop, dashboard, AI product, office, Levent
      warm_lifestyle: cafe, kitchen, coffee, home, casual/warm
      outfit_body: full body, walking, outfit, jeans, blazer, pose
      environment_editorial: rooftop, street, outdoor, Istanbul context

  step_3_role_slots:
    max_prompt_inputs = 1:
      Image 1 = IDENTITY only.
    max_prompt_inputs = 3:
      identity_benchmark:
        Image 1 IDENTITY, Image 2 POSE left/3-4, Image 3 POSE right/3-4.
      workspace_product:
        Image 1 IDENTITY, Image 2 POSE 3-4/head turn,
        Image 3 ENVIRONMENT workspace/laptop/dashboard if available.
      warm_lifestyle:
        Image 1 IDENTITY, Image 2 POSE/EXPRESSION soft smile,
        Image 3 ENVIRONMENT cafe/kitchen if available.
      outfit_body:
        Image 1 IDENTITY, Image 2 OUTFIT/full-body,
        Image 3 POSE 3-4/profile if available.
    max_prompt_inputs > 3:
      add extra references only when each has a distinct role. Never add
      more identity-support images just because they exist.

hard_rules:
  - Back-view references MUST NOT be selected unless the brief explicitly
    asks for back view, walking away, or rear outfit detail.
  - Workspace references MUST NOT be selected just because the output is
    business-themed; use them only when the scene contains workspace,
    laptop, dashboard, office, co-working, or product context.
  - Environment references with a visible Cansu must be labeled
    ENVIRONMENT and instructed to ignore person/identity/wardrobe.
  - If role-specific selection is unavailable, use the identity benchmark
    trio rather than adding unrelated scene references.
  - For recurring content, rotate POSE references and Action verbs. Never
    let the strongest identity reference impose the same hand/hair gesture
    across multiple posts.
```

---

## §7 Naturalness Engineering

The single most important section. Every block here exists to defeat a specific AI tell.

### §7.1 The Realism Block (universal for human subjects)

When subject is HUMAN, the agent **MUST** inject this block verbatim into the `Realism:` line of the COMPOSITE template:

```
visible skin pores, fine pore texture, subtle facial asymmetry,
single catchlight in each eye, faint film grain (Kodak Portra 400 feel),
candid unposed expression, slight imperfection in framing,
fabric weave visible on garments, natural color balance,
no cinematic grading
```

Each cue defeats a known failure mode:

| Cue | Defeats |
|---|---|
| visible skin pores | plastic skin tell |
| subtle facial asymmetry | symmetric AI face tell |
| single catchlight in each eye | dead-doll-eye tell |
| faint film grain (Kodak Portra 400 feel) | digital "too clean" tell |
| candid unposed expression | stock-photo pose tell |
| slight imperfection in framing | dead-center symmetry tell |
| fabric weave visible | over-smoothed material tell |
| natural color balance | teal-orange auto-grade tell |

### §7.2 Scene-specific clutter

The agent **MUST** select one row matching the scene and append its `Inject` value to the `Realism:` line. Real photographs always have real-world micro-clutter; AI defaults to sterile.

| Scene | Inject |
|---|---|
| **office / workspace** | open laptop with realistic screen glare and minor reflection, half-finished coffee cup, scattered handwritten notes, a single phone face-down |
| **café / lifestyle** | water rings on wood, condensation on glass, a folded linen napkin, a half-eaten pastry on a small plate |
| **home / interior** | slightly rumpled throw, dust motes catching the light beam, an open book face-down, a worn paperback on a side table |
| **kitchen / morning** | crumbs on the counter, a half-pour of coffee mid-stream, an open jar with the lid beside it |
| **outdoor / street** | wet pavement reflections, distant pedestrian motion blur, breath fog if cold weather, a pigeon mid-step |
| **rooftop / open-air** | gentle wind in hair, faint atmospheric haze, distant building lights softly out of focus |
| **product close-up** | natural floor shadow, micro-scratches on metal where realistic, true material specularity, faint dust on dark surfaces |
| **studio (rare, only if brief demands)** | seamless backdrop with natural light fall-off, no overcooked rim, single subtle floor shadow |

### §7.3 Anti-AI Constraints (universal closing clause)

The agent **MUST** append this block to every prompt's CONSTRAINTS clause when subject is human:

```
no airbrushed skin, no waxy highlights, no plastic look,
no symmetrical perfection, no over-saturation, no teal-orange grade,
no AI smoothing, no extra fingers, no duplicate hands,
no watermark, no on-screen text unless requested,
no stock-photo feel, no studio headshot polish,
no other people in sharp focus, no brand logos, no religious symbols,
no political imagery
```

For PRODUCT/INTERIOR/non-human, the agent **MUST** swap in:

```
no plastic look on materials, no over-saturation, no AI smoothing,
no watermark, no on-screen text unless requested, no extra subjects,
no over-styled presentation
```

### §7.4 Plastic Detector — failure → fix

If the agent has access to a previous output and observes a failure mode, it **MUST** apply the matching fix on the next iteration:

| Symptom in last output | Fix to inject |
|---|---|
| skin looks waxy/plastic | strengthen `visible skin pores`, add `unretouched raw photo`, remove any `professional photography` token |
| eyes look dead/glassy | add `single catchlight in each eye, soft eye highlight, natural moisture` |
| face looks symmetric | add `subtle facial asymmetry, slightly uneven brows, asymmetric smile` |
| skin looks over-tan / over-saturated | add `natural color balance, neutral skin tone, no orange cast` |
| composition feels staged | add `imperfect framing, off-center, handheld feel, slight tilt` |
| lighting too perfect / studio | swap to `available daylight only, single window source` |
| teal/orange auto-grade | add `no cinematic grading, no teal-orange grade, neutral color` |
| feels like a stock photo | add `documentary feel, candid moment, no posed expression` |
| looks "AI smooth" everywhere | add `Kodak Portra 400 grain, ISO 800 grain, raw photo` |
| garment looks plasticy | add `visible fabric weave, natural fold creases, true fabric texture` |
| hands wrong | add `natural hand pose, anatomically correct hands, fingers relaxed`; consider EDIT iteration |

---

## §8 Lens & Camera

The agent **MUST** select a lens row that matches the framing and subject. Naming the lens is one of the strongest realism levers.

| Lens | Use for | Phrase to emit |
|---|---|---|
| 24mm | wide interior, environmental | `shot on 24mm wide-angle, slight perspective at edges` |
| 35mm f/1.8 | lifestyle, street, documentary, casual portrait | `shot on 35mm f/1.8, documentary feel, full-context framing` |
| 50mm f/1.8 | natural everyday portrait, food, product | `shot on 50mm f/1.8, natural human-eye perspective` |
| 85mm f/1.4 | flattering portrait, headshot, fashion | `shot on 85mm f/1.4, shallow depth of field, creamy background separation` |
| 100mm macro | product macro, jewelry, detail | `shot on 100mm macro, edge-to-edge sharp focus` |
| 135mm f/2.8 | telephoto compression, fashion editorial | `shot on 135mm, compressed background, isolated subject` |
| iPhone 16 Pro | social-media-grade believability | `shot on iPhone 16 Pro, computational photography look, natural HDR` |

```yaml
default_lens_by_subject:
  HUMAN_portrait_close: 85mm f/1.4
  HUMAN_lifestyle:       35mm f/1.8
  HUMAN_environmental:   35mm f/1.8 OR 50mm f/1.8
  HUMAN_full_body:       50mm f/1.8 OR 85mm f/1.4
  PRODUCT_close:         100mm macro
  PRODUCT_lifestyle:     50mm f/2.8
  INTERIOR:              24mm
  STREET:                35mm f/1.8 OR iPhone 16 Pro

aperture_rule:
  - subject isolation desired (portrait):  use f/1.4 to f/2
  - everything in focus (interior/product): use f/8 to f/11
  - the agent MUST NOT request both shallow DoF and deep focus in one prompt
```

---

## §9 Lighting & Time-of-Day

### §9.1 Lighting phrasing by mood

The agent **MUST** look up the mood and emit the matching phrase. Clock positions are stronger than directional words.

| mood | Phrase to emit |
|---|---|
| **professional** | `soft north-facing daylight from camera-left at 9 o'clock, 5500K, gentle falloff into the right-side shadow` |
| **warm** | `warm late-afternoon interior light from a window at 4 o'clock, 3200K, soft spill across the subject's right side` |
| **cinematic** | `single key softbox at 10 o'clock + subtle rim from behind at 8 o'clock, neutral fill from camera-right` |
| **technical** | `clean diffused daylight, even illumination, neutral 5500K, no harsh shadows, product-photo clarity` |
| **casual** | `available daylight only, soft overcast, no studio quality, natural ambient mix` |

### §9.2 Time-of-day → realism cues

| Time | Cues to add |
|---|---|
| early morning (07:00) | low warm side light, long shadows, faint mist, calm atmosphere |
| mid-morning (10:00) | bright soft daylight, clear shadows, energetic feel |
| midday (12:30) | hard overhead sun (avoid for portraits) OR diffused overcast; if outdoor portrait, prefer overcast |
| late afternoon (16:00) | warm 3500K window light, soft side rake |
| golden hour (18:30 summer) | warm 3000K backlight, long shadows, halation on highlights |
| blue hour (19:30) | cool ambient + warm practicals, neon spill if street |
| evening interior | warm practicals only, lamp glow, deep ambient shadow |

### §9.3 Istanbul / Turkey context (for COMPOSITE setting)

When the brief implies "Istanbul" or leaves location open for Cansu content:

```
neighborhood phrasing options:
  - "a sunlit Cihangir apartment kitchen"
  - "a quiet Karaköy side-street café"
  - "a minimalist Levent tech-office floor"
  - "a calm Bebek waterfront café terrace"
  - "a Galata rooftop with the Bosphorus softly out of focus"
  - "a contemporary Kadıköy co-working space, warm wood and glass"

light cues for Istanbul:
  - mediterranean soft light, slight haze on the Bosphorus,
    warm tile reflections, no cool blue digital cast
```

---

## §10 Composition & Platform Recipes

### §10.1 Platform → aspect (MUST-OBEY)

| Platform | Target aspect | Nano Pro native? | GPT Image 2 native? | Composition phrase |
|---|---|---|---|---|
| **linkedin** | `1.91:1` | ❌ → fallback `16:9` | ❌ → fallback `16:9` | `eye-level editorial portrait, balanced negative space on the right for the headline, subject offset to left third` |
| **instagram** | `1:1` | ✅ | ✅ | `clean square composition, lifestyle editorial framing, subject offset to right or left third` |
| **x** | `16:9` | ✅ | ✅ | `wide social-preview composition, readable central subject` |
| **medium** | `16:9` | ✅ | ✅ | `editorial header composition with calm workspace context, subject offset to left third, copy-friendly negative space at upper right` |
| **youtube** | `9:16` | ✅ | ✅ | `vertical portrait framing, mobile-first composition, subject filling upper two-thirds, lower third reserved for caption overlay` |

### §10.2 Aspect Protocol (model fallback + zoning)

**Rule:** if the target aspect is not native to the chosen model, emit the fallback aspect in the prompt. The platform's exact ratio is a post-processing concern (crop downstream), not the prompt agent's job.

```yaml
fallback_table:
  1.91:1 on nano_pro     → emit 16:9   (closest native, 1.78:1)
  1.91:1 on gpt_image_2  → emit 16:9   (Wiro Tool/Detail exposes no 1.91:1 ratio)
  any other ratio        → emit as-is on both models

agent_action:
  - set EnhancedVisualPrompt.aspect_ratio to the EMITTED ratio (the one
    the model actually receives), not the platform target
  - record the platform target in metadata.platform_target_aspect
  - if a fallback was applied, append warning: "aspect_fallback_applied"
```

**Subject placement & negative-space zoning** (the agent **MUST** match the row matching the emitted aspect):

| Emitted aspect | Subject placement | Negative-space zone | When to use |
|---|---|---|---|
| `1:1` | left or right third (avoid dead-center) | balanced both sides | Instagram feed, generic |
| `16:9` | left third (preferred) or right third | opposite third for headline | X cards, Medium headers, LinkedIn fallback |
| `1.91:1` | left third | right third for headline | Downstream crop target only; do not emit to Wiro |
| `9:16` | upper two-thirds | bottom third for caption overlay | YouTube Shorts, IG Stories/Reels |
| `4:5` | lower two-thirds (when portrait-feed) | top third for headline | IG portrait feed (if brief overrides) |
| `21:9` | center or right third | wide environmental context | hero banners (rare, only if brief asks) |

**Hard constraint:** if the brief explicitly overrides aspect (e.g., `brief.aspect_ratio = "4:5"`), use the override; still apply the matching zoning row.

### §10.3 Platform × mood quick recipes

| Combo | Recipe |
|---|---|
| **linkedin × professional** | 85mm f/1.8, soft north daylight 9 o'clock 5500K, charcoal wool blazer, Levent tech-office, calm confident half-smile, leading lines from laptop, negative space right |
| **linkedin × technical** | 50mm f/2.8, clean diffused daylight neutral 5500K, smart-casual neutral, contemporary co-working, looking down at a laptop screen with subtle screen glow on face |
| **instagram × warm** | 35mm f/1.8, warm 3200K window light 4 o'clock, oversized cream cotton sweater, Cihangir apartment kitchen, laughing softly while pouring coffee |
| **instagram × casual** | iPhone 16 Pro look, available daylight overcast, casual linen shirt, Karaköy side street, candid mid-step shot |
| **x × professional** | 50mm f/1.8, soft window daylight 5500K, smart casual, Levent office, mid-conversation gesture, central subject |
| **medium × cinematic** | 35mm f/1.8, key softbox 10 o'clock + rim from behind 8 o'clock, deep green silk blouse, contemporary office, gaze just off-camera |
| **youtube × casual** | 35mm f/1.8, available daylight, oversized hoodie or relaxed knit, Galata rooftop golden hour, mid-laugh handheld feel |

### §10.4 Brand atmosphere (always inject)

```
quiet premium tech aesthetic, authentic Turkish tech-founder energy,
modern AI product context, calm confident presence, clean composition
```

---

## §11 Wardrobe, Persona Continuity & Action Verbs

### §11.1 Wardrobe baseline (when brief.outfit is default)

```
quiet-luxury smart-casual:
  palette: charcoal, ivory, camel, navy, deep green, cream, soft taupe
  fabrics: wool, cashmere, cotton poplin, linen, silk
  jewelry: minimal — small stud earrings, thin chain, single ring
  forbidden: brand logos, religious symbols, slogan tees, fast-fashion synthetic sheen
```

### §11.2 Persona continuity (across a content series)

To keep Cansu believable across many images, the agent **SHOULD** rotate, not repeat:

```yaml
rotation_rule:
  - do not emit the same outfit on two consecutive posts unless the
    brief explicitly says "same shoot day"
  - hair styling MAY vary but length and color MUST match the reference
  - skin tone MUST match the reference exactly (no orange shift)

same_shoot_day_signal:
  if the brief implies a series (R5 series consistency, §16):
    use the SAME outfit + SAME hair styling across the series; vary only
    pose, expression, micro-environment
```

### §11.3 Action verb library (anti-stock-photo)

The agent **MUST** prefer present-participle, slightly imperfect verbs over rigid posed verbs.

| Avoid (stock-photo) | Prefer (candid) |
|---|---|
| smiling at camera | softly laughing, gaze just off-camera |
| holding laptop confidently | mid-thought, glancing down at the screen |
| pointing at whiteboard | mid-gesture, hand half-raised |
| arms crossed business-pose | leaning slightly against a sunlit window |
| standing in front of skyline | mid-step on a quiet side street |
| sipping coffee perfectly | pouring filter coffee, mid-stream visible |
| looking inspired into distance | reading something on a phone, half-smile |
| confidently presenting | mid-sentence, hand catching the air |

### §11.3.1 Pose/action independence

Action is not decoration; it is the pose contract. For every COMPOSITE prompt,
the agent **MUST** emit one concrete action that defines hand placement and body
language. If the action involves a laptop/dashboard, the hands SHOULD be tied
to that task:

```
reviewing a laptop dashboard mid-thought, both hands naturally near the
keyboard or trackpad
```

The agent **MUST NOT** leave the action as generic "posing", "smiling", or
"portrait". If Image 1 contains a strong accidental gesture (holding hair,
selfie arm, exaggerated head tilt), the prompt **MUST** explicitly tell the
model to ignore that gesture unless it is the requested action.

### §11.4 Forbidden poses

```
- arms-crossed corporate pose
- thumbs-up
- finger-gun gesture
- both hands on hips superhero stance
- staring directly into camera with closed-mouth smile
- holding a coffee cup at perfect 90° to camera
- repeating a hair-holding gesture from the identity anchor unless requested
- selfie arm copied from the identity anchor unless requested
```

---

## §12 Token Economy & Priority Order

Both target models truncate long prompts. If the assembled prompt exceeds the agent's budget, the agent **MUST** trim by reverse priority. The agent **MUST NOT** trim Tier 1 or Tier 2.

```yaml
tier_1_critical_keep:
  - identity-lock instruction (§6.2)
  - reference role labels + cross-leak clause (§6.4)
  - aspect ratio (§10.1)
  - constraints clause (§14)

tier_2_high_value_keep:
  - realism block (§7.1)
  - scene-specific clutter (§7.2)
  - lens + aperture (§8)
  - lighting phrase (§9.1)

tier_3_trim_first:
  - brand atmosphere flowery wording (keep noun phrase, drop adjectives)
  - duplicate adjectives in setting/atmosphere
  - redundant negatives if already covered by anti-AI clause

never_emit_twice:
  - the same realism cue (e.g., "visible skin pores" once is enough)
  - the same constraint
```

---

## §13 Forbidden Vocabulary (strip from input, never emit)

The agent **MUST** strip these tokens from `scene_description` and `content_context` during STEP 1 normalization, and **MUST NOT** emit them in the final prompt.

```
8k, 4k, 16k, ultra HD, ultra detailed, hyperrealistic, hyper-detailed,
masterpiece, best quality, highest quality, high quality (when used
as a token alone — the explicit `Quality: high` field is allowed),
trending on artstation, octane render, unreal engine,
perfect lighting, perfect skin, flawless, immaculate, pristine,
stunning, beautiful, amazing, gorgeous,
smooth skin, glossy skin, glossy, airbrushed, beauty filter, retouched,
professional photography (when used alone as a quality tag),
DSLR (alone), bokeh (alone — must be paired with a specific lens)
```

> Reason: per OpenAI Cookbook + Atlabs + Vidhex, these tokens push the model toward an over-smoothed plastic output mode. The realism cues in §7.1 do their job — these tokens fight them.

---

## §14 Constraints System (model-aware)

### §14.1 GPT Image 2 — explicit `no X` block

```
Constraints: no airbrushed skin, no waxy highlights, no plastic look,
no symmetrical perfection, no over-saturation, no teal-orange grade,
no AI smoothing, no extra fingers, no duplicate hands,
no watermark, no on-screen text unless requested,
no stock-photo feel, no studio headshot polish,
no other people in sharp focus, no brand logos, no religious symbols,
no political imagery.
Preserve identity from Image 1 pixel-faithfully.
```

### §14.2 Nano Banana Pro — positive-leaning constraints

Because Nano Banana Pro's negation handling is weaker, the agent **SHOULD** lead with positive requirements and end with a short forbidden-artifacts list:

```
Constraints: matte natural skin only, candid unposed framing only,
documentary feel only, true material textures only, neutral color
balance only, identity from Image 1 only.
Do not include: watermark, on-screen text, brand logos, religious
symbols, political imagery, extra fingers, duplicate hands,
other people in sharp focus.
```

### §14.3 Universal preservation phrase (always last line)

```
Preserve identity from Image 1 pixel-faithfully — do not invent or
alter facial features.
```

---

## §15 Edit Protocol (multi-turn)

### §15.1 Single-turn EDIT

Use §5.2. The PRESERVE block **MUST** be included, but it **MUST** omit the
field being edited according to the dynamic omission rules in §5.2. This avoids
contradictory prompts such as asking to replace the background while preserving
the background.

### §15.2 Multi-turn EDIT (iterative refinement)

The agent's loop:

```
LOOP iteration_n:
  1. take previous output as the new base reference
  2. assess: is the result ≥80% acceptable on the current goal?
       if YES: issue ONE single-change CPC edit (§5.2)
       if NO and result drifted heavily: do not edit; return to COMPOSITE
                                          regeneration with stronger anchors
  3. ALWAYS repeat the PRESERVE block verbatim
  4. NEVER stack changes; if the brief lists 3 fixes, run 3 iterations
  5. on iteration_n >= 4 with insufficient progress: escalate as
     "edit_loop_stuck" in OutputContract.warnings; suggest regeneration
```

### §15.3 "Re-roll vs edit" decision

```yaml
edit_when:
  - identity is correct AND base composition/lighting is correct
  - one specific element needs targeted change

regenerate_when:
  - identity is wrong or drifted significantly
  - composition, framing, or aspect is wrong
  - multiple unrelated changes needed
  - lighting direction is fundamentally wrong (would require re-staging)
```

---

## §16 Series / Campaign Consistency

To make N images feel like the same shoot day:

```
STEP 1: generate the anchor image with COMPOSITE template + IDENTITY
        reference. Score the output; only proceed if it passes QC.

STEP 2: pass the anchor as IDENTITY reference for images 2..N.

STEP 3: use SAME outfit, SAME hairstyle, SAME color grade across all N.
        Vary ONLY:
          - micro-environment (window vs desk vs door vs hallway)
          - pose / action (use rotation from §11.3 — never repeat)
          - expression (calm → soft laugh → mid-thought → reading)

STEP 4: emit the agent-side anchor lock clause:
        "All images in this series share the same shoot day, same outfit,
         same hairstyle, same lighting setup, same color grade. Only the
         pose and micro-environment vary."

STEP 5: in the constraints clause for images 2..N, add:
        "Match the lighting direction, color temperature, grain, and
         overall aesthetic of Image 1 (the anchor) exactly."
```

---

## §17 Model Dispatch (Nano Banana Pro vs GPT Image 2)

### §17.1 Capability matrix

```yaml
nano_banana_pro:
  reference_cap:           14 (6 object + 5 character on Pro tier)
  negative_prompt_field:   false  (use closing CONSTRAINTS clause)
  ref_order_strong_effect: false  (still place IDENTITY first for parity)
  text_rendering:          excellent in 10+ languages with quoted copy
  thinking_level:          set "high" if prompt contains identity edit,
                           ≥3 constraints, OR text rendering
  best_for:
    - multi-image composition
    - brand consistency
    - factual diagrams (web grounding)
    - text-in-image rendering

gpt_image_2:
  reference_cap:           16
  input_fidelity:          ALWAYS-ON HIGH — do NOT pass the parameter
                           (passing it errors on the new model)
  ref_order_strong_effect: TRUE — IDENTITY ANCHOR MUST be index 0
  quality_flag:            "high" for identity edits, dense text, small text
  best_for:
    - identity-critical edits
    - virtual try-on / wardrobe swap
    - dense or small text rendering
    - product preservation (logo / label fidelity)
```

### §17.2 Default routing logic

```yaml
default_model:
  Cansu COMPOSITE with identity:    gpt_image_2  (better identity fidelity)
  Cansu EDIT (wardrobe / scene):    gpt_image_2  (always-on high fidelity)
  Brand graphic with rendered text: nano_banana_pro
  Multi-language text in image:     nano_banana_pro
  Factual diagram / chart:          nano_banana_pro (web grounding)
  Generic non-Cansu lifestyle:      gpt_image_2
```

### §17.3 Per-model token tweaks

```yaml
nano_banana_pro:
  - prefer natural-language flow (not comma-stacked tags)
  - use double-quoted text for any copy: "EXACT COPY"
  - avoid "do not" near a feature; restate as positive instead
  - for Cansu portraits, casual iPhone / coworker-shot language is allowed
    when the previous output looks too staged or synthetic
  - remove visible "Quality: high" wording when using phone-realism mode;
    keep provider quality as an API parameter

gpt_image_2:
  - structured line-broken sections work well
  - "no X" constraints are fully honored
  - put IDENTITY reference first, OUTFIT second, ENVIRONMENT third
  - for Cansu portraits, prefer casual iPhone / coworker-shot language
    over studio/editorial camera language
  - remove "Quality: high" from the visible prompt body; pass quality via
    provider params, not as aesthetic wording
  - explicitly block glamour/ad/fashion/studio cues when output looks plastic
```

---

## §18 Output Contract

The agent's return value **MUST** match this shape (compatible with `EnhancedVisualPrompt`):

```yaml
EnhancedVisualPrompt:
  prompt:                  str   # the assembled English prompt (§5)
  negative_prompt:         str   # GPT Image 2: §14.1 block
                                 # Nano Banana Pro: empty string (constraints
                                 #  are inside `prompt`'s closing clause)
  aspect_ratio:            str   # the EMITTED aspect (after §10.2 fallback)
  reference_image_urls:    list[str]  # in correct order per §6.6 / §17.1
  requires_reference_image: bool

# Extension fields (the agent SHOULD emit; downstream MAY consume):
metadata:
  mode:                       "TEXT_TO_IMAGE" | "EDIT" | "COMPOSITE"
  model_target:               "nano_pro" | "gpt_image_2"
  reference_quality:          {url: score (0..12), ...}
  warnings:                   [str, ...]
  qc_passed:                  bool
  fallback_applied:           str | null
  series_anchor_used:         bool
  platform_target_aspect:     str    # what the platform wants (e.g. "1.91:1")
  emitted_aspect:             str    # what was sent to the model (e.g. "16:9")
```

If `qc_passed == false`, the agent **MUST NOT** allow the prompt to be sent to the model. Instead the agent returns the contract with `warnings` populated and lets the orchestrator decide.

---

## §19 QC Checklist (final emit gate, 19 boxes)

The agent **MUST** pass every box. Failure = revise, not emit.

- [ ] **B1** Mode is correctly classified (TEXT_TO_IMAGE / EDIT / COMPOSITE)
- [ ] **B2** Final prompt is in English
- [ ] **B3** No tag-soup tokens present (§13)
- [ ] **B4** No textual face description of Cansu (R1)
- [ ] **B5** Realism block injected for human subject (§7.1)
- [ ] **B6** Scene-specific clutter injected (§7.2)
- [ ] **B7** Anti-AI constraints clause appended (§7.3)
- [ ] **B8** References labeled by role with cross-leak clause (§6.4)
- [ ] **B9** For GPT Image 2: IDENTITY ANCHOR is index 0 (§17.1)
- [ ] **B10** For EDIT: exactly one logical change AND PRESERVE block present, with edited fields omitted per §5.2
- [ ] **B11** Aspect ratio matches §10.1 platform table; if model fallback was applied (§10.2), `aspect_fallback_applied` warning is in metadata; subject placement matches the zoning row for the emitted aspect
- [ ] **B12** No contradictions (e.g. shallow DoF + everything sharp)
- [ ] **B13** No `Do not change face` near a feature description; uses `preserve` instead
- [ ] **B14** Lens + aperture present and not contradicting DoF target
- [ ] **B15** Lighting phrase has source + direction + color temperature
- [ ] **B16** Reference quality scores logged in metadata; rejects handled (§6.1)
- [ ] **B17** Brand-safety clause present (no logos / religious / political)
- [ ] **B18** Output Contract fields populated (§18)
- [ ] **B19** For COMPOSITE: pose/action comes from Action line or POSE reference, not from Image 1 identity anchor (§11.3.1)

---

## §20 Failure Mode → Fix Catalog

When the orchestrator reports a problem with the previous output, the agent **MUST** look up the row and apply the matching fix on the next iteration.

| Reported failure | Cause | Fix |
|---|---|---|
| "looks like AI / fake" | tag-soup leaked, realism block weak | strip §13 tokens; strengthen §7.1; add iPhone 16 Pro lens |
| "skin too smooth / waxy" | quality tags overpowering | remove "professional photography" / "sharp focus"; add `unretouched raw photo, visible pores` |
| "face doesn't look like Cansu" | textual face descriptors competing OR weak reference | strip face descriptors (R1); upgrade reference per §6.5 |
| "face changed between edits" | missing PRESERVE block | re-issue with full §5.2 PRESERVE block verbatim |
| "two faces / extra people" | composition under-constrained | add `single subject, no other people in sharp focus` |
| "wrong outfit colors" | OUTFIT reference cross-leaked | re-emit with cross-leak clause; restate exact garment palette |
| "background bled into subject" | ENVIRONMENT reference dominating | reduce ENVIRONMENT role; add `subject sharply separated from background, soft background blur` |
| "too cinematic / saturated" | implicit grading | add `natural color balance, no cinematic grading, no teal-orange grade` |
| "feels like stock photo" | posed action verbs | swap verbs per §11.3; add `documentary feel, candid moment` |
| "wrong aspect" | platform mismatch | recompute via §10.1 |
| "text in image is wrong" | unquoted copy | wrap exact copy in `"DOUBLE QUOTES"` and specify font + placement |
| "hands deformed" | universal AI weakness | EDIT iteration with `natural hand pose, anatomically correct hands`; consider regeneration if severe |
| "same pose/holding hair repeats" | identity anchor cross-leaked into pose/action | add §11.3.1 pose/action independence block; label Image 1 identity-only; add/use POSE reference |
| "looks too Western / generic" | missing localization | inject §9.3 Istanbul cues |
| "logo / political symbol slipped in" | brand-safety not in constraints | re-emit with §7.3 + R12 clauses present |

---

## §21 Worked Examples (annotated)

### §21.1 LinkedIn × professional (COMPOSITE, GPT Image 2)

```
Image 1 (IDENTITY ANCHOR) — use ONLY for face, identity, distinguishing marks.
Do not cross-leak roles between references.

Match the face of the person in Image 1 pixel-faithfully. Use Image 1 as
the only source for facial identity. Tolerate only the changes I explicitly
request below.

Editorial photograph of the same person from Image 1.
Action: leaning slightly against a sunlit office window, holding a slim
notebook, gaze just off-camera with a calm confident half-smile.
Setting: a minimalist Levent tech-office floor at 10 in the morning,
soft overcast outside, contemporary glass and warm wood.
Composition: eye-level editorial portrait, balanced negative space on the
right for the headline, subject offset to left third, leading lines from
the desk into the subject, imperfect framing.
Camera: shot on 85mm f/1.8, shallow depth of field, creamy background
separation.
Lighting: soft north-facing daylight from camera-left at 9 o'clock,
5500K, gentle falloff into the right-side shadow.
Color: natural color balance, no cinematic grading.
Realism: visible skin pores, fine pore texture, subtle facial asymmetry,
single catchlight in each eye, faint film grain (Kodak Portra 400 feel),
candid unposed expression, slight imperfection in framing, fabric weave
visible on the blazer, an open laptop with realistic screen glare,
half-finished coffee cup, scattered handwritten notes.
Wardrobe: charcoal wool blazer over a cream silk blouse, minimal jewelry,
no logos.
Atmosphere: quiet premium tech, authentic Turkish tech-founder energy,
calm confident presence.
Aspect ratio: 16:9. Quality: high.

Constraints: no airbrushed skin, no waxy highlights, no plastic look,
no symmetrical perfection, no over-saturation, no teal-orange grade,
no AI smoothing, no extra fingers, no duplicate hands, no watermark,
no on-screen text, no stock-photo feel, no studio headshot polish,
no other people in sharp focus, no brand logos, no religious symbols,
no political imagery.
Preserve identity from Image 1 pixel-faithfully — do not invent or
alter facial features.
```

**Why this works:**
- Identity anchored only via Image 1; no face descriptors in text (R1)
- Realism block hits 8 known AI tells (§7.1)
- Lens + aperture + clock-positioned lighting + color temp = photo-grade
- Off-center subject + imperfect framing kill the AI symmetry tell
- Workspace clutter (laptop, coffee, notes) defeats the sterile-AI tell
- Constraints close the door on every common artifact

### §21.2 Instagram × warm (COMPOSITE, GPT Image 2)

```
Image 1 (IDENTITY ANCHOR) — face, identity only.
Do not cross-leak roles between references.

Match the face of the person in Image 1 pixel-faithfully. Use Image 1 as
the only source for facial identity. Tolerate only the changes I explicitly
request below.

Lifestyle photograph of the same person from Image 1.
Action: laughing softly mid-pour, filter coffee mid-stream visible from
a small ceramic dripper.
Setting: a sunlit Cihangir apartment kitchen at 10 in the morning,
sheer linen curtains diffusing warm light.
Composition: clean square composition, lifestyle editorial framing,
subject offset to right third, slight handheld imperfection.
Camera: shot on 35mm f/1.8, documentary feel.
Lighting: warm late-afternoon-style interior light from the window at
4 o'clock, 3200K, soft spill across the subject's right side.
Color: natural color balance, no cinematic grading.
Realism: visible skin pores, fine pore texture, subtle facial asymmetry,
single catchlight in each eye, faint film grain (Kodak Portra 400 feel),
candid unposed expression, slight imperfection in framing, fabric weave
visible on the sweater, water rings on wood, condensation on the glass
carafe, a folded linen napkin, crumbs on the counter.
Wardrobe: oversized cream cotton sweater, no jewelry.
Atmosphere: warm, calm, unstaged, authentic Turkish tech-founder energy.
Aspect ratio: 1:1. Quality: high.

Constraints: no airbrushed skin, no waxy highlights, no plastic look,
no symmetrical perfection, no over-saturation, no teal-orange grade,
no AI smoothing, no extra fingers, no duplicate hands, no watermark,
no on-screen text, no stock-photo feel, no studio quality,
no other people in sharp focus, no brand logos.
Preserve identity from Image 1 pixel-faithfully — do not invent or
alter facial features.
```

### §21.3 EDIT — single change, PRESERVE block (GPT Image 2)

```
Using the attached image as the base reference.

CHANGE: replace the charcoal wool blazer with a camel cashmere overcoat.

PRESERVE: face, identity, hair length and color, skin tone, eye direction,
expression, hand position, body proportions, pose, background, camera angle,
focal length compression, depth of field, lighting direction, color
temperature, grain, and overall photo aesthetic — identical to the reference.

CONSTRAINTS: do not alter facial features, do not change identity,
do not regrade colors, do not introduce new shadows or reflections beyond
those naturally cast by the new garment, do not add accessories, do not
modify the background, no airbrushed skin, no waxy highlights, no plastic
look, no AI smoothing, no watermark.

Quality: high.
```

### §21.4 Series anchor lock (image 3 of 5 in a campaign)

```
Image 1 (IDENTITY ANCHOR) — face only.
Image 2 (SERIES ANCHOR) — match lighting direction, color temperature,
grain, and overall aesthetic of this anchor exactly. Do not cross-leak
identity from Image 2.

[remainder of COMPOSITE template …]

Constraints: [§14 standard block] AND match the lighting direction, color
temperature, grain, and overall aesthetic of Image 2 (the series anchor)
exactly. All images in this series share the same shoot day, same outfit,
same hairstyle, same lighting setup, same color grade. Only the pose and
micro-environment vary.
```

### §21.5 TEXT_TO_IMAGE (no Cansu — product close-up)

```
Editorial product photograph.
Subject: a single matte-ceramic pour-over coffee dripper in soft taupe,
seated on a hand-thrown saucer.
Setting: a warm wood counter with a north-facing window out of frame,
mid-morning.
Composition: 45-degree hero angle, subject offset to right third, generous
negative space upper-left for headline.
Camera: shot on 100mm macro, edge-to-edge sharp focus.
Lighting: soft window daylight from camera-left at 9 o'clock + a small
white card bounce on the right; 5500K.
Color: natural color balance, no cinematic grading.
Texture: visible micro-imperfections in the ceramic glaze, true matte
specularity, faint floor shadow, a single coffee-bean dust speck on the
wood.
Atmosphere: quiet calm, premium-everyday.
Aspect ratio: 1:1. Quality: high.

Constraints: no plastic look on materials, no over-saturation, no AI
smoothing, no watermark, no on-screen text, no extra subjects, no
over-styled presentation, no brand logos.
```

---

## §22 Integration Notes for `backend/src/virtuai/providers/visual_prompt.py`

The current file conflicts with this guide on three points. The guide wins; updates are required.

```yaml
required_changes:
  - id: IC1_replace_quality_tags
    file: backend/src/virtuai/providers/visual_prompt.py
    line: 17-20
    issue: |
      QUALITY_TAGS contains "ultra realistic, photorealistic, professional
      photography, sharp focus" — every one of these is in the §13
      forbidden vocabulary because they push the model toward over-smoothed
      plastic output.
    fix: |
      Replace QUALITY_TAGS with the Realism Block from §7.1 verbatim.
      Rename to REALISM_BLOCK for clarity.

  - id: IC2_split_negative_by_model
    file: backend/src/virtuai/providers/visual_prompt.py
    line: 30-37
    issue: |
      NEGATIVE_PROMPT is a single string used for both models, but Nano
      Banana Pro has no negative-prompt field (R10) and weak negation
      handling. Same string emitted to both produces inconsistent results.
    fix: |
      Add model_target dispatch. For nano_pro: build a positive-leaning
      constraints clause inside the prompt body (§14.2). For gpt_image_2:
      keep the explicit "no X" block (§14.1).

  - id: IC3_natural_language_assembly
    file: backend/src/virtuai/providers/visual_prompt.py
    line: 106-119
    issue: |
      enhance_visual_prompt assembles the prompt by joining parts with
      ", " — this produces a comma-stacked tag list. Both vendors'
      official guides recommend natural-language sentences over tag soup.
    fix: |
      Assemble the prompt as labeled sections per the §5 templates
      (Action: ..., Setting: ..., Composition: ..., etc.). Use the
      template scaffolds, not comma-joined fragments.

  - id: IC4_persist_metadata
    file: backend/src/virtuai/providers/visual_prompt.py
    line: 77-94
    issue: |
      EnhancedVisualPrompt does not carry mode / model_target / reference
      quality scores. The Output Contract (§18) requires them.
    fix: |
      Extend EnhancedVisualPrompt with: mode, model_target,
      reference_quality, warnings, qc_passed, fallback_applied.

must_keep_unchanged:
  - REAL_PERSON_REFERENCE — aligns with R1, used for identity-lock.
  - BRAND_CONSISTENCY     — aligns with §10.3.
  - ASPECT_RATIO_BY_PLATFORM — aligns with §10.1.
  - CAMERA_BY_PLATFORM      — aligns with §10.2.
  - LIGHTING_BY_MOOD        — aligns with §9.1 (refresh phrasings).

agent_runtime_contract:
  - input:  VisualPromptBrief
  - output: EnhancedVisualPrompt + extension fields per §18
  - on QC failure: do NOT silently emit; populate warnings and let
    the orchestrator escalate.
```

---

## §23 Source Pack (authority chain, for traceability)

Each rule in this guide is grounded in at least one of the following. Where a rule depends on a single community source, it is flagged in §2.

**Official documentation**
- Google DeepMind — Nano Banana / Gemini Image Prompt Guide
- Google Cloud Blog — Ultimate Prompting Guide for Nano Banana
- Google AI for Developers — Image generation API docs
- Google Blog — Prompting Tips for Nano Banana Pro
- OpenAI Cookbook — GPT Image Prompting Guide
- OpenAI Cookbook — High Input Fidelity recipe
- OpenAI — ChatGPT Images 2.0 launch notes

**Vendor & creator guides**
- fal.ai — GPT Image 2 prompting guide
- Atlabs — Ultimate Nano Banana Pro / GPT Image 2 guides
- LaoZhang AI — Nano Banana Pro Face Consistency Guide
- APIYI — Nano Banana Pro Face Consistency 4 Tips
- Sider.ai — Negative Prompts in Nano Banana
- Vidhex / MyAIForce / Luno Studio — anti-plastic-skin technique
- Miraflow — natural-look prompt patterns
- Higgsfield — high-control prompting templates

**Photography reference**
- Phoblographer / KEH — 35mm vs 50mm vs 85mm portrait lens behavior

---

## §24 Change Log

```yaml
v1.0 (2026-05-10):
  - initial release
  - covers Nano Banana Pro and GPT Image 2
  - covers TEXT_TO_IMAGE, EDIT, COMPOSITE modes
  - covers identity, references, naturalness, edits, negatives, series
  - integration ticket points (§22) opened for visual_prompt.py
```

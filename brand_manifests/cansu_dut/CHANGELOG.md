# Brand Manifest Changelog

All notable changes to the brand manifest are documented here. Versioning follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-05-07

### Added

- Initial brand manifest skeleton for **Cansu Dut** persona
- `persona.md` — full Cansu Dut profile (25, İstanbul, Bahçeşehir AI Engineering senior student, AI/ML primary niche)
- `voice.md` — platform-specific voice rules (LinkedIn professional-soft, Twitter casual-witty, Instagram visual-led, YouTube Shorts conversational, Medium technical blog)
- `visual.md` — Nano Banana Pro primary style guide (ultra realistic primary + cinematic + diagram tertiary)
- `compliance.md` — 8 banned topics + AI disclosure platform-specific standard
- `platforms/linkedin.md` — Tier 1 priority, 3 posts/week, professional-soft tone
- `platforms/instagram.md` — Tier 1 priority, 3 posts/week, visual-led
- `platforms/twitter.md` — Tier 1 priority, 5 posts/week, casual-witty + #AIcreated mandatory
- `platforms/youtube-shorts.md` — Tier 2 priority, Phase 2 (Week 4-5), video pipeline
- `platforms/medium.md` — Tier 3 priority, Phase 3 (Week 5), long-form blog
- `examples.md` — 17 few-shot examples across 5 platforms (RAG embedding ready)
- `schema.py` — Pydantic validator for CI gate

### Decision Reference

This manifest reflects decisions from:
- `01-Teknik-Plan.md` (technical architecture)
- `02-Ekip-Kararlari.md` (team decisions)
- `03-Is-Paketleri.md` (work packages)
- `2026-05-07 debate session` ([final-report.md](../docs/debates/2026-05-07-virtuai-capstone-start/final-report.md))
- Persona interview Q&A (8 questions, 2026-05-07)

### Open Items (to be finalized)

- [ ] Persona anchor visual generation (Nano Banana Pro `cansu_anchor_v1.webp`)
- [ ] CLIP baseline embedding for anchor (`anchors/cansu_anchor_v1.embedding.npy`)
- [ ] Wiro voice profile selection (Wiro MiniMax voice ID for Cansu)
- [ ] CHANGELOG updates per content pillar performance review (Week 4 retrospective)

### Versioning Rules

- **Patch (0.1.0 → 0.1.1):** typo, wording improvement, minor clarification
- **Minor (0.1.0 → 0.2.0):** new fields, new examples, niche expansion, new content pillar
- **Major (0.1.0 → 1.0.0):** persona core change (name, niche, value system, visual identity)

Each version bump requires:
1. Git commit with descriptive message
2. CHANGELOG entry (this file)
3. CI gate pass (`python brand_manifest/schema.py ci`)
4. Audit log entry (DB)

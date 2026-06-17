# Brand Manifest — Cansu Dut

> **Canonical persona definition for VirtuAI capstone project.**
> All agents and pipelines derive their context package from these files.
> Git canonical, DB runtime mirror.

## Structure

```
brand_manifest/
├── README.md             # This file
├── CHANGELOG.md          # Version history
├── persona.md            # Cansu Dut full profile
├── voice.md              # Platform-specific voice/tone rules
├── visual.md             # Nano Banana Pro primary style guide + CLIP anchors
├── compliance.md         # Banned topics + AI disclosure standards
├── examples.md           # Few-shot examples corpus (RAG-ready)
├── schema.py             # Pydantic validator
└── platforms/
    ├── linkedin.md       # LinkedIn config (Tier 1)
    ├── instagram.md      # Instagram config (Tier 1)
    ├── twitter.md        # Twitter/X config (Tier 1)
    ├── youtube-shorts.md # YouTube Shorts config (Tier 2 — Phase 2)
    └── medium.md         # Medium config (Tier 3 — Phase 3)
```

## Quick Reference

| Field | Value |
|---|---|
| **Persona Name** | Cansu Dut |
| **Codename** | `cansu` |
| **Status** | active |
| **Manifest Version** | 0.1.0 |
| **Schema Version** | 1.0.0 |
| **Created** | 2026-05-07 |
| **Niche** | AI/ML Engineering (~70%) + tech generalist (~30%) |
| **Languages** | TR primary 70%, EN secondary 30% |
| **Active Platforms** | 5 (LinkedIn, Instagram, Twitter, YouTube Shorts, Medium) |
| **AI Disclosure** | Hybrid platform-specific (compliance.md) |

## Validation

```bash
# Local validation
cd brand_manifest
python schema.py validate

# CI mode (fails build on errors)
python schema.py ci
```

Required: Python 3.11+, `pydantic>=2.0`, `pyyaml>=6.0`.

## Update Workflow

1. Edit relevant `.md` file (e.g. `persona.md`)
2. Update frontmatter `last_updated` date
3. Bump `manifest_version` (semver):
   - Patch: typo, minor wording
   - Minor: new fields, examples, pillar
   - Major: persona core change
4. Update `CHANGELOG.md`
5. Run `python schema.py validate` locally
6. Git commit
7. CI gate runs on PR

## Agent Context Package Pattern

Each agent receives a **task-specific minimal slice** of this manifest:

| Agent | Files Loaded |
|---|---|
| Trend Scout | persona.md (niche), platform.md (target platforms) |
| Writer | persona.md, voice.md, examples.md, target platform.md |
| Visual Director | persona.md, visual.md |
| Compliance Checker | compliance.md, persona.md (values) |
| Publisher | platform.md (publishing config) |

Agents do NOT load the full manifest. Context package builder selects relevant slices to keep token cost minimal.

## Persona Anchor Visual

**Status:** TODO (Hafta 0 deliverable)

Reference anchors are consented Cansu photos stored as private `reference_anchor` assets. Generated visuals are compared against the approved reference set for visual consistency; raw reference photos are not published.

## License

This brand manifest is part of the VirtuAI capstone project (Bahçeşehir University AI Engineering, 2026). The persona "Cansu Dut" is AI-driven; any real-person likeness references require consented, private reference assets and human approval before public publishing.

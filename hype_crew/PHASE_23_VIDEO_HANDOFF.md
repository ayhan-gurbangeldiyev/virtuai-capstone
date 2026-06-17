# Phase 23 — Video Pipeline Handoff

Status: **Text + image pipeline is production-ready. Video pipeline is scaffolded but not deployed.** User is taking the video work over from here.

Last updated: 2026-05-18 by autonomous agent session.

---

## Why this exists

Phase 23 added a video branch to the autonomous content flow (Shorts/Reels). After extensive testing (Pruna lip-sync, MiniMax TTS, Kling/Seedance/Veo3, Wav2Lip research, LivePortrait probing), the conclusion was:

- **Wiro account at our current tier does not expose a true mouth-only photo lip-sync model** — everything we can call either (a) distorts the face (Pruna p-video-avatar), (b) crashes (wiro/memo `pexit=-999`), or (c) is gated (`Alibaba-Quark/Live-Avatar` and `wiro/live-portrait` return `Project authorization is not valid`).
- **Action-video alternatives** (`klingai/kling-v3-omni`, ByteDance Seedance) are accessible but either change subject (no lip-sync) or hard-block real-person inputs.
- Production-grade options outside Wiro: **Replicate Easy-Wav2Lip** ($0.02-0.10/clip, math-guaranteed mouth-only) or **fal.ai MuseTalk** — both require new API keys.

User decided to take the video pipeline finalisation over personally. The rest of the system is set up so the video step is the only remaining production task.

---

## What is production-ready (no further work required)

| Layer | Status | File / Reference |
|---|---|---|
| Multi-platform text generation | ✅ Live | `flow.py:write_via_typehype` (Phase 20) |
| Per-platform compliance + disclosure enforcement | ✅ Live | `flow.py:_apply_platform_metadata`, `_enforce_hashtag_count` (Phase 22) |
| Visual generation (Cansu Seedream 4.5) | ✅ Live | `tools/visual_director_tools.py`, `flow.py:generate_visual` |
| Visual scene rotation (Tier 1/2/3 weighted) | ✅ Live | `flow.py:generate_visual` — 6 scenes from `brand_manifests/cansu_dut/visual.md` |
| Trend dedup (24h window) | ✅ Live | `tools/supabase_tools.py:query_trends` |
| 4-layer image compliance gate | ✅ Live | `tools/compliance/` (CLIP + aesthetic + LLM judge + OCR) |
| Multi-platform Postiz schedule | ✅ Live | `tools/postiz_client.py:schedule_posts` |
| Auto-Drafts approval UI | ✅ Live | `frontend/src/pages/AutoDraftsPage.jsx` + `backend/routes/hype.py` |
| Style profile selector | ✅ Live | `hype_account_config.active_style_profile_id` |
| Hourly cron + persona-aware Flow | ✅ Live | `runner.py` + Hetzner systemd timer |

**Current production run cost**: ~$0.003 (skip branch) - $0.05 (full text+image multi-platform draft) per hourly fire. Cansu is producing 4-platform drafts (X / LinkedIn / Dev.to / Instagram) several times per day.

---

## What is scaffolded but NOT deployed (your remaining work)

### Files in repo (local only, NOT on Hetzner)

```
hype_crew/tools/video_pipeline.py        # 7 pipeline classes — strategy registry
hype_crew/tools/minimax_tts_client.py    # MiniMax T2A v2 — Türkçe Cansu voice clone, proven working
hype_crew/scripts/pilot_4_video_pipelines.py
hype_crew/scripts/pruna_prompt_experiment.py
hype_crew/scripts/upload_anchors.py     # already used; anchors uploaded
```

### Flow integration

`flow.py:generate_video` (Phase 23.5) already exists in the file but is **gated behind `persona.video_enabled`** which is `false` for Cansu. The import of `StoredVideoAsset` from `tools.video_pipeline` is wrapped in `try/except ModuleNotFoundError` so Hetzner — where the video module is absent — still imports `flow.py` cleanly.

### Pipeline classes (all in `tools/video_pipeline.py`)

| pipeline_id | Architecture | Status | Cost/clip |
|---|---|---|---|
| `static_photo_voiceover` | Photo + MiniMax TTS + captions, zero motion | Works ✓ (FFmpeg-only) | $0.0001 |
| `kling_voiceover` | Kling V3 Omni silent action + MiniMax TTS overlay | Implemented, untested live | ~$0.42 |
| `seedance_voiceover` | Seedance + AI-generated Cansu portrait (bypass ByteDance face filter) | Implemented, untested | ~$0.05 |
| `talking_head_memo` | Pruna p-video-avatar lip-sync | Works but **face distorts** (rejected by user) | $0.18-0.31 |
| `hybrid_seedance_memo` | Seedance action + Pruna talking head | Blocked (Seedance privacy filter) | — |
| `veo3_native` | Google Veo3 dialogue + audio native | Blocked (Vertex AI safety filter non-deterministic) | $1.20-3.20 |
| `memo_seedance_v2` | Pruna head + Seedance B-roll | Blocked (same Seedance filter) | — |

### Wiro client dispatches available (`tools/wiro_client.py`)

- `generate_action_video` — Veo3, Seedance, Kling V3 Omni
- `generate_talking_avatar` — Pruna p-video-avatar (working), MEMO (-999 crash), Alibaba-Quark Live-Avatar (auth-locked)
- `generate_voice` — Wiro Chatterbox (works but English presets only; we use MiniMax direct for Türkçe)

### What you'll need to finish video

1. **Pick a lip-sync model that works at production quality**. Candidates ranked:
   - **Replicate Easy-Wav2Lip + GFPGAN** (best static-head fidelity, $0.02-0.10/clip, math-guaranteed)
   - **fal.ai MuseTalk 1.5** (latent inpainting, mouth-only)
   - Wiro tier upgrade to unlock MuseTalk / Sonic / EchoMimic (talk to Wiro support)
2. **Implement the model in `tools/video_pipeline.py`** as a new pipeline class. Reuse `_synthesize_turkish_voice` helper for MiniMax TTS, `_ffmpeg_*` helpers for composition.
3. **Set Cansu's `personas.video_pipeline_default`** to the new pipeline_id.
4. **Add `youtube` or `instagram-reels` to `personas.default_target_platforms`** for Cansu — currently only `[twitter, linkedin, devto, instagram]`.
5. **Flip `personas.video_enabled = true`** to trigger the video_branch.
6. **Deploy to Hetzner**: `rsync hype_crew/tools/{video_pipeline.py,minimax_tts_client.py,wiro_client.py} root@46.225.27.85:/opt/hype-crew/tools/` + `systemctl restart hype-crew.timer` (timer already runs hourly).

### Reference materials in `/Users/berkay/.claude/plans/`

The main plan file `projeyi-inceleyip-anlar-m-s-n-woolly-eagle.md` contains the full Phase 23 history including pilot test results, model comparisons, and architectural decisions. Section **"Phase 23.7 — PIVOT (2026-05-17): Kling V3 Omni Voice-Over Mimarisi"** has the most relevant context.

---

## Operating the system today (without video)

### Toggle live publishing (current state: dry-run)

Cansu's current config:
- `personas.visual_enabled = true` (image gen on)
- `personas.video_enabled = false` (video off — correct)
- `hype_account_config.auto_publish_enabled = false` (manual approval via UI)
- `hype_account_config.dry_run_mode = true` (Postiz schedule mocked)
- `hype_account_config.active_style_profile_id = ce907cea-d925-4397-9f90-93dc5f891dc0` (Cansu Dut Canonical Style — 8 manifest-seeded tweets)

To go live — **single SQL flip is enough** (Gap #4 fix 2026-05-18: DB value now wins over env, env `HYPE_DRY_RUN=true` is fallback only):
```sql
UPDATE hype_account_config
SET dry_run_mode = false
WHERE account_id = '2b731bf7-8c24-40c5-8237-d348ee822d51';
```

After this, approve in Auto-Drafts UI → Postiz schedules real posts across 4 platforms.

For full autonomous publishing (no manual approval):
```sql
UPDATE hype_account_config
SET auto_publish_enabled = true
WHERE account_id = '2b731bf7-8c24-40c5-8237-d348ee822d51';
```

(Recommend waiting until 3-5 days of dry-run drafts have been manually reviewed before flipping this.)

### Cost cap (Gap #5 — 2026-05-18: ENFORCED)

`HYPE_DAILY_COST_CAP_USD=2.00` in `.env` is the global fallback. Per-account override via `hype_account_config.daily_cost_cap_usd numeric(10,4)`.

`runner.py:run_for_account` pre-flight check (before any LLM/Wiro spend):
1. Sum today's `hype_runs.total_cost_usd` for the account
2. If `>= effective_cap` → skip Flow.kickoff + insert `hype_runs` row with `status='cost_cap_exceeded'`

To override Cansu's cap (e.g., $5/day during a campaign):
```sql
UPDATE hype_account_config
SET daily_cost_cap_usd = 5.00
WHERE account_id = '2b731bf7-8c24-40c5-8237-d348ee822d51';
```
NULL → env fallback ($2.00). 0 → disabled (no cap).

### Failure-rate alarm (Gap #6 — 2026-05-18: WIRED)

`runner.py:_recent_failure_streak` checks the last 3 non-running, non-cap runs. If all 3 are `status='failed'` → ERROR log: `[ALARM] N consecutive failures for account=…; investigate`. View via `journalctl -u hype-crew.service | grep ALARM`. V2 will add email/webhook delivery.

### Monitoring

```sql
-- Today's runs
SELECT id, status, total_cost_usd, started_at
FROM hype_runs
WHERE account_id = '2b731bf7-8c24-40c5-8237-d348ee822d51'
  AND started_at > date_trunc('day', now())
ORDER BY started_at DESC;

-- Pending drafts awaiting your approval
SELECT id, platform, trend_topic, content, created_at
FROM daily_drafts
WHERE source = 'hype_auto' AND status = 'pending'
ORDER BY created_at DESC LIMIT 20;

-- Visual compliance status (Cansu image gen)
SELECT compliance_passed, aesthetic_score, clip_persona_similarity, llm_judge_verdict, created_at
FROM persona_assets
WHERE persona_id = '653cea63-8105-478e-803c-24377038c39c' AND asset_type = 'generated_image'
ORDER BY created_at DESC LIMIT 10;
```

---

## Open items (parking lot)

- **Visual aesthetic threshold tuning**: Cansu images score 0.50-0.55 (threshold 0.55). Recent fix added scene rotation + magazine-quality augmentation — observe next 24h to see if compliance pass rate improves. If not, lower threshold to 0.50 or further iterate prompts.
- **Engagement feedback loop (Phase 22)**: not implemented yet. After 1-2 weeks of real published posts, add cron-poll of Postiz engagement → write to `hype_memory.performance_log` → Strategist reads for smarter angle picks.
- **Cost cap enforcement**: V2 if needed.
- **Multi-persona**: schema supports it; only Cansu seeded today.

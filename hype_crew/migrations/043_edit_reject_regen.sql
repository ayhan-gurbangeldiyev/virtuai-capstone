-- ────────────────────────────────────────────────────────────────────
-- Phase 43.A + 43.B — Edit + Reject + Regen consolidation
-- ────────────────────────────────────────────────────────────────────
-- Apply via Supabase Studio → SQL Editor. Every statement is idempotent
-- (ADD COLUMN IF NOT EXISTS, CREATE INDEX IF NOT EXISTS) so reruns are
-- safe. The backend already ships with graceful-degrade for each new
-- column, so the deploy order is: ship code → apply this migration →
-- new behavior activates automatically on the next Hype Crew run.
--
-- Summary of column adds:
--   daily_drafts:
--     · edit_token          UUID    (43.A — edit/approve race guard)
--     · edit_fields         JSONB   (43.A — multi-field edit payload)
--     · regen_started_at    TIMESTAMPTZ (43.B.2/.5 — watchdog timeout source)
--     · image_regen_count   INT     (43.B.2 — per-draft cap, default 0)
--     · confidence_score    FLOAT8  (43.B.5 — composite, nullable)
--   image_regen_jobs:
--     · override_scene_description TEXT (43.B.2 — user-supplied scene)
--     · user_composition_type      TEXT (43.B.2 — user-supplied comp type)
-- Plus a partial index to make the watchdog scan O(orphans) instead of
-- O(table) once the regen flow is in real use.
-- ────────────────────────────────────────────────────────────────────

BEGIN;

-- ── 43.A — edit_token + edit_fields on daily_drafts ─────────────────
ALTER TABLE public.daily_drafts
  ADD COLUMN IF NOT EXISTS edit_token  uuid,
  ADD COLUMN IF NOT EXISTS edit_fields jsonb;

-- Used by /approve to validate "the row hasn't moved under us". GIN keeps
-- future filtered queries (e.g. "drafts where edit_fields.scene exists")
-- snappy without bloating row-scan cost.
CREATE INDEX IF NOT EXISTS idx_daily_drafts_edit_fields_gin
  ON public.daily_drafts USING GIN (edit_fields);

-- ── 43.B.2 — state-machine columns on daily_drafts ──────────────────
ALTER TABLE public.daily_drafts
  ADD COLUMN IF NOT EXISTS regen_started_at  timestamptz,
  ADD COLUMN IF NOT EXISTS image_regen_count int DEFAULT 0;

-- Watchdog will hit this every 60s — partial index keeps it cheap.
CREATE INDEX IF NOT EXISTS idx_daily_drafts_regen_pending
  ON public.daily_drafts (regen_started_at)
  WHERE status = 'regen_pending';

-- ── 43.B.2 — override columns on image_regen_jobs ───────────────────
-- Worker prefers these columns; falls back to [OVERRIDE_*] markers
-- inside rejection_feedback if a deploy runs before the migration.
ALTER TABLE public.image_regen_jobs
  ADD COLUMN IF NOT EXISTS override_scene_description text,
  ADD COLUMN IF NOT EXISTS user_composition_type      text;

-- ── 43.B.5 — confidence_score on daily_drafts ───────────────────────
-- Composite: 1.0 − 0.5 · trend_reject_rate_30d · sample_weight.
-- FLOAT8 because we always clamp to [0,1] and the extra precision
-- is essentially free; nullable so legacy rows stay valid.
ALTER TABLE public.daily_drafts
  ADD COLUMN IF NOT EXISTS confidence_score double precision;

COMMIT;

-- ── Post-flight sanity (optional, run separately if curious) ────────
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'public'
--   AND table_name IN ('daily_drafts', 'image_regen_jobs')
--   AND column_name IN (
--     'edit_token','edit_fields','regen_started_at','image_regen_count',
--     'confidence_score','override_scene_description','user_composition_type'
--   )
-- ORDER BY table_name, column_name;

-- 026_langgraph_resume_fixes.sql — Faz 2 gate bulguları (MED-3 + MED-4), 14 Haz 2026.
-- Data-safety pre-check'li (PG 17.6, pipeline draftlarında 0 dup).

-- MED-3: daily_drafts idempotency index'i NULL content_type'ı da kapsasın.
-- Eski index NULL'ları DISTINCT sayıyordu → NULL content_type draft'ı korumuyordu.
-- DÜZELTME: NULLS NOT DISTINCT + pipeline'a kapsamla (hype_run_id IS NOT NULL) — çünkü
-- magic_morning/dna_test gibi NULL-hype_run_id satırlar (38+ adet, meşru) tablo-genelinde
-- NULLS NOT DISTINCT'i bloklardı; idempotency zaten yalnız pipeline run'ları için.
DROP INDEX IF EXISTS uq_daily_drafts_run_platform_ctype;
CREATE UNIQUE INDEX uq_daily_drafts_run_platform_ctype
  ON daily_drafts (hype_run_id, platform, content_type) NULLS NOT DISTINCT
  WHERE deleted_at IS NULL AND hype_run_id IS NOT NULL;

-- MED-4: poison-run koruması. Hızlı-çöken run <2h olduğu için reaper'a takılmadan
-- sonsuz resume olabiliyor. resume_attempts sayacı: run_or_resume her resume'dan ÖNCE
-- artırır; cap (3) aşılırsa force-fail (kör re-call önlenir; çift-post riski kapanır).
ALTER TABLE hype_runs ADD COLUMN IF NOT EXISTS resume_attempts int NOT NULL DEFAULT 0;

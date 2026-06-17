-- 2026-06-07 — video integrity check (SEV-1 follow-up P0).
-- Mirrors the live migration applied via Supabase MCP.

ALTER TABLE daily_drafts
    ADD COLUMN IF NOT EXISTS video_duration_s         NUMERIC(7,2),
    ADD COLUMN IF NOT EXISTS expected_duration_s      NUMERIC(7,2),
    ADD COLUMN IF NOT EXISTS video_integrity_ok       BOOLEAN,
    ADD COLUMN IF NOT EXISTS video_integrity_reason   TEXT,
    ADD COLUMN IF NOT EXISTS video_integrity_checked_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_daily_drafts_video_integrity_fail
    ON daily_drafts (account_id, video_integrity_ok, status)
    WHERE video_integrity_ok = FALSE;

-- 2026-06-07 — video↔content binding (post-SEV-1 P0 fix).
-- Mirrors the live migration applied via Supabase MCP.

ALTER TABLE daily_drafts
    ADD COLUMN IF NOT EXISTS video_content_sha TEXT,
    ADD COLUMN IF NOT EXISTS video_stale BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_daily_drafts_video_stale
    ON daily_drafts (account_id, video_stale, status)
    WHERE video_stale = TRUE;

-- Backfill (run once): stamp sha256(content) on every existing video draft.
-- UPDATE daily_drafts
-- SET video_content_sha = encode(digest(coalesce(content, ''), 'sha256'), 'hex'),
--     video_stale = FALSE
-- WHERE video_url IS NOT NULL AND video_content_sha IS NULL;

-- Migration: Trends V2 - RSS Pipeline Support
-- Date: 2026-02-09
-- Description: Add columns for URL dedup, source tracking, visibility, and raw content

-- New columns
ALTER TABLE trends ADD COLUMN IF NOT EXISTS url TEXT;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'ai';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_name TEXT;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS is_visible BOOLEAN DEFAULT true;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS raw_content TEXT;

-- Unique constraint on URL for duplicate prevention
CREATE UNIQUE INDEX IF NOT EXISTS idx_trends_url_unique ON trends (url) WHERE url IS NOT NULL;

-- Index for common queries
CREATE INDEX IF NOT EXISTS idx_trends_score ON trends (score DESC);
CREATE INDEX IF NOT EXISTS idx_trends_visible_score ON trends (is_visible, score DESC);
CREATE INDEX IF NOT EXISTS idx_trends_source_type ON trends (source_type);
CREATE INDEX IF NOT EXISTS idx_trends_published_at ON trends (published_at DESC);

-- RLS: Allow authenticated users to read visible trends
-- (trends are global, not per-user)
ALTER TABLE trends ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Authenticated users can read visible trends" ON trends;
CREATE POLICY "Authenticated users can read visible trends"
  ON trends FOR SELECT
  TO authenticated
  USING (is_visible = true);

DROP POLICY IF EXISTS "Service role full access on trends" ON trends;
CREATE POLICY "Service role full access on trends"
  ON trends FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

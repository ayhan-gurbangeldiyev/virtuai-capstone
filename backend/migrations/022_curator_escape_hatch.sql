-- Trusted-Curator Escape Hatch (@upcornco, AI-only)
-- Tek-kaynaklı taze AI haberini çoklu-kaynak funnel'ını baypas ederek
-- yayınlanabilir aday yapan force-seed yolu için işaret kolonu.
-- Run on Supabase SQL Editor.

ALTER TABLE trends ADD COLUMN IF NOT EXISTS is_curator BOOLEAN DEFAULT FALSE;

-- Index for curator trends (fast downstream filtering / audit)
CREATE INDEX IF NOT EXISTS idx_trends_is_curator ON trends(is_curator) WHERE is_curator = TRUE;

COMMENT ON COLUMN trends.is_curator IS 'Force-seeded from a trusted curator (@upcornco) via news-filter; bypasses the multi-source mega-trend funnel + the launch rubric (news-bar instead). Subject to recently_covered + GuardedPostiz like any trend.';

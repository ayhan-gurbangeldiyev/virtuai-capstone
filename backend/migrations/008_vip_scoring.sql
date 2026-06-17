-- VIP Scoring System: Source multiplier + Semantic triggers
-- Run on Supabase SQL Editor

ALTER TABLE trends ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT FALSE;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS vip_reason TEXT DEFAULT '';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS semantic_triggers TEXT[] DEFAULT '{}';

-- Index for VIP trends (fast filtering)
CREATE INDEX IF NOT EXISTS idx_trends_is_vip ON trends(is_vip) WHERE is_vip = TRUE;

-- Comment
COMMENT ON COLUMN trends.is_vip IS 'VIP source (Tier 1 AI labs, official product accounts)';
COMMENT ON COLUMN trends.vip_reason IS 'Why this trend got VIP boost (source + trigger info)';
COMMENT ON COLUMN trends.semantic_triggers IS 'Detected semantic triggers (launch, scandal, milestone, breaking)';

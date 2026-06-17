-- Migration 011: Feed Enrichment — media, quotes, bookmarks, metadata
-- XQuik lookup_tweet() ile gelen ek verileri saklamak için yeni kolonlar

ALTER TABLE tweet_feed
  ADD COLUMN IF NOT EXISTS quotes INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS bookmarks INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS media JSONB DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS has_media BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS image_url TEXT,
  ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT false,
  ADD COLUMN IF NOT EXISTS followers_count INT DEFAULT 0,
  ADD COLUMN IF NOT EXISTS enriched_at TIMESTAMPTZ;

-- Media filtresi için partial index
CREATE INDEX IF NOT EXISTS idx_feed_has_media ON tweet_feed (has_media) WHERE has_media = true;

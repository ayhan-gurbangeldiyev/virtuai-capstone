-- Migration 010: Tweet Feed + API Cache
-- TypeHype sinyal pipeline v3: batch tweet feed + persistent cache

-- ================================================================
-- TWEET FEED: Tüm batch + radar + monitor tweetleri
-- ================================================================
CREATE TABLE IF NOT EXISTS tweet_feed (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tweet_id TEXT UNIQUE NOT NULL,
    username TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    content TEXT NOT NULL,
    likes INT DEFAULT 0,
    retweets INT DEFAULT 0,
    replies INT DEFAULT 0,
    views INT DEFAULT 0,
    tweet_url TEXT,
    batch_type TEXT NOT NULL,          -- 'ai_tech', 'tr_haber', 'spor', 'monitor', 'radar'
    source_detail TEXT,                -- radar: kaynak adı, batch: username
    tweet_created_at TIMESTAMPTZ,
    collected_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_feed_created ON tweet_feed (tweet_created_at DESC);
CREATE INDEX IF NOT EXISTS idx_feed_batch ON tweet_feed (batch_type);
-- 48h cleanup function
CREATE OR REPLACE FUNCTION cleanup_old_feed()
RETURNS void AS $$
BEGIN
    DELETE FROM tweet_feed WHERE tweet_created_at < now() - interval '48 hours';
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- API CACHE: L2 persistent cache (Supabase)
-- ================================================================
CREATE TABLE IF NOT EXISTS api_cache (
    cache_key TEXT PRIMARY KEY,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_expires ON api_cache (expires_at);

-- Cache cleanup function
CREATE OR REPLACE FUNCTION cleanup_expired_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM api_cache WHERE expires_at < now();
END;
$$ LANGUAGE plpgsql;

-- ================================================================
-- RSS feeds devre dışı bırak
-- ================================================================
UPDATE rss_feeds
SET is_active = false, last_status = 'disabled: replaced by xquik batch + radar'
WHERE is_active = true;

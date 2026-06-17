-- Migration: viral_tweets tablosu
-- Viral tweet collector pipeline için

CREATE TABLE IF NOT EXISTS viral_tweets (
  id BIGINT PRIMARY KEY,  -- tweet_id
  author_handle TEXT NOT NULL,
  author_name TEXT,
  author_followers INTEGER,
  author_verified BOOLEAN DEFAULT false,
  content TEXT NOT NULL,
  likes INTEGER DEFAULT 0,
  retweets INTEGER DEFAULT 0,
  replies INTEGER DEFAULT 0,
  quotes INTEGER DEFAULT 0,
  bookmarks INTEGER DEFAULT 0,
  impressions INTEGER DEFAULT 0,
  media_type TEXT,  -- none, image, video, gif, poll
  has_link BOOLEAN DEFAULT false,
  hashtags TEXT[],
  mentions TEXT[],
  language TEXT DEFAULT 'tr',
  tweet_length INTEGER,
  posted_at TIMESTAMPTZ,
  collected_at TIMESTAMPTZ DEFAULT NOW(),
  niche TEXT,  -- tech, finans, lifestyle, mizah, haber, kripto, kisisel_gelisim
  engagement_rate DECIMAL(10,6),
  is_thread BOOLEAN DEFAULT false,
  thread_position INTEGER,
  hook_type TEXT  -- sonra dolduracağız
);

CREATE INDEX IF NOT EXISTS idx_viral_tweets_niche ON viral_tweets(niche);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_likes ON viral_tweets(likes DESC);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_engagement ON viral_tweets(engagement_rate DESC);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_language ON viral_tweets(language);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_author ON viral_tweets(author_handle);

-- RLS
ALTER TABLE viral_tweets ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'viral_tweets' AND policyname = 'Service role full access'
  ) THEN
    CREATE POLICY "Service role full access" ON viral_tweets FOR ALL USING (true);
  END IF;
END
$$;

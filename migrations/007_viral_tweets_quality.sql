-- Migration: viral_tweets kalite sütunları
-- has_cta, cta_type, sentiment, content_format ekleniyor

ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS has_cta BOOLEAN DEFAULT false;
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS cta_type TEXT DEFAULT 'none';  -- bookmark_trigger, reply_trigger, rt_trigger, follow_trigger, none
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS sentiment TEXT;  -- positive, negative, neutral, provocative
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS content_format TEXT;  -- single, thread_start, thread_part, quote, reply
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS posted_hour INTEGER;  -- 0-23 UTC
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS source TEXT;  -- timeline, search, trending
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS follower_following_ratio DECIMAL(10,4);
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS account_age_days INTEGER;
ALTER TABLE viral_tweets ADD COLUMN IF NOT EXISTS similarity_hash TEXT;  -- deduplikasyon için

CREATE INDEX IF NOT EXISTS idx_viral_tweets_sentiment ON viral_tweets(sentiment);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_hook_type ON viral_tweets(hook_type);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_content_format ON viral_tweets(content_format);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_posted_hour ON viral_tweets(posted_hour);
CREATE INDEX IF NOT EXISTS idx_viral_tweets_similarity ON viral_tweets(similarity_hash);

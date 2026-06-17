-- ContentFactory Migration 001: New Platform Tables
-- Run this in Supabase Dashboard → SQL Editor

-- Trends tablosu
CREATE TABLE IF NOT EXISTS trends (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  topic text NOT NULL,
  category text,
  source text,
  source_url text,
  score float DEFAULT 0,
  tweet_count int DEFAULT 0,
  avg_engagement float DEFAULT 0,
  sample_tweets jsonb DEFAULT '[]'::jsonb,
  ai_summary text,
  ai_content_suggestions jsonb DEFAULT '[]'::jsonb,
  expires_at timestamptz,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);

-- Account analyses tablosu
CREATE TABLE IF NOT EXISTS account_analyses (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id text,
  twitter_username text NOT NULL,
  display_name text,
  bio text,
  followers_count int DEFAULT 0,
  following_count int DEFAULT 0,
  tweet_count int DEFAULT 0,
  analysis jsonb DEFAULT '{}'::jsonb,
  top_tweets jsonb DEFAULT '[]'::jsonb,
  strengths jsonb DEFAULT '[]'::jsonb,
  weaknesses jsonb DEFAULT '[]'::jsonb,
  recommendations jsonb DEFAULT '[]'::jsonb,
  posting_patterns jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Content calendar tablosu
CREATE TABLE IF NOT EXISTS content_calendar (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id text,
  platform text NOT NULL,
  scheduled_at timestamptz NOT NULL,
  content_type text,
  content text,
  status text DEFAULT 'draft',
  generation_id text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trends_category ON trends(category);
CREATE INDEX IF NOT EXISTS idx_trends_created_at ON trends(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_analyses_username ON account_analyses(twitter_username);
CREATE INDEX IF NOT EXISTS idx_content_calendar_user ON content_calendar(user_id);
CREATE INDEX IF NOT EXISTS idx_content_calendar_scheduled ON content_calendar(scheduled_at);

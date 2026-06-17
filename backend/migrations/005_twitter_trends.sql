-- Migration 005: Twitter Multi-Signal Trend Intelligence
-- Adds Twitter signal tracking to trends table + watch accounts

-- 5.1 trends tablosuna yeni kolonlar
ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_type TEXT DEFAULT 'rss';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS signal_count INT DEFAULT 1;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS engagement_total INT DEFAULT 0;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_tweets JSONB DEFAULT '[]';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS key_angles TEXT[] DEFAULT '{}';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS suggested_hooks JSONB DEFAULT '[]';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS content_pillars TEXT[] DEFAULT '{}';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS cluster_id UUID;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS twitter_account TEXT;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS tweet_id TEXT;

CREATE INDEX IF NOT EXISTS idx_trend_cluster ON trends(cluster_id) WHERE cluster_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_trend_source ON trends(source_type);
CREATE INDEX IF NOT EXISTS idx_trend_tweet ON trends(tweet_id) WHERE tweet_id IS NOT NULL;

-- 5.2 twitter_watch_accounts tablosu
CREATE TABLE IF NOT EXISTS twitter_watch_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  username TEXT NOT NULL UNIQUE,
  display_name TEXT,
  tier INT DEFAULT 1,
  category TEXT,
  last_tweet_id TEXT,
  active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- 5.3 Seed data
INSERT INTO twitter_watch_accounts (username, display_name, tier, category) VALUES
  ('AnthropicAI', 'Anthropic', 1, 'ai_lab'),
  ('OpenAI', 'OpenAI', 1, 'ai_lab'),
  ('GoogleDeepMind', 'Google DeepMind', 1, 'ai_lab'),
  ('MistralAI', 'Mistral AI', 1, 'ai_lab'),
  ('xaborai', 'xAI', 1, 'ai_lab'),
  ('MetaAI', 'Meta AI', 1, 'ai_lab'),
  ('huggingface', 'Hugging Face', 1, 'ai_lab'),
  ('ollaborai', 'Ollama', 1, 'ai_lab'),
  ('LangChainAI', 'LangChain', 1, 'ai_lab'),
  ('PerplexityAI', 'Perplexity', 1, 'ai_lab'),
  ('CohereForAI', 'Cohere', 1, 'ai_lab'),
  ('StabilityAI', 'Stability AI', 1, 'ai_lab'),
  ('veraborai', 'Vercel AI', 1, 'ai_lab'),
  ('sama', 'Sam Altman', 2, 'ceo'),
  ('daborai', 'Dario Amodei', 2, 'ceo'),
  ('ylecun', 'Yann LeCun', 2, 'researcher'),
  ('JeffDean', 'Jeff Dean', 2, 'researcher'),
  ('kaborai', 'Karpathy', 2, 'researcher'),
  ('hardmaru', 'David Ha', 2, 'researcher'),
  ('aaborai', 'Amanda Askell', 2, 'researcher'),
  ('goodaborai', 'Ian Goodfellow', 2, 'researcher'),
  ('demaborai', 'Demis Hassabis', 2, 'ceo')
ON CONFLICT (username) DO NOTHING;

-- RLS policies
ALTER TABLE twitter_watch_accounts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon_read_watch_accounts" ON twitter_watch_accounts FOR SELECT USING (true);

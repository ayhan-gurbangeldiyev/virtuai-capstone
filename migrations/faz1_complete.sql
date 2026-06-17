-- =====================================================
-- Type Hype Trend Pipeline - Faz 1 Complete Migration
-- Tüm tabloları oluşturur, eksik kolonları ekler,
-- seed data yükler. Idempotent — tekrar çalıştırılabilir.
-- =====================================================

-- =====================================================
-- 1. rss_feeds tablosu
-- =====================================================
CREATE TABLE IF NOT EXISTS rss_feeds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  niche TEXT NOT NULL,
  sub_category TEXT,
  source TEXT NOT NULL,
  rss_url TEXT NOT NULL UNIQUE,
  language TEXT DEFAULT 'en',
  region TEXT DEFAULT 'Global',
  update_freq TEXT DEFAULT 'Daily',
  priority TEXT DEFAULT 'Medium',
  notes TEXT,
  is_active BOOLEAN DEFAULT true,
  last_fetched TIMESTAMPTZ,
  last_status TEXT,
  error_count INT DEFAULT 0,
  health_score NUMERIC(3,1) DEFAULT 100.0,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- =====================================================
-- 2. raw_signals staging tablosu
-- =====================================================
CREATE TABLE IF NOT EXISTS raw_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_type TEXT NOT NULL,
  source_name TEXT,
  niche TEXT,
  title TEXT,
  url TEXT,
  raw_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  collected_at TIMESTAMPTZ DEFAULT now(),
  processed_at TIMESTAMPTZ,
  status TEXT DEFAULT 'pending',
  batch_id UUID
);

-- URL unique constraint (PostgREST dedup için gerekli)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'raw_signals_url_unique'
  ) THEN
    ALTER TABLE raw_signals ADD CONSTRAINT raw_signals_url_unique UNIQUE (url);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_raw_signals_status ON raw_signals(status);
CREATE INDEX IF NOT EXISTS idx_raw_signals_collected ON raw_signals(collected_at);
CREATE INDEX IF NOT EXISTS idx_raw_signals_batch ON raw_signals(batch_id);

-- =====================================================
-- 3. system_config tablosu (kill switch + config)
-- =====================================================
CREATE TABLE IF NOT EXISTS system_config (
  key TEXT PRIMARY KEY,
  value JSONB,
  updated_at TIMESTAMPTZ DEFAULT now()
);

INSERT INTO system_config (key, value) VALUES
  ('pipeline_mode', '"active"'::jsonb),
  ('daily_cost_limit', '1.0'::jsonb),
  ('model_primary', '"openai/gpt-4o-mini"'::jsonb),
  ('model_fallback', '"openai/gpt-4.1-nano"'::jsonb)
ON CONFLICT (key) DO NOTHING;

-- =====================================================
-- 4. content_drafts tablosu (içerik üretimi)
-- =====================================================
CREATE TABLE IF NOT EXISTS content_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trend_id UUID REFERENCES trends(id) ON DELETE SET NULL,
  platform TEXT NOT NULL, -- 'linkedin', 'twitter', 'blog'
  content TEXT NOT NULL,
  image_prompt TEXT,
  status TEXT DEFAULT 'draft', -- 'draft', 'approved', 'published'
  metadata JSONB DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_content_drafts_trend ON content_drafts(trend_id);
CREATE INDEX IF NOT EXISTS idx_content_drafts_status ON content_drafts(status);

-- =====================================================
-- 5. twitter_watch_accounts — eksik kolonları ekle
-- =====================================================
ALTER TABLE twitter_watch_accounts
  ADD COLUMN IF NOT EXISTS niche TEXT,
  ADD COLUMN IF NOT EXISTS weight NUMERIC(3,1) DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS region TEXT DEFAULT 'Global',
  ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT false;

-- =====================================================
-- 6. trends — eksik kolonları ekle (VIP scoring)
-- =====================================================
ALTER TABLE trends ADD COLUMN IF NOT EXISTS source_count INT DEFAULT 1;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS is_vip BOOLEAN DEFAULT false;
ALTER TABLE trends ADD COLUMN IF NOT EXISTS vip_reason TEXT DEFAULT '';
ALTER TABLE trends ADD COLUMN IF NOT EXISTS semantic_triggers TEXT[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_trends_is_vip ON trends(is_vip) WHERE is_vip = true;

-- =====================================================
-- 7. Feed error increment fonksiyonu (auto-disable)
-- =====================================================
CREATE OR REPLACE FUNCTION increment_feed_error_count(feed_id UUID)
RETURNS void AS $$
BEGIN
  UPDATE rss_feeds
  SET error_count = error_count + 1,
      health_score = GREATEST(0, health_score - 10),
      is_active = CASE
        WHEN error_count + 1 >= 5 THEN false
        ELSE is_active
      END
  WHERE id = feed_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 8. VIP Twitter hesapları güncelle (mevcut)
-- =====================================================
UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.5, region = 'Global', is_vip = true
WHERE username IN ('AnthropicAI', 'OpenAI', 'GoogleDeepMind', 'MistralAI', 'MetaAI', 'StabilityAI', 'CohereForAI');

UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.3, region = 'Global', is_vip = true
WHERE username IN ('huggingface', 'PerplexityAI');

UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.5, region = 'Global', is_vip = true
WHERE username IN ('xaborai');

UPDATE twitter_watch_accounts SET niche = 'devtools', weight = 1.3, region = 'Global', is_vip = true
WHERE username IN ('LangChainAI', 'veraborai');

UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.3, region = 'Global', is_vip = true
WHERE username IN ('ollaborai');

UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.5, region = 'Global', is_vip = false
WHERE username IN ('sama', 'daborai', 'demaborai');

UPDATE twitter_watch_accounts SET niche = 'ai', weight = 1.3, region = 'Global', is_vip = false
WHERE username IN ('ylecun', 'JeffDean', 'kaborai', 'hardmaru', 'aaborai', 'goodaborai');

-- =====================================================
-- 9. Yeni VIP hesaplar ekle
-- =====================================================
INSERT INTO twitter_watch_accounts (username, display_name, tier, category, niche, weight, region, is_vip, active)
VALUES
  ('ClaudeAI', 'Claude', 1, 'ai_lab', 'ai', 1.5, 'Global', true, true),
  ('ChatGPTapp', 'ChatGPT', 1, 'ai_lab', 'ai', 1.5, 'Global', true, true),
  ('cursor_ai', 'Cursor', 1, 'devtools', 'devtools', 1.5, 'Global', true, true),
  ('deepseek_ai', 'DeepSeek', 1, 'ai_lab', 'ai', 1.5, 'Global', true, true),
  ('GoogleAI', 'Google AI', 1, 'ai_lab', 'ai', 1.5, 'Global', true, true),
  ('ycombinator', 'Y Combinator', 2, 'business', 'business', 1.3, 'Global', true, true),
  ('elaborai_labs', 'ElevenLabs', 1, 'ai_lab', 'ai', 1.3, 'Global', true, true),
  ('midjourney', 'Midjourney', 1, 'ai_lab', 'ai', 1.3, 'Global', true, true),
  ('VitalikButerin', 'Vitalik Buterin', 2, 'crypto', 'crypto', 1.5, 'Global', true, true),
  ('caborin_zhao', 'CZ (Binance)', 2, 'crypto', 'crypto', 1.3, 'Global', true, true),
  ('elonmusk', 'Elon Musk', 2, 'ceo', 'business', 1.2, 'Global', true, true),
  ('GalatasaraySK', 'Galatasaray', 2, 'sports_tr', 'sports', 1.5, 'TR', true, true),
  ('Fenerbahce', 'Fenerbahce', 2, 'sports_tr', 'sports', 1.5, 'TR', true, true),
  ('Besiktas', 'Besiktas', 2, 'sports_tr', 'sports', 1.5, 'TR', true, true)
ON CONFLICT (username) DO UPDATE SET
  niche = EXCLUDED.niche,
  weight = EXCLUDED.weight,
  region = EXCLUDED.region,
  is_vip = EXCLUDED.is_vip;

-- =====================================================
-- 10. TR haber/tech/spor hesapları
-- =====================================================
INSERT INTO twitter_watch_accounts (username, display_name, tier, category, niche, weight, region, is_vip, active)
VALUES
  ('ntv', 'NTV', 3, 'tr_news', 'news', 1.2, 'TR', false, true),
  ('bbcturkce', 'BBC Turkce', 3, 'tr_news', 'news', 1.2, 'TR', false, true),
  ('Haberturk', 'Haberturk', 3, 'tr_news', 'news', 1.2, 'TR', false, true),
  ('webrazzi', 'Webrazzi', 3, 'tr_tech', 'devtools', 1.3, 'TR', false, true),
  ('shiftdeletenet', 'ShiftDelete.Net', 3, 'tr_tech', 'devtools', 1.2, 'TR', false, true),
  ('TechnopatNet', 'Technopat', 3, 'tr_tech', 'devtools', 1.2, 'TR', false, true),
  ('sporx', 'Sporx', 3, 'tr_sports', 'sports', 1.2, 'TR', false, true),
  ('fanatikcomtr', 'Fanatik', 3, 'tr_sports', 'sports', 1.2, 'TR', false, true),
  ('TFF_Org', 'TFF', 3, 'tr_sports', 'sports', 1.2, 'TR', false, true),
  ('onediocom', 'Onedio', 3, 'tr_news', 'entertainment', 1.1, 'TR', false, true),
  ('bpthaber', 'Bi Posta', 3, 'tr_news', 'entertainment', 1.1, 'TR', false, true),
  ('gusholderhaber', 'Gusholder', 3, 'tr_news', 'entertainment', 1.1, 'TR', false, true),
  ('BloombergHT', 'Bloomberg HT', 3, 'tr_economy', 'business', 1.3, 'TR', false, true)
ON CONFLICT (username) DO UPDATE SET
  niche = EXCLUDED.niche,
  weight = EXCLUDED.weight,
  region = EXCLUDED.region,
  tier = EXCLUDED.tier,
  category = EXCLUDED.category;

-- =====================================================
-- 11. RLS Policies
-- =====================================================
ALTER TABLE raw_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE rss_feeds ENABLE ROW LEVEL SECURITY;
ALTER TABLE system_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_drafts ENABLE ROW LEVEL SECURITY;

-- Service role full access (backend kullanımı için)
DO $$
BEGIN
  -- raw_signals
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'service_full_raw_signals') THEN
    CREATE POLICY service_full_raw_signals ON raw_signals FOR ALL USING (true) WITH CHECK (true);
  END IF;
  -- rss_feeds
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'service_full_rss_feeds') THEN
    CREATE POLICY service_full_rss_feeds ON rss_feeds FOR ALL USING (true) WITH CHECK (true);
  END IF;
  -- system_config
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'service_full_system_config') THEN
    CREATE POLICY service_full_system_config ON system_config FOR ALL USING (true) WITH CHECK (true);
  END IF;
  -- content_drafts
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'service_full_content_drafts') THEN
    CREATE POLICY service_full_content_drafts ON content_drafts FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

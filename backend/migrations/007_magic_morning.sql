-- FAZ 7: Magic Morning (JIT Daily Drafts)
-- Kullanıcı giriş yaptığında lazy-generate edilen günlük taslaklar

CREATE TABLE IF NOT EXISTS daily_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  trend_id UUID REFERENCES trends(id) ON DELETE SET NULL,
  content TEXT NOT NULL,
  platform TEXT DEFAULT 'twitter',
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'edited', 'published', 'dismissed')),
  trend_topic TEXT,
  trend_summary TEXT,
  insight TEXT,  -- "Bu konu senin nişin için neden önemli?"
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Index: kullanıcının bugünkü taslakları
CREATE INDEX IF NOT EXISTS idx_daily_drafts_user_date 
  ON daily_drafts(user_id, created_at DESC);

-- RLS
ALTER TABLE daily_drafts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can read own drafts" ON daily_drafts
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users can update own drafts" ON daily_drafts
  FOR UPDATE USING (auth.uid() = user_id);

-- Eski taslakları temizle (7 günden eski)
-- Cron ile çalıştırılabilir: DELETE FROM daily_drafts WHERE created_at < now() - interval '7 days';

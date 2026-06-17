-- Account analyses tablosu güncelleme
-- Eksik kolonlar ekleniyor

-- avatar_url kolonu (yoksa ekle)
ALTER TABLE account_analyses ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- overall_score kolonu (yoksa ekle) 
ALTER TABLE account_analyses ADD COLUMN IF NOT EXISTS overall_score INTEGER DEFAULT 0;

-- updated_at kolonu (yoksa ekle)
ALTER TABLE account_analyses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

-- Unique constraint: aynı kullanıcı + aynı twitter hesabı
CREATE UNIQUE INDEX IF NOT EXISTS idx_account_analyses_user_username 
  ON account_analyses(user_id, twitter_username);

-- updated_at sıralama için index
CREATE INDEX IF NOT EXISTS idx_account_analyses_updated 
  ON account_analyses(user_id, updated_at DESC);

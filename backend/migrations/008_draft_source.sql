-- 008: daily_drafts tablosuna source kolonu + GET by ID desteği
-- Çalıştır: Supabase SQL Editor

-- 1. source kolonu (magic_morning, dna_test, manual)
ALTER TABLE daily_drafts ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'magic_morning';

-- 2. Mevcut kayıtları etiketle
UPDATE daily_drafts SET source = 'magic_morning' WHERE source IS NULL;

-- 3. Index (ilerideki "Taslaklarım" sayfası için)
CREATE INDEX IF NOT EXISTS idx_daily_drafts_source ON daily_drafts(user_id, source, status);

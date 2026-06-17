-- Style Lab v3: Tek adım stil profili, avatar desteği
-- style_profiles tablosuna yeni kolonlar

ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS twitter_username TEXT;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS twitter_display_name TEXT;
ALTER TABLE style_profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Mevcut profilleri migrate et: source'lardan username/display_name çek
UPDATE style_profiles sp
SET 
    twitter_username = ss.twitter_username,
    twitter_display_name = ss.twitter_display_name
FROM style_sources ss
WHERE ss.id = (sp.source_ids->>0)::uuid
  AND sp.twitter_username IS NULL;

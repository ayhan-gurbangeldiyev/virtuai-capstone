-- Faz 5: Creator Hub - Master Identity & Brand Voice
-- Migration: 006_creator_hub.sql

-- Master Identity
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS display_name TEXT;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS avatar_url TEXT;

-- Niche / İlgi Alanları (pre-defined slugs)
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS niches TEXT[] DEFAULT '{}';

-- Brand Voice DNA (validated JSONB)
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS brand_voice JSONB DEFAULT '{}';

-- Index: niche bazlı trend filtreleme için GIN index
CREATE INDEX IF NOT EXISTS idx_user_settings_niches ON user_settings USING GIN (niches);

-- Yorum: brand_voice yapısı
COMMENT ON COLUMN user_settings.brand_voice IS 'Validated via Pydantic. Structure: {tones: {informative: int, witty: int, aggressive: int}, principles: [str], avoid: [str], sample_voice: str}';
COMMENT ON COLUMN user_settings.niches IS 'Pre-defined taxonomy slugs: ai, saas, startup, marketing, crypto, etc.';

-- Creator Hub Sprint 1
-- Varsayılan draft stilini user_settings üzerinde persist etmek için JSONB alanı

ALTER TABLE user_settings
ADD COLUMN IF NOT EXISTS default_draft_style JSONB;

COMMENT ON COLUMN user_settings.default_draft_style IS
'Creator Hub default draft style. Shape: {type: own_voice|cloned|archetype, profile_id?: uuid, key?: text}';

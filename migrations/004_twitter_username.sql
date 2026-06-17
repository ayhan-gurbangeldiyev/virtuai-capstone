-- Add twitter_username column to user_settings
ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS twitter_username TEXT;

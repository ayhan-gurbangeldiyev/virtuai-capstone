-- ============================================================
-- MULTI-ACCOUNT SUPPORT — ROLLBACK (DOWN)
-- ============================================================
-- Tarih: 2026-02-23
-- Bu script UP migration'ı tamamen geri alır.
-- Sıralama ÖNEMLİ: önce data temizle, sonra index/kolon sil.
-- ============================================================

-- ──────────────────────────────────────────────
-- ADIM 1: account_id verilerini temizle (NULL'a çevir)
-- ──────────────────────────────────────────────

UPDATE generations SET account_id = NULL WHERE account_id IS NOT NULL;
UPDATE favorites SET account_id = NULL WHERE account_id IS NOT NULL;
UPDATE style_profiles SET account_id = NULL WHERE account_id IS NOT NULL;
UPDATE coach_weekly_plans SET account_id = NULL WHERE account_id IS NOT NULL;
UPDATE coach_dismissed_cards SET account_id = NULL WHERE account_id IS NOT NULL;

-- ──────────────────────────────────────────────
-- ADIM 2: Index'leri sil
-- ──────────────────────────────────────────────

DROP INDEX IF EXISTS idx_generations_account;
DROP INDEX IF EXISTS idx_favorites_account;
DROP INDEX IF EXISTS idx_style_profiles_account;
DROP INDEX IF EXISTS idx_coach_plans_account;

-- ──────────────────────────────────────────────
-- ADIM 3: account_id kolonlarını sil
-- ──────────────────────────────────────────────

ALTER TABLE generations DROP COLUMN IF EXISTS account_id;
ALTER TABLE favorites DROP COLUMN IF EXISTS account_id;
ALTER TABLE style_profiles DROP COLUMN IF EXISTS account_id;
ALTER TABLE coach_weekly_plans DROP COLUMN IF EXISTS account_id;
ALTER TABLE coach_dismissed_cards DROP COLUMN IF EXISTS account_id;

-- ──────────────────────────────────────────────
-- ADIM 4: user_settings'ten active_account_id sil
-- ──────────────────────────────────────────────

ALTER TABLE user_settings DROP COLUMN IF EXISTS active_account_id;
ALTER TABLE user_settings DROP COLUMN IF EXISTS subscription_tier;
ALTER TABLE user_settings DROP COLUMN IF EXISTS account_limit;

-- ──────────────────────────────────────────────
-- ADIM 5: connected_accounts ek kolonlarını sil
-- ──────────────────────────────────────────────

ALTER TABLE connected_accounts DROP COLUMN IF EXISTS status;
ALTER TABLE connected_accounts DROP COLUMN IF EXISTS last_verified_at;
ALTER TABLE connected_accounts DROP COLUMN IF EXISTS label;

-- ──────────────────────────────────────────────
-- ADIM 6: Ghost account kayıtlarını sil
-- ──────────────────────────────────────────────

DELETE FROM connected_accounts WHERE platform = 'default';

-- ============================================================
-- Rollback tamamlandı. Sistem eski haline döndü.
-- Doğrulama:
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'generations' AND column_name = 'account_id';
-- (0 satır döndürmeli)
-- ============================================================

-- ============================================================
-- MULTI-ACCOUNT SUPPORT — FAZ 1: DB Migration (UP)
-- ============================================================
-- Tarih: 2026-02-23
-- Açıklama: Çoklu hesap desteği için tablo yapısı güncellemeleri
-- Güvenlik: Tüm değişiklikler nullable, mevcut data etkilenmez
-- Tahmini süre: <1 saniye (toplam ~155 satır)
-- Downtime: YOK (ALTER TABLE ADD COLUMN nullable = anlık, lock yok)
-- ============================================================

-- ──────────────────────────────────────────────
-- ADIM 1: connected_accounts'a yeni kolonlar
-- ──────────────────────────────────────────────

-- Hesap sağlık durumu (token kopması kontrolü)
ALTER TABLE connected_accounts
  ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';

-- Son doğrulama zamanı
ALTER TABLE connected_accounts
  ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;

-- Etiket (Kişisel, Marka, vb.)
ALTER TABLE connected_accounts
  ADD COLUMN IF NOT EXISTS label TEXT;

-- ──────────────────────────────────────────────
-- ADIM 2: user_settings'e active_account_id
-- ──────────────────────────────────────────────

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS active_account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- Subscription tier (Free/Pro/Agency) ve hesap limiti
ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'free';

ALTER TABLE user_settings
  ADD COLUMN IF NOT EXISTS account_limit INT DEFAULT 1;

-- ──────────────────────────────────────────────
-- ADIM 3: Mevcut tablolara account_id ekleme
-- ──────────────────────────────────────────────

-- generations
ALTER TABLE generations
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- favorites
ALTER TABLE favorites
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- style_profiles
ALTER TABLE style_profiles
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- coach_weekly_plans
ALTER TABLE coach_weekly_plans
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- coach_dismissed_cards
ALTER TABLE coach_dismissed_cards
  ADD COLUMN IF NOT EXISTS account_id UUID REFERENCES connected_accounts(id) ON DELETE SET NULL;

-- ──────────────────────────────────────────────
-- ADIM 4: Index'ler (partial, sadece dolu olanlar)
-- ──────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_generations_account
  ON generations(account_id) WHERE account_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_favorites_account
  ON favorites(account_id) WHERE account_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_style_profiles_account
  ON style_profiles(account_id) WHERE account_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_coach_plans_account
  ON coach_weekly_plans(account_id) WHERE account_id IS NOT NULL;

-- ──────────────────────────────────────────────
-- ADIM 5: Ghost Account Çözümü
-- ──────────────────────────────────────────────
-- Hesap bağlamamış ama üretim yapmış kullanıcılar için
-- "default" adında sanal bir connected_account oluştur.
--
-- Mantık:
--   1. generations'da user_id'si olan AMA connected_accounts'ta
--      hiç kaydı olmayan kullanıcıları bul
--   2. Her birine platform='default' bir kayıt oluştur
--   3. Bu kayıt is_primary=true olur
--
-- NOT: Bu kullanıcılar ileride gerçek hesap bağladığında,
-- null migration ile default hesabın ID'si eski datalara atanır.
-- ──────────────────────────────────────────────

INSERT INTO connected_accounts (id, user_id, platform, username, is_primary, status, created_at, updated_at)
SELECT
  gen_random_uuid(),
  g.user_id,
  'default',
  'kullanıcı',
  true,
  'active',
  NOW(),
  NOW()
FROM (
  SELECT DISTINCT user_id FROM generations
  UNION
  SELECT DISTINCT user_id FROM favorites
) g
WHERE g.user_id NOT IN (
  SELECT user_id FROM connected_accounts
)
AND g.user_id IS NOT NULL;

-- ──────────────────────────────────────────────
-- ADIM 6: Mevcut NULL dataları primary hesaba ata
-- ──────────────────────────────────────────────
-- Şu an tüm data null. Her kullanıcının primary hesabına atıyoruz.
-- Bu sayede Faz 3'te "WHERE account_id = :active" filtresi
-- mevcut datayı da yakalar.
-- ──────────────────────────────────────────────

-- generations
UPDATE generations g
SET account_id = ca.id
FROM connected_accounts ca
WHERE g.user_id = ca.user_id
  AND ca.is_primary = true
  AND g.account_id IS NULL;

-- favorites
UPDATE favorites f
SET account_id = ca.id
FROM connected_accounts ca
WHERE f.user_id = ca.user_id
  AND ca.is_primary = true
  AND f.account_id IS NULL;

-- style_profiles
UPDATE style_profiles sp
SET account_id = ca.id
FROM connected_accounts ca
WHERE sp.user_id = ca.user_id
  AND ca.is_primary = true
  AND sp.account_id IS NULL;

-- coach_weekly_plans
UPDATE coach_weekly_plans cwp
SET account_id = ca.id
FROM connected_accounts ca
WHERE cwp.user_id = ca.user_id
  AND ca.is_primary = true
  AND cwp.account_id IS NULL;

-- coach_dismissed_cards
UPDATE coach_dismissed_cards cdc
SET account_id = ca.id
FROM connected_accounts ca
WHERE cdc.user_id = ca.user_id
  AND ca.is_primary = true
  AND cdc.account_id IS NULL;

-- ──────────────────────────────────────────────
-- DOĞRULAMA QUERY'LERİ (migration sonrası kontrol)
-- Bunları ayrı çalıştır, hata yoksa her şey tamam
-- ──────────────────────────────────────────────

-- Hiç NULL account_id kalmamış olmalı:
-- SELECT COUNT(*) as null_generations FROM generations WHERE account_id IS NULL;
-- SELECT COUNT(*) as null_favorites FROM favorites WHERE account_id IS NULL;
-- SELECT COUNT(*) as null_styles FROM style_profiles WHERE account_id IS NULL;

-- Ghost account oluşmuş mu kontrol:
-- SELECT * FROM connected_accounts WHERE platform = 'default';

-- Her kullanıcının en az 1 connected_account'u olmalı:
-- SELECT DISTINCT g.user_id
-- FROM generations g
-- LEFT JOIN connected_accounts ca ON g.user_id = ca.user_id
-- WHERE ca.id IS NULL;
-- (Bu query 0 satır döndürmeli)

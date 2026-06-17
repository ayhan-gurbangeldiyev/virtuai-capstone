-- Migration 003: Favorites soft delete (Recently Deleted)
-- Favorilere soft delete desteği ekler. deleted_at NULL = aktif, dolu = çöp kutusunda.

-- 1. deleted_at kolonu ekle
ALTER TABLE favorites ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ DEFAULT NULL;

-- 2. Aktif favoriler için partial index (performans)
CREATE INDEX IF NOT EXISTS idx_favorites_active ON favorites (user_id, created_at DESC) WHERE deleted_at IS NULL;

-- 3. Silinmiş favoriler için partial index
CREATE INDEX IF NOT EXISTS idx_favorites_deleted ON favorites (user_id, deleted_at) WHERE deleted_at IS NOT NULL;

-- 4. 30 günden eski silinmişleri temizleme fonksiyonu (opsiyonel, cron'dan da çağrılabilir)
-- SELECT count(*) FROM favorites WHERE deleted_at IS NOT NULL AND deleted_at < NOW() - INTERVAL '30 days';

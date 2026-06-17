-- 029_trend_fetch_batch_stats.sql
-- X-ingestion sağlamlaştırma (Faz 2-3): her fetch turunda per-batch (ve ileride
-- per-account) sonuç DB'ye yazılır. Eskiden per-account sonuç sadece log'daydı
-- (R9) ve zero-streak in-memory'di (restart'ta sıfırlanıyordu). Bu tablo:
--   1) kuraklık geçmişi/analizi (hangi batch ne zaman kaç tweet)
--   2) DB-backed zero-streak (restart-dayanıklı, _db_zero_streak okur)
--   3) anında batch-zero alarmının kanıt kaynağı
--
-- Additive (FK yok, mevcut tablolara dokunmaz). Düşük risk.

CREATE TABLE IF NOT EXISTS trend_fetch_batch_stats (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- bir fetch turunu gruplar (cycle uuid; trend_fetch_runs.id ile soft-ref olabilir)
    run_id         uuid,
    batch_type     text NOT NULL,            -- ai_core | ai_news_en | ai_news_tr | ai_tech | ...
    username       text,                     -- NULL = batch-toplam satırı; dolu = per-account
    tweets_fetched integer NOT NULL DEFAULT 0,
    error          text,                     -- batch/hesap hatası (varsa)
    attempts       integer DEFAULT 1,
    created_at     timestamptz NOT NULL DEFAULT now()
);

-- Zero-streak sorgusu: batch_type + (username IS NULL) + created_at DESC.
CREATE INDEX IF NOT EXISTS idx_tfbs_batch_created
    ON trend_fetch_batch_stats (batch_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tfbs_run
    ON trend_fetch_batch_stats (run_id);

-- RLS aç: yalnızca backend service-key (service_role) yazar/okur — service_role
-- RLS'i baypas eder, policy gerekmez; anon/authenticated erişimi kapanır (028 deseni).
ALTER TABLE trend_fetch_batch_stats ENABLE ROW LEVEL SECURITY;

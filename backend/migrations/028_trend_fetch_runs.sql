-- 028_trend_fetch_runs.sql
-- "Sistem Sağlığı + Huni" paneli — "Şimdi trend çek" butonunun %100 kanıtlanabilir
-- olması için minimal tetik-durum tablosu. Buton fire-and-forget DEĞİL: her tetik
-- bir satır yaratır (status='running'), arka-plan görevi done/failed'a günceller,
-- panel bu satırı okuyup "✓ N trend / ✗ hata / takıldı" gösterir.
--
-- Additive (FK yok, mevcut tablolara dokunmaz). Düşük risk.

CREATE TABLE IF NOT EXISTS trend_fetch_runs (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 'manual:<user_id>' (panel butonu) ya da 'cron' (ileride). Kim tetikledi.
    triggered_by  text NOT NULL DEFAULT 'manual',
    -- running → done | failed. running'de >10dk kalırsa panel "takıldı" sayar.
    status        text NOT NULL DEFAULT 'running',
    started_at    timestamptz NOT NULL DEFAULT now(),
    finished_at   timestamptz,
    -- refresh_all() dönüş alanları (done'da doldurulur).
    twitter_items integer,
    trends_saved  integer,
    -- failed'da kısa hata metni (secret sızdırmaz, 500 char ile sınırlı yazılır).
    error         text
);

-- Panel "son tetik" + "şu an çalışan var mı (çift-tetik kilidi)" sorguları için.
CREATE INDEX IF NOT EXISTS idx_trend_fetch_runs_started
    ON trend_fetch_runs (started_at DESC);

-- RLS aç: yalnızca backend service-key (service_role) yazar/okur — service_role
-- RLS'i baypas eder, dolayısıyla policy gerekmez ve backend bozulmaz. Bu, anon/
-- authenticated key'lerin tabloya erişimini kapatır (kardeş backend-only tablolardan
-- daha güvenli; içerik hassas değil ama gereksiz expose etmiyoruz).
ALTER TABLE trend_fetch_runs ENABLE ROW LEVEL SECURITY;

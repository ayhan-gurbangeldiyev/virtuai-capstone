-- 025_langgraph_resume.sql — LangGraph Faz 2 durability/resume idempotency altyapısı
-- (14 Haz 2026). Hepsi ADDITIVE + data-safety pre-check'li (canlı veriyle çakışmaz).
--
-- Amaç: checkpoint resume node'u baştan çalıştırır → ödeme/yan-etki node'ları
-- run_id-keyed idempotent olmalı. Bu migration o idempotency'nin DB temelini kurar.

-- 1) daily_drafts idempotency anahtarı.
--    DİKKAT: (hype_run_id, platform) DEĞİL — kart batch'leri bir run'da aynı platforma
--    HEM dictionary HEM question yazıyor (meşru, 12 mevcut grup). Doğru anahtar
--    content_type'ı da içerir: haber (content_type hep dolu: model_launch/...) tek
--    satır/platform; kart (dictionary≠question) ayrışır. Pre-check: 0 duplicate.
--    Resume'da _write_daily_draft UPSERT bununla idempotent olur (çift draft yok).
CREATE UNIQUE INDEX IF NOT EXISTS uq_daily_drafts_run_platform_ctype
  ON daily_drafts (hype_run_id, platform, content_type)
  WHERE deleted_at IS NULL;

-- 2) hype_stages idempotency — resume aynı stage'i tekrar loglamasın (UI temiz).
--    Pre-check: 0 duplicate. log_stage UPSERT(run_id, stage_order) bununla çalışır.
CREATE UNIQUE INDEX IF NOT EXISTS uq_hype_stages_run_order
  ON hype_stages (run_id, stage_order);

-- 3) image_render_log — Wiro görsel üretimi için salvage/idempotency defteri
--    (video_render_log 020 deseninin görsel eşi). Resume'da aynı prompt yeniden
--    ÜRETİLMEZ (çift ücretli render yok). 'submitting' write-ahead status: submit
--    ÖNCESİ satır yazılır, dönen URL ile 'submitted'a güncellenir → orphan-render penceresi kapanır.
CREATE TABLE IF NOT EXISTS image_render_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  prompt_sha text NOT NULL,
  slug text NOT NULL DEFAULT '',            -- wiro model slug / pipeline varyantı
  image_url text,
  status text NOT NULL DEFAULT 'submitting'
    CHECK (status IN ('submitting','submitted','completed','consumed','failed')),
  est_cost_usd numeric(8,4) DEFAULT 0,
  run_id uuid,                              -- üreten run (idempotency izi)
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  consumed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_irl_salvage
  ON image_render_log (persona_id, prompt_sha, slug, created_at DESC);

-- 4) video_render_log: HeyGen write-ahead için 'submitting' status ekle.
--    Submit ÖNCESİ 'submitting' satırı yazılır → ledger-write-failure orphan-render
--    penceresi kapanır; resume salvage 'submitting'i de görür (poll/await, re-render yok).
ALTER TABLE video_render_log DROP CONSTRAINT IF EXISTS video_render_log_status_check;
ALTER TABLE video_render_log ADD CONSTRAINT video_render_log_status_check
  CHECK (status IN ('submitting','submitted','completed','consumed','failed'));

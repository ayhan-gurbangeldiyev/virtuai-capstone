-- 020 (2026-06-10) — video_render_log: "ödenen render asla çöpe gitmez" defteri.
-- Berkay: "video işi çok pahalı, 3 defa generate etme lüksümüz yok."
-- Submit anında kayıt → süreç ölse bile iz; salvage-first → aynı script'in
-- ödenmiş render'ı varsa yeniden render YOK; bütçe consumed-olmayanları sayar.
-- Prod'a 2026-06-10 04:2x UTC elle uygulandı; bu dosya kayıt içindir.
CREATE TABLE IF NOT EXISTS video_render_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  pipeline text NOT NULL,
  script_sha text NOT NULL,
  heygen_video_id text NOT NULL,
  narration_url text,
  status text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','completed','consumed','failed')),
  est_cost_usd numeric(8,4) DEFAULT 0,
  duration_sec numeric(8,2),
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  consumed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_vrl_salvage ON video_render_log (persona_id, pipeline, script_sha, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_vrl_budget ON video_render_log (persona_id, created_at);

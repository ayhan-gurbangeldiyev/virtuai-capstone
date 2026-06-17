-- ============================================================================
-- Hype Crew — Data Model Migration 001
-- Tarih: 2026-05-15
-- Kapsam: 5 yeni tablo + 1 enum type + mevcut tablolara nullable kolon eklemeleri
-- Mevcut data: DOKUNULMAZ. Sadece additive değişiklikler.
-- ============================================================================

-- ─── ENUM ──────────────────────────────────────────────────────────────────
CREATE TYPE public.hype_memory_type AS ENUM (
  'voice_examples',      -- Kullanıcının asıl sesi (positive anchors)
  'approved_drafts',     -- Onaylanmış postlar (positive examples)
  'rejected_drafts',     -- Reddedilen postlar + sebep (negative examples)
  'performance_log',     -- Engagement metrikleri post-publish
  'trend_log',           -- İşlenmiş trendler (dedup için)
  'editor_diffs'         -- Kullanıcının yaptığı düzenlemeler (asıl voice signal)
);

-- ─── TABLE 1: hype_account_config ──────────────────────────────────────────
-- Her hesap için brand voice + content strategy + safety settings
CREATE TABLE public.hype_account_config (
  account_id uuid PRIMARY KEY REFERENCES public.connected_accounts(id) ON DELETE CASCADE,
  identity_card text,
  voice_description text,
  topics_focus text[] DEFAULT '{}',
  forbidden_topics text[] DEFAULT '{}',
  watch_accounts text[] DEFAULT '{}',
  reactive_enabled boolean DEFAULT true,
  reactive_triggers text[] DEFAULT '{}',
  follower_goal int,
  posting_cadence text DEFAULT 'daily',
  daily_post_quota int DEFAULT 2,
  auto_publish_enabled boolean DEFAULT false,
  dry_run_mode boolean DEFAULT true,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now()
);
ALTER TABLE public.hype_account_config ENABLE ROW LEVEL SECURITY;

-- ─── TABLE 2: hype_memory ──────────────────────────────────────────────────
-- CrewAI Memory backend için ana storage
CREATE TABLE public.hype_memory (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid NOT NULL REFERENCES public.connected_accounts(id) ON DELETE CASCADE,
  memory_type public.hype_memory_type NOT NULL,
  scope text NOT NULL,
  content text NOT NULL,
  metadata jsonb DEFAULT '{}',
  importance_score numeric(3,2) DEFAULT 0.5,
  created_at timestamptz DEFAULT now(),
  expires_at timestamptz
);
CREATE INDEX idx_hype_memory_scope ON public.hype_memory (scope, created_at DESC);
CREATE INDEX idx_hype_memory_account_type ON public.hype_memory (account_id, memory_type, created_at DESC);
ALTER TABLE public.hype_memory ENABLE ROW LEVEL SECURITY;

-- ─── TABLE 3: hype_runs ────────────────────────────────────────────────────
-- Her crew kickoff = 1 satır
CREATE TABLE public.hype_runs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id uuid REFERENCES public.connected_accounts(id),
  trend_id uuid REFERENCES public.trends(id),
  triggered_by text CHECK (triggered_by IN ('cron', 'manual', 'webhook')) DEFAULT 'cron',
  status text CHECK (status IN (
    'running', 'completed', 'failed',
    'rejected_by_compliance', 'rejected_by_user',
    'approved', 'published'
  )) DEFAULT 'running',
  dry_run boolean DEFAULT false,
  flow_state jsonb,
  draft_content text,
  daily_draft_id uuid REFERENCES public.daily_drafts(id),
  postiz_post_id text,
  scheduled_at timestamptz,
  total_tokens int DEFAULT 0,
  total_cost_usd numeric(10,4) DEFAULT 0,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz,
  error text
);
CREATE INDEX idx_hype_runs_account_status ON public.hype_runs (account_id, status, started_at DESC);
ALTER TABLE public.hype_runs ENABLE ROW LEVEL SECURITY;

-- ─── TABLE 4: hype_stages ──────────────────────────────────────────────────
-- Her CrewAI agent çıktısı — observability + debugging için
CREATE TABLE public.hype_stages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid NOT NULL REFERENCES public.hype_runs(id) ON DELETE CASCADE,
  agent_name text NOT NULL,
  stage_order int NOT NULL,
  input jsonb,
  output jsonb,
  model_used text,
  tokens_used int,
  duration_ms int,
  guardrail_retries int DEFAULT 0,
  status text CHECK (status IN ('success', 'failed', 'skipped', 'retried')) DEFAULT 'success',
  error text,
  started_at timestamptz DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX idx_hype_stages_run ON public.hype_stages (run_id, stage_order);
ALTER TABLE public.hype_stages ENABLE ROW LEVEL SECURITY;

-- ─── TABLE 5: hype_feedback ────────────────────────────────────────────────
-- Kullanıcı approve/reject/edit kayıtları (asıl learning signal)
CREATE TABLE public.hype_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  run_id uuid REFERENCES public.hype_runs(id),
  account_id uuid NOT NULL REFERENCES public.connected_accounts(id),
  user_id uuid REFERENCES auth.users(id),
  action text CHECK (action IN ('approved', 'rejected', 'edited', 'expired')) NOT NULL,
  rejection_category text CHECK (rejection_category IN (
    'too_long', 'too_short', 'tone_off', 'wrong_topic', 'inaccurate',
    'already_posted', 'low_quality', 'off_brand', 'other'
  )),
  free_text_feedback text,
  original_content text,
  edited_content text,
  content_diff jsonb,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_hype_feedback_account ON public.hype_feedback (account_id, created_at DESC);
ALTER TABLE public.hype_feedback ENABLE ROW LEVEL SECURITY;

-- ─── Mevcut tablolara nullable kolon eklemeleri ────────────────────────────
-- connected_accounts: Postiz mapping
ALTER TABLE public.connected_accounts ADD COLUMN IF NOT EXISTS postiz_integration_id text;
ALTER TABLE public.connected_accounts ADD COLUMN IF NOT EXISTS postiz_provider text DEFAULT 'twitter';

-- daily_drafts: Hype Crew integration (mevcut Magic Morning verileri etkilenmez)
ALTER TABLE public.daily_drafts ADD COLUMN IF NOT EXISTS hype_run_id uuid REFERENCES public.hype_runs(id);
ALTER TABLE public.daily_drafts ADD COLUMN IF NOT EXISTS scheduled_at timestamptz;
ALTER TABLE public.daily_drafts ADD COLUMN IF NOT EXISTS postiz_post_id text;

-- ─── RLS Policies ──────────────────────────────────────────────────────────
-- Service role bypass otomatik; authenticated user account_id ownership ile sınırlı

CREATE POLICY hype_account_config_owner ON public.hype_account_config
  FOR ALL TO authenticated
  USING (account_id IN (
    SELECT id FROM public.connected_accounts WHERE user_id = (SELECT auth.uid())
  ));

CREATE POLICY hype_memory_owner ON public.hype_memory
  FOR ALL TO authenticated
  USING (account_id IN (
    SELECT id FROM public.connected_accounts WHERE user_id = (SELECT auth.uid())
  ));

CREATE POLICY hype_runs_owner ON public.hype_runs
  FOR ALL TO authenticated
  USING (account_id IN (
    SELECT id FROM public.connected_accounts WHERE user_id = (SELECT auth.uid())
  ));

CREATE POLICY hype_stages_via_run ON public.hype_stages
  FOR ALL TO authenticated
  USING (run_id IN (
    SELECT r.id FROM public.hype_runs r
    JOIN public.connected_accounts a ON a.id = r.account_id
    WHERE a.user_id = (SELECT auth.uid())
  ));

CREATE POLICY hype_feedback_owner ON public.hype_feedback
  FOR ALL TO authenticated
  USING (account_id IN (
    SELECT id FROM public.connected_accounts WHERE user_id = (SELECT auth.uid())
  ));

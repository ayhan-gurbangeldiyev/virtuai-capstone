/**
 * Hype Crew API wrapper.
 *
 * Backend: /api/hype/* — auto-drafts approval, config, runs.
 * All requests carry JWT (via lib/api.js interceptor) + X-Active-Account-Id.
 */
import api from "@/lib/api";

/**
 * Home v1 — operator-facing editorial briefing.
 * Source of truth: projects/post-capstone/home-v1-implementation-plan.md.
 *
 * Step 1 returns a status_only hero + real pause state + real cron liveness.
 * Decision-pair selection and Sonnet composition arrive in Steps 2–3.
 */
export async function fetchHomeSummary(accountId) {
  const { data } = await api.get(
    `/hype/home-summary?account_id=${encodeURIComponent(accountId)}`,
  );
  return data;
}

export async function fetchEditorialTrail(days = 7) {
  const { data } = await api.get(`/hype/editorial-trail?days=${days}`);
  return data;
}

// C2 (2026-06-07) — Lifecycle endpoint. 7-join coalesce surfaced as
// operator-language outer keys + an `engineer` drawer for the technical
// detail. See backend/routes/hype.py:get_draft_lifecycle.
export async function fetchDraftLifecycle(draftId) {
  const { data } = await api.get(
    `/hype/lifecycle/${encodeURIComponent(draftId)}`,
  );
  return data;
}

export async function setPauseState(accountId, paused) {
  const { data } = await api.post(
    `/hype/kill-switch?account_id=${encodeURIComponent(accountId)}`,
    { paused },
  );
  return data;
}

export async function listAutoDrafts({ accountId, status = "pending", platform, limit = 50 } = {}) {
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  if (status) params.set("status", status);
  if (platform) params.set("platform", platform);
  if (limit) params.set("limit", String(limit));
  // Berkay 6 Haz 2026 — cache-bust the GET so a long-open AutoDrafts
  // tab can't serve a stale heuristically-cached response after a
  // server-side edit. Combined with the page-level 30s polling +
  // visibility-change refetch, ensures the rendered list matches the
  // current DB state without forcing a hard reload.
  //
  // PR #18 originally added `Cache-Control: no-cache` + `Pragma: no-cache`
  // as request headers. Those are NOT in the backend's CORSMiddleware
  // allow_headers (Authorization, Content-Type, X-TH-Client,
  // X-Requested-With, X-Admin-Key, X-TH-Timestamp, X-TH-Nonce,
  // X-Active-Account-Id) so the preflight OPTIONS failed → every
  // listAutoDrafts call surfaced as "Network Error" in the UI.
  // The _t cache-bust param alone is sufficient to defeat any
  // heuristic browser cache; the headers were redundant + breaking.
  params.set("_t", String(Date.now()));
  const { data } = await api.get(`/hype/drafts/auto?${params.toString()}`);
  return data;
}

export async function approveDraft(draftId) {
  const { data } = await api.post(`/hype/drafts/${draftId}/approve`);
  return data;
}

/**
 * Phase 40 — Approve all drafts under a content_thread_id in a single call.
 * Backend builds a multi-platform Postiz schedule request and updates every
 * row's status/postiz_post_id/scheduled_at in one atomic pass.
 */
export async function approveThread(threadId) {
  const { data } = await api.post(`/hype/threads/${threadId}/approve`);
  return data;
}

export async function rejectDraft(
  draftId,
  {
    category = "other",
    feedback = "",
    rejection_target = "both",          // Phase 28: 'text' | 'image' | 'both'
    image_rejection_reason = null,      // Phase 28: deformed_hand | fake_logo | ...
  } = {},
) {
  const { data } = await api.post(`/hype/drafts/${draftId}/reject`, {
    category,
    feedback,
    rejection_target,
    image_rejection_reason,
  });
  return data;
}

export async function editDraft(draftId, { edited_content, feedback = "" }) {
  const { data } = await api.post(`/hype/drafts/${draftId}/edit`, { edited_content, feedback });
  return data;
}

// AI-refine: returns N variants without persisting them. User picks one and
// then calls editDraft() to commit. Pattern mirrors XAIModule's /api/evolve.
export async function refineDraft(draftId, { feedback = "", quick_tags = [], variant_count = 3 } = {}) {
  const { data } = await api.post(`/hype/drafts/${draftId}/refine`, {
    feedback,
    quick_tags,
    variant_count,
  });
  return data;  // { variants: [{index, content}], tokens_used }
}

// Phase 28.P — iterative refinement: each call yields ONE new variant
// + records iteration history. Max 10 iterations per draft (server-enforced).
//
// Response shape:
// {
//   version: int (1-10),
//   content: string,
//   tokens_used: int,
//   cost_usd: float,
//   remaining_attempts: int,
//   max_iterations: 10,
//   iterations: [{ version, content, status, rejection_category }]
// }
//
// On 409 → caller must show "max attempts reached" UI.
export async function iterateDraft(
  draftId,
  {
    rejection_category = "other",
    rejection_feedback = "",
    rejection_target = "both",
    image_rejection_reason = null,
    quick_tags = [],
    // Phase 43.B.4 — anchor-preserve regen. When true, the LLM is told
    // to carry `preserved_segments` byte-for-byte and only rewrite the
    // surrounding text. The backend verifies post-LLM and reports the
    // success rate in response.preserve_stats so the UI can warn when
    // the model mangled the user's anchor.
    preserve_user_edits = false,
    preserved_segments = [],
  } = {}
) {
  const body = {
    rejection_category,
    rejection_feedback,
    rejection_target,
    image_rejection_reason,
    quick_tags,
  };
  if (preserve_user_edits) {
    body.preserve_user_edits = true;
    body.preserved_segments = preserved_segments;
  }
  const { data } = await api.post(`/hype/drafts/${draftId}/iterate`, body);
  return data;
  // Phase 43.B.4 — when preserve_user_edits=true, response includes:
  //   preserve_stats: { requested, preserved, lost, success_rate, miss_samples }
}

// Phase 28.R-Lite — server-side truth for IterationDialog re-open.
// The draft.iterations array carried in the list response goes stale once
// new iterations are persisted; this fetches the authoritative latest chain.
export async function getDraftIterations(draftId) {
  const { data } = await api.get(`/hype/drafts/${draftId}/iterations`);
  return data;  // { draft_id, iterations: [{version, content, status, image_url, ...}] }
}

// Phase 28.R-Lite-V2 — Cancel a previously-approved draft.
// Backend cancels Postiz schedule and flips status to 'auto_rejected'.
// Throws 409 with already_published detail when scheduled_at has passed.
export async function cancelApprovedDraft(draftId) {
  const { data } = await api.post(`/hype/drafts/${draftId}/cancel-approval`);
  return data;
}

// Phase 28.R-Lite Sprint 1B — image regen job polling.
// When iterate is called with scope='image'|'both', the response includes
// an image_job_id. Frontend polls this every 3-5s until status=completed
// (image_url ready) or failed.
export async function getImageRegenJob(jobId) {
  const { data } = await api.get(`/hype/image-regen-jobs/${jobId}`);
  return data;
}

export async function getConfig(accountId) {
  const { data } = await api.get(`/hype/config/${accountId}`);
  return data;
}

export async function updateConfig(accountId, body) {
  const { data } = await api.patch(`/hype/config/${accountId}`, body);
  return data;
}

export async function listRecentRuns({ accountId, limit = 20 } = {}) {
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  if (limit) params.set("limit", String(limit));
  const { data } = await api.get(`/hype/runs/recent?${params.toString()}`);
  return data;
}

// Crew Akışı — full pipeline flow for a single run (7 fixed nodes + drafts + trust signals)
export async function getRunFlow(runId) {
  const { data } = await api.get(`/hype/runs/${runId}/flow`);
  return data;  // { run, nodes, drafts, trust_signals, default_selected_node }
}

// Phase 17.5 — per-agent breakdown for a draft
export async function getDraftStages(draftId) {
  const { data } = await api.get(`/hype/drafts/${draftId}/stages`);
  return data;  // { stages: [{stage_order, agent_name, output, ...}], run: {...} }
}

// Phase 17.4 — user's explicit approve/reject/edit counts (NOT system auto-rejects)
export async function getUserFeedbackStats({ accountId, days = 7 } = {}) {
  const params = new URLSearchParams();
  if (accountId) params.set("account_id", accountId);
  if (days) params.set("days", String(days));
  const { data } = await api.get(`/hype/stats/user-feedback?${params.toString()}`);
  return data;  // { days, counts: {approved, rejected, edited}, total }
}

// Phase 17.2 — user's style profiles for the Hype config dropdown
export async function listStyleProfiles() {
  const { data } = await api.get("/hype/style-profiles");
  return data;  // { items: [{id, name, source_type, tweet_count, ...}], count }
}

// ─── Phase 43.D / Tier 2 — persona introspection ──────────────────────

// Workspace-scoped persona list. Used by AutonomyScorePage and the
// Edit Elevation page to pick which persona to query.
export async function listPersonas() {
  const { data } = await api.get("/hype/personas");
  return data;  // { items: [{id, slug, display_name, ..._autonomy_unlocked, ...}], count }
}

// Phase 43.D — live per-bucket autonomy snapshot for a persona.
export async function getPersonaAutonomyScore(personaId) {
  if (!personaId) throw new Error("getPersonaAutonomyScore: personaId required");
  const { data } = await api.get(`/hype/personas/${personaId}/autonomy-score`);
  return data;
  // {
  //   persona_id, slug,
  //   buckets: {
  //     text:  { sample_count, sample_min, reject_count, edit_count,
  //              reject_rate, edit_rate, passes_sample, passes_reject,
  //              passes_edit, currently_unlocked, qualifies_for_unlock },
  //     image: {...}, video: {...}
  //   },
  //   last_autonomy_check_at, last_consecutive_reject_at, lookback_days,
  // }
}

// Phase 43.D — Edit Elevation candidates list + decisions
export async function listEditElevations(personaId, { status = "pending", limit = 50 } = {}) {
  if (!personaId) throw new Error("listEditElevations: personaId required");
  const params = new URLSearchParams();
  params.set("status", status);
  params.set("limit", String(limit));
  const { data } = await api.get(
    `/hype/personas/${personaId}/edit-elevations?${params.toString()}`
  );
  return data;  // { persona_id, items: [...], count }
}

export async function acceptEditElevation(elevationId, { scope = "trend_type", notes } = {}) {
  if (!elevationId) throw new Error("acceptEditElevation: elevationId required");
  const payload = { scope };
  if (notes && notes.trim()) payload.notes = notes.trim();
  const { data } = await api.post(`/hype/elevations/${elevationId}/accept`, payload);
  return data;  // { status: 'accepted', elevation_id, promoted_scope, editor_diffs_promoted }
}

export async function rejectEditElevation(elevationId, { notes } = {}) {
  if (!elevationId) throw new Error("rejectEditElevation: elevationId required");
  const payload = {};
  if (notes && notes.trim()) payload.notes = notes.trim();
  const { data } = await api.post(`/hype/elevations/${elevationId}/reject`, payload);
  return data;  // { status: 'rejected', elevation_id }
}

// ─── Tier 3 — System Health (cost / reliability / postiz) ────────────

export async function getQualityHealth() {
  const { data } = await api.get("/hype/quality-health");
  return data;
}

// ─── Sistem Sağlığı + Huni (/control/sistem) ────────────────────────
// "Sistem çalışıyor mu, nerede tıkandı" — supply/huni/son-run/cron + bottleneck.
export async function getFunnelHealth() {
  const { data } = await api.get("/hype/funnel-health");
  return data;
}

// "Şimdi trend çek" — manuel trend-fetch tetikler. Arka-planda çalışır, 202 +
// fetch_run_id döner; sonucu funnel-health.fetch.run satırından poll'la.
// 409 = zaten çalışıyor, 429 = çok sık (son taramadan 5 dk geçmeli).
export async function triggerTrendFetch() {
  const { data } = await api.post("/hype/trend-fetch/trigger");
  return data;  // { status: 'started', fetch_run_id, message }
}

export async function getSystemHealth() {
  const { data } = await api.get("/hype/system-health");
  return data;
  // {
  //   cost: { today_runs, today_cost_usd, today_cap_usd, today_pct,
  //           week_*, regen_today_*, video_*, video_personas: [...] },
  //   reliability: { today_fail_rate, today_fail_rate_pct, week_*,
  //                  regen_today_*, runs_by_status, recent_failures: [...],
  //                  tone: 'ok'|'warn'|'danger', warn_threshold, danger_threshold },
  //   postiz: { ok, error?, http_status?, recent_count, last_published_at,
  //             integrations_count },
  //   modes: { dry_run_mode_anywhere, auto_publish_enabled_anywhere },
  //   as_of
  // }
}

// PATCH hype_account_config (existing endpoint) — wraps the run-cost cap.
export async function updateAccountConfig(accountId, body) {
  if (!accountId) throw new Error("updateAccountConfig: accountId required");
  const { data } = await api.patch(`/hype/config/${accountId}`, body);
  return data;
}

// Tier 3 — PATCH persona-level budget knobs (video budget + video_enabled).
export async function updatePersonaBudget(personaId, body) {
  if (!personaId) throw new Error("updatePersonaBudget: personaId required");
  const { data } = await api.patch(`/hype/personas/${personaId}/budget`, body);
  return data;
}

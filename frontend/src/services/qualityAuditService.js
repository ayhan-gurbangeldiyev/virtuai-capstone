/**
 * Phase 43.E — Quality Audit dashboard API wrapper.
 *
 * Backend: /api/hype/quality-audits/* + /audits/{id}/rate
 * All requests carry JWT via lib/api.js interceptor.
 */
import api from "@/lib/api";

/**
 * List pending audits (current month) or rated history.
 * @param {object} opts
 * @param {"pending"|"history"|"all"} [opts.status="pending"]
 * @param {number} [opts.limit=60]
 */
export async function listQualityAudits({ status = "pending", limit = 60 } = {}) {
  const params = new URLSearchParams();
  params.set("status", status);
  params.set("limit", String(limit));
  const { data } = await api.get(`/hype/quality-audits?${params.toString()}`);
  return data; // { items, count, freeze_meta, freeze_threshold, current_audit_month }
}

/**
 * Lightweight summary for sidebar badge + FrozenBanner state.
 */
export async function getQualityAuditSummary() {
  const { data } = await api.get(`/hype/quality-audits/summary`);
  return data; // { personas:[{persona_id,slug,pending,pass,fail,rated,total,freeze_threshold}], pending_total, auto_publish_enabled_anywhere, current_audit_month }
}

/**
 * Submit a Pass/Fail rating. `notes` is optional and only meaningful on Fail.
 * @param {string} auditId
 * @param {object} body
 * @param {"pass"|"fail"} body.rating
 * @param {string} [body.notes]
 */
export async function rateAudit(auditId, { rating, notes } = {}) {
  if (!auditId) throw new Error("rateAudit: auditId required");
  if (!["pass", "fail"].includes(rating)) {
    throw new Error(`rateAudit: invalid rating ${rating}`);
  }
  const payload = { rating };
  if (notes && notes.trim()) payload.notes = notes.trim();
  const { data } = await api.post(`/hype/audits/${auditId}/rate`, payload);
  return data; // { audit_id, rating, fail_count_this_month, rated_count_this_month, freeze_threshold, froze_accounts }
}

/**
 * Manually trigger a new audit cycle for one persona or the whole workspace.
 * Backend refuses with 409 if a pending audit already exists this month.
 * @param {object} [opts]
 * @param {string} [opts.personaId]
 * @param {number} [opts.sampleSize=10]
 */
export async function triggerQualityAudit({ personaId, sampleSize = 10 } = {}) {
  const payload = { sample_size: sampleSize };
  if (personaId) payload.persona_id = personaId;
  const { data } = await api.post(`/hype/quality-audits/trigger`, payload);
  return data; // { audit_month, personas:[{persona_id, slug, inserted, audit_ids, skipped?}], inserted_total }
}

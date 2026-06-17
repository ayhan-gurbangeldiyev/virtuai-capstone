/**
 * Executive Board API wrapper (Phase 26).
 *
 * Backend: /api/exec/* — C-suite decision queue, memos, meetings.
 */
import api from "@/lib/api";

const qp = (obj) => {
  const p = new URLSearchParams();
  Object.entries(obj || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  });
  return p.toString();
};

export async function listDecisions({ accountId, status, role, days = 7, limit = 100 } = {}) {
  const params = qp({ account_id: accountId, status, role, days, limit });
  const { data } = await api.get(`/exec/decisions?${params}`);
  return data;
}

export async function approveExecDecision(decisionId) {
  const { data } = await api.post(`/exec/decisions/${decisionId}/approve`);
  return data;
}

export async function rejectExecDecision(decisionId) {
  const { data } = await api.post(`/exec/decisions/${decisionId}/reject`);
  return data;
}

export async function revertExecDecision(decisionId) {
  const { data } = await api.post(`/exec/decisions/${decisionId}/revert`);
  return data;
}

export async function listMemos({ accountId, role, days = 7, limit = 100 } = {}) {
  const params = qp({ account_id: accountId, role, days, limit });
  const { data } = await api.get(`/exec/memos?${params}`);
  return data;
}

export async function listMeetings({ accountId, kind, days = 7, limit = 50 } = {}) {
  const params = qp({ account_id: accountId, kind, days, limit });
  const { data } = await api.get(`/exec/meetings?${params}`);
  return data;
}

export async function execSummary(accountId) {
  const { data } = await api.get(`/exec/summary?${qp({ account_id: accountId })}`);
  return data;
}

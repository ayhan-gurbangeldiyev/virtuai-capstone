// Phase 36 — Postiz Social Media Manager API wrapper
// Mirrors backend/routes/postiz.py endpoints; JWT auth handled by lib/api.js.
import api from "@/lib/api";

export async function listPosts({ status, platform, days = 30 } = {}) {
  const p = new URLSearchParams();
  if (status) p.set("status", status);
  if (platform) p.set("platform", platform);
  if (days) p.set("days", String(days));
  const { data } = await api.get(`/postiz/posts?${p.toString()}`);
  return data;
}

export async function getPost(postId) {
  const { data } = await api.get(`/postiz/posts/${postId}`);
  return data;
}

export async function schedulePost(body) {
  // body: { scheduled_at, posts:[{integration_id,provider,content,title,tags,media}], publish_now }
  const { data } = await api.post(`/postiz/posts`, body);
  return data;
}

export async function updatePost(postId, body) {
  // body: { group_id, scheduled_at, posts:[...] }
  const { data } = await api.put(`/postiz/posts/${postId}`, body);
  return data;
}

export async function cancelPost(postId) {
  const { data } = await api.post(`/postiz/posts/${postId}/cancel`);
  return data;
}

export async function changePostStatus(postId, status) {
  // status: 'draft' | 'schedule'
  const { data } = await api.put(`/postiz/posts/${postId}/status`, { status });
  return data;
}

export async function listIntegrations() {
  const { data } = await api.get(`/postiz/integrations`);
  return data;
}

export async function getNextSlot(integrationId) {
  const p = new URLSearchParams();
  if (integrationId) p.set("integration_id", integrationId);
  const { data } = await api.get(`/postiz/slot?${p.toString()}`);
  return data;
}

export async function uploadFromUrl(url) {
  const { data } = await api.post(`/postiz/upload`, { url });
  return data;
}

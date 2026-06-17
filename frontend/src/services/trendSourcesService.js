/**
 * Trend X-source management API wrapper.
 *
 * Endpoints under /api/trends/sources. Used by TrendDashboardPage → gear icon
 * → TrendSourcesSheet to manage the X accounts that feed the trends pipeline.
 */
import api from "@/lib/api";

export async function listTrendSources() {
  const { data } = await api.get("/trends/sources");
  return data;  // { sources: { ai_tech: [...], tr_haber: [...], spor: [...] }, total }
}

export async function addTrendSource({ batch_type, username, fetch_limit }) {
  const payload = { batch_type, username };
  if (fetch_limit) payload.fetch_limit = fetch_limit;
  const { data } = await api.post("/trends/sources", payload);
  return data;
}

export async function removeTrendSource(sourceId) {
  const { data } = await api.delete(`/trends/sources/${sourceId}`);
  return data;
}

export async function toggleTrendSource(sourceId) {
  const { data } = await api.patch(`/trends/sources/${sourceId}/toggle`);
  return data;
}

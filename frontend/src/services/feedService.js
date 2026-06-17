import api from "@/lib/api";

export async function fetchFeed(params = {}) {
  const searchParams = new URLSearchParams();
  if (params.batch_type) searchParams.set("batch_type", params.batch_type);
  if (params.limit) searchParams.set("limit", String(params.limit));
  if (params.offset) searchParams.set("offset", String(params.offset));
  if (params.sort) searchParams.set("sort", params.sort);

  const { data } = await api.get(`/feed?${searchParams.toString()}`);
  return data;
}

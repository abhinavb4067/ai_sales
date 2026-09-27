import { apiClient } from "./apiClient";

export async function listApiKeys() {
  const { data } = await apiClient.get("/api-keys/");
  return data.results ?? data;
}

export async function createApiKey(name) {
  const { data } = await apiClient.post("/api-keys/", { name });
  return data;
}

export async function revokeApiKey(id) {
  const { data } = await apiClient.post(`/api-keys/${id}/revoke/`);
  return data;
}

export async function getUsageSummary() {
  const { data } = await apiClient.get("/usage/summary/");
  return data;
}

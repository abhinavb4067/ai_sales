import { apiClient } from "./apiClient";

export async function listAgents() {
  const { data } = await apiClient.get("/agents/");
  return data.results ?? data;
}

export async function getAgent(id) {
  const { data } = await apiClient.get(`/agents/${id}/`);
  return data;
}

export async function createAgent(payload) {
  const { data } = await apiClient.post("/agents/", payload);
  return data;
}

export async function updateAgent(id, payload) {
  const { data } = await apiClient.patch(`/agents/${id}/`, payload);
  return data;
}

export async function deleteAgent(id) {
  await apiClient.delete(`/agents/${id}/`);
}

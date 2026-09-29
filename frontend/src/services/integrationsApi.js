import { apiClient } from "./apiClient";

export async function listIntegrations() {
  const { data } = await apiClient.get("/integrations/");
  return data.results ?? data;
}

export async function createIntegration(payload) {
  const { data } = await apiClient.post("/integrations/", payload);
  return data;
}

export async function deleteIntegration(id) {
  await apiClient.delete(`/integrations/${id}/`);
}

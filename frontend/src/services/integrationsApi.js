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

export async function completeWhatsAppEmbeddedSignup({ agentId, code, wabaId, phoneNumberId }) {
  const { data } = await apiClient.post("/integrations/whatsapp/embedded-signup/", {
    agent_id: agentId,
    code,
    waba_id: wabaId,
    phone_number_id: phoneNumberId,
  });
  return data;
}

import { apiClient } from "./apiClient";

export async function listLeads(params = {}) {
  const { data } = await apiClient.get("/leads/", { params });
  return data.results ?? data;
}

export async function listLeadStages() {
  const { data } = await apiClient.get("/lead-stages/");
  return data.results ?? data;
}

export async function changeLeadStage(leadId, stageId) {
  const { data } = await apiClient.post(`/leads/${leadId}/change_stage/`, { stage: stageId });
  return data;
}

export async function addLeadNote(leadId, content) {
  const { data } = await apiClient.post(`/leads/${leadId}/add_note/`, { content });
  return data;
}

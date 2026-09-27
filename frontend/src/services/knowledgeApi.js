import { apiClient } from "./apiClient";

export async function listKnowledge() {
  const { data } = await apiClient.get("/knowledge/");
  return data.results ?? data;
}

export async function createKnowledgeEntry(payload) {
  const { data } = await apiClient.post("/knowledge/", payload);
  return data;
}

export async function createKnowledgeFile({ title, sourceType, agent, file }) {
  const formData = new FormData();
  formData.append("title", title);
  formData.append("source_type", sourceType);
  if (agent) formData.append("agent", agent);
  formData.append("file", file);
  const { data } = await apiClient.post("/knowledge/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function deleteKnowledgeEntry(id) {
  await apiClient.delete(`/knowledge/${id}/`);
}

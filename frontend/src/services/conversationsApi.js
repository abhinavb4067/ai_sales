import { apiClient } from "./apiClient";

export async function listConversations(params = {}) {
  const { data } = await apiClient.get("/conversations/", { params });
  return data.results ?? data;
}

export async function getConversation(id) {
  const { data } = await apiClient.get(`/conversations/${id}/`);
  return data;
}

export async function takeoverConversation(id) {
  const { data } = await apiClient.post(`/conversations/${id}/takeover/`);
  return data;
}

export async function resolveConversation(id) {
  const { data } = await apiClient.post(`/conversations/${id}/resolve/`);
  return data;
}

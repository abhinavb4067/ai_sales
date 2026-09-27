import { apiClient } from "./apiClient";

export async function sendPlaygroundMessage({ agentId, conversationId, message }) {
  const { data } = await apiClient.post("/playground/chat/", {
    agent_id: agentId,
    conversation_id: conversationId ?? undefined,
    message,
  });
  return data;
}

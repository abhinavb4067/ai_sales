import { apiClient } from "./apiClient";

export async function listWebhookSubscriptions() {
  const { data } = await apiClient.get("/webhook-subscriptions/");
  return data.results ?? data;
}

export async function createWebhookSubscription(payload) {
  const { data } = await apiClient.post("/webhook-subscriptions/", payload);
  return data;
}

export async function updateWebhookSubscription(id, payload) {
  const { data } = await apiClient.patch(`/webhook-subscriptions/${id}/`, payload);
  return data;
}

export async function deleteWebhookSubscription(id) {
  await apiClient.delete(`/webhook-subscriptions/${id}/`);
}

export async function listWebhookDeliveries(subscriptionId) {
  const { data } = await apiClient.get("/webhook-deliveries/", {
    params: subscriptionId ? { subscription: subscriptionId } : {},
  });
  return data.results ?? data;
}

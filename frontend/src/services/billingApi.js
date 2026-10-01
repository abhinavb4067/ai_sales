import { apiClient } from "./apiClient";

export async function listPlans() {
  const { data } = await apiClient.get("/billing/plans/");
  return data;
}

export async function getSubscription() {
  const { data } = await apiClient.get("/billing/subscription/");
  return data;
}

export async function changePlan(planCode) {
  const { data } = await apiClient.post("/billing/subscription/change-plan/", { plan_code: planCode });
  return data;
}

export async function cancelSubscription() {
  const { data } = await apiClient.post("/billing/subscription/cancel/");
  return data;
}

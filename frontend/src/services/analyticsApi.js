import { apiClient } from "./apiClient";

export async function fetchAnalyticsOverview(days = 30) {
  const { data } = await apiClient.get("/analytics/overview/", { params: { days } });
  return data;
}

import { apiClient } from "./apiClient";

export async function fetchCurrentBusiness() {
  const { data } = await apiClient.get("/business/me/");
  return data;
}

import { apiClient } from "./apiClient";
import { setAccessToken, clearTokens } from "./tokenStore";

export async function register({ name, email, password, businessName }) {
  const { data } = await apiClient.post("/auth/register/", {
    name,
    email,
    password,
    business_name: businessName,
  });
  setAccessToken(data.tokens.access, data.tokens.refresh);
  return data.user;
}

export async function login({ email, password }) {
  const { data } = await apiClient.post("/auth/login/", { email, password });
  setAccessToken(data.tokens.access, data.tokens.refresh);
  return data.user;
}

export async function logout(refreshToken) {
  try {
    await apiClient.post("/auth/logout/", { refresh: refreshToken });
  } finally {
    clearTokens();
  }
}

export async function fetchCurrentUser() {
  const { data } = await apiClient.get("/auth/me/");
  return data.user;
}

import { apiClient } from "./apiClient";

export async function listMembers() {
  const { data } = await apiClient.get("/business/members/");
  return data.results ?? data;
}

export async function inviteMember(email, role) {
  const { data } = await apiClient.post("/business/members/invite/", { email, role });
  return data;
}

export async function revokeMember(id) {
  const { data } = await apiClient.post(`/business/members/${id}/revoke/`);
  return data;
}

export async function changeMemberRole(id, role) {
  const { data } = await apiClient.post(`/business/members/${id}/role/`, { role });
  return data;
}

export async function listMyInvites() {
  const { data } = await apiClient.get("/team/my-invites/");
  return data.results ?? data;
}

export async function acceptInvite(id) {
  const { data } = await apiClient.post(`/team/invites/${id}/accept/`);
  return data;
}

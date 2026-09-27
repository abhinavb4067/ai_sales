// Token storage strategy for Phase 1:
//   - access token: kept ONLY in memory (module-level variable). Never
//     persisted to localStorage/sessionStorage — lost on hard refresh by
//     design, and immediately re-derived from the refresh token.
//   - refresh token: sessionStorage (survives reload within a tab, cleared
//     when the tab closes) — a deliberately narrower blast radius than
//     localStorage, which persists indefinitely and is readable by any
//     script for the lifetime of the browser profile.
//
// This is a practical middle ground given the backend issues tokens as
// JSON (not httpOnly cookies) in Phase 1. Moving refresh-token storage to
// a backend-set httpOnly cookie is the recommended hardening for a later
// phase — flagged here rather than done silently.

let accessToken = null;

const REFRESH_KEY = "ai_sales_refresh_token";

export function setAccessToken(access, refresh) {
  accessToken = access;
  if (refresh) {
    sessionStorage.setItem(REFRESH_KEY, refresh);
  }
}

export function getAccessToken() {
  return accessToken;
}

export function getRefreshToken() {
  return sessionStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  accessToken = null;
  sessionStorage.removeItem(REFRESH_KEY);
}

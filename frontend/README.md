# AI Sales & Support Agent — Dashboard (Phase 1)

React + Vite dashboard.

## Setup

```bash
cd frontend
npm install
cp .env.example .env   # points at the backend API, defaults to localhost:8000
npm run dev
```

Open http://localhost:5173

## Structure

- `src/services/` — the only place axios is called (`apiClient.js` handles
  JWT attach + automatic refresh-on-401; one module per API resource).
- `src/context/AuthContext.jsx` + `src/hooks/useAuth.js` — auth state.
- `src/routes/ProtectedRoute.jsx` — redirects unauthenticated users to `/login`.
- `src/pages/` — one folder per feature area (auth, dashboard, agents,
  knowledge, playground).

## Token storage (Phase 1 tradeoff, documented)

The access token is held only in memory; the refresh token is kept in
`sessionStorage` rather than `localStorage` to limit its lifetime/exposure.
See the comment in `src/services/tokenStore.js` — the recommended
hardening for a later phase is backend-issued httpOnly cookies for the
refresh token, which isn't implemented yet since Phase 1's auth endpoints
return tokens as JSON.

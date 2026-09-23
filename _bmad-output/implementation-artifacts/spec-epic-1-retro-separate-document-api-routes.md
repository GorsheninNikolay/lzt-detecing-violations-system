---
title: 'Separate run document and API routes'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="user-owned intent">

## Intent

**Problem:** Vite proxies every `/runs` request to the backend, so direct navigation or reload of `/runs/{run_id}` returns JSON instead of the Run Workspace document.

**Approach:** Keep `/runs/{run_id}` as the browser page, send client API requests through `/api/runs/*`, and proxy that API prefix to the backend's existing `/runs/*` routes. Preserve the exact body and idempotency key when retrying a pending request saved with an older endpoint.

</frozen-after-approval>

## Implementation Notes

- `web/vite.config.ts` proxies `/api/runs/*` to backend `/runs/*`; `/runs/{run_id}` remains a document route.
- `web/src/App.tsx` uses the API prefix for submission, status, and artifacts. A saved legacy `/runs/*` submission endpoint is translated on retry without changing its body or idempotency key.
- `web/src/App.test.tsx` covers the new client paths and legacy pending retry. `README.md` and `web/README.md` describe the development and production routing contract.
- Verification: `npm test -- --run` passed (23 tests), `npm run build` passed, and `git diff --check` passed. With Vite and a temporary backend running locally, two direct `GET /runs/{run_id}` requests returned HTML; `GET /api/runs/{run_id}` and its artifact path returned backend JSON after `/api` was removed. The temporary servers were stopped.
- Independent review found no functional defect in the route split. Production deployment was not performed or verified.

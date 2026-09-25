# Web app

The Russian New Analysis page submits one JPEG or an ordered series of 2–8 JPEGs to the existing observation API. Each image must be at most 16,000,000 bytes and 40 million pixels. The browser checks JPEG decoding before submission. A returned `run_id` opens `/runs/{run_id}`; this route currently confirms the run identity and reads its server state. Pipeline progress and results are later stories.

From `web/`:

```sh
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Vite serves the app at `/runs/{run_id}` and `/provider-comparison`, and proxies `/api/*` to the matching backend paths at `http://127.0.0.1:8000`. Start the backend separately with an admitted `OBSERVER_PROFILE_ID` and `OBSERVER_SNAPSHOT_DIR` as described in the root README. The backend must be ready before submission. For production, proxy `/api/runs/*` to `/runs/*` and `/api/provider-comparison` to `/provider-comparison` on the backend; serve the app with history fallback for `/runs/{run_id}`, `/provider-comparison`, and `/about`.

```sh
npm test -- --run
npm run build
```

The UI uses `observation_only` with explicit scenario, area, timezone-aware period, and excavator/dump-truck scope. It does not evaluate stage rules or infer that equipment is absent from the whole site. An uncertain response keeps the exact JSON body and idempotency key for retry until the server returns a run ID or a definitive rejection. The pending request can be retried after refreshing the same tab; small requests use session storage and larger requests use IndexedDB with a session-scoped pointer. Refreshing discards editable local files, so resolve the pending request before starting another analysis.

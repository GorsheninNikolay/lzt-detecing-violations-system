---
title: 'Submit an Observation in the Responsive Web App'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '431af9df9e12548c5e38badab1f950acdb4cf12b'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      Rendered 320 CSS pixel, 200% zoom, text spacing, and touch behavior remains unverified.
    evidence: |-
      Component tests run in jsdom and cannot measure layout or physical targets. The user's working agreement prohibits opening or controlling GUI applications; a permitted browser review would settle this.
    location: >-
      web/src/styles.css
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The observation API accepts images and context, but there is no web app for a site manager to assemble, reorder, and submit them. The `web` directory contains only a placeholder README.

**Approach:** Build the Russian responsive New Analysis surface and a stable run route, using the existing single-image and series contracts. Keep the local image manifest and entered context intact through validation and submission recovery.

## Boundaries & Constraints

**Always:** This story submits `observation_only` with explicit scenario, area, timezone-aware period, and JPEG images. Support one image or 2–8 ordered images; preserve duplicate bytes as separate frames. Validate supported format, decodability, size, and pixel count before submission. Show persistent labels, supported scope, local reversible removal, accessible order announcements, nearby errors, offline state, and full-night responsive styling. Keep one idempotency key and exact request body across an uncertain response until the run identity is recovered; route to `/runs/{run_id}` only after an authoritative ID. Keep native controls, keyboard operation, visible focus, 44px targets, Russian status text, and 320px/200% zoom usability.

**Never:** Claim rule evaluation or site-wide absence, queue offline uploads, silently discard context/images after an error, turn duplicate images into one frame, issue a new idempotency key while an outcome is uncertain, or invent progress/results for the run workspace (Stories 1.6–1.7).

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Single or ordered series | 1 or 2–8 valid JPEGs and context | Correct endpoint and order; navigate only on returned `run_id` | Preserve all form values on failure |
| Reorder and removal | Duplicate files, move/remove/undo | Distinct visible `Кадр N` positions; undo restores prior position | Announce updated position and removal |
| Invalid or unavailable input | Unsupported/undecodable file, denied camera, offline | Retain accepted files and context; explain affected input | No offline upload or unwanted camera re-prompt |
| Uncertain response | Network loss or `submission_in_progress` | Reconcile with the same key/body before enabling a new submit | Stay on form with recovery action and focused error summary |

</intent-contract>

## Code Map

- `web/README.md` -- placeholder only; create the React/Vite entry and document local start.
- `backend/app/main.py:119` -- `POST /runs/single-image`, `POST /runs/series`, `Idempotency-Key`, 202 with `run_id` or `submission_in_progress`; `GET /runs/{run_id}` is the authoritative run route.
- `backend/app/application/submission.py:44` -- JPEG decode and limits (16 MB, 40 million pixels, series 2–8); context strings and timezone-aware ISO period; preserve array order.
- `_bmad-output/planning-artifacts/epics.md:528` -- Story 1.5's outer-surface acceptance and accessibility constraints; read-only.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/DESIGN.md` -- approved colors, type, spacing, and focus tokens; read-only.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:120` -- shell, manifest, submission recovery, and responsive behavior; read-only.
- `_bmad-output/implementation-artifacts/spec-1-4-complete-an-ordered-series-observation-run.md` -- backend order and duplicate-byte continuity; read-only.

## Tasks & Acceptance

**Execution:**
- `web/package.json`, `web/index.html`, `web/vite.config.ts`, `web/tsconfig.json` -- establish the pinned web seed and same-origin API development proxy.
- `web/src/App.tsx`, `web/src/main.tsx` -- build semantic app shell, New Analysis form, ordered image manifest, submission/recovery state, and stable run route.
- `web/src/styles.css` -- apply approved full-night tokens and responsive/accessibility layout.
- `web/src/App.test.tsx` -- exercise the matrix through user-facing controls, including uncertain-response key reuse.
- `web/README.md`, `README.md` -- document web startup, API connection, and supported submission scope.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize Story 1.5 with verified workflow status.

**Acceptance Criteria:**
- Given a laptop or 320px phone viewport, when New Analysis opens, then Russian persistent context labels, JPEG selection, supported scope, product identity, and usable navigation are visible.
- Given accepted images, when the manager moves, removes, or restores one, then `Кадр N` order matches the submitted array and changes are announced without dropping duplicates.
- Given an invalid file, denied camera, or offline device, when the manager continues, then accepted images and context remain and the affected control has a Russian recovery message.
- Given a valid form, when the manager submits, then duplicate activation is prevented, `Создаём анализ…` stays visible, and navigation occurs only after an authoritative `run_id`.
- Given an uncertain response, when the manager retries, then the same request and idempotency key are used until the server returns a run ID or a definitive error; the form remains intact.
- Given keyboard use, 200% zoom, text spacing, or reduced motion, when the form is operated, then focus, labels, reorder controls, and submission remain perceivable and usable.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 23 findings — high 0, medium 16, low 5, false 1, maybe-false 1
- findings:
  - `[medium]` `[patch]` A readiness rejection after an uncertain send could lose the original key — all 5xx responses now retain the exact pending request.
  - `[medium]` `[patch]` Refresh lost the reconciliation handle — pending body and key now recover from session storage or IndexedDB through a session pointer.
  - `[medium]` `[patch]` Submit could outrun file decoding — it now awaits the validation queue before serializing inputs.
  - `[medium]` `[patch]` Overlapping file selections could exceed eight frames — additions use a serialized queue and current frame reference.
  - `[medium]` `[patch]` A late camera stream could survive navigation — generation and mount checks stop orphaned tracks and navigation closes the stream.
  - `[low]` `[patch]` Null camera encoding silently closed capture — it now reports a recoverable error and keeps the camera open.
  - `[low]` `[patch]` Transient camera errors disabled future attempts — only permission denial disables repeat prompts.
  - `[low]` `[patch]` Undo silently did nothing at eight frames — its control is disabled until there is room.
  - `[medium]` `[patch]` A nonexistent daylight saving wall time could be submitted — local datetime round-trip validation rejects it.
  - `[low]` `[patch]` Run GET failure had no action matching its retry instruction — the run route now provides `Проверить снова`.
  - `[medium]` `[patch]` A new run route could show the prior run's state — state clears before each authoritative read.
  - `[medium]` `[patch]` A 404 run route asserted creation — it now shows `Анализ не найден` after server readback.
  - `[medium]` `[patch]` Parallel Base64 conversion could multiply phone memory use — conversion now proceeds one frame at a time through FileReader; the backend's maximum aggregate remains a residual browser-memory risk.
  - `[medium]` `[patch]` File selection and submit races were independently reported — the same serialized validation queue and submit wait address both paths.
  - `[medium]` `[patch]` Malformed JSON on a definitive 4xx left the old request pending — the HTTP status is classified before parsing.
  - `[medium]` `[patch]` Stale run state was independently reported — route read resets it before fetch.
  - `[medium]` `[patch]` Late camera acquisition after unmount was independently reported — returned tracks are stopped when generation or mount no longer matches.
  - `[low]` `[patch]` Null camera capture was independently reported — a nearby error now keeps retry possible.
  - `[false]` `[reject]` `min-width: 320px` was said to break a 320 CSS pixel viewport — its minimum equals the stated viewport width; actual rendered zoom behavior is separately unverified.
  - `[medium]` `[patch]` Equal-byte test fixtures could not prove submitted reorder — distinct and duplicate bytes now assert the exact outgoing array order.
  - `[medium]` `[patch]` Decode and pixel-limit branches lacked effective tests — focused rejection tests now retain an accepted frame.
  - `[medium]` `[patch]` Sprint tracking remained `backlog` — synchronized it to `review` during review and to `done` after verification.
  - `[maybe-false]` `[defer]` Browser layout and touch acceptance are not observed by jsdom — rendered 320 CSS pixel, 200% zoom, text spacing, and touch checks would settle it; GUI use is prohibited by the user's working agreement.

## Design Notes

Use the existing HTTP idempotency contract as the reconciliation mechanism: retain the key and serialized body for an uncertain send, then repeat that exact request. The server returns the existing run ID for an accepted duplicate. Do not create a second logical submission while the first remains uncertain.

## Verification

**Commands:**
- `cd web && npm ci && npm test -- --run && npm run build` -- UI behavior and type/build pass.
- `cd backend && uv run pytest -q` -- existing API contracts still pass.
- `git diff --check` -- patch formatting is clean.

## Auto Run Result

Status: done

Implemented the Russian responsive New Analysis form for one JPEG or an ordered 2–8-frame series, local validation and reversible ordering, camera/file input, offline and submission recovery, and a stable run identity route. The existing observation-only API receives an exact ordered body and idempotency key; an uncertain submission is retried with the same body and key, including after a same-tab refresh.

Files changed: `web/package.json` and `web/package-lock.json` pin the client dependencies; `web/index.html`, `web/vite.config.ts`, `web/tsconfig.json`, and `web/src/vite-env.d.ts` establish the app; `web/src/App.tsx`, `web/src/main.tsx`, and `web/src/styles.css` implement its behavior and full-night shell; `web/src/App.test.tsx` covers user-facing submission and recovery; `web/README.md`, `README.md`, and `.gitignore` document and support local use; `sprint-status.yaml` records completion.

Review: 23 findings across four layers: 16 medium and 5 low patched, 1 false rejected because the CSS minimum equals the specified 320 CSS pixel viewport, and 1 maybe-false layout concern deferred pending a permitted rendered-browser check. The patched medium findings include concurrent selection, uncertain-response identity, source order, route state, and validation tests. Follow-up review recommended: true, because actual rendered 320 CSS pixel/200% zoom behavior and large-request IndexedDB recovery remain unverified. No GUI was opened under the user's working agreement.

Verification: `npm ci`, `npm test -- --run` (11 passed), and `npm run build` passed. The full backend suite passed `43 passed in 60.75s` against the isolated test PostgreSQL/MinIO configuration. `git diff --check` and YAML frontmatter parsing passed. React 19.3.0 and Vite 8.3.0 from the architecture document returned npm 404, so available pinned React 19.1.1 and Vite 8.2.2 were used; TypeScript 6.0.3 and Radix Themes 3.3.0 are pinned. No deployed browser or visual interaction was verified.

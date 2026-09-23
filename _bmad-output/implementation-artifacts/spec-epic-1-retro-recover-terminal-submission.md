---
title: 'Recover from terminal submission failure'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '94fca60067d582844ba70cd60147029622d7daea'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The API returns HTTP 503 with `submission_publication_failed` or `submission_interrupted` for a permanently failed idempotency key. The web app treats every 503 as uncertain, retains that key, and locks the form indefinitely.

**Approach:** Recognize only those authoritative terminal codes in the response body. Release the saved request and allow an explicit new submission with a new key; keep the exact body and key for network errors, undecodable responses, `submission_in_progress`, and other 503 responses.

## Boundaries & Constraints

**Always:** Preserve current form inputs and selected files after a terminal response in the current page. Explain that a fresh submission is required and make it a user action. Clear durable pending state before unlocking editing. Keep the accepted-run path unchanged. Preserve F1/F2 changes and retrospective evidence.

**Never:** Automatically resubmit, reuse the terminal key for new work, infer a terminal result from HTTP 503 alone, alter server idempotency records, close other retrospective action items, or use a GUI.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Terminal failure | HTTP 503 and `submission_publication_failed` or `submission_interrupted` | Saved request is cleared; form is editable; next explicit submit creates a different key | Display the terminal failure and fresh submission action |
| Uncertain response | Network failure, unreadable body, `service_not_ready`, or `submission_in_progress` | Exact body and key remain available across retry and reload | Explain same-key retry |
| Accepted response | HTTP 202 with valid run ID | Saved request clears and app navigates to run | No error expected |

</intent-contract>

## Code Map

- `backend/app/main.py:148` -- maps the two terminal submission codes to HTTP 503; generic readiness and unavailable responses also use 503, so status alone is insufficient.
- `backend/app/application/submission.py:82` -- failed submission state returns the stored code under the same key; a fresh key is required.
- `web/src/App.tsx:156` -- `storePending`, `recoverPending`, and `clearPending` persist the exact body/key in sessionStorage or IndexedDB.
- `web/src/App.tsx:506` -- `send` handles definitive 4xx, accepted 202, and uncertain responses. Terminal code handling belongs here before generic uncertainty.
- `web/src/App.tsx:548` -- `submit` creates a new UUID only when there is no pending request; form controls are disabled while pending.
- `web/src/App.test.tsx:229` -- existing uncertain-response and legacy route retry tests provide adjacent coverage. F1 and F2 dirty work is already present and must remain intact.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md:27` -- source finding and action-item contract; read-only evidence.

## Tasks & Acceptance

**Execution:**
- `web/src/App.tsx` -- branch on the two terminal response codes, clear durable pending state and in-memory pending request, then show a fresh-submission message without sending automatically.
- `web/src/App.test.tsx` -- verify terminal codes unlock the form and a user-driven submit uses a new key; verify uncertain responses retain exact body/key and reload behavior.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark only F3 `in-progress` at start and `done` after passing checks.

**Acceptance Criteria:**
- Given a pending single or series request with a terminal server code, when its response arrives, then a user can edit the form and explicitly submit with a new idempotency key.
- Given an uncertain response, when the user retries or reloads, then the same serialized body and idempotency key are used.
- Given a successful submission, when the accepted run ID arrives, then the app navigates to that run and clears the saved request.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 13 findings — high 0, medium 7, low 2, false 4, maybe-false 0
- findings:
  - `[medium]` `[defer]` Startup reconciliation can interrupt another instance's live publisher — verified pre-existing multi-instance limitation, recorded in the F1 spec; F3 does not change startup.
  - `[medium]` `[defer]` A dead publisher can stay pending until startup — verified pre-existing lack of publisher ownership, recorded in the F1 spec.
  - `[medium]` `[defer]` Runless object inspection waits for startup — verified consequence of F1 runtime scoping, recorded in the F1 spec.
  - `[medium]` `[defer]` Unrelated run-bound intent can fail the runtime reconciliation pass — verified pre-existing scan scope, recorded in the F1 spec.
  - `[low]` `[defer]` Failed IndexedDB deletion leaves an unreachable old body — verified in `clearPending`; F7 remains open for durable storage cleanup coverage.
  - `[medium]` `[defer]` Terminal-response tests do not exercise IndexedDB quota fallback — verified missing branch, already tracked by F7.
  - `[false]` `[reject]` F3 status is `done` while this spec is `in-review` — review was in progress when the diff was captured; this final result now records verification and closes the spec.
  - `[false]` `[reject]` F4 and F5 are open — deliberately separate action items; neither was closed by this run.
  - `[false]` `[reject]` Rendered UI evidence is absent — F6 explicitly remains open and GUI use is prohibited for this run.
  - `[false]` `[reject]` F8 and F9 remain open — separately tracked deferred items, outside the requested F1/F3 implementation.
  - `[low]` `[defer]` Failed IndexedDB deletion still clears its pointer — same storage cleanup limitation as above; the submission itself is already terminal.
  - `[medium]` `[defer]` F2 route split lacks a repeatable server HTTP check — verified prior F2 scope; its spec records a one-off CLI HTTP check, while this run changed only F3.
  - `[medium]` `[defer]` F2 artifact fetch tests do not assert the exact URL — verified prior F2 test gap; no artifact URL change was made in F3.

Intent alignment: the request permits F1 as the first step toward F3. F1/F2 were already present when this run began; this run added F3. F1 has live database/artifact concurrency coverage and F3 has component coverage; no GUI or production end-to-end claim is made.

## Verification

**Commands:**
- `npm test -- --run` in `web` -- all component tests pass.
- `npm run build` in `web` -- TypeScript and production build pass.
- `git diff --check` -- no whitespace errors.

## Auto Run Result

Status: done.

F3 recognizes only the two authoritative terminal submission codes in an HTTP 503, clears the saved request, preserves the current form, and waits for an explicit new submission with a fresh key. Uncertain responses still retain the exact body and key. The F1 race fix and F2 route split were present at the start and remain intact. Only F3 was advanced in sprint tracking during this run; F1/F2 were already `done`, and F4–F9 remain `open`.

Changed for F3: `web/src/App.tsx` handles terminal responses and waits for durable pending cleanup; `web/src/App.test.tsx` covers single and series terminal recovery, uncertain reload/retry, and accepted cleanup; `sprint-status.yaml` records F3 completion.

Review: no F3 code patch was required. Independent reviewers reported pre-existing F1/F2 limitations and the separately tracked F7 storage cleanup gap. Follow-up review recommended: false; patched high 0, patched medium 0.

Verification: `npm test -- --run` — 26 passed; `npm run build` — passed; `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 71 passed against local PostgreSQL/MinIO with the F1 concurrency cases; `git diff --check` — passed. The first backend attempt was sandbox-denied at localhost, then the authorized local-network run passed. GUI, deployment, and production runtime were not exercised. Existing uncommitted work and retrospective evidence were preserved; no commit or push was made.

---
title: 'Bound a stalled submission request'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: 'be4f6b4890aca335ba9e5a7c10763a71b67eaca3'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** A submit fetch that never settles keeps the form in `sending` forever, preventing a same-key retry.

**Approach:** Bound the request wait, abort the outstanding fetch on timeout, and return to the existing uncertain-result state with the exact durable request and key available for an explicit retry.

## Boundaries & Constraints

**Always:** Preserve the exact persisted body, endpoint, and idempotency key after timeout. Release `sending` even when a transport ignores abort. Keep definitive response handling and late-response safety. Update only F9's sprint action item to `done` after checks pass.

**Never:** Automatically retry, generate a new key on uncertainty, clear the durable request on timeout, modify completed F1, change other action items, or use a GUI.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stalled first send | Persisted single or series request; fetch never settles | Deadline aborts fetch, enables retry and retains saved request/key | Explain uncertain outcome |
| Stalled retry | Same request resent; fetch never settles | Same deadline applies and retry remains available | Retain same body/key |
| Late transport result | Timed-out fetch resolves after the UI unlocks | Late result cannot clear pending request or navigate | Explicit retry remains authoritative |
| Definitive response | HTTP 202 with run ID or terminal rejection before deadline | Existing navigation or cleanup behavior | Clear timer |

</intent-contract>

## Code Map

- `web/src/App.tsx:516` — `send` is the sole POST path for both first send and retries. It persists before sending through `submit` and uses `busy`/`sending` to lock the form. `:330` has a 10-second read poll timeout pattern.
- `web/src/App.tsx:133-192` — `storePending`, `loadPending`, and `clearPending` retain the exact request across reloads; timeout must leave this storage intact.
- `web/src/App.test.tsx:276-306,375-455` — submission tests cover uncertain and terminal responses with exact body/key assertions; add a transport that never resolves and a late result.
- `backend/tests/test_single_image.py:49` and `spec-epic-1-retro-protect-live-submissions.md` — completed F1 concurrent recovery regression and verification; read-only continuity evidence.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — F1 already `done`; F9 is set `in-progress` at start.

## Tasks & Acceptance

**Execution:**
- `web/src/App.tsx` — apply a finite deadline to every submission POST and release the UI on timeout while preserving the pending request.
- `web/src/App.test.tsx` — exercise never-settling and late-settling transports, verify retry uses the exact saved body/key, and verify definitive response behavior remains intact.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — mark only F9 `done` after relevant checks pass.

**Acceptance Criteria:**
- Given a saved request and a submit transport that does not settle, when its deadline expires, then the form offers an explicit same-key retry and the exact request remains durable.
- Given a timed-out request, when its transport later resolves, then it does not navigate or erase the saved request.
- Given a retry after timeout, when the server responds definitively, then existing success or terminal handling applies to the same body and key.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 8 findings — high 0, medium 4, low 2, false 2, maybe-false 0
- findings:
  - `[medium]` `[patch]` A stalled response body could keep the form busy — extended the same deadline through `response.json()` and added a stalled-body retry test.
  - `[low]` `[reject]` No timeout-specific reload assertion — `loadPending` is unchanged; the existing uncertain-response reload test exercises the same saved request path.
  - `[low]` `[reject]` No timeout-specific IndexedDB assertion — persistence precedes `send`, and the existing quota-backed reload test covers that storage branch.
  - `[false]` `[reject]` The spec lists expected rather than observed checks — observed results are recorded under Auto Run Result at finalization.
  - `[medium]` `[patch]` Headers without a completed body defeat the deadline — same fix and test as the first finding.
  - `[medium]` `[patch]` The finite-deadline claim excluded body parsing — same fix and test as the first finding.
  - `[medium]` `[patch]` Tests did not stall a response body — added a stalled 202 body with late completion and same-key retry assertions.
  - `[false]` `[reject]` The diff lacks F1 backend work — F1 was already done at the baseline and its concurrent regression passed again in the 73-test backend suite; F9 was the remaining open item.

## Verification

**Commands:**
- `npm test -- --run` (from `web`) — expected: submission regressions and existing component tests pass.
- `npm run build` (from `web`) — expected: TypeScript and Vite build pass.
- `git diff --check` — expected: no whitespace errors.

## Auto Run Result

Status: done.

The submission POST now has a 10-second deadline through response-body parsing. On timeout, the fetch is aborted, the form offers an explicit retry, and the persisted endpoint, body, and idempotency key remain intact. A late response cannot navigate or clear them. F1 stayed done; only F9 changed from open through in-progress to done.

Changed files: `web/src/App.tsx` bounds the send; `web/src/App.test.tsx` covers stalled single and series sends, stalled response bodies, late replies, and exact-key retries; `sprint-status.yaml` records F9 completion; this spec records the work and review.

Review: one medium root cause was patched (four findings about response-body stalls); two low test expansions were rejected because existing storage tests cover the unchanged paths; two findings were refuted by the final result record and pre-existing F1 implementation. Patched medium entries: 1. Follow-up review recommended: false.

Verification on 2026-09-23: `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 73 passed, including F1 concurrent upload/recovery; `web: npm test -- --run` — 31 passed; `web: npm run build` — passed; `git diff --check` — passed. No GUI or deployment verification was performed.

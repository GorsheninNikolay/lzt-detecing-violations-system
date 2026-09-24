---
title: 'Verify IndexedDB submission recovery'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '19192c0042d76bf11046f0a4666d8ed7a6ffa711'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      Failed IndexedDB deletion can leave an inaccessible saved request.
    evidence: |-
      clearPending swallows a failed delete and then removes the session pointer. This pre-existing failure path was not exercised by the successful definitive-response cleanup check.
    location: >-
      web/src/App.tsx:178
    severity: medium
  - summary: >-
      IndexedDB read failure can unlock a form with an uncertain prior send.
    evidence: |-
      recoverPending rejects, but the mount effect finishes recovery with pending unset. A new submission can then use a fresh key while the earlier request remains unresolved.
    location: >-
      web/src/App.tsx:304
    severity: medium
  - summary: >-
      A missing IndexedDB record leaves a stale session pointer.
    evidence: |-
      recoverPending returns null for a missing record without clearing its pointer; the next submission can replace that pointer.
    location: >-
      web/src/App.tsx:163
    severity: medium
---

<intent-contract>

## Intent

**Problem:** The F7 retrospective found no regression assertion for the IndexedDB recovery path after a large request exceeds sessionStorage quota. An uncertain submission must retain its exact body and idempotency key through a same-tab reload, and a definitive response must remove that durable request.

**Approach:** Force the quota failure at the storage boundary in a component test, exercise IndexedDB persistence and reload, then verify retry identity and definitive cleanup. Repair any demonstrated failure in that path.

## Boundaries & Constraints

**Always:** Preserve F1 behavior and the retrospective evidence. Set only F7's sprint item to `done` after checks pass. Keep same-key retry for uncertain outcomes and fresh-key behavior after a definitive terminal response.

**Never:** Use a GUI, alter unrelated action items, or claim rendered-browser acceptance from a jsdom test.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Quota fallback | Full request cannot fit in sessionStorage; small pointer fits | IndexedDB stores exact body/key under the pointer before POST | No POST if persistence fails |
| Same-tab reload | POST outcome uncertain and component remounts | Retry uses same endpoint, body and key | Pending form stays locked until definitive outcome |
| Definitive response | Retried POST accepts a run or returns terminal rejection | IndexedDB request and session pointer are removed | New submission can use a fresh key |

</intent-contract>

## Code Map

- `web/src/App.tsx:136-195` -- `storePending`, `recoverPending`, and `clearPending` own sessionStorage/IndexedDB fallback and deletion. `send` at 515-549 handles uncertain and definitive responses; `submit` at 552-581 persists before POST.
- `web/src/App.test.tsx:229-254,299-325` -- existing tests prove only small sessionStorage recovery. Add an IndexedDB-backed regression using quota failure and remount here.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md` -- read-only F7 finding and evidence.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- F7 action item only; now `in-progress`.

## Tasks & Acceptance

**Execution:**
- `web/src/App.test.tsx` -- add quota-triggered IndexedDB persistence/reload/retry/cleanup and persistence-failure checks with an asynchronous storage double -- prove the durable branch and fail-closed send.
- `web/src/App.tsx` -- repair only behavior the regression exposes -- preserve correct identity and cleanup.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- set F7 to `done` only after verification passes.

**Acceptance Criteria:**
- Given quota failure for the full request and IndexedDB availability, when an uncertain submission is reloaded and retried, then the POST endpoint, exact body, and idempotency key match the first attempt.
- Given that stored request and a definitive response, when cleanup completes, then the pointer and IndexedDB record are absent and a new explicit submission can use a fresh key.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 7 findings — high 0, medium 5, low 0, false 2, maybe-false 0
- findings:
  - `[false]` `[reject]` F7 was done while its spec was in review — the spec remained in review during checks and is now done after the passing readback.
  - `[medium]` `[patch]` Accepted-run cleanup lacked coverage — added a valid 202 run response and asserted deletion of its exact record and pointer.
  - `[medium]` `[defer]` A failed IndexedDB delete strands a saved record — the existing catch clears its pointer; abnormal cleanup failure needs a separate recovery contract.
  - `[medium]` `[defer]` Failed IndexedDB read unlocks a fresh submission — the mount effect finishes recovery after its catch; safe handling of inaccessible stored state needs a separate recovery contract.
  - `[medium]` `[defer]` A missing record leaves a stale pointer — the existing read returns null without clearing that pointer; handling partial storage loss needs a separate recovery contract.
  - `[medium]` `[patch]` The IndexedDB double skipped first-open object-store creation — it now invokes upgrade and rejects transactions against missing stores.
  - `[false]` `[reject]` F1 was absent from this diff — F1 was already done at the baseline and its existing concurrent coverage passed in the backend suite during this run.

## Verification

**Commands:**
- `npm test -- --run` in `web` -- expected: all component tests pass, including the new quota path.
- `npm run build` in `web` -- expected: TypeScript and Vite build pass.
- `git diff --check` -- expected: no whitespace errors.

## Auto Run Result

Status: done.

Added quota-triggered IndexedDB component checks for persistence before POST, exact same-key/body recovery after remount, cleanup after rejection and accepted run, and fail-closed behavior when persistence fails. No production code change was required. `web/src/App.test.tsx` contains the checks; `sprint-status.yaml` marks only F7 done.

Review: two medium test gaps patched; three pre-existing storage-failure paths deferred; two findings rejected with reasons above. Follow-up review is recommended for the patched first-open and accepted-run checks until a permitted real-browser run validates IndexedDB semantics.

Verification on 2026-09-23: web `npm test -- --run` — 28 passed; `npm run build` — passed; `git diff --check` — passed. Existing F1 concurrent backend behavior was also rechecked by `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 71 passed in 64.42s with local PostgreSQL and MinIO. No GUI was used. Browser IndexedDB behavior remains unverified.

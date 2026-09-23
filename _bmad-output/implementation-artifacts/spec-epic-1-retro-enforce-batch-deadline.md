---
title: 'Enforce the admitted batch deadline for ordered series'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '52d07c86a725984c1576f7b4d5537fecdabc9edf'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** Admission records a batch timeout, but ordered-series execution ignores it. A series can spend the full per-image allowance on every frame, exceeding the snapshotted batch budget.

**Approach:** Start one monotonic deadline when a series begins execution, use the smaller of the per-image allowance and remaining batch budget for each provider invocation, and fail the run when the shared budget is exhausted.

## Boundaries & Constraints

**Always:** Preserve F1's runtime reconciliation and concurrent submission checks, retrospective evidence, per-image timeout, ordered frame persistence, and existing lease/error handling. Mark only F8 `done` after relevant checks pass.

**Never:** Reset the batch budget per frame, change admission formulas or other action items, use a GUI, or claim wall-clock provider/production evidence from mocked tests.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Series within budget | Two assessable frames complete within the shared bound | Both observations persist and the run succeeds | No error |
| Remaining budget | First frame consumes most of the bound | Second provider receives only the remaining allowance | Timeout is recorded as `observer_timeout` |
| Budget exhausted in preflight or publication | Work reaches a deadline before another frame can complete | Run fails without a false success | Persist `observer_timeout` |

</intent-contract>

## Code Map

- `backend/app/adapters/postgres.py:397-407,614-740` -- Admission snapshots both limits; final completion must reject an expired batch before transaction commit.
- `backend/app/application/executor.py:129-177` -- `ClaimLoop._execute` preflights every frame, then reserves, invokes `_observe_bounded`, publishes evidence, and records completion. `_observe_bounded` already accepts a timeout and reports `observer_timeout`.
- `backend/tests/test_ordered_series.py:226-500` -- PostgreSQL/S3 series integration test and mocked observer provide a place to assert the remaining timeout and terminal persisted state.
- `backend/tests/test_single_image.py:49-160` -- Existing F1 concurrent single/series upload regression; retain it and rerun focused checks.
- `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:167-172` -- AD-30 is the read-only source of the admitted timeout contract.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md` -- Read-only F8 finding and F1 historical evidence.

## Tasks & Acceptance

**Execution:**
- `backend/app/application/executor.py` -- Enforce one monotonic series budget through preflight, invocations, and final completion while preserving the per-image bound and terminal failure behavior.
- `backend/tests/test_ordered_series.py` -- Verify a shrinking provider allowance and exhausted-budget persisted failure with a controlled monotonic clock.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- Keep F8 `in-progress` during work and change it to `done` only after checks pass.

**Acceptance Criteria:**
- Given an admitted series with a batch limit, when the second frame begins after the first uses part of that limit, then its provider allowance is the remaining batch time capped by the per-image limit.
- Given the batch budget expires before series completion, when execution reaches its next boundary, then the run records `observer_timeout` and does not report success.
- Given a concurrent submission during runtime recovery, when focused F1 regression checks run, then the live publisher still commits with the same key.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 9 findings — high 0, medium 7, low 1, false 1, maybe-false 0
- findings:
  - `[medium]` `[patch]` Final completion could commit success after the deadline — added a monotonic check inside `finish_ordinary` before transaction commit.
  - `[medium]` `[patch]` Preflight and publication waits could outlast the shared budget — each awaited series operation now uses the remaining budget; final completion checks before commit.
  - `[medium]` `[patch]` No preflight-expiry regression — added a controlled-clock preflight case that verifies terminal `observer_timeout` and no observations.
  - `[low]` `[patch]` The test did not prove the snapshotted limit survives caller mutation — it now changes the caller snapshot after submission and checks the stored allowance.
  - `[medium]` `[patch]` Final completion could succeed after expiry, independently reported by the edge-case reviewer — the database completion check rolls back the transaction.
  - `[medium]` `[patch]` The claim of enforcement through completion needed a final transaction check — the same rollback guard covers it.
  - `[medium]` `[patch]` Preflight expiry lacked an assertion, independently reported by the verification-gap reviewer — added the preflight case.
  - `[medium]` `[patch]` Final completion could commit after expiry, independently reported as another verification gap — the final transaction now checks the deadline before commit and its rollback is tested.
  - `[false]` `[reject]` F1 was allegedly omitted from this diff — F1 was already completed at baseline, its concurrent single/series regression remains in the full passing backend suite, and only F8 needed new code.

## Verification

**Commands:**
- `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` -- expected: backend suite, including F1/F8 integration checks, passes against isolated local PostgreSQL/S3 fixtures.
- `git diff --check` -- expected: no whitespace errors.

## Auto Run Result

Status: done.

The series now uses one monotonic batch deadline from its persisted profile snapshot. Provider calls use the smaller per-image or remaining batch allowance; preflight, reservation, and publication waits are bounded by the same deadline. Final database completion rolls back if the deadline has expired before commit, recording `observer_timeout` rather than success.

Changed files: `backend/app/application/executor.py` enforces the shared budget; `backend/app/adapters/postgres.py` guards final completion; `backend/tests/test_ordered_series.py` covers shrinking allowance, preflight/provider/publication/final-completion expiry, and snapshot immutability; `sprint-status.yaml` records F8 completion. F1 code/tests and retrospective evidence were preserved.

Review: four root issues patched (three medium, one low); one F1 omission claim rejected because it was already fixed at baseline. Follow-up review is recommended because several medium findings required patches. The unverified risk is a worker thread that remains blocked after its async wait times out; cancellation does not terminate the underlying synchronous call.

Verification: `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 71 passed in 65.66s against isolated local PostgreSQL/MinIO; `git diff --check` passed. No GUI, deployment, or production execution was performed.

---
title: 'Recover Interrupted Runs and Artifact Publication'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '7800047b60fe47a21a1dc3b3c4006d10ef75bf46'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Process-level restart during an in-flight observer call has not been exercised.
    evidence: |-
      PostgreSQL lease races and startup gates passed against local PostgreSQL/S3, but a killed-process test would establish the complete restart behavior and observed UI state.
    location: >-
      backend/app/main.py:45
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Restart handling currently rejects pending publication intents without inspecting S3 and can strand the service before readiness. Recovery must also ensure an uncertain observer call cannot be resumed or committed by a former owner.

**Approach:** Reconcile intent metadata against verified existing objects under the PostgreSQL advisory lock, quarantine unverifiable or stranded work, and fence expired-run terminalization in one transaction before enabling claims.

## Boundaries & Constraints

**Always:** Preserve queued runs and unexpired leases. Record each reconciliation pass, including failures, and use digest, size, final key, and creator metadata where applicable to prove object identity. Allow a later intent to reference existing content-addressed bytes only after verification; preserve the original object's creator attribution. Quarantine stranded `content_verified` intents without promoting them. Retain run, invocation, stage, and artifact evidence when an expired lease becomes `failed` with `executor_interrupted`; skip downstream stages. Keep readiness false and claims disabled if any gate cannot complete.

**Never:** Repeat or resume a reserved provider call; change terminal run state; overwrite, delete, move, replace, or retag evidence bytes during reconciliation; infer a missing digest from an S3 key; treat an S3 outage as proven corruption; store credentials or signed URLs in durable evidence.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Incomplete upload | `pending_upload`, temporary object possibly present | Retain bytes, quarantine intent metadata after owner interruption | S3 inspection outage fails the gate and records a failed pass |
| Interrupted promotion | `content_verified`, final object possibly present | Verify recorded content identity; quarantine stranded intent, preserving bytes | Mismatch is recorded as integrity failure, no attachment |
| Published but unreferenced | `object_published`, matching final object | Verify and attach only through existing run/submission reference contract; otherwise quarantine | Missing or mismatched bytes cannot become referenced |
| Duplicate content | Later intent and existing `sha256/<digest>` from another creator | Verify digest and size before reference; keep original creator metadata | Mismatch quarantines or fails integrity without mutation |
| Recovery | queued, live lease, expired lease, or owner race | Preserve first two; fail expired run atomically and fence old writes | Lock or ownership uncertainty fails the gate |

</intent-contract>

## Code Map

- `backend/app/adapters/postgres.py:62-115` -- current advisory-lock reconciliation records pass counts but fails on any live pending intent; recovery selects expired running rows yet its update does not compare the selected owner token. Reuse transaction and gate-error patterns; coordinate S3 checks without silently committing a partial pass.
- `backend/app/adapters/postgres.py:209-267,398-480,485-674` -- publication transitions, submission reference transaction, ordinary claim/reservation/completion, and owner-fenced writes. Run-bound native intents and submission intents without `run_id` need distinct attachment decisions.
- `backend/app/adapters/artifacts.py:19-87` -- verified temporary and final reads, immutable conditional final publication, and S3 error classification. Add a read-only reconciliation inspection operation; do not reuse the health probe's cleanup path.
- `backend/app/main.py:45-83` -- startup gates currently run recovery before reconciliation; align them with architecture AD-9 order and pass the artifact inspector into reconciliation before readiness and claim-loop start.
- `backend/app/application/executor.py:176-190` -- idle loop invokes recovery; preserve behavior that cannot re-claim failed runs.
- `backend/tests/test_startup.py:90-188,300-381` -- PostgreSQL/S3 integration fixtures and gate assertions; replace the old blanket-pending failure expectation with deterministic interrupted-state, repeat-pass, competing-owner, and readiness cases.
- `backend/tests/test_single_image.py:235-248,340-432` -- existing interrupted submission and lease race tests; preserve their reference and fencing contracts.
- `backend/migrations/versions/0002_admission.py:80-89` -- `artifact_metadata.run_id` is non-null; do not create orphan metadata for a submission intent with no accepted run.
- `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:81,117,165` -- read-only authority for gate order, evidence-preserving recovery, and metadata-only reconciliation.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize verified Story 1.8 status.

## Tasks & Acceptance

**Execution:**
- `backend/app/adapters/artifacts.py` -- expose read-only verification of temporary/final keys and creator metadata with distinct missing-object, mismatch, and unavailable outcomes.
- `backend/app/adapters/postgres.py` -- reconcile interrupted intent/submission states under the existing advisory lock, record every pass, attach only verified published content through valid reference ownership, and quarantine stranded metadata without changing S3 bytes.
- `backend/app/adapters/postgres.py` -- strengthen expired-run recovery with selected owner/token and expected-state checks in one transaction while preserving prior invocation/artifact rows and skipping dependent stages.
- `backend/app/main.py` -- run the artifact reconciliation gate before guarded recovery, and enable readiness/claims only after both complete.
- `backend/tests/test_startup.py`, `backend/tests/test_single_image.py` -- test the matrix against isolated PostgreSQL and S3, including repeated passes, creator-preserving deduplication, owner races, and failed readiness.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- reflect only the verified workflow state.

**Acceptance Criteria:**
- Given interrupted publication metadata and existing S3 bytes, when startup reconciliation runs, then each state receives an evidence-backed metadata disposition, repeated passes are idempotent, and no evidence object is mutated.
- Given a matching final object first created by a different intent, when a valid published intent is referenced, then digest and size are verified and original creator metadata is retained.
- Given queued work or a live running lease, when recovery executes, then queued work stays claimable and the running owner remains unchanged; a mismatched owner cannot write or terminalize the live run.
- Given an expired running lease, when guarded recovery commits, then one fenced transaction fails the run with `executor_interrupted`, skips dependent stages, retains invocation and artifact evidence, and rejects subsequent former-owner completion.
- Given reconciliation, object verification, or recovery cannot complete, when startup checks readiness, then `/health/ready` stays false and the executor has not claimed work.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 15 findings — high 0, medium 10, low 0, false 4, maybe-false 1
- findings:
  - `[medium]` `[patch]` A second pass could clear a prior integrity gate failure — reconciliation now records and returns a failed pass while any `failed_integrity` intent remains.
  - `[false]` `[reject]` A second live service instance could have a publishing submission — this MVP runs one application instance, and its current reconciliation entrypoint is startup after the prior process has stopped; no concurrent operator entrypoint exists.
  - `[false]` `[reject]` A queued admission run could be publishing — admission reserves the invocation and changes the run to `running` before `_publish` creates an intent.
  - `[medium]` `[patch]` A lease could expire between reconciliation and recovery — startup now runs a second reconciliation pass after recovery before readiness.
  - `[false]` `[reject]` A missing temporary object under `content_verified` was not treated as a gate failure — the prescribed disposition of a stranded `content_verified` intent is quarantine without promotion or attachment; no referenced evidence is accepted from it.
  - `[medium]` `[patch]` Any UUID in final creator metadata passed — reconciliation now checks that the creator intent exists with the exact digest, size, and final key.
  - `[medium]` `[patch]` Inspecting whole objects in memory could exhaust memory — reconciliation now hashes in bounded chunks while closing the response body.
  - `[medium]` `[patch]` Edge review found the same lease-expiry window — the second reconciliation pass settles intents after recovery.
  - `[medium]` `[patch]` S3 `404` and `NotFound` were treated as outages — a read-only bucket check now separates missing objects from bucket or service failure.
  - `[medium]` `[patch]` A corrupt final object at `content_verified` lacked a direct assertion — an integration case now checks integrity failure and the readiness gate.
  - `[medium]` `[patch]` Wrong temporary-object creator metadata lacked a direct assertion — an integration case now checks `failed_integrity` and the readiness gate.
  - `[medium]` `[patch]` Verification review independently found the repeat-pass integrity gap — a startup gate assertion now verifies the failure stays sticky.
  - `[medium]` `[patch]` Sprint tracking still said `backlog` — Story 1.8 is synchronized to `review` during verification and to `done` on finalization.
  - `[false]` `[reject]` Former-owner completion after expiry was untested — `test_expired_lease_fences_completion_during_recovery` exercises concurrent completion, expired ownership, rejection, and retained rows.
  - `[maybe-false]` `[defer]` A process-level restart with an in-flight provider call was not exercised — the PostgreSQL concurrency and startup contracts passed, but a killed-process test would establish the full restart behavior.

## Design Notes

`content_verified` records a verified temporary upload and intended final key, not proof that a final object was safely published. Reconciliation must quarantine this stranded state even if matching bytes happen to exist at the final key. `object_published` only proves final publication; referencing still requires the owning run or submission transaction to be valid.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_startup.py tests/test_single_image.py` -- PostgreSQL/S3 recovery and publication contracts pass.
- `cd backend && uv run pytest` -- complete backend suite passes.
- `git diff --check` -- patch whitespace clean.

## Auto Run Result

Status: done

Restart reconciliation now inspects existing S3 objects without mutating evidence bytes, verifies digest, size, and creator attribution, quarantines stranded publication metadata, and keeps a prior integrity failure blocking readiness on later passes. Startup reconciles before and after guarded expired-lease recovery, then enables claims only after all gates succeed. Recovery compares the selected owner and lease expiry before terminalizing an expired run.

Files changed: `backend/app/adapters/artifacts.py` adds bounded read-only object inspection; `backend/app/adapters/postgres.py` reconciles intent states and fences recovery; `backend/app/main.py` orders startup gates; `backend/tests/test_startup.py`, `backend/tests/test_single_image.py`, and `backend/tests/test_ordered_series.py` cover the contracts; `sprint-status.yaml` records Story 1.8 as done.

Review: one pass triaged 15 findings: 10 medium patches, 4 false findings rejected with reasons in the triage log, and one unverified process-level restart scenario deferred. Follow-up review recommended: true because multiple medium corrections were made; a real killed-process restart with an in-flight provider call is the specific remaining risk.

Verification: focused PostgreSQL/S3 tests passed 37/37; the complete backend suite passed 56/56 against isolated local PostgreSQL and MinIO; `git diff --check` passed. A process-level restart and rendered browser behavior were not run.

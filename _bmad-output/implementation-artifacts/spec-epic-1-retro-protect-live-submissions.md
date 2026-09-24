---
title: 'Protect live submissions during runtime reconciliation'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: '94fca60067d582844ba70cd60147029622d7daea'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      A publisher that dies while the service remains up can leave a publishing request pending until startup reconciliation.
    evidence: |-
      Runtime reconciliation preserves every pre-run submission because the schema has no durable publisher ownership or expiry. The pre-existing recovery limitation needs an owner or expiry design to distinguish abandoned work.
    location: >-
      backend/app/adapters/postgres.py:77
    severity: medium
  - summary: >-
      Startup reconciliation in another instance can interrupt a live publisher.
    evidence: |-
      Startup still applies full pre-run cleanup while a separate ready instance may be uploading. This multi-instance startup overlap predates F1 and was not exercised by the runtime regression.
    location: >-
      backend/app/main.py:51
    severity: medium
  - summary: >-
      An abandoned pre-run publication object receives no runtime integrity inspection.
    evidence: |-
      Runtime mode excludes runless intents until startup; the existing startup path inspects them. A durable owner or expiry signal would allow safe runtime reconciliation of abandoned submissions.
    location: >-
      backend/app/adapters/postgres.py:77
    severity: medium
  - summary: >-
      Runtime reconciliation can encounter unrelated unresolved run-bound intents.
    evidence: |-
      The existing pass scans all unresolved run-bound intents, not only IDs returned by recovery. An unrelated artifact outage can still fail that pass and stop the claim loop; the F1 filter leaves this pre-existing scope unchanged.
    location: >-
      backend/app/adapters/postgres.py:77
    severity: medium
---

<intent-contract>

## Intent

**Problem:** The runtime claim loop calls reconciliation after recovering an expired run. Reconciliation quarantines pre-run publication intents and fails every `publishing` submission, including a healthy upload in another request.

**Approach:** Scope runtime reconciliation to recovered-run work and preserve active pre-run submissions. Keep startup reconciliation's interrupted-submission cleanup, and verify a real concurrent upload/recovery interleaving against PostgreSQL and artifact storage.

## Boundaries & Constraints

**Always:** Keep existing retrospective files and evidence intact. Set only F1's sprint action item to `done` after passing verification. Preserve idempotency and the publisher's ability to commit after recovery; retain reconciliation of orphaned expired-run intents and its integrity gate.

**Never:** Automatically close other action items, change frontend behavior, or use a GUI. Do not weaken startup cleanup or claim that pending submissions from dead publishers are recovered at runtime without evidence.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Live single upload | A submission is paused after creating its intent; an expired run triggers runtime recovery and reconciliation | The publisher can finish and the same key resolves to its accepted run; its intent is referenced | No `submission_interrupted` |
| Live series upload | A series is paused after creating a later intent while runtime recovery runs | Every frame remains publishable and the series reaches one accepted run | No quarantined live intent |
| Orphaned run | Expired leased run has an unresolved publication intent | Runtime recovery fences the run and reconciles its intent | Existing integrity failures still gate reconciliation |
| Interrupted startup submission | No live publisher owns a pre-run intent at startup | Startup reconciliation still quarantines it and records `submission_interrupted` | Same-key retry reports terminal failure |

</intent-contract>

## Code Map

- `backend/app/application/executor.py` -- `ClaimLoop._run` invokes recovery and reconciliation both while ready and after ordinary execution; runtime call sites must select the safe scope.
- `backend/app/adapters/postgres.py` -- `PostgresStore.reconcile` currently locks all nonterminal intents and fails all `publishing` requests; `begin_submission`, `create_submission_intent`, and `commit_series_submission` connect pre-run intent ownership to a submission key.
- `backend/app/application/submission.py` -- single and series publishers update intent states outside one transaction and finalize through `commit_submission` or `commit_series_submission`.
- `backend/app/main.py` -- startup runs reconciliation before enabling readiness; retain its full interrupted-submission cleanup.
- `backend/tests/test_startup.py`, `backend/tests/test_single_image.py`, `backend/tests/test_ordered_series.py` -- integration fixtures and existing reconciliation/submission contracts. Retrospective F1 and its retained reproduction are read-only evidence.

## Tasks & Acceptance

**Execution:**
- `backend/app/adapters/postgres.py` -- allow runtime reconciliation to exclude live pre-run submissions while retaining expired-run intent processing and startup cleanup.
- `backend/app/application/executor.py` -- select runtime-safe reconciliation at both ready-loop call sites.
- `backend/tests/test_startup.py` and/or submission test files -- add deterministic concurrent single and series interleavings using real database and artifact fixtures; cover orphaned-run and startup behavior.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- set only F1 to `done` after checks pass.

**Acceptance Criteria:**
- Given an active publisher and an expired run, when the runtime loop recovers and reconciles, then the publisher's request can reach an accepted run and same-key retry returns that run.
- Given a pre-run submission left interrupted before startup, when startup reconciliation runs, then it remains terminally failed and its orphan intent is quarantined.
- Given an expired run with an unresolved intent, when runtime reconciliation runs, then its intent is reconciled under the existing integrity rules.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Follow-up review
- verdicts: 12 findings — high 0, medium 9, low 1, false 0, maybe-false 2
- findings:
  - `[medium]` `[defer]` Startup on another instance can fail a live publisher — carried: startup still performs full cleanup; cross-instance ownership is absent and already deferred above.
  - `[medium]` `[defer]` A dead publisher can retain a publishing key until startup — carried: runtime has no durable ownership or expiry signal to distinguish it from a live publisher.
  - `[medium]` `[defer]` Abandoned pre-run objects are not inspected at runtime — carried: the same missing ownership signal prevents safe cleanup; startup still inspects them.
  - `[medium]` `[defer]` An unrelated run-bound intent can fail a runtime pass — carried: the run-bound scan predates F1 and remains an existing gate.
  - `[maybe-false]` `[defer]` A concurrent run-row lock might abort reconciliation — no harmful interleaving was demonstrated; an instrumented lock-contention test would settle it.
  - `[low]` `[reject]` Series preflight makes a second artifact read — no material cost or failure was measured, and this belongs to the already completed F5 change.
  - `[medium]` `[defer]` Series preflight lacks a batch deadline — this is tracked as the open F8 action item.
  - `[maybe-false]` `[defer]` IndexedDB deletion could strand a stored request — the reviewer did not demonstrate a reachable cleanup failure; a forced browser storage failure would settle it under F7.
  - `[medium]` `[defer]` Storage access can throw during client cleanup — this is outside the F1 backend change and needs a frontend failure test.
  - `[medium]` `[defer]` Vite routing lacks an automated HTTP proxy check — the F2 work has one-time HTTP evidence, while a repeatable proxy check remains useful.
  - `[medium]` `[defer]` Dead-publisher retry can stay pending — carried duplicate report of the existing ownership limitation.
  - `[medium]` `[defer]` Vite proxy rewrite lacks regression coverage — duplicate verification-gap report; F2 has one-time HTTP evidence.

### 2026-09-23 — Review pass
- verdicts: 11 findings — high 0, medium 6, low 2, false 2, maybe-false 1
- findings:
  - `[false]` `[reject]` Runtime mode is described as processing only recovered-run intents — the implementation retains the pre-existing scan of all run-bound intents; F1 concerns exclusion of pre-run submissions, so no newly broadened scan occurs.
  - `[medium]` `[patch]` The post-execution recovery call lacked a concurrent regression — the test now exercises both claim-loop recovery sites with a paused publisher and verifies commit and same-key retry.
  - `[medium]` `[defer]` A dead publisher can remain `publishing` while service stays up — no durable owner signal exists; runtime preserves these keys until startup so it cannot safely distinguish them from live uploads.
  - `[medium]` `[defer]` Another instance's startup can interrupt a live publisher — startup's full cleanup predates this runtime-specific change and multi-instance overlap remains unverified.
  - `[medium]` `[defer]` Abandoned pre-run objects lack runtime integrity inspection — runtime intentionally leaves all pre-run intents for startup without an owner signal.
  - `[medium]` `[defer]` Unrelated run-bound intents can fail runtime reconciliation — the scan already covered all nonterminal run-bound intents and this change retains that gate.
  - `[maybe-false]` `[reject]` Run-bound intent row locking might delay claims — actual producer transaction length and a harmful wait were not established; an instrumented overlap would settle the impact.
  - `[low]` `[reject]` Ten-second test synchronization might flake in slow CI — the observed integration suite passed and no slow-run evidence warrants more timeout machinery.
  - `[medium]` `[patch]` Test cleanup could delete a shared content-addressed final object — cleanup now deletes only unique temporary objects.
  - `[low]` `[reject]` Publication states after `pending_upload` lack separate concurrent pauses — runtime's runless filter is state-independent and the requested concurrent upload check covers single and series publication.
  - `[false]` `[reject]` Retrospective text still describes F1 as unfixed — it is a preserved historical review snapshot; current remediation is tracked by the F1 action item and this spec.

## Design Notes

Runtime recovery has no durable owner signal for pre-run submissions. Excluding pre-run submission intents from its pass prevents false interruption. Startup runs before this instance accepts requests and retains its existing orphan cleanup; cross-instance startup overlap is not proven safe by this change.

## Verification

**Commands:**
- `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` -- expected: backend suite passes with isolated PostgreSQL and S3 fixtures.
- `git diff --check` -- expected: no whitespace errors.

## Auto Run Result

Status: done.

Runtime reconciliation now processes run-bound intents without changing pre-run publication intents or `publishing` requests. Both claim-loop recovery calls use this mode; startup retains full reconciliation. Only the F1 sprint action item is `done`.

Changed files: `backend/app/adapters/postgres.py` selects reconciliation scope; `backend/app/application/executor.py` selects runtime mode; `backend/tests/test_single_image.py` covers single/series overlap at both call sites; `backend/tests/test_startup.py` covers startup interruption and runtime integrity failures; `sprint-status.yaml` records F1 completion.

Review: two medium findings patched (post-execution test gap and unsafe shared-object cleanup); four pre-existing or owner-model limitations deferred; five findings rejected with reasons in the triage log. Follow-up review is recommended because two medium findings required patches. The remaining unverified risk is cross-instance startup overlap and dead-publisher ownership, which this runtime regression check cannot distinguish.

Verification: `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 71 passed in 65.56s; `git diff --check` — passed. GUI, deployment, and production runtime were not exercised. No commit or push was made; the user's pre-existing retrospective and evidence remain uncommitted and unchanged.

Follow-up verification on 2026-09-23: the F1 patch was applied to a clean temporary clone on branch `fix/epic-1-retro-protect-live-submissions` and checked against isolated PostgreSQL database `epic1_f1_test` and MinIO bucket `epic1-f1-test`. Focused runtime single/series upload interleavings, startup interruption cleanup, runtime/startup integrity gates, and lease recovery: **14 passed in 2.21s**. `git diff --check` passed. No GUI or production environment was used.

Current follow-up verification on 2026-09-23 at `7b5b3b6`: the existing F1 runtime filter and both claim-loop call sites were read back; the concurrent single and series tests still assert accepted publication, preserved intents, and same-key retry after recovery. `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` passed **71 tests in 68.60s** against local PostgreSQL and MinIO; `git diff --check` passed. No F1 code change was needed in this pass. The F1 sprint item was set to `in-progress` for this verification and restored to `done` only after it passed. F6 remains open because rendered UI acceptance requires GUI operation, which this run prohibits.

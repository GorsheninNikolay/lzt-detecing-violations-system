---
title: 'Make series frame-usability progress truthful'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
baseline_revision: 'ca1b340bc745eabff822490b6d0b7438b68e28ea'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The first observation reservation completes the run-level frame-usability stage while later series frames have not been read or assessed. Polling therefore reports completed work that has not happened.

**Approach:** Finish verified reads and usability assessment for every ordered frame before the first observation reservation. Keep the stage running during that pass and advance to equipment observation only after it finishes.

## Boundaries & Constraints

**Always:** Preserve the six ordered persisted stages, one running stage, the run lease and authorization fence, per-frame observation order, prior completed invocation evidence after later observation failure, and source-artifact integrity checks. Retain the current one-frame-at-a-time memory bound by rereading assessable frames for provider execution. Change only F5's action item to `done` after verification.

**Never:** Mark usability complete after checking only the first frame, hold every decoded image in memory, change the unsupported numeric usability policy as part of F5, or close other retrospective items.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Later frame still checking | A two-frame run pauses during frame 2 usability assessment | API and database show usability `running`, observation `pending`, and no invocation | Release allows normal completion |
| All frames checked | The pass finishes and frame 1 provider work is paused | API and database show usability `succeeded`, observation `running` | Resume yields one successful series |
| Later read fails during observation | Frame 2 passed preflight but its observation read fails | Run fails at equipment observation and retains frame 1 evidence | No result projection |
| Preflight integrity fails | Frame 2 fails its first verified read | Run fails at frame usability, with observation skipped | No provider reservation |

</intent-contract>

## Code Map

- `backend/app/application/executor.py:129` -- `_execute` currently reads, assesses, reserves, and observes each frame in one loop; preflight all ordered frames before entering the reservation loop. `ClaimLoop._run` is its production caller.
- `backend/app/adapters/postgres.py:551` -- `claim_ordinary` starts stage 1; `reserve_ordinary` at line 585 completes it on the first call and starts stage 2. The executor must not call it until every frame is checked. `fail_ordinary` fails the currently running stage and skips pending stages.
- `backend/tests/test_ordered_series.py:214` -- existing PostgreSQL/S3 series contract covers successful ordered processing and later read failure; add intermediate API and persisted-stage assertions, and make the later-read failure occur after preflight.
- `_bmad-output/planning-artifacts/epics.md:563` and architecture AD-26 -- persisted progress must reflect committed stage truth, with at most one running stage. Read-only requirements.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md:35` -- retained F5 finding; leave retrospective evidence unchanged.

## Tasks & Acceptance

**Execution:**
- `backend/app/application/executor.py` -- assess all frames before the first reservation and reread only assessable frames for provider execution.
- `backend/tests/test_ordered_series.py` -- verify both intermediate stage states through the API and database, preflight failure, and preserved frame 1 evidence on a later observation read failure.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- keep F5 `in-progress` during work and set only F5 `done` after the relevant checks pass.

**Acceptance Criteria:**
- Given an accepted series, when frame 2's usability check is paused, then the persisted API reports frame usability `running` and equipment observation `pending` with no provider invocation.
- Given all frames passed the usability pass, when frame 1's observer call is paused, then the API reports usability `succeeded` and observation `running` while the run remains running.
- Given a later observation read fails after frame 1 completed, when failure commits, then frame 1 evidence remains, observation is `failed`, downstream stages are skipped, and no projection exists.
- Given a later preflight read fails, when failure commits, then usability is `failed`, equipment observation is skipped, and no invocation exists.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 8 findings — high 0, medium 1, low 4, false 3, maybe-false 0
- findings:
  - `[medium]` `[patch]` A single-image run gained a second verified S3 read and failure window — it now reuses the preflight bytes; series runs still release each image before the next frame.
  - `[low]` `[patch]` The first five-second pause could expire during API and PostgreSQL assertions on slow CI — its gate now waits up to 30 seconds.
  - `[false]` `[reject]` A third/eighth-frame test was requested to prove complete traversal — `_execute` iterates the entire `work["frames"]` list in preflight, and the second-frame pause already catches premature first-frame completion; no cardinality branch exists.
  - `[false]` `[reject]` A separate read-count assertion for an unassessable frame was requested — the `invocation is None` branch never performs the second read, and the existing mixed-frame test checks its insufficient observations and usable count.
  - `[low]` `[reject]` The verification command uses a temporary local launcher — the launcher exists and the full suite passed; a change only to this spec's command is not an implementation finding. Repository setup remains documented separately.
  - `[low]` `[patch]` The edge-case layer identified the same first pause timeout — the 30-second gate is the shared fix.
  - `[low]` `[patch]` The observation pause had the same five-second CI timeout risk — its gate now waits up to 30 seconds.
  - `[false]` `[reject]` The intent-alignment layer saw no F1 change in this F5 diff — F1 was completed and pushed in baseline `ca1b340bc745eabff822490b6d0b7438b68e28ea` before the user directed development to continue.

## Design Notes

Artifact reads are verified against immutable, content-addressed bytes. A second verified read for an assessable frame avoids keeping all JPEG bodies in memory. Any failure in that second read belongs to the observation stage, while a failure in the first pass belongs to usability.

## Verification

**Commands:**
- `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` -- expected: backend integration suite passes with isolated PostgreSQL and MinIO data.
- `git diff --check` -- expected: clean patch formatting.

## Auto Run Result

Status: done.

Every ordered frame now receives a verified read and usability assessment before the first observation reservation completes the run-level usability stage. Series images are reread only when provider execution needs them; a single-image run reuses its verified bytes. The API and PostgreSQL checks observe usability `running` during the second-frame assessment and `succeeded` only after the full pass, while observation is `running`.

Changed files: `backend/app/application/executor.py` separates the usability pass from observation; `backend/tests/test_ordered_series.py` checks intermediate stages, preflight failure, and a later observation-read failure; `sprint-status.yaml` records only F5 as `done`; this spec records the contract and review.

Review: one medium and one low root-cause group patched (four finding rows); two low and three false findings rejected with reasons above; no items deferred. Follow-up review recommended: false. No high entry and only one medium entry required a patch.

Verification: `backend/.venv/bin/python /private/tmp/epic1_verify.py tests` — 71 passed in 67.34s after review fixes, using isolated local PostgreSQL and MinIO fixtures. Focused follow-up checks — 11 passed. `git diff --check` and the staged diff check passed. Every I/O matrix row is exercised by `test_ordered_series_http_postgres_s3`, which ran in the full suite. GUI, deployment, and production runtime were not exercised.

Residual risk: the repeated verified reads for series add S3 requests; maximum-series latency was not measured. F4 and the other retrospective action items retain their tracked statuses.

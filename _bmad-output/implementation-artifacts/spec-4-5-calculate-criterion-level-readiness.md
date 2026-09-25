---
title: 'Story 4.5: Calculate Criterion-Level Readiness'
type: 'feature'
created: '2026-09-25'
status: 'done'
baseline_commit: '358d46efe4ffb14d38db5e6ce75a3f6a18f9a9cd'
baseline_revision: '358d46efe4ffb14d38db5e6ce75a3f6a18f9a9cd'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The frozen comparison campaign retains every run and its evidence, but has no criterion-level readiness verdict. A success-only aggregate could hide missing cells, failed calls, false warnings, or incorrect outcomes.

**Approach:** Generate an immutable, campaign-bound report from a consistent evidence snapshot. Keep literal measures separate and attach run and input evidence to each criterion and measure.

## Boundaries & Constraints

**Always:** Bind the exact campaign, evaluation set, and explicit readiness-policy revision. Use all 36 planned cells as the population, including failures and timeouts. Produce exactly one `pass|fail|not_evaluated` row per policy criterion. Any unevaluated criterion makes overall status `incomplete`; otherwise any fail makes it `fail`; only all-pass makes it `pass`. Count technical errors in applicable denominators and as misses where a detection is expected. Preserve `insufficient_data` and `not_analyzed` as distinct states; neither is a negative observation nor a false warning. Record latency, cost availability, repeat disagreement, and check-request comprehension as separate literal measures. Evidence references must identify the actual run and, where available, input, observation, invocation, projection, and artifact.

**Never:** Infer equipment absence from technical failure or unavailable observations, fabricate cost or comprehension measurements, omit missing cells, choose a provider, publish a decorative score, mutate campaign evidence, or imply a live campaign was executed.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Complete correct campaign | All cells terminal, required detections and outcomes correct, no false check request | All criteria pass; literal metrics and evidence retained | No error expected |
| Pending cell | One manifest cell still planned or running | Its mandatory coverage is `not_evaluated`; overall `incomplete` | Keep planned denominator and missing evidence visible |
| Terminal failure or timeout | Applicable cell has no valid observation/outcome | Mandatory criterion fails; error or timeout remains in its population | Never score as negative observation |
| False check request | `check_requested` on a fixture that does not expect it | Zero-false-warning criterion fails with run evidence | Non-applicable/insufficient observations do not become warnings |
| Repeat disagreement | Same fixture and candidate yields differing terminal outcomes or observations | Separate disagreement numerator and denominator | Missing repeats remain missing, not agreement |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:977` and `_bmad-output/implementation-artifacts/epic-4-context.md` — Story 4.5 and AD-24 outcome/accounting requirements.
- `backend/app/domain/comparison_campaign.py:15` — frozen fixture and candidate manifest; reuse its immutable expected outcome and frame labels.
- `backend/app/domain/evaluation_set.py:23` — scenario contract and portable label semantics.
- `backend/app/adapters/postgres.py:171` — existing repeatable-read campaign readback; extend to report evidence and immutable report persistence from one snapshot.
- `backend/app/adapters/postgres.py:1137` — successful run writes observations and projection; terminal failures retain error and invocation evidence.
- `backend/migrations/versions/0012_comparison_completion.py` — latest migration and terminal evidence guard; add report tables after this revision.
- `backend/app/application/evaluation.py:16` — existing operator CLI; add report generation/readback with safe JSON error behavior.
- `backend/app/adapters/artifacts.py` — private integrity-checked artifact publication contract for report bytes.
- `backend/tests/test_comparison_campaign.py` — PostgreSQL-backed 36-cell fixtures and operator-command tests.

## Tasks & Acceptance

**Execution:**
- `backend/app/domain/evaluation_report.py` — define the explicit versioned criterion set, deterministic metric populations and fail-closed status calculation from manifest plus actual evidence.
- `backend/migrations/versions/0013_evaluation_report.py` — persist immutable campaign/revision-bound report snapshots and criterion rows, with unique evidence digest and one row per criterion; permit a later snapshot when pending campaign evidence changes.
- `backend/app/adapters/postgres.py` — read all planned cells, labels, outcomes, observations, invocations and artifact references in one consistent snapshot; persist and read a report idempotently by evidence digest.
- `backend/app/adapters/artifacts.py` — publish report bytes privately with integrity verification using the existing artifact contract.
- `backend/app/application/evaluation.py` — expose explicit report generation and readback commands; serialize byte-free safe output.
- `backend/tests/test_comparison_campaign.py` — cover the I/O matrix, exact denominators, row uniqueness, links, idempotence, and technical/non-applicable distinctions.

**Acceptance Criteria:**
- Given a frozen campaign and readiness-policy revision, when a report is generated, then every criterion has one status, reason, evidence references, and applicable numerator/denominator, with the overall status derived from all rows.
- Given expected-detection, expected-outcome, false-warning, and non-applicable populations, when evidence is scored, then misses, false detections, errors/timeouts, repeat disagreements, latency, cost, and comprehension appear as separate literal measures with manifest-based denominators.
- Given a false check request, absent mandatory case, or incorrect required outcome, when readiness is generated, then the relevant criterion fails and no provider winner or aggregate score is present.

## Spec Change Log

## Review Triage Log

### 2026-09-25 — Review pass
- verdicts: 14 findings — high 0, medium 10, low 3, false 1, maybe-false 0
- findings:
  - `[medium]` `[patch]` Absent manifest cell was treated as pending — `build_report` synthesized `state=missing` and then marked coverage `not_evaluated`; missing cells now fail coverage while existing planned/running cells remain unevaluated.
  - `[medium]` `[patch]` Failed run's retained false detection was omitted — observations can be retained before later failure; count persisted `detected` against a `no` label regardless of run terminal state.
  - `[medium]` `[patch]` Repeat disagreement denominator included unevaluated groups — the numerator only inspects complete groups; denominator now equals completed groups while missing cells remain in planned-cell accounting.
  - `[medium]` `[patch]` Empty latency was called observed — no run may have a latency measurement; availability now reflects zero measurements and reports `measured_count`.
  - `[low]` `[reject]` Observation reason is absent from compact report references — references identify run, input, class, invocation, and projection; `read_ordinary` retrieves the persisted observation reason at `backend/app/adapters/postgres.py:1397`. Duplicating that text in every criterion row would expand the immutable report without improving traceability.
  - `[false]` `[reject]` Legacy `evaluation_report_bindings` is not populated — the new `evaluation_reports.evaluation_revision_id` column has a direct foreign key and binds each report in the same row; no report reader uses the legacy table.
  - `[low]` `[reject]` Report readback omits creation time — `evaluation_reports.created_at` is persisted; the requested Story 4.5 CLI does not require that presentation field, and Story 4.6 owns last-known-report display.
  - `[low]` `[patch]` Criterion declaration was unused — a later policy edit could silently omit a row; exact generated-key coverage is now checked against `CRITERIA` before status derivation.
  - `[medium]` `[patch]` Empty latency availability, independently found by the edge-case reviewer — same observed path and correction as the fourth finding.
  - `[medium]` `[patch]` Missing mandatory cell, independently found by the edge-case reviewer — same synthesized-missing path and correction as the first finding.
  - `[medium]` `[patch]` No false-detection positive assertion — the old test checked only the denominator; added a retained failed-run detection with numerator and run/input evidence assertions.
  - `[medium]` `[patch]` Persisted successful outcome was not verified through report generation — added a successful campaign cell's projection and linked evidence assertion in the PostgreSQL-backed execution test.
  - `[medium]` `[patch]` Sprint tracking still said Story 4.5 `backlog` — synchronizing only the Story 4.5 entry after review and validating the canonical status file.
  - `[medium]` `[patch]` Missing mandatory cell diverged from the story's criterion verdict, independently found by the intent auditor — same synthesized-missing path and correction as the first finding.

## Design Notes

The policy gates are `campaign_coverage`, `mandatory_detections`, `mandatory_outcomes`, and `zero_false_warnings`. Pending cells make applicable criteria `not_evaluated` unless observed evidence already proves failure; terminal technical failure fails applicable mandatory criteria. A later evidence snapshot creates a new immutable report, while regeneration from identical evidence returns the same report. Cost and check-request comprehension have no persisted observation source in the current execution contract, so report them as unavailable measures with a reason, without fabricating zero or making them an unrequested passing gate.

## Verification

**Commands:**
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest tests/test_comparison_campaign.py -q` — focused report and campaign tests pass.
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest -q` — backend regressions pass.
- `git diff --check` — no whitespace errors.

## Auto Run Result

Status: done. Story 4.5 now generates an immutable, campaign-bound criterion report with separate literal measures and evidence references. An incomplete campaign yields an incomplete report; a missing manifest cell or terminal mandatory failure fails its applicable criterion. No provider winner or aggregate score is produced.

Files changed:
- `backend/app/domain/evaluation_report.py` — versioned four-criterion calculation and literal population accounting.
- `backend/migrations/versions/0013_evaluation_report.py` — immutable report and criterion persistence.
- `backend/app/adapters/postgres.py` — consistent evidence readback, report generation, idempotent storage, integrity-checked readback.
- `backend/app/adapters/artifacts.py` — verified private JSON publication and temporary-object cleanup.
- `backend/app/application/evaluation.py` — explicit generate/read CLI commands.
- `backend/tests/test_comparison_campaign.py` — matrix, persistence, S3-cleanup, and successful-projection regression checks.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — targeted Story 4.5 synchronization.

Review: 14 findings triaged. Six medium and one low root-cause entries were patched; no items were deferred. Two low findings were rejected because linked run evidence already exposes the observation reason and Story 4.6 owns report-time display; one false finding was rejected because the new report row has a direct evaluation-revision foreign key. A follow-up review is recommended because multiple medium entries required repair. The specific unverified risk is the generated report against a live, fully executed local/cloud campaign; tests use synthetic campaign inputs and controlled provider responses.

Verification: `tests/test_comparison_campaign.py` passed 55 tests. The full backend suite passed 209 tests with no skips on isolated PostgreSQL, a separate MinIO test bucket, the pinned offline local model, and checksum-verified held-out archive/image. An operator CLI smoke generated an `incomplete` four-criterion report from a synthetic campaign and read the identical JSON back through real MinIO. The canonical sprint validator passed and readback shows Story 4.5 `done`. `git diff --check` and staged whitespace checks passed. No live cloud campaign or GUI surface was exercised.

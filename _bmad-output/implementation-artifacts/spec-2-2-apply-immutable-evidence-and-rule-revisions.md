---
title: 'Apply Immutable Evidence and Rule Revisions'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '4d763a9834bce2eab00938c56675b6dff76be036'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Rule runs persist policy and rule snapshots, but their revision identities can be reused after configuration changes, and the database does not prevent rewriting the bound configuration. The API omits part of the immutable run binding from readback.

**Approach:** Define complete, content-identified initial policy and rule revisions, bind them with the declared context, taxonomy, and authorized observer profile, and make those run bindings immutable after creation. Return the binding evidence needed to verify a run.

## Boundaries & Constraints

**Always:** Keep the configured expectation that excavators work continuously and dump trucks arrive periodically, labeled `demonstration rule`. Require explicit excavation stage, scenario, declared observation area, period, and enabled observer profile. Keep the two portable classes and upload order. A rule needs at least three usable frames from the declared area; observer inability or insufficient usable frames yields `insufficient_data` with a reason and no check request. Leave subjective resolution, visibility, object-size, cadence, duration, miss-rate, false-detection, and stability thresholds unset. A changed policy or rule value receives a distinct revision identity; old run evidence remains unchanged.

**Never:** Edit historical migrations or rewrite old run snapshots. Infer area, period, stage, or rule from filenames, images, or schedules. Treat demonstration provenance as normative or turn non-detection into a site-wide absence claim. Add a policy editor, revision-management API, or Story 2.3+ behavior.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Rule run binding | Valid excavation request and enabled observer | Persist and read back the complete policy, rule, taxonomy, context, and observer binding | Reject incomplete or inapplicable binding |
| Configuration revision | Any policy or rule value changes | New content-identified revision; existing run retains its original snapshot | Database rejects attempts to rewrite bound run evidence |
| Insufficient evidence | Fewer than three usable frames or an unassessable observation | `insufficient_data`, specific reason, no recommendation | Technical failures remain failures without a projection |

</intent-contract>

## Code Map

- `backend/app/domain/rule.py:1-43` -- initial rule/policy constants and evaluator. Preserve current outcome semantics; complete the policy fields and derive revision identity from canonical snapshot content.
- `backend/app/domain/observations.py:7-9,79-94` -- canonical two-class taxonomy and portable observation states.
- `backend/app/application/submission.py:37-85` -- explicit intent, stage, area, period, and class request validation; JPEG decoding is the current supported-image boundary.
- `backend/app/adapters/postgres.py:491-560` -- atomic run binding for observer profile and authorization, context, policy/rule/taxonomy snapshots, and ordered inputs; `:782-822` is the API readback, which currently omits taxonomy and top-level profile binding.
- `backend/migrations/versions/0003_single_image.py` and `0005_rule_intent.py` -- historical snapshot columns. Do not edit; add a forward migration for binding completeness and update protection.
- `backend/tests/test_rule_intent.py:47-153` -- existing normalized-outcome and PostgreSQL/S3 run coverage; extend it for complete readback, revision identity, and immutable snapshot enforcement.
- `web/src/App.tsx:98-103` and `web/src/App.test.tsx:87-100` -- result surface already renders the bound rule revision, expectation, and provenance; retain this server-snapshot behavior.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark Story 2.2 `in-progress` during implementation and `done` only after the verified acceptance work is complete.

## Tasks & Acceptance

**Execution:**
- `backend/app/domain/rule.py` -- define the full initial evidence policy (supported decoded JPEG, upload order, one declared area, three usable frames, observer inability, and unset subjective thresholds) and make rule/policy revision identities change whenever snapshot content changes -- rationale: give each check a stable, reproducible meaning.
- `backend/migrations/versions/0006_immutable_run_configuration.py` -- add rule-binding completeness constraints and prevent updates to run context, observer binding, taxonomy, policy, rule, and requested-class snapshots -- rationale: enforce the historical record at the database boundary.
- `backend/app/adapters/postgres.py` -- persist and read back the complete taxonomy and observer binding with existing snapshots -- rationale: expose enough evidence to verify what the run used.
- `backend/tests/test_rule_intent.py` -- verify all bound fields, changed-content revision identity, rejected snapshot rewrites, and retained insufficient-data behavior -- rationale: catch drift in configuration and persistence.
- `web/src/App.test.tsx` -- assert completed rule explanations display the bound revision, expectation, and `demonstration rule` provenance -- rationale: test the outer result surface named by the acceptance criteria.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize only Story 2.2 with the verified workflow state -- rationale: keep sprint tracking authoritative.

**Acceptance Criteria:**
- Given a valid rule-evaluation request, when the run is created and read back, then it contains the complete immutable policy and rule snapshots, two-class taxonomy, explicit area and period, ordered manifest, and selected observer profile with its authorization revision.
- Given any policy or rule value changes, when the configuration is snapshotted, then its revision identity changes, and an update to an existing run's bound evidence is rejected while its original values remain readable.
- Given a supported decoded image the observer cannot assess or fewer than three usable images from the declared area, when policy evaluation completes, then the result is `insufficient_data` with a specific reason and no check request, without applying subjective quality, visibility, size, cadence, or duration thresholds.
- Given a completed rule run, when its explanation is rendered, then it uses the bound revision and states that excavators are continuously expected, dump trucks are periodically expected, and provenance is `demonstration rule`.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 11 findings — high 0, medium 9, low 0, false 2, maybe-false 0
- findings:
  - `[false]` `[reject]` Sprint-status synchronization has no automated test — the request requires synchronized tracking, not a new test; this diff changes Story 2.2 from `backlog` to `in-progress`, and final state will be read back after verification.
  - `[medium]` `[patch]` Submitted input manifests can be rewritten — `run_inputs` has no mutation guard, while accepted ordinary runs are still read from those rows; add a database guard for insert, update, and delete after submission acceptance, with regression coverage.
  - `[medium]` `[patch]` Rule policy permits fewer than three usable frames — the insert guard validates only that the minimum is numeric, and `evaluate_rule` trusts it; reject values below three while allowing a later stricter revision.
  - `[false]` `[reject]` Database does not recompute content-derived revision identity — the supported creation path constructs `RULE` and `RULE_POLICY` through `revisioned_snapshot` and persists those constants; request fields cannot supply policy or rule content, so the claimed reuse does not occur on the application path.
  - `[medium]` `[patch]` Bound observer snapshot may not match its profile ID — authorization is rechecked at commit but the run snapshot argument is not compared with the stored profile snapshot; require equality in the insert guard and cover mismatches.
  - `[medium]` `[patch]` Policy admission value is not validated — the guard checks that the field exists but accepts a value inconsistent with the fixed supported-decoded-JPEG policy; require `supported_decodable_images`.
  - `[medium]` `[patch]` Insufficiency explanation hardcodes three frames — rule evaluation reads the bound minimum from the policy, but its reason stays fixed at three; render the bound minimum and test a changed revision.
  - `[medium]` `[patch]` Rule policy permits fewer than three usable frames — the database guard has no lower bound for the numeric minimum; reject values below three while preserving future stricter revisions. Duplicate of the blind review's same verified claim.
  - `[medium]` `[patch]` Policy admission value is not validated — a complete-looking run can persist a different admission policy; require the initial policy's `supported_decodable_images` value. Duplicate of the blind review's same verified claim.
  - `[medium]` `[patch]` Bound observer snapshot may not match its profile ID — the trigger validates profile authorization but not snapshot identity; compare the stored profile snapshot with the run binding. Duplicate of the blind review's same verified claim.
  - `[medium]` `[patch]` Submitted input manifests can be rewritten — ordinary-run image hashes, context, and order remain mutable through `run_inputs`; guard mutation after accepted submission. Duplicate of the blind review's same verified claim.

## Design Notes

The observer profile already has an admitted immutable row and authorization revision; preserve that binding rather than introducing a second profile registry. Derive policy and rule revision identity from canonical content so changing a value cannot silently reuse the current identity. Store per-run copies and protect only the run's immutable binding columns; lifecycle state and lease updates must continue to work.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py tests/test_ordered_series.py tests/test_single_image.py` -- expected: new snapshot protections and existing observation/rule regressions pass against local PostgreSQL/S3.
- `cd web && npm test -- --run` -- expected: bound rule explanation and existing form flows pass.
- `cd web && npm run build` -- expected: production TypeScript build succeeds.

## Auto Run Result

Status: done

Implemented content-identified rule and policy revisions, complete evidence-policy snapshots, immutable run bindings and accepted-submission manifests, and API readback for the taxonomy and observer profile binding. The result explanation continues to show the bound revision, expectation, and demonstration provenance.

Files changed:
- `backend/app/domain/rule.py` -- complete policy fields, content-derived identities, preserved `not_analyzed` outcomes, and revision-bound insufficiency wording.
- `backend/app/adapters/postgres.py` -- return the taxonomy and observer-profile binding in run readback.
- `backend/migrations/versions/0006_immutable_run_configuration.py` -- validate rule bindings and prevent rewriting snapshots or accepted input manifests.
- `backend/tests/test_rule_intent.py` -- cover content identity, complete binding readback, database guards, immutable manifests, and policy outcomes.
- `web/src/App.test.tsx` -- assert the result displays the bound rule details and provenance.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark Epic 2 Story 2.2 done after verification.
- This specification -- record the implementation, review, and verification evidence.

Review findings: five patch entries fixed (five medium); zero deferred; two false findings rejected with reasons in the Review Triage Log. Follow-up review recommended because this pass patched five medium entries. The specific unverified risk is migration rollout: `0006` was applied and exercised against an isolated local database, but no deployed application database or runtime was checked.

Verification:
- Backend regression command -- 32 passed against an isolated PostgreSQL database and MinIO bucket, with the pinned offline CPU model snapshot. Temporary database and bucket were removed.
- Web tests -- 37 passed.
- Production web build -- passed.
- Alembic history showed `0006_immutable_run_configuration` at head; the backend suite applied it successfully to the isolated test database.

Residual risks: No deployed runtime or rendered browser session was checked. Deployment must apply migration `0006` before serving these bindings.

---
title: 'Choose an Applicable Analysis Intent'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '01d67a263ea807c1b211eb766de6e9f6ea7c97eb'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      A rule deployment between choice loading and submission may bind a revision different from the one displayed.
    evidence: |-
      The choice endpoint and submission use static in-process rule data, but the deployment envelope is not defined. A rolling revision change during an open form would settle this risk.
    location: >-
      web/src/App.tsx:325; backend/app/adapters/postgres.py:536
    severity: medium (unverified)
  - summary: >-
      A future policy revision may make the fixed three-frame pre-submit notice stale.
    evidence: |-
      Current policy and notice both require three frames. A changed minimum without synchronized frontend deployment would make the notice inaccurate; no such revision exists now.
    location: >-
      web/src/App.tsx:635
    severity: medium (unverified)
  - summary: >-
      The connected manager journey has not been checked in a rendered browser.
    evidence: |-
      UI tests cover the live choices fetch with a mocked response and backend integration covers publication and rule outcomes, but the working agreement prohibits launching GUI applications in this session.
    location: >-
      web/src/App.tsx; backend/app/main.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** New Analysis silently submits observation-only runs. A manager cannot choose the configured excavation check or see the rule context before committing evidence.

**Approach:** Expose a stage-aware native-radio intent choice, bind the selected intent and applicable rule on the server, and render the backend's truthful outcome for rule submissions. Preserve observation-only behavior and exact request recovery.

## Boundaries & Constraints

**Always:** Only the explicit configured excavation stage permits rule evaluation. Show stage, area, period, rule name, revision, expectation, and demonstration provenance before submit. Permit one or two images with a non-blocking three-usable-image notice; the server determines `insufficient_data`. Persist intent in the immutable run and idempotency identity. A rule run must not succeed as `observations_only`; evaluation uses normalized observations and immutable rule/policy context, with no rule inference from filenames, stage labels, or dates. With at least three usable same-area frames, a detected excavator and dump-truck non-detection in every usable frame requests one human check; a detected dump truck yields `no_check`. Other evidence yields a specific non-check outcome, never an invented detection. Keep the existing observation-only API path valid.

**Never:** Treat a short series as a client-side verdict, claim a violation, invent a normative source, or turn observer failure into insufficient evidence. Do not create the Story 2.5 viewer, Story 2.6 demonstration chooser, or Epic 3 stage dashboard here.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Configured stage | Excavation selected | Rule radio selected; applied context visible; exact chosen intent submitted | Invalid intent/stage combination rejected by API |
| Observation mode | User selects alternative | Observation-only request and result, no rule check | Reused key with changed intent conflicts |
| Unconfigured stage | Other stage selected | Rule radio unavailable with exact scope reason; observation mode selected | Direct rule API request rejected |
| Short rule series | One or two JPEGs | Submission allowed; notice shown; backend emits specific `insufficient_data` after observation | Technical failure remains failed, with no projection |
| Sufficient rule series | Three or more usable JPEGs | Backend applies the bound rule and returns its evidence-based outcome | Unassessable evidence cannot create a check |

</intent-contract>

## Code Map

- `web/src/App.tsx:257,586,609` -- form state and hardcoded observation-only request/UI; preserve `Pending` body's key during uncertain recovery at lines 145–176, 516–560.
- `web/src/App.test.tsx:234` -- existing submission contract and user-facing tests; extend for intent, stage, context, short series, and retry.
- `web/src/styles.css` -- existing panel/fieldset styles; add only the selector and context presentation needed.
- `backend/app/application/submission.py:30` -- rejects rule intent and omits intent from request hash; preserve existing JPEG/series validation.
- `backend/app/adapters/postgres.py:493,522,700,725,765` -- commits fixed observation policy, skips rule, creates observation-only projection, omits snapshot readback; reuse normalized frame observations.
- `backend/app/main.py:120` -- submission/read routes; serve authoritative rule applicability/context without inferring it in the browser.
- `backend/migrations/versions/0002_admission.py:101` -- outcome constraint is observation-only; change through a new migration, not historical migration edits.
- `_bmad-output/planning-artifacts/epics.md:635` -- Story 2.1 acceptance and Epic 2 boundary; read-only.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:124` -- radio, context, notice and result language; read-only.

## Tasks & Acceptance

**Execution:**
- `backend/app/application/submission.py`, `backend/app/main.py` -- publish a stable stage/rule choice contract, validate selected intent and stage, and include intent in idempotency identity.
- `backend/app/adapters/postgres.py`, `backend/migrations/versions/0005_rule_intent.py` -- bind immutable applicable context, evaluate rule intent from normalized evidence, and persist/read truthful outcome without altering historical migrations.
- `web/src/App.tsx`, `web/src/styles.css` -- provide explicit stage and intent controls, pre-submit context and short-series notice; preserve the exact pending request on retry and display the returned rule outcome.
- `backend/tests/test_rule_intent.py`, `web/src/App.test.tsx` -- exercise the matrix at API/database and user-facing surfaces, including ordinary observation regression.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize Epic 2 and Story 2.1 with the verified workflow state.

**Acceptance Criteria:**
- Given New Analysis on the configured excavation stage, when it opens, then the rule radio is selected and the area, period, name, revision, expectation, and provenance are visible before submission.
- Given an unconfigured stage, when it is selected, then rule evaluation is disabled with `Для этого этапа правило не настроено в прототипе`, observation-only is selected, and the API rejects a forged rule submission.
- Given one or two images in rule mode, when the manager submits, then the form does not block, the three-usable-image notice is visible, and the run eventually shows backend-derived `insufficient_data` with no check request.
- Given observation-only mode, when the manager submits and reopens the run, then its selected intent and observation-only result remain authoritative; uncertain retry preserves the original body and key.
- Given a sufficient configured rule run, when it completes, then the result is derived from normalized persisted evidence and the bound revision, never relabeled observation-only.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 15 findings — high 0, medium 6, low 2, false 4, maybe-false 3
- findings:
  - `[false]` `[reject]` Free-form scenario can differ from excavation stage — applicability is bound to the explicit stage key, and scenario text is never used to infer a rule.
  - `[false]` `[reject]` Mixed physical areas can be uploaded under one declared area — the contract records the user's single area declaration and does not claim image-derived area verification.
  - `[medium]` `[patch]` Rule requests could omit a required class — submission now rejects requests without both informative classes; focused tests cover the guard.
  - `[maybe-false]` `[defer]` Displayed rule revision could differ after a deployment — rule data is static per process; a rolling change during an open form would establish the risk.
  - `[maybe-false]` `[defer]` Three-frame notice could drift from a future policy revision — current policy and UI both say three; a changed minimum would establish the risk.
  - `[medium]` `[patch]` Stage switching reset an explicit observation-only choice — the form now retains that preference and a UI test covers the round trip.
  - `[false]` `[reject]` `no_check` lacks a supporting frame reference — normalized per-frame observations and their source IDs remain in the same projection and run readback.
  - `[medium]` `[patch]` A failed choices request stranded the form — added in-page retry and a test that preserves entered context.
  - `[low]` `[reject]` Queued and failed run headers omit the intent — the selected intent is available at submission and persisted in readback; adding another header surface for this story has negligible benefit.
  - `[medium]` `[patch]` No database `no_check` test — the integration test now verifies its persisted outcome and absent recommendation.
  - `[low]` `[reject]` Downgrade fails with rule outcomes — reverting this data-bearing migration is non-routine, and making it succeed would require deleting or relabeling immutable results.
  - `[medium]` `[patch]` Production choices fetch path was bypassed in UI tests — a test now fetches the endpoint shape and checks the default rule selection and enabled submit.
  - `[medium]` `[patch]` Persisted `no_check` was not covered — the same database integration case now checks the readback after execution.
  - `[false]` `[reject]` Invocation might mean Epic 1 Story 1.1 — Epic 2 has Story 2.1 as its first and no Story 1.1; the epic qualifier resolves the target.
  - `[maybe-false]` `[defer]` Connected manager journey may diverge from component and backend tests — no rendered end-to-end run was permitted; browser evidence would settle it.

## Design Notes

Story 2.1 is the first vertical entry into rule intent. Later stories deepen revision management, evidence inspection and demonstration fixtures, but a selectable rule cannot point at the current observation-only projection. The initial rule evaluation therefore needs a truthful minimal outcome path and database constraint migration. The browser displays the server contract and projection rather than deciding applicability or result from names or frame count.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py tests/test_single_image.py tests/test_ordered_series.py` -- expected: new and regression cases pass with local PostgreSQL/S3 composition.
- `cd web && npm test -- --run` -- expected: intent choice and existing UI tests pass.
- `cd web && npm run build` -- expected: TypeScript and production build pass.

## Auto Run Result

Status: done

Implemented an explicit stage and intent selector backed by server-provided rule context. Rule submissions bind immutable policy/rule snapshots, retain intent through publication and readback, and produce evidence-derived outcomes; observation-only runs remain supported. The UI displays the server outcome and preserves uncertain submission retries.

Files changed:
- `backend/app/application/submission.py`, `backend/app/main.py` — validate and expose the intent/stage contract.
- `backend/app/domain/rule.py`, `backend/app/adapters/postgres.py`, `backend/migrations/versions/0005_rule_intent.py` — evaluate normalized evidence, persist revisions and outcomes, and read them back.
- `backend/tests/test_rule_intent.py` — validate choices, eligibility, and PostgreSQL/S3 execution of insufficient, check-requested, and no-check cases.
- `web/src/App.tsx`, `web/src/styles.css`, `web/vite.config.ts`, `web/src/App.test.tsx` — show the choice and result, support settings retry, and verify form behavior.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — mark Epic 2 in progress and Story 2.1 done.

Review: 15 findings; five medium root-cause entries patched (six medium rows, including duplicate `no_check` coverage reports), three unverified risks deferred, and six findings rejected with reasons in the Review Triage Log. Follow-up review recommended because multiple medium patches changed the request and settings paths; the remaining revision drift risk needs a deployment-bound contract check.

Verification: isolated local PostgreSQL database migrated to `0005_rule_intent`; full backend suite `87 passed`; web suite `37 passed`; production web build passed; `git diff --check` passed. No rendered-browser or deployed-runtime check was performed under the no-GUI working agreement.

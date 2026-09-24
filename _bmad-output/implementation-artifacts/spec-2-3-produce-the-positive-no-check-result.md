---
title: 'Produce the Positive No-Check Result'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: 'ac3e37feac78b0683895ad1903e50e83f5e8a2fb'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** A positive excavation-rule series already reaches `no_check`, but its supporting frame IDs are not identified as result evidence, and the UI and deterministic fixture do not establish the complete positive outcome contract.

**Approach:** Preserve the existing normalized rule decision and terminal projection transaction. Bind positive supporting frames to the projection, verify the source-backed persisted result and zero human-check requests, and render the bounded result clearly.

## Boundaries & Constraints

**Always:** Require at least three usable ordered frames in one declared area and period, an excavator detection, and a dump-truck detection. Use normalized states and the bound rule revision. Persist one `no_check` projection with frame observations and the upload-ordered union of usable frames detecting either required class as supporting IDs, and no recommendation. State only that no check was requested for this evidence; keep uncertainty visible. Keep the deterministic development fixture separate from held-out evaluation.

**Never:** Infer whole-stage health, legal compliance, or site-wide presence from these frames. Use provider-native detail to decide the rule. Rewrite historical run bindings or implement the separate persistent non-detection check-request story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Positive series | Three usable ordered frames; excavator and dump truck each detected at least once | One succeeded `no_check` projection with positive supporting IDs, bound revision, observations, no recommendation | No error expected |
| Inadequate evidence | Fewer than three usable frames or no excavator detection | Existing `insufficient_data` result; no positive supporting IDs | Technical failure remains failed with no projection |

</intent-contract>

## Code Map

- `backend/app/domain/rule.py:44-68` -- normalized evaluator already selects `no_check`; its `supporting_input_ids` currently includes only check requests. Preserve outcome precedence and use ordered usable IDs to identify positive evidence.
- `backend/app/adapters/postgres.py:693-759` -- completion builds source-bound frame observations and ordered series evidence, merges the bound rule decision, and commits one projection with succeeded state in a transaction.
- `backend/app/adapters/postgres.py:782-827` -- readback returns bound rule and projection only for succeeded runs.
- `backend/tests/test_rule_intent.py:68-99,191-241` -- normalized-state tests and deterministic mocked-observer integration already exercise `no_check`; extend positive assertions and fixture provenance.
- `web/src/App.tsx:91-102` and `web/src/App.test.tsx:87-105` -- result surface uses server outcome and bound rule, but has no positive-result assertion.
- `backend/admission/exclusions/held_out_evaluation.json` and `evaluation/README.md` -- held-out fixtures are separate and currently unassigned; do not use them for the development contract.
- `_bmad-output/implementation-artifacts/sprint-status.yaml:28` -- synchronize Story 2.3 with workflow state.

## Tasks & Acceptance

**Execution:**
- `backend/app/domain/rule.py` -- add ordered positive supporting frame IDs to `no_check` while retaining its existing decision guards and absence of a recommendation.
- `backend/tests/fixtures/positive_no_check.json` and `backend/tests/test_rule_intent.py` -- add a labeled synthetic development fixture of normalized observations, assert its separation from held-out inventory, `no_check`, zero check requests, supporting frames, and persisted bound-revision/source evidence.
- `web/src/App.test.tsx` -- assert the succeeded positive result displays the bounded `no_check` explanation, frame observations, and bound rule revision without whole-stage-health language.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- move only Story 2.3 through `in-progress` to `done` after verification.

**Acceptance Criteria:**
- Given at least three usable ordered images from the same declared area and period with an excavator and dump truck detected, when the bound rule completes, then the succeeded ResultProjection is `no_check` with supporting frame observations and the applied rule revision, and the result does not claim the whole stage is healthy.
- Given the development positive fixture of normalized observations, when its deterministic contract test runs, then `no_check` and zero check requests are asserted and its source group is absent from the held-out evaluation inventory.
- Given a completed positive rule run, when its result is displayed, then the user sees that a check was not requested for the observed evidence and can inspect the supporting frames and rule revision.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 10 findings — high 0, medium 2, low 0, false 8, maybe-false 0
- findings:
  - `[false]` `[reject]` One unassessable frame overrides three usable positive frames — the immutable policy explicitly makes observer inability `insufficient_data`; `evaluate_rule` checks it before the positive decision, preserving the prior Story 2.2 contract.
  - `[medium]` `[patch]` Positive UI mock used two usable frames — changed the mock to three ordered usable inputs with matching observations and series summary; the test now asserts the count.
  - `[false]` `[reject]` Fixture omits an explicit zero-check count — the only check-request effect is the `check_requested` outcome with recommendation, while the fixture asserts `no_check` and no recommendation; persisted readback additionally asserts one `no_check` projection and zero `check_requested` projections.
  - `[false]` `[reject]` Zero `check_requested` rows are tautological — the one-projection constraint is exactly the persistence invariant, and there is no separate check-request table or side effect to count.
  - `[false]` `[reject]` Fixture and integration scenario are separate — the fixture verifies the normalized evaluator and the integration test independently verifies a matching positive state pattern through persistence and source readback; both tests passed.
  - `[false]` `[reject]` Supporting IDs are not linked to frame cards — every frame card displays its input ID and observation, allowing the displayed supporting IDs to identify those cards.
  - `[medium]` `[patch]` Positive UI mock retained the no-dump-truck series text — same mock defect as the two-frame finding; cleared persistence text and IDs and asserted the contradictory text is absent.
  - `[false]` `[reject]` The fixture alone does not count check requests — the normalized outcome and absent recommendation establish no request at the evaluator boundary; the persisted run asserts zero `check_requested` projections.
  - `[false]` `[reject]` The UI test uses a stubbed API response rather than a live browser — the PostgreSQL/S3 integration test covers authoritative completion and readback, and the UI test covers rendering that response; GUI use is prohibited by the project working agreement.
  - `[false]` `[reject]` Sprint status is only `in-progress` in the review diff — that is the required review-phase state; it is synchronized to `done` after verification and review.

## Auto Run Result

Status: done

Implemented ordered positive supporting input IDs for `no_check`, a synthetic development acceptance fixture, persisted projection and provenance assertions, and a bounded positive result display.

Files changed:
- `backend/app/domain/rule.py` — identify usable frames detecting either required class for the positive result.
- `backend/tests/fixtures/positive_no_check.json` — declare normalized synthetic positive evidence outside the held-out inventory.
- `backend/tests/test_rule_intent.py` — assert normalized and persisted positive outcomes, source references, bound revisions, and no check request.
- `web/src/App.tsx` — display positive supporting input IDs beside the bound rule.
- `web/src/App.test.tsx` — verify the user-facing positive result with a consistent three-frame response.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — mark Story 2.3 done after verification.
- This specification — record the implementation, review, and checks.

Review: one medium patch entry covering two findings; zero deferred; eight rejected findings with reasons above. Follow-up review is not recommended because one medium entry was patched and the focused regressions passed.

Verification: `17 passed` in `backend/tests/test_rule_intent.py` against isolated PostgreSQL and MinIO; existing ordered-series failure test `1 passed`; web tests `38 passed`; web production build passed; `git diff --check` passed.

Residual risk: a rendered browser session was not checked because GUI use is prohibited. No deployment or application-database migration was performed for this story.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py` -- expected: normalized contract and persisted positive run pass against isolated PostgreSQL/S3.
- `cd web && npm test -- --run` -- expected: positive result and existing UI behavior pass.
- `cd web && npm run build` -- expected: production TypeScript build succeeds.

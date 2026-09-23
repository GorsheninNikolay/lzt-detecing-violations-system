---
title: 'Request a Check Only for Persistent Non-Detection'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '776b0aa12f344b3fe9ecfdc24765c4776f7bce65'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The normalized evaluator already chooses `check_requested` for persistent dump-truck non-detection, but the negative development contract and the complete persisted, user-visible check request are not established.

**Approach:** Preserve the existing decision and single terminal projection. Verify it through a separate negative development fixture and persisted run, then present its source-bound evidence and human-verification boundary in a named check-request panel.

## Boundaries & Constraints

**Always:** A check requires at least three usable upload-ordered images in one declared area, an excavator detection in at least one, and `dump_truck == not_detected_in_frame` in every usable image. Persist exactly one projection with ordered supporting frame IDs and observations, period, expectation, immutable rule revision and demonstration provenance, uncertainty, reason, and recommended human verification. Nonqualifying series produce no check; technical errors and timeouts fail without a projection. The Russian panel must say `Это рекомендация для проверки, а не подтверждение нарушения.`

**Never:** Infer site-wide absence, legal or contractual violation, or stage health; take management action; use provider-native counts or confidence for eligibility; tune against held-out evaluation evidence. Do not add a separate check-request record or workflow.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Persistent non-detection | Three usable same-area frames, excavator detected in one, dump truck not detected in all | One `check_requested` projection with ordered supporting frames and a human recommendation | No error expected |
| Nonqualifying series | One or two usable frames, observer inability, no excavator, or any other dump-truck state | `insufficient_data`, `not_analyzed`, or `no_check` as applicable; no check recommendation | Technical failure remains failed with no projection |

</intent-contract>

## Code Map

- `backend/app/domain/rule.py:44-74` -- normalized check eligibility, precedence, ordered supporting IDs, bound rule/context and uncertainty already exist. Retain them; strengthen only if contract tests expose a gap.
- `backend/app/application/submission.py:44-85` and `backend/app/adapters/postgres.py:500-551` -- one explicit observation area is bound to the series and copied to each ordered input; no supported per-frame area override exists.
- `backend/app/adapters/postgres.py:700-756,784-827` -- terminal transaction assembles source-bound frames and series evidence, inserts one projection, and returns it with bound rule and context. Preserve failed-run absence of a projection.
- `backend/tests/test_rule_intent.py:68-112,156-278` -- normalized and PostgreSQL/S3 run tests already exercise the negative outcome, but lack a dedicated negative fixture and full persisted evidence assertions.
- `backend/tests/test_ordered_series.py:540-672` -- timeout tests already verify failed state and no projection; reuse as regression evidence.
- `backend/admission/exclusions/held_out_evaluation.json` -- development fixture source group must be disjoint from this inventory.
- `web/src/App.tsx:91-102`, `web/src/App.test.tsx:87-105`, `web/src/styles.css:8-11` -- result already shows rule and recommendation; make check-request evidence a named panel and assert its rendered contract.
- `_bmad-output/implementation-artifacts/sprint-status.yaml:29` -- synchronize Story 2.4 with actual workflow state.

## Tasks & Acceptance

**Execution:**
- `backend/tests/fixtures/persistent_non_detection.json` and `backend/tests/test_rule_intent.py` -- add a labeled synthetic negative development fixture and assert exact normalized eligibility and disjoint held-out provenance.
- `backend/tests/test_rule_intent.py` -- assert one persisted `check_requested` projection with source-bound ordered supporting frames, context period, rule revision/provenance/expectation, reason, uncertainty, and human recommendation; verify disqualifying normalized states and same-area input binding.
- `web/src/App.tsx`, `web/src/App.test.tsx`, and `web/src/styles.css` -- render and test a named Russian check-request panel with supporting frame IDs, uncertainty, recommendation, and the required non-violation sentence; use only server-projected fields.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- move only Story 2.4 through `in-progress` to `done` after verification.

**Acceptance Criteria:**
- Given at least three usable upload-ordered images from one declared area with an excavator detected in at least one and dump truck `not_detected_in_frame` in every usable image, when the bound rule run succeeds, then exactly one source-backed `check_requested` projection includes its supporting frames, period, expectation, immutable rule revision and provenance, uncertainty, reason, and recommended human check.
- Given one or two usable frames, observer inability, missing excavator evidence, or a dump-truck state other than `not_detected_in_frame`, when rule evaluation completes, then no haulage-delay check is produced and the backend explains the applicable outcome; given a technical failure or timeout, when the run ends, then it is failed with no projection.
- Given a completed `check_requested` run, when its Russian result is rendered, then the named panel shows the supporting evidence and `Это рекомендация для проверки, а не подтверждение нарушения.` without asserting a legal or contractual violation or initiating an action.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 7 findings — high 0, medium 2, low 0, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` Per-frame area metadata could yield a mixed-area check — the supported submission contract accepts one explicit observation area for the whole series and copies it to every immutable input; no per-frame area field is accepted as evidence. The UI labels the area as user-declared and unverified from pixels.
  - `[medium]` `[patch]` Check text omitted the possible haulage-delay concern — changed the projected reason to name a *possible* delay and assert that bounded wording in backend and UI tests.
  - `[medium]` `[patch]` Persisted negative test detected an excavator in every frame — changed the mocked observer to detect one only in the first frame and asserted the resulting series support and frame states.
  - `[false]` `[reject]` Exactly-three-frame tests miss a four-frame rule branch — `evaluate_rule` uses a minimum threshold and iterates every usable input without an exact-three branch; the proposed fourth frame exercises the same path.
  - `[false]` `[reject]` Observation-only timeout tests leave rule failures unguarded — `ClaimLoop._execute` handles timeouts before rule evaluation and calls the same `fail_ordinary` path for both intents; the existing timeout tests assert failure and no projection.
  - `[false]` `[reject]` Store-level readback can diverge from the HTTP check response — `GET /runs/{run_id}` returns `read_ordinary` through `JSONResponse` with no other projection transformation; the integration test verifies the complete persisted payload and the web test verifies its rendering.
  - `[false]` `[reject]` Intent-alignment audit identified an untested image-to-observation or physical-area inference — Story 2.4's rule consumes normalized observations and explicit declared context; observer admission was established in Epic 1, and runnable demonstration images belong to Story 2.6. The UI explicitly states that the declared area is not verified from images.

## Auto Run Result

Status: done

Implemented the persistent non-detection development fixture, verified one source-bound persisted check request with only one excavator detection, and rendered the check evidence in a named Russian panel. The projected reason now identifies a possible soil-haulage delay without claiming a proven violation.

Files changed:
- `backend/app/domain/rule.py` — describe the bounded possible-delay concern in the check reason.
- `backend/tests/fixtures/persistent_non_detection.json` — add synthetic negative normalized evidence outside the held-out inventory.
- `backend/tests/test_rule_intent.py` — assert eligibility, one persisted projection, ordered supporting evidence, immutable rule context, and one-frame excavator support.
- `web/src/App.tsx` and `web/src/styles.css` — display a named check-request panel with evidence, provenance, uncertainty, recommendation, and the safety sentence.
- `web/src/App.test.tsx` — verify the complete user-visible check request using a consistent three-frame response.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — mark Story 2.4 done after verification.
- This specification — record the implementation, review, and verification result.

Review: two medium patch entries fixed; no deferrals; five findings rejected with specific reasons in the Review Triage Log. Follow-up review is recommended by the two-medium-patch threshold. Specific unverified risk: the panel was not visually checked in a real browser at narrow widths because project instructions prohibit GUI use; its content and build passed CLI checks.

Verification: backend `25 passed` in `tests/test_rule_intent.py` and `tests/test_ordered_series.py` against isolated PostgreSQL and MinIO; web `38 passed`; web production build passed; `git diff --check` passed. No deployment or application-database migration was performed for this story.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py tests/test_ordered_series.py` -- expected: normalized and persisted negative contracts plus timeout regressions pass against isolated PostgreSQL/S3.
- `cd web && npm test -- --run` -- expected: check-request panel and existing result behavior pass.
- `cd web && npm run build` -- expected: production TypeScript build succeeds.

---
title: 'Cover Insufficient and Out-of-Scope Journeys'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '64d23e2618a56ee399ec2432924b35c01aad5879'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
deferred:
  - summary: >-
      The phrase "unsupported work" may require a not_analyzed result for a stage without a configured rule.
    evidence: |-
      Story 2.7 permits this reading, while the approved UX disables rule evaluation for that stage and selects observation-only; AD-35 keeps observation-only as its own top-level outcome. A product decision that a successful run on the unconfigured stage must report not_analyzed would settle the interpretation. The current change covers successful unsupported requested classes.
    location: >-
      _bmad-output/planning-artifacts/epics.md:780; web/src/App.tsx:138; backend/app/application/submission.py:48
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Users need clear, evidence-linked outcomes when a run cannot assess its evidence or the requested work is outside the rule's scope. They must not read withheld analysis as a healthy-stage result.

**Approach:** Keep successful outcomes backend-projected, explain insufficiency and non-applicability with the affected inputs, and preserve the ordered source history.

## Boundaries & Constraints

**Always:** A rule-evaluation run with fewer than three usable same-area frames or unassessable required evidence succeeds as `insufficient_data`, identifies the limiting series condition or input frames, and has no check request. Observation-only runs retain `observations_only`; affected class rows may say `insufficient_data`. An unsupported requested class has a `not_analyzed` row with reason and input reference; rule evaluation with an unsupported requested class projects `not_analyzed` and no check request. A stage without a configured rule keeps rule evaluation unavailable and can run observation-only. Development acceptance fixtures are distinct from held-out evaluation.

**Never:** Infer a rule result from provider-native metadata, turn in-frame non-detection into site-wide absence, present `no_check` as proof of a healthy stage, or describe a human check recommendation as a confirmed violation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Short rule series | Two accepted images in one rule-evaluation series | Successful `insufficient_data`, series-limit reason, no Check-request Panel, ordered inputs retained | Technical failure remains a failed run with no result projection |
| Unassessable evidence | Accepted image cannot be assessed | Rule-evaluation intent projects `insufficient_data`; observation-only intent keeps `observations_only` and marks affected class rows | Preserve source frame and reason |
| Unsupported work or class | Stage has no rule, or the request includes an unsupported class | Rule selection explains the unavailable stage; an accepted observation run remains `observations_only`. An unsupported class keeps a `not_analyzed` row with its source, and a rule run that requested it projects `not_analyzed` without a check request | Never label that class as detected or absent |
| Acceptance outcomes | Development fixtures cover the five closed outcomes | Assert `observations_only`, `no_check`, `check_requested`, `insufficient_data`, and `not_analyzed`, with fixture provenance and held-out exclusion | Keep fixture provenance separate from held-out evaluation |

</intent-contract>

## Code Map

- `backend/app/domain/rule.py:44-75` -- evaluates series sufficiency and rule outcomes; name unassessable input frames and treat a requested unsupported class as a non-applicable rule input before check/no-check branches.
- `backend/app/application/submission.py:34-58` -- validates run intent and rejects rule evaluation when the selected stage is not `excavation`.
- `backend/app/application/executor.py:143-188` -- accepted unassessable frames complete with per-class `frame_unassessable`; technical observer failure remains a failed run.
- `backend/app/domain/observations.py:85-94` -- maps unsupported requested classes to `not_analyzed` and attaches the source artifact ID.
- `backend/app/adapters/postgres.py:638-750` -- builds the terminal projection from persisted observations and input references, preserves order, and keeps observation-only intent distinct from rule evaluation.
- `web/src/App.tsx:138-215` -- renders backend outcome, frame rows, input IDs, series order, rule reason, and a Check-request Panel only for `check_requested`; use the exact `Не анализировалось` outcome label.
- `web/src/App.test.tsx` -- covers successful check/no-check results; unsupported and insufficient rows currently appear only in a failed partial-run case.
- `backend/tests/test_rule_intent.py:109-128,300-388` -- covers domain outcomes and persisted one/two-image rule series; `backend/tests/test_ordered_series.py:406-425` and `backend/tests/test_single_image.py:286-296` cover unassessable observation-only rows.
- `backend/tests/fixtures/positive_no_check.json`, `backend/tests/fixtures/persistent_non_detection.json`, `backend/admission/exclusions/development_acceptance.json`, and `web/src/demoCases.json` -- existing development provenance and exclusions; extend outcome coverage without using held-out evidence.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- advance Story 2.7 through `in-progress`, `review`, and `done` at the corresponding verified gates, preserving other statuses.

## Tasks & Acceptance

**Execution:**
- `backend/app/domain/rule.py` -- identify unassessable frame IDs in the rule reason and withhold checks when any requested class is `not_analyzed`; preserve the existing minimum-series and intent precedence.
- `backend/tests/test_rule_intent.py` and `backend/tests/fixtures/development_outcomes.json` -- exercise the five distinct outcomes, source groups, and held-out exclusion; verify successful persisted short, unassessable, and unsupported-class runs with ordered source references.
- `web/src/App.tsx` and `web/src/App.test.tsx` -- render successful `insufficient_data` and `not_analyzed` projections, class reasons, ordered history, and absent Check-request Panel; use the exact Russian out-of-scope outcome label.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- record Story 2.7 at each verified implementation/review/completion gate using the existing sprint tool.

**Acceptance Criteria:**
- Given a two-image rule-evaluation series, when its ordinary run succeeds, then Run Workspace shows `Недостаточно данных`, the minimum-series reason, both ordered historical inputs, and no Check-request Panel.
- Given accepted but unassessable evidence, when a rule-evaluation run succeeds, then Run Workspace names the limiting frame and shows `Недостаточно данных` without a Check-request Panel; when observation-only succeeds, it keeps `Только наблюдения` and marks the affected class row `Недостаточно данных` with its input reference.
- Given a requested class outside the MVP scope, when an ordinary run succeeds, then its class row says `Не анализировалось` with a scope reason and input reference; if the run requested rule evaluation, its outcome is `Не анализировалось` with no Check-request Panel or unsupported detection claim.
- Given a stage without a configured rule, when New Analysis is opened, then rule evaluation is unavailable with its existing explanation and observation-only remains available.
- Given the development acceptance fixture suite, when it runs, then `observations_only`, `no_check`, `check_requested`, `insufficient_data`, and `not_analyzed` are asserted as distinct outcomes and fixture source groups remain separate from the held-out evaluation set.

## Working Agreements

Use CLI, skills, and APIs only; never open or control GUI applications. Preserve unrelated work and the active branch. Keep code self-explanatory, and comment only non-obvious algorithms, invariants, concurrency assumptions, or linked workarounds.

## Spec Change Log

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 3 findings — high 0, medium 0, low 0, false 2, maybe-false 1
- findings:
  - `[maybe-false]` `[defer]` The intent may require a successful `not_analyzed` outcome for the unconfigured `other` stage — the approved selector disables rule evaluation there, the API rejects that rule request, and AD-35 gives an observation-only run `observations_only`; a product decision on whether Story 2.7 changes that contract would settle the claim (medium if true).
  - `[false]` `[reject]` Accepted unassessable observation-only evidence does not need a top-level `insufficient_data` outcome — AD-35 and the approved UX require `observations_only` with class-level insufficiency; persisted backend and successful UI tests cover that behavior, while rule evaluation projects `insufficient_data`.
  - `[false]` `[reject]` The five outcomes are exercised by persisted ordinary runs in `backend/tests/test_rule_intent.py` and successful UI projections in `web/src/App.test.tsx`; the development manifest separately records synthetic provenance and checks source groups against the held-out inventory. One combined browser fixture runner is not required by the story.

## Design Notes

The approved architecture and UX distinguish the top-level result by intent: rule evaluation can return `insufficient_data`, while observation-only remains `observations_only` even when all class rows are insufficient. They also say a stage without an applicable rule disables rule evaluation and selects observation-only. This plan applies the story's out-of-scope result to unsupported requested classes. A configured rule does not issue a check from a request that contains an unsupported class; supported frame facts remain visible and the unsupported row carries its own reason.

For combined inputs, AD-35's precedence is applicability, then sufficiency, then check. An unsupported requested class therefore yields `not_analyzed` even when the same series is short or another class is unassessable.

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_rule_intent.py` -- expected: five outcomes and persisted input/evidence contracts pass against isolated PostgreSQL/S3.
- `cd web && npm test -- --run && npm run build` -- expected: successful insufficient/out-of-scope rendering and production build pass.
- `UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run .agents/skills/bmad-sprint-planning/scripts/sprint_plan.py validate --status-file _bmad-output/implementation-artifacts/sprint-status.yaml` -- expected: valid canonical story statuses.
- `git diff --check` -- expected: no whitespace errors.

## Auto Run Result

Earlier attempt: `blocked` for intent gap. On continuation, the approved architecture and UX resolve intent-specific insufficiency and the no-rule stage behavior; the story's `not_analyzed` journey is scoped to unsupported requested classes.

Tooling: `ruamel.yaml` was downloaded into the isolated uv cache. The official sprint validator returned `valid=true`, with no problems or legacy statuses. Story 2.7 advanced to `in-progress` through the sprint generator and was read back from the canonical ledger.

Implemented: rule projection names unassessable input IDs and withholds check requests when any requested class is `not_analyzed`, including short series. Successful Run Workspace results use the exact Russian insufficiency and out-of-scope labels, retain source/order evidence, and show no Check-request Panel for those outcomes. A development fixture manifest records all five outcomes and synthetic source groups separate from held-out evaluation.

Files changed:
- `backend/app/domain/rule.py` — applicability-first outcome precedence and source-linked reasons.
- `backend/tests/test_rule_intent.py` and `backend/tests/fixtures/development_outcomes.json` — domain, persisted-run, and provenance coverage.
- `web/src/App.tsx` and `web/src/App.test.tsx` — exact outcome labels and successful-result coverage.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` and this spec — verified story progress and review record.

Review: Blind Hunter was skipped because only three reviewer slots were available. Edge Case Hunter and Verification Gap Reviewer found no issues. Intent Alignment Auditor reported three descriptive divergences: two were rejected with evidence and one medium-if-true interpretation was deferred. Patched entries: high 0, medium 0, low 0; follow-up review recommended: false.

Verification: `backend/tests/test_rule_intent.py` passed 24/24 against isolated PostgreSQL/S3; the existing ordered-series failure test passed 1/1 and confirmed technical failure leaves no ResultProjection. Web tests passed 52/52 and production build passed. The official sprint validator returned `valid=true`; staged and working-tree diff checks passed. No GUI was opened, so the rendered browser journey remains unverified.

Residual risk: whether Story 2.7's “unsupported work” includes a successful run on an unconfigured stage remains a product interpretation. The currently approved UI disables that rule choice and offers observation-only instead.

Tracking: Story 2.7 and Epic 2 are `done`; `epic-2-retrospective` remains `optional`. The canonical sprint file passed official validation and status readback with no risks or illegal entries.

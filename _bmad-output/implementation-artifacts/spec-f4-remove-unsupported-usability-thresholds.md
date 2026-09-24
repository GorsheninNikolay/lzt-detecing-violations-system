---
title: 'Remove Unsupported Frame Usability Thresholds'
type: 'bugfix'
created: '2026-09-24'
baseline_revision: '0744bfd9d70e5e1ffdb9c1c8d412e5792a97ff64'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred:
  - summary: >-
      The current Grounding DINO adapter does not emit observer-reported `insufficient_data` for a decoded image.
    evidence: |-
      `GroundingDinoCpu.observe` currently maps every successful inference to `detected` or `not_detected_in_frame`; the insufficiency path is covered with a stub. A model-specific, evidence-backed inability signal is not established, and adding another image-quality cutoff would contradict the selected policy.
    location: >-
      backend/app/profiles/grounding_dino.py:133-140
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The executor classifies decoded images as unusable using hard-coded minimum dimensions and per-channel pixel-range thresholds. These decisions are absent from the immutable applied policy and contradict its supported-decoded-image contract.

**Approach:** Remove pixel-dimension and pixel-range gates while retaining verified artifact reads and actual image decoding. Let the bound observer's normalized response determine whether it can assess an accepted image; keep the complete existing policy snapshot as the recorded authority.

## Boundaries & Constraints

**Always:** Preserve the per-frame usability stage and ordered-series preflight, artifact integrity checks, supported-class behavior, observer normalization, and batch deadline. A supported JPEG that decodes successfully reaches the observer. Persisted rule runs continue to carry the complete immutable policy snapshot, including explicit null subjective thresholds.

**Never:** Add replacement numeric image-quality thresholds, change the canonical policy, infer observer inability from dimensions or pixel extrema, alter historical snapshots, or change other retrospective action items.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Decodable image below the old cutoffs | Supported JPEG with a dimension below 64 pixels or every RGB channel range below 5 | Frame passes usability preflight and the observer receives the original verified bytes; persisted outcome follows its normalized response | Observer errors remain technical failures |
| Observer cannot assess an accepted image | Observer returns normalized `insufficient_data` | Preserve `frame_unassessable`; rule evaluation yields `insufficient_data` without a check request | Do not substitute a pixel heuristic |

</intent-contract>

## Code Map

- `backend/app/application/executor.py:71-77,145-164` -- `_unassessable` applies the hidden thresholds; `_execute` uses it during the all-frame preflight and to skip observer reservation. Replace the threshold decision with a decode-only check and let supported requests reach `reserve_ordinary`.
- `backend/app/profiles/grounding_dino.py:108-151` -- the bound observer decodes the image and emits normalized detection states; preserve its result as the source of assessment.
- `backend/app/domain/observations.py:71-95` -- `closed_observations` preserves normalized observer states and maps `insufficient_data` to `frame_unassessable`.
- `backend/app/domain/rule.py:16-37` -- `RULE_POLICY` is content-revisioned and already records supported decodable images and null quality thresholds; `evaluate_rule` maps observer inability to `insufficient_data`.
- `backend/app/adapters/postgres.py:515-560,709-755,780-814` and `backend/migrations/versions/0006_immutable_run_configuration.py:25-120` -- persist, project, read back, and constrain the complete immutable policy snapshot. No schema change is expected.
- `backend/tests/test_ordered_series.py:295-360,390-435` -- covers F5 preflight progress and currently expects black frames to bypass observation; retain the progress assertion and update obsolete heuristic expectations.
- `backend/tests/test_rule_intent.py:305-375,425-438` -- currently simulates threshold-based unassessable frames; retain coverage by simulating an observer `insufficient_data` response and asserting its invocation/evidence.
- `backend/tests/test_single_image.py:209-302` -- covers the single-image observer path and currently expects a black image to bypass it; assert the same verified bytes and invocation hash reach the observer.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md:31-34,95-110` and `_bmad-output/implementation-artifacts/sprint-status.yaml:73-79` -- source of F4 and its open tracking item; update only that action after verified completion.
- `_bmad-output/specs/spec-construction-monitoring-concepts/prototype-scenarios.md:28-44` and `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:71-76,288-292` -- canonical frame-usability behavior and rule against unsupported numeric gates.

## Tasks & Acceptance

**Execution:**
- [x] `backend/app/application/executor.py` -- replace `_unassessable` with a decode-only preflight and remove the Boolean threshold gate from observer reservation -- preserve F5 stage ordering while applying the canonical policy.
- [x] `backend/tests/test_ordered_series.py`, `backend/tests/test_rule_intent.py`, and `backend/tests/test_single_image.py` -- update existing regression coverage for below-cutoff decoded images, observer-reported inability, and intermediate series-stage progress -- prevent the old heuristic from returning unnoticed.
- [x] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark only `epic-1-retro-version-usability-policy` done after implementation verification -- keep action tracking evidence-backed.
- [x] `_bmad-output/implementation-artifacts/spec-f4-remove-unsupported-usability-thresholds.md` -- record review and verification results -- leave the audit trail for F4.

**Acceptance Criteria:**
- Given a supported JPEG that decodes and falls below either previous numeric cutoff, when a supported analysis runs, then frame preflight succeeds and an ordinary observer invocation records the original image hash and normalized result.
- Given the observer returns `insufficient_data` for a decoded image, when observations and the result projection are persisted, then the frame retains `frame_unassessable`, rule evaluation reports `insufficient_data`, and no check request is created.
- Given a rule-evaluation run is created and read back, when its policy is inspected, then the complete content-revisioned snapshot is unchanged and declares no numeric image-quality, resolution, or visibility threshold.

## Spec Change Log

## Review Triage Log

- `medium / patch` -- `backend/tests/test_single_image.py`: the black-frame case expected heuristic `insufficient_data` although its observer stub reports a detection. Updated the expectation and asserted that the original bytes and matching invocation hash reach the observer.
- `medium / patch` -- `backend/app/adapters/postgres.py`: completed invocations with persisted `insufficient_data` were included in `series.usable_input_ids` and `usable_count`. Excluded those inputs and added a regression assertion that observer-unassessable frames do not count as usable.
- Preliminary implementation review (before the formal review pass): Edge Case Hunter and Verification Gap reviewers ran; Blind Hunter was skipped because only two reviewer slots were available. The formal pass below ran all four review layers.

### 2026-09-24 -- Review pass
- verdicts: 7 findings -- high 0, medium 0, low 5, false 1, maybe-false 1
- findings:
  - `[low]` `[patch]` Invocation helper did not require one completed, hash-matching invocation per input -- assert exact row count against the expected input count.
  - `[low]` `[patch]` Single-image observer stub could substitute a captured image when called without image bytes -- require the image argument and forward arguments through local response wrappers.
  - `[false]` `[reject]` Boundary-image regression suite used a stub observer -- a direct call to the pinned `GroundingDinoCpu` processed the 32x48 and uniform 96x96 JPEGs and returned normalized states; this does not assert model accuracy.
  - `[maybe-false]` `[defer]` Current `GroundingDinoCpu` emits only `detected` or `not_detected_in_frame`, so its production path cannot emit observer-reported `insufficient_data` -- the downstream path is covered by a stub, while evidence for a model-specific inability signal is absent; settle with an evidence-backed observer signal that does not reintroduce subjective image-quality thresholds.
  - `[low]` `[patch]` Observer inability was tested only when both classes were insufficient -- add a mixed-class case and assert frame-level usability and rule outcome.
  - `[low]` `[patch]` Verification command omitted the isolated PostgreSQL/MinIO environment -- point to the README setup and record the passing configured run.
  - `[low]` `[patch]` F4 action and execution checklist remained open after service-backed verification -- mark only the verified F4 tracking items done.

## Verification

**Commands:**
- Configure the isolated database and bucket using `README.md:29-40`, then run the command below from the project root.
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py tests/test_ordered_series.py tests/test_single_image.py::test_http_submission_and_guarded_execution --tb=short` -- expected: all targeted policy, observer, and ordered-stage regressions pass.
- `git diff --check` -- expected: no whitespace errors.

**Results:**
- Initial attempt without `TEST_DATABASE_URL`: 26 passed and 4 fixture setup errors. After confirming the isolated `evidence_test` database was at migration `0006_immutable_run_configuration`, the final post-review run used the README PostgreSQL/MinIO configuration: 31 passed in 5.73s.
- Matrix row 1 is covered by the small and uniform JPEG observer-invocation assertions in all three changed regression files; matrix row 2, including the mixed-class case, is covered by observer-reported `insufficient_data` projection assertions in `test_rule_intent.py`. All covering integration tests ran and passed.
- The pinned `GroundingDinoCpu` adapter processed generated 32x48 and uniform 96x96 JPEGs and returned normalized states for both. This smoke establishes input handling, not model accuracy.
- `python3 -m py_compile` for all six changed Python files and `git diff --check`: passed.

## Auto Run Result

Status: done

Implemented F4 by removing the unsupported dimension and pixel-range gates. Decodable images reach the bound observer, while observer-reported `insufficient_data` is retained and excluded from usable series evidence. Existing complete immutable policy snapshots remain unchanged.

Files changed:
- `backend/app/application/executor.py` -- replace subjective usability heuristics with decode-only preflight.
- `backend/app/domain/observations.py` -- accept observer-reported `insufficient_data`.
- `backend/app/adapters/postgres.py` -- exclude observer-unassessable frames from usable series evidence.
- `backend/tests/test_ordered_series.py`, `backend/tests/test_rule_intent.py`, and `backend/tests/test_single_image.py` -- cover cutoff images, observer inability, and invocation provenance.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- close only the verified F4 action.
- This specification -- record scope, review triage, and verification.

Review findings: 5 low findings patched; 1 maybe-false medium finding deferred; 1 false finding rejected. The bound-observer coverage concern was settled by the pinned-model smoke above. The deferred item records that the current Grounding DINO adapter does not emit observer-reported inability; no evidence-backed threshold was introduced. Edge Case Hunter and Verification Gap Reviewer found no additional items. Intent alignment found no divergence from the canonical policy.

Follow-up review recommendation: false. Patched counts: high 0, medium 0, low 5. No high or medium patch remains.

Verification: targeted backend run passed 31 tests after review patches; `py_compile` and `git diff --check` passed. A direct pinned-model smoke processed the two boundary JPEGs. No model-accuracy, deployment, or rendered-browser claim is made.

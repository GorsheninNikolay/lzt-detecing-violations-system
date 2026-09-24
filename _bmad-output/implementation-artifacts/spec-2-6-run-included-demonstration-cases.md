---
title: 'Run Included Demonstration Cases'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: 'fa17fdf32a65faf6baf380e3d1257614f1b9ebad'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      A rolling rule deployment could change the revision after the demo reads analysis choices.
    evidence: |-
      The choice endpoint and submission bind static in-process rule data, but the deployment envelope is not defined. A rolling revision change between choice loading and submission would settle whether the selected case can bind a different revision. Story 2.1 recorded the same unverified race.
    location: >-
      web/src/App.tsx:550; backend/app/adapters/postgres.py:536
    severity: medium (unverified)
  - summary: >-
      The complete demo journey has not been observed in a rendered browser.
    evidence: |-
      UI tests verify editable selection and the ordinary request with mocked fetch; two real pinned-observer canaries verified PostgreSQL/S3 projections and source bytes, but did not execute the browser. The working agreement forbids controlling GUI applications. A permitted browser run would settle layout and full client-to-service behavior.
    location: >-
      web/src/App.tsx:547; web/src/App.test.tsx:439
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A jury member cannot load the included positive and check-request examples into New Analysis. Existing development fixtures contain normalized states but no ordinary image inputs.

**Approach:** Bundle two small JPEG series derived from the organizer archive and let a selector populate the existing editable form. Submission, publication, observation, rule evaluation, and result inspection use the same path as manually chosen images.

## Boundaries & Constraints

**Always:** The positive case uses archive frames 87, 89, 90; the negative case uses 23, 25, 26. Both are three usable frames from one visually identified site per case in archive order. The pinned Grounding DINO Tiny adapter on quality-90 JPEGs returned `no_check`-qualifying observations for the positive case and `check_requested`-qualifying observations for the negative case. Preserve source member names, original and derived checksums, development source groups `organizer-archive-site-85-94` and `organizer-archive-site-22-26`, and held-out exclusion. Populate excavation, rule intent, scenario, declared area, an editable period, and ordered files; show the current rule revision before submission. Positive frames 89/90 and all negative frames display dates; frame 87 has no date mark. The prefilled clock time is illustrative and must be labeled as such. Keep loading failure atomic and preserve pending-submission recovery.

**Never:** Feed recorded fixture states into a user run, bypass the admitted observer or ordinary submission endpoint, infer rule applicability from an image, represent demo cases as held-out readiness evidence, assert an exact capture time or site-wide absence, or claim a violation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Positive example | Jury member selects the truck case | Form shows three ordered editable JPEGs, explicit context and live rule revision; normal submission produces `no_check` with source evidence | A failed asset load leaves the prior form unchanged |
| Negative example | Jury member selects the persistent non-detection case | Normal submission produces `check_requested`, source evidence and human-check wording | A changed or unavailable rule prevents misleading fixture selection |
| Existing work | User has edited fields or has an uncertain pending request | Selection replaces an editable draft atomically; pending request remains locked to its exact stored body | No partial replacement or new idempotency key during pending recovery |

</intent-contract>

## Code Map

- `artifacts/dataset/Строительная_техника.zip` -- read-only organizer source; frames 87/89/90 carry the positive site and 23/25/26 the negative site; preserve original PNG hashes.
- `backend/app/profiles/grounding_dino.py:14-19,111-140` -- pinned model, prompts, thresholds and image processor; keep read-only. The local pinned snapshot has produced the expected normalized class states on the selected JPEG conversion.
- `backend/app/domain/rule.py:11-75` -- live immutable rule/policy revisions and outcome logic; keep read-only, and match the demo to the current `RULE.revision`.
- `backend/app/application/submission.py:37-85,123-156` and `backend/app/application/executor.py:132-190` -- ordinary JPEG series publication and observation path; reuse without fixture-specific branches.
- `web/public/demo/*.jpg` -- new bundled quality-90 JPEG derivatives; six images only, below the ordinary per-frame size/pixel limits.
- `web/src/demoCases.json` -- new ordered case metadata: source archive/member/group/hash, bundled JPEG path/hash, declared context, expected outcome and bound rule revision. UI must not use expected observations to determine a result.
- `backend/admission/exclusions/development_acceptance.json` -- reserve both visual source groups and hashes outside the held-out set; existing admission and held-out inventories remain read-only.
- `web/src/App.tsx:375-416,535-568,712-755` -- existing editable form, validation queue, pending request and normal series submission; add atomic preset loading without changing `submit` or result computation.
- `web/src/App.test.tsx:430-550` -- test New Analysis case loading, editing, ordinary request bytes/order, load failures and pending safety.
- `backend/tests/test_rule_intent.py:223-300` -- reuse persisted ordinary-run integration and verify demo assets and expected rule outcomes without a new runtime route.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- advance only Story 2.6 through `in-progress`, `review`, and `done` at their verified gates.

## Working Agreements

Use CLI, skills, and APIs only; never launch or control a GUI application. Preserve unrelated work and the active branch. Keep code self-explanatory and comments limited to non-obvious invariants or workarounds.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark Story 2.6 `in-progress` at implementation start, `review` after verification, and `done` only after acceptance.
- [x] `web/public/demo/Screenshot_87.jpg`, `Screenshot_89.jpg`, `Screenshot_90.jpg`, `Screenshot_23.jpg`, `Screenshot_25.jpg`, `Screenshot_26.jpg`, and `web/src/demoCases.json` -- create six quality-90 JPEG derivatives and a checksum/provenance manifest with two ordered cases, the current rule revision and illustrative clock time.
- [x] `backend/admission/exclusions/development_acceptance.json` -- reserve the selected visual source groups and image hashes so these demos cannot be treated as held-out fixtures.
- [x] `web/src/App.tsx` -- load and validate a selected case before atomically replacing the editable form; show demo provenance/time caveat, live rule revision, loading/error state and unchanged ordinary submission behavior.
- [x] `web/src/App.test.tsx` and `backend/tests/test_rule_intent.py` -- cover the matrix with a normal three-image request, editable replacement, loading failure, pending recovery, asset integrity and persisted rule outcome.

**Acceptance Criteria:**
- Given either included case on New Analysis, when a jury member selects it, then the editable form presents its explicit scenario, area, illustrative period, current excavation rule revision and three source-ordered images before the ordinary submit action.
- Given the selected positive case, when the ordinary run succeeds, then its result is `no_check` with the applied rule revision and inspectable source frames, and it is not counted as held-out readiness evidence.
- Given the selected negative case, when the ordinary run succeeds, then its result is `check_requested` with the supporting source frames and an explicit recommendation for human verification rather than a violation finding.
- Given an unavailable fixture asset, mismatched current rule revision or uncertain pending submission, when case selection is attempted, then the existing form or stored pending body remains intact and an understandable status is shown.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 6 findings — high 0, medium 2, low 1, false 1, maybe-false 2
- findings:
  - `[medium]` `[patch]` A stalled demo asset fetch could disable the form indefinitely — bounded loading to ten seconds, aborted outstanding fetches, and passed a regression that preserves the existing draft.
  - `[medium]` `[patch]` A camera callback created before demo selection could use stale React state and append a late frame — added a synchronous loading ref and preset generation checks; the delayed-callback regression passed.
  - `[maybe-false]` `[defer]` A deployment could bind a new rule revision after choices were loaded — the rule is static per process and no rolling deployment contract is known; a live rolling revision change would settle the prior Story 2.1 risk.
  - `[false]` `[reject]` A future held-out copy of a bundled JPEG would pass unnoticed because admission validation ignores derived hashes — the demo asset test explicitly rejects either original or derived hash in the held-out inventory, while `validate_manifest` governs admission fixtures rather than cross-tier held-out inclusion; the proposed occupied-hash change alone would not enforce cross-inventory uniqueness.
  - `[low]` `[reject]` A fresh checkout skips comparison with the ignored source ZIP — the checked-in JPEG hashes and exclusion records are still verified, and this run verified all original PNG hashes locally. Bundling six more PNGs or the 221 MB archive solely to guard a rare simultaneous provenance edit would add disproportionate data.
  - `[maybe-false]` `[defer]` The tests do not exercise a rendered browser through a live service — UI request and two real persisted model runs are verified separately; a browser-level run is needed to settle their full client-to-service composition and layout, but GUI control is prohibited here.

## Design Notes

The observed positive series has a visible dump truck in frame 87 and another in frame 89; frame 90 has no dump-truck detection. All three negative frames have an excavator detection and no dump-truck detection. Positive frames 89/90 display 2024-01-21; negative frames display 2024-01-24. Frame 87 and all capture times are unverified, so prefilled noon is only an editable demo value. These curated development examples demonstrate outcomes of the current pinned profile, not detector accuracy or a frozen candidate's readiness.

## Verification

**Commands:**
- `cd web && npm test -- --run && npm run build` -- expected: editable demo selection, error handling, ordinary request and production asset build pass.
- `cd backend && uv run --no-cache pytest tests/test_rule_intent.py` -- expected: demo asset integrity and persisted ordinary-run outcomes pass against isolated PostgreSQL/S3.
- `git diff --check` -- expected: no whitespace errors.

**Observed before review:** web 46/46 and production build passed; rule-intent backend 21/21 and admission backend 13/13 passed in isolated PostgreSQL/MinIO. Two real pinned-observer runs in the isolated test database succeeded: `2a0678b6-3210-4c31-bb1e-f0e8bc382f54` projected `no_check`, and `ba99f0ef-19c4-4b06-b3a6-8f33a814d872` projected `check_requested`. All six source artifacts were read back byte-for-byte from the test bucket. Sprint tracking validation and `git diff --check` passed.

## Auto Run Result

Status: done

Included two editable three-frame demonstration cases from the organizer archive. They load into New Analysis, retain current rule-revision visibility and source provenance, and submit through the existing ordinary series path. The current pinned observer produced `no_check` for the truck case and `check_requested` for persistent non-detection in isolated PostgreSQL/MinIO runs; all six uploaded source artifacts were verified by readback.

Files changed:
- `web/public/demo/*.jpg` and `web/src/demoCases.json` — six JPEG derivatives with original and derived checksums, source groups, rule revision, and illustrative period metadata.
- `web/src/App.tsx` — atomic editable demo loading with asset integrity, timeout, camera-race protection, and normal submission.
- `web/src/App.test.tsx` — case selection, editing, ordinary request, failure, pending-recovery, timeout, and camera-callback checks.
- `backend/admission/exclusions/development_acceptance.json` — reserve the two development source groups and hashes outside held-out evaluation.
- `backend/tests/test_rule_intent.py` — verify manifest and exclusion integrity and both cases through persisted ordinary-run contracts.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` and this spec — record the verified story state.

Review: six findings from three active layers; Blind Hunter was skipped because only three reviewer slots were available. Two medium findings were patched (bounded asset loading and stale camera callback); two maybe-false medium risks were deferred (rolling rule revision and rendered browser journey); one false and one low finding were rejected with reasons in the Review Triage Log. Follow-up review recommended: true because two medium entries were patched. Specific unverified risk: a rolling revision change or browser-only behavior could still differ from the isolated CLI and DOM checks.

Verification: web tests 48/48 and production build passed; backend rule-intent tests 21/21 and admission tests 13/13 passed against isolated PostgreSQL/MinIO. Two actual pinned-observer runs succeeded with persisted `no_check` and `check_requested` projections; six source artifacts matched the submitted bytes. Six production-bundled JPEGs matched manifest hashes. Sprint tracking validation and `git diff --check` passed. The organizer ZIP is local and ignored by Git: original PNG hashes were checked here, while the original-hash test skips in a checkout without that archive. No GUI application was launched, so the rendered browser journey remains unverified.

---
title: Hybrid photographs to evidence-bound site signals
type: feature
created: '2026-09-27'
status: in-review
route: dispatch
review_loop_iteration: 0
baseline_commit: ef157b1c168c1a22df2ad4bca971056b94402082
context: []
---

<frozen-after-approval reason="User explicitly authorized implementation of the supplied completion plan">

## Intent

Complete the local photograph → both YOLO checkpoints → Yandex DeepSeek-V4.1-Flash → persisted project signals flow. Preserve uploads, projects, annotations, historical results, human stage confirmation, cloud consent and uncertain-call non-replay. Delivery includes reproducible real inference, evaluation, demonstration, accompanying PDF and presentation PDF. User already approved this entire scope; do not ask for another planning approval.

## Boundaries & Constraints

No GUI, remote deployment, destructive migrations, secret output or overwriting unrelated work. Local CPU inference is mandatory. Keep original weights at case-sensitive `artifacts/Models/{apoce,kaggle}.pt`, mount read-only. Persist a manifest with SHA-256, original classes, pinned dependencies, inference settings and explicit mapping. Never map APOCE lifting-equipment automatically to mobile_crane. Unsupported/ambiguous classes retain raw names and null mapping. Load and verify weights at startup, cache once and serialize inference. Preserve separate normalized oriented-image detections, scores, model/frame identity and provenance.

DeepSeek receives each photo and both detectors, reconciles physical objects once with detection references and disagreements, class assessability and frame usability. Assessment receives series photos, timestamps, exact immutable plan revision, bounded history, rule results and comparison method. Return activity (working_signs / possible_idle / insufficient_data) with evidence and uncertainty, multiple frame→stage→plan-entry hypotheses, and structured risks (cause, work, frame/observation references, impact, recommended check, limitations). Presence or static pose alone proves neither work nor idle. No duration/dynamics without reliable comparable independent frames. Duplicate image hashes are not independent observations.

Compare plan operations at each relevant frame's time, including interval boundaries and concurrent operations. Preserve conservative expected-missing/excluded-equipment rules and reconcile duplicates with model risks. Server validates references, usable evidence, plan applicability and activity grounds. Schedule risks require a bound applicable work; process signals may lack a plan but require a zone. Publish signals/projection in one lease-fenced transaction. Signal fingerprint uses zone, revision, cause, work and source evidence, never generated text or run ID. Keep immutable basis, new/in_progress/closed states/comments; calm later analyses never auto-close.

Default to plan comparison when the selected zone has a plan, display chosen revision and allow opt-out. Show boxes, activity, reasons, stage hypotheses, plan links and created signals. Add compatible API fields/OpenAPI/examples and YOLO progress without breaking historical runs. Additive migrations only.

Quality acceptance requires independently reviewed eight-class labels/scenes/activity/signals; never promote machine proposals to ground truth. Cover excavation, concrete and roadwork, each normal/risk/ambiguous/unusable; single/duplicate/poor visibility/working/possible idle. Measure class precision/recall, localization, stage correctness, false signals, uncertainty, latency and cost; no arbitrary accuracy threshold; zero false warnings and all required cases correct. Missing/unmet evidence blocks readiness. Real API budget is at most RUB 1000; reserve conservative upper cost before each call including uncertain outcomes, start minimal. No claim of project completion from mocks alone. Commit/push/merge only after verification. Preserve local data; no server update.

## I/O & Edge-Case Matrix

| Given / when | Then |
|---|---|
| Oriented JPEG/PNG, overlapping detections or same-class machines | Valid normalized boxes, source detections retained, physical-object reconciliation |
| Unusable/uncertain class or repeated photo | No missing-equipment/temporal proof from those inputs |
| Boundary-crossing series, concurrent operations, changed current revision | Applicable per-frame operations from frozen revision only |
| No plan, invalid references, unsupported idle/delay assertion | No invalid published signal; strict rejected response retained |
| Missing/corrupt weights, timeout, invalid JSON, lost lease, restart | No false success, automatic uncertain retry or duplicate signal |
| Old result/plan/profile | Reads without reprocessing or destructive migration |

</frozen-after-approval>

## Code Map

- `backend/app/profiles/deepseek.py`: retain legacy snapshot/schema validation; add distinct hybrid snapshot/contract and validated structured output; `oriented_image` is canonical EXIF preprocessing.
- `backend/app/application/deepseek_runtime.py`: lease, reserve-before-call, save_result, freeze_context, complete and execute; reuse these durability guarantees. `backend/app/main.py` startup and `application/executor.py` dispatch; preserve kind deepseek compatibility if hybrid is a contract revision.
- `backend/app/domain/site_analysis.py`: current all-times-in-one-entry comparison must become per-entry/per-frame with duplicate/assessability gates.
- `backend/app/application/{signals,site,submission}.py`, `adapters/postgres.py`, migrations: immutable plan binding, signal storage/readback and result evidence.
- `web/src/{App,EvidenceViewer,FramePreview}.tsx` and related project/signals components: existing boxes and source-frame navigation; extend in established design, avoid redesign.
- `infra/deploy/{backend.Dockerfile,compose.yaml,init.py}`, `backend/{pyproject.toml,uv.lock}`, `Makefile`: pinned CPU runtime and read-only local weights; do not change remote deployment state.
- `backend/tests/test_deepseek.py`, `test_site_analysis.py`, DB/S3 fixtures: reuse isolated database/bucket patterns; full suite is current contract.
- `evaluation/expansion/draft-annotations.json`: machine proposals, not reviewed ground truth. `Architecture.md`, `PRODUCT.md`, canonical `EXPANSION.md`, `docs/`: reconcile current behavior and evidence limits.

## Tasks & Acceptance

- [x] Implement manifest, both-detector runtime, dependency lock/startup/container path and real CPU smoke.
- [x] Implement hybrid schemas, evidence validation, photos in assessment, activity and work mappings; preserve old contracts.
- [x] Implement conservative time-aware comparison, atomic validated signals, source-based deduplication, additive migration.
- [x] Extend UI/API/progress/default plan comparison compatibly, with focused regressions.
- [x] Run backend/frontend suites, build, additive history checks, real local HTTP chain and independent review.
- [ ] Prepare controlled real evaluation, budget ledger, demo and both PDFs with honest acceptance status.
- [ ] Update product/architecture/run documentation; commit/push/merge verified work, local deploy with preserved data.

Acceptance: Given real weights and authorized cloud access, when demo photos are processed locally, then both raw detectors, actual photo-bearing DeepSeek calls and persisted source-bound signals can be inspected. Given complete reviewed control scenarios, when evaluated, then readiness reflects actual outcomes; missing labels/provider/build evidence remains explicitly blocked.

## Implementation Notes

Intent has no unresolved product decisions. Additive local migrations and paid calls within budget are authorized. This is one cohesive user outcome spanning all layers. Initial tree clean on main; preserve the user's active branch. Implementation agent should implement code/tests/docs first and report verification gaps; root coordinates real spend, delivery artifacts and final VCS/local rollout. Do not launch a second build workflow or pay for cloud calls in the implementation agent.

## Spec Change Log

## Review Triage Log

## Verification

Use full `backend/.venv/bin/python -m pytest backend/tests` with isolated PostgreSQL/private S3, `npm --prefix web test -- --run`, frontend build, real CPU checkpoint inference, container build and HTTP smoke. Root performs budget-controlled real cloud verification and PDF creation. GUI visual acceptance remains manual/not run.

### Independent review triage (2026-09-27)

All three layers completed against `review.diff` (282876 bytes). Findings were verified against callers, current guards and tests. Repairs preserve the accepted intent and existing evidence; no spec change or implementation rollback is needed.

| Finding | Verdict | Evidence and route |
| --- | --- | --- |
| Blind: frame context legacy version | medium | execute uses legacy REVISION for hybrid frame context; patch profile-bound versions. |
| Blind: YOLO stage succeeds after first frame | medium | reserve transitions ordinal 1 before subsequent detector calls; patch stage completion after all detections. |
| Blind: per-work insufficient frames omitted | medium | global count passes, per-entry count silently continues; patch explicit per-work insufficiency. |
| Blind: unassessable frame suppresses sufficient absence evidence | medium | all applicable IDs include unassessable class states; patch per-class usable subset while retaining positive sightings. |
| Blind: timed series bypasses duration validation | high | comparison_method alone disables guard, independent times do not prove continuous duration; patch asserted duration claims. |
| Blind: explanatory fields omitted from claims checks | high | impact/action/uncertainty/hypothesis fields reach UI unchecked; patch all published text fields with assertion-aware checks. |
| Blind: work claim includes frames without work signs | high | any() over union allows unsupported frame; patch evidence per cited frame. |
| Blind: substantive stage from unusable frame | high | hypothesis reference validation has no usability gate; patch unknown/ambiguous only where unusable. |
| Blind: Boolean-only quality pass | high | three flags permit pass without measured inventory; patch evidence-backed gate and reject minimal assertion reports. |
| Blind: legacy build demands YOLO | medium | Makefile check unconditional although legacy execution supported; patch conditional requirement. |
| Edge: unresolved detections become absence | high | class_state ignores dispositions; patch conservative unresolved-class handling and carry dispositions to frozen frames. |
| Edge: equivalent timestamp strings counted separately | high | string-set time comparison permits equal UTC instants; patch parsed timezone-aware times. |
| Edge: claims bypass through impact/action/hypothesis | high | same verified field coverage defect as blind reviewer; shared patch, retain separate finding record. |
| Edge: unrelated views permit temporal claim | high | comparison_method proves times/zone only; same temporal guard patch. |
| Edge: calendar fingerprint change duplicates old closed signals | high | old completion_unconfirmed identity changed with no migration; preserve legacy calendar fingerprint. |
| Verification: detector integrity/startup untested | high | integration replaces whole detector factory; add direct adapter corruption/class/dependency/startup rejection checks. |
| Verification: human confirmation endpoint untested | medium | direct inserted rows bypass per-frame confirmation; add DB round trip for boundaries/concurrency. |
| Verification: raw detector UI selection untested | medium | existing viewer fixtures contain reconciled objects only; add frame-specific model switching assertions. |
| Real HTTP: harmless temporal recommendations rejected | high | actual 48 assessment failed hybrid_duration_unverified for recommendation to acquire timed frames; patch assertion matching and retain this real response as regression evidence. |

Quality acceptance remains blocked separately: the reviewed candidates cover six classes and no qualified temporal idle series; real YOLO errors were observed. This does not relax technical publication guards.

### Real provider verification repairs

Real requests exposed additional contract/provenance defects after mock regression passed. Preserved all rejected responses and failed runs; no automatic provider retry was enabled. Added a captured disclaimer regression, clarified detector association versus label correction, and prohibited planned stages/generic hazards from substituting for visual evidence. The request now narrows activity/risk enums when independent timed evidence is unavailable; the server retains full validation. A successful real repeat exposed a stage-signal duplicate caused by varying model observation references. Stage-plan mismatch identity now uses its stable zone/revision/work/cause and original input hashes; cited observations remain immutable basis, rather than changing the signal identity. Earlier prototype duplicates remain historical evidence, not deleted records. Final verification uses a fresh plan revision and checks successful repeated publication and closed-state preservation.


### Final technical disposition

The final backend suite passed 300 cases with one explicit historical archive-dependent skip; frontend passed 203 cases and production build. Original CPU weights loaded on host and Linux. Actual photo-bearing frame/assessment calls, persisted plan mismatch, artifact SHA readback and successful quiet repeat were checked. Changed AI citations are covered by an independent DB regression; the live repeat returned no AI risks, so an identical provider risk was not claimed. All 31 paid checks are retained in the ledger (estimated RUB 58.7845, no unresolved transport/usage outcomes). Quality acceptance remains BLOCKED; this spec is not marked done. The review queue and targeted collection/training instructions are prepared, while eight-class adjudication, the complete quality matrix and final release acceptance remain outstanding. Final delivery and VCS evidence are recorded in docs/HYBRID_VERIFICATION.md/JSON.

The final UI check also normalizes unknown/ambiguous/unsupported stage proposals to an empty selection: confirmation remains disabled until a selectable stage is explicitly chosen. Four added regressions passed; final frontend suite is 203 passed with a successful production build.

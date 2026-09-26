---
title: DeepSeek service transition and Russian service documentation
type: feature
created: '2026-09-26'
status: done
route: dispatch
review_loop_iteration: 0
baseline_commit: 25ed8ccd5dfc1159b55f1d02bdf6e88613e769ff
context: []
---

<frozen-after-approval reason="User explicitly requested implementation of the supplied plan">

## Intent

Replace active recognition and analytics with a dedicated Yandex AI Studio DeepSeek adapter, and make the working service understandable to Russian-speaking judges and developers. Current photos go directly to DeepSeek; future two server-side YOLO profiles will provide explicitly mapped detections to DeepSeek. Do not connect trained weights, perform full training, make paid verification calls, or deploy to the live server.

## Boundaries & Constraints

Preserve all historical profiles, evidence, results, images, corrections and reports. Add migrations only. Reject new execution and retries of retired DINO/Qwen profiles; keep historical comparisons readable outside the main demonstration. Remove their active execution/configuration/preparation commands and exclusive dependencies; move shared helpers into neutral modules. Preserve projects, uploads, history, plans, annotation, feedback, admin and eight-class training compatibility.

Use the verified experimental client as reference: `deepseek-v4.1-flash/latest`, reasoning none, temperature 0, max output 8192, store false, data logging disabled. Validate decoding, JPEG/PNG MIME and EXIF orientation; boxes refer to the oriented image. Validate model identity, completion, mode, strict JSON, usage and coordinates; reject malformed/truncated output. Reserve each call durably before sending, bind it to the run and never automatically repeat an uncertain call.

Observe frames separately, then make exactly one analysis call with frozen observations, frame order/times, bound plan revision and up to three earlier successful same-zone analyses. Without a zone or reliable timestamps, omit history. Keep immutable normalized assessment and raw provider response plus instruction/schema versions, model and usage. Optional `ai_assessment` is null/absent for old runs, containing summary, stage hypothesis, risks, recommendations and limitations. Risks have category process/plan/safety and valid frame/observation references. Preserve free equipment names, unknown class, optional box and absent confidence. Never invent numeric confidence or grow catalog. Free hypotheses enter training export only after explicit human mapping/review.

Require explicit cloud-processing consent in upload request and persisted run. Enforce consent before all provider calls and preserve separate fixture/admission upload restrictions. Without a plan, no delay claim; non-detection is not proof of absence. Safety risks require visible frame evidence, never verified distances or normative violation claims. Show limits, source, stage, risks and evidence; human confirmation is separate.

No GUI applications, remote deploy, paid calls, secrets in files/output, modifying unrelated user work, or required runtime dependencies on /private/tmp. Use CLI/headless mocks. User already authorized this full plan; no additional planning approval is needed.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior |
|---|---|
| JPEG/PNG with orientation | Validated oriented observations and matching boxes |
| Missing consent | Rejected before cloud invocation |
| Free/unknown equipment, absent box/score | Preserved; not automatically training eligible |
| Wrong model/mode, incomplete response, malformed JSON/usage/coordinates | Failed run, no successful projection |
| Missing plan | Explicit insufficiency, no plan-delay assertion |
| Wrong risk reference | Rejected |
| Missing zone/time or later/other-zone history | Excluded from frozen context |
| Uncertain provider outcome | Durable failed/uncertain state, no automatic replay |
| Retired profile/new run/retry | Explicit rejection, old reads preserved |
| Historical result without assessment | Reads and renders normally |
| /api proxy docs and direct backend | ReDoc, Swagger and OpenAPI resolve correctly |

</frozen-after-approval>

## Code Map

- `backend/app/profiles/cloud_api.py`: historical Qwen client and bounded HTTP; `evaluation/cloud_api.py` is old experiment. Reusable DeepSeek experiment and Windows training bundle may exist under `/private/tmp/run-lzt-deepseek-authorized.py`, `/private/tmp/run-lzt-deepseek-ab-authorized.py`, `/private/tmp/lzt-yolo-training-build`, `/private/tmp/lzt-yolo-training-extracted`; inspect source without exposing secrets and copy reusable non-secret source into repo.
- `backend/app/application/{submission,executor}.py`: image validation, idempotency, claim/reservation/provider execution; `backend/app/adapters/postgres.py`: immutable snapshots, profiles, finish/read/retry, leases/publication, comparison reads.
- `backend/migrations/versions/0021_annotations.py`: current head; `backend/app/domain/observations.py`: normalized objects and stage hypotheses. `backend/app/application/{site,annotations,signals,engagement}.py`: existing API behavior to preserve/document.
- `backend/app/main.py`: manual Request parsing and JSONResponse endpoints, body size bounds, lifespan readiness. Add OpenAPI metadata without replacing these limits. `infra/deploy/nginx.conf` strips /api/.
- `web/src/App.tsx`, `EvidenceViewer.tsx`, `FramePreview.tsx`, `Annotations.tsx`, `AppHeader.tsx`: upload/result/annotation/navigation flow.
- `infra/deploy/{compose.yaml,init.py,backend.Dockerfile,web.Dockerfile}`: deployment startup. `backend/pyproject.toml`/`uv.lock`: remove app DINO-only packages.
- `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md`: old decisions; preserve IDs/history and link superseding current architecture.

## Tasks & Acceptance

- [x] Implement adapter, consent, new profile provisioning, persisted observation/assessment/context and immutable evidence; retire old execution safely.
- [x] Update UI and types for consent, free objects, assessment, evidence and separate confirmation; link ReDoc.
- [x] Add Russian FastAPI tags/operation/field descriptions, requests/responses/errors/examples and headers/auth for all existing groups, including manual-body endpoints. Configure root_path so /api/redoc, /api/openapi.json, /api/docs work through nginx; direct /redoc, /openapi.json, /docs stay available.
- [x] Write Russian README.md, Architecture.md with Mermaid current/future paths, docs/CODE_GUIDE.md with real module/entity/API/test links, API JSON/curl examples; reconcile nested README and old architecture. Cover Compose, catalog preparation, frontend build, env, migrations, private S3, profile configuration, readiness, first analysis, logs/errors. Include existing/repo-contained Windows setup_windows.cmd and smoke/pilot/full for two YOLO profiles, separate RTX 3060 training env, artifact transfer; do not execute training. Document idempotency/retry/uncertainty, consent, missing plan, retired profiles, historical null analytics, admin access.
- [x] Verify backend edge matrix, frontend/headless demo and historical flow, additive migrations in isolated PostgreSQL/private S3, mocked API examples and schema validation, direct/proxy docs, Compose/image builds/documented startup, Markdown/Mermaid. Record actual passes and exact environment limitations.

Acceptance: Given new consenting uploads, when processed with mocked DeepSeek, then per-frame observations and one immutable assessment are source-bound and human review remains explicit. Given historical rows, when read/annotated, then evidence and corrections remain usable without rewriting. Given documented clean setup, when run with mocks, then service and proxy docs match documented behavior. Technical smoke never claims model accuracy or safety quality.

## Implementation Notes

Intent has no unresolved user decisions. Scope spans backend, frontend and documentation as one service transition. Only local additive migrations/test data are authorized; production mutation is excluded. Keep verification gaps explicit if local infrastructure cannot run.

## Spec Change Log

## Review Triage Log

## Verification

Run backend pytest (including isolated PostgreSQL/S3 tests), frontend tests/build, CLI/headless integration, Compose config/build, documentation link/schema checks. Use saved or simulated provider output only.

### Investigation continuation

Verified reusable experiment source: `/private/tmp/lzt-jury-ready-release/scripts/prepare_deepseek_comparison.py` contains strict free-object schema, response/mode/usage validation; transport in `prepare_qwen_annotations.py` is shared but hardcodes PNG (must fix). The DeepSeek experiment rejects duplicate keys/nonfinite JSON and validates exact model URI and completed assistant output. Training sources are `/private/tmp/lzt-yolo-training-build/kit/{README.md,setup_windows.cmd,train.py,integrity.py,train_kaggle.cmd,train_apoce.cmd}`; scripts require manifest/index/archive datasets and weights. Copy source into stable repo path and document required bundle/input, never imply source alone includes datasets/weights.

### Delivery follow-up

User additionally authorized committing all changes, starting the application locally, and pushing to GitHub. User selected existing local Yandex configuration. Root verified existing yc service account access without invoking the model. Production deployment remains excluded.

### Independent review triage (2026-09-26)

All three reviewers completed against `/private/tmp/lzt-deepseek-review.diff`. Findings below are implementation defects or concrete verification gaps within the already authorized intent; repair retained code with bounded changes, preserving tests and history.

| Finding | Verdict | Verified evidence / route |
| --- | --- | --- |
| Blind: active rule option is rejected | high | submission rejects rule_evaluation while choices/UI offer it; patch active choices/UI together. |
| Blind: consent carries across drafts | high | only checkbox setter initializes consent; reset when draft inputs/context change, retain exact pending replay. |
| Blind: user context omitted | medium | freeze_context returns no scenario/area/period/stage; include immutable declared context. |
| Blind: unsorted timestamps discarded | medium | reliable=False sets every captured_at null; preserve timestamps independently from history eligibility. |
| Blind: no-plan disclaimer rejected | high | regex matches any occurrence of delay words across entire response, including explicit insufficiency; narrow assertion guard and test. |
| Blind: uncertain type becomes detected | high | complete() derives detected from catalog membership regardless of status; retain uncertainty in derived observation and UI. |
| Blind: plan signals lost | medium | replacement completion omits existing compare_equipment/site_signals path; restore source-bound plan comparison. |
| Blind: failed evidence hidden | medium | App only renders AI evidence under ai_assessment; expose retained/invalid/uncertain calls on failed runs too. |
| Blind: opaque risk references | medium | panel prints IDs with no source text/action; resolve frozen observations and open supporting frame. |
| Blind: unbounded history under locks | medium | fetches all same-zone context/results then slices Python list; bound eligible selection in SQL and fetch minimal fields. |
| Blind: full regression unresolved | high | 90 failures include preserved workflows and shared-fixture cascades; fix narrow fixture drift, isolate reruns, distinguish obsolete execution expectations explicitly. |
| Edge: no-plan disclaimer rejected | high | carried same concrete regex defect; same patch. |
| Edge: new plan stage menu rejected | medium | shared STAGE_NAMES has 8 stages but plan validator accepts 3; separate existing plan options from hypothesis labels. |
| Edge: consent carries across drafts | high | carried draft setter evidence; same patch. |
| Edge: declared context omitted | medium | carried freeze_context return fields; same patch. |
| Edge: uncertain type label absent | medium | carried object list render ignores details.status; same patch. |
| Edge: enabled retired queued runs stuck | medium | fail_unauthorized_queued only checks auth; current claim selects current profile, so old queues never terminate; explicitly fail retired queues. |
| Verification: bound-plan test missing | high | tests only freeze plan=None; add revision A/B persisted outgoing-context test. |
| Verification: invalid response retention untested | medium | validation tests bypass save_result/readback; add invalid frame/assessment persisted cases and nullable evidence schema. |
| Verification: claim restrictions untested | medium | no negative cases for nonvisible safety reference/unsupported assertion; add negative and permitted-counterpart tests. |
| Verification: transport tests target retired helper | medium | legacy tests exercise cloud_api helper while DeepSeek uses shared.cloud; test actual size/deadline helper. |

Root independent checks before repairs: actual HTTP synthetic lifecycle PASS; actual Compose nginx routes PASS; actual headless UI lifecycle PASS with no JavaScript errors/mobile overflow; backend/web image builds PASS; 39 OpenAPI operations and 326 embedded examples schema-validated; 46 local Markdown links valid; 2 Mermaid diagrams parsed and headlessly rendered. Re-run affected checks after patches; these are not evidence of model accuracy.

### Final verification disposition

All requested implementation surfaces and acceptance scenarios are implemented and checked. Verification is COMPLETED_WITH_GAPS: 148 isolated acceptance backend cases and 197 frontend cases pass; the preserved complete legacy backend suite remains 83 failed/219 passed/2 skipped, versus 41 failures on the original baseline. No test deletion or blanket skip was performed. Exact checks, retired-contract and fixture limitations are recorded in docs/DEEPSEEK_VERIFICATION.md. Model accuracy, paid access, training, Windows/CUDA and live deployment are outside verified scope. Independent review defects were repaired with bounded patches; original architecture frontmatter/decision IDs are preserved. User-authorized commit/local launch/GitHub push follows.

### Authorized legacy-test cleanup

The user explicitly authorized deletion of old tests after delivery of 1264066. Removed obsolete DINO/Qwen admission/provider execution tests; retained historical read/evidence/rights coverage and migrated ordinary upload, retry and recovery tests to DeepSeek. Added a distinct-frame series ordering/idempotency regression after independent review. Shared test fixtures now create per-module temporary PostgreSQL databases and private buckets, preventing cross-module pollution. A migrated lease-expiry regression exposed and fixed a real bug: complete() now fences its final success UPDATE and rolls back expired completion. Verification: full backend 256 passed/1 archive-dependent skip; the skipped test then passed against the existing source archive (all 257 tests covered). No blanket skip or xfail added. Frontend unchanged from its previously verified 197 passing tests. This supersedes the legacy regression gap above.

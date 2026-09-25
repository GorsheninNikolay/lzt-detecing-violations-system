---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - ../specs/spec-construction-monitoring-concepts/SPEC.md
  - ../specs/spec-construction-monitoring-concepts/prototype-scenarios.md
  - architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md
  - ux-designs/ux-lzt-detecing-violations-system-2026-09-21/DESIGN.md
  - ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md
---

# lzt-detecing-violations-system - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for lzt-detecing-violations-system, decomposing the requirements from the canonical SPEC bundle, UX design contract, and Architecture requirements into implementable stories.

The four-epic, 26-story breakdown was approved as one batch. AD-30 and AD-37 now define a complete local admission-smoke set separate from the held-out EvaluationSetRevision; the earlier draft's sequencing conflict is resolved.

## Requirements Inventory

### Functional Requirements

FR1: A user can submit one supported, decodable construction-site image for equipment observation.

FR2: A user can submit an explicitly ordered series of supported, decodable images from one controlled observation area and period.

FR3: A user can explicitly choose between rule evaluation and equipment-observation-only analysis before submission.

FR4: A user can explicitly provide or confirm the excavation scenario, controlled observation area, observation period, and applicable rule revision; the system does not infer these from a schedule, filename, or image date.

FR5: The system analyzes only the `excavator` and `dump_truck` classes in the Rapid MVP and marks other requested classes or unsupported work as `not_analyzed`.

FR6: For every requested class and evaluated input, the system produces exactly one of `detected`, `not_detected_in_frame`, `insufficient_data`, or `not_analyzed` and links it to the evaluated input.

FR7: An accepted image that the bound observer cannot assess produces `insufficient_data` rather than an upload rejection or `not_detected_in_frame`.

FR8: The system preserves per-frame observations when aggregating a series and never converts in-frame non-detection into a site-wide absence claim.

FR9: The system evaluates series sufficiency using the bound immutable PolicyProfile and reports `insufficient_data` when fewer than three usable same-area images are available for the initial excavation rule.

FR10: The system evaluates the excavation rule only from normalized observations, the explicit context, the immutable RuleRevision, and the immutable PolicyProfile snapshot.

FR11: The system produces a haulage-delay check request only when at least three usable same-area images are in explicit upload order, an excavator is detected in at least one usable image, and a dump truck is `not_detected_in_frame` in every usable image.

FR12: Single-image non-detection, mixed-area evidence, insufficient evidence, observer inability, or any dump-truck state other than `not_detected_in_frame` suppresses the haulage-delay check request.

FR13: A positive excavation series showing the expected excavator and dump truck produces `no_check` and exposes its supporting observations and applied rule.

FR14: A qualifying negative excavation series produces `check_requested` with a recommendation to check a possible soil-haulage delay.

FR15: A successful analysis produces exactly one top-level outcome from `observations_only`, `not_analyzed`, `insufficient_data`, `check_requested`, or `no_check`; a technical failure produces no ResultProjection.

FR16: Every check request exposes the supporting observations, observation period, applicable expectation, rule revision and provenance, uncertainty and reason, and recommended human check.

FR17: The system labels demonstration and heuristic rule provenance accurately and does not present either as a normative requirement.

FR18: The system creates an immutable AnalysisRun containing its intent, input manifest, context, bound rule and policy snapshots, observer profile, stage executions, invocation evidence, and final outcome.

FR19: A submitted run progresses asynchronously through the persisted ordered stages of input registration, frame usability, equipment observation, series aggregation, rule evaluation, and result projection.

FR20: A user can view the persisted lifecycle and factual result of each pipeline stage without client-invented progress percentages.

FR21: A user can inspect per-frame observations, separate series evidence, source images, rule provenance, uncertainty, and attributed provider-native evidence for a completed run.

FR22: A user can browse analysis history, reopen a run, and follow immutable predecessor/successor retry lineage.

FR23: A user can retry a technically failed run as at most one linked successor without overwriting or resuming the failed run.

FR24: A user can view a stage overview whose status comes from the latest succeeded ResultProjection, while newer queued, running, or failed lifecycle state is shown separately.

FR25: A user can choose an included demonstration fixture that populates the same explicit analysis context and ordered input manifest used for user-supplied images.

FR26: The system can execute an immutable 11-image evaluation set covering positive, check-request, insufficient-data, out-of-scope, and single-image observation cases.

FR27: The system can run a frozen, complete local-versus-cloud comparison campaign with one retained AnalysisRun per candidate, fixture, and repeat, including error and timeout cells.

FR28: A user can inspect criterion-level prototype readiness evidence, including mandatory outcomes, false warnings, misses, false detections, errors/timeouts, repeat disagreements, and check-request comprehension.

FR29: A user can inspect provider comparison separately from prototype readiness, with planned, completed, failed, timed-out, and missing cells visible and no automatically selected winner.

FR30: A user can inspect the project method, supported scope, limitations, team attribution, and source provenance on an About Project surface.

### NonFunctional Requirements

NFR1: No system output may declare a legal or contractual violation, claim site-wide equipment absence from one frame, or initiate management action.

NFR2: Prototype readiness requires zero false warnings across the complete frozen evaluation campaign; missing mandatory cases, incorrect mandatory outcomes, or any false warning fails readiness.

NFR3: Misses, false detections, errors/timeouts, and repeated-run disagreements must remain separately visible with literal numerators and denominators and must not be hidden by aggregate wording or a winner score.

NFR4: All run inputs, revision snapshots, execution identity, stage evidence, artifact references, and outputs must be reproducible and immutable; reprocessing creates a linked successor.

NFR5: Structured runtime state must use PostgreSQL only; runtime or test fallbacks to SQLite and placeholder use of `pgvector` are prohibited.

NFR6: Image bytes, model weights, rendered evidence, native responses, and reports must reside in a private S3-compatible artifact store, while PostgreSQL stores immutable metadata, URI, size, SHA-256, and lineage.

NFR7: Artifact publication and reads must verify integrity, tolerate deduplication without rewriting creator attribution, and never expose partial or unverified objects as evidence.

NFR8: Secrets, credentials, headers, and durable signed URLs must never be stored in run snapshots, artifacts, PostgreSQL, logs, or UI output.

NFR9: Run and stage transitions must be atomic, monotonic, lease-fenced, and immutable after terminal state; at most one stage is running for a run.

NFR10: Restart recovery must preserve uncertain external-call evidence, terminalize expired interrupted work without resuming it, and complete reconciliation before readiness or new claims.

NFR11: The delivered MVP runs as one single-host application instance with exactly one executor claim loop; liveness and readiness are distinct.

NFR12: Startup readiness requires migration-head verification, PostgreSQL read/write smoke, isolated S3 write/read/cleanup health, artifact reconciliation, and guarded expired-run recovery.

NFR13: Every candidate must have a reproducible locked environment, exact adapter and model identity, artifact hashes, commercial-rights evidence, and an end-to-end admission fixture before scored comparison.

NFR14: Local candidate admission requires a complete ordinary-laptop Apple M3 Pro CPU-only smoke on a separate admission set; accelerator profiles are optional separate revisions and cannot silently fall back to CPU.

NFR15: The bounded cloud prototype requires current evidence from the intended owner's active paid Yandex Cloud account for model access, quota, applicable commercial and data-processing/retention terms, exact image authorization, returned model identity, and a strict-schema image canary; provider failure has no hidden fallback. Any later customer account or real-site imagery requires its own rights and data gates.

NFR16: The application must remain usable at 320 CSS pixels, at 200% browser zoom, and on laptop, tablet, and phone layouts without two-dimensional page scrolling except inside the zoomable evidence canvas.

NFR17: The user interface must meet WCAG 2.2 AA, including specified contrast, visible focus, semantic structure, keyboard operation, 44x44 CSS-pixel touch targets, text-equivalent status cues, and reduced-motion support.

NFR18: All user-facing copy, accessibility names, errors, statuses, and help must be Russian; stable technical identifiers may appear only with Russian labels in secondary disclosure.

NFR19: Polling or reconnect behavior must preserve the last known persisted state and must never fabricate completion, failure, percentage progress, or an estimated finish time.

NFR20: The evaluation and demonstration must remain runnable on ordinary event hardware; latency, memory, cost, and failure measurements must be literal evidence rather than undocumented assumptions.

NFR21: Source code must be readable and modular, with domain filters depending on ports rather than web, PostgreSQL, S3, or provider SDK details.

NFR22: The initial PolicyProfile must accept every supported image that decodes, must not impose unvalidated resolution, visibility, object-size, cadence, duration, miss-rate, false-detection, or stability thresholds, and may change only by a new immutable revision.

### Additional Requirements

- Use the repository structural seed: `backend/domain`, `backend/application`, `backend/ports`, `backend/adapters`, `backend/migrations`, `backend/profiles`, `web`, `evaluation`, and `infra`.
- Pin the backend seed to Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.54, and PostgreSQL through `postgresql+psycopg`, with exact transitive locks per observer profile.
- Pin the web seed to React 19.3, TypeScript 6.0.3, and Vite 8.3.0; use Radix Themes for accessible interaction primitives.
- Model the domain as an ordered pipes-and-filters pipeline whose typed outputs are materialized only after successful stages.
- Implement immutable `AnalysisRun`, `InputManifest`, `PolicyProfile`, `RuleRevision`, `EquipmentCatalogRevision`, `ObserverExecutionProfileRevision`, `ProfileExecutionAuthorization`, `ObserverInvocation`, `ResultProjection`, `EvaluationSetRevision`, `ComparisonCampaign`, and `EvaluationReport` contracts.
- Create every run and its fixed ordered stage rows atomically in PostgreSQL; perform inference outside database transactions and commit guarded transitions with already-published artifact metadata.
- Use zero-based input ordinals as the only canonical initial-MVP order; retain duplicate checksums as eligible inputs unless a later PolicyProfile changes that rule.
- Keep normalized observations presence-only; provider-native counts, confidence, geometry, masks, and prose may be retained only as attributed secondary evidence and cannot drive rules or comparison scoring.
- Bind exactly one immutable observer profile revision and current authorization revision to every run before execution; adapters may not select, change, or fall back to another profile.
- Permit draft observer profiles only for explicit profile-admission runs; user-facing, demonstration, retry, and comparison runs require admitted and currently enabled profiles.
- Reserve each external observer call in PostgreSQL before bytes leave the process, binding run, stage, profile, authorization, exact inputs, and intended provider identity; normalized observations must reference one completed invocation.
- Record requested and returned model identity separately and never fill a missing returned identity from the requested alias.
- Reject hybrid execution in the delivered MVP even though the profile schema may represent a future explicit hybrid composition.
- Enforce run lifecycle `queued -> running -> succeeded|failed` and stage lifecycle `pending -> running -> succeeded|failed` or `pending -> skipped`; technical failure skips dependents and creates no ResultProjection.
- Implement database-backed claim leases, guarded renewal, lease-expiry recovery, and idempotent successor creation using expected-prior-state and ownership fencing.
- Implement atomic S3 publication using `PublicationIntent`, temporary keys, content verification, content-addressed final keys, final HEAD verification, reference commit, and metadata-only quarantine reconciliation.
- Store artifact bytes under private access and expose them only through server authorization or short-lived generated access; do not persist signed URLs in runs.
- Provide operator-triggered and startup artifact reconciliation under one named PostgreSQL advisory lock; reconciliation may not overwrite, move, delete, replace, or re-tag evidence.
- Configure the initial two-class taxonomy as `excavator` and `dump_truck`; preserve provider-to-portable mappings as immutable revisioned evidence.
- Configure the initial excavation RuleRevision with continuous excavator expectation, periodic dump-truck expectation, explicit demonstration provenance, reason wording, and recommended human check.
- Configure the initial PolicyProfile with supported-decodable-image admission, observer-inability insufficiency, three-usable-same-area series sufficiency, explicit upload order, and zero-false-warning readiness.
- Seed the versioned 11-image evaluation set with one single-both-present image, one single-excavator-only image, a three-image positive series, a three-image check-request series, a two-image insufficient series, and one out-of-scope image.
- Record evaluation image checksums, both-class manual labels, context, source rights, cloud-upload permission, and test-specific sufficiency notes; keep this set disjoint from training and validation data.
- Maintain three distinct fixture tiers: deterministic contract and development acceptance fixtures, a complete real end-to-end observer-admission smoke set, and the held-out readiness evaluation set; no tier may be presented as evidence belonging to another.
- Permit a deterministic test observer only in test composition and reject it as a runtime, demonstration, admission, or comparison profile; test persistence still uses PostgreSQL and the real artifact-store contract rather than SQLite or an alternate repository implementation.
- Keep Epic 1 contract/admission fixtures and Epic 2 development acceptance fixtures outside the held-out evaluation set and outside candidate tuning after evaluation freeze.
- Before freezing an EvaluationSetRevision, reject any content-checksum overlap or source/site/camera/time-sequence group overlap with training, validation, contract, admission, or development acceptance fixtures.
- Start the required comparison with admitted Grounding DINO Tiny CPU and Yandex AI Studio Qwen3.6 35B profiles on the accepted Story 4.1 evaluation revision; RF-DETR stays conditional on an independently approved rights-clear corpus, and Kimi stays outside the campaign until all Russia, commercial, payment, and data gates pass.
- Freeze evaluation, policy, rule, taxonomy, preprocessing, profiles, timeouts, concurrency `1`, SDK retries `0`, fixtures, candidates, and three repeat matrices before starting a comparison campaign.
- Execute comparison cells in deterministic `(campaign_id, repeat_ordinal, fixture_ordinal, candidate_ordinal)` order, one at a time; retain every error and timeout in immutable denominators.
- Generate an EvaluationReport with one `pass|fail|not_evaluated` evidence row per readiness criterion; derive overall readiness as `incomplete`, `fail`, or `pass` without a model winner score.
- Keep provider selection and `ActiveObserverConfiguration` publication out of the delivered MVP; an initial interactive profile comes from validated runtime configuration.
- Pin Grounding DINO Tiny to revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`; its required admission profile is Apple M3 Pro CPU-only with locked artifacts and offline smoke.
- Gate Qwen3.6 use on the owner's active paid Yandex Cloud account, applicable commercial and data terms, quota, exact authorized-image hashes, served-identity readback, and a strict-schema image canary. Record request data controls without claiming provider deletion; later customer accounts and real-site images require separate approval.
- Treat RF-DETR Nano `rfdetr==1.10.0` at `0f432b6` as non-blocking until a rights-clear two-class corpus, group-disjoint split, sampled label QA, locks, and CPU smoke are approved; exclude YOLO from delivered-MVP implementation absent a separate license decision.
- Expose only committed backend stage state and backend-derived outcome wording through the API; the web client must not infer rule results or stage completion.

### UX Design Requirements

UX-DR1: Implement a dark-only full-night theme using the exact declared color, typography, radius, spacing, focus, and semantic-status tokens from `DESIGN.md`; do not introduce light cards, gradients, glows, or color-only meaning.

UX-DR2: Use the exact product name `Контроль строительства` and team attribution `17 мгновений ИИ`; show the complete unedited logo only where it remains legible and use exact text in compact headers.

UX-DR3: Implement a responsive Application Shell with laptop navigation `Этапы`, `Анализы`, `Готовность`, secondary `О проекте`, one persistent `Новый анализ` action, and phone bottom navigation with visible labels.

UX-DR4: Implement the Stages Overview as a read-only evidence navigator with selectable Stage Tiles and a Stage Inspector; it must not display schedule completion, project-health percentages, trends, or automatically inferred current stage.

UX-DR5: Stage Tiles must show the latest succeeded ResultProjection outcome and any newer run lifecycle on separate labeled lines, including explicit empty and unconfigured states.

UX-DR6: Implement New Analysis with an explicit two-choice native-radio intent selector, compact editable Analysis Context, image uploader, ordered Input Manifest, demonstration-fixture chooser, and one primary submit action.

UX-DR7: If a stage has no configured rule, disable rule-evaluation intent with the visible reason `Для этого этапа правило не настроено в прототипе` and select observation-only intent without silently choosing another rule.

UX-DR8: Validate only supported format and decoding at upload; retain all unaffected files after a decode failure and surface observer-assessability only through pipeline results.

UX-DR9: Input Manifest rows must display `Кадр N`, preserve explicit order, provide always-available `Выше`, `Ниже`, and `Удалить` controls, support reversible local removal with `Вернуть`, and treat drag reordering as optional enhancement.

UX-DR10: Rule-evaluation submission with one or two images must remain allowed while showing the exact non-blocking three-usable-image insufficiency notice.

UX-DR11: Duplicate checksums must remain in the manifest with distinct ordinals and a non-blocking disclosure matching the active PolicyProfile.

UX-DR12: Submission must preserve context, intent, images, and order; prevent duplicate activation; reconcile an uncertain `run_id`; and navigate only after an authoritative run identity is available.

UX-DR13: Implement Run Workspace as one stable route that opens immediately for queued work, renders all six exact Russian pipeline-stage labels in persisted ordinal order, and later reveals the result without replacing the route.

UX-DR14: Pipeline Route must show textual lifecycle, factual summaries, timestamps when available, and visible skip or failure reasons; it must not invent percentages, estimated completion, or timestamp-based ordering.

UX-DR15: Result Summary must render exactly one backend-derived Russian outcome and must keep run lifecycle, result outcome, readiness, and model confidence visually and semantically separate.

UX-DR16: Observation Rows must show one frame, one requested class, one closed state, the exact input reference, and reasons for `insufficient_data` or `not_analyzed`; no portable object count may be shown.

UX-DR17: Series Evidence must be a separate component showing usable-frame count, same-area confirmation, upload order, excavator-supporting frames, and backend-projected persistence wording without inventing a series-level absence state.

UX-DR18: Every Check-request Panel must expose action, reason, evidence, area, period, rule revision, provenance, uncertainty, recommendation, and the persistent safety line `Это рекомендация для проверки, а не подтверждение нарушения.`

UX-DR19: Implement Evidence Thumbnails with source ordinal outside the image and one accessible Evidence Viewer with zoom/reset/previous/next/close controls, source metadata, optional supplied geometry, and provider-native attribution.

UX-DR20: Provider-native counts, confidence, and geometry disclosures must carry the label `Данные конкретного наблюдателя. Не используются правилом этапа.`

UX-DR21: Implement Analysis History with stable ordering during polling, creation time, stage, intent, lifecycle, terminal outcome, retry identity, empty/loading/error states, and no row jumps under pointer or focus.

UX-DR22: Offer retry only for technical failure; make clear that retry creates a linked successor, while changes to images, context, intent, rule, or policy start a distinct analysis.

UX-DR23: Implement Prototype Readiness as criterion-level rows with `Пройдено`, `Не пройдено`, or `Нет данных`, literal evidence, revision identities, and linked runs; show missing criteria instead of calculating a pass for an incomplete report.

UX-DR24: Implement Provider Comparison as a separate semantic table or evidence block showing candidate identity and complete planned-run accounting; incomplete comparison must say `Сравнение не завершено` and show no winner.

UX-DR25: Implement About Project with team identity, method, supported scope, limitations, and source provenance; if the logo cannot load, use exact team text rather than a generic icon.

UX-DR26: Preserve known content during loading, polling disconnect, history/readiness fetch failure, artifact failure, offline-before-submission, and server restart; place recovery actions next to affected content instead of relying on toasts.

UX-DR27: Use the exact evidence-bound Russian vocabulary from `EXPERIENCE.md`, including frame-bounded non-detection, possible-delay language, and `Недостаточно данных`; avoid legal certainty, urgency, gamification, English statuses, and marketing claims.

UX-DR28: Provide one `main` landmark, one Russian `h1` and document title per route, a visible-on-focus skip link, `aria-current` navigation, and focus movement to the destination heading only for user-initiated route changes.

UX-DR29: Make the Evidence Viewer a named modal with contained focus, inert background, `Esc` close, focus restoration, announced frame position and zoom changes, and 44x44 keyboard-operable controls.

UX-DR30: Provide native semantic buttons, links, inputs, and radio groups; persistent field labels; inline errors with `aria-invalid` and `aria-describedby`; a focused Russian error summary after failed submission; and one deduplicating polite status region.

UX-DR31: Announce each pipeline transition once, announce terminal success or failure once, never move focus during polling, and keep a submitting button present in the accessibility tree with the label `Создаём анализ…`.

UX-DR32: Support laptop, tablet, and phone topologies exactly as specified: horizontal six-step route only at laptop width, vertical route below 1024px, single-column primary flow below 768px, and full-screen phone Evidence Viewer.

UX-DR33: Preserve operability at 320 CSS pixels, 200% zoom, WCAG text-spacing overrides, device safe areas, and meaningful source order; only the evidence canvas may require two-dimensional scrolling.

UX-DR34: Implement `prefers-reduced-motion`; constrain meaningful motion to 150–220ms; prohibit flashing, timed actions, auto-advancing carousels, scroll hijacking, and motion-only state communication.

UX-DR35: Meet the declared contrast and focus thresholds, preserve at least 13px evidence metadata on laptop and 14px on phone, keep text off photographs without an opaque scrim, and verify semantic colors against their actual adjacent surfaces.

UX-DR36: Provide contextual image alternatives that identify source ordinal, usability, and relevant observation; ensure evidence geometry is never the only explanation and provider regions remain available as visible text.

UX-DR37: Preserve local form state while offline, disable but do not remove network-dependent submission, and state that images remain only on the device until refresh; do not queue uploads offline.

UX-DR38: Render readiness and provider matrices as semantic tables when relationships require them, including captions, row and column headers, a concise Russian summary, and explicit expanded-state controls.

### FR Coverage Map

FR1: Epic 1 - Submit one supported image for equipment observation.
FR2: Epic 1 - Submit an explicitly ordered same-area image series.
FR3: Epic 2 - Choose rule-evaluation or observation-only intent when the rule-evaluation path is available.
FR4: Epic 1 - Provide explicit scenario, area, period, and rule context.
FR5: Epic 1 - Limit portable MVP observations to excavator and dump truck.
FR6: Epic 1 - Produce one closed observation state per requested class and input.
FR7: Epic 1 - Represent observer inability as insufficient data.
FR8: Epic 1 - Preserve frame-bounded meaning during series aggregation.
FR9: Epic 2 - Apply PolicyProfile series-sufficiency rules.
FR10: Epic 2 - Evaluate the excavation rule only from normalized immutable evidence.
FR11: Epic 2 - Create a check request only for the qualifying persistent pattern.
FR12: Epic 2 - Suppress checks for ineligible or insufficient evidence.
FR13: Epic 2 - Produce and explain the positive no-check result.
FR14: Epic 2 - Produce and explain the qualifying check request.
FR15: Epic 1 - Produce exactly one closed top-level outcome for a successful run.
FR16: Epic 2 - Expose complete check-request evidence and recommendation.
FR17: Epic 2 - Preserve accurate rule provenance labels.
FR18: Epic 1 - Persist an immutable reproducibility-complete AnalysisRun.
FR19: Epic 1 - Execute the persisted six-stage asynchronous pipeline.
FR20: Epic 1 - Show authoritative evidence-backed pipeline progress.
FR21: Epic 2 - Inspect observations, series evidence, provenance, and native evidence.
FR22: Epic 3 - Browse history and immutable retry lineage.
FR23: Epic 3 - Retry a technical failure as one linked successor.
FR24: Epic 3 - Navigate stage status backed by the latest succeeded projection.
FR25: Epic 2 - Populate a real analysis from a demonstration fixture.
FR26: Epic 4 - Execute the versioned 11-image evaluation set.
FR27: Epic 4 - Execute the frozen local-versus-cloud comparison campaign.
FR28: Epic 4 - Inspect criterion-level prototype-readiness evidence.
FR29: Epic 4 - Inspect provider comparison without an inferred winner.
FR30: Epic 3 - Inspect project method, scope, limitations, and provenance.

## Epic List

### Epic 1: Traceable Equipment Observation

Users can submit one image or an explicitly ordered series and receive reproducible, source-bound excavator and dump-truck observations through an authoritative asynchronous pipeline.

**FRs covered:** FR1, FR2, FR4, FR5, FR6, FR7, FR8, FR15, FR18, FR19, FR20

**Implementation notes:** Deliver a complete observation-only path with immutable PostgreSQL state, S3-backed evidence, one admitted observer profile, the closed observation and outcome contracts, and the responsive Run Workspace. Create deterministic contract fixtures for states, failures, idempotency, and recovery plus one separate complete real end-to-end admission-smoke set; a test observer is valid only in test composition and cannot become a runtime profile. None of these fixtures may enter the held-out evaluation set. This epic establishes the end-to-end execution substrate but does not yet issue an excavation-rule check.

### Epic 2: Evidence-Bound Excavation Check

Users can explicitly choose observation-only or bounded excavation-rule evaluation, receive an evidence-backed `no_check`, `check_requested`, or `insufficient_data` outcome, and inspect why the result was produced without the system declaring a violation.

**FRs covered:** FR3, FR9, FR10, FR11, FR12, FR13, FR14, FR16, FR17, FR21, FR25

**Implementation notes:** Extend the working observation pipeline with the explicit intent selector, immutable PolicyProfile and RuleRevision evaluation, separate per-frame and series evidence, demonstration fixtures, the Check-request Panel, and the accessible Evidence Viewer. Add development acceptance fixtures for `observations_only`, `no_check`, `check_requested`, `insufficient_data`, and `not_analyzed`; keep them outside candidate tuning and the held-out evaluation set. Preserve observation-only behavior from Epic 1.

### Epic 3: Analysis Navigation and Recovery

Users can navigate evidence-backed stage status, reopen prior analyses, understand technical failures, create a linked retry, and inspect the product's method, scope, and limitations.

**FRs covered:** FR22, FR23, FR24, FR30

**Implementation notes:** Add Stages Overview, Analysis History, retry lineage, recovery states, and About Project over the immutable runs delivered by earlier epics. A newer non-succeeded run must never replace the latest succeeded stage outcome.

### Epic 4: Evidence-Based Prototype Readiness

Jury members and product owners can verify every readiness criterion and separately compare admitted local and cloud observer candidates through a complete reproducible campaign without an automatically selected winner.

**FRs covered:** FR26, FR27, FR28, FR29

**Implementation notes:** Add the versioned 11-image evaluation set, frozen three-repeat comparison matrices, literal metric accounting, criterion-level readiness, and a separate Provider Comparison surface. Before freeze, prove content- and source-group disjointness from all training, validation, contract, admission, and development acceptance fixtures. Errors and timeouts remain in denominators; incomplete evidence cannot produce a readiness pass or winner.

## Epic 1: Traceable Equipment Observation

Users can submit one image or an explicitly ordered series and receive reproducible, source-bound excavator and dump-truck observations through an authoritative asynchronous pipeline.

### Story 1.1: Start the Evidence Service Safely

As a prototype operator,
I want the application to expose liveness only when the process is running and readiness only after its required persistence gates succeed,
So that users cannot submit evidence to an unhealthy or misconfigured service.

**Acceptance Criteria:**

**Given** a clean checkout with the pinned backend configuration
**When** the operator installs and starts the application
**Then** it uses Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.54, and the committed exact dependency lock
**And** the initial repository structure separates domain, application, ports, adapters, migrations, profiles, web, evaluation, and infrastructure concerns.

**Given** a configured database URL that is not an explicit PostgreSQL dialect URL
**When** startup validates configuration
**Then** startup fails before accepting work
**And** no SQLite database, fallback repository, or second structured-state implementation is created.

**Given** a PostgreSQL database whose schema is not at the required migration head
**When** the application performs startup checks
**Then** readiness remains false with a stable machine-readable reason
**And** liveness continues to report only process health.

**Given** PostgreSQL is at migration head
**When** the database startup gate runs
**Then** it completes a real write/read/rollback-or-cleanup smoke through the production SQLAlchemy adapter
**And** any failure keeps readiness false without exposing credentials or connection secrets.

**Given** a configured private S3-compatible artifact store
**When** the artifact-store startup gate runs
**Then** it writes a collision-resistant object under `health/<startup-id>` outside publication and reconciliation namespaces
**And** it HEAD- and read-verifies the bytes before performing best-effort cleanup.

**Given** the S3 health object cannot be written, verified, read, or successfully cleaned up
**When** the startup gate completes
**Then** readiness remains false and reports the failed gate
**And** no health object is treated as run evidence or attached to an artifact record.

**Given** no analysis or publication data exists yet
**When** startup invokes the advisory-lock-fenced reconciliation gate
**Then** the pass completes idempotently as an evidenced no-op
**And** the design permits later PublicationIntent states to be added without changing the health namespace contract.

**Given** all applicable startup gates succeed
**When** the application completes initialization
**Then** `/health/live` reports process health and `/health/ready` reports ready
**And** exactly one application-owned executor claim loop is enabled for the single-host MVP.

**Given** any mandatory startup gate has not completed or has failed
**When** a client queries readiness or attempts work submission
**Then** readiness is false and work submission is unavailable
**And** no adapter, executor, or background task can bypass the gate.

**Given** automated verification of the startup behavior
**When** the test suite runs
**Then** it uses PostgreSQL and an S3-compatible implementation exercising the production port contracts
**And** it verifies non-PostgreSQL rejection, migration mismatch, database smoke failure, S3 verification failure, cleanup failure, reconciliation locking, and successful readiness without using SQLite.

### Story 1.2: Admit the Initial Local Observer Through the Evidence Pipeline

As a prototype operator,
I want to admit one reproducible local observer profile through the ordinary evidence pipeline,
So that subsequent user analyses can bind to a verified observer rather than an implicit or untested model configuration.

**Acceptance Criteria:**

**Given** the initial local candidate configuration
**When** the operator creates its draft execution-profile revision
**Then** it identifies Grounding DINO Tiny at immutable revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`
**And** records the adapter code, version, entrypoint and bundle hash; requested model identity; per-file model artifact hashes; preprocessing; prompts and thresholds; taxonomy mapping; observation and outcome contract revisions; runtime; commercial-rights manifest; and canonical profile hash.

**Given** the draft local profile
**When** its runtime is prepared
**Then** `uv lock --check` and frozen synchronization succeed from committed locks
**And** the pinned model snapshot completes an offline-load smoke without downloading mutable content during execution.

**Given** the required ordinary-laptop baseline
**When** the admission profile is validated
**Then** it declares Apple M3 Pro arm64 CPU-only execution with 12 CPU cores and 36 GB RAM
**And** any MPS, CUDA, or implicit CPU-fallback execution causes this profile's admission to fail.

**Given** a versioned admission-smoke set whose fixture manifests record checksums, context, source rights, and exclusion groups
**When** the operator starts admission
**Then** the system creates an immutable `purpose=profile_admission` AnalysisRun for each fixture, bound to the same draft profile
**And** the complete smoke set is disjoint by checksum and source/site/camera/time-sequence group from training, validation, development acceptance, and held-out evaluation sets.

**Given** a profile-admission run
**When** it begins execution
**Then** it snapshots an explicit positive bootstrap watchdog independently of the future admitted timeout
**And** creates the ordered stage rows, immutable input manifest, profile snapshot, and observer-invocation reservation before model execution begins.

**Given** the observer invocation reservation has committed
**When** Grounding DINO processes the admission fixture
**Then** the call uses the exact reserved inputs and records the actual CPU device, returned model identity, request or execution identity when available, preprocessing revision, and native artifact metadata
**And** requested identity is never copied into a missing returned-identity field.

**Given** the observer returns native detections
**When** the adapter normalizes its result
**Then** it emits exactly one closed state for `excavator` and one for `dump_truck`, each referencing the evaluated input and completed invocation
**And** native counts, confidence and geometry remain attributed evidence and do not enter portable rule or outcome semantics.

**Given** an admission fixture completes successfully
**When** its pipeline commits the terminal result
**Then** PostgreSQL contains its immutable run, stages, invocation, normalized observations, artifact metadata and one `observations_only` ResultProjection
**And** all referenced bytes have passed the S3 publication and integrity contract before the structured references commit.

**Given** every fixture in the first complete Apple M3 Pro CPU-only admission smoke succeeds and records actual device, literal latency, memory, errors, and required evidence
**When** admission is finalized
**Then** the system creates a new immutable `admitted` successor profile rather than mutating the draft
**And** atomically creates its initially `enabled` authorization with per-image timeout `max(2 × smoke p95, 60 s)` and batch timeout `max(2 × smoke total p95, 10 min)`.

**Given** installation, artifact publication, decoding, observer execution, normalization, identity recording, or terminal persistence fails
**When** the admission run terminates
**Then** it is retained as `failed`, downstream stages are marked `dependency_failed` where applicable, and no ResultProjection is created
**And** the profile remains draft with no enabled authorization.

**Given** a deterministic test observer or a profile without immutable admission evidence
**When** it is configured for runtime, demonstration, retry, or comparison execution
**Then** startup or submission rejects it
**And** the test observer remains usable only through explicit test composition.

**Given** profile or provider secrets are present in the process environment
**When** admission evidence is persisted or rendered
**Then** credentials, headers, signed URLs, and secret values are absent from PostgreSQL, artifacts, logs, profile snapshots, and API output
**And** verification covers both success and failure paths.

### Story 1.3: Complete a Single-Image Observation Run

As a construction site manager,
I want to submit one image for equipment observation,
So that I can see exactly what that image supports.

**Acceptance Criteria:**

**Given** a ready service with an admitted, enabled prototype profile
**When** I submit one supported decodable image with observation-only intent and explicit scenario, area, and period
**Then** the API returns one authoritative `run_id` for an asynchronously queued run
**And** no rule revision is required or evaluated. (FR1, FR4)

**Given** an unsupported or undecodable file
**When** I submit it
**Then** the API rejects the affected file with a stable error code
**And** it creates no run or evidence reference for those bytes.

**Given** a valid submission with an idempotency key
**When** the same logical request is delivered again
**Then** both responses identify the same run or the same terminal submission error
**And** the service does not create a second run, input reference, or observer call.

**Given** input publication succeeds
**When** the run is created
**Then** one PostgreSQL transaction persists intent, context, a one-item ordinal-`0` manifest, immutable policy and taxonomy snapshots, bound profile and authorization revisions, and six ordered stage rows
**And** the referenced input object has passed the PublicationIntent, checksum, and final-object verification contract. (FR18, FR19)

**Given** the executor claims the queued run
**When** it reaches equipment observation
**Then** it commits a fenced invocation reservation against the expected enabled authorization before sending input bytes
**And** every stage transition is guarded by prior state and owned lease.

**Given** the observer completes for an assessable frame
**When** its result is normalized
**Then** `excavator` and `dump_truck` each receive exactly one `detected` or `not_detected_in_frame` state with input and completed-invocation references
**And** native counts, confidence, and geometry remain attributed secondary evidence. (FR5, FR6)

**Given** the observer cannot assess an accepted frame or a requested class is outside scope
**When** normalization completes
**Then** the affected class is respectively `insufficient_data` or `not_analyzed`, with a reason and input reference
**And** neither state becomes an absence or deviation claim. (FR7)

**Given** observation-only processing succeeds
**When** the terminal transaction commits
**Then** exactly one immutable `observations_only` ResultProjection is stored even if every class is `insufficient_data`
**And** the API exposes committed lifecycle, stage, observation, outcome, and evidence data appropriate to the run state. (FR15)

**Given** a timeout, provider error, malformed output, missing artifact, or guarded-write failure
**When** execution terminates
**Then** the run is `failed`, dependent pending stages are `skipped` with `dependency_failed`, and no ResultProjection exists
**And** no profile or device fallback occurs.

### Story 1.4: Complete an Ordered-Series Observation Run

As a construction site manager,
I want to analyze images in my explicit order,
So that each observation stays tied to the right frame and area.

**Acceptance Criteria:**

**Given** two or more supported decodable images from one declared controlled area and period
**When** I submit an observation-only series
**Then** the immutable manifest records a stable input ID, checksum, and contiguous zero-based upload ordinal for each image
**And** filenames, EXIF times, multipart order, and receipt times do not reorder it. (FR2)

**Given** two images have identical checksums
**When** the series is submitted
**Then** both remain eligible manifest entries with different ordinals
**And** artifact deduplication does not erase either input reference.

**Given** the series is processed
**When** observations are aggregated
**Then** per-frame states and input references remain available for both requested classes
**And** the series result never promotes frame non-detection to site-wide absence. (FR8)

**Given** one accepted frame is unassessable or one observer call fails
**When** the run completes or fails
**Then** inability is recorded as class-level `insufficient_data`, while technical failure follows the failed-run contract
**And** neither is silently counted as `not_detected_in_frame`.

### Story 1.5: Submit an Observation in the Responsive Web App

As a construction site manager,
I want a clear form for adding and ordering images,
So that I can submit an observation with the intended context.

**Acceptance Criteria:**

**Given** the observation-only MVP
**When** I open New Analysis on laptop or phone
**Then** I see persistent Russian labels for scenario, area, period, supported scope, and image selection
**And** the page uses the approved full-night tokens, product name, semantic controls, and responsive layout. (UX-DR1–3, UX-DR6, UX-DR28, UX-DR32)

**Given** accepted files in the Input Manifest
**When** I move or remove an image
**Then** `Выше`, `Ниже`, `Удалить`, and `Вернуть` preserve a visible `Кадр N` order and reversible local state
**And** drag input is optional, duplicate checksums remain, and reordering is announced accessibly. (UX-DR9, UX-DR11)

**Given** one file cannot decode, camera permission is denied, or the device is offline
**When** I try to add or submit images
**Then** the form retains valid files, context, and order and displays a nearby Russian recovery message
**And** offline submission is disabled without queueing an upload. (UX-DR8, UX-DR26, UX-DR37)

**Given** a valid form
**When** I activate `Запустить анализ` or an uncertain response occurs
**Then** the control remains present as `Создаём анализ…`, prevents duplicate activation, and reaches Run Workspace only after an authoritative `run_id` is known
**And** failure preserves entered values and focuses an error summary linked to affected controls. (UX-DR12, UX-DR30, UX-DR31)

**Given** laptop, tablet, or phone width, 200% zoom, text-spacing overrides, or reduced-motion preference
**When** I use the form and application shell
**Then** navigation, labels, controls, and accepted-image order remain operable at 320 CSS pixels with declared contrast, visible focus, and 44x44 CSS-pixel touch targets
**And** motion is reduced without hiding state, Onest falls back without clipping, and status is never conveyed by color alone. (UX-DR1, UX-DR3, UX-DR28, UX-DR32–35)

### Story 1.6: Follow Authoritative Pipeline Progress

As a construction site manager,
I want to see what the analysis has actually completed,
So that I can distinguish waiting, processing, and failure.

**Acceptance Criteria:**

**Given** a queued or running run
**When** I open its workspace
**Then** the same route shows all six persisted stages in their fixed ordinal order with the exact Russian labels from `EXPERIENCE.md`
**And** laptop uses a horizontal route while narrower layouts use a vertical route. (FR20, UX-DR13, UX-DR32)

**Given** stage transitions commit
**When** polling refreshes the workspace
**Then** it shows factual summaries, timestamps when present, and failed or skipped reasons from the backend
**And** it invents no percentage, estimate, completion, or focus movement. (UX-DR14, NFR19)

**Given** polling disconnects or the run fails
**When** the workspace updates
**Then** the last known persisted state remains visible with `Проверить статус` or the failed stage and preserved completed evidence
**And** a shared status region announces each meaningful transition once. (UX-DR26, UX-DR31)

### Story 1.7: Inspect the Source-Bound Observation Result

As a construction site manager,
I want to inspect each equipment observation beside its source frame,
So that I understand the result's limits.

**Acceptance Criteria:**

**Given** a succeeded observation-only run
**When** I read its result
**Then** the Result Summary displays backend-derived `Только наблюдения` and says `Правило этапа не проверялось`
**And** each requested-class row shows one translated closed state, reason when applicable, and exact input reference. (FR6, FR15, UX-DR15, UX-DR16)

**Given** a multi-image run
**When** I inspect observations
**Then** frame rows remain distinct and a separate Series Evidence block shows backend-projected usable count, area confirmation, order, and supporting frame references
**And** it makes no site-wide absence claim. (FR8, UX-DR17)

**Given** I open a source image or attributed native artifact
**When** bytes load or integrity verification fails
**Then** I can inspect the image and its source metadata or see a specific integrity error while observation text remains available
**And** no durable signed URL, secret, or native confidence is presented as a portable rule fact. (UX-DR19, UX-DR20, UX-DR36)

### Story 1.8: Recover Interrupted Runs and Artifact Publication

As a prototype operator,
I want restart recovery to retain evidence and settle interrupted work,
So that users never see a resumed uncertain provider call as a fresh result.

**Acceptance Criteria:**

**Given** pending or stranded PublicationIntents after a restart
**When** the advisory-lock-fenced reconciler scans them
**Then** it records pass evidence, verifies existing objects, attaches only provably matching published content, and quarantines stranded `content_verified` intents
**And** it never overwrites, deletes, moves, or retags evidence bytes.

**Given** an unclaimed queued run or an unexpired running lease
**When** guarded startup recovery runs
**Then** queued work remains claimable and an unexpired running run remains owned
**And** owner/token mismatch blocks writes without terminalizing that unexpired run.

**Given** a running lease has expired
**When** recovery commits
**Then** one fenced transaction marks the run `failed` with `executor_interrupted`, skips downstream dependencies, and retains its invocation and artifact evidence
**And** the provider call is not resumed or repeated.

**Given** reconciliation or guarded recovery cannot complete
**When** startup checks readiness
**Then** readiness remains false and executor claims remain disabled
**And** deterministic PostgreSQL/S3 contract tests cover repeat recovery and competing-owner attempts. (NFR9–NFR12)

## Epic 2: Evidence-Bound Excavation Check

Users can explicitly choose observation-only or bounded excavation-rule evaluation, receive an evidence-backed `no_check`, `check_requested`, or `insufficient_data` outcome, and inspect why the result was produced without the system declaring a violation.

### Story 2.1: Choose an Applicable Analysis Intent

As a construction site manager,
I want to choose whether to observe equipment or check the configured excavation rule,
So that the result matches the question I am asking.

**Acceptance Criteria:**

**Given** a configured excavation stage
**When** I open New Analysis
**Then** `Проверить правило этапа` is the default and `Только распознать технику` is an explicit native-radio alternative
**And** context displays the area, period, rule name, revision, expectation, and provenance before submission. (FR3, UX-DR6)

**Given** a stage without an applicable rule
**When** I select it
**Then** rule evaluation is unavailable with `Для этого этапа правило не настроено в прототипе` and observation-only is selected
**And** no rule is silently inferred from stage name, schedule, filename, or date. (UX-DR7)

**Given** a rule-evaluation submission with only one or two images
**When** I review the form
**Then** submission remains available with the three-usable-image insufficiency notice
**And** the backend, not the browser, decides the eventual outcome. (UX-DR10)

### Story 2.2: Apply Immutable Evidence and Rule Revisions

As a construction site manager,
I want every check to use a recorded rule and evidence policy,
So that its meaning does not change after I review it.

**Acceptance Criteria:**

**Given** the initial excavation configuration
**When** a rule-evaluation run is created
**Then** it binds complete immutable PolicyProfile and RuleRevision snapshots, the two-class taxonomy, explicit area and period, and the selected observer profile
**And** changing any policy or rule value creates a new revision without rewriting earlier runs. (FR4, FR10)

**Given** a supported image decodes but is unassessable or fewer than three usable same-area frames exist
**When** the policy evaluates evidence
**Then** the rule outcome is `insufficient_data`, with a specific reason and no check request
**And** no subjective resolution, visibility, size, cadence, or duration threshold is imposed. (FR9, NFR22)

**Given** the excavation rule revision
**When** its explanation is rendered
**Then** excavator is continuously expected, dump truck periodically expected, and provenance is labeled `demonstration rule` until a different identified source is adopted
**And** heuristic or demonstration provenance is never described as normative. (FR17)

### Story 2.3: Produce the Positive No-Check Result

As a construction site manager,
I want a usable series with the expected equipment to show that no check was requested,
So that I can distinguish that result from a failed or incomplete analysis.

**Acceptance Criteria:**

**Given** at least three usable ordered images from the same area and period with a detected excavator and at least one detected dump truck
**When** the bound rule is evaluated
**Then** the succeeded ResultProjection is `no_check` with supporting frame observations and applied rule revision
**And** it makes no claim that the whole work stage is healthy. (FR13)

**Given** a development positive fixture
**When** its deterministic contract test runs
**Then** the expected `no_check` outcome and zero check requests are asserted from normalized observations
**And** the fixture remains outside the held-out evaluation set.

### Story 2.4: Request a Check Only for Persistent Non-Detection

As a construction site manager,
I want a possible haulage delay flagged only when the defined series evidence supports it,
So that the warning remains a prompt for human review.

**Acceptance Criteria:**

**Given** at least three usable images from one area in upload order, excavator detected in at least one, and dump truck `not_detected_in_frame` in every usable image
**When** the excavation rule evaluates the series
**Then** exactly one `check_requested` projection asks the manager to check a possible soil-haulage delay
**And** its immutable and rendered evidence includes supporting frames, period, expectation, rule revision, provenance, uncertainty, reason, and recommended human check. (FR11, FR14, FR16)

**Given** a single frame, mixed-area evidence, observer inability, insufficient usable frames, or any dump-truck state other than `not_detected_in_frame`
**When** rule evaluation runs
**Then** no haulage-delay check is created and the appropriate backend outcome explains why
**And** errors and timeouts fail the run instead of becoming `insufficient_data` or `no_check`. (FR12)

**Given** the user reads a check request
**When** it is rendered in Russian
**Then** the visible panel includes `Это рекомендация для проверки, а не подтверждение нарушения.`
**And** neither API nor UI calls it a legal or contractual violation or takes management action. (NFR1, UX-DR18, UX-DR27)

### Story 2.5: Inspect Evidence and Rule Provenance

As a construction site manager,
I want to inspect the observations and source images behind a check,
So that I can decide what to verify on site.

**Acceptance Criteria:**

**Given** a succeeded rule-evaluation run
**When** I expand its details
**Then** per-frame Observation Rows, a separate Series Evidence block, source thumbnails, rule provenance, uncertainty, and recommended check are available in that order
**And** the UI renders only the backend's ResultProjection and evidence wording. (FR21, UX-DR16–18)

**Given** I open an Evidence Thumbnail
**When** the named viewer appears
**Then** keyboard-operated zoom, reset, previous, next, and close controls work with focus containment and restoration
**And** source ordinal, usability, observation text, artifact identity, and checksum remain inspectable at 320 CSS pixels and 200% zoom. (UX-DR19, UX-DR29, UX-DR33, UX-DR36)

**Given** provider-native evidence exists
**When** I reveal technical detail
**Then** it attributes adapter, profile revision, invocation, input IDs, preprocessing revision when applicable, and artifact checksum
**And** native count, confidence, and geometry are labeled `Данные конкретного наблюдателя. Не используются правилом этапа.` (UX-DR20)

### Story 2.6: Run Included Demonstration Cases

As a jury member,
I want to launch positive and check-request examples through the ordinary analysis form,
So that I can inspect the same path a site manager uses.

**Acceptance Criteria:**

**Given** an included positive or negative demonstration fixture
**When** I select it in New Analysis
**Then** its explicit scenario, area, period, rule revision, and ordered images populate the editable form
**And** submission creates an ordinary immutable run through the same publication, pipeline, and projection contracts as user images. (FR25)

**Given** the positive and negative fixtures complete
**When** I inspect their results
**Then** the positive fixture yields `no_check` and the qualifying negative fixture yields `check_requested` with visible source evidence
**And** neither fixture is counted as held-out readiness evidence or used to tune a frozen candidate. (FR13, FR14)

### Story 2.7: Cover Insufficient and Out-of-Scope Journeys

As a construction site manager,
I want inadequate or unsupported evidence to be explained plainly,
So that I do not mistake a withheld check for a healthy stage.

**Acceptance Criteria:**

**Given** a two-image rule-evaluation series or accepted but unassessable evidence
**When** the run succeeds
**Then** Result Summary says `Недостаточно данных`, identifies the limiting frames or series condition, and shows no Check-request Panel
**And** historical inputs and their order remain available. (FR9, UX-DR10, UX-DR15)

**Given** unsupported work or a non-informative requested class
**When** the run succeeds
**Then** outcome or class row says `Не анализировалось` with a scope or rule reason and input reference
**And** no detection, deviation, or check claim appears. (FR5, FR15)

**Given** the development acceptance fixture suite
**When** it runs
**Then** `observations_only`, `no_check`, `check_requested`, `insufficient_data`, and `not_analyzed` are asserted as distinct outcomes
**And** the suite records fixture provenance and exclusion groups separate from the held-out evaluation set.

## Epic 3: Analysis Navigation and Recovery

Users can navigate evidence-backed stage status, reopen prior analyses, understand technical failures, create a linked retry, and inspect the product's method, scope, and limitations.

### Story 3.1: Reopen Analyses and Their Evidence

As a construction site manager,
I want a stable history of my analyses,
So that I can return to a result without rerunning the observer.

**Acceptance Criteria:**

**Given** persisted runs with mixed lifecycle states
**When** I open `Анализы`
**Then** each row shows creation time, stage, intent, lifecycle, terminal outcome when available, and linked retry identity
**And** selecting a row opens its immutable Run Workspace. (FR22, UX-DR21)

**Given** polling changes one run's state
**When** history refreshes
**Then** row order stays stable under pointer or focus and the outcome is not inferred for an unfinished or failed run
**And** an empty, loading, or fetch-failure state has its specified Russian text and recovery action.

### Story 3.2: Retry a Failed Run as a Linked Successor

As a construction site manager,
I want to retry a technical failure without altering the earlier attempt,
So that its evidence remains auditable.

**Acceptance Criteria:**

**Given** a terminal `failed` run and an admitted, enabled profile
**When** I choose `Повторить анализ`
**Then** an idempotent expected-no-successor guard creates at most one direct successor with `retry_of_run_id`
**And** the original run, stage evidence, artifacts, and invocation remain immutable. (FR23)

**Given** a newer failed successor already exists
**When** I retry the lineage again
**Then** the next run descends from that newest failed successor and no branch is created
**And** the user can see the predecessor and successor identities in history and workspace.

**Given** I keep the configured prototype profile or explicitly choose another server-listed retry-eligible profile
**When** the successor is submitted
**Then** admission, current authorization, account/data gates, and binding kind are revalidated and snapshotted
**And** a changed image, context, intent, rule, or policy starts a distinct analysis rather than masquerading as retry. (UX-DR22)

**Given** a succeeded, running, or queued run
**When** its workspace is shown
**Then** no retry action is offered
**And** leaving a running workspace does not cancel the server run.

### Story 3.3: Navigate Evidence-Backed Stage Status

As a construction site manager,
I want to see which stage has recent analysis evidence,
So that I can open that evidence or begin a new analysis.

**Acceptance Criteria:**

**Given** the Stages Overview
**When** it loads
**Then** each configured Stage Tile and its inspector use only the latest run with both succeeded lifecycle and ResultProjection for that stage
**And** a newer queued, running, or failed run appears only as separate lifecycle context. (FR24, UX-DR4, UX-DR5)

**Given** a stage has no completed analysis or no configured rule
**When** I select it
**Then** the inspector shows `Анализов нет` or `Не настроено в прототипе` with an actionable route or scope explanation
**And** it shows no schedule completion, percentage, trend, or project-health rollup.

**Given** phone or laptop navigation
**When** I select a stage or move to another route
**Then** focus, selected-state semantics, labeled navigation, and the visible `Новый анализ` action follow the UX contract
**And** the stage inspector never implies that stage selection changed a schedule. (UX-DR3, UX-DR28, UX-DR32)

### Story 3.4: Explain the Prototype and Its Limits

As a jury member or site manager,
I want a concise description of the product's method and limits,
So that I can interpret its results accurately.

**Acceptance Criteria:**

**Given** `О проекте`
**When** I open it from navigation or attribution
**Then** it explains the excavation scenario, two supported classes, source images, observation states, rule provenance, human-check semantics, and excluded capabilities in Russian
**And** it identifies `Контроль строительства` as the product and `17 мгновений ИИ` as the team. (FR30, UX-DR2, UX-DR25)

**Given** the supplied team logo is unavailable or too small to remain legible
**When** the page renders
**Then** it uses the exact team text and no invented replacement mark
**And** the page retains semantic headings, contrast, focus, and mobile reading order.

## Epic 4: Evidence-Based Prototype Readiness

Jury members and product owners can verify every readiness criterion and separately compare admitted local and cloud observer candidates through a complete reproducible campaign without an automatically selected winner.

### Story 4.1: Freeze the Held-Out Evaluation Set

As a prototype evaluator,
I want a versioned set of manually labeled fixtures,
So that readiness can be checked against evidence that was not used for development or tuning.

**Acceptance Criteria:**

**Given** the proposed initial evaluation manifest
**When** its revision is frozen
**Then** it contains exactly 11 images across single-both-present (1), single-excavator-only (1), positive series (3), check-request series (3), insufficient series (2), and out-of-scope (1)
**And** every image has checksum, both-class manual labels, context, source rights, cloud-upload permission, and test-specific sufficiency notes. (FR26)

**Given** training, validation, contract, admission, or development acceptance manifests
**When** the evaluation freeze gate runs
**Then** it rejects matching checksums and overlapping source/site/camera/time-sequence groups
**And** the decision and exact group identities are recorded without exposing private source bytes.

**Given** any fixture, label, right, or sufficiency condition changes after freeze
**When** a later evaluation is planned
**Then** it uses a new immutable EvaluationSetRevision
**And** prior reports remain bound to the earlier revision.

### Story 4.2: Admit the Required Cloud Candidate

As a prototype evaluator,
I want a verified cloud observer profile,
So that local and cloud results can be compared under the same evidence contract.

**Acceptance Criteria:**

**Given** the intended owner's active paid Yandex Cloud account and a declared approved prototype image set
**When** the admission gates are evaluated
**Then** current Qwen3.6 access, quota, applicable commercial and data-processing/retention terms, request data controls, and exact image rights and authorization are evidenced from that account
**And** failure of any gate keeps the profile draft and blocks image upload. (NFR15)

**Given** an approved canary image and a bounded invocation
**When** the exact Yandex AI Studio Qwen3.6 profile is called
**Then** strict two-class output, provider response/request identity, served-model URI, request data controls, and private input and native artifacts are verified through the ordinary invocation and artifact contracts
**And** timeout, malformed output, missing identity, or unauthorized input remains an admission failure rather than an inferred absence; `store=false` does not establish provider deletion.

**Given** admission succeeds
**When** a new immutable profile revision is created
**Then** it records requested and returned model URI, adapter, prompt, schema, reasoning and temperature revisions, runtime limits, account/data evidence, allowed image hashes, and enabled authorization
**And** any hosted-model revision that cannot be pinned is disclosed as an identity gap.

### Story 4.3: Freeze a Complete Comparison Campaign

As a prototype evaluator,
I want the complete comparison plan fixed before running candidates,
So that failures and missing cells cannot disappear from the result.

**Acceptance Criteria:**

**Given** admitted, enabled Grounding DINO Tiny CPU and Qwen3.6 profiles plus the accepted Story 4.1 EvaluationSetRevision
**When** I start the required campaign
**Then** one atomic manifest freezes evaluation, policy, rule, taxonomy, preprocessing, profile revisions, timeouts, concurrency `1`, SDK retries `0`, candidate and fixture ordinals, and all three repeat matrices
**And** the Qwen profile's authorized hashes include every campaign input, while no RF-DETR, Kimi, hybrid, or unadmitted profile enters by implicit fallback. (FR27)

**Given** the campaign manifest
**When** planned cells are materialized
**Then** every `(campaign_id, repeat_ordinal, fixture_ordinal, candidate_ordinal)` has one distinct planned AnalysisRun
**And** duplicate image checksums never collapse fixture cells or denominators.

**Given** a configuration value changes after campaign freeze
**When** execution is requested
**Then** the current campaign remains immutable and a changed campaign requires a new revision
**And** the UI does not present either campaign as a selected provider.

### Story 4.4: Execute and Recover Every Planned Cell

As a prototype evaluator,
I want each planned comparison cell to reach a retained terminal state,
So that the report reflects the whole experiment.

**Acceptance Criteria:**

**Given** a frozen comparison campaign
**When** its executor runs
**Then** it processes one cell at a time in the frozen tuple order and creates one ordinary evidence-backed AnalysisRun per cell
**And** it performs no scored retry within a cell. (FR27)

**Given** an observer error, timeout, revocation, or restart
**When** the cell terminates or recovery resumes the campaign
**Then** the failed cell and its evidence remain in the matrix and recovery selects the lowest non-terminal key
**And** an uncertain external call is never resumed or replaced under the same cell identity.

**Given** all three repeat matrices
**When** accounting is inspected
**Then** planned, succeeded, failed, timed-out, and missing cells reconcile exactly to the immutable manifest
**And** denominators come from that manifest rather than the observed successes.

### Story 4.5: Calculate Criterion-Level Readiness

As a prototype evaluator,
I want a literal, evidence-linked readiness report,
So that I can say which criterion passed and which did not.

**Acceptance Criteria:**

**Given** the campaign and bound readiness-policy revision
**When** EvaluationReport is generated
**Then** each criterion has exactly one `pass|fail|not_evaluated` row with reason, evidence references, and literal numerator and denominator where applicable
**And** missing criteria make overall readiness `incomplete`, any failed criterion makes it `fail`, and only all-pass makes it `pass`. (FR28)

**Given** expected-detection, expected-outcome, false-warning, and non-applicable populations
**When** metrics are computed
**Then** misses, false detections, errors/timeouts, repeated-run disagreements, latency, cost, and comprehension remain separate literal measures
**And** technical errors remain in applicable denominators while `insufficient_data` and `not_analyzed` are not scored as negative observations. (NFR2, NFR3)

**Given** a false check request, missing mandatory case, or incorrect required outcome
**When** readiness is evaluated
**Then** the relevant criterion fails, including the zero-false-warning gate
**And** no provider winner or decorative aggregate score is generated.

### Story 4.6: Inspect Prototype Readiness

As a jury member,
I want to open each readiness criterion and its evidence,
So that I can reproduce the prototype's readiness decision.

**Acceptance Criteria:**

**Given** a generated or incomplete EvaluationReport
**When** I open `Готовность`
**Then** I see evaluation set identity, size, checksums, label coverage, sufficiency conditions, revisions, literal measures, and each criterion as `Пройдено`, `Не пройдено`, or `Нет данных`
**And** each row links to its runs and evidence without converting incomplete data to pass. (FR28, UX-DR23)

**Given** a failed, loading, or unavailable report
**When** the surface updates
**Then** failing or missing criteria remain explicit with the last known report time and nearby retry action
**And** the matrix uses semantic captions and headers, accessible expansion, Russian summary, and no ornamental score. (UX-DR26, UX-DR38)

### Story 4.7: Inspect Provider Comparison Separately

As a jury member,
I want a separate view of local and cloud comparison evidence,
So that I do not confuse model comparison with prototype readiness.

**Acceptance Criteria:**

**Given** a complete or incomplete comparison campaign
**When** I inspect Provider Comparison
**Then** candidate identity, profile revision, planned and terminal cells, failures, timeouts, missing cells, repeated disagreements, latency, and cost are shown separately from readiness criteria
**And** an incomplete matrix says `Сравнение не завершено` and shows no winner. (FR29, UX-DR24)

**Given** a candidate's cloud or local admission evidence
**When** I expand technical detail
**Then** the view distinguishes measured performance, commercial/data gates, returned identity, and unresolved gaps
**And** neither the comparison report nor UI publishes an ActiveObserverConfiguration or treats a shortlisted candidate as a selected winner.

## Epic 5: Zone plans, located equipment, and review signals

This increment extends the completed Rapid MVP. The source XLSX is a work catalog, not a schedule. Existing evidence, profile, and comparison revisions remain immutable.

1. **Catalog and plan:** Given the supplied XLSX, importing it preserves 377 distinct source rows, raw/date-formatted codes, cell coordinates, and applicability; given a zone, a manager can save parallel work entries as an immutable, optimistic plan revision.
2. **PNG and located observations:** Given JPEG/PNG input and an admitted local profile, a completed run retains original bytes and returns frame-bound normalized boxes for every detected object; old/cloud runs do not invent boxes.
3. **Stage hypotheses:** Given corroborating equipment and scene features in the same frame, a run proposes excavation, concreting, or roadwork with supporting frame IDs; without corroboration it returns no decisive stage. A confirmation is stored separately.
4. **Signals:** Given an explicitly bound plan revision and enough usable frames, equipment checks use all concurrent work entries and create idempotent, reviewable signals; given an expired unfinished entry, the calendar signal states only that completion is unconfirmed.
5. **Release gate:** Given a group-disjoint labeled eight-class set, report class, box, stage, signal, and laptop-speed results; only admitted capabilities appear ready. Reproduce the original-PNG demo and verify jury access, presentation, accompanying document, and camera guidance.

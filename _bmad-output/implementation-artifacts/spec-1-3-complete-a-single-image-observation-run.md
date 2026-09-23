---
title: 'Complete a Single-Image Observation Run'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '9133196036af73e503b426f2911c5c66bc93ffd7'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Admission proves the observer and evidence pipeline, but a user cannot submit a single image, receive an asynchronous run, or read its committed result.

**Approach:** Add a single-image observation-only API and a guarded executor path using the admitted profile, verified artifact publication, and the existing six-stage persistence model.

## Boundaries & Constraints

**Always:** Require service readiness and an enabled admitted profile; validate explicit scenario, observation area, period, image format and decode before creating run/evidence references. Default requested classes to `excavator` and `dump_truck`; retain explicitly requested unsupported classes as `not_analyzed`. Bind immutable input ordinal `0`, context, policy and taxonomy snapshots, profile and authorization revision, and six stages in one run transaction after final-object verification. Serialize submission idempotency and reject reuse of a key for different logical bytes/context. Claim, renew, reserve, complete, and fail work through current ownership and authorization fences; read exactly the reserved bytes and keep provider inference outside transactions. Persist source-linked closed states and exactly one projection only on success; render stored state from the API without leaking secrets or signed URLs.

**Never:** Execute the observer in the submit request, use a draft/revoked/test profile, silently change model or device, infer absence from one frame, require/evaluate a rule revision, create a projection on technical failure, or expose native confidence/count/geometry as portable rule facts. Do not implement ordered-series or web UI stories here.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Valid submit | One supported decodable image, observation-only intent, explicit context, idempotency key | Queued `run_id`; verified input and one ordinal-0 reference | Stable validation and readiness codes |
| Duplicate or changed request | Same key and same/different logical request, including concurrent delivery | Same run or same stored terminal submission error for identical request; never duplicate reference/call | Different request returns stable key-conflict code |
| Unusable accepted frame | Valid format but observer cannot assess it | Per-class `insufficient_data` with reason and source; successful `observations_only` result | No false non-detection |
| Unsupported class | A requested class outside admitted taxonomy | `not_analyzed` with reason and source | No provider call for unsupported class alone |
| Execution failure | Timeout, provider/malformed output, missing artifact, stale lease or authorization | Failed run, dependent stages skipped, no projection | Stable safe code, no fallback |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:447` -- Story 1.3 acceptance; read-only.
- `_bmad-output/implementation-artifacts/epic-1-context.md:20` -- cross-story evidence, stage, and authorization constraints; read-only.
- `backend/app/main.py:28` -- readiness gates and single claim loop; only health routes exist at line 86.
- `backend/app/application/executor.py:7` -- dormant loop with bound profile/revision; extend for ordinary queued runs.
- `backend/app/application/admission.py:57` -- existing temp/verified/final publication sequence to reuse without coupling user requests to admission fixtures.
- `backend/app/adapters/artifacts.py:24` -- integrity verification and content-addressed publication/read primitives.
- `backend/app/adapters/postgres.py:112` -- atomic admission run/stage inserts; reservation at 142, completion at 162, publication at 202, terminal projection at 230, failure at 259, authorization check at 340. Add ordinary methods with live-lease fencing, preserving admission behavior.
- `backend/migrations/versions/0002_admission.py:42` -- schema supports profiles/runs/stages/invocations/artifacts but `run_inputs.fixture_id` is required and request idempotency, context/snapshots, state reasons are absent; add a new migration.
- `backend/app/domain/observations.py:7` -- two portable classes and six stage names; normalization at 79 currently permits only two states.
- `backend/app/profiles/grounding_dino.py:100` -- pinned offline CPU adapter; `observe` at 111 returns native evidence and two presence states.
- `backend/tests/test_startup.py:90`, `backend/tests/test_admission.py:80` -- real PostgreSQL/S3, HTTP, and CPU patterns; extend without using admission fixtures as acceptance data.

## Tasks & Acceptance

**Execution:**
- `backend/migrations/versions/0003_single_image.py` -- add ordinary request idempotency, publication intents that can precede a run while retaining admission linkage, immutable context/policy/taxonomy snapshots, nullable user input fixture identity, input artifact linkage, per-class reasons and source references, and DB constraints for one projection and class state per input.
- `backend/app/domain/observations.py` -- validate the closed four-state taxonomy and reason requirements; retain native evidence separately.
- `backend/app/adapters/postgres.py` -- add atomic idempotent submission and input reference commit, authorized queued claim/lease renewal, fenced invocation reservation and completion, terminal success/failure, and read-only run projection; leave admission behavior intact.
- `backend/app/application/submission.py`, `backend/app/main.py` -- validate/decode an image and explicit context, coordinate publication and idempotency, expose submit and run-read API with stable safe errors and state-based responses.
- `backend/app/application/executor.py`, `backend/app/config.py` -- use the existing single loop to claim ordinary work, verify current binding and artifact, run the pinned CPU observer with bounded execution, publish native evidence, and commit guarded terminal transitions.
- `backend/tests/test_single_image.py` -- exercise matrix cases through HTTP and real PostgreSQL/S3, including concurrent duplicates, revocation/lease overlap, all-insufficient success, and technical failures; use only contract/development fixtures.
- `README.md` -- document request/read contract, required offline runtime setting, and CLI verification.

**Acceptance Criteria:**
- Given a ready service and admitted enabled profile, when a valid single-image observation-only request is submitted, then the API returns a queued authoritative `run_id` without requiring a rule revision.
- Given invalid format or undecodable bytes, when submitted, then the API returns a stable file error and no run, evidence reference, or observer call exists for those bytes.
- Given repeated identical keyed submissions, when concurrent or sequential requests arrive, then the API returns the same run or terminal submission error and only one input reference and observer invocation can result.
- Given a queued run, when the executor claims it, then the API shows committed stage changes and the invocation is durably reserved with current authorization and fencing before the verified input reaches the observer.
- Given a successful assessable observation, when the run completes, then the API shows one source-linked closed state for each class, attributed native evidence, and exactly one immutable `observations_only` outcome.
- Given an accepted but unassessable frame, when processing completes, then the API shows reasoned `insufficient_data` states and one `observations_only` outcome without an absence claim.
- Given timeout, provider error, malformed output, missing artifact, or rejected guarded write, when processing ends, then the API shows a failed run with dependent stages skipped and no result projection or fallback.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 17 findings — high 0, medium 11, low 1, false 5, maybe-false 0
- findings:
  - `[false]` `[reject]` Reconciliation can fail a live upload in another instance — the epic runs exactly one service instance; startup reconciliation occurs before that instance accepts submissions.
  - `[medium]` `[patch]` A duplicate can time out and fail the original publisher — removed the duplicate's timeout write; it waits for the owner's terminal result without mutating the reservation.
  - `[low]` `[reject]` Renewal failure leaves a bounded inference running — reservation was authorized before the call and completion is fenced; the remaining CPU work is bounded by the profile timeout, while cross-process cancellation adds disproportionate control paths.
  - `[medium]` `[patch]` The API parses an unbounded body before validation — bounded streamed request bytes at the HTTP entrypoint before JSON parsing.
  - `[medium]` `[patch]` JPEG pixels load before the dimension check — moved the dimension check before decoding compressed pixels.
  - `[false]` `[reject]` Routes lack an authentication layer — this prototype binds Uvicorn to loopback and the story defines no remote multi-user access contract; adding one would create an unsupported product surface.
  - `[medium]` `[patch]` States and native detections can contradict — added presence-mapping validation before persistence.
  - `[medium]` `[patch]` Queued work for an old binding can remain forever after restart with a new binding — cleanup now fails queued work whose authorization is no longer enabled at its bound revision.
  - `[false]` `[reject]` Nullable artifact links permit ordinary-run source loss — admission rows require nullable fields, while ordinary creation and completion attach and verify the source in the same guarded application transactions; no ordinary caller writes a missing link.
  - `[medium]` `[patch]` No automated real observer API path — added a local admitted-profile and offline CPU API test.
  - `[false]` `[reject]` Reconciliation races another instance's upload — the required single-instance startup sequence excludes that simultaneous second instance.
  - `[medium]` `[patch]` Spawned child can survive a completed queue result — added termination and join before returning or failing.
  - `[false]` `[reject]` Renewal exception clearing readiness is itself a defect — when ownership or authorization cannot be renewed, clearing readiness is a conservative service-health response; terminal completion remains fenced.
  - `[medium]` `[patch]` Expired running work waits for restart to recover — the active loop now runs guarded recovery after an execution attempt.
  - `[medium]` `[patch]` Background claim loop lacks an executing submission test — added submit-to-terminal coverage with the active loop.
  - `[medium]` `[patch]` Spawned observer process lacks a test — added actual process transfer and bounded-timeout coverage.
  - `[medium]` `[patch]` Product-level execution proof is absent from automated coverage — the admitted-profile test now covers readiness, API submission, active loop, and offline CPU inference.

## Design Notes

An idempotency record and PublicationIntent must exist before a non-transactional S3 upload, but the queued `AnalysisRun` and its input reference may be committed only after the final object is verified. The current PublicationIntent requires a run FK, so the migration must allow a pre-run intent and link it atomically at run creation. Keep an in-progress reservation and a stable terminal outcome so retries and concurrent requests never race to create separate runs. Preserve failed/unreferenced publication evidence for reconciliation without treating it as a run input.

## Verification

**Commands:**
- `cd backend && uv lock --check && uv run pytest -q` -- committed dependencies and focused real-service contracts pass.
- `git diff --check` -- no whitespace errors.
- Submit through HTTP with the admitted local profile and poll the run API -- queued/running/terminal state and verified evidence agree with PostgreSQL/S3 readback.

## Auto Run Result

Status: done

Implemented single-JPEG observation-only submission and read APIs, request idempotency, verified S3 input/native publication, immutable run snapshots, and a fenced asynchronous CPU executor. The API reports persisted stages, source-bound class observations, and exactly one successful `observations_only` projection; technical failures retain no projection.

Files changed:
- `backend/migrations/versions/0003_single_image.py` -- add ordinary submission, snapshot, source, and idempotency schema.
- `backend/app/adapters/postgres.py` -- persist and read ordinary runs with authorization, lease, publication, and terminal guards.
- `backend/app/application/submission.py`, `backend/app/main.py` -- validate and publish a bounded request, then expose submit/read endpoints.
- `backend/app/application/executor.py`, `backend/app/config.py`, `backend/app/domain/observations.py` -- process queued work with the pinned offline observer and closed source-linked states.
- `backend/tests/test_single_image.py`, `README.md` -- cover and document the API and real local CPU path.

Review: 17 findings; 11 medium patch findings fixed, one low and five false findings rejected with individual reasons in the triage log, none deferred. The global ordinal-0 constraint was also removed before review so later ordered-series inputs remain possible. Reads of run lifecycle, stages, and observations use one repeatable-read snapshot.

Verification: `uv lock --check` passed with a writable temporary UV cache; `uv run pytest -q` passed 38 tests against local PostgreSQL/S3 and the pinned offline CPU observer after review patches. `git diff --check` and `git diff --cached --check` passed. A real HTTP run from the implementation pass reached `succeeded/observations_only`; PostgreSQL showed one input, one completed CPU invocation, one projection, and two S3 artifacts passing SHA-256 readback. Local application and test databases are at migration `0003_single_image`; an obsolete ordinal constraint left by an earlier local migration draft was removed from the application database and read back absent.

Follow-up review recommended: true. Eleven medium findings were patched in this pass; a true concurrent overlap of lease renewal failure and recovery/completion remains unverified. No push was performed.

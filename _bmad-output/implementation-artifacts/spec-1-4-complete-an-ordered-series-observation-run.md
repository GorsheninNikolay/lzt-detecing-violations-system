---
title: 'Complete an Ordered-Series Observation Run'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: 'c89e3f678534ae0b9481f35207044d6c279f6b38'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The ordinary observation API and executor accept one image only. A manager cannot submit an ordered series or inspect which frame supports each observation.

**Approach:** Extend the ordinary observation path to accept an explicit ordered image array, retain one run with a distinct input reference per array element, observe each frame under the same fenced run and profile, and expose frame-bound observations and series evidence.

## Boundaries & Constraints

**Always:** Require two or more supported, decodable JPEG images with one explicit scenario, area, and period. Array position is the only initial order; preserve duplicate checksums as distinct inputs with stable IDs and contiguous zero-based ordinals. Hash idempotency over ordered image hashes and logical context. Publish and verify every input before atomically committing the queued run and manifest. Reserve each provider call under the current run lease and enabled authorization before inference. Retain one closed state per requested class per frame, with source ID, ordinal, reason where required, and completed invocation for provider-derived states. Preserve secondary native evidence attribution. Complete series aggregation only after all frames are represented; its evidence must remain frame bounded and never infer site-wide absence. A technical call or persistence failure fails the run with no ResultProjection. Keep the single-image API and admission path working.

**Never:** Reorder by filename, EXIF, receipt time, checksum, or publication timing; collapse duplicate inputs because bytes deduplicate; silently retry or switch provider/device; convert unassessable frames into non-detection; introduce rule evaluation, a site-level claim, or web UI in this story.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Ordered series | Two or more images in JSON array | One queued run; ordinal and stable ID per item; one frame-bound class set per item | Stable validation error for malformed request |
| Duplicate bytes | Same JPEG twice at different positions | Two manifest items and observations, distinct source references | Artifact byte deduplication may remain |
| Changed order | Same idempotency key and reversed distinct images | Conflict, no second run | `idempotency_key_conflict` |
| Unassessable frame | Accepted frame yields no assessable scene | Per-class `insufficient_data` with reason and source | Run can still succeed |
| Technical failure | One provider call or verified read fails | Failed run; no projection; retained prior invocation evidence | No false frame non-detection |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:500` -- Story 1.4 acceptance; read-only.
- `_bmad-output/implementation-artifacts/epic-1-context.md` -- cross-story evidence and policy constraints; read-only.
- `backend/app/application/submission.py:22` -- existing validation, idempotency, and verified publication; extend shared path with ordered images.
- `backend/app/main.py:118` -- bounded request streaming and API response; add series route without changing single-image contract.
- `backend/app/adapters/postgres.py:410` -- atomic submission, claim, reservation, completion, and readback; remove ordinal-0 assumptions for series while preserving admission methods.
- `backend/app/application/executor.py:129` -- single-frame claim loop; observe frames sequentially under one renewable run lease.
- `backend/migrations/versions/0002_admission.py:54` and `0003_single_image.py:10` -- current run input key, unique invocation per run, and observation key need per-input association in a new migration; do not rewrite historical migrations.
- `backend/app/adapters/artifacts.py:35` -- existing content-addressed upload and read integrity; reuse for each input.
- `backend/tests/test_single_image.py:91` -- real PostgreSQL/S3 contract patterns; retain all existing single-image tests.

## Tasks & Acceptance

**Execution:**
- `backend/migrations/versions/0004_ordered_series.py` -- add immutable stable input ID and per-input invocation/observation keys while preserving admitted and single-image rows.
- `backend/app/application/submission.py`, `backend/app/main.py` -- validate bounded explicit image array, hash canonical order, publish each item, and offer series submission with stable errors.
- `backend/app/adapters/postgres.py` -- atomically commit full ordered manifest, claim all inputs, reserve/record per-frame calls under current lease, aggregate only complete frame evidence, and read frame-ordered results.
- `backend/app/application/executor.py` -- process all frames sequentially and finish one fenced run; preserve incomplete evidence on technical failure.
- `backend/tests/test_ordered_series.py` -- exercise HTTP, PostgreSQL, and S3 paths for order, duplicate bytes, reversed idempotency, mixed assessability, partial technical failure, and source/invocation attribution.
- `README.md` -- document series request/read behavior and limits.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize story status with verified workflow outcome.

**Acceptance Criteria:**
- Given two supported frames and explicit context, when the series is submitted and processed, then readback exposes a contiguous ordered manifest and both class states tied to each stable input ID.
- Given two equal checksums, when the series completes, then two distinct input references and two sets of observations remain inspectable.
- Given one unassessable accepted frame, when aggregation completes, then its states are reasoned `insufficient_data` and no series or outcome field claims absence across the area.
- Given a technical failure in a later frame, when the executor terminates, then the run is failed, prior invocation evidence is retained, dependent stages are skipped, and no projection exists.
- Given the existing single-image and admission workflows, when the migration and executor change are applied, then their existing API and evidence behavior still passes.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 16 findings — high 0, medium 12, low 2, false 2, maybe-false 0
- findings:
  - `[medium]` `[patch]` Additional publication keys can collide with another submission's first key — intent UUIDs now form the unique publication keys; a collision regression is tested.
  - `[medium]` `[patch]` A series commit did not verify ownership of each extra intent — the commit now checks `submission_key` and rejects repeated or foreign intent IDs.
  - `[medium]` `[patch]` An invocation or observation could reference an input from another run — the migration now enforces the `(run_id, input_id)` relationship and tests cross-run rejection.
  - `[false]` `[reject]` Reservation could process a later ordinal first — the only ordinary caller iterates the ordered `frames` returned by `claim_ordinary`; no public caller can select an arbitrary input.
  - `[low]` `[patch]` All-unassessable supported frames recorded `unsupported_classes` — the skipped observation stage now uses a neutral reason covering unassessable frames and unsupported classes.
  - `[medium]` `[patch]` A duplicate request could wait forever for a stalled publisher — the shared wait is bounded and returns retryable `submission_in_progress` without changing publisher state.
  - `[low]` `[reject]` Downgrade after storing series rows cannot restore the old single-input keys — reducing populated series data to the prior one-invocation/one-class-pair schema would discard evidence; the migration's downgrade failure preserves it, and no rollback requirement was specified.
  - `[medium]` `[patch]` A later S3 read failure had no series-specific check — the test now retains the first frame's evidence, fails the run, and asserts no projection.
  - `[medium]` `[patch]` Backfill of existing rows lacked verification — a populated revision `0003_single_image` database is now upgraded and its admission and ordinary associations checked.
  - `[medium]` `[patch]` A stalled publisher could hold a series request indefinitely — same bounded-wait fix as the sixth finding, with an HTTP retry response check.
  - `[medium]` `[patch]` Sprint tracking still said `backlog` — synchronized it through `review` to `done` after full verification.
  - `[medium]` `[patch]` Existing data was absent from migration verification — same populated-upgrade test as the ninth finding, including cross-run integrity checks.
  - `[medium]` `[patch]` Interrupted series reconciliation lacked a multi-intent test — the new test checks all intents become quarantined and readiness succeeds.
  - `[medium]` `[patch]` Native evidence input-ID attribution was unasserted — the test now matches each API item to its ordered input and persisted invocation.
  - `[false]` `[reject]` The manager-facing UI was not implemented — Story 1.5 assigns the responsive image-ordering form to a separate story; Story 1.4's API readback is the current submission and inspection surface.
  - `[medium]` `[patch]` The requested sprint-status synchronization was absent — same `done` update as the eleventh finding.

## Design Notes

The public series request uses `images_base64` as an ordered JSON array. Keep each element's own publication intent and input ID even when the final content-addressed object key is shared. Use the existing single host claim loop and one run lease; do not add a second worker or queue.

## Verification

**Commands:**
- `cd backend && uv lock --check && uv run pytest -q` -- all real-service contracts pass.
- `git diff --check` -- clean patch formatting.
- Submit two images through HTTP, poll the run, and compare ordered API inputs/observations with PostgreSQL and verified S3 bytes.

## Auto Run Result

Status: done

Implemented ordered 2–8-image submission and per-frame evidence using the existing single-host claim loop. Each input retains a stable ID and ordinal, including duplicate bytes; each observer call and observation is bound to its input. Aggregation completes after every frame has closed states and makes no site-wide absence claim. Technical failures leave prior evidence and no projection.

Files changed: `backend/migrations/versions/0004_ordered_series.py` adds per-input keys, backfill, and composite integrity constraints; `backend/app/application/submission.py` and `backend/app/main.py` add bounded series submission and retryable duplicate handling; `backend/app/adapters/postgres.py` and `backend/app/application/executor.py` add ordered fenced persistence and execution; `backend/tests/test_ordered_series.py` covers the request matrix and migration/recovery cases; `README.md` documents the API; `sprint-status.yaml` records completion.

Review: 16 findings, including 12 medium and one low patched findings, one low finding rejected to preserve evidence on downgrade, and two false findings rejected with reasons above. Shared-root findings received the same fix. Follow-up review recommended: true, because the actual application database has not undergone the populated `0003` → `0004` upgrade; only isolated PostgreSQL databases were migrated and tested.

Verification: `uv lock --check` passed. The full backend suite passed `43 passed in 59.50s` against a newly created, migrated temporary PostgreSQL database, isolated MinIO bucket, and pinned offline CPU model snapshot. The temporary database was removed after the run. The HTTP/PostgreSQL/S3 series test exercised all five I/O matrix rows. `git diff --check` passed before final documentation edits; final patch formatting is checked at commit preparation. No application database migration, service deployment, or remote push was performed.

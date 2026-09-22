---
title: 'Admit the Initial Local Observer Through the Evidence Pipeline'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '663a0c60c75c9d38e7298be572f3b3a98081cba6'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The service has no runnable observer or immutable admission evidence, so later analyses cannot bind to a verified local profile.

**Approach:** Install and fingerprint the pinned Grounding DINO Tiny CPU runtime, execute a versioned rights-cleared smoke set through the ordinary PostgreSQL and S3 evidence pipeline, and authorize only an immutable successor of a fully successful draft profile.

## Boundaries & Constraints

**Always:** Use Grounding DINO Tiny revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e` and Apple M3 Pro arm64 CPU-only, 12-core, 36-GB baseline. Pin runtime and per-file model hashes; load offline during execution. Reserve each invocation and immutable inputs before inference; publish and verify every referenced artifact before structured references commit. Retain literal device, identity, latency, memory, failures, rights, and source-group evidence. Admission fixtures must be disjoint by checksum and source/site/camera/time-sequence group from every other tier. Failed or incomplete smoke leaves the profile draft and unauthorized.

**Never:** Substitute test-observer results for a real admission, infer returned identity from requested identity, silently use MPS/CUDA or CPU fallback, turn counts/confidence/geometry into portable rule semantics, expose secrets or signed URLs, mutate a draft into an admitted profile, or treat a single-image non-detection as site-wide absence.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Complete CPU smoke | Pinned offline snapshot and approved disjoint fixture manifest | One immutable admission run and observations-only projection per fixture; immutable admitted successor and enabled authorization | None |
| Incomplete or overlapping set | Missing rights/hash/group or overlap with another tier | No admission runs or authorization | Stable manifest error without secrets |
| Runtime or evidence failure | Failed decode, publication, CPU execution, normalization, identity, or terminal commit | Retained failed run; dependent stages skipped; no projection or authorization | Stable failure reason; keep reservation and partial evidence |
| Unauthorized execution | Test observer, draft profile outside admission, revoked or absent authorization | Reject startup or submission before provider call | Stable authorization error |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:379` -- authoritative Story 1.2 acceptance; read-only.
- `_bmad-output/implementation-artifacts/epic-1-context.md:20` -- cross-story evidence and profile boundaries; read-only.
- `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:161` -- AD-28 publication; AD-30 profile at line 167; AD-34 binding at line 185; AD-36 invocation at line 197; AD-37 CPU baseline at line 203; read-only.
- `backend/migrations/versions/0001_seed.py:13` -- only skeleton run, stage, and publication-intent tables; extend with a new migration, preserving existing revision.
- `backend/app/adapters/postgres.py:22` -- production SQLAlchemy store and reconciliation/recovery; reuse engine and transaction pattern.
- `backend/app/adapters/artifacts.py:13` -- S3 health probe only; add publication beside it, isolated from `health/`.
- `backend/app/main.py:25` -- readiness gates and claim loop; guard all non-admission runtime bindings.
- `backend/app/application/executor.py:4` -- dormant loop, no pipeline yet; evolve the same application-owned executor.
- `backend/app/domain/`, `backend/app/ports/`, `backend/app/profiles/` -- existing package boundaries, currently empty.
- `backend/pyproject.toml:1` and `backend/uv.lock` -- exact backend lock, no vision dependencies; add pinned runtime and refresh committed lock.
- `backend/tests/test_startup.py` -- real PostgreSQL/S3 test pattern and isolated resources; keep contract checks on these adapters.
- `artifacts/dataset/Ссылки на открыте датасеты.txt` -- organizer-provided source list includes the Kaggle Construction equipment dataset; read-only.
- `/private/tmp/kaggle-construction-equipment.zip` -- locally downloaded 19,982 JPG images with matching YOLO TXT labels; class `0` is dump truck and `1` is excavator according to the linked Kaggle card. Select four fixtures from source groups `1235` (both), `1233` (dump only), `1422` (excavator only), and `1325` (neither); reserve each whole group from other tiers. Do not commit the 16-GB archive.
- `artifacts/dataset/Строительная_техника.zip` -- separate organizer archive of 100 PNG images without labels; do not confuse it with the annotated Kaggle download.
- `evaluation/README.md:1` -- held-out evaluation tier only; no held-out fixture manifest exists yet.

## Tasks & Acceptance

**Execution:**
- `backend/pyproject.toml`, `backend/uv.lock` -- pin the supported Grounding DINO Transformers/PyTorch/image runtime and verify `uv lock --check` plus frozen sync.
- `backend/app/profiles/grounding_dino.py`, `backend/app/profiles/__init__.py` -- implement exact-revision offline snapshot preparation, per-file digest verification, adapter bundle fingerprint, explicit CPU execution, returned identity/device capture, and secret-free native metadata.
- `backend/migrations/versions/0002_admission.py`, `backend/app/adapters/postgres.py` -- persist immutable profile revisions, CAS authorization, fixture manifests, run inputs/snapshots/stages, fenced invocations, observations, projections, artifact metadata and publication-intent transitions.
- `backend/app/adapters/artifacts.py` -- implement AD-28 temporary upload, digest/size verification, exclusive or verified-deduplicated final publication, integrity-checked read, and reference transition; do not reuse health objects.
- `backend/app/domain/observations.py`, `backend/app/application/admission.py` -- validate manifest and exclusion groups, construct one six-stage run per fixture with positive bootstrap watchdog, normalize two closed states, record literal measurements/failures, and finalize immutable successor plus enabled authorization from complete-smoke p95.
- `backend/app/main.py`, `backend/app/application/executor.py` -- expose an operator admission entrypoint through the guarded single executor and reject non-admission draft, test, missing-evidence, and revoked profiles.
- `backend/admission/fixtures/`, `backend/admission/manifest.json` -- extract only four selected JPGs with matching labels from the local ZIP, commit their SHA-256, source URL, organizer link, declared CC0, provenance caveat, context, and reserved source-group IDs in one versioned manifest. The selected archive members are `train/images/1235_08_47_31_983151-2023-11-10.jpg`, `train/images/1233_09_26_32_077311-2023-11-10.jpg`, `train/images/1422_12_49_39_102843-2023-09-22.jpg`, and `train/images/1325_11_08_44_816463-2023-09-22.jpg`; keep the same basenames under `fixtures/`.
- `backend/tests/test_admission.py`, `README.md` -- exercise success and failure against PostgreSQL/S3, verify offline CPU smoke and secret redaction, document fixture extraction, model preparation and operator commands.

**Acceptance Criteria:**
- Given the pinned model snapshot and committed locks, when the operator prepares the draft, then its canonical hash covers adapter, model files, preprocessing, prompts, taxonomy, contracts, rights, and runtime; offline load and CPU-only validation succeed on the required Mac.
- Given a complete versioned rights-cleared set and exclusion inventories, when admission starts, then checksum and source-group overlaps are rejected before one immutable admission run per fixture is created.
- Given each admission run, when inference begins, then its positive bootstrap watchdog, input and profile snapshots, ordered stages, and fenced invocation reservation are committed before the exact reserved bytes reach the model.
- Given native model output, when normalization and publication complete, then each frame has one invocation-linked closed state per required class and native details remain attributed evidence outside portable rules.
- Given a successful fixture, when the run becomes terminal, then verified S3 bytes precede PostgreSQL artifact references and exactly one `observations_only` projection exists.
- Given all fixtures succeeded with actual CPU device and literal measurements, when admission finalizes, then one immutable admitted successor and enabled CAS authorization commit atomically with the specified p95-derived timeouts.
- Given any technical or evidence failure, when its run terminates, then it remains failed without a projection, dependent stages are skipped, the draft has no enabled authorization, and no secret appears in stored or rendered evidence.
- Given a test observer or profile without immutable admission evidence, when runtime, demonstration, retry, or comparison attempts to bind it, then startup or submission rejects it before invocation.

## Spec Change Log

- 2026-09-23: The owner accepted the Kaggle card's declared CC0 license and organizer-provided source link for local prototype smoke. The local ZIP provides paired YOLO labels; other annotated datasets are unnecessary for zero-shot execution. Reserve four distinct source groups and preserve the unresolved original-camera provenance as a manifest caveat.

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 18 findings — high 3, medium 8, low 0, false 7, maybe-false 0
- findings:
  - `[false]` `[reject]` Missing `OBSERVER_PROFILE_ID` still permits health readiness — no ordinary submission or observer claim exists yet; an absent configured profile is not an invalid configured profile.
  - `[false]` `[reject]` Revocation leaves a startup binding tuple — the current claim loop performs no observer call or submission, so the stale tuple cannot start one; future call paths must revalidate authorization.
  - `[medium]` `[patch]` The CLI permits arbitrary admission manifests — restrict the runtime command to the approved committed manifest so a self-declared CC0 input cannot replace the owner's chosen set.
  - `[high]` `[patch]` The CLI permits arbitrary model digest lists — restrict runtime to the committed model-file hashes so compatible but unapproved weights cannot retain the pinned requested identity.
  - `[false]` `[reject]` Empty exclusion inventories undermine the present split — the owner confirmed no other annotated sets exist; these inventories record the current empty tiers and validation rejects overlap when entries are added.
  - `[false]` `[reject]` Admission does not grade detections against fixture labels — Story 1.2 admits the executable evidence pipeline; detection quality belongs to the later held-out evaluation, and the negative fixture's real false positives are retained as evidence.
  - `[medium]` `[patch]` Completion accepts an unrelated returned checkpoint digest — require exact equality with the verified safetensors hash before completing or authorizing a profile.
  - `[false]` `[reject]` A failed attempt leaves its invocation reserved — the reservation intentionally records an uncertain attempt; the run and stage retain the failure code without inventing a completed external call.
  - `[medium]` `[patch]` A corrupt image can leave `frame_usability` succeeded — validate decoding before reservation and fail that stage with downstream dependency skips.
  - `[medium]` `[patch]` Aggregation and rule stages claim success without execution — mark them skipped with an explicit not-applicable reason in observation-only admission runs.
  - `[medium]` `[patch]` Measured latency excludes cold model loading inside the watchdog — measure the entire reserved invocation so derived timeouts include cold start.
  - `[false]` `[reject]` Published temporary S3 bytes are retained — AD-28 forbids implicit evidence-byte deletion and defers retention/purge to a later explicit policy.
  - `[high]` `[patch]` Recovery can fail a run while completion writes invocation and observations — fence completion on the live run state, matching lease owner, and unexpired lease.
  - `[medium]` `[patch]` Exclusion overlap ignores the explicit camera/time-sequence group — compare that field as well as `source_group` so renamed source groups cannot collide.
  - `[medium]` `[patch]` Unequal native label/score/box arrays are truncated by `zip` — reject malformed output before normalization.
  - `[false]` `[reject]` The CPU admission test omits detection-vs-label assertions — accuracy is deliberately evaluated later; the required admission test verifies closed, source-linked observations and retained native evidence.
  - `[medium]` `[patch]` The test accepts any checkpoint identity suffix — assert the exact committed safetensors digest after adding the runtime identity guard.
  - `[high]` `[patch]` Only an isolated test database holds a verified profile — current readback found zero admitted profiles in the application database and four in the test database; run final admission against the local application database and verify retained enabled authorization after fixes.

## Design Notes

The admission-smoke fixture set is an operator-owned evidence input, not a synthetic stand-in. Its exact image sources and rights determine whether an `admitted` result can truthfully exist. A temporary implementation test set can prove code paths but cannot become admission evidence.

Use CLI and non-GUI interfaces only. Preserve unrelated user work and the current branch.

## Verification

**Commands:**
- `cd backend && uv lock --check && uv sync --frozen` -- exact committed environment resolves.
- `cd backend && uv run pytest` -- PostgreSQL/S3 contract checks pass, including failure and secret paths.
- Run the documented offline admission command with network disabled on this Apple M3 Pro -- every manifest fixture has a terminal, evidenced run and an authorized successor exists only after full success.

## Auto Run Result

Status: done

Implemented and ran the pinned offline Grounding DINO Tiny CPU admission pipeline. The application database retains admitted successor `78977402-bfdc-4520-8aa8-1773c86e3fbd` with enabled authorization revision 1. Its four runs succeeded; each has four succeeded stages, two explicitly skipped inapplicable stages, two observations, and one `observations_only` projection. Eight referenced S3 objects passed size and SHA-256 readback.

Files changed:
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/admission/model-files.json` -- pin runtime dependencies and each model snapshot file digest.
- `backend/admission/manifest.json`, `backend/admission/fixtures/`, `backend/admission/exclusions/` -- commit four distinct-source admission fixtures, rights evidence, and disjointness inventories.
- `backend/migrations/versions/0002_admission.py`, `backend/app/adapters/postgres.py` -- persist immutable profile, run, invocation, stage, observation, projection, publication, and authorization evidence.
- `backend/app/adapters/artifacts.py` -- publish and integrity-check content-addressed S3 evidence.
- `backend/app/profiles/grounding_dino.py`, `backend/app/domain/observations.py`, `backend/app/application/admission.py` -- run pinned CPU inference, validate fixtures, normalize observations, and finalize admission.
- `backend/app/application/executor.py`, `backend/app/main.py` -- reject invalid configured runtime bindings at startup.
- `backend/tests/test_admission.py`, `backend/tests/test_startup.py`, `README.md` -- verify and document real PostgreSQL/S3/CPU admission and startup contracts.

Review: 18 findings; 11 grouped or direct patches applied (high 3, medium 8), seven false findings rejected with individual reasons in the triage log, none deferred. The operational-profile finding was resolved by admitting and reading back the final adapter revision in the application database.

Verification: `uv lock --check` passed; `uv sync --frozen --extra test` passed; `uv run pytest -q` passed 33 tests against Podman PostgreSQL/MinIO and the exact offline M3 Pro CPU model. Application database/S3 startup gates passed. A separate final four-fixture application admission and readback confirmed enabled authorization, CPU device on every invocation, literal latency and memory, 60-second image and 600-second batch timeouts, and integrity of all eight referenced S3 artifacts. `git diff --check` and `git diff --cached --check` passed.

Follow-up review recommended: true. The high-severity lease-fencing repair was exercised by state-transition tests, but a controlled concurrent recovery/completion overlap against PostgreSQL has not yet been run. Model detection accuracy remains for held-out evaluation; the admission smoke observed false positives on the fixture labeled with neither class. Original-camera provenance remains unverified beyond the owner-accepted Kaggle CC0 declaration and organizer-provided link for this local prototype smoke.

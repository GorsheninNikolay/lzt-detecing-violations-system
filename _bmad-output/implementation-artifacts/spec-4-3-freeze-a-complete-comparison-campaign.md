---
title: 'Story 4.3: Freeze a Complete Comparison Campaign'
type: 'feature'
created: '2026-09-25'
status: 'done'
baseline_revision: '68f5934493bd3e94c62f24a2f7c7d9191701521f'
review_loop_iteration: 2
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      Story 4.4 must add guarded queued, running, and terminal transitions for comparison cells.
    evidence: |-
      The Story 4.3 migration deliberately holds every linked run in planned state until input artifacts and ordered execution exist. Story 4.4 must add its activation and recovery transitions without changing frozen bindings.
    location: >-
      backend/migrations/versions/0010_comparison_campaign.py:guard_comparison_run
    severity: medium
---

<intent-contract>

## Intent

**Problem:** No campaign owner or planned cells exist. A later run could omit failed fixtures or compare changed configurations without exposing that change.

**Approach:** Atomically freeze the accepted evaluation revision, two admitted profiles, all execution and interpretation revisions, six ordered scenario fixtures, and the complete three-repeat matrix. Materialize one planned AnalysisRun for each cell; execution is Story 4.4.

## Boundaries & Constraints

**Always:** The campaign has 36 cells: 3 repeats × 6 fixtures × 2 candidates. The six fixtures preserve all eleven frame ordinals, including multi-image series and distinct fixtures even if image checksums repeat. Only enabled Grounding DINO Tiny Apple M3 Pro CPU and Yandex AI Studio Qwen3.6 profiles qualify. Validate current authorization and Qwen's exact allowlist against every frame. Freeze policy, rule, taxonomy, preprocessing, profile/authorization revisions, timeouts, concurrency 1, SDK retries 0, and stable candidate/fixture ordinals in one transaction. A changed configuration creates a new campaign revision; the old manifest and cell map remain immutable.

**Never:** Execute an observer, upload image bytes, use held-out data for admission or tuning, infer a winner or active provider, insert RF-DETR/Kimi/hybrid/fallback, or use checksum as cell identity. Planned rows must not be claimed by the ordinary worker before Story 4.4 activates them.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Complete prerequisites | Frozen eleven-frame revision and exact admitted pair | One immutable manifest, 36 distinct planned runs and ordered cells | No observer call |
| Missing gate | Missing/revoked profile, expired Qwen evidence, wrong revision or hash scope | No campaign or cells persist | Return specific safe gate failure |
| Concurrent or changed freeze | Repeated request or modified configuration | No partial/overwritten matrix; changed request creates separate revision | Explicit duplicate or revision result |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:931` and `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:69,189` — 36-cell campaign, tuple order, one bound run per cell, no selection.
- `backend/migrations/versions/0009_evaluation_set.py` — immutable evaluation revision and decision; extend with a new migration, preserving prior rows.
- `backend/app/adapters/postgres.py:53,516,603,671` — evaluation freeze, authorization verification, ordinary run binding and worker claim. New campaign writes must be transactional and planned state must stay outside ordinary claim.
- `backend/app/domain/evaluation_set.py:14` and `evaluation/held-out-v1.json` — six scenario groups and eleven accepted frame records; read the persisted revision as authority, not the current file.
- `backend/app/profiles/grounding_dino.py:56`, `backend/app/profiles/cloud_api.py:270`, `backend/app/domain/rule.py:11` — profile revision/preprocessing/runtime values and rule/policy snapshots.
- `backend/app/application/evaluation.py` and `backend/pyproject.toml` — existing operator CLI entry point; add campaign freeze/readback command without remote inference.
- `backend/tests/test_evaluation_set.py` — PostgreSQL fixture and freeze tests to extend for atomicity, immutability and duplicate hash accounting.
- `_bmad-output/implementation-artifacts/spec-4-2-admit-the-required-cloud-candidate.md` — current Qwen evidence was verified in isolated local PostgreSQL, not a deployed application database; local profile availability in that same DB remains to be checked before a live campaign freeze.

## Tasks & Acceptance

**Execution:**
- `backend/migrations/versions/0010_comparison_campaign.py` — persist immutable manifest and cell keys; require `binding_kind=comparison_cell`, guard frozen run identity/configuration against UPDATE or DELETE, and allow only an explicit future Story 4.4 activation transition. Reject downgrade while any campaign exists so its planned evidence is not deleted.
- `backend/app/domain/comparison_campaign.py` — construct the six-fixture, two-candidate, three-repeat manifest; validate each frozen scenario outcome and requested-class contract from the persisted evaluation revision, require finite positive timeouts and fixed concurrency/retries, and require the admitted local runtime identity to match the Apple M3 Pro CPU baseline.
- `backend/app/adapters/postgres.py` — verify both admitted enabled profiles, cloud scope, profile hash under the transaction lock, a matching accepted-decision manifest hash, and current gates; atomically insert manifest and 36 planned runs with rule snapshot retained in every run. Preserve every frame's distinct observation area in the fixture binding; read back frozen identity and order.
- `backend/app/application/evaluation.py` and `backend/pyproject.toml` — expose explicit freeze and readback CLI using selected evaluation and profile UUIDs, mapping normal admission failures to safe operator errors.
- `backend/tests/test_comparison_campaign.py` — verify all 36 run bindings against manifest profile, policy, rule, taxonomy, context, and requested classes; include the two-area insufficient fixture, invalid timeout values, duplicate checksums in separate persisted fixture cells, accepted-decision hash mismatch, expired/revoked cloud gates, wrong candidate, simultaneous freeze, rollback, and distinct valid successor revision. Exercise the real admission gate.
- `backend/tests/test_comparison_campaign.py` — run the operator CLI for a rejected freeze and missing campaign, asserting safe JSON error and nonzero exit; verify downgrade refuses even a wholly planned campaign without deleting its evidence.

**Acceptance Criteria:**
- Given accepted evaluation and exact enabled profiles, when an evaluator freezes a campaign, then readback shows six ordered fixtures, two candidates, three repeats and 36 distinct planned AnalysisRuns with all configuration revisions bound.
- Given a duplicate image checksum in different fixtures, when cells are materialized, then both fixture ordinals retain separate run IDs and both remain in the denominator.
- Given any missing authorization, wrong candidate, expired cloud gate, or uncovered image hash, when freeze is attempted, then no campaign or planned run persists.
- Given a frozen campaign, when source configuration later changes, then the existing manifest and cells remain unchanged and a separately requested revision receives a new identity.

## Spec Change Log

- 2026-09-25: Review found current-code scenario labels instead of persisted evaluation labels, incomplete CPU-host validation, missing per-run rule binding, and a revision test that bypassed real admission. The execution tasks now require persisted scenario validation, precise recorded runtime checks, locked profile-hash verification, actual admission rejection tests, safe CLI errors, and explicit downgrade behavior. This avoids a frozen manifest whose interpretation or candidate identity could drift. KEEP the atomic 36-cell transaction, planned state outside ordinary worker claims, immutable cell keys, and byte-free CLI readback.
- 2026-09-25: Second review found that campaign rows were immutable while bound runs could change, downgrade deleted planned evidence, the insufficient fixture lost its second area, decision hashes could diverge, and timeout validation admitted unusable values. The migration and store tasks now guard run bindings, keep campaign evidence on downgrade, preserve all area identities, match decision hashes, and reject nonfinite/nonpositive limits. Tests must assert persisted run bindings and the operator surface. KEEP the transaction-scoped real admission check, persisted scenario contract, 36-cell tuple order, and existing safe CLI rejection.

## Review Triage Log

### 2026-09-25 — Review pass
- verdicts: 16 findings — high 0, medium 12, low 0, false 4, maybe-false 0
- findings:
  - `[medium]` `[bad_spec]` Blind 1: observation-only runs omit the rule snapshot — amended tasks to retain the frozen rule revision on all 36 runs.
  - `[false]` `[reject]` Blind 2: sealing allegedly permits a wrong candidate/fixture run — the application inserts each run inside the corresponding candidate/fixture loop; unique bounded tuple keys plus exactly 36 rows cover the matrix, and no external pre-seal writer exists.
  - `[medium]` `[bad_spec]` Blind 3: fixture outcomes come from current constants — amended the domain task to validate and use the persisted revision's scenario contract.
  - `[medium]` `[bad_spec]` Blind 4: any CPU local profile could pass — amended the candidate task to validate recorded Apple M3 Pro CPU runtime identity.
  - `[medium]` `[patch]` Blind 5: normal admission rejection can escape the CLI as a traceback — safe error mapping is now explicit in the CLI task; repair follows re-derivation.
  - `[medium]` `[bad_spec]` Blind 6: a mutated admitted snapshot under a mocked gate masquerades as a new valid revision — amended tests to use immutable successor profiles and exercise the real admission gate.
  - `[medium]` `[bad_spec]` Blind 7: downgrade leaves activated comparison runs before restoring the old constraint — amended migration task to reject or safely handle that state without deleting evidence.
  - `[medium]` `[bad_spec]` Edge 1: profile hash can drift between preliminary check and locked read — amended the transactional gate to revalidate the locked hash.
  - `[medium]` `[patch]` Edge 2: ordinary admission failure produces a CLI traceback — same CLI repair as Blind 5.
  - `[medium]` `[bad_spec]` Edge 3: downgrade fails after cell activation — same migration amendment as Blind 7.
  - `[false]` `[reject]` Edge 4: duplicate checksum test uses a state current evaluation freeze rejects — it deliberately verifies that campaign identity is fixture ordinal rather than checksum if such a persisted revision is supplied; current accepted set remains distinct.
  - `[medium]` `[bad_spec]` Verification 1: tests do not assert run-to-candidate bindings — amended test task to check all 36 bindings.
  - `[medium]` `[bad_spec]` Verification 2: all campaign tests bypass the actual admission gate — amended test task to exercise real rejection on stale evidence.
  - `[medium]` `[patch]` Verification 3: CLI omits AdmissionStoreError — same safe-error repair as Blind 5.
  - `[false]` `[reject]` Intent 1: sprint-status is absent from the in-review diff — synchronization belongs after verified completion; the current ledger still correctly says backlog while review is underway.
  - `[false]` `[reject]` Intent 2: a concrete live campaign was not frozen — the request dispatches the implementation story; the story defines behavior for when an evaluator starts a campaign, while its admitted pair is not confirmed in one application database.

### 2026-09-25 — Review pass
- verdicts: 18 findings — high 0, medium 14, low 0, false 4, maybe-false 0
- findings:
  - `[medium]` `[bad_spec]` Blind 1: downgrade deletes planned campaign evidence — amended migration task to refuse downgrade while any campaign exists.
  - `[medium]` `[bad_spec]` Blind 2: linked run purpose/state can change and allow ordinary claim — amended migration task to guard frozen bindings and define an explicit future activation boundary.
  - `[medium]` `[bad_spec]` Blind 3: insufficient fixture run stores only first area — amended store task to preserve every frame's area identity.
  - `[false]` `[reject]` Blind 4: non-M3 hardware could be admitted — local admission checks `system_profiler` chip type Apple M3 Pro, CPU count and memory before creating admitted evidence; this story verifies that evidence through the real gate.
  - `[medium]` `[bad_spec]` Blind 5: zero, negative or nonfinite timeouts pass — amended domain task to require finite positive limits.
  - `[medium]` `[bad_spec]` Blind 6: no expired/revoked cloud freeze test — amended test task to exercise both through the store.
  - `[medium]` `[bad_spec]` Blind 7: tests do not inspect each run's frozen interpretation — amended test task to compare all run bindings with the manifest.
  - `[medium]` `[bad_spec]` Blind 8: duplicate checksum test stops at domain manifest — amended test task to persist and read distinct cells with equal image hashes.
  - `[medium]` `[bad_spec]` Edge 1: campaign table immutability leaves linked run bindings mutable — same migration amendment as Blind 2.
  - `[medium]` `[bad_spec]` Edge 2: candidate timeout gate accepts invalid values — same domain amendment as Blind 5.
  - `[medium]` `[bad_spec]` Edge 3: accepted decision may name a different manifest hash — amended store gate to compare decision and revision hashes.
  - `[false]` `[reject]` Edge 4: generic host could claim M3 baseline — the admission path verifies the actual Apple M3 Pro chip before recording successful local evidence, and `require_authorized` validates the bound admission runs.
  - `[medium]` `[bad_spec]` Edge 5: wrong-candidate and simultaneous-freeze paths lack tests — amended test task to cover both.
  - `[medium]` `[bad_spec]` Verification 1: all run configuration fields escape test assertion — same 36-run binding test amendment as Blind 7.
  - `[medium]` `[bad_spec]` Verification 2: CLI rejection JSON and exit code lack tests — amended test task to exercise command surface.
  - `[medium]` `[bad_spec]` Verification 3: decision hash mismatch passes test setup — same store and test amendment as Edge 3.
  - `[false]` `[reject]` Intent 1: sprint-status absent in review diff — synchronization follows completed implementation verification and is still pending.
  - `[false]` `[reject]` Intent 2: no operational campaign was created — this is a build-auto implementation dispatch; profile co-location in an application database was not established.

### 2026-09-25 — Review pass
- verdicts: 16 findings — high 0, medium 12, low 0, false 4, maybe-false 0
- findings:
  - `[medium]` `[defer]` Blind 1: queued comparison runs cannot progress — Story 4.4 owns execution and must add guarded queued/running/terminal transitions after it attaches inputs; this freeze-only story intentionally holds planned rows.
  - `[medium]` `[patch]` Blind 2: planned-to-queued accepted an unguarded direct SQL update — migration now rejects linked run state changes until Story 4.4 defines activation.
  - `[medium]` `[patch]` Blind 3: insufficient run used its first area as singular scope — it now uses `multiple_observation_areas` and retains the exact ordered area/context list.
  - `[false]` `[reject]` Blind 4: stored manifest/hash mismatch could pass — Story 4.1 computes the hash from the same manifest during accepted insertion, and both revision and decision rows are immutable; no application path creates the mismatch.
  - `[false]` `[reject]` Blind 5: duplicate-hash campaign test is not a current accepted path — the present evaluation gate rejects duplicate images; this test exercises the stated downstream ordinal accounting invariant with a synthetic persisted revision.
  - `[medium]` `[patch]` Blind 6: changed-revision test varied several identities — it now keeps the evaluation and profiles fixed and changes only the policy revision.
  - `[medium]` `[patch]` Blind 7: expired-evidence test failed earlier required fields — it now changes only `checked_at` and directly proves a current copy passes while the stale copy fails.
  - `[medium]` `[patch]` Blind 8: downgrade test depended on test order — it now creates its own campaign and passes alone on a clean migrated database.
  - `[medium]` `[patch]` Blind 9: cloud scope rejection used only a mocked dictionary — it now also rejects a real locked admitted profile with an uncovered frame.
  - `[medium]` `[patch]` Blind 10: successful freeze bypassed real admission in all tests — a real admitted pair now freezes 36 planned cells in PostgreSQL.
  - `[medium]` `[defer]` Edge 1: queued-to-running remains unavailable — carried with Blind 1 for Story 4.4's guarded execution transition.
  - `[medium]` `[patch]` Edge 2: planned-to-queued lacked an activation gate — same migration fix as Blind 2.
  - `[medium]` `[patch]` Verification 1: positive freeze lacked real admission coverage — same real-pair database test as Blind 10.
  - `[medium]` `[patch]` Verification 2: successful CLI output lacked an assertion — the command now has a real-admission success test asserting campaign ID and 36 cells.
  - `[false]` `[reject]` Intent 1: sprint-status is absent from the review diff — it will be synchronized only after the final verified result, as requested.
  - `[false]` `[reject]` Intent 2: no application-database campaign was frozen — the requested build-auto story implements the freeze operation; the co-located admitted pair and target deployment were not established.

## Design Notes

`planned` is a reserved run state for Story 4.4: it does not carry input artifacts yet, and existing `claim_ordinary` only selects `queued`. The campaign must still bind immutable profile, policy, rule and taxonomy snapshots at freeze. Story 4.4 will attach private frame artifacts and activate cells in tuple order without changing those bindings.

## Verification

**Commands:**
- `cd backend && uv run --extra test pytest tests/test_comparison_campaign.py tests/test_evaluation_set.py` — migration and campaign contracts pass with PostgreSQL.
- `git diff --check` — no whitespace errors.

## Auto Run Result

Status: done. Story 4.3 implements an atomic, byte-free comparison freeze with six fixtures, two admitted candidates, three repeats, and 36 immutable planned runs. The ordinary worker cannot claim them. A campaign remains a plan until Story 4.4 adds guarded execution.

Changed files:
- `backend/app/domain/comparison_campaign.py` — validate the persisted evaluation contract, exact candidates, cloud image scope, and runtime limits; build the ordered manifest.
- `backend/migrations/versions/0010_comparison_campaign.py` — immutable campaign/cell tables, comparison-run binding protection, and downgrade protection for retained evidence.
- `backend/app/adapters/postgres.py` — transaction-scoped real admission, decision/hash checks, atomic cell materialization, and readback.
- `backend/app/application/evaluation.py` — operator freeze/readback commands with safe rejection JSON.
- `backend/tests/test_comparison_campaign.py` — matrix, binding, gate, rollback, concurrency, CLI, and downgrade verification.
- This spec — intent, review triage, verification, and residual risk.

Review: the final pass had eight grouped medium patch entries, one deferred Story 4.4 transition, and four rejected claims. Follow-up review recommended: true because this pass patched multiple medium issues in the activation boundary and admission/CLI proof. The material unverified risk is operational freeze against an application database containing both current admitted profiles.

Verification: a fresh isolated PostgreSQL accepted migration `0010_comparison_campaign`; the specified campaign/evaluation test command yielded 37 passed and 1 skipped (the external real archive path was not supplied). The downgrade protection test passed alone on a second fresh database. `git diff --check` and `git diff --cached --check` passed. No cloud request, held-out image upload, application deployment, or real campaign freeze was performed.

---
title: 'Story 4.4: Execute and Recover Every Planned Cell'
type: 'feature'
created: '2026-09-25'
status: 'done'
baseline_commit: '5e133534147d4b086f36aff5baa0606119ff10d3'
baseline_revision: '5e133534147d4b086f36aff5baa0606119ff10d3'
review_loop_iteration: 5
followup_review_recommended: false
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** Story 4.3 freezes 36 comparison cells and their ordinary AnalysisRuns in `planned` state, but no cell can execute. A restart or uncertain provider call must not erase a cell or silently retry it.

**Approach:** Add an explicit operator-driven campaign executor that verifies and publishes the frozen fixture bytes, activates and processes one existing cell run at a time in manifest tuple order, and reports exact manifest-based accounting. Persist recovery decisions before advancing to the next cell.

## Boundaries & Constraints

**Always:** Keep the immutable campaign and run bindings, six fixture ordinals, two candidate ordinals, three repeats and 36 distinct run IDs. Verify the complete archive against frozen SHA-256 and size values before any cell activation or byte publication. Reserve an external invocation durably before the call. On restart, finish an expired or ownership-uncertain call as a failed cell with retained evidence, then select the lowest non-terminal tuple. Recheck authorization before sending bytes; preserve an already reserved call's evidence if authorization changes later. Report planned as the manifest total and reconcile succeeded, failed, timed-out and missing to that total; no success-only denominator.

**Never:** Repeat a scored call under the same cell identity, replace a failed run, call an unadmitted provider, collapse duplicate hashes, infer absence from technical failure, send fixture bytes before checking rights/authorization, or let the ordinary worker claim campaign cells.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Complete campaign | Frozen manifest and matching private archive | 36 runs execute in tuple order, one at a time; inputs, invocations, native output and observations retain ordinary evidence | Failures retain their cells |
| Archive mismatch | Missing member or changed bytes | No image is uploaded or invoked | Reject execution before cell activation; manifest unchanged |
| Restart or uncertain call | Running cell with lost lease or reserved invocation | Its run and invocation become terminal failure; next lowest non-terminal key is selected | No same-cell external retry |
| Revocation or provider timeout | Gate changes or bounded call fails | Affected cell remains in matrix with attributable failure or timeout | No fallback or scored retry |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:954` and `_bmad-output/implementation-artifacts/epic-4-context.md` — source AC and frozen order/accounting constraints.
- `_bmad-output/implementation-artifacts/spec-4-3-freeze-a-complete-comparison-campaign.md:13` — completed freeze and deferred activation; 36 existing planned runs are the cell identities.
- `backend/migrations/versions/0010_comparison_campaign.py:38` — current trigger forbids all linked run state changes; add a forward migration for guarded execution, keeping frozen fields and cell rows immutable.
- `backend/app/adapters/postgres.py:97` — atomic freeze and readback; extend with ordered cell claim/recovery, guarded input attachment and manifest accounting. `claim_ordinary` at line 768 excludes campaign purpose.
- `backend/app/application/executor.py:104` — ordinary single-runtime loop and evidence pipeline; reuse bounded decode, reservation, invocation, native artifact publication, normalization and completion without letting ordinary claiming steal campaign cells.
- `backend/app/adapters/postgres.py:308` — existing expired-lease recovery; reconcile campaign calls and retain invocation identity before selecting the next cell.
- `backend/app/domain/comparison_campaign.py:15` — frozen manifest contains archive member/hash/size and fixture frame contexts, but not private image bytes.
- `backend/app/application/evaluation.py:16` and `backend/pyproject.toml` — operator CLI for freeze/readback; add execute/resume and accounting commands with safe JSON failures.
- `backend/app/adapters/artifacts.py:20` and `backend/app/domain/evaluation_set.py` — private publication and archive integrity patterns; local archive is named by `evaluation/README.md` and real-set tests use `EVALUATION_ARCHIVE_PATH`.
- `backend/tests/test_comparison_campaign.py` — PostgreSQL integration fixtures and matrix tests; extend with execution, restart, timeout, revocation and exact accounting.

## Tasks & Acceptance

**Execution:**
- [x] `backend/migrations/versions/0011_comparison_execution.py` — permit guarded planned-to-active-to-terminal transitions, including attributable pre-call failures; lock the complete input binding against INSERT/UPDATE/DELETE bypasses, retry lineage and terminal outcome fields against later edits, preserve frozen configuration, and reject destructive downgrade with campaign evidence. Block direct terminal failure while a reserved invocation remains unsettled inside its provider safety window. Protect referenced artifact metadata/publication rows and terminal invocation, observation, stage and projection evidence from INSERT/UPDATE/DELETE after terminalization; preserve immutable reservation identity fields while a call is reserved and reject deletion of a reserved campaign invocation even before terminalization. Freeze referenced publication intents as soon as attached to an input or native artifact, and guard both OLD and NEW campaign links on UPDATE. An input row requires a matching publication intent belonging to the same run in published/referenced state. Require owner-fenced lease renewal to move expiry forward and forbid clearing/decreasing provider safety while a call can be active.
- [x] `backend/app/adapters/postgres.py` — attach checksum-verified fixture inputs to the existing run, claim only the lowest non-terminal cell under a campaign lock, reserve/renew/finish/fail with fencing, recover uncertain calls as terminal, and compute readback with input, invocation, observation and artifact identifiers from one consistent database snapshot. Make input publication resumable by stable cell/frame identity. Preserve a reserved call's successful evidence after authorization revocation. Reject direct claim of a later tuple while a lower non-terminal cell exists. Keep ordinary `recover()` and `reconcile()` from changing campaign runs or active campaign input intents; startup/runtime ordinary maintenance must respect the campaign ownership boundary. Reconcile or quarantine incomplete campaign publication intents after a terminal cell failure. On campaign recovery, fail closed while a running cell has a live lease or otherwise uncertain evidence publication, including cells that make no provider call. An ordinary failure path must not terminalize a reserved campaign call before its provider safety window; stale ownership must not finalize it. Enforce fenced updates to lease owner, expiry and provider safety fields; report authorization revision changes distinctly from generic preparation failures.
- [x] `backend/app/application/executor.py` — expose bounded one-cell execution using the ordinary evidence contract for local and cloud profiles, with no within-cell scored retry or fallback. Observe lease-renewal failure during work and stop before additional provider calls or evidence writes when ownership is lost. A second executor must not start another external call while a prior call may still run after lease loss; enforce an execution ownership boundary that survives normal DB transactions and resolves conservatively on uncertain ownership. Recover expired calls before requiring archive bytes for remaining cells. Treat publication/activation failure as an attributable terminal cell result and continue in tuple order, while leaving archive-wide preflight failures as explicit pre-execution rejection. Verify the archive bytes and extract members through one stable file handle.
- [x] `backend/app/application/evaluation.py` and `backend/pyproject.toml` — accept campaign ID and private archive path for explicit execution/resume and expose byte-free ordered accounting with safe JSON errors, including database URL parsing, store construction and unavailable archive failures.
- [x] `backend/tests/test_comparison_campaign.py` — cover the I/O matrix with distinct image bytes bound to each frame; record actual activation order of all 36 cells, including no-provider cells, and provider-call tuple order. Test a reserved invocation through recovery and actual next-cell execution without retry, a later bad archive member before any upload, and timeout accounting as its own manifest category. Exercise the `execute-campaign` CLI entry point. Verify no overlapping in-flight call after lease/session loss, ordinary worker recover/reconcile exclusion against pending campaign input, live-lease and no-provider evidence recovery refusal, duplicate checksums as distinct cells, technical publication failure and terminal intent reconciliation, stable upload adoption, terminal and lineage/evidence immutability (including reservation deletion and referenced intent updates), zero upload after pre-publication revocation, authorization changes after reservation for both candidates, snapshot-consistent accounting and CLI readback.

**Acceptance Criteria:**
- Given a frozen campaign and matching private archive, when the operator executes it, then the outer CLI readback shows each of the 36 existing run IDs in tuple order with a retained terminal state and ordinary evidence links.
- Given a crash after reservation, when execution resumes, then readback shows that cell failed with its reserved invocation and the next lowest non-terminal cell executes without a second invocation for the failed cell.
- Given completed or partially failed repeats, when accounting is inspected, then planned, succeeded, failed, timed-out and missing reconcile to the frozen 36-cell manifest, including every fixture and candidate ordinal.

## Spec Change Log

- 2026-09-25: Review found overlap after lease expiry, planned cells stranded by publication errors, non-idempotent input upload, mutable terminal accounting, inconsistent readback, archive replacement between opens, and recovery blocked by a missing archive. The tasks now require a durable execution ownership boundary, attributable pre-call failure transitions, stable publication adoption, stronger DB guards, one read snapshot, a stable archive handle, and recovery before future-input preflight. KEEP the existing 36-cell identities, ordinary evidence pipeline, exact tuple order, input hash checks, working local/cloud path, and manifest accounting; retain the successful and failure integration tests while re-deriving.
- 2026-09-25: Second review found ordinary `recover()` and `reconcile()` still crossed campaign ownership, and campaign recovery discarded a live-lease result after session lock loss. The store task now isolates ordinary maintenance and refuses uncertain recovery; migration/test tasks also protect retry lineage and prove actual call order and pre-upload revocation. KEEP the complete 36-cell integration path, manifest-bound input guards, stable publication keys, archive preflight, snapshot readback, and post-reservation evidence retention while re-deriving.
- 2026-09-25: Third review found terminal campaign intents without reconciliation, unsafe evidence recovery for no-provider cells, unobserved lease-renewal failure, mutable referenced/terminal evidence and recovery fields, and missing all-cell activation proof. The tasks now close these evidence and fencing gaps and require local/cloud revocation checks. KEEP the observed provider order, 36-cell CLI readback with evidence IDs, ordinary maintenance isolation, archive preflight, stable publication identity, and passing full backend suite while re-deriving.
- 2026-09-25: Fourth review found ordinary campaign failure could bypass the provider safety window, stale ownership could finalize, evidence guards missed INSERT or OLD/NEW links, and tests used uniform archive bytes and omitted timeout/activation assertions. The tasks now enforce these fences and source-level evidence invariants and require distinct-fixture operator tests. KEEP the native stage names, 36-cell successful path, safe archive preflight, immutable tuple and input binding, stable publication identity, and green UTC backend suite while re-deriving.
- 2026-09-25: Fifth review found DB-level safety bypasses on terminal failure, reservation deletion, and referenced publication mutation, plus missing evidence IDs and lowest-key enforcement in public store methods. The tasks now guard those transitions and prove recovery continuation and operator CLI execution. KEEP the settled provider-call path, authorization lock through upload, scoped evidence guards that preserve ordinary retries, distinct fixture bytes, timeout accounting, and full backend green run while re-deriving.

## Review Triage Log

### 2026-09-25 — Review pass
- verdicts: 15 findings — high 1, medium 10, low 0, false 4, maybe-false 0
- findings:
  - `[medium]` `[bad_spec]` Blind 1: archive preflight precedes expired-call recovery — a missing archive stops recovery; amended executor task to recover first.
  - `[high]` `[bad_spec]` Blind 2: expired lease can coexist with an in-flight call — another executor can start the next cell; amended task with durable execution ownership.
  - `[medium]` `[bad_spec]` Blind 3: publication failure leaves a planned cell — no terminal accounting or advance; amended failure transition and executor task.
  - `[medium]` `[bad_spec]` Blind 4: fresh publication UUID on resume leaves orphan intents — amended task for stable cell/frame adoption.
  - `[false]` `[reject]` Blind 5: zero-missing CLI exit can include all failed cells — JSON explicitly exposes failed and timed-out counts; process exit reports completed accounting, not criterion readiness.
  - `[false]` `[reject]` Blind 6: cloud allowlist failure is labeled profile unauthorized — freeze validates all campaign hashes against the immutable candidate allowlist, so this branch is unreachable for a valid frozen campaign.
  - `[medium]` `[bad_spec]` Blind 7: terminal error_code can be changed and alter accounting — amended migration task to lock terminal outcome fields.
  - `[medium]` `[bad_spec]` Blind 8: UPDATE can move an ordinary input into a campaign run — the trigger checks OLD.run_id only; amended complete input guard task.
  - `[medium]` `[bad_spec]` Blind 9: readback queries can observe different committed states — amended store task to use one snapshot.
  - `[medium]` `[bad_spec]` Edge 1: publication failure leaves planned/missing — same root as Blind 3; amended failure transition task.
  - `[false]` `[reject]` Edge 2: non-authorization AdmissionStoreError is mislabeled — the caught calls are current authorization checks; artifact/store failures have other exception types.
  - `[medium]` `[bad_spec]` Edge 3: archive path can change between hashing and ZIP extraction — amended stable handle requirement.
  - `[medium]` `[bad_spec]` Verification 1: no test completes a reserved call after revocation — amended test task for post-reservation revocation evidence.
  - `[medium]` `[bad_spec]` Verification 2: later invalid archive member is untested — amended multi-member preflight test task.
  - `[false]` `[reject]` Intent alignment: sprint-status is not in the in-review diff — synchronization follows verified completion and is still explicitly pending in this invocation.

### 2026-09-25 — Review pass
- verdicts: 14 findings — high 4, medium 5, low 0, false 3, maybe-false 2
- findings:
  - `[high]` `[bad_spec]` Blind 1: ordinary `recover()` includes expired campaign runs — confirmed unrestricted query; amended store task to exclude campaign ownership.
  - `[high]` `[bad_spec]` Blind 2: ordinary `reconcile()` can quarantine active campaign input intents — confirmed planned cells are not skipped; amended store task to isolate them.
  - `[high]` `[bad_spec]` Blind 3: campaign recovery fails a still-live run after loss of lock connection — confirmed unconditional running-row update; amended task to refuse uncertain evidence publication.
  - `[maybe-false]` `[defer]` Blind 4: provider work might outlast timeout plus safety window — the call is bounded locally, but pathological OS/provider behavior is not proven; a forced-hang/process-loss test or provider completion evidence would settle it (high if true).
  - `[false]` `[reject]` Blind 5: owner-gate read after revocation sends fixture bytes — owner-gate check precedes invocation but sends no fixture image; authorization is checked at reservation before image upload/call.
  - `[false]` `[reject]` Blind 6: revocation after reservation must prevent the call — the frozen intent explicitly preserves an already reserved invocation and its evidence; pre-reservation authorization is checked.
  - `[medium]` `[bad_spec]` Blind 7: retry_predecessor_id remains mutable — the campaign trigger omits retry lineage; amended migration and test task to preserve it.
  - `[medium]` `[bad_spec]` Blind 8: unexpected DB errors escape operator CLI as tracebacks — amended safe JSON error task.
  - `[medium]` `[bad_spec]` Blind 9: sorted readback does not prove execution order — amended observed provider-call order test.
  - `[high]` `[bad_spec]` Edge 1: ordinary reconciliation can quarantine active campaign input — same confirmed root as Blind 2; amended store task.
  - `[maybe-false]` `[defer]` Edge 2: a call could run past provider_safe_after — same unresolved bound as Blind 4; settle with a hung-call or process-death check (high if true).
  - `[medium]` `[bad_spec]` Verification 1: revocation before publication has no zero-upload assertion — amended test task.
  - `[medium]` `[bad_spec]` Verification 2: execution order is asserted only in readback — amended provider-call order test; same root as Blind 9.
  - `[false]` `[reject]` Intent alignment: no real campaign was executed and status is in-progress — this invocation supplies no campaign ID or private archive and requests a build iteration; in-progress is the current verified status pending completion.

### 2026-09-25 — Review pass
- verdicts: 14 findings — high 0, medium 10, low 0, false 1, maybe-false 3
- findings:
  - `[maybe-false]` `[defer]` Blind 1: a lost advisory-lock connection can leave the old executor running — carried prior uncertainty; the persisted safety window blocks a new call until its bound, but a forced session-loss/hung-worker test would settle the beyond-bound case (high if true).
  - `[maybe-false]` `[defer]` Blind 2: provider work may outlast provider_safe_after — carried prior timeout-bound uncertainty; a forced process hang or provider completion record would settle it (high if true).
  - `[medium]` `[bad_spec]` Blind 3: lease-renewal failure is not observed during `_execute` — a call can continue after ownership loss; amended executor task.
  - `[medium]` `[bad_spec]` Blind 4: terminal failures leave campaign publication intents unresolved while ordinary reconciliation excludes them — amended campaign reconciliation task.
  - `[medium]` `[bad_spec]` Blind 5: referenced artifact metadata/publication rows remain mutable — a frozen input can change after terminalization; amended migration task.
  - `[medium]` `[bad_spec]` Blind 6: direct updates can change running recovery fields without fencing — amended store/migration task.
  - `[medium]` `[bad_spec]` Blind 7: terminal invocation/observation/stage/projection rows remain mutable — amended migration task to retain evidence.
  - `[medium]` `[bad_spec]` Blind 8: authorization revision change becomes generic preparation failure — amended store/CLI attribution task.
  - `[medium]` `[bad_spec]` Blind 9: test records provider calls but omits no-provider activation order — amended all-cell activation test.
  - `[medium]` `[bad_spec]` Blind 10: cloud post-reservation revocation path is untested — amended test task for both candidates.
  - `[maybe-false]` `[defer]` Edge 1: provider dispatch may be delayed past its safety window — same unresolved bound as Blind 2; an injected dispatch delay plus session loss would settle it (high if true).
  - `[medium]` `[bad_spec]` Verification 1: out-of-scope activation order is unverified — same root as Blind 9; amended test task.
  - `[medium]` `[bad_spec]` Verification Other: recovery may fail an unfinished no-provider cell after lease expiry — amended recovery guard/test task.
  - `[false]` `[reject]` Intent alignment: no live campaign completion shown — request invokes a build iteration without a campaign ID or private archive; synthetic integration evidence is appropriately reported as such.

### 2026-09-25 — Review pass
- verdicts: 19 findings — high 3, medium 14, low 0, false 1, maybe-false 1
- findings:
  - `[high]` `[bad_spec]` Blind 1: lease-renewal failure can immediately fail a reserved call before safety expiry — amended failure fencing task.
  - `[high]` `[bad_spec]` Blind 2: stale owner can finalize after lease loss — amended owner/lease checks for campaign failure.
  - `[medium]` `[bad_spec]` Blind 3: evidence trigger omits INSERT after terminalization — amended migration task.
  - `[medium]` `[bad_spec]` Blind 4: reserved invocation identity fields can change before completion — amended migration task.
  - `[medium]` `[bad_spec]` Blind 5: publication UPDATE checks OLD but not NEW campaign link — amended migration task.
  - `[medium]` `[bad_spec]` Blind 6: owner can move lease expiry backward — amended monotonic renewal guard.
  - `[medium]` `[bad_spec]` Blind 7: URL/store construction precedes CLI JSON error handler — amended CLI task.
  - `[medium]` `[bad_spec]` Blind 8: recovery test omits reserved invocation and next-cell execution — amended test task.
  - `[medium]` `[bad_spec]` Blind 9: provider order omits no-provider activation order — amended test task.
  - `[medium]` `[bad_spec]` Blind 10: later corrupt archive member is untested — amended distinct-fixture preflight test.
  - `[maybe-false]` `[defer]` Blind 11: call may outlive provider safety window — carried prior bound uncertainty; a forced hung process/provider completion trace would settle it (high if true).
  - `[medium]` `[bad_spec]` Blind 12: ordinary maintenance exclusion has no pending-campaign regression test — amended test task.
  - `[high]` `[bad_spec]` Edge 1: provider safety can be set NULL while reserved — amended nonnull/monotonic guard.
  - `[medium]` `[bad_spec]` Edge 2: referenced native artifact metadata can be deleted before terminalization — amended evidence guard task.
  - `[medium]` `[bad_spec]` Edge 3: CLI startup error escapes JSON handler — same root as Blind 7; amended CLI task.
  - `[medium]` `[bad_spec]` Edge 4: no-provider activation order unverified — same root as Blind 9; amended test task.
  - `[medium]` `[bad_spec]` Verification 1: uniform archive bytes hide wrong frame mapping — amended distinct-byte test task.
  - `[medium]` `[bad_spec]` Verification 2: timeout classification is untested — amended accounting test task.
  - `[false]` `[reject]` Intent alignment: no live provider campaign shown — build-auto invocation supplies no campaign ID or private archive; this diff is judged as implementation, not live execution.

### 2026-09-25 — Review pass
- verdicts: 16 findings — high 4, medium 8, low 1, false 2, maybe-false 1
- findings:
  - `[medium]` `[bad_spec]` Blind 1: readback exposes counts without evidence IDs — amended store task for direct identifiers.
  - `[medium]` `[bad_spec]` Blind 2: direct claim accepts a later planned cell — amended lowest-key enforcement task.
  - `[high]` `[bad_spec]` Blind 3: SQL can fail a running cell with an unsettled provider call before safety expiry — amended trigger task.
  - `[high]` `[bad_spec]` Blind 4: reserved campaign invocation can be deleted before terminalization — amended evidence guard task.
  - `[medium]` `[bad_spec]` Blind 5: referenced publication intent can change while run is active — amended publication guard task.
  - `[medium]` `[bad_spec]` Blind 6: input guard does not bind the publication intent to the run and published state — amended input guard task.
  - `[maybe-false]` `[defer]` Blind 7: an old upload thread may continue after recovery's safety window — same previously recorded bounded-call uncertainty; forced hung-upload/process-loss evidence would settle it (high if true).
  - `[false]` `[reject]` Blind 8: bounded local observer returns while child remains alive — `_observe_bounded` waits after terminate/kill and only returns after `join`, so the described overlap is not shown.
  - `[medium]` `[bad_spec]` Blind 9: missing archive opens outside specific error translation — amended safe operator rejection task.
  - `[low]` `[reject]` Blind 10: one advisory lock serializes independent campaigns — each campaign is still correct and no parallel-campaign requirement exists; per-campaign lock keys add complexity without demonstrated harm.
  - `[high]` `[bad_spec]` Edge 1: direct terminal failure bypasses active provider safety — same confirmed root as Blind 3; amended trigger task.
  - `[high]` `[bad_spec]` Edge 2: reserved invocation DELETE bypasses evidence retention — same confirmed root as Blind 4; amended guard task.
  - `[medium]` `[bad_spec]` Edge 3: referenced publication mutation bypasses retained input provenance — same confirmed root as Blind 5; amended guard task.
  - `[medium]` `[bad_spec]` Verification 1: recovery test never executes the next cell — amended end-to-end continuation test.
  - `[medium]` `[bad_spec]` Verification 2: execute-campaign CLI branch is untested — amended operator CLI test.
  - `[false]` `[reject]` Intent alignment: no real campaign run shown — request is a build iteration without campaign ID or private archive, so live execution is not claimed.

### 2026-09-25 — In-place repair review

The owner explicitly requires preserving the fifth implementation and repairing confirmed defects in place. This overrides workflow re-derivation, rollback and loop-limit routing; review fixes remain within this story.

- `[high]` `[patch]` Blind 1: `require_comparison_authorized` omits the existing admitted adapter/lock hash gate; a previously frozen campaign can use changed runtime code. Reuse the established authorization gate before publication and activation.
- `[high]` `[patch]` Blind 2: an unsettled reservation can change to `completed`, bypassing the run guard that searches reserved calls. Require explicit settlement before campaign invocation completion.
- `[medium]` `[patch]` Blind 3: allowed downgrade without campaigns leaves a trigger referencing dropped safety columns. Restore the prior run guard and cover the downgrade/re-upgrade path on a disposable database.
- `[medium]` `[patch]` Blind 4: authorization changes before reservation become `ordinary_reservation_rejected`. Preserve distinct campaign authorization reasons after ownership validation.
- `[medium]` `[patch]` Blind 5: provider-order assertions ignore actual image bytes. Assert the frozen ordered frame hashes passed to both provider adapters.
- `[medium]` `[patch]` Blind 6: manually assigning a publication error does not verify an actual partial upload failure or continuation. Inject a real publication boundary failure and assert retained/quarantined intent states and the next tuple.
- `[false]` `[reject]` Blind 7: all mutable state, counts and evidence IDs are read in one SQL statement; the preceding campaign manifest is immutable, and the connection additionally uses REPEATABLE READ. The proposed inter-query commit cannot produce mixed cell/evidence snapshots.
- `[medium]` `[patch]` Blind 8: the session-loss test finishes before renewal runs. Inject renewal failure during blocked work and assert no later call/evidence writes.
- `[medium]` `[patch]` Blind 9: provider cancellation/drain and settlement are consequential new concurrency paths without an exercised cancellation boundary. Add focused cancellation coverage.
- `[low]` `[reject]` Blind 10: additional CLI examples would help discoverability, but parser help exposes both commands and missing prose causes no execution defect. Documentation expansion is excluded from this focused repair.
- `[high]` `[patch]` Edge 1: losing the global lock session permits another campaign to execute while the old campaign has a running cell. Reject execution while another campaign has uncertain running ownership.
- `[high]` `[patch]` Edge 2: a legal post-reservation artifact read can consume the safety allowance before provider dispatch. Read the frame before reservation so its delay cannot shorten the provider window.
- `[medium]` `[patch]` Verification 1: failure/recovery quarantine of incomplete intents lacks assertions and ordinary reconciliation excludes these intents. Add explicit failure and expired-recovery cases, preserving referenced evidence.

## Design Notes

The word “creates” in the Story 4.4 AC refers to the already materialized ordinary `AnalysisRun` for each cell. Creating another run would break the frozen `comparison_cells.run_id` identity and Story 4.3's 36-run contract. `planned` is activated only after its own input bytes have been verified and privately published.

## Verification

**Commands:**
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest tests/test_comparison_campaign.py tests/test_evaluation_set.py` — migration, execution, recovery and accounting integration cases pass.
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest` — backend regression suite passes.
- `git diff --check` — no whitespace errors.

## Previous Auto Run Result (superseded by the repair below)

Status: blocked.
Blocking condition: Automatic approval review rejected the workflow-required fifth targeted rollback of the uncommitted Story 4.4 implementation. Prior permissions were treated as iteration-specific; a separate question for this fifth rollback remains unanswered. The current code is preserved, and its complete diff is saved at `/private/tmp/story44-20260925-r5-before-rerun.diff`.

The fifth implementation passed 51 focused tests (1 skipped) and 181 backend tests (2 skipped) against isolated PostgreSQL and local MinIO. Independent review then confirmed DB-level safety and evidence-link gaps recorded above; the green suites do not establish completion. The sprint entry is `in-progress` and its validator passes. No live private-archive/provider campaign was run.

## Repair Run Constraints — 2026-09-25

Continue the existing fifth implementation in this working tree. Preserve staged and unstaged work; do not run build-auto, restore/reset, recreate the implementation, use GUI, or push. Confirm the latest review findings against current code and make only focused repairs. Prioritize provider safety on terminal failure, reserved invocation deletion and referenced publication intent protection, earliest unfinished tuple claiming, explicit evidence identifiers in readback, actual recovery continuation and execute-campaign CLI coverage. Add boundary tests, run focused tests and the full backend suite against isolated PostgreSQL/MinIO without printing secrets. Inspect the entire diff and diff --check. The coordinator owns final verification, sprint synchronization and local commit.

## Repair Verification Result — 2026-09-25

Status: implementation complete; sprint story is `review` under the build workflow. The prior workflow rollback blocker is resolved by the owner's explicit in-place repair instruction. No code was reverted or re-derived. All original staged and unstaged Story 4.4 content was preserved and repaired in the existing working tree.

Confirmed review findings were repaired in place. The complete implementation diff was inspected, including the inherited migration/executor/CLI work. No new known defect was deferred; earlier pathological process/provider-bound uncertainties remain observation limits rather than proven guarantees.

- Fresh isolated PostgreSQL 17.6 and MinIO containers: migration to `0011_comparison_execution` succeeded; disposable-database downgrade/re-upgrade and destructive-downgrade refusal passed. Only this run's containers were removed afterward. Credentials were transient and sanitized from test output.
- Focused: `uv run --extra test pytest tests/test_comparison_campaign.py tests/test_evaluation_set.py -q -rs --tb=short` — **70 passed, 1 skipped**.
- Full backend: `uv run --extra test pytest -q -rs --tb=short` with the pinned offline Grounding DINO CPU snapshot — **200 passed, 2 skipped**. Both runs used `TZ=UTC` and isolated database/bucket configuration.
- The five changed backend source/test files had SHA-256 `d0cbd0888503817eb53f28cb730db1dbef7d40ec148e4365dc549f6b4aa75704` for their ordered concatenation throughout the final test runs; no source changed during verification.
- Tests prove the 36-cell CLI path and ordered frame hashes, exact evidence identifiers/accounting, reserved-call retention and continuation, SQL safety/immutability boundaries, runtime identity and authorization gates, partial-publication quarantine, same/different-campaign lock-session loss, renewal failure and provider cancellation.
- `git diff --check` and the sprint validator passed. The sprint change from the repair's starting state is limited to Story 4.4 (`in-progress` → `review`); other story/epic/action statuses are preserved.

Not verified: no real campaign ID or private evaluation archive was supplied, so no real scored local/cloud campaign was executed. Campaign integration tests use synthetic archives and provider stubs; the full suite separately includes real local CPU admission/inference. The two skips require `EVALUATION_ARCHIVE_PATH` and `TEST_HELD_OUT_IMAGE_PATH`. Provider processing beyond its declared safety bounds, live account/quota behavior and actual campaign quality/readiness remain unproven. No GUI or remote publication was used.

## Follow-up Verification — 2026-09-25

The in-place follow-up preserves commit `4f103263f3fe5c228bbd6ec71678dae373f09f28` and adds a guarded completion migration, manifest-bound input claiming, and focused regression tests. Repeated review findings about incomplete inputs and mutable or missing evidence were repaired. The final full backend suite passed **206 tests with no skips** using isolated PostgreSQL/MinIO, the pinned local CPU model snapshot, the verified private evaluation archive, and its first held-out JPEG. Migration `0012_comparison_completion` passed downgrade/re-upgrade on the disposable test database, and `git diff --check` passed. Temporary test containers were removed. The actual scored campaign, live cloud account behavior, and calls beyond the declared provider safety window remain unverified.

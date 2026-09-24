---
title: 'Navigate Evidence-Backed Stage Status'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '5d2899e93de57b950d99467a16b1165e699c819c'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      Excavation rule outcomes remain unavailable in the current runtime.
    evidence: |-
      Epic 2 is backlog and the current backend completes observation-only projections. Verify rule outcomes after Epic 2 is implemented; this story only navigates persisted outcomes.
    location: >-
      backend/app/adapters/postgres.py:726
    severity: medium (unverified)
  - summary: >-
      Rendered browser and phone behavior remains unverified.
    evidence: |-
      Headless component tests and build pass, but GUI use is prohibited in this workspace. A permitted rendered browser session would settle layout and focus behavior.
    location: >-
      web/src/App.tsx:683
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The app opens on new analysis and has no construction-stage overview. Users cannot find the latest evidence-backed outcome for a stage or distinguish it from a newer unfinished or failed run.

**Approach:** Bind new analyses to an explicit construction-stage key, expose a server-derived stage summary, and provide a Russian stage navigator with an inspector and routes to the source run and new analysis.

## Boundaries & Constraints

**Always:** The configured excavation stage uses only the latest ordinary run with `state = succeeded` and a persisted `ResultProjection`. A newer queued, running, or failed run is separate lifecycle context. Stage binding is immutable input context and survives retry. Existing runs without an explicit stage key remain unbound rather than guessed from scenario text. Show an explicit no-analysis state; explain unsupported stages. Keep one visible `Новый анализ` action and keyboard/focus semantics on route and tile changes.

**Never:** Use the six pipeline stages as construction stages; infer schedule progress, trend, project health, or a current stage; treat provider failure as a negative outcome; invent a result from partial evidence; silently enable a rule for an unsupported stage.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Completed result | Bound succeeded run with projection | Excavation tile/inspector show projected outcome and source-run link | No error expected |
| Newer attempt | Newer queued/running/failed bound run | Prior projected outcome remains; newer lifecycle appears separately | No false outcome |
| No completion | Only unbound/failed/running runs | `Анализов нет`; optional recent lifecycle is separate | No inferred stage for legacy runs |
| Unsupported stage | Tile without configured rule | `Не настроено в прототипе` with scope explanation | No rule-evaluation action |
| Overview unavailable | Fetch failure | Clear Russian error and retry action | Preserve last known summary if present |

</intent-contract>

## Code Map

- `backend/app/application/submission.py:38` validates and hashes analysis context; add an explicit known `stage_id` to the immutable request context and idempotency hash.
- `backend/app/adapters/postgres.py:496` commits the context; `:759` returns only succeeded projections; `:806` paginates history; `:873` copies context on retry. Add a single authoritative stage-summary query over all ordinary runs, independent of history page size.
- `backend/app/main.py:180` exposes runs/history; add a distinct stage-summary route before dynamic run paths.
- `backend/migrations/versions/0005_retry.py` already stores context as JSONB; a new column is unnecessary for a fixed key within the immutable context. Do not retroactively classify old free-text contexts.
- `web/src/App.tsx:253` parses routes; `:434` navigates and focuses headings; `:636` posts form context; `:654` renders shell. Add `Этапы` route, stage selection/inspector, and explicit stage binding on submission.
- `web/src/styles.css` defines shell/panel responsiveness; extend for stage tiles, inspector and labeled phone navigation.
- `backend/tests/test_ordered_series.py` has real API/database test fixtures; `web/src/App.test.tsx` has route, polling and focus tests.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:59` defines outcome labels; its mockup lists excavation plus illustrative unsupported stages. The UX spine says only excavation has the configured Rapid MVP rule.

## Tasks & Acceptance

**Execution:**
- `backend/app/application/submission.py` — accept an optional, explicit known construction-stage key and include it in the immutable hashed context; keep older clients without the key unbound.
- `backend/app/adapters/postgres.py` — summarize latest qualified projection and separately newer bound lifecycle per stage from committed state; exclude unbound legacy runs and all admission runs.
- `backend/app/main.py` — expose the read-only stage summary with stable shape and error behavior.
- `web/src/App.tsx` — open Stages Overview as the primary destination, add labeled shell navigation, tile selection/inspector, evidence-run and new-analysis routes, and carry selected stage into submission.
- `web/src/styles.css` — make tiles and inspector usable on laptop and phone without obscuring the persistent new-analysis action.
- `backend/tests/test_ordered_series.py`, `web/src/App.test.tsx` — exercise the matrix, exact projection/lifecycle separation, legacy run exclusion, selection semantics, route focus and fetch recovery.

**Acceptance Criteria:**
- Given a bound succeeded run with a completed Result Projection and a newer incomplete or failed bound run, when the Stages Overview loads, then its tile and inspector show the completed run's projected status and evidence link while the newer run appears only as lifecycle context.
- Given no completed bound analysis or an unsupported construction stage, when I select its tile, then the inspector shows `Анализов нет` or `Не настроено в прототипе` with a useful route or scope explanation and no schedule or project-health claim.
- Given laptop or phone navigation, when I select a stage or change route, then labels, selected-state semantics, focus and the visible `Новый анализ` action follow the UX contract and stage selection does not modify any schedule.

## Spec Change Log

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 15 findings — high 0, medium 11, low 2, false 0, maybe-false 2
- findings:
  - `[medium]` `[patch]` New analysis hides its excavation binding — show the explicit bound stage in the form before submission.
  - `[medium]` `[patch]` Starting from an unsupported tile silently resets to excavation — make the supported destination and stage binding visible.
  - `[maybe-false]` `[defer]` Excavation rule outcomes are absent — Epic 2 is backlog and current execution produces observation-only projections; the future rule implementation must be verified before claiming rule coverage.
  - `[low]` `[patch]` Inspector omits the returned creation time — show the last result and recent attempt times where known.
  - `[medium]` `[patch]` An unresolved overview fetch can load forever — bound the request and offer retry.
  - `[medium]` `[patch]` Overview does not refresh while open — provide an ordinary refresh path for new committed outcomes.
  - `[low]` `[patch]` First-load error claims cached data without any — make error text depend on retained data.
  - `[medium]` `[patch]` Source workspace does not show the persisted stage binding — expose it alongside run context.
  - `[medium]` `[patch]` Unknown routes render a null analysis workspace — render an explicit not-found state.
  - `[medium]` `[patch]` A sole failed run is described as newer with no prior result — distinguish a recent attempt from one newer than the shown result.
  - `[medium]` `[patch]` Unsupported-stage submission can silently bind excavation — same visible-destination correction as the second finding.
  - `[medium]` `[patch]` Summary test cannot detect missing ordinary/stage filters — add newer excluded runs with projections.
  - `[medium]` `[patch]` Retry test cannot detect dropped stage binding — exercise a bound retry and summary readback.
  - `[medium]` `[patch]` Sprint status remains backlog — synchronize the targeted story after final verified result.
  - `[maybe-false]` `[defer]` Rendered phone/browser experience is unverified — GUI use is prohibited; a permitted browser session would settle visual and focus behavior.

## Design Notes

The fixed MVP catalog uses a stable excavation key and display name `Земляные работы котлована`; other tiles explain scope. Existing legacy runs have no explicit construction-stage identity, so they remain available through history and their workspaces but do not enter stage summaries. The summary must rank a successful projection independently of the latest lifecycle; a history page or a single latest-run query can drop the qualified result.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_ordered_series.py` — stage API, immutable input and retry regressions pass against project test services.
- `cd web && npm test -- --run` — stage UI, navigation, and existing workspace tests pass.
- `cd web && npm run build` — TypeScript and production bundle succeed.

## Auto Run Result

Status: done

Implemented: explicit immutable excavation-stage binding, a PostgreSQL summary that independently selects the latest succeeded Result Projection and recent lifecycle, and a Russian stage overview with keyboard-operable tiles, inspector, run links, visible binding, refresh, timeout, and navigation states.

Files changed: `backend/app/application/submission.py` validates and hashes optional stage binding; `backend/app/adapters/postgres.py` derives the stage summary; `backend/app/main.py` exposes it; `backend/tests/test_ordered_series.py` verifies binding, excluded runs, retry inheritance and summary behavior; `web/src/App.tsx`, `web/src/styles.css`, and `web/src/App.test.tsx` implement and test the overview and related navigation; `sprint-status.yaml` marks only Story 3.3 done.

Review: 15 findings. Patched 11 medium and 2 low findings, including visible binding, lifecycle wording, refresh/timeout, not-found behavior, and stronger database tests. Deferred two unverified dependencies: Epic 2 rule outcomes and rendered browser/phone behavior. No findings were rejected. Follow-up review is recommended because several medium patches touched navigation and polling; a rendered browser pass remains unverified under the no-GUI instruction.

Verification: `backend/tests/test_ordered_series.py` passed 11/11 against a fresh isolated PostgreSQL database and MinIO bucket; `npm test -- --run` passed 40/40; `npm run build` passed; `git diff --check` passed. Browser rendering and deployment were not checked.

## Branch Integration Readback — 2026-09-24

The deferred Epic 2 rule-outcome note above describes the branch state when Story 3.3 was built. The merged tree includes Epic 2 rule evaluation and its projection outcomes; the stage summary reads those persisted outcomes. The merged backend suite passed 107 tests with one skip, and the web suite passed 75 tests. Rendered browser and deployed behavior remain unverified.

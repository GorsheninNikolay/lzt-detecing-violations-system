---
title: 'Reopen Analyses and Their Evidence'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '47aae2ae533c5dc64e9504fa9c32fa17bf13412b'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      Full history polling may become expensive if retained run volume grows substantially.
    evidence: |-
      GET /runs reads every ordinary run every three seconds per open history page. No production run count or load measurement is available; measure before adding pagination or incremental fetch.
    location: >-
      backend/app/adapters/postgres.py:784
    severity: 'medium (unverified)'
  - summary: >-
      Creation time for runs predating migration 0007 is unknown.
    evidence: |-
      Earlier analysis_runs had no creation timestamp. The migration leaves their created_at NULL and the UI says the time is unknown. Whether such runs exist in a deployed database remains unverified; no trustworthy source was found for reconstruction.
    location: >-
      backend/migrations/versions/0007_run_history.py:14
    severity: 'medium (unverified)'
---

<intent-contract>

## Intent

**Problem:** Persisted analyses can only be revisited through a known run URL. Managers need a stable history that identifies runs and links back to their immutable evidence.

**Approach:** Expose a read-only ordinary-run history from committed database state and add an `Анализы` page linking each row to the existing Run Workspace.

## Boundaries & Constraints

**Always:** Include every persisted ordinary run across lifecycle states, newest creation first with a stable ID tie-breaker; show creation time, stage, intent, lifecycle, terminal outcome only when backed by a succeeded Result Projection, and predecessor/successor identity when present. Preserve row order on polling and focus on the selected row. Reopening a run reads its original immutable workspace and evidence. Keep user-facing copy in Russian.

**Never:** Treat a queued, running, or failed run as a completed result; include admission runs; rerun the observer when opening history; infer an outcome from partial observations; move focus during polling.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Mixed history | Ordinary runs in queued, running, succeeded, failed states | Stable rows with required fields; only succeeded projection has outcome | Missing projection gives no outcome |
| Empty history | No ordinary runs | `Запусков пока нет.` and new-analysis route | No error |
| Refresh | A run changes lifecycle after first load | Existing rows retain position and focus; state updates | Failed fetch retains earlier list with `Не удалось загрузить анализы` and `Повторить` |
| Open row | Selected persisted run | Navigate to `/runs/{run_id}` and load its original evidence | Existing workspace handles unavailable run/artifact |

</intent-contract>

## Code Map

- `backend/app/main.py:164` — Existing `GET /runs/{run_id}` and artifact routes; add history before the parameter route.
- `backend/app/adapters/postgres.py:784` — `read_ordinary` is the source for immutable workspace data; add a compact read-only list query scoped to `purpose = 'ordinary'` and projection-backed outcome.
- `backend/migrations/versions/0001_seed.py`, `0002_admission.py`, `0006_immutable_run_configuration.py` — Run schema, `created_at`, ordinary purpose, current migration head; no retry link column exists yet.
- `web/src/App.tsx:381`, `:440`, `:529`, `:543`, `:816` — Path routing, polling/focus, navigation, workspace render; add the history route and page without disturbing submission recovery.
- `web/src/styles.css` — Existing navigation, panel, focus, phone rules to extend for readable history rows.
- `backend/tests/test_single_image.py`, `web/src/App.test.tsx` — Existing API/client integration patterns for focused checks.

## Tasks & Acceptance

**Execution:**
- `backend/migrations/versions/0007_run_history.py` — Add nullable self-referential retry predecessor with unique direct successor constraint for durable lineage readout; leave retry creation to Story 3.2.
- `backend/app/adapters/postgres.py` — Add ordered ordinary-run history query and predecessor/successor fields to history and workspace; derive outcome only from succeeded projection.
- `backend/app/main.py` — Expose read-only `GET /runs` from the store.
- `web/src/App.tsx` and `web/src/styles.css` — Add `Анализы` navigation, loading/empty/error states, stable polling, linked rows, Russian labels and responsive layout.
- `backend/tests/test_single_image.py` and `web/src/App.test.tsx` — Cover mixed lifecycle, projection guard, exclusion, order, retained list on error, focus stability, and reopen.

**Acceptance Criteria:**
- Given persisted runs with mixed lifecycle states, when the user opens `Анализы`, then each ordinary row shows creation time, stage, intent, lifecycle, an available terminal outcome, and linked retry identity, and selecting a row opens its immutable Run Workspace.
- Given polling changes one run's state, when history refreshes, then row order and focus stay stable, and no unfinished or failed run gains an inferred outcome.
- Given empty, loading, or fetch-failure history, when the page is viewed, then the specified Russian state and recovery action appear.

## Spec Change Log

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 18 findings — high 0, medium 9, low 1, false 5, maybe-false 3
- findings:
  - `[medium]` `[patch]` History retained stale order on reentry — reset history state when leaving the route; reentry test passes.
  - `[medium]` `[patch]` A stalled history request never settled — added a ten-second abort and retry path; timeout test passes.
  - `[maybe-false]` `[defer]` Full-list polling may become costly — no measured run volume or load exists; measure before changing the complete-history contract.
  - `[maybe-false]` `[defer]` Legacy runs may lack creation times — the old schema stored none; a deployed old-run count and trustworthy timestamp source would settle impact.
  - `[false]` `[reject]` Admission predecessor could create a dead link — current application has no writer for retry_predecessor_id; Story 3.2 must validate ordinary lineage when it adds that writer.
  - `[false]` `[reject]` A retry cycle could be stored — current application has no writer for retry_predecessor_id; future retry creation must prevent cycles.
  - `[low]` `[patch]` The `other` stage appeared in English — rendered a Russian label and tested it.
  - `[medium]` `[patch]` Never-settling fetch lacked recovery — same timeout root cause as the second finding; bounded and tested.
  - `[medium]` `[patch]` Reopened history kept an old order — same reentry root cause as the first finding; reset and tested.
  - `[false]` `[reject]` Admission lineage could lead to a hidden workspace — no current application writer stores such lineage; Story 3.2 owns its write guard.
  - `[false]` `[reject]` Multi-run lineage could cycle — no current application writer stores lineage; the future retry endpoint must enforce a chain.
  - `[maybe-false]` `[defer]` Existing runs may lack creation time — same legacy timestamp limitation as the fourth finding; real deployed row count is unknown.
  - `[medium]` `[patch]` Admission exclusion test filtered the forbidden row before asserting — asserted absence from the full list.
  - `[medium]` `[patch]` Row details had no positive UI assertions — asserted stage, intent, lifecycle, outcome, time, and lineage.
  - `[medium]` `[patch]` Pending-outcome assertion checked the wrong label — asserted absence of the actual `no_check` label and the outcome field.
  - `[medium]` `[patch]` New-run timestamp default was untested — inserted a row without created_at and asserted its returned timestamp.
  - `[medium]` `[patch]` Sprint status was absent from the review diff — synchronize only Story 3.1 and Epic 3 after final verification, then read back.
  - `[false]` `[reject]` No new real-browser evidence retrieval test — navigation uses the existing workspace and artifact routes; CLI checks verify the new history boundary, while GUI use is disallowed by project instructions. Real rendering remains unverified.

## Design Notes

Earlier run rows have no recorded creation timestamp. Migration preserves that uncertainty as `NULL`; history displays `Время создания неизвестно` for those rows. New runs receive a database timestamp. Existing row positions remain stable during polling; newly discovered runs append until the page is reopened.

## Verification

**Commands:**
- `cd backend && uv run --offline pytest tests/test_single_image.py::test_ordinary_history_orders_and_guards_outcome tests/test_single_image.py::test_history_route_reads_store_without_starting_observer` — history API/SQL tests pass against an isolated migrated `TEST_DATABASE_URL`.
- `cd web && npm test -- --run && npm run build` — UI tests and type/build pass.

## Auto Run Result

Status: done

Implemented read-only ordinary-run history, retry lineage readout, stable polling, and navigation to the original Run Workspace. Synchronized Story 3.1 to `done` and Epic 3 to `in-progress`.

Files changed: `backend/migrations/versions/0007_run_history.py` adds timestamps and lineage fields; `backend/app/adapters/postgres.py` lists committed ordinary runs; `backend/app/main.py` exposes the list; `web/src/App.tsx` and `web/src/styles.css` add history navigation and states; `backend/tests/test_single_image.py` and `web/src/App.test.tsx` verify behavior; `sprint-status.yaml` records the targeted status.

Review: eight distinct patch groups resolved (nine medium and one low finding across reviewers); two unverified risks deferred in frontmatter. Five findings rejected because current application has no retry-link writer, or because the existing workspace is reused under a no-GUI constraint. See Review Triage Log for each finding and reason.

Verification: isolated PostgreSQL migrated to head; 2 focused backend SQL/API tests passed; 56 web tests passed; web build passed; sprint-status validation passed; `git diff --check` passed. The wider backend suite requires separate S3 integration configuration and was not run to completion. Real browser rendering and deployed runtime were not verified.

Follow-up review recommended: true. Review the history page against a real browser and backend with persisted evidence when GUI verification is available; the current run is limited to CLI and test surfaces.

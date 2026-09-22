---
title: 'Start the Evidence Service Safely'
type: 'feature'
created: '2026-09-22'
status: 'done'
baseline_revision: 'e10687e8e16bbbf4427e34280653dc9fb70ed8f8'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      A versioned S3 bucket might retain a health object version after delete.
    evidence: |-
      The probe verifies ordinary HEAD returns 404 after deletion, but no versioned S3 implementation was available in this run. A versioned-bucket integration check and the configured store's version-delete semantics would settle whether bytes remain.
    location: >-
      backend/app/adapters/artifacts.py:38
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The repository has no executable service. An unhealthy or misconfigured instance must not claim readiness or accept evidence work.

**Approach:** Seed the pinned backend and separated project structure, then expose process liveness and readiness guarded by PostgreSQL schema/write checks, a private S3 byte probe, and advisory-lock-fenced reconciliation and recovery. Enable one application-owned claim loop only after all gates pass.

## Boundaries & Constraints

**Always:** PostgreSQL is the only structured runtime and test store. Use the production SQLAlchemy and S3 adapters for startup probes. Keep secrets out of errors and logs. The S3 health key is unique under `health/`, outside publication namespaces, and its cleanup failure is fatal to readiness. Reconciliation is idempotent and evidenced; recovery must respect unexpired leases. Keep submission and executor claims behind the same readiness state.

**Never:** Create SQLite or a fallback repository, treat a health object as evidence, start a second claim loop, delete publication bytes during reconciliation, or introduce a live submission endpoint before its persisted run contract exists.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|----------------------------|----------------|
| Process alive | Gates pending or failed | `/health/live` returns live; `/health/ready` returns false and a stable gate code | No credentials in response |
| Invalid database | Non-PostgreSQL dialect URL | Startup rejects configuration before adapters or workers start | Stable configuration code |
| Database gate | Missing migration head or failed write/read | Readiness stays false | Stable database gate code |
| Artifact gate | Write, HEAD, read, or delete fails; bytes differ | Readiness stays false | Stable artifact gate code; cleanup still attempted after a successful write |
| Reconciliation | Empty intent set | One locked, recorded successful no-op | Lock or query failure blocks readiness |
| Ready | Every gate succeeds | `/health/ready` true; one claim loop enabled | Later loop failure revokes readiness |

</intent-contract>

## Code Map

- `README.md` -- project root currently contains only a placeholder; replace with startup and verification instructions.
- `spec.md` -- existing project description; read-only background.
- `_bmad-output/planning-artifacts/epics.md:321` -- Story 1.1 user-facing acceptance contract; read-only.
- `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:79` -- AD-9 startup order and single claim loop; AD-14 PostgreSQL-only ownership at line 107; AD-17 lock/recovery at line 113; AD-28 health namespace at line 161; structural seed at line 241. Read-only.
- `_bmad-output/implementation-artifacts/epic-1-context.md` -- condensed cross-story constraints; read-only.
- No backend, migration, lock, test, web, evaluation, or infrastructure code exists yet; seed only the Story 1.1 slice.

## Tasks & Acceptance

**Execution:**
- `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version` -- pin Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.54 and exact transitive dependencies; create package and CLI entrypoint.
- `backend/app/config.py`, `backend/app/main.py` -- validate explicit `postgresql+psycopg` configuration, coordinate startup gates in AD-9 order, serve stable live/ready JSON, and prohibit work before readiness.
- `backend/app/adapters/postgres.py`, `backend/migrations/` -- define the first migration and production SQLAlchemy adapter for head check, real rollback-safe write/read smoke, advisory-lock-fenced reconciler evidence and guarded empty-run recovery.
- `backend/app/adapters/artifacts.py` -- implement a private S3-compatible health probe with unique key, write/HEAD/read verification and mandatory cleanup outcome.
- `backend/app/application/executor.py` -- own exactly one dormant claim loop activated only by successful startup; preserve a readiness fence for future claim/submission paths.
- `backend/tests/`, `infra/` -- add PostgreSQL and S3-compatible integration checks for the matrix and runnable local service dependencies. Do not substitute mocks or SQLite for contract checks.
- `backend/app/domain/`, `backend/app/ports/`, `backend/app/profiles/`, `web/`, `evaluation/`, `README.md` -- establish the agreed concern boundaries with only useful seed content and document exact startup commands.

**Acceptance Criteria:**
- Given the documented clean installation, when the backend starts, then it uses the pinned Python and locked dependencies and exposes the separated repository concerns.
- Given any mandatory startup gate pending or failed, when a client requests readiness or future work submission, then readiness is false and no claim loop can acquire work.
- Given a database at migration head and reachable private artifact store, when the startup sequence runs, then it records a real database smoke, an isolated verified and cleaned S3 probe, one locked reconciliation pass, and guarded recovery before readiness becomes true.
- Given a healthy service, when the process serves health requests, then liveness reports process health, readiness reports true, and only one application-owned claim loop exists.
- Given integration verification, when the suite runs against PostgreSQL and an S3-compatible service, then it covers the failure cases in the matrix without a SQLite path.

## Spec Change Log

## Review Triage Log

### 2026-09-22 — Review pass
- verdicts: 19 findings — high 3, medium 9, low 2, false 4, maybe-false 1
- findings:
  - `[medium]` `[patch]` False readiness used HTTP 200 — HTTP status-only probes could admit an unready instance; changed the route to return 503 until ready.
  - `[false]` `[reject]` One-shot failed startup does not retry — the story requires failed gates to remain unready and does not require automatic retries; an operator restart reruns the gates.
  - `[false]` `[reject]` Readiness is not a continuous DB/S3 monitor — the story defines startup gates and a failed claim-loop revocation, not periodic dependency probes; no submission endpoint exists yet.
  - `[medium]` `[patch]` Ambiguous successful S3 PUT could leave a health object — the probe now attempts cleanup after every PUT attempt, including a lost response.
  - `[low]` `[patch]` Reconciliation failure audit recorded zero intents despite finding some — the failed pass now records the observed count.
  - `[medium]` `[patch]` Recovery locked live leased rows — the query now selects only expired or unknown leases with bounded lock waiting.
  - `[high]` `[patch]` Missing integration configuration silently skipped most tests — fixtures now fail clearly, and the README gives an isolated real-service verification path.
  - `[medium]` `[patch]` Fresh test database lacked migration setup — the README now migrates the isolated database and the fixture checks its head.
  - `[low]` `[patch]` Reusing the isolated test bucket could fail creation — the fixture now creates it only when absent.
  - `[high]` `[patch]` Test database could equal the application database — the fixture compares database targets before mutating test state.
  - `[medium]` `[patch]` Documented Compose startup had no readiness wait — Compose now waits for health and the README polls MinIO.
  - `[medium]` `[patch]` Alembic required S3 configuration while using only PostgreSQL — migrations now validate the database URL alone.
  - `[medium]` `[patch]` Lost PUT response could orphan a health object — same verified root cause and applied cleanup fix as the earlier S3 row.
  - `[maybe-false]` `[defer]` S3 versioning may preserve health bytes after a delete marker — settle with a configured versioned S3 implementation and its version-delete contract; the current MinIO test bucket is unversioned.
  - `[medium]` `[patch]` Recovery could wait on live row locks — same verified root cause and applied selective-query fix as the earlier recovery row.
  - `[false]` `[reject]` Probe does not verify bucket privacy — the story assumes a configured private bucket; privacy admission is a deployment/configuration precondition, not a specified probe operation.
  - `[medium]` `[patch]` Isolated test database needs migrations — same verified root cause and applied migration-head check as the earlier database row.
  - `[high]` `[patch]` Default `pytest` could pass without startup integration tests — same verified root cause and applied fail-on-missing-config fix; the reviewer observed 2 passed, 16 skipped before repair.
  - `[false]` `[reject]` Installed CLI server may diverge from ASGI tests — a live `uv run evidence-service` smoke against PostgreSQL and MinIO returned `{"live":true}` and `{"ready":true,"code":"ready"}`; no divergence remained.

## Design Notes

The empty reconciliation pass should persist a run row while holding a PostgreSQL advisory lock. It must scan the publication-intent namespace even when empty; later intent states can extend that scan. Recovery should inspect the run namespace and leave unexpired ownership intact; no placeholder success if an unknown running state is present.

## Verification

**Commands:**
- `cd backend && uv lock --check && uv sync --frozen` -- exact lock and environment succeed on Python 3.13.15.
- `cd backend && uv run pytest` -- integration checks pass with PostgreSQL and S3-compatible dependencies.
- `cd backend && uv run alembic upgrade head` -- fresh PostgreSQL schema reaches required head.

## Auto Run Result

Status: done

Implemented the pinned FastAPI backend with PostgreSQL-only migrations and smoke, isolated S3 health probe, fenced reconciliation, guarded recovery, live/ready endpoints, and one readiness-controlled claim loop. Added real PostgreSQL/MinIO integration tests and local operator instructions.

Files changed: `README.md` (setup and verification), `backend/pyproject.toml`, `backend/uv.lock`, `backend/.python-version` (pinned runtime), `backend/app/` (configuration, adapters, health, executor), `backend/migrations/` (schema), `backend/tests/test_startup.py` (integration coverage), `infra/` (local services and bucket setup), and `web/` plus `evaluation/` (concern boundaries).

Review: 10 grouped patches applied (high 2, medium 6, low 2); one medium unverified S3-versioning item deferred. Four findings rejected: automatic startup retry and continuous dependency probing are outside the defined startup-gate behavior, bucket privacy is a configured precondition, and a live CLI smoke disproved the alleged test/operator divergence. All 19 individual findings and their reasons are in the triage log.

Verification: `uv lock --check` passed; frozen sync passed on Python 3.13.15; Alembic upgraded isolated PostgreSQL; 19 integration tests passed against PostgreSQL and MinIO; the MinIO `mc ready local` healthcheck passed; a live `uv run evidence-service` returned successful liveness and readiness. `git diff --check` passed before finalization.

Follow-up review recommended: true. High-severity test isolation and fail-on-missing-config repairs were verified against temporary services, but a second independent review of the final verification path remains useful. Residual risk: S3 bucket versioning cleanup was not tested.

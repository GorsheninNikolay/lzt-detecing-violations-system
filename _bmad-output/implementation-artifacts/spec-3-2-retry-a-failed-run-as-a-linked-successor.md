---
title: 'Retry a Failed Run as a Linked Successor'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '7b5b3b6d5b34b299ec7e2841b8f91c749a82b258'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      Cross-operator visibility of history remains unverified.
    evidence: |-
      The current local application has no operator identity or ownership boundary, while existing run and artifact reads are already ID-addressable. A multi-operator deployment model would settle whether access controls are required.
    location: >-
      backend/app/main.py:181
    severity: medium (unverified)
  - summary: >-
      Rendered browser-to-server retry behavior remains unverified.
    evidence: |-
      HTTP integration and component tests pass, but GUI use is prohibited in this run. A permitted browser test would settle focus and navigation behavior in a rendered client.
    location: >-
      web/src/App.tsx:655
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A technical failure currently has no safe retry path. A new submission would lose lineage and might silently use different inputs or policy.

**Approach:** Let a failed ordinary run create one linked successor using its immutable analysis inputs and current authorized runtime profile. Expose both identities in the workspace and analysis history.

## Boundaries & Constraints

**Always:** Retry is failed-only, linear, and atomic under concurrent requests. Preserve the source run, stage evidence, artifacts, and invocation. Verify inherited source bytes before creation. Revalidate the current admitted profile, enabled authorization, runtime binding, and applicable local admission gates; snapshot the new binding. Keep image order, context, requested classes, intent, rule/policy, and taxonomy unchanged. A retry creates a fresh run with fresh stage rows and no inherited result projection.

**Never:** Resume or edit the failed run; classify technical failure as a negative observation; branch a lineage; silently switch profiles; offer retry on queued, running, or succeeded runs. Input edits belong to a distinct new analysis. Do not expose an alternative profile that the current worker cannot execute.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First retry | Failed ordinary run, verified source images, current admitted runtime binding | One queued successor with `retry_of_run_id`; preserved input order and snapshots | Return successor ID |
| Duplicate or concurrent retry | Same failed source, existing successor | Return that successor; never create another | Database uniqueness is final guard |
| Later failure | Failed successor | Create its one successor, maintaining a linear chain | Existing ancestor remains unchanged |
| Ineligible run | Queued, running, succeeded, missing, or admission run | No successor | Stable client-visible rejection |
| Invalid current binding or source | Revoked/drifted profile or corrupt/missing source bytes | No successor | Explain unavailable retry without changing source |

</intent-contract>

## Code Map

- `backend/migrations/versions/0001_seed.py`, `0002_admission.py`, `0003_single_image.py`, `0004_ordered_series.py` — current run/input/artifact schema; no lineage, run creation time, or history index. Add a forward migration.
- `backend/app/adapters/postgres.py` — `require_authorized` validates admission evidence and runtime identity; `commit_series_submission` atomically creates ordinary runs; `read_ordinary` projects immutable workspace; `resolve_run_artifact` checks run-local ownership. Add transactional successor creation, lineage/read/history, and run-local references to verified source objects.
- `backend/app/adapters/artifacts.py` — `read_verified` checks content address, hash, and size before retry inherits an object.
- `backend/app/main.py` — runtime binding and POST/GET routes; add retry route and history/read-only eligibility surface using the configured executable profile.
- `backend/app/application/executor.py` — worker claims only configured profile/revision; retry must bind that executable revision.
- `web/src/App.tsx` — route and Run Workspace polling, Russian failure states, immutable evidence; add retry action, lineage links, and history entry. Existing submission retry is unrelated.
- `backend/tests/test_single_image.py`, `backend/tests/test_ordered_series.py`, `web/src/App.test.tsx` — existing real PostgreSQL/S3 and web test patterns for HTTP and user flow.
- `_bmad-output/planning-artifacts/epics.md:812` and Epic 3 context — Story 3.2 contract; Story 3.1 history is not yet implemented, so add only the history slice needed to expose lineage.

## Tasks & Acceptance

**Execution:**
- `backend/migrations/versions/0005_retry.py` — add predecessor FK, unique direct-successor constraint, creation time, and inherited-artifact metadata support.
- `backend/app/adapters/postgres.py` — implement atomic failed-only retry, run-local source references, profile authorization recheck, and lineage/history read models.
- `backend/app/main.py` — expose retry, retry-eligible profile, and history routes with stable error codes; verify source bytes through the artifact store.
- `web/src/App.tsx`, `web/src/styles.css` — show Russian failed-run retry and predecessor/successor links in workspace and a small history route.
- `backend/tests/test_single_image.py`, `backend/tests/test_ordered_series.py`, `web/src/App.test.tsx` — test matrix failures, concurrent/idempotent retry, immutable predecessor, and visible UI lineage.
- `backend/app/adapters/postgres.py`, `web/src/App.tsx` — keep image verification outside the locked creation transaction, recheck the exact manifest under lock, and provide paged history with a truthful unknown time for runs predating this feature.
- `web/src/App.tsx` — distinguish history loading, empty, and fetch failure with a recovery action; ignore a late retry response after route navigation.
- `backend/tests/test_ordered_series.py` — compare all copied input/snapshot fields and execute a successor through the worker path to a completed projection.

**Acceptance Criteria:**
- Given a failed ordinary run with current authorization and intact source bytes, when I choose `Повторить анализ`, then I see a new queued run linked to the failed run and the earlier workspace/evidence remains available.
- Given two simultaneous retry requests for one failed run, when both complete, then history shows exactly one direct successor and both responses identify it.
- Given a failed successor, when I retry it, then history and workspace show one linear predecessor/successor chain.
- Given a queued, running, or succeeded run, when I open its workspace, then there is no retry action and navigation away does not cancel execution.
- Given a revoked profile or damaged source artifact, when I attempt retry, then I see an error and no successor exists.

## Spec Change Log

### 2026-09-24 — Review loop 1
- Trigger: artifact reads held database locks, history silently hid old runs and invented their creation time, and loading/failure states were incomplete.
- Amendment: require pre-lock source verification with a locked manifest recheck; nullable legacy creation time with explicit unknown display; paged history and loading/retry states; end-to-end successor execution and snapshot equality checks.
- Avoids: long authorization-lock stalls, invisible lineage, false timestamps, and unverified successor execution.
- KEEP: failed-only unique lineage, immutable predecessor, run-local inherited artifact records, Russian workspace links, and current executable-profile binding.

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 16 findings — high 0, medium 9, low 2, false 3, maybe-false 2
- findings:
  - `[maybe-false]` `[defer]` History may expose runs across operators — all existing run/artifact APIs lack ownership; current service binds localhost. A multi-operator deployment model would settle the risk.
  - `[medium]` `[bad_spec]` History silently stops at 100 — `list_ordinary` limits results and has no next page; add paging.
  - `[false]` `[reject]` Retry eligibility omits byte verification — the action is an eligibility hint; retry checks bytes and reports a blocking error without creating a run.
  - `[medium]` `[bad_spec]` Artifact reads hold source and authorization locks — `retry_ordinary` calls S3 under its transaction; verify before locks and compare manifest under lock.
  - `[false]` `[reject]` Admission may drift between checks — admitted evidence is immutable in application flows, and the locked recheck compares authorization state, revision, audit hash, and profile snapshot.
  - `[medium]` `[bad_spec]` Migrated runs gain an invented creation time — server default backfills historical rows; keep unknown legacy time explicit.
  - `[medium]` `[bad_spec]` History shows empty while loading and cannot recover fetch failure — add distinct loading and retry states.
  - `[low]` `[reject]` Downgrade fails with inherited artifacts — restoring the earlier schema after new dependent data requires data loss; a destructive downgrade is outside normal use.
  - `[medium]` `[bad_spec]` Old lineage falls outside latest 100 rows — same cap as the second finding; add paging.
  - `[low]` `[reject]` Downgrade cannot restore non-null intent IDs — same migration boundary as the eighth finding; destructive conversion is unwarranted.
  - `[medium]` `[patch]` Late retry response redirects after navigation — check current route before moving to the successor.
  - `[medium]` `[patch]` Successor never executes in tests — exercise claim and completion through the worker path.
  - `[medium]` `[patch]` Copied inputs and snapshots lack comparison tests — assert source/successor equality for all immutable analysis fields.
  - `[false]` `[reject]` Alternate profile selection is absent — the current server lists only its executable runtime binding; no other retry-eligible executable profile exists.
  - `[medium]` `[patch]` Sprint status remains backlog — synchronize the targeted story after final verified result.
  - `[maybe-false]` `[defer]` Integrated browser-to-server behavior is unverified — headless component/API tests pass; GUI use is prohibited, so live rendered behavior remains unobserved.

Review repair used forward corrections because automatic approval review rejected the workflow's full code-reversion step as destructive. The corrected diff keeps the verified lineage implementation and addresses all `bad_spec` and `patch` rows above.

## Verification

**Commands:**
- `cd backend && uv run --no-cache pytest tests/test_single_image.py tests/test_ordered_series.py` — retry and existing submission/execution checks pass against the project test services.
- `cd web && npm test -- --run` — workspace and lineage tests pass.
- `cd web && npm run build` — TypeScript and production bundle succeed.

## Auto Run Result

Status: done

Implemented: failed-only, linear, idempotent retry with a current executable profile; immutable predecessor, verified inherited source bytes, fresh successor stages, lineage in workspace and paged history.

Files changed: `backend/migrations/versions/0005_retry.py` adds lineage and truthful creation time; `backend/app/adapters/postgres.py` adds atomic successor creation and history reads; `backend/app/main.py` adds retry/history routes; `backend/tests/test_ordered_series.py` covers concurrent retries, immutable inputs, completed successor execution, and migration; `web/src/App.tsx`, `web/src/styles.css`, and `web/src/App.test.tsx` add and check Russian retry/history UI.

Review: four spec-level issues corrected (locking, history paging, historical time, loading/error states); three implementation patches applied (late response guard and two test gaps); sprint synchronization is handled after final verification. Rejected findings: source-byte eligibility is checked on retry; admission state is rechecked under lock; destructive downgrade conversion is not justified; no alternate executable profile is currently listed. Two uncertain risks are deferred above.

Follow-up review recommended: true. Four medium findings were triaged as patches, including the sprint synchronization, and the rendered browser-to-server flow remains unverified under the no-GUI instruction.

Verification: 18 backend integration tests passed against isolated PostgreSQL/S3; 32 web tests passed; web production build, Python compilation, and diff whitespace checks passed. Remote migration/deployment and rendered browser behavior were not checked.

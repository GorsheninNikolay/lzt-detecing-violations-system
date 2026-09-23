---
title: 'Follow Authoritative Pipeline Progress'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '55a2881edda1ff066de01e3cbd046c801a4a046b'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      The Run Workspace has not been exercised against a live ordinary-run API response.
    evidence: |-
      Component tests use fetch snapshots matching the documented GET shape, while backend tests verify persisted stages separately. A local full-stack run with PostgreSQL and the ordinary executor would settle the integration behavior.
    location: >-
      web/src/App.tsx
    severity: medium (unverified)
  - summary: >-
      Rendered horizontal and vertical pipeline behavior at laptop and narrow widths remains unverified.
    evidence: |-
      CSS defines six columns at laptop width and one below 1024px, but jsdom cannot measure layout. The user's working agreement prohibits opening or controlling GUI applications; a permitted rendered-browser inspection would settle it.
    location: >-
      web/src/styles.css
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The run route currently shows only one fetched run state and a placeholder. Managers cannot see committed stage transitions or distinguish execution failure from a lost connection.

**Approach:** Render the six backend stages on the existing run route and refresh the authoritative run snapshot while work is active. Preserve the last successful snapshot across read failures and announce meaningful changes once.

## Boundaries & Constraints

**Always:** Show all six stages in backend ordinal order using the exact Russian labels in `EXPERIENCE.md`; expose backend state, reason, and timestamp only when actually present. Keep completed stages visible after failure. Poll queued/running runs, stop at terminal states, and support an explicit status retry after disconnection. Use one polite status region for transition announcements, with no focus movement during polling. Support horizontal laptop and vertical narrow layouts.

**Never:** Infer stage state from elapsed time, input count, or client timers; show percentages or finish estimates; treat a read error as run failure; display technical reason codes as user-facing prose; expose Story 1.7 result details.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Queued then running | Committed snapshots on one run route | Six ordered stages update with factual states and summaries | Keep the prior snapshot during refresh |
| Terminal failure | Failed stage, completed and skipped stages with reasons | Show preserved stages and failure or skip explanation | Stop polling |
| Disconnection | A refresh rejects after a valid snapshot | Keep all prior stages and show `Проверить статус` | Retry reads the same run; do not announce false transitions |
| Missing run | First read returns 404 | Show `Анализ не найден` | Do not invent a pipeline |

</intent-contract>

## Code Map

- `web/src/App.tsx:124-205` -- run route and one-shot GET state; replace its run snapshot logic with polling and explicit retry, retaining route identity and focus behavior.
- `web/src/App.tsx:419` -- placeholder Run Workspace markup to replace; leave New Analysis behavior intact.
- `web/src/styles.css` -- existing full-night tokens and responsive breakpoints; add pipeline layout at 1024px.
- `web/src/App.test.tsx` -- existing route and submission tests; extend with committed transitions, terminal failure, disconnect, retry, and route switch.
- `backend/app/main.py:158-165`, `backend/app/adapters/postgres.py:676-710` -- GET returns one consistent committed snapshot with ordered `stages` containing `name`, `state`, `reason`; no stage timestamp or summary fields currently exist. Read-only unless a missing contract requires a narrow backend change.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:131-157` -- authoritative labels and state wording; read-only.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize Story 1.6 with verified workflow state.

## Tasks & Acceptance

**Execution:**
- `web/src/App.tsx` -- render run and stage snapshots, refresh active runs, retain known data on fetch errors, deduplicate transition announcements, and offer explicit retry.
- `web/src/styles.css` -- give the six-stage route a horizontal layout at laptop width and vertical layout below 1024px.
- `web/src/App.test.tsx` -- exercise the I/O matrix through the visible Run Workspace and API snapshots.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- reflect the story's verified status.

**Acceptance Criteria:**
- Given a queued or running backend run, when its workspace opens, then the same route shows six stages in ordinal order with exact Russian labels and backend-derived states.
- Given a committed transition, when polling reads it, then the changed stage and its available reason or timestamp appear without invented progress or focus movement, and the shared status region announces that transition once.
- Given a lost connection after a successful read, when polling fails, then the last known stages remain and `Проверить статус` retries the same run.
- Given a failed run, when its terminal snapshot arrives, then the failed stage and previously completed stages remain visible and later skipped stages show the backend-derived reason.
- Given laptop or narrower viewport, when the workspace renders, then the pipeline is horizontal at laptop width and vertical below 1024px.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 17 findings — high 0, medium 12, low 1, false 2, maybe-false 2
- findings:
  - `[medium]` `[patch]` A later 404 contradicted retained stages — the read now preserves the snapshot and reports that current status is unavailable.
  - `[low]` `[patch]` An unknown run state claimed execution — the heading now reports unknown status.
  - `[false]` `[reject]` An assertive terminal announcement was claimed as required — `EXPERIENCE.md` specifies one polite pipeline status region, which the UI uses.
  - `[medium]` `[patch]` The run container lacked `aria-busy` during reads — it now reflects the active read.
  - `[medium]` `[patch]` Repeated retry clicks could overlap requests — the retry button now shows checking and disables until the read settles.
  - `[medium]` `[patch]` Sprint tracking still said `backlog` — synchronized it to `review` during review and to `done` after final verification.
  - `[medium]` `[patch]` A stalled status request could stop progress indefinitely — reads now time out after ten seconds and expose retry.
  - `[medium]` `[patch]` A later 404 contradicted known state — the same retained-snapshot fix covers this independently reported case.
  - `[false]` `[reject]` `frame_decode_failed` was claimed as an ordinary-run reason — that code belongs to admission runs, while GET filters `purpose = 'ordinary'`; unknown reasons are in technical disclosure.
  - `[medium]` `[patch]` Disconnection was not announced — the shared status region now announces the connection warning.
  - `[medium]` `[patch]` Sprint status still said `backlog` — the same tracking update covers this independently reported case.
  - `[medium]` `[patch]` Successful completion and polling stop were untested — focused visible-behavior assertions now cover both.
  - `[medium]` `[patch]` Recovery could leave a stale warning — a focused test now verifies the notice clears and the refreshed snapshot appears.
  - `[medium]` `[patch]` Normal `not_applicable` explanation was untested — the successful-run test now asserts it.
  - `[maybe-false]` `[defer]` Component tests do not prove live API integration — a local PostgreSQL-backed ordinary run and UI read would settle it.
  - `[maybe-false]` `[defer]` CSS tests do not prove rendered laptop and narrow behavior — rendered inspection would settle it, but GUI use is prohibited.
  - `[medium]` `[patch]` Sprint status was absent from the reviewed diff — the tracking file is now included in this run's change set.

## Design Notes

The GET response currently has ordered stages but no stage timestamps or dedicated summaries. Render available state and translated reason; do not manufacture timestamps. A later backend timestamp addition can be shown when the field exists.

## Verification

**Commands:**
- `cd web && npm test -- --run && npm run build` -- Run Workspace behavior and type/build pass.
- `git diff --check` -- patch formatting is clean.

## Auto Run Result

Status: done

Implemented the Run Workspace's six-stage pipeline from ordered backend snapshots. Active runs poll the same route; terminal snapshots stop polling. A disconnected or stalled read preserves the last known stages and exposes an explicit retry. Stage changes and connection loss use one polite status region; polling does not move focus.

Files changed: `web/src/App.tsx` renders and refreshes the authoritative stages, translates known states and reasons, and handles retry and timeout; `web/src/styles.css` lays out the pipeline horizontally at laptop width and vertically below 1024px; `web/src/App.test.tsx` covers queued, running, failed, successful, missing, disconnected, timed-out, and route-switch states; `sprint-status.yaml` records Story 1.6 as done.

Review: 17 findings were triaged. Ten distinct patch entries were fixed (9 medium, 1 low), including later-404 consistency, stalled requests, retry state, disconnection announcements, and successful-completion verification. Two findings were rejected: the UX requires a polite pipeline status region, and `frame_decode_failed` applies to admission rather than ordinary runs. Two unverified items were deferred: live ordinary-run API integration and rendered layout at narrow and laptop widths. Follow-up review recommended: true, because those two surfaces remain unverified after the medium patch work.

Verification: `npm test -- --run` passed 16/16, `npm run build` passed, `git diff --check` passed, and the YAML frontmatter parsed with two retained deferred entries. The backend was read for contract shape but no live full-stack run was performed. GUI inspection was prohibited by the user's working agreement.

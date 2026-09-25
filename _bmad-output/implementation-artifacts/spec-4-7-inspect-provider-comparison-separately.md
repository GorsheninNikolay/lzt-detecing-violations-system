---
title: 'Story 4.7: Inspect Provider Comparison Separately'
type: 'feature'
created: '2026-09-25'
status: 'done'
baseline_revision: 'caa6bbc80c74aed5f2f855ad2ad500b8966cb971'
review_loop_iteration: 2
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      A headless full-stack rendered journey against a persisted comparison campaign has not been observed.
    evidence: |-
      The isolated PostgreSQL persistence test, HTTP test and mocked React tests passed separately. An integrated headless run would settle their joined behavior and responsive rendering; no such run was completed.
    location: >-
      web/src/ProviderComparisonPage.tsx
    severity: medium (unverified)
  - summary: >-
      The comparison projection has not been tested with a persisted successful campaign cell.
    evidence: |-
      The isolated PostgreSQL test covers planned cells; a separate existing S3-dependent execution test reaches a successful cell, but the required S3 service is unavailable in this environment. Running that path and checking the projected outcome and observations would settle the gap.
    location: >-
      backend/tests/test_comparison_campaign.py
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A jury member can inspect prototype readiness, but cannot independently inspect the frozen local-versus-cloud comparison, its missing cells, or the candidates' admission limits.

**Approach:** Expose a safe read-only projection of the latest frozen comparison campaign and render it on a separate Russian Provider Comparison route. Use persisted cell and admission evidence, with links to retained runs; never select a winner.

## Boundaries & Constraints

**Always:** Show campaign and evaluation revision identity, candidate/profile/authorization revision and returned identity, per-candidate planned and terminal counts, failed, timed-out and missing cells, repeat disagreement, measured latency and cost availability. Distinguish measured results from commercial/data gates and unresolved identity or evidence gaps. Preserve fixture, repeat and candidate identities and run links. An incomplete matrix explicitly says `Сравнение не завершено`; loading, absence and refresh failure have accessible retry and preserve the last known snapshot/time.

**Never:** Expose raw profile snapshots, account or service identifiers, hashes authorized for upload, rights attestations, secrets, provider request controls or image bytes through the comparison API. Never derive a winner score, publish `ActiveObserverConfiguration`, regenerate reports, mutate a campaign on read, or treat an admission as present when it is absent.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Frozen complete or incomplete campaign | Open Provider Comparison | Separate candidate and cell evidence, literal counts and available measures | Incomplete says `Сравнение не завершено`; no winner |
| No campaign | Open Provider Comparison | Explicit no-data state and retry | No inferred comparison |
| Refresh failure or later 404 | Previously loaded comparison | Retain snapshot and its time, mark stale and offer retry | No false fresh state |
| Technical detail and cell link | Expand candidate, open run | Safe admission/gap details and retained run evidence | Missing run says unavailable |

</intent-contract>

## Code Map

- `backend/app/adapters/postgres.py:172` — `read_comparison_campaign` already joins frozen manifest and ordinary run cells with repeat/fixture/candidate keys, state, error, latency and evidence; do not return its raw manifest or projections to HTTP. Add deterministic latest-campaign read and a strict safe projection. `:297` shows latest report readback pattern.
- `backend/app/domain/evaluation_report.py:121` — repeat disagreement definition compares terminal repeated cells; reuse the same semantics, including denominator of complete groups. Its cost measure is explicitly unavailable because cost is not recorded.
- `backend/app/domain/comparison_campaign.py:60` — manifest fixes two candidate ordinals, three repeats, six fixtures, profile snapshots and revisions. Only selected safe fields may cross the HTTP boundary.
- `backend/app/profiles/cloud_api.py:275` and `backend/app/profiles/grounding_dino.py:56` — admitted snapshots carry returned identity, rights and cloud owner evidence; many fields are sensitive. Project only gate status, checked time or decision revision where safe, and named unresolved gap.
- `backend/app/main.py:172` — `/readiness` is the read-only, no-store route and error pattern; `/runs/{id}` already reads comparison-run evidence.
- `web/src/App.tsx:382` and `:975` — route matching, title, navigation and page branch. `web/src/ReadinessPage.tsx` — fetch, stale retry, semantic tables and run links to reuse as patterns. `web/src/styles.css` — incumbent dark tokens and responsive table treatment.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — persistent campaign/API and rendered route tests.
- `_bmad-output/implementation-artifacts/sprint-status.yaml:49` — update only Story 4.7 after verified completion with canonical sprint tooling.

## Tasks & Acceptance

**Execution:**
- `backend/app/adapters/postgres.py` — select latest frozen campaign deterministically; project only safe candidate/admission fields, each planned cell with its expected and observed outcome and portable observation summary, and literal per-candidate accounting from the frozen manifest and retained states; compute repeat disagreement consistently with report semantics without requiring a report.
- `backend/app/main.py` — expose a no-store comparison read route with explicit absent/unavailable responses.
- `web/src/ProviderComparisonPage.tsx` — show separate candidate technical detail, accounting and matrix with expected versus observed outcome, portable class observations and run links; distinguish latency from successful and failed runs, unmeasured cost, unevaluated repeat groups and missing evidence; distinguish frozen admission from current authorization; show incomplete banner and bounded stale retry; use Russian copy and semantic tables/disclosures.
- `web/src/App.tsx`, `web/src/styles.css` — add separate route and navigation, title and responsive styling within the established visual system.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — cover the I/O matrix, safe projection, incomplete/complete accounting, disagreement, technical detail, run navigation and stale state.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — synchronize only Story 4.7 through official updater after verification, validate and reread.

**Acceptance Criteria:**
- Given a complete or incomplete frozen campaign, when the jury member opens Provider Comparison, then both candidates show profile revision and identity, literal planned/terminal/failed/timed-out/missing cells, expected and observed outcomes and class observations, repeat disagreements, latency and cost availability, separately from readiness criteria.
- Given an incomplete campaign, when the matrix renders, then `Сравнение не завершено` is visible and every pending, failed or timed-out cell remains traceable to its fixture/repeat/candidate and run when one exists.
- Given local or cloud admission evidence, when technical detail expands, then measured performance, commercial/data gate state, returned identity and unresolved gaps are distinguished without exposing sensitive account or request data.
- Given a cell link, when it opens, then the existing run route shows retained source and observation evidence without making the run eligible for ordinary retry or history.
- Given no data or a failed refresh, when the view updates, then it offers a nearby retry and never infers a winner, selection or readiness verdict; a previously loaded snapshot remains marked stale with its saved time.

## Spec Change Log

### 2026-09-25 — Review repair 1
- Trigger: the first comparison matrix exposed lifecycle and latency but omitted expected/observed outcomes and portable observations; measured results were not directly comparable on the page.
- Added explicit outcome and observation projection and presentation, success/failure latency distinction, unevaluated repeat handling, and frozen/current admission labels. Preserve the safe allowlist API, immutable campaign accounting, separate route, stale retry, and passing focused checks. Repair is applied in place to preserve the reviewed implementation.

### 2026-09-25 — Review repair 2
- Trigger: manual labels were absent from the comparison matrix and stored manifest integrity was not checked on the new read path.
- Added safe frozen labels, explicit outcome mismatch, fail-closed malformed evidence, campaign and evaluation manifest hash checks, linked latency presentation, and production route documentation. Preserve the separate route, literal accounting, safe allowlist, and validated sprint update.

## Review Triage Log

### 2026-09-25 — Review pass 1
- verdicts: 13 findings — high 0, medium 8, low 4, false 0, maybe-false 1
- findings:
  - `[medium]` `[bad_spec]` Candidate results lacked a direct performance comparison — added expected and observed outcomes and portable class observations to the API and matrix.
  - `[medium]` `[bad_spec]` Fixture expectation was absent — projected the frozen expected outcome and displayed it for each planned cell.
  - `[medium]` `[bad_spec]` Cell outcome was absent — projected the persisted outcome and displayed missing results explicitly.
  - `[medium]` `[patch]` Failed-run latency was mixed with successful latency — separated both literal populations and labeled each cell.
  - `[low]` `[patch]` Frozen audit evidence looked like a current authorization claim — labeled it as frozen evidence and current authorization separately.
  - `[low]` `[reject]` Authorization rows can change during the multi-query read — current state is informational and explicitly labeled current; a transactional snapshot would add complexity without changing the frozen result or any decision.
  - `[low]` `[patch]` Frozen and current authorization times were unclear — labeled the freeze revision and current state independently.
  - `[medium]` `[patch]` Zero complete repeat groups read as zero disagreements — the page now says the groups are unevaluated.
  - `[low]` `[reject]` A stale comparison run link opens the generic not-found page — null cells already say the run is unavailable; a deleted run is exceptional and browser back returns to the campaign.
  - `[medium]` `[patch]` Recorded cloud data and paid-account gates lacked a UI assertion — added a rendered cloud case with decision revision, check time and revoked current authorization.
  - `[medium]` `[patch]` Sprint ledger still marked Story 4.7 backlog — the canonical generator set only the targeted story to done, then validator and readback passed.
  - `[medium]` `[patch]` Intent alignment independently found the same unsynchronized ledger entry — the same validated targeted update resolved it.
  - `[maybe-false]` `[defer]` No full-stack rendered jury journey is proven — isolated persistence, API and mocked UI checks pass; a headless integrated run with a persisted campaign would settle the remaining contract risk.

### 2026-09-25 — Review pass 2
- verdicts: 12 findings — high 0, medium 7, low 3, false 1, maybe-false 1
- findings:
  - `[medium]` `[bad_spec]` Frozen manual labels were absent beside observations — projected safe labels and displayed them in each matrix row.
  - `[medium]` `[patch]` Unknown stored outcome or observation values looked absent — invalid values now fail the comparison read.
  - `[false]` `[reject]` Duplicate or out-of-range cell keys could silently alter counts — the database has a composite primary key, ordinal check constraints, and immutable comparison-cell rows.
  - `[low]` `[reject]` Repeat disagreement could use hidden observations — the new projection rejects unknown classes or states, and both calculations use the same portable class/state/frame observations.
  - `[low]` `[patch]` Returned identity looked like a campaign measurement — its label now identifies the frozen admitted profile as the source.
  - `[medium]` `[patch]` Outcome mismatches were hard to scan — terminal mismatches now have an explicit message in the matrix.
  - `[low]` `[patch]` Candidate latency values lacked cell links — summary now gives counts and directs readers to linked values in the matrix.
  - `[medium]` `[patch]` Manifest was not integrity-checked on the new route — the read now verifies campaign and bound evaluation manifest hashes before projection.
  - `[medium]` `[patch]` Production route instructions omitted Provider Comparison — documented API proxy and page history fallback in web README.
  - `[maybe-false]` `[defer]` Integrated rendered journey remains unobserved — carried from pass 1; a headless run with persisted campaign would settle it.
  - `[medium]` `[defer]` Persisted successful outcome and observations are not checked through the new read method — the available isolated DB case covers planned rows; an S3-backed execution case is needed.
  - `[medium]` `[defer]` Intent alignment confirms the same integrated-journey evidence gap — carried from pass 1, with separate component checks and validated ledger sync.

### 2026-09-25 — Review pass 3
- verdicts: 16 findings — high 0, medium 8, low 5, false 0, maybe-false 3
- findings:
  - `[medium]` `[patch]` Failed cell without outcome looked like measured mismatch — mismatch now requires an observed outcome.
  - `[medium]` `[patch]` Class disagreements required manual scanning — measured yes/no comparisons now label misses and false detections.
  - `[medium]` `[patch]` Failed-run observations looked complete — marked them as partial evidence.
  - `[low]` `[reject]` Candidate latency has no separate aggregate numeric summary — each literal value and run link is in the matrix, and a second summary would duplicate it.
  - `[low]` `[reject]` Per-invocation returned identity is absent — the page explicitly labels frozen admission identity; the run evidence remains reachable and execution already rejects identity drift.
  - `[low]` `[patch]` Current authorization row could imply effective permission — relabeled it as recorded state and revision.
  - `[medium]` `[patch]` Free-text error code crossed the new public API — timeout codes remain literal and other failures become `campaign_failure`.
  - `[low]` `[patch]` Fully terminal failed campaign lacked explanatory state — added completed-with-errors copy.
  - `[maybe-false]` `[defer]` Persisted successful result may fail to traverse the new read path — carried S3-dependent verification gap; successful-cell test would settle it.
  - `[medium]` `[patch]` Two-candidate matrix mapping lacked a rendered test — added distinct cloud outcome, observation and run-link assertions.
  - `[low]` `[reject]` Done status lacks the full-stack caveat in sprint YAML — the canonical ledger tracks implementation status; evidence limits are in this spec, and only Story 4.7 was synchronized.
  - `[maybe-false]` `[defer]` Verification-gap reviewer independently confirmed the persisted-success test gap — carried from pass 2; S3-backed execution would settle it.
  - `[medium]` `[patch]` Evaluation manifest mismatch branch lacked a test — added a focused rejection case.
  - `[medium]` `[patch]` Verification-gap reviewer independently found missing-outcome mismatch — fixed with the same non-null guard.
  - `[medium]` `[patch]` Edge-case reviewer independently found missing-outcome mismatch — fixed with the same non-null guard.
  - `[maybe-false]` `[defer]` Intent alignment again found no joined rendered journey — carried from pass 1; the headless integrated path remains unobserved.

## Design Notes

The API should treat the manifest as the denominator and include cells even when their run is still planned or unexpectedly absent. A campaign is immutable, but cells progress; the displayed time is the latest successful read time, explicitly labeled as such rather than a persisted report creation time. Each candidate's measures are literal, not normalized into a score. If the campaign lacks cost records, show unavailable rather than zero.

## Verification

**Commands:**
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest tests/test_comparison_campaign.py::test_provider_projection_is_safe_and_accounts_for_each_planned_cell tests/test_startup.py::test_provider_comparison_http_is_read_only_and_no_store -q` — focused projection and HTTP cases pass.
- `cd backend && TEST_DATABASE_URL=<isolated migrated PostgreSQL URL> UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest tests/test_comparison_campaign.py::test_latest_provider_comparison_reads_frozen_cells_without_mutation -q` — real persistence read passes against an isolated database.
- `cd web && npm test -- --run` — UI states and navigation pass.
- `cd web && npm run build` — production TypeScript build passes.
- `UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run .agents/skills/bmad-sprint-planning/scripts/sprint_plan.py validate --status-file _bmad-output/implementation-artifacts/sprint-status.yaml` — canonical ledger valid.
- `git diff --check` — whitespace clean.

## Auto Run Result

Status: done. Story 4.7 adds a separate Russian Provider Comparison route backed by a read-only, safe projection of the latest frozen campaign. It shows both candidates, immutable profile identity and admission limits, planned and terminal cells, errors, timeouts, missing evidence, repeat disagreements, expected outcomes, frozen manual labels, portable observations, latency, unavailable cost and links to retained runs. No winner or active observer selection is published.

Files changed:
- `backend/app/adapters/postgres.py`, `backend/app/domain/provider_comparison.py`, `backend/app/domain/evaluation_report.py`, `backend/app/main.py` — deterministic campaign read, manifest integrity checks, allowlisted comparison data, shared disagreement semantics and no-store API.
- `web/src/ProviderComparisonPage.tsx`, `web/src/App.tsx`, `web/src/styles.css`, `web/README.md` — separate accessible route, candidate and cell evidence, stale retry, responsive styling and deployment routing instructions.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — safe projection, integrity, HTTP and rendered-state regression checks.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — only Story 4.7 moved from backlog to done using the canonical generator; the file timestamp changed and its YAML emitter reflowed one existing action-item line without changing its value.

Review: three passes identified missing substantive comparison evidence, labeling and integrity checks. The final pass patched eight medium and two low root-cause groups (including duplicate reports of one missing-outcome defect); three low findings were rejected for lack of material harm. A follow-up review is recommended because several medium fixes followed the last review. The concrete remaining risk is the unobserved joined journey with a persisted successful campaign.

Verification: 8 focused backend tests passed after final changes; one isolated, migrated PostgreSQL persistence test passed; all 93 web tests and the production TypeScript/Vite build passed. The canonical sprint validator and YAML readback passed. `git diff --check` passed. The full backend suite could not run because the required S3 test service and configuration are unavailable; its initial attempt reported 15 passing tests and 90 environment setup errors. A persisted successful comparison cell and a full-stack headless rendered journey remain unverified. No GUI application was used.

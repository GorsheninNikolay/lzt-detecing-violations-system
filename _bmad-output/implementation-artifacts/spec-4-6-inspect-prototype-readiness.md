---
title: 'Story 4.6: Inspect Prototype Readiness'
type: 'feature'
created: '2026-09-25'
status: 'done'
baseline_revision: '84e13b1d1cad06f5119385a8f3ca534077779038'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: [oversized]
deferred:
  - summary: >-
      The readiness journey has no observed full-stack rendered verification against a persisted report.
    evidence: |-
      PostgreSQL/S3 backend tests and mocked React tests passed separately. A headless integrated run with a persisted report would settle whether the API response, rendered page, and source links join at the outer surface.
    location: >-
      web/src/ReadinessPage.tsx
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** The immutable criterion report exists only through an operator CLI. A jury member cannot inspect its evidence in the product, and comparison run IDs do not open in the existing run route.

**Approach:** Expose the latest persisted, integrity-checked report and its bound evaluation metadata through a read-only API. Add a Russian readiness page with literal measures, accessible criterion disclosures, and working links to retained runs and artifacts.

## Boundaries & Constraints

**Always:** Select the latest persisted report deterministically; show its stored creation time and exact report, campaign, evaluation-set, policy, and rule identities. Display all 11 image checksums, manual labels, and per-image sufficiency notes from its bound frozen evaluation revision. Show `Пройдено`, `Не пройдено`, `Нет данных` strictly from server criterion statuses; preserve failed and missing populations, report incompleteness, literal denominators, and unavailable cost/comprehension. Failed refresh retains the last known report with its timestamp and a nearby retry, marked stale. Each criterion's evidence opens an actual campaign run; run artifacts remain integrity-checked.

**Never:** Generate or mutate an evaluation report on page load, fabricate missing evidence or measurements, infer pass from cached fragments, publish a score or model winner, expose source bytes/credentials/provider secrets in the metadata response, or fold Story 4.7 provider comparison into this page.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stored complete or incomplete report | Open `Готовность` | Bound identities, all image/label/sufficiency metadata, all criterion states, literal measures and run/evidence links | Incomplete remains explicit, never pass |
| No stored report | Open `Готовность` | Clear `Нет данных` state and retry | No misleading readiness verdict |
| Read/refresh fails | Previously loaded or first load | Keep last report and time when present; announce stale state and show retry | No fabricated fresh status |
| Criterion evidence | Expand row and select run/input/artifact | Campaign run route opens persisted observations and source evidence | Missing run/artifact says unavailable without hiding criterion |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:1000` and `_bmad-output/implementation-artifacts/epic-4-context.md` — Story 4.6 contract; Story 4.7 owns provider comparison.
- `backend/app/adapters/postgres.py:172` — campaign snapshot; `:242` report generation; `:281` integrity-checked report readback; add a latest-report read joined to its frozen evaluation revision without regenerating evidence. Project safe fixture ordinal/scenario/expected outcome from the bound campaign; never recalculate expected outcomes in the client.
- `backend/migrations/versions/0013_evaluation_report.py` — immutable report rows already contain `created_at`, `campaign_id`, `evaluation_revision_id`; no schema change expected.
- `evaluation/held-out-v1.json` and `backend/app/domain/evaluation_set.py:23` — frame fields to project: ID, ordinal, scenario, image checksum, manual labels, sufficiency notes; do not return archive paths or rights attestations.
- `backend/app/main.py:172` — read-only HTTP routes; `/runs/{id}` currently calls `read_ordinary`, which excludes comparison runs.
- `backend/app/adapters/postgres.py:1384` — existing run detail and artifact associations; reuse its read shape for comparison runs without relaxing ordinary history/retry rules.
- `web/src/App.tsx:148` — `ObservationResult` currently returns early for failed runs with no observations; retain the input-only source viewer for comparison runs. `:382` routes; `:972` navigation.
- `web/src/styles.css` — dark, responsive panel and focus styles; add only readiness table/disclosure layout.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — PostgreSQL/S3 report contract, HTTP route, and accessible page state tests.
- `_bmad-output/implementation-artifacts/sprint-status.yaml:48` — synchronize only Story 4.6 after verified completion using the canonical updater and validator.

## Tasks & Acceptance

**Execution:**
- `backend/app/adapters/postgres.py` — select latest immutable report with creation time, bound evaluation frames and safe campaign fixture expectations; permit read-only detail for comparison run IDs while keeping ordinary list/retry behavior scoped.
- `backend/app/main.py` — expose safe readiness read and comparison run read routes; return explicit missing/unavailable errors and no-store cache policy.
- `web/src/App.tsx` — add `/readiness` destination and page; show retained source inputs for a failed comparison run even with no observations.
- `web/src/ReadinessPage.tsx` — show overall `pass|fail|incomplete` in Russian, then failed criteria first; explicitly separate pending evidence. Each expanded criterion identifies expected versus observed outcome or manual label versus observation where applicable. Make numeric measure evidence reachable, including disagreement run groups. Use Russian scenario/state labels, table captions, label-coverage counts, accessible disclosure, and a bounded fetch timeout; preserve a stale report on error or a later 404.
- `web/src/styles.css` — responsive readable tables, wrapped hashes, and visible keyboard focus.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — verify the I/O matrix, immutable selection, all 11 projected frames, metadata minimization, no-report, timeout, later-404 and failure states, expected/observed evidence, numeric-measure links, and input-only failed-run navigation.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — mark only Story 4.6 done after checks; validate and reread the canonical ledger.

**Acceptance Criteria:**
- Given a persisted complete or incomplete EvaluationReport, when a jury member opens `Готовность`, then each criterion shows its persisted status, reason, numerator/denominator, and reachable run evidence alongside bound revision and image metadata.
- Given a failed criterion, when the page renders, then it is prominent before passing criteria and no decorative aggregate score or winner appears.
- Given loading, absent report, or fetch failure, when the page updates, then it has semantic busy/error states, a nearby retry, and preserves the last known report time where available.
- Given a criterion evidence link, when the linked campaign run opens, then source input and artifact can be inspected without enabling ordinary retry or placing the run in ordinary history.
- Given a failed or pending criterion, when its disclosure opens, then a jury member can identify the exact expected and observed or missing evidence and follow the linked run; a failed run with only retained inputs still exposes its source images.
- Given a literal measure with retained evidence, when the measure is expanded, then its contributing run or group is reachable without deriving an aggregate score.

## Spec Change Log

### 2026-09-25 — Review repair 1
- Trigger: criterion disclosures lacked expected-versus-observed explanations; measure evidence was counted but unreachable; input-only failed runs hid source images. The first plan named only generic evidence links, which allowed a page that could not reproduce its own failures.
- Amended the Code Map, tasks, and ACs to require authoritative fixture expectations, explicit criterion/measure evidence, retained input viewing, Russian overall and row states, table captions, label coverage, bounded loading, and complete projection tests. Avoid the known-bad state where a jury member sees a count but cannot trace why it failed or which source remained.
- KEEP: immutable latest-report readback with integrity checks, minimal frozen frame metadata, no-store HTTP, ordinary history/retry separation, accessible native disclosures, and the verified 102 backend / 79 web test baseline. Rebuild these behaviors rather than dropping them.
- The workflow's destructive reset was rejected twice by automatic approval review; repair proceeds in place while preserving the existing diff.

## Review Triage Log

### 2026-09-25 — Review pass
- verdicts: 16 findings — high 0, medium 13, low 2, false 0, maybe-false 1
- findings:
  - `[medium]` `[bad_spec]` Overall fail/pass is absent — `ReadinessPage` only announces `incomplete`; amended page task to show the persisted overall state in Russian.
  - `[medium]` `[bad_spec]` Pending evidence is buried in the full population — no separate pending disclosure exists; amended page task to identify pending cells explicitly.
  - `[medium]` `[bad_spec]` Outcome misses lack expected/observed comparison — row omits existing observed outcome and API omits bound fixture expectation; amended API and page tasks to present both.
  - `[medium]` `[bad_spec]` Detection misses lack label/observation comparison — row omits available observation detail and bound manual label; amended page task to present both.
  - `[medium]` `[bad_spec]` Numeric measures discard retained evidence links — `ReadinessPage` reads counts but not measure `evidence`; amended page task to expose contributing runs and disagreement groups.
  - `[medium]` `[bad_spec]` Failed comparison run without observations hides its source — `ObservationResult` returns before rendering retained inputs; amended `App.tsx` task to keep the input-only viewer.
  - `[medium]` `[bad_spec]` Readiness tables omit captions — source has headers but no `<caption>`; amended page task to add semantic captions.
  - `[medium]` `[bad_spec]` Label coverage needs manual tally — per-frame labels are shown but no positive/negative/unknown totals; amended page task to summarize exact frozen-label counts.
  - `[low]` `[bad_spec]` Raw English states and scenario keys interrupt the Russian evidence explanation — amended page task to label known codes in Russian while keeping exact technical IDs available.
  - `[low]` `[reject]` Broader comparison-run read path — comparison IDs remain UUID-bound, ordinary APIs already expose run artifacts by ID, and no narrower HTTP authorization boundary exists in the product; report scoping would add a new access rule without an evidenced everyday defect.
  - `[medium]` `[bad_spec]` Unbounded readiness fetch can leave the page busy forever — no timeout in the new effect; amended page task to abort and offer retry.
  - `[medium]` `[bad_spec]` Input-only failed comparison run hides source, independently found — same early return as the sixth finding; amended the single `App.tsx` task.
  - `[medium]` `[bad_spec]` Frozen-frame projection test checks only frame 0 — the API projects eleven frames; amended test task to compare all eleven to the bound revision.
  - `[medium]` `[bad_spec]` Later 404 retention lacks a test — current code preserves the snapshot but a regression would evade tests; amended test task to assert saved report/time and stale warning after refresh 404.
  - `[medium]` `[patch]` Sprint status still says Story 4.6 `backlog` — synchronization is deliberately sequenced after final verification; the targeted canonical entry remains to update before completion.
  - `[maybe-false]` `[defer]` No full-stack rendered journey is in this diff — backend PostgreSQL/S3 and mocked React layers passed separately; a headless integrated run against a persisted report would settle whether their contracts join at the outer surface. Medium if a mismatch exists; no mismatch was observed.

### 2026-09-25 — Review pass 2
- verdicts: 17 findings — high 0, medium 7, low 6, false 2, maybe-false 2
- findings:
  - `[low]` `[reject]` Planned-cell evidence lists manifest cells including a missing cell — `build_report` uses all 36 manifest references and labels the missing row explicitly; a missing persisted cell is exceptional, and separate coverage criterion already exposes it. Another view would duplicate the matrix.
  - `[low]` `[reject]` Evidence rows use candidate ordinals without provider names — Story 4.7 owns provider comparison; Story 4.6 keeps readiness separate and ordinal plus run ID still trace the cell.
  - `[false]` `[reject]` Out-of-scope requested class cannot be identified — the frozen sufficiency note explicitly says the test requests unsupported crane; the note is displayed in the eleven-frame table.
  - `[low]` `[reject]` Frozen sufficiency notes remain in English — they are exact immutable source notes, while navigation, state, scenario summary, and headings are Russian; duplicating eleven translations risks changing evidence meaning.
  - `[medium]` `[patch]` Comparison run exposed full cloud profile metadata — projected only `adapter.code` for comparison runs, retaining ordinary read shape, and asserted local/cloud filtered responses.
  - `[low]` `[patch]` Campaign run looked like an ordinary analysis — added a visible `Доказательство сравнительной кампании` designation and a navigation test.
  - `[medium]` `[patch]` Raw artifact URL showed JSON on read failure — readiness now shows the artifact ID beside the run link and routes inspection through the existing source viewer with inline integrity errors.
  - `[low]` `[reject]` Repeat disagreement lacks an inline comparison of every run field — the report retains all run IDs and the page links each one; the separate comparison analysis belongs to Story 4.7.
  - `[low]` `[patch]` Cost/comprehension lacked unavailable reasons — rendered Russian explanations for known persisted codes and retained an unknown code visibly.
  - `[false]` `[reject]` Immutable row policy/digest can diverge from served report through the normal path — generation inserts them together with the snapshot, DB triggers reject later mutation, and verified artifact bytes and criterion rows must equal the snapshot; no reachable mismatch was demonstrated.
  - `[medium]` `[patch]` Story 4.6 remained `backlog` — changed only its canonical status to `done`, updated `last_updated`, validated and reread the ledger.
  - `[maybe-false]` `[defer]` Carried: integrated rendered journey has not been observed; a headless product run with a persisted report would settle the separate-layer contract risk.
  - `[medium]` `[patch]` Eleven-frame rendering was weakly tested — asserted all eleven displayed rows against their ID, checksum, labels, and sufficiency note.
  - `[medium]` `[patch]` False-warning criterion was absent from UI fixture — added its failed row and asserted status, expectation/fact, and run link.
  - `[medium]` `[patch]` Metadata integrity failure path lacked a regression — simulated a mismatched report/campaign binding and asserted read rejection plus HTTP 503 mapping.
  - `[medium]` `[patch]` Carried: Story 4.6 sprint status was not synchronized — the same targeted ledger change as the eleventh finding is now validated.
  - `[maybe-false]` `[defer]` Carried: no full-stack rendered product journey was checked; backend integration and mocked UI tests remain separate evidence layers.

## Design Notes

The report is a snapshot, not a live verdict. The API should read the newest stored row by `created_at DESC, id DESC`, then use the existing verified report readback. The frontend should label it by that persisted time, not the time of fetch. A comparison run is still an `AnalysisRun`; exposing its evidence through the existing result presentation requires a purpose-aware read path, while ordinary history and retry remain restricted. Avoid returning the full evaluation or campaign manifest because they include archive/provenance and profile material irrelevant to this page. Project only fixture identity and expected outcome for comparison with persisted run outcome; do not copy profile snapshots or provider configuration into the readiness response.

## Verification

**Commands:**
- `cd backend && UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run --extra test pytest tests/test_comparison_campaign.py tests/test_startup.py -q` — focused API and report cases pass against isolated PostgreSQL/S3.
- `cd web && npm test -- --run` — readiness and existing UI cases pass.
- `cd web && npm run build` — TypeScript and production build pass.
- `UV_CACHE_DIR=/private/tmp/lzt-bmad-uv-cache uv run .agents/skills/bmad-sprint-planning/scripts/sprint_plan.py validate --status-file _bmad-output/implementation-artifacts/sprint-status.yaml` — canonical status valid.
- `git diff --check` — whitespace clean.

## Auto Run Result

Status: done. Story 4.6 exposes the latest persisted, integrity-checked readiness report through a read-only API and a Russian `/readiness` page. The page displays bound revisions, all eleven checksummed frames and labels, literal measures, explicit failed/pending criteria, expected versus observed evidence, and links into retained campaign runs. Failed comparison runs with retained inputs still expose their source images; ordinary history and retry stay scoped to ordinary runs.

Files changed:
- `backend/app/adapters/postgres.py` — latest-report binding/readback, minimal frozen metadata, comparison-run read and verified artifact resolution.
- `backend/app/main.py` — no-store readiness and campaign-run HTTP read paths.
- `web/src/App.tsx`, `web/src/ReadinessPage.tsx`, `web/src/styles.css` — navigation, accessible readiness presentation, stale retry, and input-only evidence display.
- `backend/tests/test_comparison_campaign.py`, `backend/tests/test_startup.py`, `web/src/App.test.tsx` — persistent and HTTP contracts, integrity failure, rendered states, and evidence navigation.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — targeted Story 4.6 synchronization.

Review: pass 1 had 16 findings and led to one spec repair; the automatic approval review rejected the workflow's destructive reset twice, so the implementation was repaired in place. Pass 2 had 17 findings: six medium root-cause entries and two low entries were patched; four low and two false findings were rejected. The integrated rendered journey is deferred as an unverified risk, and a follow-up review is recommended because multiple medium fixes followed the second review.

Verification: the focused PostgreSQL/MinIO suite passed 102 tests on a fresh isolated database and bucket; the full backend suite passed 211 tests with one environment-dependent skip, then the skipped cloud-profile test passed separately with a checksum-verified held-out JPEG. All 85 web tests and the production TypeScript/Vite build passed. The canonical sprint validator and readback passed; only Story 4.6 changed status. `git diff --check` passed. No live cloud campaign, GUI application, or full-stack rendered browser journey was exercised.

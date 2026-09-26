---
title: Jury release
status: in-progress
route: dispatch
baseline_commit: 10eef28553db4260724c8c86152d7a30f8ddfb45
context: []
---

<frozen-after-approval>
## Intent
Implement the user's approved jury release plan, preserving historical analyses and commit 10eef28. Work in /private/tmp/lzt-jury-ready-release on feat/jury-ready-release. No GUI. The user authorizes commits, push, PR, independent review, merge and deployment, but release requires verified model acceptance and installed-service evidence. Never present machine suggestions as ground truth. Paid calls require upper-bound reservation within a total 1000 RUB budget; unknown cost means no call.

## Boundaries
Deliver eight construction stages with manually confirmed equipment templates; calendar and quick-stage modes; per-frame zone/time matching, parallel operations and stage transitions; exact persisted plan bindings; explainable warnings and conservative insufficient-data results; capability-aware API and UI; backward-compatible retries and historical evidence. Stages: preparation, demolition, excavation, concreting, installation, roadwork, utilities, landscaping. Preserve existing visual style and removed technical form card. No invented boxes/stage hypotheses. No model readiness without independent reviewed source/series-disjoint data.

## Acceptance
Given each stage and three assessable relevant frames, comparison reports missing expected equipment only when all relevant observations support non-detection. Given fewer than three, unknown classes or missing observations, report insufficiency. Given concurrent permitted machinery, do not report it as excluded. Given stage transitions, associate frames with their individual work windows. Given retries, retain exact immutable settings and do not duplicate signals. Given old runs, retain original contracts. Given a clean installation, CI verifies frontend, backend and migrations with real PostgreSQL/S3. Release/model/deployment acceptance stays incomplete until actual evidence exists.
</frozen-after-approval>

## Code Map
- backend/app/domain/site_analysis.py: pure comparator currently wrongly requires all timestamps to fit one work.
- backend/app/adapters/postgres.py: plan comparison in complete_ordinary, immutable persistence and retry lineage.
- backend/app/domain/rule.py: legacy excavation rule must remain compatible.
- backend/app/application/site.py and signals.py: catalog, immutable plan, stage confirmation.
- backend/app/application/submission.py: stage and payload validation.
- backend/app/main.py: analysis choices and runtime binding.
- web/src/App.tsx: plan editor, submission/recovery, results; styles in premium.css.
- infra/deploy: HTTP-only deployment; no verified new release target.
- evaluation/expansion: unreviewed candidates, no independent acceptance set.

## Execution
Implement sequentially, first backend stage catalog and corrected calendar comparison with regression tests, then frontend integration, CI/deployment protections and Russian release package. Do not execute paid experiments or release while the evidence gate is unresolved. Use existing runtime and tests. Record concrete blockers and verified results, never replace required quality checks with mocks.

## Tasks
- [x] Eight-stage catalog and templates, capability-aware choices and validation.
- [x] Per-frame calendar comparison and evidence, retry-stable signal identity; regression tests.
- [x] UI modes, confirmed expectations, searchable work selection and timeline.
- [ ] CI and migration/service checks; protected deployment and budget enforcement.
- [ ] Reviewed model acceptance, actual demo runs, Russian PDFs/package, release delivery.

## Implementation Notes
Approved user plan is the authorization source; no redundant approval checkpoint. Human reviewed labels and provenance are currently missing; user has been asked asynchronously. This is a release blocker, not permission to weaken gates.

## Review Triage Log

| Finding | Verdict and evidence | Resolution |
|---|---|---|
| Historical rule_results lacks supporting_input_ids | high: previous projections omit the field and UI called map | Optional field fallback and historical rendering regression |
| Alternative cranes simultaneously selected | high: default required both alternatives | Template selects mobile crane; user may replace manually |
| Neutral concurrent work suppresses exclusion | high: intersection silently drops explicit exclusions | Union of exclusions minus concurrent permissions |
| Empty/uncovered comparison silent | high: comparator returned empty results without evidence | Explicit insufficiency; partly uncovered frame fix in progress |
| Observation mode retains quick expectations | high: payload independent of selected mode | Mutually exclusive payload and confirmation regression |
| Stage confirmation pools series stages | high: later mismatched frames hidden | Per-frame mismatch IDs |
| Confirmation duplicates on independent rerun | medium: run ID in fingerprint | Content/plan/stage identity |
| Fourth unusable frame suppresses 3 usable frames | medium: all relevant frames required usable | Per-class suitable subset |
| Unsupported/unassessable excluded class | high: excluded class filtered by supported set silently | Add insufficiency and regression |
| Identical uploaded photo satisfies 3-frame threshold | high: distinct IDs do not prove distinct image evidence | Preserve inputs; count distinct hashes for new comparison |
| Timestamp spelling duplicates signals | medium: fingerprints hash raw timestamp strings | Normalize instants for identity |
| Dedup retains original signal rather than linking every new run | false: each run retains its own immutable projection and artifacts; existing signal intentionally stays attached to original evidence and is not reopened by reruns | Preserve explicit user dedup and historical provenance |
| Empty successful comparison hidden in UI | medium: length guard hides performed check | Show comparison-completed state and expectations |
| Cloud budget block advertised as available | high: actual transport blocked after request persisted | Early capability/submission gate |
| Mobile annotation zoom clamped | medium: max-width overrides selected width | Removed clamp; headless asserts 200% width |
| Annotation confirms unloaded image | high: image error does not guard confirmation | Loaded identity + naturalWidth gate, headless regression |
| Annotation tests absent in CI | medium: standalone UI uncovered by web suite | Added checksum build and headless job steps |
| Non-excavation initial navigation selects excavation rule | high: stale stage assumption creates invalid request | Derive intent from selected stage |
| Annotation allows >500 boxes but import rejects | medium: export cannot round-trip | Cap drawing/adoption and confirmation |
| Quick completion lacks DB test | medium: validator/pure tests miss persistence branch | Add actual PostgreSQL completion/readback |
| Equipment signal dedup lacks DB test | medium: manually inserted signals do not verify execution | Add equivalent/changed evidence completion tests |
| Quick confirmation lacks UI payload test | medium: renderer fixture does not exercise submission | Add user-driven confirmation/payload test |
| Repeated candidate creates duplicate box | medium: adoption appends repeatedly | Disable accepted candidates and test |
| Import overwrites scene-only/provenance-only draft | high: overwrite guard checks only equipment | Include all editable fields; dialog regression |
| Draft import permits invalid maps | high: editing imported strings throws after persistence | Validate keys/enums/maps before replacing progress |
| Invalid calendar date accepted | medium: Date.parse normalizes impossible date | Round-trip local calendar validation |

## Remaining release gates
Human labeling site requested and delivered under Desktop/lzt_plan/annotation-review. Owner will supply reviewed JSON. Independent grouping, full class coverage, extended model admission, monetary reservation ledger, remote CI configuration, trusted production TLS, restore-proven backup, merge and deployed-service acceptance remain incomplete. Paid transport is intentionally blocked pending monetary reservation implementation; do not merge as a working cloud release.

## Final local verification
Full backend: 278 passed including legacy real CPU admission; later history-only change verified separately. Frontend: 117 passed, production build successful. Annotation headless and real API/PG/S3 plan/UI checks passed. None of these proves expanded eight-class model quality or remote deployment.

Late history projection adjustment: 17 backend module tests passed after full278 run; final117 frontend tests/build passed. Functional commit: 64ee525d4bf953365b3d015e9ddaee33dacc40ac.

## Owner direction update: 2026-09-26

The owner explicitly authorized preliminary annotation of the organizer100 images through Qwen3.6 and chose Qwen3.6 as the target for all model analysis. Grounding DINO stays historical evidence, not the target release candidate. This authorizes upload of this source collection for this annotation run; machine proposals remain unreviewed. The current human review files and browser storage must remain intact. First execute a small real pilot, inspect quality/usage, then resume remaining images within the shared1000RUB budget. Prior expenditure must be supplied or verified before new paid calls. A standalone persistent reservation ledger reserves a conservative full-context bound for each request, settles only known usage, and retains uncertain charges. Production profile admission and runtime cutover remain separate implementation and verification steps; annotation success alone does not establish readiness.

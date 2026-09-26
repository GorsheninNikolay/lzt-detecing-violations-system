---
title: 'Project workspaces and a photo-first workflow'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '10eef28553db4260724c8c86152d7a30f8ddfb45'
context:
  - '_bmad-output/specs/spec-construction-monitoring-concepts/EXPANSION.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/DESIGN.md'
---

<frozen-after-approval reason="User explicitly requested implementation of the agreed plan">

## Intent

Implement the supplied project workspace plan: create project → upload photos → inspect results → optionally add a plan and compare. The shared project list has no registration or privacy boundary. Preserve the existing visual system and immutable evidence mechanisms.

## Boundaries & Constraints

Always use CLI/API/headless verification, never GUI. Preserve unrelated work and active branch. Keep legacy API calls and historical runs intact. Do not automatically attach orphan runs or evaluation runs to projects. No auth, project deletion, new models, algorithms, deployment, or remote publication. Russian UI; English repository documentation. Technical IDs, revisions, JSON and model/execution details belong in technical disclosures. Use “участок” in user-facing copy.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected behavior | Error handling |
|---|---|---|---|
| First visit | Empty shared project list | Create with name and browser timezone; atomic Main area; photo analysis without plan | Actionable error and retry |
| Isolation | Two projects and independent clients/tabs | URL project governs runs, plans, signals, counts; filtering precedes pagination/count | Unknown project has explicit error |
| Binding | Workspace trio with optional plan revision | Project, area, per-frame times immutable; validate ownership before publication and commit | Foreign area/revision rejected without images published |
| History | Legacy orphan or comparison evidence | Separate orphan archive; no reassignment; old run link resolves server ownership | Wrong project URL cannot misattribute run |
| Recovery | Lost submission response and reload | Same request/key and original project recover; retry preserves bindings | No duplicate submission or silent rebinding |
| Navigation | Slow response, dirty upload/plan, project switch | Cancel stale reads, clear data, confirm abandoning draft; tabs independent | Stay on original draft when declined |
| Plan | Added later or concurrent save | Old result unchanged; new analysis snapshots selected version | Revision conflict preserves draft |

</frozen-after-approval>

## Code Map

- `backend/app/application/site.py`: project/area/plan endpoints; create default area atomically, reuse version guards.
- `backend/app/application/submission.py`: validate_images currently couples four plan keys; separate workspace trio and optional revision; hash already includes context.
- `backend/app/adapters/postgres.py`: validate_plan_binding, commit_series_submission, read_run, list_ordinary. Validate workspace again in transaction, expose project/area without plan, filter ordinary history and count before pagination. Retry copies immutable context already.
- `backend/app/main.py`: GET /runs offset parsing; add project_id and unassigned filter with validation.
- `backend/migrations/versions/0015_detected_objects.py`: current head; add 0016 project history expression index on request_context project and ordering, ordinary partial predicate.
- `web/src/App.tsx`: routing, history, upload, pending recovery, plan editor and results. Preserve existing artifact, retry, and request-recovery guarantees. Existing requests support abort/generation guards; extend to all workspace reads.
- `web/src/AppHeader.tsx`, `SignalsPage.tsx`, `NewAnalysisPage.tsx`, `ReadinessPage.tsx`, `ProviderComparisonPage.tsx`: scope navigation/signals, simplify upload, rename report labels. Signals API already supports project filter.
- `web/src/styles.css`, `premium.css`, `result.css`: preserve Onest and plum visual system; responsive accessible project navigation.
- `backend/tests/test_site_workflow_db.py`, `test_site_analysis.py`, `test_single_image.py`, `web/src/App.test.tsx`, `SignalsPage.test.tsx`: extend meaningful coverage; use isolated TEST_DATABASE_URL only.
- `README.md`, `infra/compose.yaml`, existing headless scripts under `_bmad-output/implementation-artifacts`: local execution/verification patterns.

## Tasks & Acceptance

**Execution:**
- [x] Backend files above: atomic default area, independent workspace binding, filtered history/count, explicit read ownership and index; preserve old APIs and retries.
- [x] Frontend files above: `/` project list with creation/empty state and archive link; `/projects/{id}` overview, `/analyses`, `/new`, `/plan`, `/signals`, `/runs/{runId}`; persistent project name/switcher and upload action. Legacy run routes resolve actual workspace.
- [x] Overview: scoped latest analyses/open signals and real planned works, no fixed stage placeholders or global summary.
- [x] Upload: selected project, default Main area, optional additional areas, capture times, app-filled scenario, observation-only default; opt-in compare if plan exists; legacy excavation check explained as additional option.
- [x] Result: equipment, model hypothesis, attention/reason, plan stage and human confirmation clearly separate; capability gaps explained in relevant block. Reports only linked through About system, named Quality check and AI model comparison in Russian.
- [x] Navigation/recovery: stale read cancellation, dirty guard including browser navigation/unload, original workspace/key recovery, independent tabs.
- [x] Update canonical SPEC/EXPANSION, EXPERIENCE, DESIGN and existing architecture spine for the agreed scenario; preserve IDs and historical contracts.
- [x] Run backend isolated-DB integrations, frontend tests/build, desktop/mobile keyboard headless scenario and active-profile real pipeline smoke. Record actual evidence and limitations separately.

**Acceptance Criteria:**
- Given two clients and two projects, when each uploads and reads data, then histories, results, plans, signals and counts never mix.
- Given a project without a plan, when photos are submitted with a working admitted profile, then results open in that project; adding a later plan never rewrites the saved result.
- Given available browser tools, when verification runs, then it is headless and includes desktop/mobile and keyboard operation; automated UI success is never described as AI quality or deployment proof.

## Implementation Notes

The user's explicit instruction to implement the agreed plan authorizes proceeding through the spec checkpoint without asking again. No intent gaps. Migration is additive; apply only to isolated verification database unless separately authorized. No model/profile or live deployment mutation.

## Spec Change Log

## Review Triage Log

| Finding | Verdict | Evidence and disposition |
|---|---|---|
| Blind 1 demo cancellation | medium | Navigation increments generation; old finally skips clearing loading. Patch reset on leaving upload. |
| Blind 2 file validation crosses projects | high | addFiles checks only route new after await; A and B share that route. Patch upload generation fence. |
| Blind 3 create area drops plan | high | Creation changes zoneId without dirty confirmation. Patch existing area transition guard. |
| Blind 4 save readback crosses areas | high | loadPlan after PUT has no identity check; selector stays enabled. Patch disable/fence mutation and readback. |
| Blind 5 edit during initial plan load | high | Controls are active before asynchronous loadPlan replaces draft. Patch loading gate. |
| Blind 6 pending request shown in wrong workspace | high | pending is global; restoration of original project happens only at mount. Patch explicit recovery handoff on navigation. |
| Blind 7 late submission redirects | high | send invokes accepted navigation regardless of newer route/draft. Patch source navigation generation check. |
| Blind 8 declined Back destroys forward entries | medium | popstate pushes old URL, truncating forward history. Patch indexed traversal restoration. |
| Blind 9 failed plan reads lack retry | medium | Failure hides editor and its refresh control; only error text remains. Patch workspace reload action. |
| Blind 10 no-plan frame times hidden | medium | Capture times are rendered only inside plan binding. Patch independent saved frame time display. |
| Blind 11 keyboard path not exercised | medium | Headless only presses Tab once and uses click/selectOption thereafter. Patch actual keyboard navigation assertions. |
| Blind 12 saved planned works unprotected | medium | No original-revision-after-new-revision assertion. Patch backend and UI regression. Fresh live planned UI now passes planned-ui.json. |
| Edge 1 compare stays enabled on planless area | medium | Area effect clears plan but not opt-in; hidden checkbox leaves validation blocking. Patch reset compare when area changes. |
| Edge 2 create area drops plan | high | Same confirmed mutation as Blind 3. Patch shared transition guard. |
| Edge 3 delayed area readback | high | Same confirmed mutation/readback as Blind 4. Patch identity fence. |
| Edge 4 late submission navigation | high | Same confirmed unconditional accepted navigation as Blind 7. Patch navigation fence. |
| Edge 5 workspace fetch hangs | medium | siteRequest has no timeout; project/area/catalog/overview loading can remain indefinitely. Patch bounded GET timeout and actionable retry. |
| Gap 1 immutable planned works | medium | Reviewer verified missing backend/UI assertions for nonempty revision-bound planned_works. Patch coverage shared with Blind 12. |

### Focused repair review

- Edge repair 1: medium, confirmed. The unassigned recovery link passes `/new` through project scoping and cannot reach its original request; patch explicit unscoped handoff and regression.
- Edge repair 2: high, confirmed. Delayed IndexedDB recovery checks mounted only and redirects after newer navigation; patch navigation-generation fence and preserved-draft regression.
- Original findings were repaired with targeted passing regression checks. Parent final backend run passed 21 selected tests (the standalone CPU admission test was deselected because separate real-profile smoke and UI inference ran). Parent web run passed 122 tests and build before the two narrowly scoped recovery repairs.

## Verification

- Backend pytest using an isolated PostgreSQL test database and existing service test helpers; run matrix cases.
- `npm --prefix web test -- --run` and `npm --prefix web run build`.
- CLI headless Chromium verification at desktop/mobile sizes, including keyboard, navigation races and recovery.
- Read-only live configuration/profile check followed by a permitted input smoke if operational prerequisites permit; explicitly report blockers rather than fabricate admission/runtime evidence.

## Final verification outcome

All recorded review findings were corrected; no findings deferred. Parent verified the final recovery guards and passing regressions. Final checks: backend 21 passed / 1 standalone CPU test deselected, frontend 124 passed, production build passed, headless 28 passed. Four real admitted-profile CPU runs succeeded across API and headless UI flows. Saved planned works remained bound to the original revision after a newer empty plan. No deployment, remote publication, new model admission, or AI-quality claim.

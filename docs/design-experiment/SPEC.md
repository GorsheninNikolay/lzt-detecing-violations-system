---
title: Three independent construction-control designs
type: feature
created: 2026-09-28
status: done
route: dispatch
baseline_commit: 620f3e9e8a940f8fa475ab0576d7ec855ba1a1ac
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="User explicitly requested implementation of this approved plan">

## Intent

Build three runnable local variants of Контроль строительства with identical functionality and fixtures but distinct composition, visual systems and motion. Demonstration clarity is the comparison criterion; do not select a winner. Preserve Russian UI, logo, local Onest font, React/Vite/Radix, existing routes and backend contracts. Redesign the main journey: create project, upload photos, follow actual API stages, inspect results, manually review and open signals. Preserve plan, archive, help, training, feedback and admin behavior with shell-compatible styling.

## Boundaries & Constraints

Use CLI and headless Chromium only; never open or control GUI. Preserve main and its sole dirty file evaluation/hybrid/budget.json, and both pre-existing worktrees. All experimental files live under /private/tmp/lzt-design-experiment. The first worktree already exists at project-dashboard on design/project-dashboard at the baseline above. Create one shared technical commit there (fixtures, demo server, launch/testing infrastructure, motion dependency); branch design/photo-workspace and design/3d-experience into sibling worktrees from that commit BEFORE visual edits. No permanent foundation branch. Commit each final variant locally. No push, merge, deployment, cleanup or branch switching in the original workspace.

Directions:
- project-dashboard: light workbench, compact graphite side navigation, blue accent; overview prioritizes recent analyses, signals and upload. Adapt free MIT source/composition from https://github.com/creativetimofficial/material-dashboard-shadcn, retaining license and attribution. Brief panel/state transitions, one column and compact mobile navigation.
- photo-workspace: graphite photo-led workspace; large photo, bottom frame strip, findings and evidence at right. Minimal nesting; selected object links box and description. Mobile photo/strip first, switchable findings/evidence sections. Calm panel entrance.
- 3d-experience: dark plum, large typography, dimensional project covers. Adapt https://ui.aceternity.com/components/3d-marquee on project entry and https://ui.aceternity.com/components/container-scroll-animation in overview presentation, retaining applicable licenses/source links. Fine-pointer-only cover tilt, smaller decoration and no tilt on mobile. Working photographs and boxes NEVER sit in transformed/animated containers.

Reuse EvidenceViewer and AnnotationEditor including zoom, manual edits, drafts, undo/redo, idempotent retry, human confirmation and project attribution. Completion follows API truth without artificial animation waits. Add only motion as runtime animation dependency, imports from motion/react. Follow installed ui-ux-pro-max, impeccable, framer-motion, motion-react and ponytail skills. Directions and implementation are already authorized; do not request renewed design or spec approval. Treat user plan as overriding skill proposal/checkpoint defaults.

## I/O & Edge-Case Matrix

| Scenario | Input/state | Expected behavior | Errors |
|---|---|---|---|
| Demo | two projects, fixed dates, existing demo photos | same results, boxes and signals on all variants | explicit demonstration/quality disclaimer |
| Main journey | create, upload, analyze, review, signals | in-memory updates and project isolation | recoverable errors preserve inputs |
| State selection | empty, upload, analyzing, result, error, recovery | reproducible local controls and reset | unknown requests fail explicitly |
| Normal dev | API_PROXY_TARGET | existing backend proxy | no demo fallback |
| Production | build | demo middleware/panel excluded | no demo state exposed |
| Motion | OS reduced motion or user disable | decorative motion off; pause offscreen | static useful content |

</frozen-after-approval>

## Code Map

- web/src/App.tsx: current route/navigation, ProjectList, ProjectOverview, RunPipeline and ObservationResult; preserve request/polling/retry semantics.
- web/src/AppHeader.tsx, main.tsx, styles.css, premium.css: shell, Radix appearance, global styling.
- web/src/NewAnalysisPage.tsx: upload presentation, retain form in App.
- web/src/EvidenceViewer.tsx and Annotations.tsx: reuse image geometry and editor; retain tests.
- web/src/SignalsPage.tsx and signals.css: server summary, project scoping, evidence and human workflow.
- web/src/demoCases.json, web/public: existing photography.
- web/vite.config.ts, package.json: mode-specific middleware and scripts; normal proxy preserved.
- web/src/*.test.tsx: full existing Vitest suite, routing/project/editor/signal behavior.

## Tasks & Acceptance

- [x] Add shared fixtures and local Vite demo middleware supporting main-flow reads/writes, reset and states entirely in memory. Never forward any unknown demo API call to backend. Reuse fixtures in tests.
- [x] Add npm run dev:demo; normal dev retains API_PROXY_TARGET. Serve variants at 127.0.0.1:5174/5175/5176 with strictPort. Add persistent user motion preference and OS support.
- [x] Commit foundation and branch all variants before visual changes; implement three complete main flows and compatible secondary surfaces. Record source adaptation/licenses.
- [x] Add meaningful demo/interactions tests, retain all existing frontend tests, run full Vitest and production build in EACH worktree.
- [x] Add reproducible CLI headless verification and comparable screenshots: same main flow and empty/error/recovery states, 320/390/768/1440 widths, 200% text, long Russian names, keyboard/focus, overflow/overlap, text contrast and touch controls. Verify motion preference, offscreen pause, stable working photos. Check normal live API read connectivity separately, avoid unrequested real backend mutations; clearly state fixture-only operations.
- [x] Save commands, full commit IDs, test results, screenshots and comparison report with limitations and recommendations for specific navigation/overview/photo/presentation elements. Leave servers running simultaneously if feasible.

Acceptance: Given any variant, when the same fixture flow runs, then project ownership, results and signals agree. Given demo mode, when an unknown API request is made, then an explicit failure occurs without forwarding. Given normal mode or production, when loaded, then demo controls are absent. Given narrow width or doubled text, when navigating and reviewing, then actions remain reachable and the page does not overflow. Given reduced/disabled motion, then all decoration stops and work remains usable.

## Implementation Notes

No intent gaps or irreversible actions. Footprint is frontend-only plus local documentation/tests. Source baseline was checked live. Main dirty work is excluded. Impeccable context launcher failed with permission denied; read PRODUCT.md and existing design context directly as fallback. Keep the specified directions rather than running another concept selection. UI text Russian; engineering docs English.

## Spec Change Log

## Review Triage Log

All three code-review layers returned before classification. Duplicate findings retain individual verdicts below and share bounded repairs; no public API, backend schema, deployment or main-worktree action is added.

| Finding | Verdict | Evidence and disposition |
|---|---|---|
| BH1 saved-plan/signal identities | medium | Demo submission accepts arbitrary revisions and keeps fixture work identities. Patch: resolve the selected zone's saved revision and derive immutable run/signal evidence from it; reject absent/cross-zone revisions. |
| BH2 submitted stage | medium | server.ts merges context.stage_id but keeps top-level stage=excavation. Patch: persist the submitted context consistently. Fixed photo-derived hypotheses may remain explicitly illustrative rather than being relabeled as an observed requested stage. |
| BH3 oldest-first runs | medium | Object.values(runs) uses insertion order and overview slices its first five entries. Patch: newest insertion first, deterministic for fixed timestamps. |
| BH4 annotation route substring | medium | tail.includes(input_id) accepts a wrong frame segment containing the real identifier. Patch: capture and compare the complete route segment, with a negative regression test. |
| BH5 hidden selected object on mobile | medium | Photo SourceImage only changes selectedObject while evidence mode hides object-list. Patch: selecting a box also selects findings; verify evidence-to-box interaction. |
| BH6 OS override versus hidden preference | medium | Effective enabled is false under OS reduction, but the control still toggles allowed. Patch: explain system override and disable unavailable toggles while preserving the saved choice. |
| BH7 target-size coverage | medium | Audit checks height only and omits field/checkbox/navigation target dimensions. Patch the existing audit to measure width and height, use checkbox label hit targets, and explicitly report intentional inline-link/geometry exceptions. |
| BH8 marquee intent-only assertion | medium | data-moving is computed independently of actual rendered Motion transforms. Same repair as VG2: sample real transforms over time. |
| BH9 onboarding/menu enlarged-text coverage | medium | Harness always skips onboarding and captures the shell menu closed. Targeted first-use and open-menu checks at enlarged text and a short viewport are required for changed shell compatibility. Fix only reproduced defects. |
| BH10 harness portability/documented override | low | Harness intentionally uses the user-requested fixed experiment root/ports. The stale DEMO_URL instruction was already corrected in later docs commits to VARIANTS and fixed ports. Reject additional root configurability as unnecessary for this bounded local experiment. |
| EC1 plan-derived signal identities | medium | Independently reproduced same defect as BH1; shared repair retains original revision after later plan edits. |
| EC2 light annotation number contrast | medium | annotations.css uses background:var(--raised) with color:#fff. Dashboard raised surface is light. Patch foreground token and verify actual label contrast in editor. |
| EC3 recent analysis ordering | medium | Same insertion-order issue as BH3; shared ordering repair. |
| VG1 client preset reset untested | medium | Verified gap: all existing reset checks call the API directly. Add an actual panel-button journey with retained upload, annotation and IndexedDB state; verify cleanup, navigation, no old upload restoration, and unrelated preferences retained. |
| VG2 actual animation pause untested | medium | Verified gap: no transform sampling exists. Strengthen existing marquee check for visible movement and offscreen/user-disabled stability. |

Visual review separately found mobile navigation sibling overlap at doubled text. It was corrected using flexible normal-flow navigation and scored resolved by the same reviewer in finish-verdict.md. Mobile screenshots were refreshed. One broad photo redo timeout is retained with an unchanged-code successful narrow rerun; no cause is inferred.


## Verification

Run npm run build and npm test -- --run per worktree. Record exact results. Use headless Playwright/Chromium via CLI, not browser GUI tools. Perform one batched visual inspection and one confirming pass after fixes. Do not claim physical device or GUI checks. Read-only live API checks are separate from deterministic demo tests. No backend source/schema/migration changes.

Implementation submitted for independent review. See COMPARISON.md and the external experiment evidence directory for checked state, preserved failures and limitations.

## Final acceptance

All accepted review findings were repaired and verified; the requested fixed-path harness remains intentionally local. Immutable plan/signal provenance, exact frame identity, newest-first history, stage context and motion override have regression coverage. Photo box selection exposes its description. Focused browser evidence records 29 passing review scenarios, real preset cleanup, actual animation transforms, label contrast, expanded menus and 11 reachable rail actions at 1440x560/200% text. The independent visual reviewer scored navigation, menu/label and rail fixes resolved.

Root final verification: **221 tests passed**, production build passed, checked code revision `a3bed3e7ce87a8281e5e26fbde089d6b136fc861`. See [final verification](../../../root-final-verification.json), [comparison](../../../COMPARISON.md), [targeted UI evidence](../../../evidence/review-fixes/report.json) and [rail verdict](../../../evidence/finish-rail-verdict.md). The only later changes are design/spec documentation. Production demo exclusion is checked separately. No real backend writes, GUI or physical-device verification are claimed.

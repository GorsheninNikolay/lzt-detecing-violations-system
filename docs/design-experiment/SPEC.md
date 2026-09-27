---
title: Three independent construction-control designs
type: feature
created: 2026-09-28
status: in-progress
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

- [ ] Add shared fixtures and local Vite demo middleware supporting main-flow reads/writes, reset and states entirely in memory. Never forward any unknown demo API call to backend. Reuse fixtures in tests.
- [ ] Add npm run dev:demo; normal dev retains API_PROXY_TARGET. Serve variants at 127.0.0.1:5174/5175/5176 with strictPort. Add persistent user motion preference and OS support.
- [ ] Commit foundation and branch all variants before visual changes; implement three complete main flows and compatible secondary surfaces. Record source adaptation/licenses.
- [ ] Add meaningful demo/interactions tests, retain all existing frontend tests, run full Vitest and production build in EACH worktree.
- [ ] Add reproducible CLI headless verification and comparable screenshots: same main flow and empty/error/recovery states, 320/390/768/1440 widths, 200% text, long Russian names, keyboard/focus, overflow/overlap, text contrast and touch controls. Verify motion preference, offscreen pause, stable working photos. Check normal live API read connectivity separately, avoid unrequested real backend mutations; clearly state fixture-only operations.
- [ ] Save commands, full commit IDs, test results, screenshots and comparison report with limitations and recommendations for specific navigation/overview/photo/presentation elements. Leave servers running simultaneously if feasible.

Acceptance: Given any variant, when the same fixture flow runs, then project ownership, results and signals agree. Given demo mode, when an unknown API request is made, then an explicit failure occurs without forwarding. Given normal mode or production, when loaded, then demo controls are absent. Given narrow width or doubled text, when navigating and reviewing, then actions remain reachable and the page does not overflow. Given reduced/disabled motion, then all decoration stops and work remains usable.

## Implementation Notes

No intent gaps or irreversible actions. Footprint is frontend-only plus local documentation/tests. Source baseline was checked live. Main dirty work is excluded. Impeccable context launcher failed with permission denied; read PRODUCT.md and existing design context directly as fallback. Keep the specified directions rather than running another concept selection. UI text Russian; engineering docs English.

## Spec Change Log

## Review Triage Log

## Verification

Run npm run build and npm test -- --run per worktree. Record exact results. Use headless Playwright/Chromium via CLI, not browser GUI tools. Perform one batched visual inspection and one confirming pass after fixes. Do not claim physical device or GUI checks. Read-only live API checks are separate from deterministic demo tests. No backend source/schema/migration changes.

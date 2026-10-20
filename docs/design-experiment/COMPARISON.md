> Исторический материал эксперимента с интерфейсом. Результаты относятся к указанным здесь версиям и условиям, а не к текущему стенду. Команды `node scripts/*.mjs` используют локальные инструменты из `web/scripts`, которые больше не поставляются с репозиторием. Для текущих проверок интерфейса используйте `npm test -- --run` и `npm run build` из `web`.

# Three local construction-control variants

No overall winner is selected. The variants share one deterministic demo service and the original project, upload, polling, evidence, annotation, plan and signal flows. Comparison focuses on demonstration clarity.

| Variant | Local URL | Composition | Elements worth evaluating |
|---|---|---|---|
| Project dashboard | http://127.0.0.1:5174 | Light workbench, graphite rail, blue action; recent analyses beside attention and plan | Persistent desktop navigation helps repeated section switching. The overview keeps upload, latest analysis and signals visible together. Mobile becomes one column with wrapped labeled navigation in normal document flow. |
| Photo workspace | http://127.0.0.1:5175 | Graphite photographic surface; large source image, lower strip, findings and disclosed evidence on the right | Prioritize the large photo and direct box/list selection for review-heavy work. Mobile puts the photo/strip first and switches findings/evidence. The flat treatment avoids nested cards. |
| 3D experience | http://127.0.0.1:5176 | Dark plum, larger type, architectural covers, Aceternity-adapted marquee and overview presentation | The entry and overview illustrations provide a presentation-oriented introduction. They consume more vertical space on phones. Motion is restricted to decoration; working photos and boxes stay fixed. |

Recommendations concern individual elements, not a selected design: compare the dashboard rail for frequent navigation, its recent-analysis/attention grouping for overview tasks, the photo workspace for detailed evidence review, and the 3D cover/presentation treatment for an introduction to a project. Preserve a static path and user control for all motion.

## Reproduction

All files are under `/private/tmp/lzt-design-experiment`. Existing main, its dirty evaluation file, existing worktrees, and listeners 8000/5173 are outside this experiment. Nothing was pushed, merged or deployed.

The foundation is `6f031e7c2ea3097ca6d055bd77fae571e60b38af`. The sibling branches were created from that commit before visual edits. Full final commit IDs are recorded in `commits.json` beside this report, after the local variant commits were created. There is no permanent foundation branch.

In each variant's `web` directory:

```sh
npm run dev:demo
npm test -- --run
npm run build
```

`dev:demo` binds 127.0.0.1 with strict ports 5174, 5175 and 5176. Servers were left running. Dependencies are installed in project-dashboard/web/node_modules; the sibling node_modules entries are ignored local symlinks. To reproduce elsewhere, install each branch's lockfile in a separate working directory with `npm ci`.

Headless comparison tooling is outside application dependencies, in `tooling/node_modules/playwright-core`. The CLI scripts accept CHROMIUM_PATH and PLAYWRIGHT_PACKAGE. The default browser is the existing headless Chromium 1243 installation:

```sh
node scripts/verify-demo.mjs
node scripts/verify-interactions.mjs
node scripts/verify-photo-editor.mjs
node scripts/verify-nav.mjs
```

`verify-demo` defaults to writing `evidence/initial`; use `VISUAL_PASS=confirmation` for the confirming round. VARIANTS optionally limits named variants. It returns a nonzero exit status for failed interactions, document overflow, text contrast findings or undersized main controls. Wide descendants are retained for triage because local scroll strips and decorative clipping legitimately extend beyond their own viewports.

## Verified evidence

- Final complete Vitest and production-build outputs: `*-tests.log`, `*-build.log`, `build-test-results.json`. At the initial implementation checkpoint each variant had 13 passing test files and 218 passing tests; subsequent review repairs have focused verification below, with full revalidation owned by the root reviewer. Tests include demo isolation/idempotency/recovery, successful retry projection integrity, and motion preference persistence/OS reduction.
- `evidence/confirmation/report.json`: 146 broad-pass screenshots plus the narrowly completed photo editor capture (147 total); 320/390/768/1440 CSS-pixel widths; projects, overview, upload, results, signals, plan, empty, analyzing, error and recovery presets. Results, upload and signals also use actual 200% rendered text at 390 and 1440. Each element's computed font size is captured first and doubled, including legacy pixel rules; this is text enlargement, not browser zoom.
- Confirmation layout measurements: zero document overflow, zero nonempty-text contrast violations among the tested headings/paragraphs/labels/buttons/summaries/links, zero undersized controls within that original audit, which measured height for buttons/selects/summaries but did not measure both dimensions or field/checkbox-label targets. This is not full touch-target coverage. Wide descendants are clipped frame-strip content or decorative marquee content. Box resize handles preserve the existing 24px geometry controls and were excluded from the main 44px control audit; keyboard/numeric alternatives remain available.
- Independent finish review found sibling-label overlap in the fixed mobile navigation at actual doubled text; document-overflow checks had missed it. The smallest fix makes mobile navigation wrap into flexible columns in normal document flow. `evidence/navigation-text200-checks.json` measures sibling text rectangles, control sizes, text containment and visible/reachable keyboard focus at 390px/200% for all variants. All affected 320px/390px comparison captures, mobile 200% text, editors, long project names and pending recovery states were refreshed after the fix; `evidence/confirmation/mobile-refresh.json` lists the targeted captures. The original broad-pass measurement report is preserved as `original-report-before-mobile-refresh.json`.
- Main journey checks cover project creation (including a long Russian name), upload, server stage progression, project ownership, retained-input retry after a 503, linked box/object selection, evidence dialog Escape/focus restoration, manual annotation submission and human stage confirmation, signal workflow update, OS reduced motion and persistent user disable.
- One broad-pass photo-editor redo click timed out while scrolling. The original failure is preserved in confirmation/report.json. An unchanged-code isolated rerun passed add, undo, redo, submission and stage confirmation: `evidence/photo-editor-check.json`, with the missing screenshot captured as `evidence/confirmation/photo-workspace-editor-390.png`. No cause is asserted from timing alone.
- `evidence/interaction-checks.json`: 13 additional passing checks. Failed analysis retry reaches readable completed frames; toggling motion leaves exact image/box rectangles unchanged; OS preference changes apply without reload; each variant traverses 12 Tab stops with visible focus; 3D marquee is proven moving in view and stopped offscreen. Keyboard coverage is these paths plus existing tests, not a full screen-reader audit.
- `normal-mode-verification.json` independently checks every variant's actual normal-mode proxy: read-only health/live, health/ready, projects and analysis-choices all return HTTP 200, 9 live project cards render, no demo panel or uncaught page errors. Browser non-GET requests were blocked to avoid real telemetry and other mutations. Root-owned temporary verification servers were stopped.
- `live-api-verification.json` records the separate existing 8000/5173 backend read checks. A production bundle scan confirms demo fixture/project/state-control strings are absent. These checks do not demonstrate deployment or model quality.

The initial and confirming screenshot rounds are retained. Final code-only retry/checksum corrections are covered by unit and supplemental functional checks; they do not change the photographed layout. Desktop and mobile screenshots were visually inspected in one batched initial round and one confirming round. No GUI application was opened or controlled.

## Limits and retained behavior

Demo photographs and manually prepared boxes are illustrative; there is no model call and no quality acceptance claim. The fixed 2026 analysis/capture metadata is illustrative and differs from 2024 dates printed in the source photographs. Project covers are decorative drawings, or explicitly demo-only photo covers. Actual uploads are held only in memory on their variant's local server; unknown demo endpoints fail explicitly and never proxy.

The existing EvidenceViewer/AnnotationEditor implementation retains geometry, zoom, draft persistence, undo/redo, idempotent retry and original-versus-proposed separation. Plan, archive, help, feedback, training and admin code remains in place with shared theme tokens. The main-flow demo API is implemented; unsupported auxiliary/demo admin operations fail explicitly. Live admin authentication, physical-device touch/pinch, camera permission/capture, screen readers, model execution and real backend writes were not exercised.

Production builds retain existing large CSS and, for motion-heavy variants, a Vite chunk-size warning. The warning is recorded in the build logs and is not an assertion of measured performance. The experiment is local and ephemeral under /private/tmp; preserve it elsewhere before operating-system cleanup if needed.

Creative Tim MIT attribution and the applicable Aceternity licence/source links are in each relevant branch's `docs/design-experiment/SOURCES.md` and `licenses` directory. Aceternity is not described as MIT. No external publication is authorized or performed.

## Code-review repair verification

`evidence/review-fixes/report.json` contains 29 passing focused headless checks. The target audit now records width and height for controls, input/select/textarea fields, effective checkbox/radio/file label targets and navigation. Inline heading/prose links and existing geometry controls are explicitly enumerated exceptions, not silently counted as compliant. The target audit also feeds future verify-demo runs.

Immutable plan snapshots now govern run works and missing-equipment signals; unknown and cross-zone revisions fail. Saved stage context, newest-first history and exact annotation frame identity have focused regression tests. Photo box selection restores visible findings. OS motion override is explained and disables unavailable controls while retaining the user's choice. Actual annotation-number contrast is measured, including the light dashboard.

The 200% short-viewport overlay probe found overlapping motion/menu controls. Moving the motion button into the menu's stacked layout fixed the observed issue. First-use onboarding passed without a layout change. The focused report includes reachable menu links at 390/1440 widths and 560px height.

Marquee verification samples actual computed transforms over time while active, offscreen and disabled. Demo reset is exercised through its actual preset button after a retained failed upload, annotation draft and IndexedDB-backed request; cleanup, destination, absence of old recovery and preservation of unrelated preferences are asserted. Source/editor metadata fixes do not claim model quality.

---
title: 'Verify Rendered UI Acceptance for Epic 1 (F6)'
type: 'chore'
created: '2026-09-24'
baseline_revision: '9676a0877c6d453e85a23426866265305f79942e'
status: 'done'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** F6 remains open because jsdom tests substitute dialog behavior and image responses; they do not establish rendered layout at narrow width or scale, native dialog focus, or browser decoding of the source JPEG.

**Approach:** Verify the existing app in headless Chromium with the real browser renderer, a completed-run API fixture, and an actual bundled JPEG returned as image bytes. Save a compact report and screenshots, and fix only reproducible acceptance defects found in these checks.

## Boundaries & Constraints

**Always:** Use CLI-driven headless Chromium only; no GUI application. Check a 320 CSS-pixel viewport and a 2× device-scale rendering at 640 CSS pixels (equivalent rendered size to 200% zoom on a 1280-pixel viewport); report the exact emulation. Serve the actual `web/public/demo/Screenshot_23.jpg` bytes through the artifact request and verify the rendered image decodes. Preserve the existing API and interaction contracts.

**Never:** Claim the backend, model accuracy, production, or browser-toolbar settings were verified by the local API fixture. Add a browser-test dependency or change UI behavior without a reproduced defect. Change any unrelated Epic 1 action item.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Phone layout | Headless app at 320 CSS pixels | Main content fits without horizontal overflow; labels, navigation, and primary controls remain visible | Fail with measured widths and screenshot path |
| 200% rendered-size equivalent | 640 CSS-pixel viewport at deviceScaleFactor 2, with text-spacing overrides | Layout remains readable without clipped content; visible interactive targets remain at least 44 CSS pixels | Fail with measured bounds and screenshot path |
| Source image | Completed run fixture and bundled JPEG artifact bytes | Artifact request returns JPEG; browser image decodes with matching intrinsic dimensions | Show the app's specific unavailable/integrity message on failure |
| Evidence dialog | Keyboard-focused source-image opener | Native modal opens with focus inside, traps Tab navigation, and Escape restores focus to its opener | Fail with active element, dialog state, and screenshot |

</intent-contract>

## Code Map

- `web/src/App.tsx:29-57` -- `artifactUrl`, `useArtifact`, and `SourceImage` fetch an artifact, create a blob URL, and render the decoded image.
- `web/src/App.tsx:87-131,134-217` -- `EvidenceViewer` uses native `dialog.showModal()`; `ObservationResult` stores the opener and restores its focus on close.
- `web/src/App.tsx:462-517,807-818` -- direct `/runs/{id}` navigation fetches the run snapshot and renders the app shell.
- `web/src/styles.css:1-4,11-13` -- base sizing, 320-pixel minimum, responsive breakpoints, and full-screen phone dialog.
- `web/vite.config.ts` and `web/README.md` -- local Vite history fallback and `/api` development proxy.
- `web/public/demo/Screenshot_23.jpg` -- real bundled JPEG used for the artifact response.
- `web/src/App.test.tsx:14-55,75-100` -- existing jsdom fixture stubs `showModal`, object URLs, and non-JPEG image blobs; it cannot serve as rendered-browser evidence.
- `_bmad-output/planning-artifacts/epics.md:556-559,602-605` -- responsive, zoom, and source-artifact acceptance contract.
- `_bmad-output/implementation-artifacts/spec-1-5-submit-an-observation-in-the-responsive-web-app.md:11-18` and `_bmad-output/implementation-artifacts/spec-1-7-inspect-the-source-bound-observation-result.md` -- prior responsive deferral and source-viewer contract.
- `_bmad-output/implementation-artifacts/epic-1-retro-2026-09-23.md:39-42` and `_bmad-output/implementation-artifacts/sprint-status.yaml:87-94` -- F6 finding and the only sprint action this verification may close.
- `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/` -- save the CLI verification report and screenshots here.

## Tasks & Acceptance

**Execution:**
- [x] `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/verify-f6-rendered-ui.mjs` -- run headless Chromium against the Vite app with a minimal completed-run fixture and a real JPEG artifact response -- exercise actual layout, native dialog, and image decoding without a GUI.
- [x] `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/` -- save viewport/scale/focus/image measurements and screenshots -- retain reviewable F6 evidence.
- [x] `_bmad-output/implementation-artifacts/spec-1-5-submit-an-observation-in-the-responsive-web-app.md` -- clear only the rendered responsive deferral after its stated conditions were measured -- keep the prior verification record accurate.
- [x] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark only `epic-1-retro-verify-rendered-ui` done after every matrix row passed -- synchronize F6 evidence.
- [x] `_bmad-output/implementation-artifacts/spec-f6-verify-rendered-ui.md` -- record the browser setup, evidence paths, triage, and limitations.

**Acceptance Criteria:**
- Given the app opens at 320 CSS pixels, when its primary form and navigation render, then the report records `innerWidth`, document width, visible key controls, and no horizontal overflow.
- Given the app renders at 640 CSS pixels with deviceScaleFactor 2, when text-spacing overrides are applied, then the report records the equivalent 200% rendered scale, no clipping, and 44-pixel minimum visible targets.
- Given a completed-run fixture, when the browser requests its source artifact, then the actual JPEG response is decoded by the `<img>` element and its intrinsic dimensions match the bundled file.
- Given keyboard activation of `Открыть кадр 1`, when the evidence dialog opens and closes, then focus enters and stays within the native modal, Escape closes it, and focus returns to the opener.
- Given all checks pass, when evidence is recorded, then only F6 is marked done; the report distinguishes local fixture evidence from production/API and model verification.

## Spec Change Log

### 2026-09-24 — Rendered-browser findings
- The first headless run reproduced a Tab-boundary focus escape: Chromium moved `document.activeElement` to `BODY` after the last dialog toolbar button while the modal remained open.
- Added a boundary-only focus wrap in the native dialog; the focusable set includes `summary` so any technical disclosure remains in the keyboard sequence.
- Adding native evidence details to the fixture exposed a 24px `<summary>` target. The CSS now provides a 44px target, and the script also checks 320px text spacing, target sizes, and summary focus.
- The final headless run passed all 26 checks, including separate 320px label bounds, clipping checks at 320px and 640px, viewport bounds for scoped targets, bidirectional focus wrapping, and touch emulation.

## Review Triage Log

### 2026-09-24 — F6 rendered acceptance
- verdicts: one confirmed focus defect patched; no other rendered acceptance defects reproduced.
- focus: source-opener Enter activation enters the native modal; forward and reverse Tab remain within it; Escape closes and restores opener focus.
- source: the browser decoded the exact 272405-byte bundled JPEG response as 1215 x 811; integrity and unavailable responses render their distinct app messages.

### 2026-09-24 — Review pass
- verdicts: 17 findings — high 0, medium 4, low 10, false 3, maybe-false 0
- findings:
  - `[low]` `[patch]` The 320px record omitted associated field labels from its visibility and width checks — separate measurements now cover the scenario, area, period, and image-picker labels.
  - `[false]` `[reject]` Five phone controls are below the initial 900px viewport — the report records those positions and the full-page screenshot; ordinary vertical scrolling keeps them available, and F6 does not require the entire form to fit above the fold.
  - `[low]` `[patch]` The 320px text-spacing run did not check clipping — the headless run now checks it and reports no clipped content.
  - `[low]` `[patch]` The 640px form's no-clipping claim was not checked — the form clipping result is now measured, asserted, and recorded as empty.
  - `[low]` `[reject]` The clipping helper does not detect every hypothetical ellipsis or line-clamp mechanism — the current app styles use wrapping and no text-overflow or line-clamp rule, so that unimplemented detector has no reachable case in this rendered surface.
  - `[low]` `[patch]` The 640px target check omitted horizontal bounds — form and result targets now assert left/right bounds against the CSS viewport.
  - `[low]` `[patch]` The shared target measurement queried the whole document, contaminating modal measurements with background controls — the dialog and other measurement surfaces are now scoped; this shares a root cause with the form-target false-pass finding below.
  - `[low]` `[patch]` The dialog traversal assertion did not require the modal to remain open at each step — forward and reverse checks now assert both `open` and focus containment; this shares a root cause with the reverse-boundary finding below.
  - `[medium]` `[patch]` Clearing Story 1.5's touch deferral from target dimensions alone left touch activation unobserved — a 320px `hasTouch` tap now emits `pointerType: touch` and focuses the scenario field; evidence is labeled as emulation, not physical-device verification.
  - `[low]` `[patch]` The completed sprint action still read as a future request and retained a stale GUI restriction — its F6 entry now reports completed headless local-fixture evidence and the verification limits.
  - `[medium]` `[patch]` Fixed-port readiness could accept an unrelated server response before Vite startup — readiness now requires the launched Vite child to announce the exact configured URL; this shares a root cause with the duplicate startup finding below.
  - `[low]` `[reject]` `sips` is not listed as a portable prerequisite — the documented invocation already pins the macOS Chrome executable and this run is for that macOS environment; cross-platform verifier support is outside the F6 intent.
  - `[false]` `[reject]` Positive `tabindex` values could reorder modal endpoints and `tabindex=-1` buttons could remain tabbable — positive values are sorted before stable DOM-ordered zero values, while negative values are excluded as sequentially unfocusable; current dialog markup has no positive tab indices.
  - `[medium]` `[patch]` The verifier could pass against a service already occupying port 4179 — requiring Vite's own exact URL announcement and successful response prevents that false pass; this shares the startup root cause above.
  - `[low]` `[patch]` Navigation links alone could satisfy the 640px form target check — form, run workspace, and dialog measurements are now scoped, and the form check requires at least one measured target; this shares the measurement root cause with the modal-scope finding above.
  - `[medium]` `[patch]` Reverse Shift+Tab from the first dialog control lacked a boundary assertion — the test now verifies wrap to the last control and back while the dialog stays open; this shares the modal-traversal root cause with the open-state finding above.
  - `[false]` `[reject]` A broader interpretation might require a new feature or live browser/backend flow — the baseline sprint item identified by F6 specifically asks for rendered-browser evidence, and this change covers that action while preserving the live-backend limitation.

## Verification

**Commands:**
- `TMPDIR=/private/tmp PLAYWRIGHT_MODULE=/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright CHROME_PATH='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' node _bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/verify-f6-rendered-ui.mjs` -- passed 26/26 checks; writes [report](epic-1-retro-evidence-2026-09-24/report.md), [measurements](epic-1-retro-evidence-2026-09-24/report.json), and screenshots.
- `cd web && npm test -- --run` -- 52 passed.
- `cd web && npm run build` -- passed TypeScript and Vite production build.
- `git diff --check` -- passed with no whitespace errors.

## Browser Verification Record

Headless Playwright with Chrome 153.0.8010.53 served the existing Vite app at localhost and intercepted API reads with one completed-run fixture. No GUI application was opened. The app loaded directly at `/runs/12345678-1234-1234-1234-123456789abc`.

- Phone: 320 x 900 CSS pixels, device scale 1, browser zoom unchanged. `innerWidth`, document width, and body width were 320 CSS pixels. Scenario, area, period, and image-picker labels and key controls fit the viewport width; the 320-pixel text-spacing layout had no clipped content. Form targets were scoped to the form and measured separately from the associated labels.
- Touch input: Playwright `hasTouch` emulation tapped the scenario field, observed a `pointerType: touch` event, and confirmed focus moved to the field. This is emulated input, not physical-device verification.
- 200% rendered-size equivalent: 640 x 900 CSS pixels, device scale 2 (1280 rendered screenshot pixels). Text spacing was overridden to 0.12em letter spacing, 0.16em word spacing, 1.5 line height, and 2em paragraph spacing. The form and result had no horizontal overflow or clipped content; measured targets were at least 44 x 44 CSS pixels and stayed inside the viewport bounds.
- Source: the fixture returned the exact 272405-byte `web/public/demo/Screenshot_23.jpg` payload as `image/jpeg`; SHA-256 `2dadb850e7a78cca8691763df50d1096d441b7837b1334a26e95d612123aaf9a`; browser `naturalWidth`/`naturalHeight` 1215 x 811 matched the bundled image.
- Dialog: Enter on the keyboard-focused `Открыть кадр 1` opened the native modal with focus inside; forward and reverse boundary traversal kept focus inside while the dialog remained open and reached the native technical-evidence disclosure; Escape closed it and restored focus to the opener. The disclosure target measures 44 CSS pixels high.
- Failure handling: fixture 409 integrity and 503 unavailable responses produced `Целостность артефакта не подтверждена` and `Не удалось открыть исходное изображение` respectively.

Evidence: 26/26 browser assertions passed. See [report](epic-1-retro-evidence-2026-09-24/report.md), [JSON measurements](epic-1-retro-evidence-2026-09-24/report.json), [320 CSS-pixel screenshot](epic-1-retro-evidence-2026-09-24/f6-phone-320-css.png), [640 CSS-pixel / 2x form screenshot](epic-1-retro-evidence-2026-09-24/f6-200-equivalent-form-640-css-dsf2.png), [640 CSS-pixel / 2x result screenshot](epic-1-retro-evidence-2026-09-24/f6-200-equivalent-completed-run-640-css-dsf2.png), [native dialog screenshot](epic-1-retro-evidence-2026-09-24/f6-native-evidence-dialog-640-css-dsf2.png).

Limitations: this local API fixture verifies browser rendering and image decoding only. It does not verify a live backend, model accuracy, production, browser-toolbar zoom settings, physical-device touch behavior, or low-memory behavior with eight full-size images.

## Auto Run Result

F6 is complete. Headless Chromium verified the responsive UI, text spacing, touch-emulated field activation, native dialog focus boundaries, error messages, and decoding of the bundled JPEG bytes through a local API fixture. It fixed the reproduced keyboard focus escape and made the disclosure target 44 CSS pixels high.

Files changed:
- `web/src/App.tsx` — wraps keyboard focus at both boundaries of the evidence dialog.
- `web/src/styles.css` — gives the native technical-evidence disclosure a 44px target.
- `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/verify-f6-rendered-ui.mjs` — runs scoped headless rendering, clipping, touch, image, and focus checks against a local fixture.
- `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/report.md` and `report.json` — record the 26 passing checks and their measurements.
- `_bmad-output/implementation-artifacts/epic-1-retro-evidence-2026-09-24/*.png` — retain the four rendered screenshots.
- `_bmad-output/implementation-artifacts/spec-1-5-submit-an-observation-in-the-responsive-web-app.md` — records the later browser evidence and the limits of emulated touch.
- `_bmad-output/implementation-artifacts/spec-1-7-inspect-the-source-bound-observation-result.md` — retains live backend integration and maximum-series memory as separate deferred items.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — marks only the rendered-UI action done with its local-fixture scope.
- `_bmad-output/implementation-artifacts/spec-f6-verify-rendered-ui.md` — records the F6 contract, evidence, triage, verification, and residual risks.

Review findings: 9 patch entries covering 12 findings (3 medium and 6 low entries); none deferred. Five findings were rejected: three false claims were refuted by the tracked F6 scope, focus ordering, and reachable UI behavior; two low findings concerned hypothetical line-clamp detection and cross-platform support that this macOS-only invocation does not promise. The full reasons are recorded above.

Follow-up review recommended: **true**. This first pass patched three medium entries: origin-bound Vite readiness, modal keyboard-traversal assertions, and touch-emulated activation. The remaining unverified risks are live backend integration, browser-toolbar zoom, production behavior, and physical-device touch.

Verification:
- Headless Playwright and Chrome 153.0.8010.53 — 26/26 checks passed against a completed-run local fixture; no GUI application was opened.
- `cd web && npm test -- --run` — 52 tests passed.
- `cd web && npm run build` — TypeScript and Vite production build passed.
- `git diff --check` — passed before final workflow metadata was appended; rerun after this edit.

Residual risks: the local fixture does not prove a live backend artifact route, model accuracy, or production behavior. Device-scale rendering is a 200% equivalent, not browser-toolbar zoom. Touch was emulated in Playwright rather than verified on physical hardware. Story 1.7's eight-image low-memory behavior remains deferred.

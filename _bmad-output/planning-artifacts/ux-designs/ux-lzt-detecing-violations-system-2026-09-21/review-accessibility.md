# Accessibility Review — Construction Monitoring Rapid MVP

## Overall verdict

**Adequate, but not yet a safe WCAG 2.2 AA implementation contract.** The spine pair has unusually strong foundations for a prototype: all core actions are intended to use native semantics, status is not color-only, image reordering has non-drag controls, pipeline announcements are throttled, touch targets are generous, reduced motion preserves state, and the phone flow is first-class. Three high-impact ambiguities remain: a declared non-text-contrast target is contradicted by the actual border token, asynchronous completion moves focus without a user request, and the SPA/dialog focus contract is incomplete.

This is a contract review, not a conformance audit of rendered code. WCAG 2.2 AA conformance still requires implementation and assistive-technology testing. The relevant normative anchors are [1.4.10 Reflow](https://www.w3.org/TR/WCAG22/#reflow), [1.4.11 Non-text Contrast](https://www.w3.org/TR/WCAG22/#non-text-contrast), [2.4.1 Bypass Blocks](https://www.w3.org/TR/WCAG22/#bypass-blocks), [2.4.11 Focus Not Obscured](https://www.w3.org/TR/WCAG22/#focus-not-obscured-minimum), [2.5.7 Dragging Movements](https://www.w3.org/TR/WCAG22/#dragging-movements), and [4.1.3 Status Messages](https://www.w3.org/TR/WCAG22/#status-messages).

## Strengths

- The two explicit reorder buttons plus optional drag satisfy the intended non-drag interaction model (`EXPERIENCE.md:91`, `EXPERIENCE.md:153`).
- Pipeline updates have a bounded screen-reader announcement strategy rather than announcing every poll (`EXPERIENCE.md:192`).
- Color, icons, shape, and full Russian status text are deliberately redundant (`DESIGN.md:237-241`, `EXPERIENCE.md:87`, `EXPERIENCE.md:193`).
- The 44×44 CSS-pixel target and 8px control separation exceed the WCAG 2.2 AA minimum target size (`EXPERIENCE.md:191`).
- The phone topology, explicit image ordering, no required orientation, and motion-independent pipeline state are sound foundations (`EXPERIENCE.md:151-159`, `EXPERIENCE.md:178-184`, `EXPERIENCE.md:197`).
- Evidence is paired with ordinal, usability, observation, and textual class/state information instead of relying only on boxes over images (`EXPERIENCE.md:194-195`).
- Error recovery preserves accepted images, their order, context, and persisted run state (`EXPERIENCE.md:139-141`, `EXPERIENCE.md:198`).
- The Russian copy avoids legal certainty, site-wide absence claims, unexplained status codes, and emotional escalation (`EXPERIENCE.md:58-73`, `EXPERIENCE.md:120-128`).

## Findings

### High

- **The shared border token does not meet the declared 3:1 non-text boundary target.** `{colors.border}` is `#5B456E` (`DESIGN.md:19`) and is used for buttons, panels, inputs by inheritance, evidence frames, run rows, and readiness rows (`DESIGN.md:107-116`, `DESIGN.md:142-145`, `DESIGN.md:158-173`, `DESIGN.md:198-215`). Calculated contrast is only 2.10:1 against canvas, 1.91:1 against surface, and 1.63:1 against raised surface, contradicting `DESIGN.md:241`. Where this line is the only perceivable control or component boundary, it cannot support WCAG 1.4.11. *Fix:* introduce an `interactive-border`/`essential-boundary` token that is at least 3:1 against every adjacent surface where it is used, and explicitly limit the existing subtle border to decorative separators whose disappearance does not impair identification. Record tested pairs in the token table.

- **A completed run is specified to steal focus asynchronously.** The `succeeded` state moves programmatic focus to the Result Summary heading when the result arrives (`EXPERIENCE.md:113`), while the pipeline may take an indeterminate amount of time. A user reading completed stages, evidence, or navigation can therefore lose their place without initiating that context change; this also conflicts with the otherwise good live-region strategy (`EXPERIENCE.md:192`). *Fix:* do not move focus merely because polling observes completion. Announce the terminal state once through a status region and expose a visible `Перейти к результату` link/button. Moving focus to the result heading is appropriate only when it is the immediate, user-initiated route destination (for example, after opening an already completed run).

- **Keyboard and focus behavior is incomplete for the SPA shell and the only modal surface.** The contract says `Tab` follows reading order and `Esc` closes the Evidence Viewer with return focus (`EXPERIENCE.md:152`), but it does not require a skip-to-content mechanism, route-specific document titles, focus/announcement after client-side navigation, initial dialog focus, a trapped focus scope, inert background content, or a programmatic dialog name (`EXPERIENCE.md:17`, `EXPERIENCE.md:81`, `EXPERIENCE.md:97`, `EXPERIENCE.md:158`). Radix inheritance is not enough unless the chosen primitive and its usage are named. *Fix:* add an Application Shell/route-focus contract: visible-on-focus `К основному содержимому`, one `main` landmark, route-specific `<title>` and `h1`, `aria-current="page"`, and focus the destination `h1` only after user-initiated navigation. Specify Evidence Viewer as a named modal dialog with initial focus on `Закрыть` (or the heading), contained tab order, background inertness, `Esc`, and focus restoration to the invoking thumbnail.

### Medium

- **Form errors are visible but not fully specified for assistive technology.** Persistent labels and contextual errors are good (`EXPERIENCE.md:98`), yet decode failures, invalid values, and submission failures do not require `aria-invalid`, `aria-describedby`, an error summary, or an announcement strategy (`EXPERIENCE.md:139-141`, `EXPERIENCE.md:198`). *Fix:* associate each message with its field or manifest row, announce newly added upload errors once without moving focus, focus an error-summary heading after a failed user-initiated submit, and link summary entries to the affected control while preserving all valid inputs.

- **The reflow statement does not close the full AA test boundary.** The documents promise 200% zoom and allow collapse to tablet/phone topology (`DESIGN.md:249`, `EXPERIENCE.md:184`), but do not explicitly require operation at a 320 CSS-pixel viewport without two-dimensional page scrolling, nor survival of user text-spacing overrides. Fixed bottom navigation and optional sticky submit are specifically capable of obscuring focused controls (`EXPERIENCE.md:43`, `EXPERIENCE.md:182`). *Fix:* require no loss or two-axis page scrolling at 320 CSS px (except the image canvas when its two-dimensional layout is essential), robust reflow under WCAG text-spacing overrides, safe-area padding, and enough scroll padding that top/bottom fixed regions never fully cover keyboard focus.

- **Programmatic state semantics are underspecified for composite controls.** The visual and textual states are clear, but the contract does not bind `Analysis Intent Selector` to a radio-group/select model, Stage Tile selection to an exposed selected/expanded state, or Bottom Navigation to `aria-current` (`EXPERIENCE.md:83`, `EXPERIENCE.md:89`, `EXPERIENCE.md:102`, `DESIGN.md:275`, `DESIGN.md:281`, `DESIGN.md:294`). *Fix:* choose native radio inputs for intent, buttons with `aria-pressed` or selection controls with `aria-selected` for stage selection as appropriate, and links with `aria-current="page"` for navigation. Keep the visible Russian label at the start of each accessible name.

- **Loading, submission, reconnect, and retry messages need one coherent status-region policy.** Pipeline transitions are covered, but the skeleton, `Создаём анализ…`, polling disconnect, recovered run identity, and per-file upload changes are not assigned `aria-busy`, `status`, or `alert` behavior (`EXPERIENCE.md:85`, `EXPERIENCE.md:111-116`, `EXPERIENCE.md:134`, `EXPERIENCE.md:139-141`, `EXPERIENCE.md:155`). *Fix:* define which container owns `aria-busy`, which non-critical updates use one polite status region, which blocking failures use an alert, and how duplicate messages are suppressed. Do not disable a submit control in a way that removes it from the accessibility tree before its state is announced.

- **Evidence Viewer zoom and annotation access are not keyboard-complete.** The viewer promises zoom, previous/next, close, metadata, and optional geometry (`DESIGN.md:288-289`, `EXPERIENCE.md:96-97`), but does not define keyboard-operable zoom/reset/pan, current zoom announcement, or a textual description for each supplied evidence region. *Fix:* provide named 44×44 `Увеличить`, `Уменьшить`, `Сбросить масштаб`, `Предыдущий кадр`, `Следующий кадр`, and `Закрыть` controls; announce frame position and zoom changes politely; keep metadata and observation text reachable outside the image; and list each evidence region's class/state association in text. Never put the full observation explanation only in `alt` text.

- **One prescribed user-facing message breaks the Russian-only rule.** `Для этого этапа правило не настроено в Rapid MVP` (`EXPERIENCE.md:136`) conflicts with the requirement that all primary copy and help be Russian and avoid unexplained abbreviations (`EXPERIENCE.md:60`, `EXPERIENCE.md:73`). *Fix:* use `Для этого этапа правило не настроено в прототипе` consistently; reserve `Rapid MVP` for technical or project metadata, if needed, with a Russian label.

- **Image removal lacks an explicit accidental-action recovery rule.** Reorder and decode recovery are strong, but `Удалить` is always available and the contract does not say whether a mistaken removal can be undone (`EXPERIENCE.md:91`, `EXPERIENCE.md:153`, `EXPERIENCE.md:198`). This is especially relevant on a dense phone manifest. *Fix:* retain a reversible local removal until submission and offer an inline `Вернуть` action announced politely; preserve the restored image's prior ordinal when possible.

### Low

- **Dense readiness evidence needs a screen-reader reading model.** The Readiness Criterion and Provider Comparison keep concepts separate (`EXPERIENCE.md:100-101`, `EXPERIENCE.md:248-260`), but literal counts, candidate-fixture cells, and revisions could become an inaccessible visual grid. *Fix:* require real table markup when relationships are tabular, captions and row/column headers, a short Russian summary before dense evidence, and expansion controls with exposed state. Do not use CSS grid alone to imply header relationships.

- **The contract should name the page language.** Russian-only copy is explicit (`EXPERIENCE.md:19`, `EXPERIENCE.md:60`), but the implementation requirement for `lang="ru"` is absent. *Fix:* set the document language to Russian and mark isolated English identifiers or provider/model names with `lang="en"` only when pronunciation materially benefits.

## Mechanical notes

- Finding count: **0 critical, 3 high, 7 medium, 2 low**.
- Contrast calculations used the WCAG relative-luminance formula on the declared hex tokens. Text pairs are sound: primary/canvas 16.02:1, secondary/canvas 9.72:1, primary/surface 14.62:1, secondary/surface 8.87:1, brand/on-brand 6.19:1; semantic text/surface pairs range from 7.84:1 to 8.86:1. Disabled text is exempt only while truly inactive, matching `DESIGN.md:236`.
- The focus token is strong against declared dark surfaces: focus/canvas 9.00:1, focus/surface 8.21:1, focus/selected 6.26:1. The 3px ring also exceeds AA visibility expectations; note that WCAG 2.2 Focus Appearance itself is AAA, while Focus Visible and Focus Not Obscured (Minimum) are AA.
- The supplied logo reconciliation contains the more precise meaningful alt text; `DESIGN.md` and `EXPERIENCE.md` correctly allow empty alt when adjacent text already names the team. Keep that exact duplication rule in implementation.
- `Input Manifest` correctly converts zero-based backend ordinals to one-based Russian labels (`EXPERIENCE.md:91`); live reordering should announce both item identity and its new `N из M` position.
- No GUI or browser was used. The imported PNGs and file-based working HTML were inspected as source/reference artifacts only. The working HTML files are decision boards, not conformance evidence, and include superseded small text and interaction shortcuts that must not be copied into product code.

## Resolution verification

Rechecked against the updated `DESIGN.md` and `EXPERIENCE.md`. This section verifies only the twelve findings above; it does not introduce new review scope.

### High findings

- **Partial — shared border token contrast.** `border-essential: #8F78A0` is now defined and used by load-bearing component tokens (`DESIGN.md:20`, `DESIGN.md:106-111`, `DESIGN.md:133-203`); its measured contrast is 4.46:1 on canvas, 4.07:1 on surface, 3.47:1 on raised surface, and 3.10:1 on selected surface. The prose also restricts `{colors.border}` to decorative separation (`DESIGN.md:225`, `DESIGN.md:230`, `DESIGN.md:250`). One conflicting component sentence remains: Secondary Button still specifies a `{colors.border}` boundary (`DESIGN.md:267`) even though its frontmatter correctly uses `{colors.border-essential}` (`DESIGN.md:106-110`). *Remaining fix:* change the Secondary Button prose reference to `{colors.border-essential}`.

- **Resolved — asynchronous completion moved focus.** Successful completion is announced without moving focus, and `Перейти к результату` moves focus only after activation (`EXPERIENCE.md:125`). Background updates are explicitly forbidden from moving focus (`EXPERIENCE.md:170`).

- **Resolved — SPA and modal keyboard/focus contract.** The shell now requires a skip link, `main`, Russian route titles, one `h1`, `aria-current`, and user-initiated route focus (`EXPERIENCE.md:170`). Evidence Viewer now has a programmatic name, initial focus, contained tab order, inert background, `Esc`, and trigger-focus restoration (`EXPERIENCE.md:171`).

### Medium findings

- **Resolved — form-error association and recovery.** Submission/API failure preserves inputs and provides an error summary and retry (`EXPERIENCE.md:155`). Fields and manifest rows use `aria-invalid`/`aria-describedby`; submit failure focuses a linked Russian error summary, while per-file errors announce without moving focus (`EXPERIENCE.md:180`).

- **Resolved — 320px reflow, text spacing, and fixed-control obstruction.** The contract now explicitly covers 200% zoom, a 320 CSS-pixel viewport, WCAG text-spacing overrides, the essential evidence-canvas exception, safe areas, and scroll padding for focused controls (`EXPERIENCE.md:215`).

- **Resolved — composite-control state semantics.** Analysis intent uses native grouped radios, stage selection exposes selected/pressed state appropriate to its role, and bottom navigation uses `aria-current="page"` (`EXPERIENCE.md:173`).

- **Partial — loading and status-region policy.** Submission, reconnect, retry, upload, and pipeline messages now share one duplicate-suppressing polite region; blocking failures use one alert, submit remains exposed, and active form/run containers use `aria-busy` (`EXPERIENCE.md:181`). However, the three skeleton-loading surfaces still do not explicitly mark their loading containers busy or their skeleton shapes hidden from assistive technology (`EXPERIENCE.md:146`, `EXPERIENCE.md:157`, `EXPERIENCE.md:161`). *Remaining fix:* require `aria-busy="true"` on each loading surface container and hide purely visual skeleton fragments from the accessibility tree until real content replaces them.

- **Resolved — Evidence Viewer keyboard zoom and annotation alternatives.** Named keyboard-operable zoom/reset/navigation/close controls and announcements are specified in the component contract (`EXPERIENCE.md:109`); modal focus behavior is defined (`EXPERIENCE.md:171`); controls are 44×44 and provider regions remain textual outside image alt text (`EXPERIENCE.md:228`).

- **Resolved — English phrase in Russian UI copy.** The non-configured-stage message is now `Для этого этапа правило не настроено в прототипе` (`EXPERIENCE.md:148`), consistent with the Russian-only copy rule (`EXPERIENCE.md:71`, `EXPERIENCE.md:84`).

- **Resolved — accidental image-removal recovery.** Input Manifest now specifies reversible local removal with `Вернуть` (`EXPERIENCE.md:102`), including announcement behavior and restoration of the prior ordinal when possible (`EXPERIENCE.md:172`).

### Low findings

- **Resolved — semantic reading model for dense readiness evidence.** Readiness/provider matrices must use semantic tables with captions, row and column headers, a short Russian summary, and expansion controls exposing state (`EXPERIENCE.md:232`).

- **Resolved — document language.** The root language is now explicitly `lang="ru"`, with isolated English identifiers marked only when pronunciation benefits (`EXPERIENCE.md:220`).

### Verification counts

- **Resolved:** 10
- **Partial:** 2
- **Unresolved:** 0

## Final partial-resolution check

Verified only the two items previously marked partial.

- **Resolved — Secondary Button border prose.** The visual component description now uses `{colors.border-essential}` (`DESIGN.md:267`), matching the frontmatter token (`DESIGN.md:106-110`) and the essential-boundary rule (`DESIGN.md:230`, `DESIGN.md:250`).
- **Resolved — skeleton loading semantics.** Stages Overview, Analysis History, and Prototype Readiness now put `aria-busy="true"` on the respective loading container and hide visual skeleton fragments from assistive technology (`EXPERIENCE.md:146`, `EXPERIENCE.md:157`, `EXPERIENCE.md:161`).

Final status for the two rechecked items: **2 resolved, 0 partial, 0 unresolved**. Across all twelve original accessibility findings: **12 resolved, 0 partial, 0 unresolved**.

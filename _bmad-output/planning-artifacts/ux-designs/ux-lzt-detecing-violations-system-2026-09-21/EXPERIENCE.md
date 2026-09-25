---
name: Construction Monitoring Rapid MVP
description: Responsive Russian-language experience contract for evidence-bound construction-stage analysis.
status: final
sources:
  - ../../../../spec.md
  - ../../../specs/spec-construction-monitoring-concepts/SPEC.md
  - ../../../specs/spec-construction-monitoring-concepts/prototype-scenarios.md
  - ../../architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md
updated: 2026-09-25
---

# Construction Monitoring Rapid MVP - Experience Spine

## Subsequent zone-plan experience (2026-09-25)

The original Rapid MVP journey below remains historical. The expansion adds a project and declared-zone selector, searchable source catalog, full-revision plan editor, and capture time for each JPEG/PNG frame. The run workspace overlays public normalized boxes on both thumbnails and the zoomed viewer, offers a show/hide control and a textual object list, and separates model stage hypotheses from one human confirmation. An empty hypothesis is shown as insufficient evidence. Unsupported classes and the cloud profile's absence of boxes are explicit.

A persistent Signals surface shows a new-count, type/status filters, evidence, linked zone/work/plan revision, recommendation, and state/comment controls. Missing-equipment signals require a series; the overdue-date signal says completion is unconfirmed. Closing a signal requires a human action. The plan editor must show concurrent operations rather than forcing a single current stage.

## Foundation

The product is a responsive web application for laptop and phone. It uses React and Vite and inherits accessible interaction primitives from Radix Themes. `DESIGN.md` is the visual identity reference; this document owns information architecture, behavior, states, accessibility, and journeys.

The exact user-facing product name is `Контроль строительства`. `17 мгновений ИИ` identifies the team and never replaces the product name in navigation or route titles.

The Rapid MVP is Russian-only and full-night. It supports jury demonstration and a credible construction-site-manager workflow. It does not include authentication, Gantt editing, resource-plan mutation, schedule ingestion, automatic current-stage inference, camera management, or automatic management action. Hosting and access control remain outside this UX contract until the deployment envelope is selected.

The experience keeps four concepts separate:

1. source images and their explicit order;
2. equipment observations;
3. the selected stage rule and its provenance;
4. a recommended human check.

The UI never turns a missing object in one frame into site-wide absence and never labels a check request as a confirmed, legal, or contractual violation.

Source precedence is explicit. The canonical `SPEC.md` and `prototype-scenarios.md` own Rapid MVP product scope and result meaning. `ARCHITECTURE-SPINE.md` owns the build substrate and backend-authoritative contracts. The repository-root `spec.md` preserves the broader technical-assignment goals but does not override or expand the canonical scope. Where capability IDs collide, this document uses `TA-CAP-*` for the technical-assignment digest and plain `CAP-*` only for the canonical SPEC.

| Technical-assignment requirement | Canonical Rapid MVP coverage |
|---|---|
| `TA-CAP-1` detect and classify equipment | `CAP-1`, `CAP-3`: excavator and dump-truck observations using the closed four-state contract. |
| `TA-CAP-2` relate observations to work stages | `CAP-4`: explicit excavation rule, revision, expectation, and provenance. |
| `TA-CAP-3` detect deviations | `CAP-4`, `CAP-5`: only the bounded possible haulage-delay check is implemented. Equipment inconsistent with other stages is deferred. |
| `TA-CAP-4` visualize results | `CAP-1` through `CAP-5`: Stages Overview, Run Workspace, observations, evidence, and check explanation. |
| `TA-CAP-5` reproducible demonstration | `CAP-5`, `CAP-6`: demonstration fixtures, immutable run evidence, and criterion-level readiness. |

Visual lineage: [hackathon task-page reference](imports/hackathon-task-page-reference.png), [team logo](imports/team-17-mgnoveniy-ii-logo.png), and the selected [stage-map plus analysis-route direction](.working/directions-entry-surface.html). The full-night choice is illustrated in [.working/hackathon-theme-options.html](.working/hackathon-theme-options.html). These references illustrate visual decisions; if they conflict with the design and experience spines, the spine documents take precedence.

## Information Architecture

| Surface | Reached from | Purpose | Primary action |
|---|---|---|---|
| Stages Overview (`Этапы`) | App open, primary navigation | Read-only evidence navigator for construction stages and their latest completed analysis outcome | Select a stage or start `Новый анализ` |
| New Analysis (`Новый анализ`) | Persistent primary action, selected stage | Confirm intent and context, add ordered images, or choose a demonstration fixture | `Запустить анализ` |
| Run Workspace (`Анализ`) | Submission, analysis history, stage inspector, selected signal | Show the saved outcome and its evidence first on completed runs; reveal the processing stages on demand | Inspect evidence or open linked retry |
| Analysis History (`Анализы`) | Primary navigation | Reopen recent runs, compare outcomes, and follow predecessor/successor lineage | Open a run |
| Zone Plan (`План`) | Primary navigation | Select a project and zone, inspect catalog work, and save a new zone-plan revision | Save revision |
| Signals (`Сигналы`) | Primary navigation | Triage plan and analysis signals against their saved plan revision | Update state and comment |
| Prototype Readiness (`Готовность`) | `Ещё`, end of jury flow | Show criterion-level readiness evidence and a separate provider comparison | Open criterion evidence |
| About Project (`О проекте`) | `Ещё` or team attribution | Explain team identity, method, scope, limitations, and source provenance | Return to previous surface |

Composition references: [Stages Overview](mockups/key-stages-overview.html), [New Analysis](mockups/key-new-analysis.html), [Run Workspace](mockups/key-run-workspace.html), and [Prototype Readiness](mockups/key-readiness.html).

Laptop primary navigation contains `Этапы`, `Анализы`, `План`, and `Сигналы`; `Новый анализ` remains the persistent primary action. `Готовность`, `Сравнение провайдеров`, and `О проекте` are in the keyboard-accessible `Ещё` menu. Phone uses labeled bottom navigation for the four primary destinations and a visible `Новый анализ` action in the compact header.

The Stages Overview is not a schedule or health dashboard. A stage status summarizes only the latest completed analysis bound to that stage:

| Russian label | Meaning |
|---|---|
| `Анализов нет` | No completed run exists for this stage. |
| `Проверка не запрошена` | The latest completed rule-evaluation run produced `no_check`. |
| `Рекомендована проверка человеком` | The latest completed run produced one human check request. |
| `Недостаточно данных` | The run succeeded but evidence was insufficient for rule evaluation. |
| `Только наблюдения` | The latest succeeded run had observation-only intent; no stage rule was evaluated. |
| `Не анализировалось` | The latest succeeded rule-evaluation projection was out of scope or the rule was not applicable. |
| `Не настроено в прототипе` | The stage has no configured Rapid MVP rule. |

The stage outcome always comes from the most recent run for which both the run and its Result Projection succeeded. A newer queued, running, or failed run is shown separately as lifecycle context and never replaces the last evidence-backed outcome. No percentage, date bar, trend arrow, or red/green project-health rollup is shown unless a future schedule contract defines it.

## Voice and Tone

All user-facing copy, accessibility names, errors, statuses, and help are Russian. Stable backend codes and revision IDs may appear in technical disclosures with a Russian label.

The voice is concise, managerial, and evidence-bound. It says what the system observed, what rule was applied, and what a person should check. It does not dramatize uncertainty or imitate legal certainty.

| Prefer | Avoid |
|---|---|
| `Самосвал не обнаружен ни в одном из <N> пригодных кадров.` | `Самосвал отсутствует на площадке.` |
| `Возможна задержка вывоза грунта.` | `Обнаружено нарушение графика.` |
| `Проверьте подачу самосвалов в зону погрузки.` | `Необходимо срочно изменить план.` |
| `Недостаточно данных для проверки правила этапа.` | `Анализ не удался.` |
| `Этап распознавания завершён.` | `ИИ успешно всё распознал.` |
| `Не настроено в прототипе.` | `Скоро будет доступно!` |

Use sentence case. Buttons use short verb phrases: `Добавить изображения`, `Выбрать пример`, `Запустить анализ`, `Открыть доказательства`, `Повторить анализ`. Avoid exclamation marks, gamification, unexplained abbreviations, marketing claims, and English status text.

## Evidence and Check-request Semantics

The primary result reads in this order:

1. outcome in Russian;
2. recommended human action, when present;
3. concise reason using observations;
4. evidence images and observation period;
5. applied rule and provenance;
6. uncertainty and technical revisions behind disclosure.

For the configured excavation rule, the rule-evaluation path may request a check only when the backend projection says `check_requested`. The UI does not independently count frames, inspect detector confidence, or infer persistent absence.

Multi-frame evidence always has two visible layers:

1. per-frame, per-requested-class Observation Rows, each with exactly one closed state and exact frame reference;
2. a separate Series Evidence block containing backend-projected usable-frame count, same-area confirmation, upload order, excavator-supporting frames, and persistence evidence.

The series sentence is parameterized from backend evidence as `Самосвал не обнаружен ни в одном из <N> пригодных кадров.` It never becomes `Самосвал отсутствует` and never invents a fifth observation state.

In the completed workspace, `Основание вывода` keeps observations, series suitability, declared zone, period, rule, and recommendation near the selected source image. Only `supporting_input_ids` from the persisted projection can mark a frame as supporting evidence. The large image and thumbnails use the same artifact route; object boxes appear only when saved normalized geometry is valid and stay aligned to the rendered image. Run IDs, frame IDs, hashes, and observer payloads sit in named technical disclosures. Partial observations on a failed run retain a visible incomplete-run label.

Provider-native artifacts remain secondary and explicitly attributed. Their technical disclosure labels provider/adapter, model or observer execution-profile revision, observer invocation, exact source frame IDs, preprocessing revision when applicable, and artifact identity/checksum. Native counts, confidence, and geometry are marked `Данные конкретного наблюдателя. Не используются правилом этапа.`

The exact safety line in every Check-request Panel is: `Это рекомендация для проверки, а не подтверждение нарушения.` It remains visible without expanding technical detail.

## Component Patterns

Visual specifications are defined in the Components section of `DESIGN.md` and inherit Radix Themes unless explicitly overridden.

| Component | Use | Behavioral rules |
|---|---|---|
| Application Shell | Every surface | Keeps four primary destinations, current destination, the `Ещё` disclosure, and one persistent `Новый анализ` action. Restores the last safe route after refresh. |
| Team Brand Block | Stages Overview and About Project | Uses the complete supplied logo only where its embedded wordmark remains legible. Compact headers use the text `17 мгновений ИИ`, not a cropped or invented mark. |
| Stage Tile | Stages Overview | Entire tile selects the stage. Shows the outcome of the latest succeeded Result Projection plus any newer run lifecycle as a separate line; never a plan-completion status. |
| Stage Inspector | Stages Overview | Shows selected stage, latest outcome, area and period, then routes to evidence or a new analysis. Non-configured stages explain scope rather than presenting a dead control. |
| Primary Button | One per decision area | Fires the main action. During submission, replace the label with `Создаём анализ…` and prevent duplicate submission without hiding the control. |
| Secondary Button | Supporting actions | Used for `Выбрать пример`, `Изменить`, `Отмена`, and non-primary navigation. Never competes visually with the primary action. |
| Status Label | Stage, run, pipeline, readiness | Always includes the full Russian label. Color and icon are supplemental. It is not interactive unless paired with a separate disclosure control. |
| Analysis Context | New Analysis | Persistent fields show intent, stage, area, and period. An optional project/zone selector binds the saved plan revision; each bound frame keeps its capture time. Rule name, revision, expectation, and provenance stay visible for rule evaluation. |
| Analysis Intent Selector | New Analysis | Two explicit choices: default `Проверить правило этапа` and secondary `Только распознать технику`. Changing intent updates the explanation before submission. If the selected stage has no applicable rule, `Проверить правило этапа` is unavailable with the visible reason `Для этого этапа правило не настроено в прототипе`, and `Только распознать технику` is selected; the UI never silently chooses a rule. |
| Image Uploader | New Analysis | File selection and drop use one validation path: up to eight JPEG/PNG files, 16 MB and 40 million pixels each. Camera capture remains available where supported; subjective visibility is evaluated by the pipeline. Demonstration examples start collapsed. |
| Input Manifest | New Analysis | Lists local previews, name, size, capture time when bound to a plan, and every accepted image's zero-based backend ordinal as `Кадр 1`, `Кадр 2`, and so on. Explicit reorder and reversible remove controls remain available. |
| Pipeline Route | Run Workspace | Renders six persisted stages ordered by ordinal, not by timestamp, with these exact labels: `Регистрация входных данных`, `Проверка пригодности кадров`, `Распознавание техники`, `Объединение наблюдений серии`, `Проверка правила`, `Формирование результата`. Stable backend keys appear only in technical disclosure. |
| Observation Row | Run result | One frame, one requested class, exactly one closed observation state, and the exact evaluated-input reference. `Не анализировалось` remains a visible row with reason and input reference; only detection, non-detection, deviation claims, and check requests are suppressed. |
| Series Evidence | Run result | Separate from Observation Rows. Shows usable-frame count, same-area confirmation, upload order, excavator-supporting frame references, and backend-supplied persistence wording such as `Самосвал не обнаружен ни в одном из <N> пригодных кадров`. |
| Result Summary | Run result | Shows exactly one backend-derived outcome: observations only, not analyzed, insufficient data, check requested, or no check. Client code never re-derives it. |
| Check-request Panel | Run result | Separates recommendation from observations. Exposes reason, evidence, area, period, rule revision, provenance, uncertainty, and recommended human check. |
| Evidence Thumbnail | Run result and Evidence Viewer | Shows source ordinal outside the image. Optional evidence geometry is rendered only when supplied; absence of geometry means whole-frame evidence. |
| Evidence Viewer | Evidence disclosure | Named modal on laptop and full-screen modal on phone. Provides keyboard-operable `Увеличить`, `Уменьшить`, `Сбросить масштаб`, `Предыдущий кадр`, `Следующий кадр`, and `Закрыть`; announces frame position and zoom changes. Every provider-native artifact discloses provider/adapter, execution-profile revision, observer invocation, exact source frame IDs, preprocessing revision when applicable, and artifact identity/checksum. Native counts, confidence, and geometry are labeled non-rule-driving. |
| Input Field | Analysis Context and editable metadata | Persistent label above, optional helper below, and contextual inline error. Placeholder never replaces the label; invalid values preserve user input. |
| Run Row | Analysis History | Shows creation time, stage, intent, lifecycle, outcome when terminal, and linked retry identity. Running rows update without reordering the list. |
| Readiness Criterion | Prototype Readiness | Shows criterion name, `Пройдено`, `Не пройдено`, or `Нет данных`, then literal evidence and linked runs. Coverage includes evaluation-set identity and size, image checksums, manual labels, test-specific sufficiency conditions, false warnings, misses, false detections, disagreements, and check-request comprehension. Never compresses readiness into one decorative score. |
| Provider Comparison | Prototype Readiness | Separate block with candidate identity, complete planned-run accounting, failures/timeouts, and report status. It never implies readiness or silently publishes a winner. |
| Signal List and Detail | Signals | Filters `Все`, `Новые`, `В работе`, `Закрытые` preserve the selected signal and its unsaved comment. Initially 20 rows load; `Показать ещё` opens the next page. The detail reads the linked run and exact saved plan revision, and keeps its basis visible when frames are unavailable. A calendar signal explains that it has no linked analysis. |
| Bottom Navigation | Phone | Four labeled destinations: `Этапы`, `Анализы`, `План`, `Сигналы`. Active state uses text, shape, and {colors.brand}; no icon-only mode. |
| Inline Notice | Forms and run states | Contextual warning, error, or reconnect information placed next to the affected content. Toasts are reserved for transient confirmation with no required action. |

Overlay reference: [Evidence Viewer](mockups/key-evidence-viewer.html).

## State Patterns

### Run and pipeline lifecycle

| State | Treatment |
|---|---|
| `queued` | Run Workspace opens immediately. Header says `Анализ поставлен в очередь`; all six stages are visible as pending. |
| `running` | Exactly one eligible stage says `Выполняется`; prior stages show persisted completion summaries; later stages remain `Ожидает`. No percentage or estimated finish time. |
| `succeeded` | The saved result leads the workspace and the pipeline moves into a collapsed disclosure. Completion is announced once without moving focus. A visible `Перейти к результату` action moves focus to its heading only when activated. |
| `failed` | Active stage shows `Ошибка выполнения`; completed evidence stays visible. Downstream stages show `Пропущено: предыдущий этап завершился ошибкой`. |
| polling disconnected | Inline Notice says `Связь потеряна. Анализ может продолжаться на сервере.` Keep the known state and offer `Проверить статус`; do not fabricate failure. |
| interrupted by server restart | Terminal failure explains `Выполнение было прервано`. `Повторить анализ` creates a linked successor run; it never resumes or overwrites the failed run. |

### Observation and outcome states

| Domain state | Russian presentation | Required behavior |
|---|---|---|
| `detected` | `Обнаружен` / `Обнаружена` | Link to evaluated inputs; do not promote provider-native counts to the main result. |
| `not_detected_in_frame` | `Не обнаружен в кадре` | Always retain the frame boundary in wording. Never summarize as site-wide absence. |
| `insufficient_data` | `Недостаточно данных` | At class level, explain observer inability or frame evidence limits and retain the evaluated-frame reference. At rule-evaluation outcome level, explain visibility, coverage, or series sufficiency. Suppress check requests. |
| `not_analyzed` | `Не анализировалось` | Keep the requested-class row, reason, scope/rule explanation, and evaluated-input reference visible. Suppress only detection/non-detection, deviation claims, and check requests. |
| `observations_only` | `Только наблюдения` | Keep this top-level outcome even if every requested class is `Недостаточно данных`. Show class states and evidence, then state `Правило этапа не проверялось`; never produce a check request. |
| `no_check` | `Проверка не запрошена` | Show supporting observations and applied rule. Do not style this as proof that the whole stage is healthy. |
| `check_requested` | `Рекомендована проверка человеком` | Show one Check-request Panel and the explicit non-violation statement. |

### Surface-specific states

| Surface | State | Treatment |
|---|---|---|
| Stages Overview | loading | Stage-map container exposes `aria-busy="true"`; visual skeleton fragments are hidden from assistive technology and preserve final layout. No spinner appears over an empty page. |
| Stages Overview | no completed runs | Every configured stage says `Анализов нет`; `Новый анализ` remains the single primary action. |
| Stages Overview | non-configured stage | Inspector explains `Для этого этапа правило не настроено в прототипе` and points to the configured excavation stage. |
| New Analysis | no images | Explain accepted formats and the difference between own images and demonstration examples. |
| New Analysis | one or two images for rule evaluation | Allow submission; Inline Notice says `Для проверки правила требуется не менее трёх пригодных изображений одной зоны. Результатом может быть «Недостаточно данных».` |
| New Analysis | decode failure | Reject only the affected file with `Файл не удалось прочитать как изображение`; preserve all other inputs and order. |
| New Analysis | camera permission denied | Keep file upload available and say `Доступ к камере не предоставлен. Выберите изображения из файлов.` Do not repeatedly prompt for permission. |
| New Analysis | duplicate checksum | Keep both images and their ordinals; disclose duplication without blocking, matching the active policy. |
| New Analysis | submitting | Disable duplicate submit, preserve the manifest, and transition to the created Run Workspace after authoritative `run_id` response. |
| New Analysis | submission or API failure | Keep context, accepted images, order, and intent. Associate the Russian error with an error summary and offer `Повторить отправку`; reconcile any uncertain `run_id` before enabling a second submission. |
| Signals | no records or filter matches | Keep all four filters visible and explain that no signals match the selected state. |
| Signals | row selected | Open saved basis, saved plan revision, linked run, current human state, and the comment draft. On phones place this detail directly after the row. |
| Signals | switched selection or filter during a read | Cancel the obsolete run/plan requests and ignore late responses. Keep each signal's unsaved comment in its own draft. |
| Signals | failed save or artifact | Preserve the comment and signal context; show an inline retryable error. A missing preview never removes the saved basis. |
| Signals | calendar signal without analysis | Show the plan-based reason and state explicitly that no linked frames exist. `Закрыт` means manual handling is complete, not that the site is safe. |
| Analysis History | empty | `Запусков пока нет.` with `Новый анализ`. |
| Analysis History | loading or fetch failure | History container exposes `aria-busy="true"`; visual skeleton fragments are hidden from assistive technology and preserve list geometry. On failure show `Не удалось загрузить анализы` and `Повторить`; do not replace a previously loaded list with blank content. |
| Analysis History | mixed lifecycle | Grouping and sorting remain stable; status updates do not jump rows under the pointer or focus. |
| Prototype Readiness | incomplete report | Show missing criteria and planned runs explicitly; do not calculate an overall pass. |
| Prototype Readiness | failed readiness | Put failing criteria first, retain literal counts and run links, and avoid celebratory or punitive language. |
| Prototype Readiness | loading or fetch failure | Readiness container exposes `aria-busy="true"`; visual skeleton fragments are hidden from assistive technology. Preserve the last report timestamp when available. Show `Не удалось загрузить отчёт о готовности` with retry; never infer pass from cached fragments. |
| Provider Comparison | incomplete matrix | `Сравнение не завершено`; list missing, failed, and timed-out candidate-fixture cells. No winner is shown. |
| Evidence Viewer | artifact loading or integrity failure | Keep frame metadata and observation text available. If bytes fail to load or checksum verification fails, say `Не удалось открыть исходное изображение` or `Целостность артефакта не подтверждена`; close and retry remain available. |
| About Project | logo unavailable | Render the exact text `17 мгновений ИИ`; never substitute a generic AI icon. |
| Global | offline before submission | Disable network-dependent submission without removing controls. Preserve local form state and say `Нет соединения. Изображения останутся на этом устройстве до обновления страницы.` The MVP does not queue uploads offline. |

Recovery-state reference: [Recovery States](mockups/key-recovery-states.html).

## Interaction Primitives

- Click or tap selects; keyboard `Enter` and `Space` activate controls according to native semantics.
- Application Shell starts with a visible-on-focus `К основному содержимому` link and one `main` landmark. Every route has a Russian document title and one `h1`; links expose `aria-current="page"`. User-initiated client-side navigation moves focus to the destination `h1`, while polling and other background updates never move focus.
- `Tab` order follows visual reading order. Evidence Viewer is a programmatically named modal dialog. It places initial focus on `Закрыть` or the dialog heading, contains the tab order, makes the background inert, closes with `Esc`, and restores focus to the invoking Evidence Thumbnail.
- Users may change image order by dragging on pointer devices, but every item also provides `Выше`, `Ниже`, and `Удалить`. Reordering announces item identity and new `N из M` position. Removal remains locally reversible with `Вернуть` until submission and restores the prior ordinal when possible.
- Analysis Intent Selector uses native radio inputs inside a named group. Stage Tile selection exposes state with a selected/pressed semantic appropriate to its control role. Bottom Navigation uses links with `aria-current="page"`.
- Stage selection updates the Stage Inspector without changing schedule state. On phone, selection scrolls the inspector into view only after a user action.
- Submitting an analysis is idempotent from the user's perspective: one activation produces one visible run. A duplicate or uncertain response is reconciled by the returned or recovered run identity before another submit is enabled.
- Leaving a running workspace does not cancel the run. Analysis History shows it as queued or running. The MVP exposes no cancel action because the architecture defines no cancellation transition.
- Retry is offered only for technical failure. It always creates a successor linked by `retry_of_run_id`; the user may keep or explicitly change the observer execution profile without losing lineage. Changing images, intent, area/period, rule, or policy starts a distinct new analysis instead of retrying history.
- Result details use inline disclosure before dialogs. The Evidence Viewer is the only load-bearing overlay.
- Motion lasts 150-220ms and communicates selection, disclosure, or state change. Pipeline progress is primarily textual. `prefers-reduced-motion` removes transforms and pulses without hiding state.
- Form and manifest errors use `aria-invalid` and `aria-describedby`. A failed user-initiated submit focuses a Russian error-summary heading whose entries link to affected controls; newly added per-file errors are announced once without moving focus.
- One polite status region owns non-critical upload, submission, reconnect, retry, and pipeline messages and suppresses duplicates. The active form or run container exposes `aria-busy`; blocking failures use one alert. A submitting button remains present in the accessibility tree with its updated label.

## Responsive & Platform

| Viewport | Navigation and layout | Evidence and forms |
|---|---|---|
| Laptop, `>= 1024px` | Persistent top navigation. Stage map and inspector use a wide/narrow split. Pipeline uses the saved six-step order. | New Analysis shows context in about one third of the width and images in the remaining column. Completed Result shows a large selected frame beside its basis. Signals shows list and selected detail side by side. |
| Tablet, `768-1023px` | Top navigation condenses but keeps text labels. Stage inspector stacks below the map. Pipeline becomes a vertical route. | New Analysis stacks context and images. The result and signal columns may stack without changing reading order. |
| Phone, `< 768px` | Compact top bar plus four labeled Bottom Navigation destinations. Stage map is a single list; selected inspector follows the tile. | Result reads outcome, basis, image, then technical detail. Signal detail opens immediately after its selected row. Camera/file input, explicit reorder buttons, full-screen Evidence Viewer, and the submit panel remain operable above bottom navigation. |

The experience does not require a specific device orientation. At 200% browser zoom, laptop layout may collapse to the phone/tablet topology. At a viewport width of 320 CSS pixels, including with WCAG text-spacing overrides, the page remains operable without two-dimensional scrolling. The zoomable evidence canvas is the only essential region that may scroll on both axes. Content order remains meaningful without CSS positioning. Fixed navigation and optional sticky submit honor device safe areas and provide scroll padding so focused controls are never fully obscured.

## Accessibility Floor

- WCAG 2.2 AA is the minimum. Color contrast uses the tested pairs in `DESIGN.md`; real-image overlays are tested separately.
- The document root uses `lang="ru"`. Isolated provider/model identifiers use `lang="en"` only when it materially improves pronunciation.
- All controls use native buttons, links, and inputs through Radix Themes or semantic HTML; page structure uses semantic headings. A whole Stage Tile may be clickable only when it has one clear action and a programmatic name.
- Visible focus uses `{components.application-shell.focusColor}`, `{components.application-shell.focusWidth}`, and `{components.application-shell.focusOffset}`. Focus is never removed on pointer use.
- Minimum touch target is 44x44 CSS px. Adjacent reorder and evidence controls retain at least 8px separation.
- Pipeline updates use a polite live region that announces stage transition once, not every poll. Terminal success or failure is announced assertively once.
- Status labels always include text. Shape, icon, and color are redundant cues.
- Images have contextual alternatives: source ordinal, whether the frame was usable, and the relevant observation. Decorative logo use has empty alt text when adjacent text already names the team.
- Evidence boxes are not the only explanation. Each box has a textual class/state association, and users can inspect the source without overlays.
- Evidence Viewer zoom/reset, previous/next, and close controls are keyboard-operable 44x44 targets. Frame position and zoom changes use the shared polite status region; provider regions are listed as text outside the image rather than hidden inside alt text.
- Onest loading uses `font-display: swap`; the system fallback must not cause clipped labels or layout-dependent controls.
- Reduced motion preserves every state. No timed action, auto-advancing carousel, scroll hijack, or flashing content is allowed.
- Error recovery preserves context, accepted images, explicit order, and the last persisted run state.
- Readiness and provider matrices use semantic tables when row/column relationships exist, with captions, row and column headers, a short Russian summary, and expansion controls exposing expanded state.

## Inspiration & Anti-patterns

- **Retained from the hackathon reference:** full-night plum environment, violet brand/action accent, high-contrast type, generous space, and restrained decoration. See [reference reconciliation](reconcile-hackathon-reference.md).
- **Transformed for an operating product:** editorial event cards become compact evidence panels; the chosen Direction C stage map leads into Direction B's causal analysis route.
- **Retained from the team logo:** construction plus AI identity and the exact name `17 мгновений ИИ`. The full artwork appears only where it remains legible. See [logo reconciliation](reconcile-team-logo.md).
- **Rejected:** hackathon-site navigation, task number, authorization CTA, prize content, language switch, long promotional copy, decorative violet status meaning, fake progress, and marketing motion.
- **Rejected:** Gantt editing, project-health scoring, automatic current-stage inference, site-wide absence claims, model-confidence theater, and any UI that presents a recommendation as a violation.

## Key Flows

### Flow 1 - Jury demonstrates the check request (Marina, jury member, laptop)

**Covers:** CAP-2, CAP-3, CAP-4, CAP-5.

1. Marina opens `Этапы` and sees that only `Земляные работы котлована` is configured for the full Rapid MVP rule.
2. She selects the stage and chooses `Новый анализ`.
3. New Analysis defaults to `Проверить правило этапа` and shows the explicit area, period, applied rule revision, expectation, and demonstration-rule provenance.
4. She expands the demonstration examples and chooses `Самосвал не обнаружен в серии`; three ordered images populate the Input Manifest.
5. She confirms context and selects `Запустить анализ`.
6. Run Workspace first shows the queued state, then updates the six pipeline stages as persisted status arrives.
7. Result Summary becomes `Рекомендована проверка человеком`. The Check-request Panel says `Возможна задержка вывоза грунта` and recommends checking dump-truck supply.
8. Marina opens evidence, then rule provenance and uncertainty.
9. She opens a saved `Проверка не запрошена` run for contrast, then visits `Готовность` through `Ещё`.
10. She opens `О проекте` to verify the team, method, supported scope, and explicit limitations.
11. **Climax:** Marina can explain in her own words that an excavator was observed, no dump truck was observed in the three usable frames, and the system requested a human check rather than declaring a violation.

Failure path: if polling disconnects, the workspace preserves the last persisted stage and offers `Проверить статус`. If execution fails, completed evidence remains and `Повторить анализ` creates a linked successor.

### Flow 2 - Site manager records an observation (Alexey, construction site manager, phone)

**Covers:** CAP-1, CAP-3, CAP-4.

1. Alexey opens `Этапы` on his phone and selects `Земляные работы котлована`.
2. He chooses `Новый анализ`, then changes intent to `Только распознать технику`.
3. He confirms the controlled area and observation period.
4. He adds one image from the camera or file picker.
5. Input Manifest labels it `Кадр 1`; he confirms and submits.
6. He watches the vertical six-stage pipeline. Non-applicable rule stages may show the backend skip reason.
7. Result Summary says `Только наблюдения`; Observation Rows show excavator and dump-truck states bound to the frame.
8. **Climax:** Alexey understands exactly what the image supports without mistaking in-frame non-detection for absence from the site.

Failure path: an unsupported or undecodable file appears as an upload error with a recovery action. For an accepted but unassessable image, the top-level Result Summary remains `Только наблюдения`; each affected class row says `Недостаточно данных`, identifies the evaluated frame and reason, and states `Правило этапа не проверялось`.

### Flow 3 - Site manager handles insufficient series evidence (Alexey, phone, interrupted field session)

**Covers:** CAP-2, CAP-3, CAP-4.

1. Alexey chooses `Проверить правило этапа` but has only two images.
2. Inline Notice explains the three-usable-image policy without blocking submission.
3. He submits because he needs the observation record now.
4. The pipeline succeeds; Result Summary says `Недостаточно данных` and no Check-request Panel appears.
5. The result identifies the series-sufficiency reason and retains both ordered frames.
6. **Climax:** Alexey understands that the system withheld a warning because evidence was insufficient, not because the stage was healthy.
7. Later he starts a new analysis with a third image; the historical run remains unchanged.

Failure path: if one accepted image cannot be assessed, the result explains observer inability rather than silently converting it to `Не обнаружен в кадре`.

### Flow 4 - Jury verifies prototype readiness (Marina, jury member, after the live demo)

**Covers:** CAP-6.

1. Marina opens `Готовность`.
2. She sees the bound evaluation-set identity, its 10-15 checksummed images, manual excavator/dump-truck label coverage, test-specific sufficiency conditions, policy, rule, and report revisions.
3. She reviews check-request, no-check, insufficient-data, and out-of-scope fixture coverage using Russian outcome labels.
4. She checks false warnings first, then misses, false detections, repeated-run disagreements, and the recorded check-request comprehension outcome as separate literal measures.
5. She opens one failed or passed criterion to inspect linked runs and evidence.
6. She reviews Provider Comparison in its separate block and sees whether every planned candidate-fixture cell is terminal.
7. **Climax:** Marina can distinguish prototype readiness from model comparison and reproduce which evidence supports each decision.

Failure path: an incomplete evaluation or comparison matrix is labeled `Не завершено`; missing cells remain visible and no aggregate winner or readiness pass is inferred.

---
name: Construction Monitoring Rapid MVP
description: Full-night evidence interface for the 17 мгновений ИИ hackathon prototype, built on Radix Themes.
status: final
sources:
  - ../../../../spec.md
  - ../../../specs/spec-construction-monitoring-concepts/SPEC.md
  - ../../../specs/spec-construction-monitoring-concepts/prototype-scenarios.md
  - ../../architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md
updated: 2026-09-26
colors:
  canvas: '#211331'
  surface: '#2B1A3D'
  surface-raised: '#38264A'
  surface-selected: '#432B59'
  text-primary: '#F7F4F9'
  text-secondary: '#C9BDD1'
  text-disabled: '#897A91'
  border: '#5B456E'
  border-essential: '#8F78A0'
  brand: '#B984E0'
  brand-hover: '#C997EB'
  on-brand: '#211331'
  focus: '#D7A8F6'
  attention-surface: '#4C3512'
  attention-text: '#FFD98A'
  success-surface: '#173C32'
  success-text: '#8FE0BC'
  insufficient-surface: '#24364A'
  insufficient-text: '#B9D8F6'
  error-surface: '#4A2429'
  error-text: '#FFB4B9'
  neutral-surface: '#34293F'
  neutral-text: '#D6CDD9'
typography:
  display:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 40px
    fontWeight: '650'
    lineHeight: '1.15'
    letterSpacing: -0.02em
  heading-lg:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 28px
    fontWeight: '650'
    lineHeight: '1.2'
    letterSpacing: -0.015em
  heading-md:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 22px
    fontWeight: '650'
    lineHeight: '1.3'
  body:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-strong:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 16px
    fontWeight: '600'
    lineHeight: '1.45'
  label:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 14px
    fontWeight: '600'
    lineHeight: '1.4'
  caption:
    fontFamily: 'Onest, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.45'
rounded:
  sm: 6px
  md: 8px
  lg: 12px
  xl: 16px
  full: 9999px
spacing:
  '1': 4px
  '2': 8px
  '3': 12px
  '4': 16px
  '5': 20px
  '6': 24px
  '8': 32px
  '10': 40px
  '12': 48px
  page-mobile: 16px
  page-tablet: 24px
  page-desktop: 32px
components:
  application-shell:
    background: '{colors.canvas}'
    foreground: '{colors.text-primary}'
    maxContentWidth: 1440px
    focusColor: '{colors.focus}'
    focusWidth: 3px
    focusOffset: 2px
  primary-button:
    background: '{colors.brand}'
    foreground: '{colors.on-brand}'
    hoverBackground: '{colors.brand-hover}'
    radius: '{rounded.md}'
    minHeight: 44px
  secondary-button:
    background: '{colors.surface-raised}'
    foreground: '{colors.text-primary}'
    border: '{colors.border-essential}'
    radius: '{rounded.md}'
    minHeight: 44px
  stage-tile:
    background: '{colors.surface-raised}'
    selectedBackground: '{colors.surface-selected}'
    selectedBorder: '{colors.brand}'
    radius: '{rounded.lg}'
  status-label:
    attentionBackground: '{colors.attention-surface}'
    attentionForeground: '{colors.attention-text}'
    successBackground: '{colors.success-surface}'
    successForeground: '{colors.success-text}'
    insufficientBackground: '{colors.insufficient-surface}'
    insufficientForeground: '{colors.insufficient-text}'
    errorBackground: '{colors.error-surface}'
    errorForeground: '{colors.error-text}'
    neutralBackground: '{colors.neutral-surface}'
    neutralForeground: '{colors.neutral-text}'
    radius: '{rounded.sm}'
  team-brand-block:
    background: '{colors.surface}'
    foreground: '{colors.text-primary}'
    radius: '{rounded.lg}'
  stage-inspector:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
    radius: '{rounded.lg}'
  analysis-context:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
    radius: '{rounded.lg}'
  analysis-intent-selector:
    selectedBackground: '{colors.surface-selected}'
    selectedBorder: '{colors.brand}'
    radius: '{rounded.md}'
  image-uploader:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
    radius: '{rounded.lg}'
  input-manifest:
    rowBackground: '{colors.surface-raised}'
    border: '{colors.border-essential}'
    radius: '{rounded.md}'
  pipeline-route:
    completed: '{colors.success-text}'
    active: '{colors.brand}'
    failed: '{colors.error-text}'
    pending: '{colors.neutral-text}'
  observation-row:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
  series-evidence:
    background: '{colors.surface-raised}'
    border: '{colors.border-essential}'
    radius: '{rounded.md}'
  result-summary:
    background: '{colors.surface-raised}'
    foreground: '{colors.text-primary}'
    radius: '{rounded.lg}'
  check-request-panel:
    background: '{colors.attention-surface}'
    foreground: '{colors.attention-text}'
    radius: '{rounded.lg}'
  evidence-thumbnail:
    background: '{colors.neutral-surface}'
    border: '{colors.border-essential}'
    radius: '{rounded.md}'
  evidence-viewer:
    background: '{colors.canvas}'
    foreground: '{colors.text-primary}'
    radius: '{rounded.xl}'
  input-field:
    background: '{colors.surface-raised}'
    foreground: '{colors.text-primary}'
    border: '{colors.border-essential}'
    radius: '{rounded.md}'
  run-row:
    background: '{colors.surface}'
    border: '{colors.border}'
  readiness-criterion:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
  provider-comparison:
    background: '{colors.surface}'
    border: '{colors.border-essential}'
    radius: '{rounded.lg}'
  bottom-navigation:
    background: '{colors.surface}'
    foreground: '{colors.text-secondary}'
    active: '{colors.brand}'
  inline-notice:
    background: '{colors.neutral-surface}'
    foreground: '{colors.neutral-text}'
    border: '{colors.border-essential}'
---

# Construction Monitoring Rapid MVP - Design Spine

## Current workspace composition (2026-09-26)

The shared project list and project overview replace the historical stage-map entry below. Preserve Onest, the full-night plum/violet palette, semantic colors, focus rings, and existing evidence imagery. Use real project names and planned works, not placeholder stages or global summaries.

The header retains a labeled, keyboard-accessible project switcher and `Загрузить фото`; project navigation is `Обзор`, `Анализы`, `План работ`, `Сигналы`. On phones the switcher wraps without truncating controls and the four labeled destinations remain in bottom navigation. Root navigation leads to shared projects and the unassigned archive. Reports are discoverable through `О системе` only.

Upload foregrounds photographs, selected area, and capture times. Optional plan comparison and the legacy demonstration rule do not compete with the default observation path. Result layout separates equipment, model hypothesis, attention/basis, planned stage, and human confirmation. Profile/identity/revision/JSON details remain readable inside disclosures. Unknown project, no plan, empty history, loading, failed reads with retry, dirty draft confirmation, and revision conflict all use existing notice semantics.

## Brand & Style

The visual system is a serious operating surface with a clear hackathon identity. It uses the deep plum environment and violet interaction accent derived from the supplied [hackathon task-page reference](imports/hackathon-task-page-reference.png), then reserves independent semantic colors for evidence outcomes. The product should feel focused, transparent, and technically credible, not theatrical or punitive.

The exact user-facing product name is `Контроль строительства`. `17 мгновений ИИ` is the team attribution, not an alternate product title. Both strings remain unchanged across laptop, phone, mockups, presentation screenshots, and implementation.

The chosen composition combines the stage-oriented overview from [Direction C](.working/directions-entry-surface.html) with the causal analysis route from Direction B in the same artifact. The selected full-night treatment is recorded in [the hackathon theme comparison](.working/hackathon-theme-options.html). Earlier light themes in [.working/color-themes-entry.html](.working/color-themes-entry.html) are superseded.

Historically, the full-color [17 мгновений ИИ logo](imports/team-17-mgnoveniy-ii-logo.png) appeared only in spacious attribution areas on the Stages Overview and About Project surfaces, with text-only compact headers. The 2026-09-26 public-support extension below explicitly supersedes that placement restriction with the complete header mark and retained text attribution. The logo remains team attribution, never a status mark; do not crop, recolor, or reconstruct it.

The interface inherits Radix Themes component structure, keyboard behavior, and baseline accessibility. This file defines the full-night brand layer and product-specific evidence components. It does not restyle every Radix primitive.

## Colors

The theme is dark-only for the Rapid MVP. Do not invert individual sections into light mode.

- **Canvas (`#211331`)** is the continuous application background and top-bar field.
- **Surface (`#2B1A3D`)** contains major work areas. **Raised surface (`#38264A`)** separates tiles, drawers, and nested evidence without relying on shadows.
- **Primary text (`#F7F4F9`)** and **secondary text (`#C9BDD1`)** achieve at least WCAG AA contrast on canvas and primary surfaces. Use disabled text only for genuinely unavailable controls, never for explanatory copy.
- **Subtle border (`#5B456E`)** separates non-essential rows and tonal regions. **Essential border (`#8F78A0`)** identifies inputs, actionable panels, evidence frames, and other load-bearing boundaries; it measures at least 3:1 against canvas, surface, raised, and selected surfaces.
- **Brand violet (`#B984E0`)** means navigation selection, focus, and primary action. It never means risk, completion, model confidence, or equipment presence.
- **Attention amber** means `Требуется проверка` and no stronger claim. **Success green** means a completed technical step or `Проверка не требуется`. **Insufficient blue** means `Недостаточно данных`. **Error red** is reserved for technical failure. Neutral plum covers `Анализов нет`, `Не анализировалось`, and `Не настроено в прототипе`.
- Status meaning is always repeated in text and, where helpful, an icon or shape. Never depend on hue alone.

Contrast targets: body text and control labels meet 4.5:1; large text and essential non-text boundaries meet 3:1; focus indication meets WCAG 2.2 focus appearance requirements. The defined primary pairs exceed 5.6:1, semantic text-on-surface pairs exceed 7.8:1, and `{colors.border-essential}` reaches at least 3:1 against every declared adjacent surface. `{colors.border}` is decorative only and may disappear without obscuring a control or state. Test over real evidence images separately; text never sits directly on a photograph without an opaque scrim.

## Typography

Onest is the only product typeface. The fallback stack is `system-ui`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, and `sans-serif`. There is no decorative or monospace family in the MVP.

Use the 40px display size for desktop page titles and the main result, reducing it to 28px on phones. Block headings use 22px; body text uses 16px and captions remain at least 14px. Russian status phrases remain sentence case. Avoid all-caps labels and wide tracking; the information hierarchy comes from size, weight, grouping, and position.

Do not encode technicality with tiny type. Evidence provenance, uncertainty, timestamps, and policy revision remain at least 13px on laptop and 14px on phone. User zoom to 200% must not cause clipped controls or hidden content.

## Layout & Spacing

The base rhythm is 4px, with 16px mobile page margins, 24px tablet margins, and 32px laptop margins. Content is centered in a container with a maximum width of 1440px. New Analysis uses a one-third context column and a wider image column from 1024px; the columns stack below that width. Signals uses a list/detail split on desktop and expands the selected detail immediately after its row on phones.

The stage overview uses a wide stage map plus a narrower inspector on laptop. The inspector becomes a full-width continuation after the selected stage on phone. The analysis surface uses a six-step horizontal route at 1024px and above; it becomes a numbered vertical list on narrower screens. Evidence images use a responsive thumbnail grid and open into one image viewer, never into nested dialogs.

Composition references: [Stages Overview](mockups/key-stages-overview.html), [New Analysis](mockups/key-new-analysis.html), [Run Workspace](mockups/key-run-workspace.html), and [Prototype Readiness](mockups/key-readiness.html).

Spacing communicates hierarchy before cards do. Keep related label-value pairs within 4-8px, component internals at 12-16px, panel padding at 20-24px, and major surface gaps at 24-32px. Dense evidence metadata may use dividers, but not a separate card for every field.

## Elevation & Depth

Depth is primarily tonal: canvas, surface, raised surface, selected surface. Decorative separation uses `{colors.border}`; interactive and evidence-bearing boundaries use `{colors.border-essential}`. Shadows are reserved for transient layers such as a dialog, image viewer, or mobile sheet and remain plum-tinted and low-opacity. Persistent stage tiles, pipeline steps, and result panels do not float.

Evidence imagery is visually foregrounded with a neutral matte and a 1px boundary. Never dim an image to make the night theme feel more consistent. Bounding regions, when supplied by evidence, must remain legible over both bright and dark areas without implying unavailable precision.

## Shapes

The system uses a consistent practical radius scale: 6px for compact status labels, 8px for buttons, inputs, thumbnails, and pipeline steps, 12px for persistent panels and stage tiles, and 16px only for dialogs or large mobile sheets. Full pills are limited to compact binary controls when Radix requires them; status labels are not pills.

The logo remains irregular artwork inside a rectangular clear-space box. Do not place it in a circle, badge, or decorative glow.

## Components

- **Application Shell:** Full-night `{colors.canvas}` field. The top bar contains `Этапы`, `Анализы`, `План`, `Сигналы`, the persistent `Новый анализ` action, and a keyboard-accessible `Ещё` menu for `Готовность`, `Сравнение провайдеров`, and `О проекте`. Phone uses a compact header and labeled four-destination bottom navigation.
- **Team Brand Block:** Spacious attribution block on Stages Overview and About Project. Uses the unedited full logo with its exact text name; compact contexts fall back to text only.
- **Stage Tile:** Title, one Russian status, and the latest completed-analysis context when present. Selection uses `{colors.surface-selected}` plus a `{colors.brand}` border. A status cannot be inferred from selection styling.
- **Stage Inspector:** Summarizes the selected stage, latest outcome, affected area and period, and routes to evidence or a new analysis. It never displays schedule completion or a plan-health percentage.
- **Primary Button:** `{colors.brand}` with `{colors.on-brand}`. One primary action per decision area. Active press changes position or tone subtly; there is no glow.
- **Secondary Button:** `{colors.surface-raised}` with `{colors.text-primary}` and a `{colors.border-essential}` boundary. It supports editing, examples, cancellation, and secondary navigation.
- **Status Label:** Compact rectangular label using one semantic pair from `{components.status-label}`. Include the complete Russian phrase. Icons are supplemental and must have an accessible name or be hidden as decorative.
- **Analysis Context:** Persistent labeled fields for intent, stage, area, and period, plus optional project, zone, and saved plan revision. Each frame in a plan-bound analysis retains its capture time. The rule name, revision, expectation, and provenance are visible when rule evaluation is selected.
- **Analysis Intent Selector:** Two-option segmented choice with selected background and border; it is never a toggle whose meaning depends on position alone.
- **Image Uploader:** Bounded drop/select region on laptop and phone; dropped files use the same JPEG/PNG, 16 MB, 40-million-pixel, and eight-frame checks as picked files. Camera capture remains a separate available action. Examples are closed by default in a disclosure.
- **Input Manifest:** Ordered image rows with local object-URL preview, `Кадр N`, filename, size, optional capture time, and explicit reorder/remove/restore controls. Preview URLs are released when rows leave the screen.
- **Pipeline Route:** Six ordered steps with label, lifecycle state, factual summary, and optional timestamp. Completed uses success styling, active uses brand plus motion-independent emphasis, pending is neutral, failed is error, and skipped remains neutral with its reason visible. No client-generated percentages.
- **Observation Row:** Equipment class, translated observation state, evaluated input reference, and a disclosure for evidence. Do not show object counts as portable facts.
- **Series Evidence:** Separate aggregation block after per-frame Observation Rows. Shows usable-frame count, same-area confirmation, upload order, persistence statement, and exact supporting frame references without inventing a series-level absence observation.
- **Result Summary:** One outcome block using backend-derived wording and the corresponding semantic pair, presented before completed-run processing detail. The selected source frame is large, with a thumbnail strip and a neighboring `Основание вывода` column. On phones the order is outcome, basis, image, technical details. Supporting frames are marked only from saved result references.
- **Check-request Panel:** Attention surface with outcome, plain-language reason, recommended human check, area, period, rule revision, provenance, uncertainty, and the statement `Это рекомендация для проверки, а не подтверждение нарушения.`
- **Evidence Thumbnail:** Fixed aspect-ratio preview with ordinal `Кадр 1`, `Кадр 2`, and so on outside the image. Preserve source-image colors; no decorative filters. The viewer supports zoom and previous/next controls.
- **Evidence Viewer:** High-contrast image stage on `{colors.canvas}` with restrained chrome, source metadata, optional supplied evidence geometry, and persistent zoom/reset/close/previous/next controls. Provider-native detail visibly attributes provider/adapter, execution-profile revision, invocation, exact source frames, preprocessing revision when applicable, and artifact identity/checksum.
- **Input Field:** Radix Themes field with persistent label above, helper text below, contextual inline error, and `{colors.border-essential}` for its load-bearing boundary. Placeholder is never the only label.
- **Run Row:** Compact history row separated by `{colors.border}`. Lifecycle and outcome are different labeled fields, never one overloaded badge.
- **Readiness Criterion:** Plain row with criterion name, `Пройдено`, `Не пройдено`, or `Нет данных`, and a link to its evidence. Evaluation-set size/identity, checksums, manual-label coverage, fixture sufficiency, error counts, stability, and comprehension remain literal values from the report and never become ornamental scores.
- **Provider Comparison:** Secondary evidence panel with the same surface grammar as readiness but a separate heading and no shared overall score.
- **Signal List and Detail:** Filterable rows use the saved signal type, current zone name, date, human state, and available source preview. The detail retains the stored basis, saved plan revision, linked run, and per-signal comment draft. Amber describes a recommendation; closing a signal only completes manual handling.
- **Bottom Navigation:** Phone-only labeled navigation on `{colors.surface}` for `Этапы`, `Анализы`, `План`, and `Сигналы`. Selected state uses `{colors.brand}`, weight, and shape; text remains visible.
- **Inline Notice:** Contextual message adjacent to the affected form or run state. Attention, error, and reconnect variants use semantic text/surface pairs and never rely on a toast for required action.

State and overlay references: [Recovery States](mockups/key-recovery-states.html) and [Evidence Viewer](mockups/key-evidence-viewer.html).

## Do's and Don'ts

| Do | Don't |
|---|---|
| Keep the whole product in one full-night plum theme | Insert white cards or a light analysis page inside the dark shell |
| Use violet for brand, navigation, and actions | Use violet for warnings, confidence, or completion |
| Write every state in Russian and pair color with text | Use color-only dots, English status codes, or unexplained icons |
| Let real source images and evidence carry visual weight | Add gradients, glows, stock construction imagery, or fake detections |
| Use one 6/8/12/16 radius rule | Mix pill buttons, sharp tables, and oversized rounded cards |
| Keep the full team mark legible in attribution areas | Crop, recolor, animate, or use the logo as a loading indicator |
| Show measured backend stage state and factual summaries | Animate invented percentages or present recorded progress as live |
| Keep technical detail available through disclosure | Put policy snapshots, provider payloads, and checksums in the primary reading path |

## Public support and private owner surface (2026-09-26)

This extension supersedes the earlier compact-logo exclusion: reuse the complete unedited `team-logo.png` in the header with clear space and in favicon/apple-touch links. The project selector keeps accessible `Выбрать проект` without a redundant visible `Проект` label. Persistent text support actions remain visible below the header on narrow screens.

The introduction uses a five-step anchored tooltip with a spotlight around the exact real control and a dimmed remainder. It follows scroll and responsive geometry, stays inside the viewport without covering its target, and supports Back/Next/Skip, Escape and focus restoration. The highlighted control remains usable. Phones use a compact tooltip above or below the target. Missing project-specific controls produce explicit prerequisite guidance pointing to the actual project control. Feedback uses a separate native dialog, labeled fields, local image previews/removal, visible optional context, durable pending/error states and the exact success copy. Keep Onest, plum surfaces and existing violet/semantic tokens. The private admin has two tabs, eight requested statistic cards, labeled daily charts with visible numeric values, project rows and a feedback list/detail view. Mobile stacks charts and detail; cards use two columns. No public admin link is rendered.

The hands-on branch shows `Попробовать на примере`, its separate-project effect and any prerequisite/error inline. It stages a verified educational photograph without automatic inference, then spotlights the real submit control and persisted result. Existing working drafts are protected.

The tour extends the existing transient-layer vocabulary: a surface tooltip with an essential boundary, a focus-colored spotlight and a dark scrim around the usable target. It does not replace the page with a centered wizard. Feedback alone uses the native modal treatment, becoming a full-viewport form at 700px and below. Keep these surface-specific layouts separate; neither introduces a new palette or global type/radius scale. The password-change form sits in a disclosure on the private owner surface and uses the existing labeled-field and inline-error patterns.

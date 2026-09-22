# Validation Report - Construction Monitoring Rapid MVP

- **DESIGN.md:** `DESIGN.md`
- **EXPERIENCE.md:** `EXPERIENCE.md`
- **Run at:** 2026-09-21T16:46:36Z

## Overall verdict

The spine pair entered review as an adequate, disciplined draft with strong visual-reference coverage, resolved token references, paired component rules, and named flows for CAP-1 through CAP-6. Review initially found one critical, nine deduplicated high, fourteen medium, and three low contract gaps.

All original reviewer findings were repaired and independently rechecked: rubric 6/6 resolved, accessibility 12/12 resolved, and evidence safety 10/10 resolved, with zero partial or unresolved items. This validates the document contract only; runtime accessibility, rendering, frontend/backend mapping, and artifact integrity still require implementation evidence.

## Post-fix verification

- Rubric findings: 6 resolved, 0 partial, 0 unresolved.
- Accessibility findings: 12 resolved, 0 partial, 0 unresolved.
- Evidence-safety findings: 10 resolved, 0 partial, 0 unresolved.
- The detailed findings below are retained as the review and repair history.

## Category verdicts

- Flow coverage - adequate
- Token completeness - adequate
- Component coverage - adequate
- State coverage - thin
- Visual reference coverage - strong
- Bloat & overspecification - strong
- Inheritance discipline - thin
- Shape fit - adequate

## Findings by severity

### Critical (1)

**[Evidence safety] - Observation-only failure path violates authoritative outcome precedence** (`EXPERIENCE.md`, Flow 2)

An unassessable frame in `Только распознать технику` must keep top-level outcome `observations_only`; `insufficient_data` belongs to the affected class observation. Otherwise the UI falsely implies rule evaluation.

Fix: keep Result Summary as `Только наблюдения`, show class-level `Недостаточно данных`, evaluated-frame reference, and explicit `Правило этапа не проверялось`.

### High (9)

**[Token completeness / Accessibility] - Essential borders fail 3:1 non-text contrast** (`DESIGN.md`, colors and component boundaries)

The shared border is 1.63-2.10:1 against adjacent surfaces.

Fix: split subtle separators from an essential boundary token that reaches 3:1 on every adjacent surface.

**[State coverage] - Live-demo surfaces lack bounded loading and recovery states** (`EXPERIENCE.md`, State Patterns)

New Analysis, History, Readiness, Evidence Viewer, and About Project do not fully define permission, submission, fetch, artifact, or integrity failures.

Fix: add per-surface loading, failure, fallback, preservation, and retry behavior with Russian copy.

**[Inheritance discipline] - CAP identifiers collide between sources** (`EXPERIENCE.md`, Key Flows)

The technical-assignment digest and canonical SPEC reuse CAP-1 through CAP-5 for different meanings.

Fix: state source precedence and map `TA-CAP-*` requirements to canonical `CAP-*` capabilities.

**[Accessibility] - Asynchronous completion steals focus** (`EXPERIENCE.md`, succeeded run state)

Polling completion must not move focus while a person is reading.

Fix: announce completion once and expose `Перейти к результату`; move focus only after a user-initiated navigation.

**[Accessibility] - SPA and Evidence Viewer focus contracts are incomplete** (`EXPERIENCE.md`, Foundation and Interaction Primitives)

Skip link, route title and heading focus, dialog naming, initial focus, trapped scope, inert background, and restoration are not fully specified.

Fix: add an explicit route-focus and named-modal contract.

**[Evidence safety] - Stages Overview cannot project every backend outcome** (`EXPERIENCE.md`, stage status mapping)

`observations_only` has no stage mapping, and a newer technical failure could be confused with the last evidence-backed stage outcome.

Fix: add `Только наблюдения`; derive tile outcome only from the latest succeeded result projection and display newer lifecycle separately.

**[Evidence safety] - Frame observations and series evidence can collapse into an unsafe absence claim** (`EXPERIENCE.md`, observations and evidence)

Fix: show per-frame four-state results separately from a series-evidence block with usable count, same-area confirmation, upload order, and exact frame references.

**[Evidence safety] - Provider-native evidence attribution is incomplete** (`DESIGN.md` and `EXPERIENCE.md`, evidence disclosure)

Fix: require Russian-labeled provider/adapter, execution-profile revision, invocation, exact source frames, preprocessing revision, and artifact identity/checksum; mark native counts/confidence/geometry as non-rule-driving.

**[Evidence safety] - Changed-profile technical retry loses lineage** (`EXPERIENCE.md`, retry behavior)

Fix: allow technical retry with the same or explicitly changed observer profile while always preserving `retry_of_run_id`; context or evidence changes remain a new analysis.

### Medium (14)

**[Flow coverage] - About Project has no journey landing.** Add a short step to the jury flow or remove it as a standalone destination.

**[Component coverage] - Component registries use inconsistent names.** Align frontmatter, DESIGN Components, and EXPERIENCE Component Patterns; move visual-only tokens out of the product-component registry.

**[Shape fit] - Inspiration & Anti-patterns is missing.** Preserve the retained and rejected behavior from the hackathon reference and reconciliation notes.

**[Accessibility] - Form errors lack complete assistive association.** Require `aria-invalid`, `aria-describedby`, a linked error summary after failed submit, and non-disruptive upload-error announcements.

**[Accessibility] - Reflow boundary is incomplete.** Require operation at 320 CSS px, text-spacing resilience, safe areas, and non-obscured focus around fixed navigation.

**[Accessibility] - Composite control semantics are not bound.** Define radio semantics for intent, exposed selection for stages, and `aria-current` for navigation.

**[Accessibility] - Async status ownership is fragmented.** Define one `aria-busy` owner and bounded polite/alert regions for upload, submit, reconnect, retry, and pipeline updates.

**[Accessibility] - Evidence Viewer zoom is not keyboard-complete.** Add named zoom/reset/frame controls, announcements, and textual region descriptions.

**[Accessibility] - One visible message contains unexplained English.** Replace `Rapid MVP` in user copy with `прототипе`.

**[Accessibility] - Image removal has no undo.** Make local removal reversible until submit with `Вернуть` and restored ordinal.

**[Evidence safety] - Pre-submit context omits rule identity and provenance.** Show applied rule name/revision and provenance before rule evaluation.

**[Evidence safety] - `not_analyzed` may hide the required class row.** Show the row, reason, scope explanation, and evaluated-input reference; suppress only observation/deviation claims.

**[Evidence safety] - Readiness omits required evidence dimensions.** Add evaluation-set size/identity, checksums, manual labels, fixture sufficiency, and comprehension outcome.

**[Evidence safety] - Exact Russian pipeline labels are not fixed.** Specify all six primary labels and keep backend keys in technical detail only.

### Low (3)

**[Accessibility] - Dense readiness evidence needs semantic tables.** Require captions, headers, summaries, and exposed expansion state.

**[Accessibility] - Document language is not explicit.** Require `lang="ru"` and isolated `lang="en"` only where pronunciation benefits.

**[Evidence safety] - Three-frame wording is fixture-specific.** Parameterize as `ни в одном из {N} пригодных кадров`, with backend-supplied persistence evidence.

## Reviewer files

- `review-rubric.md`
- `review-accessibility.md`
- `review-evidence-safety.md`

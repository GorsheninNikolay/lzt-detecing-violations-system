# Evidence-safety review

## Verdict

**Changes required before key-screen mockups.** The pair has a strong safety spine: it preserves the single-frame boundary, separates observations from the rule and recommendation, delegates outcome selection to the backend, exposes the check-request rationale, and rejects legal/contractual conclusions or automatic plan mutation. One direct outcome-precedence contradiction and four high-impact contract gaps remain. They are bounded copy/behavior-spec fixes rather than a change to the selected IA or visual direction.

## Strengths

- `EXPERIENCE.md:21-28` establishes the correct separation between source images, observations, rule/provenance, and a human recommendation.
- `EXPERIENCE.md:64-73`, `161-174`, and `DESIGN.md:286-288` use appropriately cautious Russian wording, preserve uncertainty, expose the reason and recommended check, and keep the non-violation statement visible.
- `EXPERIENCE.md:118-128` names all four observation states and keeps them separate from the five backend-derived run outcomes.
- `EXPERIENCE.md:138-140` and `234-246` correctly treat fewer than three usable same-area images as a successful `Недостаточно данных` rule-evaluation result rather than an upload error.
- `EXPERIENCE.md:151-158` preserves immutable history, uncertain-submit reconciliation, technical-failure evidence, and linked successor runs in the normal retry path.
- `EXPERIENCE.md:19`, `28`, `45-56`, and `127-128` explicitly prevent schedule-health inference, site-wide absence claims, legal/contractual verdicts, and automatic management action.
- `EXPERIENCE.md:100-101`, `144-146`, and `248-260` keep prototype readiness separate from provider comparison and disclose incomplete comparison cells instead of inventing a winner.

## Critical findings

### ES-01 — Observation-only failure path violates authoritative outcome precedence

- **Location:** `EXPERIENCE.md:219-232`, especially line 232; conflicts with `ARCHITECTURE-SPINE.md:199-203`.
- **Finding:** Flow 2 selects `Только распознать технику`, but its unassessable-image branch says the run “completes as `Недостаточно данных`.” Under AD-35, `observations_only` has precedence for observation intent. `insufficient_data` is an observation state inside that result, not the run outcome.
- **Risk:** The same run can acquire different top-level meanings in frontend and backend. History, stage tiles, screenshots, and jury explanations could falsely imply that the stage rule was evaluated.
- **Required fix:** Keep Result Summary as `Только наблюдения`; render `Недостаточно данных` for each affected requested class with the observer-inability reason and evaluated frame reference. State explicitly that the rule was not evaluated and no check request can be produced.

## High findings

### ES-02 — Stage Overview cannot faithfully project every backend outcome

- **Location:** `EXPERIENCE.md:36`, `45-55`, `83-84`; compare `EXPERIENCE.md:94`, `126` and `ARCHITECTURE-SPINE.md:199-203`.
- **Finding:** The stage-status table has no mapping for `observations_only`, although the overview claims to show the latest completed analysis outcome. “Latest completed” also does not say whether a terminal technical failure may replace the last successful result projection.
- **Risk:** An observation-only run may be mislabeled `Не анализировалось`, `Проверка не требуется`, or omitted; a failed run may erase the last evidence-backed stage outcome. Either result conflates lifecycle with domain outcome.
- **Required fix:** Define a one-to-one projection for all five outcome kinds, including `Только наблюдения`. Define the tile source as the latest **succeeded run with a succeeded result projection**. Show a newer queued/running/failed run as separate lifecycle context and never derive a stage outcome from it.

### ES-03 — Multi-frame rendering does not specify the required frame/series boundary

- **Location:** `EXPERIENCE.md:91-96`, `118-128`, `161-174`, `209-214`; compare `ARCHITECTURE-SPINE.md:133-143`.
- **Finding:** `Observation Row` is described as one class, one state, and plural evaluated-input references, but the UX does not specify how per-frame four-state results remain visible while series sufficiency and persistence are shown as separate aggregation evidence. The closed state `not_detected_in_frame` cannot safely become an unlabeled series-level “absence” state.
- **Risk:** Implementers can collapse three frame-scoped non-detections into one stronger class-level absence statement, obscuring which frames were usable and which observations qualified the check request.
- **Required fix:** Specify two layers: (1) per-frame, per-requested-class rows with exactly one of the four states and an exact frame reference; (2) a separate series-evidence block with usable-frame count, same-area confirmation, upload order, excavator-observed frame references, and “самосвал не обнаружен ни в одном из N пригодных кадров.” Never introduce a fifth observation state or a site-wide absence label.

### ES-04 — Provider-native evidence lacks mandatory attribution fields

- **Location:** `DESIGN.md:285`, `289`, `308`; `EXPERIENCE.md:93`, `96`, `170`; compare `ARCHITECTURE-SPINE.md:205-209`.
- **Finding:** The documents allow provider evidence and native detail behind disclosure but do not require the disclosure/viewer to identify the observer execution profile, invocation, exact source inputs, or native artifact identity. “Source metadata” and “technical revisions” are too broad to enforce AD-36.
- **Risk:** A box, confidence, native response, or rendered detection can be presented as if it came from another provider/profile/input, weakening reproducibility and comparison credibility.
- **Required fix:** For every displayed provider-native artifact, require Russian-labeled attribution for provider/adapter, model or execution-profile revision, observer invocation, exact source frame IDs, preprocessing revision where applicable, and artifact checksum/identity in technical detail. Keep counts, confidence, and geometry explicitly provider-native and non-rule-driving.

### ES-05 — Changed-profile technical retry loses required lineage

- **Location:** `EXPERIENCE.md:155-157`; compare `ARCHITECTURE-SPINE.md:121-131`.
- **Finding:** The UX says changing the provider profile starts a new analysis instead of a retry. AD-18 explicitly allows a failed run to be retried with the same **or another** observer profile, and that successor must remain linked.
- **Risk:** A failure followed by a provider change can disappear from predecessor/successor lineage, making the apparent successful result irreproducible and provider comparison misleading.
- **Required fix:** Permit the technical-failure retry action to keep or explicitly change the observer profile while always creating a linked successor (`retry_of_run_id`). Continue treating changed images, intent, area/period, rule, or policy as a distinct new analysis, not a retry.

## Medium findings

### ES-06 — Pre-submit context omits the applicable rule identity and provenance

- **Location:** `DESIGN.md:280`; `EXPERIENCE.md:37`, `88-89`, `206-210`; compare `ARCHITECTURE-SPINE.md:61-65`, `103-107`.
- **Finding:** The New Analysis summary exposes intent, stage, area, and period, but not the rule revision/provenance that rule evaluation will bind. The selected stage can therefore appear to imply an unstated rule.
- **Risk:** The user cannot verify the expectation being tested before submission, especially whether it is a demonstration rule, heuristic, project rule, or normative source.
- **Required fix:** For `Проверить правило этапа`, show the applied rule name/revision and provenance before submit, with the expectation readable on disclosure. If no applicable rule is configured, explain that the rule outcome will be `Не анализировалось` or direct the user to observation-only intent; do not silently choose a rule.

### ES-07 — `not_analyzed` wording can be read as hiding the required state row

- **Location:** `EXPERIENCE.md:93`, `120-126`; compare `prototype-scenarios.md:5-10` and `ARCHITECTURE-SPINE.md:133-137`.
- **Finding:** The component contract requires one closed state for every requested class, but the `not_analyzed` row says “Suppress observations,” which can be implemented as suppressing the entire row and its evaluated-input reference.
- **Risk:** Out-of-scope evidence becomes indistinguishable from a missing result, and the four-state completeness contract cannot be audited.
- **Required fix:** Say: show the `Не анализировалось` state row, reason, scope/rule explanation, and evaluated-input reference; suppress only detection/non-detection and deviation claims plus the check request.

### ES-08 — Readiness does not explicitly expose two required evidence dimensions

- **Location:** `DESIGN.md:292-293`; `EXPERIENCE.md:100-101`, `248-260`; compare `.memlog.md:33-34` and `ARCHITECTURE-SPINE.md:157-161`.
- **Finding:** The readiness flow names fixture coverage and error counts, but does not explicitly require showing that the evaluation set contains 10–15 checksummed, manually labeled images with test-specific sufficiency conditions, nor the warning-comprehension outcome.
- **Risk:** A generic criterion list could appear “ready” without exposing the labeled-set boundary or whether a reviewer understood the check request, both required by the canonical readiness report.
- **Required fix:** Add explicit rows/fields for evaluation-set size and identity, manual label coverage, test-specific sufficiency conditions, and check-request comprehension outcome. Keep each linked to its report/run evidence and separate from provider comparison.

### ES-09 — Exact Russian pipeline labels are underspecified

- **Location:** `EXPERIENCE.md:60`, `92`, `211`, `228`; `DESIGN.md:284`.
- **Finding:** The contract requires all primary labels in Russian but enumerates the six displayed stages only in English. No exact Russian display strings are fixed.
- **Risk:** An implementation can expose English stage names or inconsistent translations in the main jury path.
- **Required fix:** Define exact labels, for example: `Регистрация входных данных`, `Проверка пригодности кадров`, `Распознавание техники`, `Объединение наблюдений серии`, `Проверка правила`, `Формирование результата`. Keep stable backend keys only in technical disclosure.

## Low findings

### ES-10 — Three-frame example copy is safe only for the fixed fixture

- **Location:** `EXPERIENCE.md:66`, `209-214`; compare `ARCHITECTURE-SPINE.md:79-83`.
- **Finding:** The preferred sentence says “в трёх пригодных кадрах.” That is exact for the bundled three-frame fixture but not for an arbitrary sufficient run with more usable submitted images.
- **Risk:** Reusing the copy component for four or more frames understates which evidence was evaluated.
- **Required fix:** Mark the sentence as fixture-specific or parameterize it as `Самосвал не обнаружен ни в одном из {N} пригодных кадров.` The backend-provided persistence evidence must supply `N`; the client must not derive check eligibility.

## Scope-truth notes

- This review covers the two UX spines against the UX memlog, canonical `SPEC.md` and `prototype-scenarios.md`, architecture spine, and repository-root `spec.md`. It does not assess a rendered mockup, implementation, API schema, model output, or evaluation report.
- The pair correctly narrows the Rapid MVP to excavation-pit soil removal, excavator and dump truck observations, explicit area/period context, and human check requests. It does not claim dated schedule ingestion, current-stage inference, camera management, Gantt editing, project-health scoring, or automatic plan mutation.
- The words `Пройдено`, `Не пройдено`, and `Нет данных` describe criterion/report availability only. They must not be reused as equipment observations, run outcomes, provider-comparison winners, or proof of production readiness.
- Provider comparison can inform a later active-provider selection, but neither a winning provider nor a complete comparison substitutes for prototype readiness. The current pair preserves this boundary.
- Passing this document review would establish specification consistency only. It would not prove WCAG behavior, frontend/backend outcome mapping, immutable artifact attribution, retry linkage, or readiness evidence in the running product.

## Resolution verification

Verification is limited to ES-01 through ES-10 against the current `DESIGN.md` and `EXPERIENCE.md`.

| Finding | Status | Current evidence |
|---|---|---|
| ES-01 | **Resolved** | `EXPERIENCE.md:136-138` preserves `observations_only` as the top-level outcome when class observations are insufficient; `EXPERIENCE.md:262-275` now makes the Flow 2 failure path `Только наблюдения` with per-class `Недостаточно данных` and `Правило этапа не проверялось`. |
| ES-02 | **Resolved** | `EXPERIENCE.md:57-67` adds `Только наблюдения`, maps all five backend outcomes, and defines the tile source as the latest succeeded run with a succeeded Result Projection; `EXPERIENCE.md:94` renders newer lifecycle separately. |
| ES-03 | **Resolved** | `DESIGN.md:274-275` and `EXPERIENCE.md:104-105,196-201` require per-frame/per-class closed-state rows plus a separate backend-projected Series Evidence block with exact supporting frames and no series-level absence observation. |
| ES-04 | **Resolved** | `DESIGN.md:279` and `EXPERIENCE.md:109,203` require provider/adapter, execution-profile revision, observer invocation, exact source frames, preprocessing revision, and artifact identity/checksum; provider-native counts, confidence, and geometry are explicitly non-rule-driving. |
| ES-05 | **Resolved** | `EXPERIENCE.md:177` allows the observer execution profile to be retained or changed on a technical-failure retry while always preserving `retry_of_run_id`; other context changes remain distinct analyses. |
| ES-06 | **Partial** | `DESIGN.md:269`, `EXPERIENCE.md:99`, and `EXPERIENCE.md:248-252` now expose rule name/revision, expectation, and provenance before submission. `EXPERIENCE.md:148` explains a non-configured stage in the inspector, but the New Analysis contract still does not state whether `Проверить правило этапа` is unavailable for that stage or may be submitted to produce `Не анализировалось`; the no-applicable-rule form behavior remains ambiguous. |
| ES-07 | **Resolved** | `EXPERIENCE.md:104,137` keeps the `Не анализировалось` row, reason, scope/rule explanation, and evaluated-input reference visible while suppressing only unsupported claims and check requests. |
| ES-08 | **Resolved** | `DESIGN.md:282` and `EXPERIENCE.md:112,291-303` explicitly expose evaluation-set size/identity, checksums, manual-label coverage, test-specific sufficiency conditions, error/stability measures, and check-request comprehension, while keeping Provider Comparison separate. |
| ES-09 | **Resolved** | `EXPERIENCE.md:103` fixes exact Russian labels for all six pipeline stages and confines stable backend keys to technical disclosure. |
| ES-10 | **Resolved** | `EXPERIENCE.md:77,105,201` parameterizes the statement as `Самосвал не обнаружен ни в одном из <N> пригодных кадров`, sources it from backend persistence evidence, and forbids client-derived eligibility or a site-wide absence claim. |

**Counts:** 9 resolved, 1 partial, 0 unresolved.

### Final ES-06 check

**Resolved.** `EXPERIENCE.md:100` now defines the missing no-applicable-rule behavior: `Проверить правило этапа` is unavailable with the visible reason `Для этого этапа правило не настроено в прототипе`, `Только распознать технику` is selected, and the UI never silently chooses a rule. Together with the pre-submit rule identity and provenance in `DESIGN.md:269` and `EXPERIENCE.md:99,250`, this closes both branches of ES-06.

**Final counts:** 10 resolved, 0 partial, 0 unresolved.

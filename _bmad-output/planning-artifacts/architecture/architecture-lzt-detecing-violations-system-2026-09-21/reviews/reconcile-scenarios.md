# Reconciliation — Prototype Scenarios vs Architecture Spine

## Verdict

**Needs targeted amendments before finalization.** The spine is structurally aligned with the prototype scenarios: it preserves evidence, separates observations from recommendations, versions policies and rules, compares providers through distinct runs, and defers provider selection until comparative evidence exists. However, several scenario-level contracts are referenced only by capability name or generic typed artifacts. Independent builders could therefore implement incompatible result states, warning behavior, fixtures, or readiness evidence while still complying with the current spine.

No irreconcilable contradiction was found. The issues below can be resolved by strengthening domain and acceptance-boundary invariants without changing the selected Pipes and Filters paradigm or deployment shape.

## Findings

### F1 — High: the four result states are not bound as a closed domain contract

**Scenario evidence:** `prototype-scenarios.md:3-10,30-32,38` defines exactly `detected`, `not detected in frame`, `insufficient data`, and `not analyzed`, including distinct permitted consequences and a requirement that every requested-class result point to the evaluated input.

**Spine evidence:** AD-6 only requires a normalized per-class observation contract (`ARCHITECTURE-SPINE.md:80-84`); CAP-3 is mapped generically to domain result types, policy, and conventions (`:244-247`). AD-4 independently defines stage-health values `not_observed`, `insufficient_data`, `no_signal`, and `check_required` (`:68-72`).

**Risk:** Backend, frontend, and tests can each invent different mappings. In particular, `not_observed` may be confused with `not analyzed`, and `no_signal` with an in-frame non-detection. A series result may also incorrectly introduce a fifth observation state or promote repeated frame-level non-detection into a site-wide absence claim.

**Required amendment:** Bind a closed per-requested-class observation result contract with the four scenario states and their consequences. Explicitly separate three layers:

1. per-input/per-class observation state;
2. series sufficiency and persistence evidence;
3. derived rule outcome and stage-health projection.

Every observation result must reference its evaluated frame or series input. Stage-health labels must be declared projections, never aliases for observation states. Define that series aggregation retains the underlying frame states and produces sufficiency/persistence evidence; it does not invent a site-wide absence observation.

### F2 — High: excavation-rule behavior is underspecified at the decisive warning boundary

**Scenario evidence:** `prototype-scenarios.md:12-19` fixes the bounded rule: controlled-area excavation/haulage, excavator continuously expected, dump truck periodically expected, demonstration provenance by default, no warning from one frame, and a check request only after persistent dump-truck non-detection in a usable series. The warning remains separate from observations and must not be called a violation.

**Spine evidence:** AD-1 separates observed facts, policy evaluation, and recommendation (`ARCHITECTURE-SPINE.md:50-54`), while AD-12 stores expectation categories and provenance (`:116-120`). Neither binds the actual decision semantics, sufficiency guard, positive-path suppression, or prohibited conclusions.

**Risk:** Separately built rule evaluator and UI could warn on a single image, warn when evidence is insufficient, treat a periodically expected truck as continuously required, or render a check request as a detected violation. `not_informative` is stored but its required consequence—no observation or deviation claim—is not fixed.

**Required amendment:** Add an adopted rule-evaluation invariant (or extend AD-12) that binds:

- the seeded excavation rule and default provenance;
- single-frame output to observation states only, never a delay warning;
- warning eligibility to a usable/sufficient series plus policy-defined persistent dump-truck non-detection;
- excavator and dump-truck presence consistent with the rule to an explicit no-warning outcome;
- `insufficient data` and `not analyzed` to warning suppression;
- `not_informative` to no observation or deviation claim;
- the only negative outcome wording to a request to check a *possible* haulage delay, never a legal/contractual violation and never automatic management action.

### F3 — High: readiness evidence and the mandatory fixture matrix are not architectural commitments

**Scenario evidence:** `prototype-scenarios.md:28-39` requires a 10–15-image manually labelled evaluation set, documented test-specific sufficiency, positive and negative cases, at least one inadequate-evidence fixture, at least one out-of-scope fixture, recorded misses/false detections/repeated-run stability, and a record of whether a reviewer understood each warning.

**Spine evidence:** AD-8 versions quality thresholds (`ARCHITECTURE-SPINE.md:92-96`); CAP-5 and CAP-6 point broadly to demo seeds, runs, comparison, and artifacts (`:248-249`). The Deferred section requires threshold values before acceptance-criteria decomposition (`:253-256`). It does not require the fixture classes or the evidence records needed to establish readiness.

**Risk:** A build can claim readiness after a happy-path run or aggregate score, with no negative, insufficiency, out-of-scope, stability, or comprehension evidence. Misses and false detections could disappear into summary metrics.

**Required amendment:** Bind a versioned evaluation manifest or equivalent evidence aggregate that identifies the 10–15 labelled inputs, their manual labels, expected fixture role, and test-specific sufficiency conditions. Require recorded per-fixture outcomes for positive, negative, inadequate-evidence, and out-of-scope cases; raw miss/false-detection observations; repeated-run stability results; and reviewer-comprehension evidence. Keep concrete quality thresholds deferred until before acceptance-criteria decomposition, as the spine already does.

### F4 — Medium: warning/result projection does not guarantee all required explanation fields

**Scenario evidence:** `prototype-scenarios.md:25-26,35-36` requires every warning to expose supporting images/observations, observation period, rule, provenance, recommendation, and uncertainty, and requires evaluators to identify the reason and recommended check.

**Spine evidence:** AnalysisRun retains inputs, period, rules, policies, stage outputs, and final result (`ARCHITECTURE-SPINE.md:56-60`). AD-13 puts detailed observations and provenance behind an on-demand view (`:122-126`). Uncertainty and a stable warning-to-evidence explanation contract are not named.

**Risk:** The data may exist but the API/UI projection can omit uncertainty or the causal link between evidence and recommendation. A technically traceable result may still fail the jury-readiness criterion.

**Required amendment:** Define one explanation projection for a check request containing stable references to supporting observations/images, observation period, rule revision, provenance, recommendation text, uncertainty, and reason code/summary. It may remain behind “Show evidence,” but none of these fields may be absent for a warning.

### F5 — Medium: provider comparison is aligned, but selection and runtime choice remain ambiguous

**Scenario evidence:** `prototype-scenarios.md:41` says the execution approach is selected only after comparing one ready local detector and one cloud multimodal model on the same evaluation set, and that selection is not part of MVP readiness.

**Spine evidence:** AD-7 requires distinct runs over the same evaluation set and policy identities (`ARCHITECTURE-SPINE.md:86-90`); AD-18 fixes one provider per run and allows retry with another (`:152-156`); Deferred postpones active-provider selection until comparative evidence exists (`:255-256`). These are substantively consistent.

**Risk:** “Active provider selection” can be interpreted either as a deployment default selected by the team or as an end-user selector for each run. A builder could also make provider selection a readiness gate despite the scenario expressly excluding it, or choose a default before both adapters are demonstrably ready.

**Required amendment:** Clarify that prototype readiness is provider-neutral and assessed from the required scenario fixtures; comparative evaluation is a separate evidence product. Both candidate adapters must meet a stated “ready for comparison” precondition before comparison. The post-comparison decision chooses the submitted/default execution approach, while per-run provider identity remains immutable. Explicitly decide whether the jury UI exposes provider choice or uses the selected default; do not let retry semantics decide this accidentally.

## Cross-check of aligned decisions

| Scenario concern | Spine coverage | Assessment |
| --- | --- | --- |
| Observations, warning, and recommendation remain separate | AD-1, AD-2 | Aligned, but exact rule semantics need F2. |
| Configurable series, usability, and quality thresholds | AD-8; Deferred | Aligned; values correctly remain open until before acceptance-criteria decomposition. |
| Same evaluation set for local/cloud comparison | AD-7 | Aligned. |
| No provider fusion or hidden fallback | AD-7, AD-18 | Aligned. |
| Evidence remains inspectable in the jury UI | AD-2, AD-10, AD-11, AD-13 | Aligned structurally; explanation fields need F4. |
| Positive and negative demonstration | CAP-5 map | Intent is present, but fixtures and pass conditions need F3. |
| Inadequate and out-of-scope handling | AD-8, AD-11 | Mechanisms exist, but result consequences and fixtures need F1–F3. |

## Recommended reconciliation order

1. Add the closed result-state/layering invariant (F1).
2. Bind the exact excavation rule and warning guardrails (F2).
3. Bind evaluation manifest and fixture evidence (F3).
4. Complete the explanation projection (F4).
5. Clarify default-provider versus per-run selection without making it an MVP-readiness gate (F5).

After these amendments, the scenario document can remain the source of concrete fixtures and acceptance detail while the spine carries only the cross-unit invariants needed to prevent incompatible implementations.

# SPEC reconciliation review

## Verdict

**Needs reconciliation before acceptance-criteria decomposition.** The spine preserves the core evidence-first direction and does not select a winning execution provider prematurely, but it leaves two behavior-defining SPEC invariants implicit. It also adds a material plan/UI/deployment scope that was accepted during architecture coaching but is not yet part of the canonical SPEC package.

## Findings

### 1. Critical — the exact four-state result contract is not an architecture invariant

The canonical companion requires every requested class result to use exactly one of `detected`, `not detected in frame`, `insufficient data`, or `not analyzed`, with the stated meanings and permitted consequences. The spine mentions normalized observations and maps CAP-3 to “domain result types,” but no AD fixes the exact states, their exclusivity, or the consequence boundaries. AD-4 introduces a different stage-health vocabulary (`not_observed`, `insufficient_data`, `no_signal`, `check_required`) without explicitly separating it from analysis results. AD-12 also uses `not_informative` as a rule expectation without binding its projection to `not analyzed`.

This permits independently built observer, rule, API, and UI units to choose incompatible meanings—for example, treating `no_signal` as equipment non-detection or omitting `not analyzed` entirely.

**Required reconciliation:** add an invariant binding observer output, result projection, API, and primary/secondary UI to the exact mutually exclusive result-state contract. State explicitly that stage health is a separate derived projection and cannot replace or reinterpret a class result; map an out-of-scope or non-informative request to `not analyzed` and prohibit a warning from both `insufficient data` and `not analyzed`.

### 2. Critical — warning eligibility is underspecified

The SPEC requires that one-frame absence never yield a site-wide absence claim or delay warning, and that the negative warning requires a usable same-area series with persistent dump-truck non-detection over a defined observation period. AD-1 separates observations, evaluation, and recommendation, while AD-8 versions thresholds, but neither constrains the rule evaluator to these eligibility conditions. AD-2 records area and period but does not require preservation of series order or define missing/inconsistent area-period evidence as insufficient.

An implementation could therefore comply structurally while issuing a warning from a single frame, an unordered collection, or mixed/undefined observation context.

**Required reconciliation:** bind series ordering, controlled-area identity, and observation period into the input contract; require rule evaluation to withhold the warning unless the series is usable and satisfies the versioned persistence/sufficiency policy. Explicitly forbid site-wide absence inference and any delay warning from a single image.

### 3. High — accepted plan, UI, access, and deployment scope is outside the canonical SPEC

AD-3 through AD-5 and AD-19 add a versioned construction-plan graph, planned intervals, dependencies, manually confirmed stage lifecycle, and derived stage health. AD-13 adds a jury-specific information architecture. AD-15 and AD-16 add a stable public HTTPS deployment and reusable shared access code. These are coherent, user-approved architecture decisions, but the canonical SPEC says the scenario and observation period are supplied explicitly and that deriving the current stage from a dated schedule is outside the prototype; it contains no plan-management, public-access, or shared-code capability.

The spine avoids the direct contradiction of calendar-derived factual progress because stage selection/state are explicit, but downstream stories derived from the current SPEC could legitimately omit these features, while stories derived from the spine would include them.

**Required reconciliation:** retain the existing Deferred item and update the SPEC package before generating final acceptance criteria. Clarify that the plan is a manually seeded demonstration context, not automated current-stage derivation, and add the public availability and summary-first jury flow as explicit bounded capabilities or constraints. If the SPEC is not updated, these ADs must be labeled optional/non-contractual rather than required MVP scope.

### 4. Medium — CAP-6 readiness evidence lacks an explicit owner and complete record

AD-7 provides same-evaluation-set provider comparison and AD-8 versions quality thresholds, but the spine does not assign ownership for the full readiness record required by the companion: 10–15 manually labeled images, test-specific sufficiency conditions, misses, false detections, repeated-run stability, pass/fail per readiness criterion, an inadequate-evidence fixture, an out-of-scope fixture, and whether a reviewer understood each warning and recommended check.

Without a defined evaluation artifact or harness boundary, separate units could record model metrics but omit scenario verdicts or human-understanding evidence.

**Required reconciliation:** name one versioned evaluation-manifest/report artifact as owner of labels, fixtures, policy snapshot, run links, per-criterion verdicts, error counts, stability observations, and warning-comprehension outcome. This can remain a repository/test artifact rather than a user-facing product feature.

### 5. Medium — provider comparison wording risks turning a prerequisite into runtime product scope

The SPEC keeps cloud, local, and hybrid execution undecided and says selection follows comparison of one ready local detector and one cloud multimodal model; that selection is not part of MVP readiness. AD-6 through AD-7 correctly preserve provider independence and distinct runs, but the diagrams and adapters can be read as requiring both providers in the deployed public product rather than only in the bounded evaluation setup.

**Required reconciliation:** state that the comparison harness must exercise both ready adapters on the shared evaluation set, while the public prototype may expose whichever ready adapter(s) are available without declaring the long-term execution approach. Keep the final provider selection deferred as already written.

## Preserved correctly

- Observations, explicit rules, provenance, and managerial recommendations remain separate.
- Historical evidence, rule revisions, policy revisions, provider identity, and artifacts are immutable and traceable.
- The architecture does not label results as legal/contractual violations or automate managerial action.
- Model fusion and silent fallback are excluded, preserving provenance and comparability.
- The three open quantitative questions are correctly represented as versioned policy parameters and deferred until before acceptance-criteria decomposition.


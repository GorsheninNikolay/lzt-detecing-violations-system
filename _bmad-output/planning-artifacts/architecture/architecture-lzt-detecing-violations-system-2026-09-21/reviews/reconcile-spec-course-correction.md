# SPEC Reconciliation Review — Course-Corrected Architecture Spine

**Reviewed:** 2026-09-22  
**Artifact:** `ARCHITECTURE-SPINE.md`  
**Canonical inputs:** `SPEC.md`, `prototype-scenarios.md`  
**Verdict:** **CONCERNS**

The course correction successfully removes the circular dependency between ordinary prototype execution and post-comparison provider selection. AD-34 now binds one immutable admitted candidate profile per run without publishing a winner; AD-7 and Deferred Decisions preserve local/cloud/hybrid neutrality; AD-18 keeps hybrid execution and fallback out of the delivered MVP. The four-state observation contract, immutable `PolicyProfile` snapshots, same-area ordered series, evaluation-set size, mandatory cases, zero-false-warning gate, and non-judicial wording also remain substantially aligned with the canonical inputs.

Three contract ambiguities remain. The first two can produce a result that violates the canonical scenario semantics and should be corrected before implementation readiness is declared. The third can reintroduce provider-selection drift despite AD-34.

## Findings

### F1 — HIGH: the dump-truck persistence predicate is logically ambiguous

**Canonical requirement**

- `prototype-scenarios.md:35,45` requires **no dump truck in all three usable images**, with an excavator observed somewhere in the series.
- `SPEC.md:32-33,57` permits the warning only for the qualifying negative series.

**Spine text**

- `ARCHITECTURE-SPINE.md:135` says “dump truck not detected in every usable image.” In ordinary English and formal logic, this can mean “not detected in at least one image,” which is weaker than “detected in none of the usable images.”

**Impact**

Two independently implemented rule evaluators could disagree. One could raise a haulage-delay check when a dump truck is present in one image but absent in another, creating a false warning forbidden by the readiness contract.

**Required correction**

Rewrite the predicate unambiguously, for example:

> A haulage-delay check requires at least three usable same-area images in explicit upload order, `excavator == detected` in at least one usable image, and `dump_truck == not_detected_in_frame` in every usable image.

Retain the existing suppression rules for `insufficient_data`, single-image results, and observer failure.

### F2 — MEDIUM: the warning/result contract does not explicitly carry all mandatory explanation fields

**Canonical requirement**

- `SPEC.md:28-30` requires every warning to expose supporting observations, expectation, rule provenance, observation period, and recommended check.
- `SPEC.md:55-57` and `prototype-scenarios.md:50-51` additionally require uncertainty and reviewer comprehension.

**Spine text**

- AD-2 (`ARCHITECTURE-SPINE.md:47-51`) binds the period to the run.
- AD-12 (`ARCHITECTURE-SPINE.md:95-99`) binds expectation to the rule revision.
- AD-21 (`ARCHITECTURE-SPINE.md:131-135`) says the check exposes evidence, rule, provenance, uncertainty, and recommended review, but omits the observation period and the expectation.
- AD-35 (`ARCHITECTURE-SPINE.md:191-195`) says `ResultProjection` carries class states/evidence and zero or one check request, but does not require the omitted fields to be carried or referenced by that check request.

**Impact**

The data exists elsewhere, but the API/result/UI units can independently build a formally compliant `ResultProjection` that does not expose the period or expected equipment behavior with the warning. That fails CAP-4 at the consumer boundary.

**Required correction**

Make the check-request contract explicitly carry immutable references or rendered values for:

- supporting observations;
- observation period;
- applicable expectation;
- rule revision and provenance;
- uncertainty/reason;
- recommended human check.

The projection may reference run/rule artifacts rather than duplicate them, but consumers must not have to infer these fields from provider-native data.

### F3 — MEDIUM: “primary” labels undermine the newly restored provider neutrality

**Canonical requirement**

- `SPEC.md:46,53` keeps local, cloud, and hybrid execution undecided and excludes selection from the spec.
- `prototype-scenarios.md:57` permits selection only after comparing a ready local detector and one cloud model on the same evaluation set; selection is not part of MVP readiness.

**Spine text**

- AD-34 (`ARCHITECTURE-SPINE.md:185-189`) correctly says a configured prototype binding is not a winner and defers active selection.
- AD-37 (`ARCHITECTURE-SPINE.md:203-207`) nevertheless calls Grounding DINO “Local MVP primary” and GigaChat “Cloud primary.”
- The Stack table repeats “Local primary” and “Cloud primary” (`ARCHITECTURE-SPINE.md:234,236`).

**Impact**

“Primary” is commonly interpreted as preferred/default/selected. A builder can reasonably treat these labels as an architectural selection, conflicting with AD-34 and with the canonical technology-neutral contract.

**Required correction**

Rename these labels without changing the candidate set, for example:

- `Required local comparison candidate` — Grounding DINO Tiny;
- `Required cloud comparison candidate` — GigaChat-2-Max;
- `Conditional local candidate` — RF-DETR;
- `Reserve cloud canary` — Kimi.

If one Grounding DINO profile is configured for interactive prototype runs, describe it only as the **configured prototype candidate**, not a primary or winner.

### F4 — LOW: “admission” has two owners unless its meaning is narrowed

**Canonical requirement**

- `SPEC.md:45` and `prototype-scenarios.md:28-38` assign `PolicyProfile` ownership specifically to frame usability, series sufficiency/persistence, and prototype-quality acceptance.

**Spine text**

- AD-8 (`ARCHITECTURE-SPINE.md:71-75`) says `PolicyProfile` alone owns “admission.”
- AD-30, AD-37, and AD-38 separately define observer-profile and provider admission (`ARCHITECTURE-SPINE.md:167-171,203-213`).

**Impact**

This is not currently a product contradiction, but the overloaded term can lead one unit to place provider/legal/runtime gates in `PolicyProfile` while another places them in `ObserverExecutionProfileRevision` admission evidence.

**Required correction**

Narrow AD-8 to “input/frame admission, usability, series sufficiency/persistence, and prototype-readiness gates,” and state that candidate/provider admission belongs to observer-profile audit evidence governed by AD-30/37/38.

## Confirmed Alignments

- **Prototype binding versus winner selection:** AD-34 now allows a run to use an explicitly configured admitted candidate without creating `ActiveObserverConfiguration` or claiming a winner.
- **No fallback:** AD-18 and AD-34 require a new linked run for a different profile and prohibit mid-run substitution.
- **Local/cloud/hybrid neutrality:** AD-7 retains the undecided outcome; executable hybrid behavior is deferred and rejected by the delivered executor.
- **Readiness evidence:** AD-8 and AD-24 retain the 10–15-image bounded evaluation, mandatory positive/negative/insufficient/out-of-scope cases, zero false warnings, literal error/timeout retention, and separate baseline metrics.
- **Four-state semantics:** AD-20 preserves exactly one normalized state per requested class with evaluated-input references and forbids site-wide absence inference.
- **Non-judicial outcome:** AD-21 keeps the result as a human check request and forbids violation verdicts or automated action.

## Gate Recommendation

Do not claim full SPEC reconciliation yet. Apply F1–F3 before the next sprint-readiness gate; F4 should be corrected in the same small edit because it is terminology-only and prevents ownership drift. No change to the canonical SPEC or `prototype-scenarios.md` is indicated.

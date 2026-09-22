# Reconciliation Review — Approved Sprint Change Proposal

**Reviewed artifact:** `ARCHITECTURE-SPINE.md`  
**Authority:** `sprint-change-proposal-2026-09-22.md`  
**Date:** 2026-09-22  
**Verdict:** FAIL — one approved constraint is not represented unambiguously

## Scope

This review checks only the architecture changes approved in the Sprint Change Proposal: AD-34, the observer diagram, Structural Seed wording, AD-37/local admission, active-provider and cross-hardware deferrals, hybrid scope, secrets, and the non-selecting comparison-report boundary. Story edits and coverage maps belong to `epics.md` and are outside this artifact review.

## Reconciliation Matrix

| Approved change | Evidence in updated spine | Result |
|---|---|---|
| Every MVP run binds one immutable admitted profile before execution | AD-34, lines 185–189 | PASS |
| Comparison profile comes from the immutable campaign cell | AD-34, line 189 | PASS |
| Prototype/demo profile is explicitly configured and remains a candidate, not a winner | AD-34, line 189 | PASS |
| Profile change creates a new run; no fallback | AD-34 and AD-18, lines 189 and 119–123 | PASS |
| `ProviderSelectionService` and `ActiveObserverConfiguration` are not delivered in MVP | AD-34 and Deferred Decisions, lines 189 and 282 | PASS |
| Diagram says bound local/cloud candidates, with hybrid shown as post-MVP | Diagram, lines 27–36 | PASS |
| Structural Seed uses `candidate binding` instead of `selection` | Structural Seed, lines 239–248 | PASS |
| Apple M3 Pro CPU-only is the mandatory initial ordinary-laptop baseline | AD-37, lines 203–207 | PASS |
| Complete offline evaluation-set smoke is required | AD-37, line 207 | PASS |
| Actual device, latency, memory, and errors are recorded literally | AD-37, line 207 | PASS |
| Initial profile has no arbitrary numeric performance gate | Deferred Decisions, line 283 | PASS |
| Timeouts derive from the first complete CPU smoke | AD-30 and AD-37, lines 167–171 and 207 | **FAIL** |
| MPS and RTX 3060 are separate optional profiles; CPU fallback cannot pass accelerator admission | AD-37, line 207 | PASS |
| RF-DETR is draft/non-blocking until a rights-clear corpus and split are approved | AD-37 and Deferred Decisions, lines 207 and 287 | PASS |
| Wider cross-hardware baseline is post-MVP | Deferred Decisions, line 284 | PASS |
| Executable/selected hybrid is post-MVP; data contract may still represent it | AD-18 and Deferred Decisions, lines 119–123 and 285 | PASS |
| Grounding DINO and admitted GigaChat are the required MVP candidate paths | AD-7, AD-37, and Stack, lines 65–69, 203–207, and 234–237 | PASS |
| Secrets stay in environment/secret store and out of persisted/displayed evidence | Consistency Conventions, line 221 | PASS |
| Comparison report does not derive or publish a winner | AD-24 and AD-34, lines 149–153 and 185–189 | PASS |

## Finding

### CC-1 — Timeout source still permits the optional MPS smoke instead of requiring the mandatory CPU smoke

**Severity:** Blocking for exact proposal reconciliation  
**Location:** `ARCHITECTURE-SPINE.md:171`, reinforced ambiguously by `:207`

The approved change makes Apple M3 Pro CPU-only the mandatory admission baseline and the accepted Story 3.2 wording freezes timeouts from the first complete **CPU** smoke. AD-30 still defines both timeouts from the first full `CPU/MPS` smoke. AD-37 then delegates to that formula without narrowing its source to CPU. A builder may therefore derive the timeout from the optional MPS profile, producing a different profile and leaving CPU admission without the agreed deterministic baseline.

**Required correction:** In AD-30, replace both occurrences of `first full CPU/MPS smoke` with `first full Apple M3 Pro CPU-only smoke` (or equivalently explicit CPU-only wording). Keep MPS and RTX 3060 as separate optional profiles with their own evidence; they must not set the initial mandatory profile's timeout.

## Unapproved-Scope Check

No material product-scope expansion was found. AD-34 adds implementation-level precision—application ownership, transactional persistence of the binding, validated runtime configuration, and exclusion of UI/adapter rebinding—but these clauses enforce the approved explicit immutable binding and no-fallback rule rather than adding a new capability. Existing Kimi, YOLO/Enterprise/AGPL, storage, and recovery decisions remain orthogonal pre-existing architecture constraints.

## Closeout

After CC-1 is corrected, the approved architecture portion of the Sprint Change Proposal will be fully represented and this reconciliation can pass. No other architecture correction is required by the proposal.

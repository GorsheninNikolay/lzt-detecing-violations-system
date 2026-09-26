---
id: SPEC-construction-monitoring-concepts
companions:
  - prototype-scenarios.md
  - EXPANSION.md
sources:
  - ../../forge/construction-monitoring-concepts/forged-idea.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Construction Monitoring Rapid MVP

The original Rapid MVP contract below remains the historical two-class baseline. `EXPANSION.md` defines the current shared project workspace, photo-first, optional plan, signal, visitor introduction, durable feedback and private owner-statistics scope; its additions do not retroactively change old profiles, runs, or evaluation campaigns.

## Why

Site managers need a faster way to focus their review of construction-site images on plausible process deviations. This MVP tests whether traceable equipment observations can support a useful check request for excavation-pit soil removal without overstating what an image proves or committing to an execution technology before evidence exists.

## Capabilities

- **CAP-1**
  - **intent:** Analyze one image of a controlled excavation area for excavator and dump-truck observations.
  - **success:** The result gives one defined observation state per requested class and ties it to the source image.
- **CAP-2**
  - **intent:** Analyze an ordered image series from one controlled area and observation period.
  - **success:** The result aggregates the image observations with their period and evidence, or reports that the series contains insufficient data for evaluation.
- **CAP-3**
  - **intent:** Express every requested analysis using the result-state model in `prototype-scenarios.md`.
  - **success:** The result uses exactly one applicable state with its defined meaning and never converts absence from a frame into absence from the site.
- **CAP-4**
  - **intent:** Evaluate observations against an explicit work rule while keeping the observation, rule, and recommended managerial check separate.
  - **success:** Any warning exposes the supporting observations, expectation, rule provenance, observation period, and recommended check.
- **CAP-5**
  - **intent:** Demonstrate the excavation-pit soil-removal rule through positive and negative cases.
  - **success:** Both cases produce the outcomes specified in `prototype-scenarios.md`, including a possible haulage-delay warning only for the qualifying negative series.
- **CAP-6**
  - **intent:** Produce evidence that the prototype is ready for a bounded demonstration.
  - **success:** A manually labeled 10–15-image evaluation records misses, false detections, repeat-result stability, and the pass or fail result of every readiness criterion in `prototype-scenarios.md`.

## Constraints

- The system must not determine a legal or contractual violation or take action for the manager.
- A single image may support only an in-frame observation, never a claim that equipment is absent from the whole site.
- A series-based warning requires images from the same controlled area over a defined observation period.
- The MVP covers only excavation-pit soil removal and the excavator and dump-truck classes; work not observable through these classes is not analyzed.
- Every rule identifies its provenance as a project document, normative or methodological source, expert heuristic, or demonstration rule; a heuristic must not appear as a normative requirement.
- Frame usability, series sufficiency, and prototype-quality acceptance are governed by an immutable `PolicyProfile` revision as defined in `prototype-scenarios.md`; every run records the revision and complete applied snapshot, and any value change creates a new revision.
- Cloud, local, and hybrid execution remain undecided until comparative evidence is available.

## Non-goals

- Legal or contractual violation verdicts and automated management action.
- Site-wide equipment-absence claims from one frame.
- Coverage of all eight equipment classes or exhaustive mapping of the work-type catalog.
- Selecting cloud, local, or hybrid execution as part of this spec.

## Success signal

In a bounded demonstration, a positive excavation series shows the expected excavator and dump truck without a haulage-delay warning, while a usable negative series with persistent dump-truck non-detection asks the manager to check a possible delay. Both outcomes expose their images, observation period, rule, provenance, and uncertainty, and all prototype-readiness checks pass.

## Assumptions

- The MVP receives the excavation-pit scenario and its observation period explicitly; deriving the current stage from a dated construction schedule is outside this prototype.

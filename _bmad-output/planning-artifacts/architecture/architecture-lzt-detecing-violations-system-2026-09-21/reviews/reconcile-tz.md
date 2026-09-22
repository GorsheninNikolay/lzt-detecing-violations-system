# Reconciliation: architecture spine vs. hackathon specification

## Verdict

**Needs amendment before finalization.** The spine is strong on traceability, reproducible runs, public access, a jury-friendly processing view, provider isolation, and a low-complexity MVP deployment. It does not yet cover one mandatory deviation mode from the source specification, and it leaves several submission and evaluation obligations silent. None of these require abandoning the accepted Pipes-and-Filters design; most are small additions to the architecture contract or explicit pre-submission handoffs.

Source reviewed: all 7 physical pages of `artifacts/spec.pdf` (cover plus numbered pages 1–6), extracted with `pdftotext -layout`. The comparison also considered the narrower scope stated by the linked canonical SPEC because that scope materially affects compliance with the source brief.

## Coverage summary

| Source obligation | Spine coverage | Assessment |
| --- | --- | --- |
| Detect and classify construction equipment | AD-1, AD-6, AD-7, AD-18 | **Partial.** Provider-independent observations are sound, but no canonical, extensible equipment taxonomy or adapter-label mapping is fixed. The linked SPEC intentionally limits implementation to excavators and dump trucks. |
| Relate observations to construction stages via explicit rules | AD-2, AD-3, AD-5, AD-12, AD-19 | **Covered for the bounded scenario.** Revisioned stages, rules, provenance, and run snapshots make the relation explicit and auditable. |
| Visualize mandatory functions | AD-11, AD-13 | **Covered.** The persisted stage projection avoids fake progress and the summary-first flow is appropriate for jury testing. |
| Detect missing required equipment | AD-8, AD-12 and result projection | **Covered for the excavation-series case**, assuming downstream result-state semantics remain aligned with the SPEC. |
| Detect equipment inconsistent with the current stage | AD-12 | **Not covered.** `continuous`, `periodic`, and `not_informative` cannot express “present but incompatible/unexpected”, and the canonical SPEC tells `not analyzed` fixtures to produce no warning. |
| Show affected zone and evidentiary image(s) | AD-2, AD-10, AD-13 | **Partial.** Images and an `observation area` are retained, but camera/zone identity, geometry or stable zone label, and rule/stage applicability to a zone are not structurally bound. |
| Run or demonstrate on standard computers/laptops; GPU optional | AD-14, structural seed | **Partial.** Single-host execution is defined, but there is no no-GPU baseline, standard-laptop runtime profile, resource ceiling, or verified latency target. |
| Docker-based reproducible startup is desirable | `deploy/` seed only | **Partial.** No explicit seed or handoff requires `Dockerfile`, `docker-compose.yml`, persistent mounts, configuration example, health check, or an installation smoke test. |
| Stable prototype link for jury verification | AD-15, AD-16 | **Covered well.** Stable HTTPS, persistent volumes, reusable access code, and evaluation-window availability meet the final-submission access requirement. |
| Presentation contents | None | **Missing as a handoff.** Architecture, technology/model rationale, end-to-end demo, image-to-schedule linkage, scaling path, and camera-placement recommendations must appear in `.pptx` or `.pdf`. |
| Accompanying documentation | None | **Missing as a handoff.** The required `.doc` or `.pdf` must cover data model, readable-code conventions, training data/model limits, supported equipment and stage scope, and reproducible build/install/run instructions. |
| Open repository plus prototype, presentation, and documentation links | AD-15 covers prototype only | **Partial.** Final-submission packaging and link verification are not represented. |
| Evaluation: modularity and extension to images/equipment/plans | AD-3, AD-6, AD-12, AD-19 | **Mostly covered.** Plan and provider boundaries are strong; image-source/media-decoding extension and taxonomy evolution are implicit rather than fixed. |
| Evaluation: recognition quality on diverse examples | AD-7, AD-8; CAP-6 mapping | **Partial.** The evaluation-set identity is mentioned, but its immutability, labels, provenance, train/evaluation separation, and coverage of lighting, seasonality, and equipment variation are not bound. |
| Evaluation: speed and warning latency | AD-11 timestamps | **Partial.** Timing can be derived, but no performance budget, measured metric, or target execution profile is required before submission. |
| Evaluation: explainable warnings and usability | AD-1, AD-2, AD-11, AD-13 | **Covered well.** Observation, rule, recommendation, evidence, and primary/secondary disclosure are separated. |

## Findings requiring spine changes

### F1 — High: mandatory “unexpected equipment” deviation has no rule semantics

The source brief explicitly requires anomalies including both absence of plan-required equipment **and appearance of equipment that does not correspond to the current stage** (numbered page 2). AD-12 only supports `continuous`, `periodic`, and `not_informative`. The latter intentionally carries no deviation claim in the linked SPEC, so it cannot safely double as “forbidden” or “unexpected”. Two independent implementers could therefore make incompatible decisions: warn for every unlisted class, ignore all unlisted classes, or treat `not_informative` as forbidden.

Add a durable distinction between:

- required/expected equipment (`continuous` or `periodic`);
- allowed but non-informative equipment;
- explicitly unexpected/incompatible equipment for a stage and area;
- unsupported or out-of-scope classes, which must not silently become anomalies.

Rule evaluation should emit typed deviation kinds such as `expected_equipment_not_observed` and `unexpected_equipment_observed`, each retaining observations, stage/rule revision, zone, uncertainty, and recommended human check. At least one end-to-end unexpected-equipment demonstration fixture is needed unless the organizers explicitly accept the narrower two-class absence-only interpretation.

### F2 — High: the two-class canonical scope creates a visible completeness risk

The linked SPEC says the MVP covers only excavators and dump trucks and makes coverage of all eight listed source-data classes a non-goal. The source brief asks for identification of the main types of construction equipment and later lists dump truck, excavator, roller, manipulator crane, concrete mixer, bulldozer, truck, and mobile crane as classes that may occur (numbered pages 2 and 4). It also scores recognition quality for the main classes and completeness of all section-2 functions (numbered pages 5–6).

The source does not unambiguously mandate all eight classes, so the narrow demo may remain defensible, but the architecture must prevent today’s two-class boundary from becoming a closed data model. Add a versioned canonical `EquipmentType` catalog with stable IDs, display labels, provider-specific label mappings, and explicit supported/unsupported capability per observer version. Record the declared supported-class set in every run. The final documentation and presentation must state the two-class prototype limitation plainly and show how additional classes are added without changing pipeline contracts.

### F3 — Medium: zone/camera context is too implicit for the required explanation

The source example expects a warning with the affected zone and supporting image(s) (numbered page 2). AD-2 mentions an observation area, but neither the ER seed nor invariants define stable zone/camera ownership or stage/rule applicability to a zone. A free-form string would be insufficient for cross-run comparison and UI filtering.

Add a minimal `ObservationArea` (stable ID and concise display label) and input-source/camera identity when known. A run binds one area; plan/rule applicability declares the relevant area or explicitly states project-wide applicability. The primary warning must show the human-readable zone; detailed evidence can retain camera/source and image metadata. Geometry, camera calibration, tracking, and a camera-management UI can remain deferred.

### F4 — Medium: standard-computer and performance envelopes are not acceptance-bound

The source requires demonstration on standard computers or laptops, with no mandatory GPU, and scores processing speed and warning latency (numbered pages 2 and 5). AD-14 constrains concurrency and storage ownership but not computational portability. A local detector that only works acceptably on a development GPU could satisfy the current spine while failing the source requirement.

Add a pre-acceptance runtime profile rather than a new infrastructure layer: identify the reference standard laptop/CPU/RAM, verify a no-required-GPU path (local CPU or the explicitly selected cloud adapter), set image-count/size bounds, and record end-to-end plus per-stage latency on positive and negative demo cases. Concrete latency thresholds may remain a configurable acceptance decision, but must be closed before final criteria and reported in the presentation. Cloud dependence, network dependence, and offline limitations must be explicit.

### F5 — Medium: evaluation evidence is not a first-class revisioned asset

The source supplies no hidden test set and requires the team to create diverse checks, preferably including lighting, seasonality, and equipment variation (numbered page 4). Recognition quality and stability on diverse examples are scored (numbered page 5). AD-7 references an evaluation-set identity, but no invariant says what that identity fixes.

Add an immutable `EvaluationSetRevision` or equivalent manifest binding image checksums, manual labels, area/scenario metadata, relevant diversity tags, provenance/licensing, and separation from any training or prompt-tuning material. Provider comparisons must cite the same revision and policy revision. This makes CAP-6 evidence reproducible and allows the final documentation to state the model’s data conditions and limitations truthfully.

## Required submission handoffs (do not need new domain abstractions)

These are source obligations rather than reasons to enlarge the runtime architecture. They should appear as explicit “before final submission” items, with owners and verified output paths/URLs:

1. **Presentation (`.pptx` or `.pdf`, numbered page 3):** concept and component interaction; technology and model rationale; complete demonstration from equipment recognition through analysis result; image-to-calendar-stage linkage; scaling/development path; camera-placement recommendations for reliable analytics.
2. **Accompanying documentation (`.doc` or `.pdf`, numbered page 3):** data model for equipment, stages, deviations, and violations/check requests; code structure and only necessary non-trivial comments; training/evaluation data and model limitations; supported equipment classes and configured work stage; step-by-step build, install, and run guide.
3. **Final package (numbered page 5):** publicly readable repository link; tested stable prototype link; presentation link; documentation link. Verify every link from a clean/incognito client and retain the reusable access code alongside the submitted prototype link.
4. **Reproducible deployment:** provide and smoke-test `Dockerfile` and `docker-compose.yml` (desirable per numbered page 3), with persistent structured/artifact mounts, runtime-secret injection, sample configuration, health endpoint, and no hidden local prerequisite.
5. **Pitch evidence (numbered page 6):** retain a rehearsed live path and a truthful recorded fallback showing the same real pipeline evidence. The recording must not be rendered as a live run, consistent with AD-18.

The camera-placement recommendation is mandatory presentation content even though it is not runtime functionality. It should cover viewpoint/occlusion, field of view and relevant work zone, mounting stability, lighting/weather/night conditions, cadence, image resolution, and the boundary between “not detected” and “insufficient data”.

## Scoring-oriented acceptance additions

Before story acceptance criteria are finalized, convert these scoring concerns into measured evidence rather than prose claims:

- recognition results by supported class, with misses and false detections visible;
- positive, missing-required-equipment, unexpected-equipment, insufficient-data, and out-of-scope cases;
- end-to-end and per-stage latency on the declared standard-computer/network profile;
- one clean-start installation and one deployed-link smoke test;
- a reviewer comprehension check for warning reason, affected zone, evidence, uncertainty, and recommended action;
- proof that a new provider, equipment type, and plan revision can be added through the declared boundaries without changing domain consumers.

## What already aligns particularly well

- AD-1/2/10/11 create an unusually strong evidence chain for the source’s demand for explainable warnings.
- AD-3/5/12/19 make image-to-stage linkage explicit and auditable rather than presentation-only.
- AD-13 directly serves the usability scoring criterion and protects the jury path from technical clutter.
- AD-15/16 correctly distinguish a durable, testable prototype link from a laptop demo or video.
- AD-6/7/18 preserve provider attribution and make technology/model justification evidence-based.

## Recommended disposition

Amend the spine for F1–F5, add the submission handoffs to Deferred with concrete revisit conditions, then reconcile the source SPEC: its current absence-only, two-class contract is narrower than the source brief’s explicit unexpected-equipment function. The accepted MVP shape can remain small—one excavation stage, a compact plan, two fully demonstrated classes—provided the architecture contract is extensible, the limitation is disclosed, and the mandatory unexpected-equipment path is either implemented or formally resolved with the organizers before final acceptance criteria are frozen.

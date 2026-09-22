# Research Brief: AI Candidates for Construction Monitoring Rapid MVP

## Decision

Select one primary and one reserve local detector candidate, and one primary and one reserve cloud multimodal candidate, for a controlled comparison. Documentation and external benchmarks may qualify candidates but must not select the final local, cloud, or hybrid winner.

## Binding project requirements

- Structured state uses PostgreSQL. SQLite is prohibited as a fallback or second runtime database. SQLAlchemy may remain.
- Images and large artifacts remain outside PostgreSQL unless new evidence or a later architecture decision proves otherwise.
- Do not add pgvector; the MVP has no substantiated vector-search task.
- The prototype must run or be demonstrable on an ordinary laptop. A GPU is optional.
- A Windows computer with an RTX 3060 is available as an optional CUDA benchmark and demo path. It does not replace the mandatory ordinary-laptop CPU admission check.
- The MVP recognizes excavator and dump truck.
- Single-image and ordered-series analysis use the closed four-state contract: `detected`, `not_detected_in_frame`, `insufficient_data`, and `not_analyzed`.
- Rule evaluation does not consume provider-native counts, confidence, or geometry.
- Local, cloud, and hybrid remain undecided until the shared experiment is complete.

## Requirements frame

Hard gates:

1. A currently available, concretely identifiable model/version and supported installation or API path.
2. A credible path to both required classes, with fine-tuning requirements stated rather than assumed.
3. Local candidates run on CPU on an ordinary laptop; Apple Silicon and RTX 3060 CUDA are additional measured modes.
4. Candidate output can be normalized without expanding the four-state contract or making provider-native fields rule-driving.
5. Installation/runtime dependencies can be committed to lockfiles and exercised by one end-to-end fixture.
6. Failures, refusals, errors, and timeouts remain in the experiment denominator.
7. License, service terms, privacy/retention, network dependency, and revision-pinning limitations are explicit.

Weighted shortlist criteria:

| Criterion | Weight |
|---|---:|
| Required-class and four-state contract fit | 25% |
| Reproducible laptop runtime and installation | 20% |
| Demo reliability, availability, and revision pinning | 20% |
| Evidence regions and structured output | 15% |
| Privacy and retention | 10% |
| Latency and cost | 10% |

## Research plan

1. Screen local detector candidates using current official model cards, repositories, releases, licenses, runtime documentation, and original papers.
2. Screen cloud multimodal candidates using current official model catalogs, API documentation, structured-output/image-input documentation, pricing, data-use/retention terms, availability, and versioning guarantees.
3. Reconcile runtime, reproducibility, privacy, cost, and live-demo risks; define exact `ObserverExecutionProfileRevision` fields, admission smokes, and the shared experiment.
4. Apply high validation to decisive version, compatibility, privacy, pricing, and performance claims.

## Required deliverable

An English decision-grade `research.md` containing a decision matrix, candidate profiles, exact execution-profile fields, minimal installation and end-to-end smoke commands, candidate-admission criteria, the 10-15-image comparison plan, live-demo risks, and questions requiring a user decision. Verified facts must be separated from assumptions.

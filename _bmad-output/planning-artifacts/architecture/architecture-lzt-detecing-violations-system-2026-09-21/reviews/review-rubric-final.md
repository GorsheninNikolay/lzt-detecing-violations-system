# Good-Spine Rubric Re-review

## Gate verdict

**REVISE — the update closes most prior findings, but two remaining contradictions can still produce incompatible pipeline and overview behavior.** No critical finding remains. The deterministic linter passes with zero findings, source coverage is complete, the operational envelope is proportionate, and the structural seed remains disciplined.

## Prior-finding disposition

| Prior finding | Status | Evidence |
| --- | --- | --- |
| H1 pipeline transitions | **PARTIAL** | AD-26 now defines atomic monotonic transitions and failure propagation, but AD-1 and AD-2 still make incompatible unconditional claims; see F1. |
| H2 stage-health derivation | **PARTIAL** | AD-27 makes the backend authoritative and defines ordering, but the eligible run set still lets observation-only runs replace rule-evaluation health; see F2. |
| H3 `continuous` semantics | **CLOSED** | AD-21 now explicitly withholds check requests until a future versioned policy supplies an evidence threshold. |
| M1 one-writer diagram | **CLOSED** | The deployment diagram now places API, executor, and persistence adapters inside one application-process boundary. |
| M2 area cardinality | **CLOSED** | `APPLICABILITY_SCOPE` can exist without an `OBSERVATION_AREA`, representing project-wide applicability. |
| M3 SQLite pin | **CLOSED** | The stack now pins current SQLite 3.53.4 while AD-14 keeps the safety floor at 3.51.3. |
| L1 capability map | **PARTIAL / LOW** | CAP-1 and public access were improved; several newer governing ADs remain absent from the navigation table. |

## High findings

### F1 — The older pipeline invariants still contradict the new state machine

**Evidence:**

- AD-1 says **every run executes every filter** in order (`ARCHITECTURE-SPINE.md:50-54`).
- AD-26 allows non-applicable filters to be skipped and mandates skipping every downstream filter after technical failure (`:200-204`).
- AD-2 says an `AnalysisRun` binds **every stage output and the final result** (`:56-60`), but a failed run necessarily has skipped stages with no output and may have no final result.

AD-26 is otherwise a strong state contract, but independently built components cannot obey these absolute rules simultaneously. One team may fabricate empty outputs/final results to satisfy AD-2; another may omit them to satisfy AD-26. The same ambiguity exists around whether a skipped filter counts as “executed.”

**Disposition:** **Autofix.** Amend AD-1 to say that every run materializes the fixed ordered stage registry and makes filters eligible in order; a filter executes only when AD-26 permits it. Amend AD-2 to bind every stage execution record, every output that was actually committed, and the final result when produced. In AD-26, replace “allowed terminal result” with the exact predecessor outcomes that permit advancement, such as `succeeded` or `skipped:not_applicable`.

### F2 — An observation-only run can incorrectly replace stage health

**Evidence:** AD-21 correctly says a usable single frame may report an observation only and cannot produce the periodic-equipment warning (`:170-174`). AD-27 nevertheless chooses the latest succeeded run for the provider and maps any result without insufficiency or a check request to `no_signal` (`:206-210`). It does not require that the run was eligible to evaluate the stage rule.

Therefore a newer single-image run can replace a prior series-based `check_required` with `no_signal`, even though it lacked the evidence required to evaluate periodic dump-truck absence. Two units could also disagree over whether “no warning was permitted” means `no_signal` or `insufficient_data`.

**Disposition:** **Autofix.** Define a stage-health-eligible run as one that completed the evidence shape required by its bound rule and policy. Only the latest eligible succeeded run may replace health. Observation-only runs remain visible but do not change stage health; if the latest attempted analysis cannot evaluate the rule, expose it separately as pending/failed/insufficient evidence according to its actual result. Keep `no_signal` exclusively for a completed eligible evaluation that produced no check request.

## Medium finding

### F3 — Per-session artifact ownership is required but has no stable domain owner

**Evidence:** AD-28 says a shared-code session may create and read only its own runs (`:212-216`), but neither AnalysisRun ownership, a session/authorization subject identifier, nor session continuity is represented in AD-2 or the ER diagram. The reusable shared demo code authenticates all judges alike.

Backend and frontend implementations could therefore disagree about whether ownership is tied to a browser cookie, server session, the shared code, or merely possession of an opaque ID. This matters because AD-28 explicitly claims prevention of cross-session disclosure.

**Disposition:** **Autofix.** Bind each non-seed run to an opaque server-issued session subject, store only its hash/identifier, authorize run and artifact reads against it, and state whether losing/expiring that browser session intentionally loses access to prior private runs. Keep seed runs globally read-only. No account system is required.

## Low finding

### F4 — Capability navigation lags the new governing decisions

The capability table does not link CAP-2 to AD-26/30, the minimal plan to AD-27/29, or CAP-6 to AD-30. The ADs themselves cover the requirements, so this is discoverability rather than correctness.

**Disposition:** **Autofix if the table is touched.** Add the missing IDs without adding prose.

## Full-rubric result

| Rubric dimension | Result | Note |
| --- | --- | --- |
| Real divergence points | REVISE | F1-F3 remain genuine cross-unit seams. |
| Enforceable ADs | REVISE | AD-26/27 are strong, but conflict with older absolutes or admit an ineligible input. |
| Deferred safety | PASS | Thresholds, detector/runtime fit, hosting operations, and retention have explicit revisit conditions. |
| Named technology currency and fit | PASS | Python, FastAPI, SQLAlchemy, SQLite, React, Vite, Node, and create-vite pins are current and compatible. TypeScript 6.0.3 intentionally matches the current official React+TS Vite starter while TypeScript 7 lacks a stable programmatic API for parts of the tooling ecosystem. |
| Brownfield/parent consistency | N/A | No implementation code or inherited parent spine exists. |
| Source capability coverage | PASS | CAP-1..6 and the wider hackathon prototype, presentation, documentation, ordinary-hardware, and public-link obligations are represented. |
| Operational/environmental envelope | PASS | Single-host ownership, WAL/storage constraints, upload bounds, restart behavior, health smoke, capacity response, and scale-out trigger are explicit. |
| Diagrams | PASS | State, data, and deployment diagrams now carry the important structural shape; prose fix F1 is still required. |
| Seed minimality | PASS | The spine avoids full schemas and implementation boilerplate while fixing shared boundaries. |

## Verification performed

- `lint_spine.py`: PASS, 0 findings.
- Rechecked the full spine against `SPEC.md`, `prototype-scenarios.md`, and `artifacts/spec.pdf` requirements used in the initial review.
- Reverified updated pins against official/current sources: SQLite 3.53.4, create-vite 9.2.1, Vite 8.3.0, TypeScript 6.0.3 starter compatibility, and the previously checked backend/runtime versions.

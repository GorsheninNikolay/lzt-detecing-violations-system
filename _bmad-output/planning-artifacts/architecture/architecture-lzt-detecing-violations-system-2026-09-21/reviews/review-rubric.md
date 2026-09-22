# Good-Spine Rubric Review

## Gate verdict

**REVISE — no critical findings, but three load-bearing semantics still allow independently implemented units to disagree.** The spine is otherwise unusually complete for a rapid MVP: it covers the source capabilities, makes evidence and version ownership explicit, includes a proportionate public-deployment envelope, keeps the seed small, and passes the deterministic linter.

## Checks performed

- `lint_spine.py`: PASS, 0 findings.
- Source coverage: checked against `SPEC.md`, `prototype-scenarios.md`, and the requirements extracted from `artifacts/spec.pdf`.
- Brownfield/inheritance: no implementation code or parent spine exists to ratify; no conflict found.
- Stack currency: verified against the official Python, FastAPI, React, Vite, TypeScript, Node.js, SQLAlchemy, and SQLite sources on 2026-09-21. The selected versions are current supported choices except SQLite 3.51.3, which is an explicit safe minimum rather than the latest 3.53.0; that is acceptable because AD-14 requires `3.51.3 or later`.
- Structural breadth: data/evidence ownership, runtime execution, public deployment, access, restart behavior, operability gates, extensibility, UI disclosure, and post-MVP migration are all addressed.

## High findings

### H1 — The persisted pipeline states do not form an enforceable transition contract

**Evidence:** AD-1 says every run executes all six filters in order (`ARCHITECTURE-SPINE.md:50-54`), while AD-11 allows every stage to be `pending`, `running`, `succeeded`, `skipped`, or `failed` (`:110-114`). AD-9 defines only the run-level lifecycle (`:98-102`). No rule says:

- which stage transitions are legal;
- whether only one stage may be `running`;
- what happens to downstream stages after technical failure;
- whether `insufficient_data` is a successful domain outcome that continues to result projection or a reason to skip filters;
- when the run becomes `succeeded` versus `failed`.

Two builders can therefore produce visibly different jury pipelines and incompatible recovery behavior while both claiming conformance. The conflict is especially important because the user explicitly requires visible, truthful state transitions.

**Disposition:** **Autofix.** Amend AD-1/AD-11 or add one AD with a compact state diagram. Require fixed stage records at creation; monotonic legal transitions; at most one running stage; technical failure → active stage `failed`, downstream stages `skipped` with dependency reason, run `failed`; domain insufficiency remains typed evidence and still reaches result projection; run success requires the terminal projection to succeed. Clarify that “executes in order” means “becomes eligible in order,” not that a failed run invokes every filter.

### H2 — Stage-health derivation leaves the main overview nondeterministic

**Evidence:** AD-4 says health is derived “from linked runs” and names four states (`:68-72`) but does not bind the eligible run set, recency window, precedence, treatment of failed/running runs, or behavior when several active stages/runs exist. AD-13 makes that overview the first screen (`:122-126`).

A backend team could choose latest successful run, worst state across all history, or the current observation period; a frontend could independently derive a different result. That is precisely the cross-unit divergence an architecture spine should prevent, and it could surface a stale `check_required` or hide a recent one.

**Disposition:** **Autofix.** Make the backend projection authoritative and define a minimal deterministic rule, for example: use the latest completed successful run in the selected stage/area and current plan revision; `queued`/`running` and failed runs do not replace the last result but are shown separately; no qualifying run → `not_observed`. If aggregation across multiple areas or periods is desired, define precedence and scope explicitly instead.

### H3 — `continuous` equipment has no shared evaluation semantics

**Evidence:** AD-12 makes `continuous` a first-class rule expectation and the excavation rule uses it for the excavator (`:116-120`; source `prototype-scenarios.md`). AD-21 defines warning eligibility only for missing `periodic` equipment and present `unexpected` equipment (`:170-174`). It does not say whether an absent continuously expected excavator can produce a check request, and if so whether one usable frame or a sufficient series is required. The stable generic code `expected_equipment_not_observed` in conventions (`:211`) does not resolve this.

Separate rule-evaluation and UI/test units can therefore disagree on a core class in the sole MVP scenario, potentially generating an overclaim from a single image.

**Disposition:** **Autofix or explicit defer.** Safest MVP fix: state that `continuous` absence remains an observation only and produces no check request unless a separate, policy-defined eligibility rule is adopted; or define its minimum evidence contract now. Do not leave it implicit.

## Medium findings

### M1 — Deployment diagram does not visibly preserve the one-writer process boundary

**Evidence:** AD-14 requires one application process to own all structured-state writes (`:128-132`), but the deployment diagram draws `APP` and `EXEC` as sibling components with independent arrows to SQLite (`:264-278`). A builder could reasonably deploy the executor as a second writer process, contradicting AD-14.

**Disposition:** **Autofix.** Enclose API and executor in an `APPLICATION PROCESS` boundary and show one state-owner/repository edge to SQLite; model inference alone may cross into the child-process boundary.

### M2 — Observation-area cardinality in the ER diagram conflicts with project-wide applicability

**Evidence:** AD-23 permits stage/rule applicability to bind an area **or** explicitly be project-wide (`:182-186`), while the ER diagram requires every `WORK_STAGE` to have exactly one `OBSERVATION_AREA` (`:250`). It also does not show rule applicability to area.

**Disposition:** **Autofix.** Make the WorkStage-area relation optional and/or introduce an explicit applicability association that can represent either a concrete area or project-wide scope. Keep the prose and diagram isomorphic.

### M3 — The version table overstates SQLite 3.51.3 as the stack pin

**Evidence:** AD-14 correctly gives a lower bound (`3.51.3 or later`, `:132`), while the stack table lists exactly `3.51.3` (`:220`). SQLite 3.53.0 is the current stable release and also contains the WAL-reset fix. This is not unsafe, but two builders may interpret the table as an exact pin versus a minimum runtime gate.

**Disposition:** **Autofix.** Render the table value as `>=3.51.3 (3.53.0 current verified)` or pin 3.53.0, while retaining the runtime lower-bound invariant.

## Low finding

### L1 — Capability mapping understates several governing ADs

CAP-1 omits the closed observation contract, taxonomy, and observation context (AD-20/22/23), and public jury access omits the summary-first/progress rules. The ADs themselves cover the requirements, so this is navigation rather than correctness.

**Disposition:** **Autofix if touching the table; otherwise ignore.** Add the missing IDs without expanding prose.

## Rubric summary

| Rubric dimension | Result | Note |
| --- | --- | --- |
| Real divergence points | REVISE | Pipeline transitions, stage-health selection, and continuous-expectation semantics remain open. |
| Enforceable ADs | REVISE | Most rules are enforceable; H1-H3 are materially under-specified. |
| Deferred safety | PASS | Every deferred item has a revisit trigger; acceptance thresholds are correctly required before AC decomposition. |
| Named technology currency/fit | PASS | Official sources support the selected stack; clarify SQLite minimum versus exact pin. |
| Brownfield ratification | N/A | No existing implementation or parent spine was found. |
| Source capability coverage | PASS | CAP-1..6 and the wider hackathon delivery obligations are represented. |
| Operational/environmental envelope | PASS | Single host, durability, HTTPS, access bounds, restart, capacity, smoke, and scale-out trigger are covered. |
| Diagrams | REVISE | Deployment ownership and observation-area cardinality need alignment with AD prose. |
| Seed minimality | PASS | The directory seed and diagrams establish boundaries without turning into a full design. |

## Official version evidence consulted

- Python: https://www.python.org/doc/versions/
- FastAPI: https://fastapi.tiangolo.com/release-notes/
- React: https://react.dev/versions
- Vite: https://vite.dev/releases
- TypeScript: https://www.typescriptlang.org/docs/handbook/release-notes/typescript-6-0.html
- Node.js: https://nodejs.org/en/about/previous-releases
- SQLAlchemy: https://www.sqlalchemy.org/download.html
- SQLite WAL safety: https://www.sqlite.org/wal.html
- SQLite current releases: https://sqlite.org/news.html

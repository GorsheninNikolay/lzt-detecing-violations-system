# Final Good-Spine Rubric Re-review — Course-Corrected Architecture

**Artifact:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-22  
**Lens:** targeted closure of R1–R5 plus full good-spine regression check  
**Verdict:** **PASS — all five prior rubric findings are closed, and no new blocking, high, or medium divergence was introduced.**

## Closure matrix

| Prior finding | Result | Closing evidence |
|---|---|---|
| R1 — timeout bootstrap and revision ownership | **CLOSED** | AD-30 now permits only a `purpose=profile_admission` run to bind a draft profile, requires a snapshotted positive bootstrap watchdog distinct from the admitted runtime timeout, runs the ordinary evidence pipeline, and creates a new immutable admitted successor profile carrying CPU-smoke-derived timeouts. `PolicyProfile` no longer owns those runtime values. |
| R2 — reconciliation owner and trigger | **CLOSED** | AD-17 assigns reconciliation to application-owned `ArtifactReconciler`, fixes startup and explicit-operator triggers, fences passes with one named PostgreSQL advisory lock, makes them idempotent, defines the AD-28 namespace/intent scan boundary, records pass evidence, and blocks readiness/work claims until success. AD-28 closes intent/object attribution and metadata-only quarantine. |
| R3 — per-criterion CAP-6 verdicts | **CLOSED** | AD-24 binds the readiness-policy revision, requires a row with state, evidence, and reason for every criterion, forbids `not_evaluated` in a complete report, and defines the deterministic overall readiness reduction. |
| R4 — operational/environmental envelope | **CLOSED** | AD-9 fixes one single-host application instance with exactly one claim loop, startup ordering, database and artifact-store smoke gates, reconciliation-before-readiness, and liveness/readiness meaning. Deferred explicitly gates horizontal replicas or a separately supervised executor on a later deployment decision. The sequence diagram now carries the startup boundary. |
| R5 — candidate-not-winner disclosure owner | **CLOSED** | AD-34 persists `profile_revision_id` and closed `binding_kind` in the run-creation transaction and requires technical result/readiness disclosures to expose both bound profile status and binding kind. The renderer derives candidate-not-winner wording from those backend facts. |

## Full rubric regression

### Divergence coverage — PASS

The spine fixes the non-obvious seams that independently built units could otherwise choose incompatibly: ordered pipeline and closed result contracts; immutable run/profile/policy/rule identity; transactional ownership and lease fencing; retry lineage; publication intent and artifact reconciliation; provider admission, candidate binding, comparison ordering and denominators; report reduction; and single-host startup/claim ownership. No remaining MVP divergence point was found at feature altitude.

### Enforceability of every AD — PASS

Each AD has `Binds`, `Prevents`, and a rule with a concrete owner, immutable identity, state transition, rejection behavior, or persisted evidence contract. The previously non-executable phrases—first-smoke timeout derivation, “next reconciliation pass,” and candidate disclosure—now have explicit mechanisms. AD-1's “materializes” wording remains consistent with AD-11 and AD-26: all ordered stage records exist, while dependency-failed stages may be skipped rather than executed.

### Deferred safety — PASS

Every Deferred item is either non-blocking for the delivered MVP or guarded by a clear revisit condition. Active-provider publication, broader hardware portability, hybrid execution, horizontal scaling/separate executor topology, RF-DETR corpus admission, Kimi, Enterprise/AGPL, vector search, and later numeric thresholds cannot silently alter current run evidence or provider choice.

### Canonical SPEC and scenario coverage — PASS

CAP-1 through CAP-6 are covered without contradicting the canonical constraints. In particular:

- every requested class uses the closed four-state contract and input evidence;
- the series rule requires three usable same-area ordered images, excavator evidence, and dump-truck non-detection in every usable image;
- rule, observation, period, provenance, uncertainty, and recommended human check remain separate and exposed;
- evaluation retains mandatory positive, negative, insufficient-data, and out-of-scope cases, literal error/timeout denominators, repeat disagreement, zero-false-warning verdict, and criterion-by-criterion readiness;
- no result declares a violation or takes managerial action;
- local/cloud/hybrid selection remains outside MVP readiness and no winner is published.

### Operational/environmental envelope — PASS

The delivered topology, startup order, migration/storage/reconciliation gates, readiness semantics, work-claim ownership, and future scaling boundary are now explicit. Provider choice for PostgreSQL/S3 remains a replaceable adapter concern and does not create an incompatibility because behavior and startup proofs are fixed.

### Seed minimality — PASS

The directory seed and two diagrams communicate boundary shape without duplicating domain contracts. Operational detail remains in ADs, not in an expanded project tree. Stack pins are separated cleanly from structure.

### Contradiction audit — PASS

No conflict remains among AD-8, AD-30, and AD-37 ownership: policy owns evidence/readiness decisions, while execution profiles own runtime identity and timeouts. AD-9/14/17 agree on one application instance, transactional claims, and fenced recovery. AD-18/30/34 consistently allow a draft profile only for admission, require admitted profiles for user/demo/comparison/retry runs, forbid fallback, and keep active selection post-MVP. AD-24's `incomplete|fail|pass` report reduction is consistent with the per-row `pass|fail|not_evaluated` contract and with CAP-6's requirement that a complete evaluation decide every criterion.

## Residual implementation parameters

These are not architecture findings because the governing mechanisms and evidence are fixed:

- choose and snapshot the positive bootstrap-watchdog value in the profile-admission run;
- choose the concrete advisory-lock key/name and operator-command surface;
- materialize the readiness-policy criterion IDs and wording without changing the canonical scenario semantics;
- select concrete PostgreSQL and S3-compatible deployments that pass the mandated startup smokes.

## Gate disposition

The architecture spine is convergent and enforceable enough for backlog reconciliation and the next sprint-readiness check. No further architecture correction is required by this rubric.

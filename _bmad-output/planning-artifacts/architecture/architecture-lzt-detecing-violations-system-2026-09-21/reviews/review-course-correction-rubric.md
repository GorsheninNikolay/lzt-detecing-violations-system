# Good-Spine Rubric Review — Course-Corrected Architecture

**Artifact:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-22  
**Lens:** divergence coverage, AD enforceability, Deferred safety, canonical SPEC coverage, operational envelope, seed minimality, and contradiction audit  
**Verdict:** **CONCERNS — the product/evidence spine is coherent, but two implementation boundaries remain materially under-specified and CAP-6 is not yet closed at its reporting boundary.**

## Gate summary

The course correction successfully removes the former prototype-versus-selection cycle. AD-34 now permits an explicitly configured admitted candidate without declaring a winner; AD-7, AD-18, AD-24, and Deferred keep provider selection and hybrid execution out of the delivered MVP. The canonical four-state observation model, series rule, evidence lineage, no-fallback behavior, cloud gating, immutable retries, and Apple M3 Pro CPU baseline are mutually consistent.

The spine is not yet a full PASS. The first local smoke has no executable bootstrap timeout contract, while the text assigns the resulting timeout to two different revision owners. Mandatory artifact reconciliation is named but has no owner or execution trigger. Finally, the readiness report is not required to record an explicit verdict for every canonical readiness criterion, even though that is CAP-6's success condition.

## Findings

### R1 — HIGH: local admission has a circular bootstrap and ambiguous timeout owner

**Location:** AD-30 (`ARCHITECTURE-SPINE.md:167-171`), AD-37 (`:203-207`), Deferred (`:282-284`)

**Evidence**

- AD-37 requires a complete CPU-only evaluation smoke as admission evidence and says the admitted profile receives timeouts derived from that smoke.
- AD-30 says the initial mandatory local profile *uses* the timeout formula based on the first complete smoke, but does not define the guard under which that first smoke itself runs.
- AD-30 starts the rule with “Until a measured policy revision exists,” although timeout/concurrency are fields of `ObserverExecutionProfileRevision`; AD-8 reserves `PolicyProfile` for input, sufficiency, and readiness decisions.

**Divergence / impact**

One implementation can run the first smoke without a timeout, another with an arbitrary developer timeout, and a third with the very formula that cannot be calculated until the run finishes. They can also disagree whether the measured result creates a `PolicyProfile` revision or an observer-profile revision. These choices can change which model is admitted and conflict with the accepted Story 3.2 handoff.

**Required correction — autofix**

Define one bootstrap rule for the first CPU-only smoke (for example, a separately named harness watchdog that is evidence but not the admitted runtime timeout). State that successful smoke measurements create a **new `ObserverExecutionProfileRevision`** carrying the computed per-image and batch timeouts; they do not create a `PolicyProfile` revision. Admission must apply only to that derived profile revision after its locked end-to-end proof.

### R2 — HIGH: mandatory reconciliation has no operational owner or trigger

**Location:** AD-17 (`ARCHITECTURE-SPINE.md:113-117`), AD-28 (`:161-165`), Structural Seed (`:239-267`)

**Evidence**

- AD-17 promises registration “on the next reconciliation pass.”
- AD-28 calls reconciliation mandatory.
- No AD or Deferred item defines what starts a pass, which application component owns it, whether passes are serialized/fenced, what scope they scan, or what observable condition proves one completed.
- The structural sequence stops at normal run completion and contains no recovery/reconciliation path.

**Divergence / impact**

Independent builders can reasonably implement startup-only reconciliation, a periodic job, a manual command, or no automatic invocation at all. After a crash, unreferenced evidence can therefore remain invisible indefinitely even though Story 1.4 and the spine promise deterministic quarantine. Concurrent passes could also race unless ownership is fixed.

**Required correction — discuss, then encode**

Choose the bounded single-host mechanism and state it as an invariant: owner, trigger(s), serialization/fencing, idempotency, scan boundary, and persisted last-success/error evidence. A minimal MVP choice could be an application-owned idempotent startup pass plus an explicit operator command, with demo readiness blocked until a successful pass; the exact choice belongs in an AD, not in implementation folklore.

### R3 — MEDIUM: CAP-6 does not require a verdict for every readiness criterion

**Location:** AD-8 (`ARCHITECTURE-SPINE.md:71-75`), AD-24 (`:149-153`), Capability Map (`:269-278`)

**Canonical requirement**

`SPEC.md` CAP-6 requires “the pass or fail result of every readiness criterion,” and `prototype-scenarios.md` lists the individual criteria.

**Spine gap**

AD-24 requires literal metrics, mandatory outcomes, zero-false-warning verdict, disagreements, latency/cost, and comprehension, but it does not bind a versioned criterion catalog or require one explicit verdict per criterion. “Mandatory outcomes” is not equivalent to criterion-by-criterion evaluation.

**Divergence / impact**

One report can emit only metrics and an aggregate readiness flag while another emits a full criterion matrix; both can claim conformance to AD-24, but only the latter satisfies CAP-6 and lets a reviewer see what failed.

**Required correction — autofix**

Require `EvaluationReport` to bind the exact readiness-policy revision and carry one named `pass|fail` result (or a deliberately specified third state if needed) plus evidence/reason for every criterion in that revision. Overall readiness must be a deterministic reduction of those rows and must not hide missing rows.

### R4 — MEDIUM: the operational/environmental envelope is only implied, not closed or deferred

**Location:** AD-9 (`ARCHITECTURE-SPINE.md:77-81`), AD-14 (`:107-111`), Stack (`:226-237`), Structural Seed (`:239-252`), Deferred (`:280-289`)

**Evidence**

The spine names a single host, PostgreSQL, and an S3-compatible endpoint, but it never decides or explicitly defers the environment boundary: which deployable process owns API and executor startup, whether more than one process/replica is permitted, how migrations are serialized before work claims, what constitutes demo-environment readiness, and which health/operational evidence is required. This is a whole architecture dimension called out by the reviewer rubric.

**Divergence / impact**

Two teams can produce incompatible deployment units despite agreeing on domain contracts—for example, an in-process background executor versus a separately supervised worker—with different restart and migration behavior. AD-14's lease rules make either imaginable but do not make their lifecycle compatible.

**Required correction — discuss or explicitly defer**

For the bounded MVP, state the allowed single-host process topology and startup order (migration gate, storage smoke, reconciliation, claim loop), plus minimal liveness/readiness evidence. If deployment is intentionally outside this feature spine, add an explicit Deferred item with the revisit gate “before the first deployable demo image”; leaving the dimension silent is not safe.

### R5 — LOW: candidate-not-winner disclosure has no concrete owner

**Location:** AD-34 (`ARCHITECTURE-SPINE.md:185-189`)

AD-34 says technical disclosure retains candidate-not-winner status, but it does not say which persisted contract owns that fact or which API/report surfaces must expose it. The rest of AD-34 correctly prevents an active configuration and winner publication, so this is not currently a selection contradiction. Still, separately built API and UI units can disagree about whether the disclosure is a profile status, a run field, or merely prose.

**Required correction — defer or small autofix**

Either bind the disclosure to an existing immutable field/relation (preferably the profile role plus absence of active-selection evidence) and require the result/readiness projections to expose it, or explicitly assign the display wording to the UX/story layer while preserving the backend fact contract here.

## Rubric coverage

### Divergence coverage

**CONCERNS.** Domain, evidence, lifecycle, provider, and data-integrity seams are unusually well covered. The remaining material divergence points are first-smoke bootstrap, reconciliation operations, and deployment lifecycle.

### Enforceability of ADs

**CONCERNS.** Most rules identify an owner, immutable boundary, transition, or rejection behavior. R1 and R2 are not operationally executable as written. R5 uses an outcome phrase without a data owner.

### Deferred safety

**PASS.** Active-provider publication, broader hardware portability, hybrid execution, RF-DETR corpus admission, Kimi, Enterprise/AGPL, vector search, and future numeric thresholds are all non-blocking for the required MVP path and have sensible revisit conditions. None permits current units to select a winner or silently widen scope.

### Canonical SPEC and scenario coverage

**CONCERNS.** CAP-1 through CAP-5 and nearly all CAP-6 evidence are bound. R3 is the remaining direct capability gap. No contradiction was found with the non-judicial boundary, explicit context, two-class scope, four-state meanings, same-area series, or technology-selection neutrality.

### Operational/environmental envelope

**CONCERNS.** Storage and transactional mechanics are fixed, but deployment/process topology, reconciliation execution, and readiness/health ownership are not decided or explicitly deferred (R2, R4).

### Seed minimality

**PASS.** The structural seed is small, expresses only main dependency boundaries, and does not duplicate the detailed AD contracts. Stack pins are appropriately separated from the directory seed.

### Contradiction audit

**CONCERNS.** No product-level contradiction remains after the course correction. The only substantive ownership contradiction is AD-30's reference to a “measured policy revision” for values otherwise owned by the observer execution profile (R1). AD-1's statement that every run materializes every filter should be read together with AD-11/AD-26 as materializing ordered stage records, not executing every stage; tightening that noun would be harmless but is not a gate finding.

## Recommended gate disposition

Resolve R1 and R2 before implementation readiness is declared. Resolve R3 in the same edit because it is a direct CAP-6 contract gap. R4 should either be decided now or explicitly deferred with a pre-deployment gate. R5 can be handled in the story/UX contract if the backend fact owner is made unambiguous there.

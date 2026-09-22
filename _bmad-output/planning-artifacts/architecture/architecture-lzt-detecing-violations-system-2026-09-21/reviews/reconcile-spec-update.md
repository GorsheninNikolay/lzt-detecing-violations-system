# Reconciliation — updated `SPEC.md` vs `ARCHITECTURE-SPINE.md`

## Verdict

**FAIL — the six canonical capabilities are represented, but the spine is not yet strictly reconciled to the updated canonical contract.** The main mismatch is not in the observation and warning semantics; it is that the spine continues to bind a non-canonical source and turns hackathon/jury delivery assumptions into adopted architecture requirements. One provenance semantic from the SPEC also remains under-specified.

## Findings

### 1. High — a non-canonical source still expands the binding scope

**SPEC evidence:** `SPEC.md:3-9` declares that the SPEC and its listed companion are the complete preservation-validated contract. Other source documents are traceability material only.

**Spine evidence:** `ARCHITECTURE-SPINE.md:18-22` lists `artifacts/spec.pdf` alongside the two canonical files as a source. Requirements that appear to come from that source are then adopted as binding rules, notably public jury delivery and hackathon acceptance (`AD-15`, lines 122-126), reusable-code access (`AD-16` and `AD-32`, lines 128-132 and 206-210), submission smoke requirements (`AD-25`, lines 176-180), and presentation/repository/documentation deliverables (`Deferred`, lines 338-346).

**Impact:** independently built units can treat requirements omitted from the updated canonical package as mandatory product scope. That defeats the SPEC's explicit contract boundary and makes later traceability ambiguous.

**Required reconciliation:** remove `spec.pdf` from the spine's binding `sources` or mark it explicitly as non-binding rationale. Remove the jury/hackathon, reusable-code, public-submission, presentation, repository, and documentation obligations from the spine unless they are reintroduced into `SPEC.md` or `prototype-scenarios.md`. If retained as an implementation assumption, they must not be `[ADOPTED]` and need a clear owner/revisit condition.

### 2. High — the spine scope promises a jury-facing web application that the canonical SPEC does not require

**SPEC evidence:** `SPEC.md:15-36` requires analysis capabilities and readiness evidence for a bounded demonstration. It does not prescribe a browser application, public deployment, account/access behavior, a stable URL, or a jury evaluation window.

**Spine evidence:** frontmatter scope explicitly includes a “jury-facing web application” (`ARCHITECTURE-SPINE.md:7`). The design diagram fixes React and FastAPI (`lines 31-45`); `AD-13` fixes a browser-oriented primary experience (`lines 110-114`); `AD-15`, `AD-16`, `AD-28`, and `AD-32` define public hosting and session isolation; the capability map adds “Public jury access” as an architecture area (`lines 321-331`).

**Impact:** this is product-scope expansion, not merely a seed choice. It creates substantial security, persistence, deployment, and UX work that is unnecessary to satisfy CAP-1 through CAP-6 as currently written.

**Required reconciliation:** narrow the spine scope to the bounded monitoring prototype. Keep a web/API stack only as structural seed if chosen, while moving public deployment, jury access, and reusable-code/session behavior to Deferred pending an explicit canonical requirement.

### 3. Medium — rule provenance is recorded, but heuristic-to-normative misrepresentation is not prohibited

**SPEC evidence:** `SPEC.md:44` requires every rule to identify one of four provenance categories and explicitly states that an expert heuristic must not appear as a normative requirement.

**Spine evidence:** `AD-12` records provenance category and source reference (`ARCHITECTURE-SPINE.md:104-108`), and `AD-21` exposes provenance in the result (`lines 152-156`), but neither binds the semantic rule that `expert_heuristic` cannot be rendered, serialized, or interpreted as normative/methodological authority.

**Impact:** two units can preserve the same provenance value while presenting its authority incompatibly, violating a direct canonical constraint.

**Required reconciliation:** amend `AD-12` or the UI/API consistency conventions so provenance is a closed typed category and an expert heuristic can never use normative wording or presentation.

### 4. Medium — the execution-choice deferral is preserved for the observer, but several evidence-independent runtime mandates are presented as adopted acceptance requirements

**SPEC evidence:** `SPEC.md:15`, `46`, and `53` leave cloud, local, and hybrid execution undecided until comparative evidence is available.

**Spine evidence:** `AD-7` correctly defers provider selection (`lines 74-78`, `Deferred` lines 335-337). However, `AD-25` adopts a no-required-GPU path, container, persistent mounts, health endpoint, public URL, and reusable demo access as acceptance obligations (`lines 176-180`) before those requirements exist in the canonical contract.

**Impact:** the model/provider decision remains open, but the acceptance envelope is partially preselected and may bias or exclude a technically valid evidence-backed option. At minimum, the extra mandates cannot be traced to the canonical contract.

**Required reconciliation:** keep comparative runs, observer identity, and reproducibility invariants. Recast the no-GPU/container/public-host clauses as assumptions or Deferred decisions with evidence-based revisit conditions, unless the companion explicitly binds them.

## Canonical requirements that did land

- CAP-1 through CAP-6 are all named in frontmatter and mapped to architecture ownership.
- Single-frame observations remain in-frame only; site-wide absence is prohibited (`AD-20`, `AD-21`).
- Series evaluation binds one area and period and suppresses warnings for insufficient data (`AD-8`, `AD-21`, `AD-23`, `AD-31`).
- Observation, rule, and managerial recommendation remain separate (`AD-1`, `AD-12`, `AD-21`).
- The `PolicyProfile` is immutable, revisioned, snapshotted per run, and changed only by a new revision (`AD-8`).
- Cloud/local provider selection remains deferred pending comparison evidence (`AD-7`, Deferred).
- The 10–15-image labeled evaluation records the required evidence and readiness results (`AD-24`).
- Schedule-derived stage inference remains explicitly outside scope (`AD-5`, Deferred).

## Reconciliation decision

Do not add new capabilities. Tighten source authority and remove or demote non-canonical delivery assumptions, then add the missing provenance-semantics invariant. After those changes, re-run reconciliation against both canonical files because some detailed policy values live in `prototype-scenarios.md`, not in `SPEC.md` itself.

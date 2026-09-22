# Sprint Change Proposal — Resolve MVP Execution and Story-Traceability Gaps

**Project:** lzt-detecing-violations-system  
**Date:** 2026-09-22  
**Status:** Approved for implementation  
**Approval:** Explicit user approval received on 2026-09-22  
**Change scope:** Moderate  
**Requirements authority:** `SPEC.md` and `prototype-scenarios.md` serve as the PRD-equivalent canonical contract for this project.

## 1. Issue Summary

The sprint-readiness review found that the current architecture and epic sequence cannot be implemented without inventing or bypassing decisions:

1. Epic 1 requires interactive Grounding DINO analysis, while AD-34 permits ordinary runs only after a complete Epic 3 comparison has published an active observer. Epic 3 in turn depends on the local profile prepared in Epic 1. No story publishes the active configuration.
2. The comparison campaign is scheduled before the cloud-admission story that authorizes use of GigaChat and organizer images.
3. Restart recovery, uncertain model-call handling, artifact reconciliation, and quarantine are architectural requirements but have no implementing story.
4. Local admission refers to an undefined hardware-neutral laptop baseline, although the architecture already names the Apple M3 Pro development machine.
5. UX surfaces and recovery states already required by the final UX contract are not fully represented in stories.
6. The epic inventory promises executable hybrid composition without a story or an admitted hybrid candidate.
7. Only functional requirements have an explicit coverage map; NFR and UX coverage cannot be audited mechanically.

This is a planning-decomposition problem discovered before implementation, not a change to the product goal.

## 2. Impact Analysis

### 2.1 Canonical product contract

No change is required to the canonical SPEC or prototype scenarios. They already state that:

- local, cloud, and hybrid execution remain undecided until comparative evidence exists;
- selection of the final execution approach is not part of MVP readiness;
- the prototype must still demonstrate evidence-bound observations and rule outcomes.

The correction therefore preserves the MVP and makes architecture and stories conform to it.

### 2.2 Epic impact

| Epic | Impact |
|---|---|
| Epic 1 — Trustworthy equipment observations | Retain scope. Allow an explicitly bound admitted prototype candidate without declaring a winner. Add interruption/artifact recovery and missing navigation/recovery UX coverage. |
| Epic 2 — Explainable excavation-series check | Retain scope and order. No product behavior changes. Add traceability references only. |
| Epic 3 — Demonstrable, evidence-backed prototype readiness | Retain scope. Make Grounding DINO CPU admission concrete, keep RF-DETR conditional, move GigaChat admission before comparison, and prevent the report from publishing a winner. |

The epic order remains 1 → 2 → 3. No epic is removed or replaced.

### 2.3 Architecture impact

- Revise AD-34 to separate per-run prototype candidate binding from post-MVP provider selection.
- Make Apple M3 Pro CPU-only the initial mandatory local MVP baseline; keep MPS and RTX 3060 as distinct optional profiles.
- Preserve no-fallback, immutable profile binding, complete comparison, and exact evidence requirements.
- Defer executable hybrid composition and active observer publication beyond the delivered MVP.
- Update diagram labels, structural-seed wording, and deferred decisions to match.

### 2.4 UX impact

The UX specifications remain unchanged. Existing approved requirements are transferred into stories:

- Stages Overview and About Project;
- offline, camera-denied, decode-error, uncertain-submit, polling-loss, and restart states;
- laptop/phone navigation and required accessibility behavior.

### 2.5 Technical and delivery impact

- One new backend reliability story and one new navigation/scope story are added.
- Existing stories gain explicit acceptance criteria for profile binding, admission order, secrets, and recovery.
- No implementation rollback is required because the conflict was found during planning.
- `sprint-status.yaml` must not be generated until the approved edits are applied and readiness passes.

## 3. Recommended Approach

### Selected path: Direct Adjustment

Apply bounded architecture and backlog corrections without changing the MVP contract.

**Rationale:**

- It removes the circular dependency without prematurely selecting a model.
- It preserves the current user journeys and evidence semantics.
- It avoids blocking the prototype on RF-DETR training data or a hybrid implementation.
- It makes failure recovery and artifact integrity explicit sprint work.
- It keeps the comparison campaign honest and gated by cloud authorization.

### Alternatives considered

| Option | Decision | Reason |
|---|---|---|
| Move all comparison and final selection before Epic 1 | Rejected | It would block the primary MVP flow on cloud admission and contradict the canonical statement that final selection is outside MVP readiness. |
| Roll back completed implementation | Not applicable | No conflicting implementation was identified; this is a pre-implementation planning correction. |
| Reduce the MVP product scope | Rejected | The product goal remains achievable after backlog and architecture reconciliation. |

### Effort and risk

- **Planning effort:** Medium — architecture wording, story additions/resequencing, and trace maps.
- **Implementation impact:** Medium — one reliability story, one navigation story, and expanded acceptance criteria.
- **Change risk:** Low to medium — the proposal removes ambiguity while preserving existing contracts.
- **Timeline impact:** Adds explicit work that was already required implicitly; this may increase the visible story count but reduces high-risk rework and data-loss exposure.

## 4. Detailed Change Proposals

### 4.1 Architecture — AD-34

**Current intent:** `ActiveObserverConfiguration` is required for ordinary runs and can be published only after a complete comparison campaign.

**Replace with:**

```markdown
### AD-34 — Run observer binding is explicit; active selection is deferred [ADOPTED]

- **Binds:** Prototype runs, comparison runs, and future ordinary-run configuration.
- **Prevents:** A prototype candidate being presented as a selected winner, a run following later configuration, or fallback changing the observer mid-run.
- **Rule:** Every MVP `AnalysisRun` binds exactly one immutable admitted `ObserverExecutionProfileRevision` before execution. Comparison runs obtain the profile from their immutable campaign matrix cell. Interactive prototype and demonstration runs obtain an explicitly configured prototype-profile revision. This binding is evidence for the run, not publication of a provider winner, and the candidate status remains visible in technical disclosure. Changing the profile creates a new run; no binding source may perform fallback routing. The delivered MVP does not implement `ProviderSelectionService` or publish `ActiveObserverConfiguration`. A later increment may publish an active configuration only from a complete comparison campaign and report, using an expected-prior guard.
```

Related architecture edits:

- Rename diagram labels from selected adapters to bound candidates.
- Replace `selection` with `candidate binding` in the structural seed.
- Record active observer publication as post-MVP in Deferred Decisions.

### 4.2 Architecture — local admission baseline

Revise AD-37 and Deferred Decisions so that:

- Apple M3 Pro in CPU-only mode is the initial mandatory ordinary-laptop MVP baseline.
- A complete locked offline evaluation-set smoke is the admission proof.
- CPU latency and memory are recorded literally; the initial PolicyProfile adds no arbitrary numeric performance gate.
- AD-30's measured formula determines profile timeouts after the first complete smoke.
- Apple MPS and Windows RTX 3060 remain separate profiles; implicit CPU fallback cannot pass an accelerator smoke.
- RF-DETR remains draft and non-blocking until a rights-clear training corpus and split are approved.
- A wider cross-hardware baseline is post-MVP.

### 4.3 Story 1.3 — explicit prototype candidate binding

Add:

```markdown
- Given that no comparison winner has been published, when an interactive prototype run is created, then it binds the explicitly configured admitted Grounding DINO prototype profile and records it as a candidate, not as a selected winner.
- Given the bound profile fails, then no other profile is invoked automatically; a retry creates a linked successor run and may explicitly bind another admitted profile.
```

### 4.4 New Story 1.4 — preserve evidence through interruption

```markdown
### Story 1.4: Preserve evidence through interruption

As a prototype owner, I want interrupted runs and partially published artifacts to be resolved explicitly, so that retries never hide, duplicate, or delete prior evidence.

**Acceptance Criteria:**

- Given a queued run that has not started, when the executor restarts, then the run remains queued and eligible for execution.
- Given a running executor is interrupted or loses ownership, then the run becomes terminally failed with `executor_interrupted`, completed evidence remains visible, and downstream stages are skipped with `dependency_failed`.
- Given it is unknown whether a model call completed, then the call is never resumed; retry creates a linked successor run.
- Given artifact publication begins, then a stable publication record is committed before upload, and the final reference is committed only after size and checksum verification.
- Given a stored object has no completed database reference, then reconciliation records it as quarantined evidence and does not silently delete it.
- Given an existing content-addressed object has a different size or checksum, then publication fails with an integrity error and the object is quarantined.
```

Rename the existing Story 1.4 to Story 1.5.

### 4.5 Story 1.2 and Story 1.5 — recovery UX

Add to Story 1.2:

- A decode failure rejects only the affected file and preserves all other inputs and order.
- Camera-permission denial retains ordinary file selection without repeated permission prompts.
- Offline state disables submission while preserving local form state.
- An uncertain submission response is reconciled to an authoritative run identity before a second submission is enabled.

Add to Story 1.5:

- Polling loss preserves the last known state and offers an explicit status refresh without fabricating failure.
- Server interruption is presented as terminal interruption and retry creates a linked successor.
- Execution lifecycle and analysis outcome remain separate visible fields.

### 4.6 New Story 1.6 — navigate the bounded prototype

```markdown
### Story 1.6: Navigate the bounded prototype

As a site manager or jury member, I want clear prototype navigation and scope disclosure, so that I can find evidence without mistaking it for project health.

**Acceptance Criteria:**

- The Stages Overview shows the latest successfully completed result for each configured stage and shows newer running or failed work separately.
- Stages without an MVP rule are labeled as not configured and never appear healthy, failed, or complete.
- The application provides Russian navigation to Stages, Analyses, Readiness, New Analysis, and About Project on laptop and phone.
- About Project explains the supported scenario, equipment classes, method, provenance, team identity, and explicit limitations.
- Every route remains keyboard-operable and usable at 320 CSS pixels and 200% zoom with the documented focus and status behavior.
```

### 4.7 Story 3.2 — reproducible local candidate admission

Rename the story to `Admit reproducible local candidate profiles` and replace its acceptance criteria with:

```markdown
- Given Grounding DINO preparation, then its exact checkpoint, dependencies, preprocessing, taxonomy mapping, and offline artifacts are locked and verified.
- Given initial local admission, then the complete frozen evaluation set runs offline on the Apple M3 Pro CPU profile and records actual device, latency, memory, errors, and all required evidence.
- Given the first complete CPU smoke, then per-image and batch timeouts are calculated using AD-30 and frozen in a new profile revision.
- Given MPS or Windows RTX 3060 execution, then each uses a separate profile and evidence set; implicit fallback to CPU is rejected as accelerator success.
- Given no approved rights-clear RF-DETR training corpus and split, then RF-DETR remains draft and is excluded without blocking the Grounding DINO versus GigaChat campaign.
- Given the RF-DETR corpus and split are approved, then dataset QA, corpus revision/hash, split manifest, training configuration, checkpoint hash, and seed are recorded before admission.
```

### 4.8 Epic 3 sequencing

Move cloud admission before comparison:

1. Story 3.1 — Freeze demonstration fixtures and readiness criteria.
2. Story 3.2 — Admit reproducible local candidate profiles.
3. Story 3.3 — Gate cloud candidate execution.
4. Story 3.4 — Run a complete candidate comparison campaign.
5. Story 3.5 — Present readiness and comparison evidence.

Add to Story 3.4:

```markdown
- Given the required local and cloud profiles are not both admitted, when campaign start is requested, then no comparison run starts and the unmet admission gates are recorded.
```

### 4.9 Secrets and non-selecting reports

Add to Story 3.3:

```markdown
- Given cloud credentials or tokens, then they exist only in process environment or an approved secret store and never enter source, PostgreSQL, artifacts, UI, or logs.
```

Add to Story 3.5:

```markdown
- Given a complete campaign and report, then the report presents literal evidence and ordering criteria but does not publish a winner or change the prototype profile automatically.
```

### 4.10 Hybrid scope

Replace the additional requirement:

```text
Support local Grounding DINO primary, RF-DETR experiment after dataset admission, paid-corporate GigaChat, and declared hybrid composition without fallback routing.
```

with:

```text
Deliver Grounding DINO and, after admission, GigaChat as the required MVP adapters. RF-DETR remains conditional on dataset admission. The data model may represent a declared hybrid profile, but executing or selecting a hybrid profile is post-MVP unless a complete comparison campaign admits it.
```

### 4.11 Requirement coverage maps

Add:

```text
### NFR Coverage Map

NFR1: Story 1.1
NFR2: Stories 1.1, 1.2, 1.4
NFR3: Stories 1.2, 1.3, 2.2, 3.1, 3.2, 3.4
NFR4: Stories 1.3, 1.4
NFR5: Stories 1.3, 2.3, 3.4
NFR6: Stories 1.3, 1.4, 3.4
NFR7: Stories 3.1, 3.4, 3.5
NFR8: Stories 1.3, 3.2
NFR9: Story 3.3
NFR10: Stories 1.1, 1.5, 1.6, 2.4, 3.5
NFR11: Stories 1.2, 1.4
NFR12: Story 3.3
NFR13: Story 3.2
NFR14: Stories 3.3, 3.4

### UX Coverage Map

UX-DR1: Stories 1.1, 1.2, 1.5
UX-DR2: Stories 1.2, 2.1
UX-DR3: Story 1.5
UX-DR4: Stories 1.5, 2.4
UX-DR5: Stories 2.3, 2.4
UX-DR6: Stories 2.4, 3.5
UX-DR7: Story 1.5
UX-DR8: Stories 1.1, 1.6, 3.5
UX-DR9: Stories 1.1, 1.2, 1.5, 1.6, 2.4, 3.5
UX-DR10: Stories 1.1, 1.6
```

### 4.12 Artifacts that remain unchanged

- Canonical `SPEC.md` and `prototype-scenarios.md`.
- Final `DESIGN.md` and `EXPERIENCE.md`; their existing requirements are transferred into stories.
- Research reports; they remain evidence snapshots rather than governing implementation plans.

## 5. Implementation Handoff

### Scope classification

**Moderate** — backlog reorganization and one architecture reconciliation are required, but the MVP goal and canonical product contract remain unchanged.

### Responsibilities

| Recipient | Responsibility |
|---|---|
| Solution Architect | Apply the approved AD-34, AD-37, diagram, structural-seed, and deferred-decision edits without changing stable AD IDs. Re-run architecture lint and consistency review. |
| Product Owner / Developer | Apply the accepted story additions, renumbering, Epic 3 resequencing, scope clarification, and coverage maps to `epics.md`. |
| Developer | Implement only after updated planning passes readiness and sprint tracking is generated. |

### Required sequence

1. Update the architecture spine in place, preserving stable AD IDs and history.
2. Update `epics.md` with all accepted changes and corrected numbering.
3. Verify references and coverage maps against the final story IDs.
4. Re-run `bmad-sprint-planning` readiness.
5. Generate and validate `sprint-status.yaml` only on PASS.
6. Begin implementation with Story 1.1.

### Success criteria

- Epic 1 can run an explicitly bound candidate without claiming a comparison winner.
- No story depends on a later story in the same epic.
- GigaChat admission precedes any organizer-image comparison run.
- Recovery and artifact reconciliation have explicit acceptance criteria.
- The local CPU admission baseline and timeout derivation are implementable as written.
- RF-DETR and hybrid execution do not block the required MVP path.
- Every NFR and UX requirement maps to at least one story whose acceptance criteria implement it.
- The canonical SPEC, architecture, UX, and epics contain no conflicting execution-selection claims.
- A fresh sprint-readiness gate returns PASS before tracking is generated.

## Appendix A — Checklist Status

### 1. Understand the Trigger and Context

- [x] 1.1 Triggering stories identified: 1.3, 3.3, and 3.4.
- [x] 1.2 Problem categorized as planning/architecture decomposition inconsistency.
- [x] 1.3 Evidence recorded from the canonical SPEC, architecture, epics, and UX.

### 2. Epic Impact Assessment

- [x] 2.1 Current epics remain viable after correction.
- [x] 2.2 Existing scope is modified without adding a new epic.
- [x] 2.3 All three epics reviewed.
- [x] 2.4 No epic becomes obsolete; two missing stories are added.
- [x] 2.5 Epic 3 stories are resequenced; epic order remains unchanged.

### 3. Artifact Conflict and Impact Analysis

- [x] 3.1 Canonical SPEC remains valid and unchanged.
- [x] 3.2 AD-34, AD-37, diagram, structural seed, and deferred decisions require edits.
- [x] 3.3 UX remains valid; missing coverage is transferred into stories.
- [x] 3.4 Research remains evidence; sprint tracking is deferred until readiness PASS.

### 4. Path Forward Evaluation

- [x] 4.1 Direct Adjustment is viable; effort medium, risk low to medium.
- [N/A] 4.2 Rollback is not applicable before implementation.
- [x] 4.3 MVP remains achievable without scope reduction.
- [x] 4.4 Direct Adjustment selected.

### 5. Sprint Change Proposal Components

- [x] 5.1 Issue summary completed.
- [x] 5.2 Epic and artifact impacts documented.
- [x] 5.3 Recommended path and alternatives documented.
- [x] 5.4 MVP impact and action sequence defined.
- [x] 5.5 Handoff roles defined.

### 6. Final Review and Handoff

- [x] 6.1 Applicable checklist items reviewed.
- [x] 6.2 Proposal checked for consistency and actionability.
- [x] 6.3 Complete proposal explicitly approved by the user on 2026-09-22.
- [N/A] 6.4 No sprint status exists yet; generate after approved edits and readiness PASS.
- [x] 6.5 Moderate-scope handoff assigned to Solution Architect and Product Owner / Developer, with Developer implementation gated by a fresh readiness PASS.

## Appendix B — Handoff Log

| Date | Event | Result |
|---|---|---|
| 2026-09-22 | Sprint Change Proposal reviewed incrementally | All nine proposals approved. |
| 2026-09-22 | Complete proposal approval | Explicit `yes` received. Status changed to Approved for implementation. |
| 2026-09-22 | Scope and routing confirmed | Moderate change routed to Solution Architect for the architecture edits and Product Owner / Developer for backlog reorganization. |
| 2026-09-22 | Implementation gate recorded | Apply architecture and epic edits, rerun readiness, and generate sprint tracking only after PASS. |

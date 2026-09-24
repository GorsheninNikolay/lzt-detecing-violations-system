# Sprint Change Proposal — Use Yandex AI Studio Qwen3.6 for Epic 4

- **Project:** lzt-detecing-violations-system
- **Date:** 2026-09-24
- **Status:** Approved for implementation
- **Approval:** Explicit owner approval received on 2026-09-24
- **Scope:** Moderate, direct adjustment inside Epic 4
**Requirements authority:** `../specs/spec-construction-monitoring-concepts/SPEC.md` and `prototype-scenarios.md` are the PRD-equivalent contract for this project.

## 1. Issue Summary

Story 4.2 is blocked by its requirement for a future customer's paid corporate GigaChat account. The owner has chosen Qwen3.6 35B in the owner's Yandex Cloud account instead. The separate `codex/yandex-cloud-ai-studio-20260924` branch already contains a Qwen image observer, bounded admission and ordinary-run integration, and local pilot evidence. Its report explicitly says the implementation is not merged or deployed and its comparison used an earlier image set. The newly accepted Story 4.1 evaluation revision is a different set; the branch's historic runs cannot become the new campaign's scored cells.

Yandex AI Studio's model documentation identifies Qwen3.6 35B as supporting Base64 images; the branch requests a strict two-class response through Responses API. The account, key, quota, accepted data terms, current model access, permitted image set, and served identity still require readback at Story 4.2 execution. Public documentation and a historical pilot do not replace those live gates.

## 2. Impact Analysis

| Surface | Impact |
|---|---|
| Canonical SPEC and scenarios | No change. They require one ready local detector and one cloud multimodal candidate on the same evaluation set; they do not name a cloud vendor. |
| Epic 4 | Keep the goal, seven stories, order, and complete three-repeat campaign. Change the named cloud candidate and its account/data gates in Story 4.2 and Story 4.3. |
| Architecture | Revise AD-7, AD-37, AD-38, the candidate table, and the deferred GigaChat-specific permission statement. Keep AD-30 profile immutability, AD-34 reservation, no fallback, and full-cell accounting. |
| UX | No layout or flow change. Existing technical disclosure of identity, commercial/data gates, and gaps fits Qwen. |
| Code and evidence | Evaluate the cloud branch as a source of implementation, reconcile it with current `main`, and verify its tests. Its 26-hash upload allowlist excludes the later accepted Story 4.1 set, so admission and campaign scope must be revised through an immutable profile revision. Never mutate an earlier profile or present prior pilot results as held-out readiness. |
| Sprint ledger | Story IDs and statuses stay unchanged during proposal review. Story 4.2 remains `backlog` until the corrected scope is approved and implementation starts; Story 4.1 remains `done`. |

### Change-navigation checklist

| Section | Result |
|---|---|
| 1. Trigger and evidence | [x] Story 4.2 block, owner's Qwen choice, cloud branch and pilot report inspected. |
| 2. Epic impact | [x] Only Epic 4 wording and gates change; no new epic, rollback, or resequencing. |
| 3. Artifact impact | [x] PRD-equivalent and UX stay; architecture, epics, Story 4.2 spec, and implementation need updates. |
| 4. Path evaluation | [x] Direct adjustment: medium planning/integration effort, medium risk. Rollback and MVP scope reduction do not solve a need. |
| 5. Proposal and handoff | [x] Exact edits and acceptance path below. |
| 6. Approval and sync | [x] Owner approved; canonical planning edits applied. Story IDs and sprint statuses remain unchanged; official validation and readback passed. |

## 3. Recommended Approach

Use **direct adjustment**. Retain the provider-independent evidence contract and replace the fixed GigaChat candidate with one exact Qwen3.6 35B profile in Yandex AI Studio. Scope the owner's account to the approved prototype image set. An admitted, enabled revision requires live account/model/quota/terms evidence, a bounded strict-schema image canary, returned model identity, ordinary invocation and private artifact readback, and an enforceable image-upload allowlist. Yandex's inline Base64 request has no GigaChat-style provider file lifecycle; do not claim upload-delete verification. Record `store=false` and disabled improvement logging as request settings, plus the provider's actual retention terms and any unresolved gap. Do not equate those settings with deletion of provider-held data.

The cloud branch's earlier comparison remains historical development evidence. Run the new three-repeat campaign only after the Story 4.1 evaluation revision and Qwen profile are independently frozen and reconciled. The prototype may process only the specifically authorized image set; arbitrary real site images require separate permission and account/data review.

**Effort:** medium for planning and branch integration; the campaign work remains in Stories 4.3–4.5. **Risk:** medium because branch integration, mutable hosted model identity, account state, and evaluation-set separation need fresh verification. **Timeline:** removes the unavailable GigaChat procurement dependency but does not make Story 4.2 or the campaign complete on approval.

## 4. Detailed Edit Proposals

### PRD-equivalent and UX

**Existing:** SPEC/`prototype-scenarios.md` require one local detector and one cloud multimodal model on the same evaluation set; DESIGN/EXPERIENCE show provider comparison without a winner.
**Proposed:** No edit. The chosen candidate changes implementation and admission, not the product outcome or user flow.

### Architecture

1. **AD-7 and candidate table.** OLD: `Grounding DINO Tiny CPU × GigaChat-2-Max`; `GigaChat GigaChat-2-Max paid corporate`. NEW: `Grounding DINO Tiny CPU × an admitted Yandex AI Studio Qwen3.6 35B profile in the owner's account`; candidate table names its exact requested model URI and requires returned-identity readback. The model remains a candidate, never an automatic winner.
2. **AD-37.** OLD: `The required cloud comparison candidate is paid corporate GigaChat-2-Max`. NEW: `The required cloud comparison candidate is Qwen3.6 35B in the owner's Yandex AI Studio account for an allowlisted prototype image set; the profile records exact endpoint, requested and returned model URI, adapter/prompt/schema hashes, runtime limits, account/data evidence, and remaining identity gap.` Keep local, RF-DETR, Kimi, and licensing decisions unchanged.
3. **AD-38.** OLD: `future customer's paid account` and `GigaChat additionally requires verified upload → delete behavior`. NEW: `the intended owner's active paid Yandex Cloud account` with current model access, quota, applicable commercial/data/retention terms, approved image scope, served identity, and bounded strict-schema image canary; an inline image request uses `store=false` and logging controls where supported, and its provider retention is disclosed. No provider-file deletion is asserted without a provider file. Real construction-site uploads remain blocked without their own rights and data approval; provider failure has no fallback.
4. **Cloud-retention table and deferred permission statement.** OLD: upload-delete canary and organizer images authorized for admitted GigaChat. NEW: distinguish private application artifact deletion from provider data handling, and state that only specifically owner-approved images may be sent to the admitted Qwen profile. An approval for AI Studio is not a blanket approval for new images.

### Epics and stories

1. **NFR15 and Additional Requirements.** OLD: future-customer paid corporate cloud proof plus GigaChat-specific gates. NEW: current owner's paid Yandex Cloud account proof for bounded prototype use, model/quotas/terms and exact image authorization, served identity, strict-schema canary, and no fallback. Keep a separate gate for any later customer account or real-site data. Replace the fixed GigaChat comparison line with Qwen3.6.
2. **Story 4.2 title.** Keep `Admit the Required Cloud Candidate` and its key, so sprint tracking does not need renumbering.
3. **Story 4.2 AC1.** OLD: future customer's paid corporate GigaChat account, Russia/commercial/retention/quota/model gates. NEW: Given the intended owner's paid Yandex Cloud account and a declared approved prototype image set, when admission gates run, then account/model access, quota, applicable terms, data controls and exact image rights are evidenced; a missing gate keeps the profile draft and blocks upload.
4. **Story 4.2 AC2.** OLD: GigaChat upload, strict response, served identity, provider file deletion. NEW: Given an approved canary image, when the exact Qwen3.6 profile is called through ordinary invocation, then strict two-class output, response/request identity, served model URI, private input/native artifacts, and request data controls are recorded; timeout, malformed output, missing identity, or unauthorized input fails admission. No provider deletion claim is inferred from `store=false`.
5. **Story 4.2 AC3.** OLD: immutable GigaChat successor and moving-alias gap. NEW: immutable admitted Qwen successor records adapter/prompt/schema/reasoning/temperature revisions, limits, requested/returned URI, account and data evidence, allowed image hashes, and enabled authorization; disclose any hosted model revision that cannot be pinned.
6. **Story 4.3 AC1.** OLD: admitted Grounding DINO and GigaChat. NEW: admitted Grounding DINO CPU and Qwen3.6 plus the accepted Story 4.1 evaluation revision. Campaign freeze verifies the Qwen profile's authorized hashes include exactly the campaign inputs, while preserving all existing manifest and no-fallback requirements.
7. **Story 4.7.** Existing technical-detail AC already covers identity, commercial/data gates, and unresolved gaps; no edit.

### Implementation handoff

1. Review `codex/yandex-cloud-ai-studio-20260924` at `3d2ba454e784cef823c33151282fc74cbeba4976` against current `main` without switching or overwriting either worktree. Integrate only the needed observer, admission, authorization, executor, and tests, resolving divergence with Story 4.1's accepted revision and exclusion inventory.
2. Run locked local tests and an account read-only check, then a bounded allowed-image canary only under the exact owner-approved scope. Preserve transient credentials. Verify profile, run, invocation, and artifact readback separately from deployment.
3. Freeze a new immutable cloud profile if its allowlist or prompt changes. Keep prior branch comparison files as historical evidence. Story 4.3 creates the authoritative new campaign; Stories 4.4–4.5 execute and report it.
4. Update the blocked Story 4.2 implementation spec to the approved Qwen scope; synchronize `sprint-status.yaml` only to the verified story state using its project tool, then validate and read back the ledger.

## 5. Approval and Handoff

**Classification:** Moderate. Product owner approves this candidate and data-scope change; developer updates architecture, epics, implementation spec, and integration. Story 4.2 can be marked done only after an admitted enabled profile and complete evidence are read back. The later campaign/report remains separate work.

**Approval:** The owner explicitly approved this package on 2026-09-24. Architecture, Epic 4, and the Story 4.2 draft spec were updated in the current `main` worktree. The sprint ledger retains Story 4.2 as `backlog` until implementation evidence supports a transition. Code integration and cloud resource changes are separate handoff work; the `cloud` worktree was not changed by this course correction.

**Verification:** Architecture spine lint returned zero findings; the official sprint-status validator returned `valid: true` with no problems; the status readback shows `epic-4: in-progress`, Story 4.1 `done`, and Stories 4.2–4.7 `backlog`. `git diff --check` passed. These checks verify the planning edits and ledger consistency, not cloud admission, code integration, or a new comparison campaign.

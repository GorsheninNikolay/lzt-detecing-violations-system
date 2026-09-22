# UX and research reconciliation after course correction

## Scope

Reviewed the updated canonical `ARCHITECTURE-SPINE.md` against:

- `ux-designs/ux-lzt-detecing-violations-system-2026-09-21/DESIGN.md`
- `ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md`
- `research/technical-ai-candidates-for-construction-monitorin-2026-09-22/research.md`
- `research/technical-open-excavator-dump-truck-annotated-data-2026-09-22/research.md`

The review concentrates on the approved course-correction topics: candidate disclosure, prototype profile binding, hybrid deferral, Apple M3 Pro CPU admission, RF-DETR gating, and user-visible semantics. It does not reassess unrelated architecture decisions.

## Verdict

**CONCERNS — three concrete reconciliation fixes remain.**

The intended direction is otherwise coherent: Grounding DINO is the non-training MVP local path; GigaChat is gated before real-image use; RF-DETR is conditional and non-blocking; hybrid execution is rejected in the delivered MVP; comparison cannot publish a winner; and normalized user outcomes remain independent from provider-native detail.

## Findings

### RUR-1 — The spine repeats a dataset claim overturned by the final dataset research

**Severity:** High  
**Affected:** `ARCHITECTURE-SPINE.md` AD-7, line 69; AD-37, line 207  
**Evidence:** Dataset research lines 47 and 80; recommendations lines 51-54.

AD-7 says the organizer-linked Kaggle construction-equipment corpus has compatible YOLO labels for both required classes. The final dataset report instead finds that the organizer-linked Roboflow card has only 78 images, does not publish the required exact `excavator` and `dump truck` pair, lacks sufficient provenance, and is unsuitable as the two-class training corpus. AD-37 separately says the organizer-provided archive is unannotated and may be used only for demo/evaluation, so the spine is internally inconsistent as well.

**Required correction:** Remove the compatible-label claim from AD-7. Keep only the durable rule: RF-DETR remains draft and outside the required MVP comparison until an independently approved, rights-clear two-class corpus and split pass provenance, commercial-rights, group-disjoint split, sampled-label QA, and locked CPU smoke gates. Do not name the organizer archive as a training candidate.

### RUR-2 — The timeout source still permits optional MPS evidence to define the mandatory CPU baseline

**Severity:** Medium  
**Affected:** `ARCHITECTURE-SPINE.md` AD-30, line 171; AD-37, line 207  
**Evidence:** AI-candidate research lines 46-58 and 103-114; course-corrected M3 profile in AD-37.

AD-37 correctly makes Apple M3 Pro CPU-only the mandatory initial local admission profile and makes MPS optional. AD-30 still derives timeouts from the first full `CPU/MPS` smoke. That slash leaves two incompatible implementations: one team may freeze the timeout from the mandatory CPU run, while another may use the faster optional MPS run. It also weakens the agreed meaning of the M3 CPU baseline.

**Required correction:** For the delivered MVP, derive the provisional per-image and batch timeout from the first complete Apple M3 Pro CPU-only evaluation smoke. MPS and RTX profiles record their own measured latency and may receive later profile-specific timeout revisions, but they must not redefine or satisfy the mandatory CPU admission baseline.

### RUR-3 — UX still lets a retrying user choose a profile, while the updated architecture forbids UI profile choice

**Severity:** Medium, cross-artifact conflict  
**Affected:** `EXPERIENCE.md` line 209 versus `ARCHITECTURE-SPINE.md` AD-34, line 189  
**Evidence:** UX retry rule says the user may explicitly change the observer execution profile; AD-34 says interactive runs obtain an exact admitted revision from validated runtime configuration and the UI cannot choose or rebind it.

These contracts would produce incompatible implementations. A retry screen built from the UX source could expose a model selector, while the backend contract rejects any UI-selected profile. This also risks presenting a prototype candidate as a user-selected winner.

**Required correction:** Keep AD-34 as written because it implements the approved prototype-binding decision. Update the UX contract when UX artifacts are next refreshed: retry always creates a linked successor using the currently validated configured prototype profile; a profile change is an operator configuration change outside the user flow and still creates a new linked run. The technical disclosure must show the exact profile revision and the label `candidate / not a selected winner` in Russian.

## Confirmed alignment

### Provider disclosure and user-visible semantics

- AD-13 keeps provider detail out of the primary result path, matching the UX summary-first order.
- AD-34 preserves candidate status in technical disclosure rather than presenting a configured prototype profile as a winner.
- AD-36 provides the immutable invocation/profile attribution required by the Evidence Viewer.
- AD-20, AD-33, and AD-35 preserve the UX distinction between per-frame observation state, top-level result, and provider-native counts/confidence/geometry.
- AD-24 and AD-7 keep readiness separate from provider comparison and prohibit an aggregate winner, matching the `Готовность` surface.

### Prototype binding and fallback

- AD-18 and AD-34 bind exactly one immutable admitted profile before a run starts.
- Failure is terminal and retry creates a successor; no provider or hardware fallback can masquerade as the same run.
- A recorded last-known-good demo result must be labeled and cannot masquerade as live execution.

### Hybrid deferral

- The diagram marks hybrid as post-MVP.
- AD-18 rejects hybrid execution in the delivered MVP even though the profile schema can represent it.
- AD-34 defers active-provider publication, and the Deferred section repeats that both selection and hybrid execution are post-MVP.
- Neither UX document exposes hybrid selection, so there is no user-flow promise to implement now.

### Apple M3 Pro CPU admission

- AD-37 now resolves the previously open owner decision by naming Apple M3 Pro CPU-only as the mandatory initial local profile.
- MPS and RTX 3060 remain separate optional revisions; implicit CPU fallback cannot count as accelerator success.
- The UX `laptop` viewport refers to the client layout and does not conflict with inference-hardware admission.

### RF-DETR gating

- AD-37 correctly changes RF-DETR from primary to conditional/non-blocking.
- It requires a rights-clear two-class corpus, split, sampled QA, reproducible training identity, checkpoint hashes, and platform smoke before admission.
- The held-out 11-image evaluation set remains separate from training through AD-24 and the research contract.
- Grounding DINO remains viable without a training corpus, so an unresolved RF-DETR rights gate cannot block the MVP.

### Cloud and secret controls

- AD-38 requires the intended customer's paid account, Russia access, commercial entitlement, accepted data terms, quota, served-identity evidence, and upload-delete canary before organizer images leave the laptop.
- AD-24 retains per-fixture source rights and cloud-upload permission.
- The Secrets convention matches the research requirement that credentials never enter profiles, PostgreSQL, artifacts, UI, or logs.

## Recommended disposition

1. Fix RUR-1 and RUR-2 directly in the current architecture update before final review.
2. Preserve AD-34 and record RUR-3 as a required follow-up correction to `EXPERIENCE.md`; do not weaken the architecture to accommodate the stale UX sentence.
3. After those changes, the reviewed course-correction topics are consistent enough for epic/story refresh and another sprint-planning readiness gate.

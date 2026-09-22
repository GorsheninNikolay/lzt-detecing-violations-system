# Reality and Technology Evidence Review — Course-Corrected Spine

Reviewed artifact: `../ARCHITECTURE-SPINE.md`  
Review date: 2026-09-22  
Lens: current named technologies, candidate existence and fit, and whether the course correction introduced assertions not backed by research or observed reality.

## Verdict

**PASS WITH NON-BLOCKING IMPLEMENTATION GATES.** The course correction introduces no unsupported claim that a candidate already works, is fast enough, or is legally admitted. Its new load-bearing choices are project decisions: use the actual Apple M3 Pro workstation as the initial CPU-only baseline, bind one admitted candidate profile to each run, defer winner publication and hybrid execution, and keep RF-DETR conditional. Current official-source research supports the existence, identity, licensing labels, and documented interfaces of the named candidates. The remaining uncertainties are correctly expressed as admission checks or deferred decisions rather than architecture facts.

## Evidence matrix

| Spine commitment | Reality or research evidence | Conclusion |
|---|---|---|
| Apple M3 Pro CPU-only is the initial mandatory local baseline | A live CLI hardware readback on 2026-09-22 confirms the development machine is a MacBook Pro `Mac15,6` with Apple M3 Pro, 12 CPU cores, 36 GB RAM, and arm64. The course-correction proposal explicitly selected this machine; the spine defers any wider cross-hardware claim. | Reality-checked project baseline, not a claim that all ordinary laptops are equivalent. |
| Grounding DINO Tiny at revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e` | The 2026-09-22 AI-candidate research cites the immutable Hugging Face revision and official repository, records its Apache-2.0 label and CPU-only route, and explicitly says target-machine latency and MPS behavior remain unmeasured. | Candidate identity and documented CPU path are supported. Actual installation, full offline smoke, latency, memory, and output quality remain mandatory admission evidence. |
| RF-DETR Nano `rfdetr==1.10.0` at `0f432b6` remains conditional | Current official-source research verifies the release and Apache-2.0 label for the core Nano model. Separate dataset research finds no currently admitted rights-clear two-class corpus and recommends keeping Grounding DINO as the no-training MVP path. | Supported and conservatively scoped. The spine does not imply that RF-DETR training or target-device execution has succeeded. |
| Paid corporate `GigaChat-2-Max` is the required cloud comparison candidate | The 2026-09-22 research cites official model, structured-output, corporate-contract, commercial-use, tariff, and file-workflow documentation. It also records the unresolved new-account/Cloud.ru routing, retention/no-training, exact processing-region, quota, and moving-alias gaps. | Candidate existence and Russian corporate route are supported. AD-38 correctly blocks real-image execution until account-specific terms, entitlement, identity, quota, and upload-delete canaries pass. |
| Kimi `kimi-k3` is reserve, non-sensitive, and conditional | Official Kimi documentation in the research supports model existence, image input, and strict schema. The research does not establish Russian customer/payment/commercial/data eligibility. | Spine matches the evidence by excluding Kimi from the MVP comparison until live account and written-term gates pass. |
| Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.54, React 19.3, TypeScript 6.0.3, and Vite 8.3.0 | `review-versions-update.md` and `review-versions-final2.md`, dated 2026-09-21, trace every exact pin to official release sources and verify the selected frontend versions against the official create-vite template ranges. TypeScript 6 is documented as the compatibility line rather than the newest major. | Current and directly sourced. The course correction did not change these pins or introduce new stack-version claims. |
| Optional Apple MPS and Windows RTX 3060 profiles | The AI-candidate research documents official MPS/CUDA-compatible routes but explicitly marks target-device behavior and latency as experiment-required. AD-30 and AD-37 require separate evidence and reject implicit CPU fallback. | Correctly stated as optional profiles to test, not proven accelerator support on this project. |
| Per-run immutable profile binding, no fallback, post-MVP active selection and hybrid execution | These are system design decisions from the approved Sprint Change Proposal, not externally sourced technology facts. They are consistent with the researched limitation that cloud aliases move and device/runtime results are platform-specific. | No web lookup is required; the decisions prevent unsupported equivalence and hidden substitution. |

## Findings

### R1 — LOW: Runtime compatibility is still prospective

No implementation lockfile, detector adapter, offline model snapshot, or completed Apple M3 Pro CPU evaluation smoke proves that Grounding DINO, its selected Transformers/PyTorch runtime, and Python 3.13.15 install and execute together. The official-source review proves that each named item exists and documents a CPU route; it cannot prove the eventual locked graph or runtime behavior.

This is non-blocking for the architecture because AD-30 and AD-37 make the committed lock, frozen install, per-file hashes, actual-device record, and complete offline evaluation smoke prerequisites for profile admission. Implementation and sprint acceptance must preserve that distinction and must not describe the candidate as admitted before those checks pass.

### R2 — LOW: GigaChat availability is documentation-backed, not account-proven

Official documentation supports the exact request alias, image analysis, strict JSON Schema, paid Russian corporate contracting, and upload/delete workflow. It does not prove that the intended future customer's newly created account currently exposes the model, exact tariff, accepted data-use/retention terms, quota, or a requestable immutable revision.

This is already bounded by AD-38. The cloud-admission story must perform authoritative account readback and the strict-schema upload → invoke → delete canary before real construction images or comparison runs are allowed.

### R3 — INFORMATIONAL: The Apple M3 Pro baseline is deliberately local, not universal

The selected machine exists and matches the recorded non-secret hardware profile. Calling it the initial MVP “ordinary-laptop” baseline is an owner-approved scope choice, not evidence that the measurements generalize to other laptops. The new Deferred Decision correctly postpones a cross-hardware baseline. Reports should name the exact platform and avoid generalized performance claims.

### R4 — INFORMATIONAL: No stale technology assertion was introduced by the course correction

The changed decisions concern candidate binding, CPU baseline ownership, RF-DETR conditionality, and hybrid/selection deferral. Candidate and stack identities are backed by sources checked on 2026-09-21 or 2026-09-22. The research's own staleness policy requires monthly re-checks for model/package availability and immediate pre-commitment checks for account, pricing, contract, retention, and data-use terms; those checks remain operational gates, not missing architecture decisions.

## Evidence consulted

- `../../research/technical-ai-candidates-for-construction-monitorin-2026-09-22/research.md`
- `../../research/technical-open-excavator-dump-truck-annotated-data-2026-09-22/research.md`
- `review-versions-update.md`
- `review-versions-final2.md`
- `../../sprint-change-proposal-2026-09-22.md`
- Live non-GUI hardware readback on 2026-09-22; only the non-secret model/chip/core/memory/architecture facts are recorded here.


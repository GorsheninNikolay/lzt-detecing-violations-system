# Adversarial Architecture Closure Review — Final 3

**Target:** complete `ARCHITECTURE-SPINE.md` after the final lease, authorization, artifact-lifecycle, and stage-slot fixes  
**Lens:** Can two units one level below the spine obey every adopted decision and still make a blocking, high-, or medium-severity incompatible choice?  
**Verdict:** **PASS** — no blocking, HIGH, or MEDIUM seam remains.

## Closure verification

### Lease and startup recovery

AD-9 and AD-17 now use one authority: database lease expiry. Owner/token mismatch fences renewal and writes but cannot cause early terminalization. Startup performs artifact reconciliation and guarded expired-run recovery before readiness and work claims. An independently built readiness coordinator and recovery worker therefore agree on both ordering and eligibility.

### Authorization and provider-call boundary

AD-30 separates immutable admission evidence from CAS-guarded current execution authorization. AD-34 defines a PostgreSQL `ObserverInvocation` reservation, serialized with revocation on the same authorization row, as the architectural start of a provider call. AD-36 preserves the reservation and records uncertain completion without replay. Independently built authorization, executor, and adapter units now share one unambiguous before/after boundary.

### Publication and reconciliation lifecycle

AD-28 now distinguishes `pending_upload`, `content_verified`, `object_published`, and `referenced`. Digest, size, and final key are durable before promotion; `object_published` is reached only after final-key HEAD verification. A stranded `content_verified` intent has one prescribed result—metadata quarantine and a new intent for retry—while reconciliation remains unable to mutate bytes. Creator attribution and later deduplicated attachments are compatible.

### Pipeline failure shape

AD-1 now requires fixed ordered stage slots, not successful outputs from every stage. It aligns with AD-26 dependency skips and AD-35's rule that technical failure has no `ResultProjection`. Persistence, API, and UI units cannot legitimately choose an empty projection as an alternative representation.

## Whole-spine adversarial sweep

The full spine was rechecked across the remaining major seams:

- candidate/profile admission, execution authorization, retry allowlisting, and no-fallback binding;
- complete comparison manifest materialization, canonical cell ordering, recovery, and report denominators;
- CPU bootstrap admission, measured timeout derivation, accelerator separation, and RF-DETR deferral;
- hybrid representation versus unconditional delivered-MVP execution rejection;
- PostgreSQL lease/transition fencing and single-instance startup/readiness ordering;
- S3 publication, deduplication, integrity conflicts, health-probe isolation, and metadata-only reconciliation;
- four-state observations, rule eligibility, successful/failed result projection, and evidence attribution;
- cloud account/data gates, secrets, and invocation evidence;
- capability coverage, stack seed, structural seed, and deferred decisions.

For each area, the previously constructed competing implementations are now either prohibited by an explicit invariant or produce compatible persisted/API evidence. No remaining Deferred item is needed for the MVP's independently implemented units to interoperate.

## Conclusion

The architecture spine is ready to hand to epic/story planning. This PASS is limited to architectural consistency: it does not assert that the corresponding stories, code, migrations, tests, provider access, or evaluation evidence already exist.

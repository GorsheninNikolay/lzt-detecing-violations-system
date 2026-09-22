# Final Good-Spine Regression Review — Adversarial Fix Set

**Artifact:** `../ARCHITECTURE-SPINE.md`  
**Review date:** 2026-09-22  
**Lens:** full good-spine rubric after authorization, publication deduplication, health-probe, retry-authority, and run-recovery amendments  
**Verdict:** **PASS — the amendments close the adversarial seams without reopening any prior rubric finding; no blocking, high, or medium finding remains.**

## Fix-set verification

### Execution authorization — PASS

AD-30 now separates immutable admission evidence from mutable current permission through a CAS-guarded `ProfileExecutionAuthorization`. AD-34 persists the authorization revision at run creation and rechecks current authorization immediately before the first provider invocation. Revocation therefore prevents a call that has not started without rewriting the historical profile or an already-started invocation. AD-38's account/data gates are also rechecked live where their current truth matters. Reproducibility evidence and execution permission no longer share an incompatible lifecycle.

### Publication deduplication and crash recovery — PASS

AD-28 correctly treats final-object metadata as creator attribution rather than a one-to-one intent join. Before promotion or attachment, each intent durably records digest, size, final key, and `object_published` state. Later intents recover their shared-byte relation from those persisted values plus HEAD verification, so a crash before the reference commit does not depend on rewriting final-object metadata. Reconciliation remains metadata-only and cannot corrupt shared content-addressed bytes.

### Isolated storage health probe — PASS

The startup probe now uses collision-resistant keys under a dedicated `health/<startup-id>` namespace excluded from publication and reconciliation. Write plus HEAD/read verification and cleanup are all readiness gates. This avoids fake evidence intents, avoids quarantine of probe residue, and does not weaken the no-deletion rule for evidence namespaces.

### Retry authority and lineage — PASS

AD-34 closes both dimensions independently:

- expected-no-successor plus idempotency prevents retry forks and requires later retries to continue from the newest failed successor;
- omitted profile means the validated configured prototype revision, while an explicit end-user choice is accepted only from a server-provided admitted/enabled allowlist carrying `interactive_retry_allowed=true`.

Submission revalidates authorization and applicable cloud gates. The executor and adapters cannot silently choose another profile, so this remains a new explicit run rather than fallback routing.

### Restart recovery — PASS

AD-9 places guarded run recovery after artifact reconciliation and before readiness/claims, makes database lease expiry authoritative, and requires every pre-existing running run either to retain a still-valid database lease or be terminalized after expiry with dependency skips in one fenced transaction. AD-17 and AD-26 supply the exact terminal/error behavior and monotonic transition guards. A restart therefore cannot arbitrarily steal a valid lease or expose an expired interrupted run as current work.

## Full rubric regression

### Divergence coverage — PASS

The spine fixes all material cross-unit choices at feature altitude: typed pipeline and outcome contracts, version ownership, run/profile authorization, transactional claims and recovery, retry lineage, publication/deduplication/reconciliation, candidate binding, campaign scheduling and denominators, readiness reduction, and single-host operational startup. The amended seams each have one authoritative owner and evidence path.

### AD enforceability — PASS

Every adopted decision retains `Binds`, `Prevents`, and an enforceable rule. The new clauses use concrete persisted identities, states, CAS/expected-prior guards, namespace boundaries, transaction points, and readiness conditions rather than aspirations. No amendment weakens terminal immutability, no-fallback behavior, or evidence attribution.

### Deferred safety — PASS

Deferred active-provider publication, wider hardware portability, hybrid execution, horizontal scaling/separate worker topology, RF-DETR corpus admission, Kimi, Enterprise/AGPL, vector search, and future numeric thresholds remain non-blocking and have explicit revisit conditions. The new current authorization mechanism does not accidentally publish a provider winner or turn revocation into profile mutation.

### Canonical SPEC capability coverage — PASS

CAP-1 through CAP-6 remain covered. The amendments are operational safeguards only: they do not alter the two-class scope, four-state meanings, same-area ordered-series rule, non-judicial check-request boundary, complete evaluation cases, per-criterion readiness verdicts, or technology-selection neutrality. Revocation and retry behavior preserve, rather than reinterpret, old run evidence.

### Operational/environmental envelope — PASS

The delivered single-host topology now has explicit startup order and gates for migrations, PostgreSQL, isolated S3 health, artifact reconciliation, expired-run recovery, readiness, and work claims. Liveness remains process-only; readiness represents dependency and recovery safety. Scaling remains explicitly post-MVP.

### Seed minimality — PASS

The structural seed stays small. The startup sequence diagram gained only the health and recovery edges needed to communicate operational ordering; implementation detail remains in the ADs.

### Contradiction audit — PASS

- Immutable profile admission and current authorization are separate and consistently checked by AD-30/34/38.
- AD-28's creator metadata, per-intent stored digest/final key, deduplicated attachment, and metadata-only reconciliation are compatible.
- The health namespace is explicitly outside evidence publication and retention semantics.
- Retry selection remains explicit at new-run creation and does not conflict with AD-18's no-fallback rule.
- AD-9/14/17/26 consistently treat database lease expiry as authoritative and terminal writes as guarded/monotonic.
- No amendment conflicts with the post-MVP provider-selection and hybrid-execution deferrals.

## Low-level implementation notes

These do not require architecture changes:

- make the executor's normal claim/recovery iteration re-evaluate database-expired `running` rows after startup, using the already-fixed AD-17 transaction;
- give authorization revisions and advisory-lock identifiers concrete database constraints;
- test crash points at every AD-28 state boundary, including deduplicated attachment and absent-final-object quarantine;
- treat the health-probe cleanup as mandatory for readiness despite the prose term “best-effort.”

## Gate disposition

The architecture spine remains convergent, enforceable, SPEC-complete, and operationally bounded after the final adversarial amendments. It can proceed to backlog reconciliation and sprint readiness without another architecture edit.

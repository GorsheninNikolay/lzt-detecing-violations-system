# Adversarial Architecture Re-review — Course Correction Final

**Target:** `ARCHITECTURE-SPINE.md` after fixes to the six initial adversarial findings and startup/readiness closure  
**Lens:** Can two units one level below the spine obey every adopted decision and still make incompatible choices?  
**Verdict:** **NEEDS CHANGES** — all six original findings were materially addressed, but four newly exposed seams remain; three affect data safety or execution authorization.

## Closure of the original findings

- **Admission bootstrap:** closed by the explicit `purpose=profile_admission` run, sole draft-profile exception, snapshotted positive watchdog, and admitted successor revision.
- **Publisher/reconciler join:** substantially closed by `PublicationIntent`, named states, `tmp/<intent-id>`, object metadata, content-addressed final keys, advisory-lock fencing, and metadata-only quarantine. One deduplication crash window remains as Finding 2.
- **Comparison scheduling:** closed by atomic manifest materialization, canonical tuple order, lowest-key recovery, and manifest-derived denominators.
- **Retry lineage:** branching is closed by idempotent expected-no-successor creation. Selection authority remains open as Finding 4.
- **Result/check contract:** closed by one persisted/API shape, both references and rendered snapshots, and no projection for technical failure.
- **Hybrid schema:** closed by the discriminated union and canonical hash inputs while execution stays rejected.

## Residual findings

### 1. HIGH — Immutable profile status cannot revoke an admitted revision

**Decisions:** AD-18, AD-30, AD-34, AD-38

An immutable `ObserverExecutionProfileRevision` contains one of `draft|admitted|rejected|retired`, and all ordinary runs accept any exact revision whose stored status is `admitted`. A later immutable `retired` successor cannot change the old revision's stored `admitted` value. The spine does not define an authoritative lineage head, revocation record, or effective-status lookup.

Two compliant units can diverge:

- Submission checks only the bound revision and continues executing an old `admitted` cloud profile after terms, credentials, model identity, or data permission are revoked.
- Profile management follows the newest successor and rejects that same revision as effectively retired, even though AD-34 says the exact bound revision is admitted.

This is not just API incompatibility: it can authorize cloud upload after an AD-38 gate ceases to hold.

**Required fix:** Separate immutable profile content/admission evidence from current execution authorization. Bind one effective-status mechanism, such as immutable lifecycle events with a guarded current-status projection or a lineage-head record. AD-34 must validate both the revision's admission evidence and its current non-revoked authorization in the run-creation transaction. State which checks are frozen for reproducibility and which AD-38 gates must be live at submission/campaign execution.

### 2. HIGH — Content-addressed deduplication breaks per-intent reconciliation after a crash

**Decisions:** AD-17, AD-28

When a final object already exists and matches, AD-28 attaches it to the new intent. That object already carries the original creator's `publication_intent_id`; immutable content-addressed storage cannot also replace metadata with the new intent ID. The newly created intent initially persists only ID, idempotency key, and expected media type. The spine does not require the computed digest, size, or final key to be durably written to that intent before the final reference transaction.

Two compliant units can diverge after a crash between successful HEAD verification and reference commit:

- A reconciler searches objects by the new intent ID and finds nothing because the shared object is attributed to its creator.
- Another infers `sha256/<digest>` from an implementation-specific intent field or re-hashes a temporary object; if that field/object was not preserved, it quarantines the intent instead of attaching the valid shared object.

**Required fix:** Define object metadata as creator attribution, not a one-to-one intent join. Before promotion or deduplicated attachment, durably store calculated digest, size, and final key on the current intent in `object_published`. Reconciliation must join later intents to the shared immutable object through those stored values and HEAD verification, while never rewriting the object's creator metadata.

### 3. HIGH — Startup S3 smoke is outside, or conflicts with, the only defined write/delete protocol

**Decisions:** AD-9, AD-17, AD-28

AD-9 requires an S3 read/write/delete smoke before readiness. AD-28 says a `PublicationIntent` precedes S3 write, objects are immutable, and deletion requires a later retention policy. The spine does not exempt a probe namespace or define the smoke as non-evidence. It also says reconciliation scans “the AD-28 namespaces,” without locating the probe relative to them.

Two compliant units can diverge:

- Startup writes and deletes a random probe object outside publication intents.
- Another implementation treats every S3 write as AD-28-governed evidence, creates an intent, and then cannot delete it; a third writes into `tmp/`, crashes, and the next startup quarantines its health-check residue as evidence.

**Required fix:** Reserve a distinct non-evidence health-probe namespace excluded from AD-28 publication and reconciliation. Bind random collision-resistant keys, write/read/head verification, mandatory best-effort delete, and readiness failure if either verification or cleanup fails. Alternatively run a full publication protocol, but then removal semantics and reconciliation must be explicitly designed; the isolated probe is simpler.

### 4. MEDIUM — Retry profile selection still has no caller/authority contract

**Decisions:** AD-18, AD-34, AD-38

The updated spine prevents retry forks and revalidates cloud gates, but “a retry request may explicitly name another admitted revision” still does not say who may choose it. A public user-facing API that lists all admitted profiles and an operator/server-owned retry command restricted to configured profiles both obey the rule. They differ in cost exposure, disclosure of experimental profiles, and UI/API shape.

**Required fix:** Assign profile choice to one authority. For this bounded prototype, the smallest rule is: ordinary users request retry without a profile; application configuration supplies the current admitted prototype revision; only an authenticated operator workflow may name a different admitted revision. If end-user choice is intended instead, define the exposed allowlist and audit fields.

### 5. MEDIUM — Run recovery is not part of the startup readiness barrier

**Decisions:** AD-9, AD-14, AD-17, AD-26

Startup blocks readiness on artifact reconciliation but does not say when previously `running` runs with an expired or non-current lease are terminalized. AD-17 defines the transition but not its place in startup. Since AD-9 enables readiness and claims immediately after artifact reconciliation, independent executor implementations can recover interrupted runs before readiness, before the first claim, or only after their stale timeout.

This changes what the UI observes after restart and whether new work begins while old work still appears running.

**Required fix:** Add a guarded run-recovery pass to the startup sequence after artifact reconciliation and before readiness/claims. Bind whether the new process identity makes prior leases immediately non-current or whether expiry time is authoritative; then terminalize exactly those runs and dependency-skip their remaining stages in the same fenced recovery transaction.

## Final adversarial conclusion

The revised spine is markedly stronger and the original course-correction gaps are no longer blockers. The remaining HIGH findings are narrow and fixable without changing scope: define revocable execution authorization for immutable profiles, make deduplicated objects recoverable by every attaching intent, and isolate startup S3 probes from evidence storage. Closing them, plus the retry-authority and run-recovery ordering seams, would make the updated spine safe for independent story implementation.

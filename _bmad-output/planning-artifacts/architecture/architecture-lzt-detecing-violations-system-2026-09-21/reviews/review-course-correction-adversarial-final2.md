# Adversarial Architecture Re-review — Final 2

**Target:** `ARCHITECTURE-SPINE.md` after profile-authorization, dedup-recovery, health-probe, retry-authority, and startup-recovery fixes  
**Lens:** Can two units one level below the spine obey every adopted decision and still build incompatibly?  
**Verdict:** **NEEDS CHANGES** — the requested residual findings are substantively closed, but two concurrency/recovery contradictions remain HIGH and two lifecycle seams remain MEDIUM.

## Confirmed closures

- Profile content/admission is now separate from CAS-guarded current execution authorization.
- Later deduplicating intents durably retain digest, size, and final key without rewriting creator metadata.
- Startup health probes use an isolated, non-evidence namespace.
- Retry choice is limited to the configured profile or the server-provided interactive allowlist.
- Run recovery is explicitly inside the startup readiness barrier.

## Remaining findings

### 1. HIGH — Startup run recovery has contradictory lease authority

**Decisions:** AD-9, AD-14, AD-17

AD-9 says database lease **expiry is authoritative** and readiness waits for a prior running lease to expire before terminalization. AD-17 says a running run with an `expired/non-current` lease becomes failed. After a process restart, the former owner's lease can be unexpired but non-current for the new executor.

Two compliant units can therefore disagree on the same row:

- The recovery component follows AD-17 and immediately fails the run because its owner/token is non-current.
- The readiness coordinator follows AD-9 and waits until the database expiry timestamp, treating expiry as the only terminalization authority.

Depending on integration order, readiness either opens immediately or remains closed for a lease interval, and the same run may be declared interrupted at different times.

**Required fix:** Choose one rule. The text already leans toward database expiry: amend AD-17 so only an expired lease is recoverable, and define ownership mismatch as preventing renew/write but not early terminalization. Alternatively define a durable process epoch that atomically makes earlier ownership non-current, then remove the claim that expiry alone is authoritative from AD-9.

### 2. HIGH — Authorization revocation still has a check-to-call race

**Decisions:** AD-30, AD-34, AD-38

AD-34 promises that revocation prevents a provider call that has not started, but only requires an authorization/gate recheck “immediately before” the external invocation. A database check and a network call cannot be atomic. Revocation can commit after the recheck and before the adapter sends bytes.

Two compliant units can diverge:

- The executor treats a successful read of `enabled` as sufficient and sends the image after a concurrent revocation commits.
- The authorization service treats the revocation as authoritative until the actual network send and reports that no call was permitted.

This is especially consequential for cloud data permission under AD-38.

**Required fix:** Define an atomic invocation-start reservation. In one transaction, create/fence the `ObserverInvocation` attempt using the expected enabled authorization revision; revocation and reservation serialize on the same row/revision. The committed reservation is the architectural definition of “started.” Revocation before it blocks the call; revocation after it does not cancel that already-authorized attempt, whose authorization revision remains evidence.

### 3. MEDIUM — `object_published` is recorded before the final object is published

**Decisions:** AD-17, AD-28

AD-28 moves the intent to `object_published` after hashing the temporary object but **before** exclusive promotion or deduplicated attachment. A crash in that interval leaves an `object_published` intent whose final key does not exist. The metadata-only reconciler may not promote or attach bytes, and the spine does not define whether it quarantines that intent, asks the publisher to resume it, or treats the missing final object as integrity failure.

Two compliant recovery implementations can therefore produce different terminal states and retry behavior for the same durable intent.

**Required fix:** Use a distinct pre-final state such as `content_verified` after persisting digest/size/final key. Enter `object_published` only after final-key HEAD verification succeeds. Then bind one crash action for `content_verified`: either an idempotent publisher-resume step performs promote/attach before reconciliation, or reconciliation marks it quarantined and publication retry creates a new explicit intent. Do not overload `object_published` with “publication planned.”

### 4. MEDIUM — The ordered-pipeline invariant conflicts with failed-run projection semantics

**Decisions:** AD-1, AD-11, AD-26, AD-35

AD-1 says every run materializes every filter through result projection. AD-35 says a technically failed run commits no `ResultProjection`, while AD-26 requires downstream stages to be skipped. “Materializes” can therefore mean either stage-row creation or successful output creation.

Two compliant units can diverge:

- One creates an empty/failed result projection to satisfy AD-1.
- Another creates only the fixed result-stage row, marks it skipped, and correctly stores no projection under AD-35.

That difference leaks into persistence constraints and API expectations.

**Required fix:** Amend AD-1 to say every run materializes the fixed ordered **stage slots**; a filter output is materialized only when that stage succeeds. Technical failure leaves downstream stages skipped and creates no `ResultProjection`, exactly as AD-26/AD-35 require.

## Final adversarial conclusion

The course-correction design and all previously requested fixes now converge well. The remaining work is narrow: unify lease recovery timing, create an atomic authorization-to-invocation boundary, give the pre-promotion artifact state an honest lifecycle, and align AD-1 wording with failed-run behavior. After those edits, no other blocking/high/medium incompatibility was found in the full spine.

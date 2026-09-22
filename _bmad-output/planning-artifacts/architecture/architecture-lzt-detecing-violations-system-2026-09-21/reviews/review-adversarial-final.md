# Final adversarial architecture review

## Verdict

**CHANGES REQUIRED, narrowly scoped.** The update closes all six prior findings at their main architectural seams: lifecycle transitions are monotonic and transactional; stage health has a backend-owned reduction; artifact admission/publication is fail-closed; plan identity is revision-scoped; provider comparison binds execution context; and pipeline records have canonical order and retry isolation. Four remaining contracts can still yield compliant-but-incompatible implementations, two of them directly affecting correctness or public-demo integrity.

## Prior-finding closure audit

| Prior finding | Result | Evidence in updated spine |
| --- | --- | --- |
| F1 run/stage state machine and atomicity | Closed | AD-26 fixes legal transitions, eligibility, terminal immutability, failure propagation, transaction scope, and expected-state/monotonic guards. AD-14 fixes one write-owning process and session scope. |
| F2 stage-health divergence | Closed | AD-27 fixes qualifying scope, winning run, non-success handling, precedence, area behavior, and backend ownership of status/reasons/recommendation. |
| F3 upload/artifact integrity and disclosure | Substantially closed; one public-access seam remains below | AD-28 fixes decoded validation, server naming, private serving, publication order, reconciliation, read verification, sanitization, and session-owned reads. |
| F4 plan identity and activation | Closed | AD-29 fixes revision-scoped keys, state ownership, semantic ID reuse, transactional unique activation, and explicit-only state mapping. |
| F5 provider-comparison reproducibility | Closed | AD-30 binds adapter/model/preprocessing/parameters/taxonomy/runtime and canonical comparison inputs, including errors/timeouts. |
| F6 pipeline ordering and retry presentation | Closed | AD-11 now atomically materializes the ordered registry and forbids retry-record merging or timestamp ordering. |

## Remaining findings

### R1 — Ordered-series time and frame identity are still not canonical

**Severity:** High  
**Touches:** AD-2, AD-8, AD-20, AD-21, AD-24, AD-30; time convention

**Compliant incompatible implementations:**

- The upload API assigns sequence by multipart order; the aggregation filter sorts by client-supplied capture time; the evaluation harness sorts the same canonical manifest by filename. Each can honestly call its input an “ordered series.”
- One implementation derives capture time from EXIF, another trusts a form field, and a third uses server receipt time. All can bind an observation period and ISO timestamps while producing different cadence/duration sufficiency for the same files.
- Rotated or duplicate images may be treated as separate frames by one implementation and deduplicated by checksum by another. Both preserve source checksums, but persistence evidence and periodic non-detection can differ.

**Impact:** The same uploaded series can be sufficient in one unit and `insufficient_data` in another, or can cross the persistent-non-detection threshold solely because of ordering semantics. That directly changes whether AD-21 permits a check request.

**Required tightening:** Define one immutable per-input series manifest owned at run creation. Each input needs a stable input ID, zero-based sequence ordinal, artifact checksum, and optional claimed capture instant with provenance (`user_supplied`, `manifest`, `exif`, or absent). State which field alone drives ordering and cadence for jury uploads and evaluation fixtures. Recommended MVP rule: explicit sequence ordinal is authoritative; capture instants are validated metadata used for cadence/duration, never inferred from filename or server receipt; absent/invalid required time data yields `insufficient_data`. Define whether identical checksums are rejected, retained as distinct observations, or deduplicated before policy evaluation.

### R2 — Shared-code authorization omits mutable global execution state and human records

**Severity:** High  
**Touches:** AD-4, AD-5, AD-16, AD-28, AD-29

**Compliant incompatible implementations:** AD-28 forbids shared-code sessions from mutating plan, rule, policy, or catalog **activation**, but does not cover `STAGE_EXECUTION_STATE`, acknowledgement, or notes. One API can let any jury session switch stages between `planned`, `active`, and `completed` or acknowledge another session's check; another can make those records read-only. Both obey the stated capability list. Because stage execution state is revision-global, one evaluator can change the primary overview while another is testing it.

**Impact:** The stable public prototype can present different “current stage” context during judging, and human judgement may be attributed to the system or another evaluator. This is not tenancy in the production sense; it is protection of a shared demonstration baseline.

**Required tightening:** State that reusable-code jury sessions cannot mutate any global project state, explicitly including plan activation, `STAGE_EXECUTION_STATE`, rules, policies, catalogs, seed runs, acknowledgements, and shared notes. If the demo must show these controls, either make them session-local disposable projections or place them behind a separate deployment-admin capability that is not exposed through the jury code. Specify whether user-created runs and any notes are visible only within the originating authorized session or deliberately shared read-only.

### R3 — Normalized detection shape is insufficient for independent adapter, renderer, and count UI work

**Severity:** Medium  
**Touches:** AD-6, AD-10, AD-20, AD-22; spatial-evidence convention; jury pipeline UI

**Compliant incompatible implementations:** The spine standardizes the per-class state and an optional normalized box, but does not say whether a `detected` class owns one detection or many, whether count is the number of boxes or a separate provider estimate, whether confidence is required/optional/forbidden, or which artifact owns the displayed-image transform. A cloud adapter can return `detected` with whole-frame evidence and count `1`; a local detector can return five boxes and count `5`; a renderer may draw provider-native boxes while the API exposes normalized boxes. All satisfy AD-6 and the spatial convention, but “how many objects were found” and annotated evidence can disagree.

**Impact:** Independently built adapters, result APIs, and UI can show inconsistent counts or overlays for the same normalized observation. Provider comparison may also compare class presence in one path and instance detections in another without saying so.

**Required tightening:** Choose one of two explicit MVP contracts:

1. **Presence-only:** the normalized contract promises only one class state plus optional evidence regions; no object count is claimed, and UI wording says the class was observed rather than “N objects found.”
2. **Instance contract:** a detected class contains zero-or-more typed detection instances with stable per-run IDs, optional confidence, normalized displayed-image geometry, and a defined count derived only from those instances; whole-frame evidence explicitly makes count `unknown`, not `1`.

Whichever is chosen must be shared by adapters, API, annotated rendering, evaluation labels, and UI language.

### R4 — Demo-code authentication transport and admission throttling remain implicit

**Severity:** Medium  
**Touches:** AD-15, AD-16, AD-28

**Compliant incompatible implementations:** A frontend can send the reusable demo code on every request in a query parameter, a backend can place it in a JavaScript-readable local-storage token, or the server can exchange it for a secure session cookie. All “grant access” using the code, but the first two can leak it through browser history, referrers, screenshots, reverse-proxy access logs, or script compromise, conflicting in practice with the no-secret-in-logs invariant. Implementations can also rate-limit only authenticated analysis calls while leaving code guessing unbounded.

**Impact:** Leakage or brute-force admission defeats the storage/spend bounds of the long-lived public URL. This does not justify full accounts, but the small authentication boundary needs one owner.

**Required tightening:** Define the code as a credential accepted only in a non-URL HTTPS request and compared safely; exchange it for a server-side or signed opaque session held in a `Secure`, `HttpOnly`, appropriate-`SameSite` cookie. Never persist the code in browser storage or return it to the client. Rate-limit failed admission attempts as well as authenticated submissions, and rotate the code without invalidating existing evidence. CSRF protection can be satisfied by same-site cookie policy plus an anti-CSRF mechanism for mutating routes; select one consistent approach.

## Additional adversarial checks passed

- A stale model result cannot overwrite `executor_interrupted` if AD-26's expected-state guard is honored.
- Failed retries cannot replace the last successful stage health, and predecessor evidence cannot be merged into the retry pipeline.
- Artifact publication has a safe cross-store direction: private object first, then reference; reconciliation can remove only objects that have no live reference. Implementations must ensure content-address deduplication checks all references before deletion, but this is a local algorithm consequence rather than a missing architecture decision.
- Activating a new plan cannot inherit stage state merely by stable ID, and the uniqueness constraint prevents two active revisions.
- Provider failures and timeouts remain visible in comparison denominators and cannot silently trigger fallback.
- Capacity exhaustion is already fail-closed by the Deferred contract: reject new work rather than delete evidence.

## Recommended disposition

Add R1 and R2 before decomposing stories: they decide series correctness and the public demo's mutation boundary. Resolve R3 before adapter/frontend work splits. R4 can be one concise access-session convention in AD-16 or AD-28 and should be fixed before public deployment acceptance criteria.

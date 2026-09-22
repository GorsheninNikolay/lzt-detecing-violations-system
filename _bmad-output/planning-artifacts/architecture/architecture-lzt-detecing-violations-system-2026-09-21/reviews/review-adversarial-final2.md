# Final adversarial architecture review — second fix set

## Verdict

**PASS.** No remaining blocking, high, or medium adversarial finding was reproduced. The second fix set closes all previously open contracts without weakening the earlier lifecycle, evidence, plan-revision, comparison, or public-access invariants. Independently built units now have one authoritative choice at each tested seam.

## Closure audit

| Adversarial seam | Result | Binding contract |
| --- | --- | --- |
| Run and stage lifecycle | Closed | AD-1 materializes rather than blindly executes every filter; AD-26 fixes legal transitions, predecessor eligibility, terminal immutability, single active stage, atomic output commits, failure propagation, and domain-insufficiency semantics. |
| Restart and late model output | Closed | AD-17 terminally fails interrupted runs; AD-26 expected-state or monotonic-revision guards prevent a late child-process result from overwriting that terminal state. |
| Jury pipeline truthfulness | Closed | AD-11 atomically creates the full ordered registry, renders by ordinal, preserves factual summaries/artifacts, and isolates retry records. |
| Stage-health reduction | Closed | AD-27 fixes eligible intent/state/evidence shape, plan/stage/scope key, provider filter, latest persisted completion, precedence, area behavior, and backend-owned wording. |
| Artifact integrity and publication | Closed | AD-28 fixes decoded admission, quarantine, server naming, content-addressed atomic promotion, reference commit, orphan reconciliation, checksum verification, private serving, and provider-response sanitization. |
| Plan identity and active revision | Closed | AD-29 fixes revision-scoped stage/state identity, semantic stable-ID reuse, unique transactional activation, and explicit-only state mapping. |
| Provider comparison | Closed | AD-30 binds execution profile and comparison batch inputs, parameters, taxonomy, preprocessing, runtime, failures, and timeouts. AD-7 and AD-18 forbid fusion and fallback. |
| Ordered-series identity | Closed | AD-31 freezes an immutable manifest, makes ordinal authoritative, defines time provenance and cadence behavior, excludes filename/receipt-time inference, and rejects duplicate checksums. |
| Public session isolation | Closed | AD-28 forbids jury mutation of global and human state; AD-32 binds run ownership and artifact reads to an opaque session subject. Seed evidence remains globally read-only. |
| Demo credential transport | Closed | AD-16 and AD-32 keep the code out of URLs, browser storage, artifacts, and logs; use secure HTTP-only same-site cookies, anti-CSRF protection, failed-admission throttling, and rotation without evidence mutation. |
| Cross-provider observation shape | Closed | AD-6 and AD-33 explicitly choose presence-only semantics; UI, rules, and metrics cannot claim counts, while provider-native instance data is secondary attributed evidence only. |

## New compliant-but-incompatible implementation attempts

### Attempt A — Upload order versus capture-time order

Rejected by AD-31: ordinal alone orders frames. Claimed capture instants affect cadence/duration only after the manifest is frozen; filename and receipt time cannot substitute. Missing policy-required time yields one defined domain result instead of an implementation-specific fallback.

### Attempt B — Failed retry replaces a prior successful health result

Rejected by AD-27: only succeeded `stage_evaluation` runs with the required evidence shape participate. Queued, running, failed, observation-only, and rule-ineligible runs remain visible but do not replace health.

### Attempt C — Jury user changes current stage or acknowledges shared evidence

Rejected by AD-28: jury sessions cannot mutate stage execution state, activation, seed runs, acknowledgements, or shared notes. AD-32 separately scopes private run reads.

### Attempt D — Cloud adapter reports one object while local adapter reports five

Rejected as a normalized-contract divergence by AD-33: neither value is a cross-provider object-count claim. Presence state drives rules and comparison; native count may appear only as provider-attributed secondary evidence.

### Attempt E — Query-string code and local-storage token

Rejected by AD-16 and AD-32: the credential must arrive in a non-URL HTTPS request, may not be persisted in browser storage, and is exchanged for a secure HTTP-only cookie session.

### Attempt F — Artifact row points to partial bytes after a crash

Rejected by AD-28: a closed temporary object is checksummed and atomically promoted before its reference commits; reads re-verify checksum and size. A pre-reference crash produces a private unreferenced object for reconciliation, not referenceable evidence.

### Attempt G — New plan revision inherits stage state by matching ID

Rejected by AD-29: state is revision-scoped and matching IDs never infer migration. Only an explicit operator-reviewed mapping may carry it.

### Attempt H — Remote-provider timeout disappears from evaluation denominator

Rejected by AD-30: comparison reports must account for all planned provider-fixture runs, including errors and timeouts.

## Residual low-level cautions for downstream acceptance criteria

These do not require another architecture decision and are not gate findings:

- Define the concrete `PolicyProfile` values already called out in Deferred before acceptance-criteria decomposition; otherwise the architecture is consistent but CAP-2/CAP-6 are not yet objectively testable.
- Make “persisted completion order” in AD-27 a concrete monotonic database field rather than relying on timestamp precision or unspecified query ordering.
- Artifact reconciliation must test reference counts before removing a content-addressed object shared by more than one artifact reference.
- Specify exact cookie lifetime, name, path, and `SameSite` value in the public-access story; these are implementation parameters under the already fixed AD-32 mechanism.
- Treat provider/model alias mutability honestly in evaluation reports when a remote service cannot return a concrete revision; AD-30 already requires recording the best available identity and runtime profile.

## Final disposition

The architecture spine is convergent enough for handoff. The three original SPEC questions remain deliberately parameterized rather than architecturally unresolved and must be assigned concrete values at the stated pre-acceptance-criteria gate.

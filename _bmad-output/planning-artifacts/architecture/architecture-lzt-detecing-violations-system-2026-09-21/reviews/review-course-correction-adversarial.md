# Adversarial Architecture Review — Course Correction

**Target:** `ARCHITECTURE-SPINE.md` updated 2026-09-22  
**Lens:** Can two units one level below the spine obey every adopted decision and still make incompatible choices?  
**Verdict:** **NEEDS CHANGES** — the course correction removes the original planning cycle, but three build-blocking seams and three material contract ambiguities remain.

## Findings

### 1. HIGH — Local-profile admission has a bootstrap cycle and no shared audit-execution contract

**Decisions:** AD-30, AD-34, AD-37

AD-34 requires every MVP `AnalysisRun` to bind an **admitted** profile before execution. AD-37 requires a complete CPU-only evaluation smoke before that profile can be admitted. AD-30 says the admitted profile contains timeouts derived from that first complete smoke. The spine does not define what executes the pre-admission smoke, what timeout/watchdog applies to it, or whether it is an `AnalysisRun` governed by the normal lifecycle.

Two compliant units can therefore diverge:

- The profile-admission unit executes a `draft` profile through a separate audit harness with an operator timeout, then creates a new `admitted` revision.
- The normal executor insists all executions are `AnalysisRun`s and rejects the same `draft` revision under AD-34; alternatively it runs the smoke with an arbitrary timeout embedded in the profile and thereby makes a different profile hash and admission record.

Those choices produce incompatible evidence, lifecycle, and profile hashes while each can plausibly claim compliance.

**Required fix:** Bind one bootstrap protocol. State whether an admission smoke is or is not an `AnalysisRun`; define the only status it may execute; define a fixed bootstrap watchdog distinct from the measured production timeout; and require the smoke to produce a successor immutable `admitted` revision containing the derived AD-30 timeouts. If the first smoke times out, specify whether admission fails without deriving a timeout or whether a separately recorded operator retry is allowed.

### 2. HIGH — Artifact publisher and reconciler do not share an enforceable orphan-discovery protocol

**Decisions:** AD-17, AD-28

The publisher must commit an intent, upload a private temporary object, promote it to a content-addressed key, and later commit the reference. The reconciler must find unreferenced objects and register quarantined metadata. The spine does not bind how an object carries its publication-intent identity, how temporary and final keys are enumerated, which intent states exist, or what “quarantined” permits.

Two compliant units can therefore diverge:

- The publisher names temporary objects with a random UUID and relies on process memory to associate them with an intent.
- The reconciler searches by intent ID or object metadata and cannot attribute those objects; another reconciler may classify every content-addressed object lacking a run reference as an orphan, including an object awaiting the final database commit.

The integrity-conflict case is also ambiguous: one implementation quarantines only a metadata record for the unexpected object at the final key, while another copies or moves the object. Both obey the word “quarantined,” but subsequent publication and evidence reads behave differently.

**Required fix:** Define the shared publication state machine and durable join key. At minimum bind intent ID/state, temporary-object namespace and intent metadata/tag, final-key derivation, the point at which an object is eligible for orphan classification, and quarantine semantics. Explicitly prohibit reconciliation from moving, deleting, attaching, or replacing bytes unless a later policy authorizes that exact transition.

### 3. HIGH — “Deterministic” comparison matrices do not define the same schedule or materialization boundary

**Decisions:** AD-7, AD-24, AD-34

AD-7 fixes three repeats and one cell per candidate × fixture, but does not define the tuple ordering. `repeat → fixture → candidate` and `repeat → candidate → fixture` are both deterministic and one-cell-at-a-time. Under provider drift, thermal effects, quota windows, or interruption they yield materially different evidence. The spine also does not say whether all matrix cells and their exact admitted profile revisions are materialized atomically when the campaign starts or are created lazily as execution advances.

Two compliant units can therefore diverge:

- A scheduler alternates candidates for each fixture and pre-creates the complete matrix.
- A scheduler runs all local fixtures before all cloud fixtures and creates each cell just in time.

A report validator or recovery worker built against one interpretation cannot reliably validate or resume the other. Lazy creation can also observe a later profile status or omit never-created cells after interruption, conflicting with the intended complete denominator.

**Required fix:** Define one canonical cell key and total order, for example `(repeat_ordinal, fixture_ordinal, candidate_ordinal)`, with each ordinal sourced from the frozen campaign snapshot. Require campaign start to atomically freeze and materialize all cells (or an equivalent immutable manifest) with exact profile revisions before the first execution. Recovery must select the lowest non-terminal cell in that same order, and the report denominator must come from the frozen manifest rather than observed runs.

### 4. MEDIUM — Retry profile selection has two possible owners

**Decisions:** AD-2, AD-18, AD-34, AD-38

Initial interactive runs use the exact profile from validated runtime configuration, but a retry request “may explicitly name another admitted revision.” The spine does not say whether that name is supplied by the end user/UI, by an operator-only API, or by server configuration. It also does not define whether multiple successors may be created concurrently from one failed run.

Two compliant units can therefore diverge:

- The web/API team exposes every admitted revision to the user and accepts any of them on retry.
- The application team treats candidate choice as server-owned and rejects everything except the configured prototype revision; a third implementation accepts concurrent retries and creates a forked lineage.

This changes privacy exposure, costs, and which run the UI presents as “the retry,” despite no hidden fallback occurring.

**Required fix:** Assign retry-profile choice to one authority and bind the API semantics. State whether arbitrary admitted revisions are selectable, whether cloud admission must be revalidated at retry creation, and whether a run may have multiple successors. If forks are allowed, the UI/report contract must not assume a single current successor; if not, creation needs an expected-no-successor guard.

### 5. MEDIUM — The result/check “closed contract” still permits incompatible payload shapes

**Decisions:** AD-20, AD-21, AD-35

AD-35 says a check request carries “immutable references **or** rendered values.” That is not one closed contract. A backend returning only observation IDs and a UI expecting embedded rendered values can both obey the spine and fail to integrate. The rule also does not bind whether a failed run has no `ResultProjection`, a partial projection, or a projection such as `not_analyzed`; AD-26 says technical failure fails the run but does not close this API/storage seam.

Two compliant units can therefore diverge:

- The projection writer stores only immutable IDs and expects a resolver to render them.
- The API materializes values into the projection and the UI has no resolver path.

**Required fix:** Choose one canonical persisted projection shape and one API DTO. If both references and rendered values are wanted, require both and define the rendered values as a snapshot derived in the same terminal transaction. State that technical failure creates no successful `ResultProjection` (or define the exact partial contract), while completed insufficiency remains a successful projection.

### 6. MEDIUM — The deferred hybrid schema is internally ambiguous

**Decisions:** AD-18, AD-30, AD-36; Deferred Decisions

AD-30 requires “hybrid boundaries (exactly one declared stage for non-hybrid),” while AD-18 says the data model may represent a future hybrid but execution is rejected in the delivered MVP. It is unclear whether `hybrid boundaries` is a required field on non-hybrid profiles, whether “one stage” means one observer invocation or one pipeline stage, and which fields participate in the profile hash.

Two compliant units can therefore diverge:

- One profile serializer requires a one-element `components`/boundary structure for every local and cloud profile.
- Another omits hybrid composition fields entirely for non-hybrid profiles and hashes a different canonical document.

They cannot exchange or verify the same supposedly immutable profile revision.

**Required fix:** Define a discriminated profile union. For `local_process|local_container|cloud_api`, hybrid-composition fields are absent and exactly one observer adapter/invocation boundary is implied or explicitly named. For `hybrid`, define the representable composition fields and canonical hashing now, while retaining an unconditional delivered-MVP execution rejection. Avoid the overloaded phrase “declared stage.”

## Adversarial conclusion

The updated spine now has the right product direction: prototype binding is no longer confused with winner selection; RF-DETR and hybrid work no longer block the MVP; and recovery is recognized as required behavior. It is not yet a complete consistency contract for independent implementation. Admission cannot be implemented without inventing a bootstrap path, reconciliation cannot reliably discover the publisher's orphans, and comparison scheduling/materialization can produce different evidence sets. Those three HIGH findings should be resolved before the spine is handed to story implementation. The remaining three can be fixed in the same pass without expanding product scope.

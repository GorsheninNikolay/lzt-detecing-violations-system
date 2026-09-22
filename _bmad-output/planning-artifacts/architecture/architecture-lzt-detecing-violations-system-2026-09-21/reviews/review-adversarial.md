# Adversarial architecture review

## Verdict

**CHANGES REQUIRED.** The spine has a strong domain boundary and a suitably small MVP shape, but independently built API, executor, persistence, plan, and UI units can still obey every current AD literally while producing contradictory lifecycle state, different stage-health summaries, or unsafe public artifact behavior. The first three findings are load-bearing because they affect evidence integrity and the jury-facing truthfulness of the system.

## Findings

### F1 — Run and pipeline-stage transitions have no authoritative state machine or atomicity rule

**Severity:** High  
**Touches:** AD-1, AD-9, AD-11, AD-14, AD-17; state-mutation convention

**Compliant divergence:**

- Executor A writes `AnalysisRun.running`, starts the model, writes the observation stage `succeeded`, then crashes before advancing the run. Startup recovery changes only the run to `failed/executor_interrupted`; the stage remains `succeeded`. This is arguably intended.
- Executor B handles the same crash by changing the currently `running` stage to `failed`, while executor C leaves it `running`. All comply with AD-17 because only the run's required terminal state is specified.
- The API's cancellation/error handler and the executor can both be application services and therefore both satisfy “only application services perform lifecycle transitions.” One commits `failed`, while the other commits a late `succeeded`; AD-9 and AD-14 do not define expected-state guards, transaction boundaries, or terminal-state immutability.
- One implementation marks the run `succeeded` when result projection succeeds even if an earlier stage is `skipped`; another rejects it because AD-1 says every stage “executes.” Both can cite the spine.

**Impact:** The persisted pipeline can cease to be reliable evidence. Polling can observe impossible combinations such as a terminal successful run with a failed stage, or a terminal failed run whose stage remains perpetually `running`. A retry may also race with late completion of its predecessor.

**Required tightening:** Add one transition table or invariant set covering both aggregates. At minimum:

- legal `AnalysisRun` and `PipelineStageExecution` transitions;
- which actor owns each transition;
- terminal states are immutable;
- stage `n+1` cannot start until stage `n` has an allowed terminal result;
- exact semantics of `skipped`, including which skip reasons may still permit run success;
- run terminal state is derived/validated against all stage states;
- run transition plus affected stage transition/output references commit atomically in one structured-store transaction;
- every claim/complete/fail write uses an expected prior state (or monotonic revision) so stale executor results cannot overwrite interruption/failure.

For a single-process MVP, this can remain a simple database transaction with conditional updates; no distributed lease is needed.

### F2 — Stage-health projection is underdefined and will disagree across backend and UI

**Severity:** High  
**Touches:** AD-4, AD-5, AD-7, AD-13, AD-17, AD-18, AD-19, AD-20, AD-21

**Compliant divergence:** A stage has (a) an older successful local-provider run with `no_signal`, (b) a newer failed cloud-provider retry, and (c) a successful run under a superseded plan/rule revision with `check_required`. One backend selects the latest run and reports `no_signal` or failure-as-`not_observed`; another chooses the worst historical health and reports `check_required`; the frontend independently applies a severity order and reports something else. Every implementation is “derived from linked runs” as AD-4 requires.

The same ambiguity occurs across multiple observation areas, multiple active stages, old plan revisions, insufficient runs, and positive plus negative class results. The spine also promises “one outcome” in AD-13 without defining how multiple eligible check requests collapse into that outcome.

**Impact:** The most visible jury-facing summary can contradict run details while all units remain nominally compliant. This is exactly the kind of independently chosen behavior the spine should prevent.

**Required tightening:** Give the result-projection owner a deterministic input scope and precedence contract. Specify, for example:

- only terminal successful runs for the selected active plan revision, stage, area, and configured presentation provider participate;
- whether the most recent run, a designated canonical run, or an explicit evaluation period is authoritative;
- failed/interrupted runs affect execution visibility but do not become machine health evidence;
- a total precedence order for `not_observed`, `insufficient_data`, `no_signal`, `check_required` and the conditions for each;
- deterministic reduction when several class checks or areas exist;
- backend alone emits the summary status, primary reason code, and recommended check; UI maps codes to text and never re-derives health.

### F3 — Public upload and artifact boundaries do not yet preserve immutable evidence safely

**Severity:** High  
**Touches:** AD-6, AD-10, AD-15, AD-16; artifact-integrity and logging conventions

**Compliant divergence / attack seams:**

- Checking the request `Content-Type` and byte size satisfies AD-16 literally while still accepting non-image content, polyglot files, huge decompressed pixel dimensions, malformed decoder inputs, or filenames containing traversal characters.
- A filesystem adapter computes SHA-256, inserts a reference, then moves the file; a crash leaves a dangling record. Another moves first and leaves an orphan on DB failure. Both satisfy “compute and persist SHA-256 before referenceable” without a publication protocol.
- “Never overwrite a referenced path” does not require verification on read, exclusive creation, content-addressing, private filesystem placement, or prevention of direct static serving. An attacker with the reusable shared code can potentially enumerate stable IDs or retrieve another evaluator's uploads if artifact authorization is not defined.
- AD-6 requires retaining provider-native output, while AD-16 says secrets must never appear in artifacts. Provider responses may echo signed URLs, prompt/input metadata, or user-supplied text. No sanitization boundary assigns responsibility before immutable retention.
- A reusable shared code limits admission but is not identity or tenancy. It does not by itself prevent concurrent users from viewing each other's runs, changing active plan/stage state, or exhausting retained storage.

**Impact:** Evidence can be corrupt, partially published, publicly disclosed, or permanently preserve sensitive provider data. Decoder abuse and unbounded decoded dimensions threaten availability of the required public prototype.

**Required tightening:** Define the upload-to-artifact publication boundary:

- generate server-side names; never use a client path;
- enforce request bytes, decoded dimensions/pixel count, supported decoded format, image count, and total run size; reject malformed/truncated content before creating a run;
- store outside the static web root and serve only through an authorized artifact endpoint with opaque unguessable IDs;
- write to a temporary object, fsync/close as appropriate, calculate checksum, publish by exclusive atomic rename/content-addressed key, then commit the reference; reconcile orphans/dangling references on startup;
- verify size/checksum before evidence consumption (and define corruption as a terminal safe failure);
- sanitize or envelope provider-native responses before immutable storage, with an explicit allow/deny policy for secrets and remote URLs;
- define shared-code authorization capabilities: public users may create/read their own browser-session runs, while plan/rule/policy activation and global mutations are deployment-admin operations; or explicitly accept shared visibility and remove mutation endpoints.

Encryption at rest and malware scanning can remain deferred for the hackathon if the accepted deployment threat model says so, but decoder bounds and non-public artifact storage should not be deferred.

### F4 — Plan identity, revision activation, and mutable execution state can split into incompatible models

**Severity:** Medium  
**Touches:** AD-2, AD-3, AD-5, AD-19; ID convention; ER seed

**Compliant divergence:** The ID convention says imported stage IDs remain stable across revisions, while the diagram places `WORK_STAGE` under a revision. Implementation A models `(plan_revision_id, stage_id)` as the stage identity and keeps lifecycle state per revision. Implementation B models a global `WorkStage(stage_id)` referenced by many revisions and keeps one lifecycle state across revisions. Both preserve stable IDs and immutable plan revisions, but activating a revised plan gives different current-stage state and different linkage for old runs.

The rule “one revision is active” also lacks an atomic activation invariant. Two imports/activations can temporarily or permanently create two active revisions unless uniqueness and transaction ownership are stated. It is unclear what happens to active/completed status when a new revision removes, splits, merges, or semantically changes a stage while reusing an ID.

**Impact:** Run lineage and the stage overview can silently attach facts from one plan revision to another. Teams implementing import, persistence, and UI can choose incompatible ownership boundaries.

**Required tightening:** Fix the identity model. Prefer revision-scoped stage definitions keyed by `(project_plan_revision_id, stable_stage_id)`, with execution-state records explicitly keyed to that pair. Reuse a stable ID only when semantic identity is preserved; otherwise require a new ID. Activating a revision is one transaction protected by a database uniqueness constraint for one active revision per project. Define whether lifecycle state is explicitly copied/mapped during activation or starts separately; never infer it by matching IDs silently.

### F5 — “Same evaluation set” does not make provider comparison reproducible enough

**Severity:** Medium  
**Touches:** AD-2, AD-7, AD-8, AD-18, AD-22, AD-24, AD-25

**Compliant divergence:** Two comparison runners use identical image checksums and policy IDs, but one resizes/orients images before adapter invocation, one sends originals; one applies current rule/catalog revisions, another reuses prior snapshots; cloud adapters use different prompt/system instruction, decoding parameters, or remote model aliases under the same component version string. Failed provider runs are excluded in one report and counted as failures in another. Every runner can claim distinct completed runs over the same evaluation set and policy identities.

**Impact:** CAP-6 can produce apparently authoritative yet incomparable metrics, and a mutable cloud model alias can make repeat-stability evidence irreproducible.

**Required tightening:** Define a versioned observer-execution identity that includes adapter code version, concrete model identifier/revision when available, preprocessing revision, inference/prompt parameters, and supported taxonomy mapping. A comparison batch should bind the exact evaluation-set, policy, rule, taxonomy, preprocessing, and runtime-profile revisions and create all provider runs from one canonical input manifest. The report must account for every planned provider/fixture run; errors and timeouts cannot disappear from denominators and need an explicit readiness outcome.

### F6 — Pipeline observability exposes stage truth but not ordering/attempt semantics

**Severity:** Medium  
**Touches:** AD-1, AD-11, AD-17; UI convention

**Compliant divergence:** “Fixed records with stable stage keys” permits eager creation of all records or lazy creation as stages begin. Polling clients can therefore render missing stages as nonexistent, pending, or failed. A retry is a new run, but the UI may merge predecessor evidence into the successor's pipeline because completed evidence “remains visible.” Timestamp ties or clock adjustments can also change ordering if the client sorts by time rather than a prescribed ordinal.

**Impact:** The jury-visible pipeline can appear to skip, reorder, or reuse work, undermining the explicit goal of proving that uploaded images are actually processed.

**Required tightening:** Define a canonical ordered stage registry with display-safe keys/labels and ordinal; materialize all stage records atomically with run creation; each run shows only its own stage records and artifacts; predecessor evidence is reached through an explicit retry link, never merged. Backend responses should include ordinal and state, and UI must render registry order rather than timestamp order. If very fast stages are intended to remain perceptible, retain completed states rather than artificially delaying or animating them.

## Coverage notes

- **Shared shapes:** Observation state is closed, but the provider-neutral spatial evidence needed for rendered detections is not explicitly fixed. If CAP-1/API/UI require boxes, masks, confidence, or per-detection IDs, those fields and coordinate semantics must be standardized before independent adapter and renderer work. If they do not, state that annotated images are adapter artifacts and no cross-provider geometric contract exists in MVP.
- **Artifact lifecycle:** Retention is correctly deferred, but capacity rejection needs a deterministic preflight rule so a run is not accepted when its complete bounded artifact budget cannot fit.
- **Public access:** Stable URL, persistent volumes, reusable access, spend ceilings, and secret injection are correctly captured. Availability behavior when a cloud ceiling is reached should surface a stable safe error code and must not silently switch providers.
- **UI semantics:** Summary-first is appropriate. All managerial labels should be backend-owned mappings from stable reason/status codes or versioned shared contract; otherwise frontend and report generation can phrase the same result differently.

## Recommended disposition

Resolve F1–F3 in the spine before story decomposition. Resolve F4 and F5 before persistence/import and evaluation stories are independently assigned. F6 can be folded into AD-11 with a small rule expansion. The remaining coverage notes may be explicit decisions or narrow Deferred items, provided their revisit condition precedes the affected story work.

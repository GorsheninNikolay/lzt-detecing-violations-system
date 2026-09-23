---
title: 'Inspect the Source-Bound Observation Result'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: 'b36ec87bdde4451ba934e29d0c24566300956d34'
review_loop_iteration: 2
followup_review_recommended: true
context: []
warnings: ['oversized']
deferred:
  - summary: >-
      Loading eight full-size source images for inline thumbnails may exceed mobile memory.
    evidence: |-
      The view creates object URLs for all inputs and retains them while open. A low-memory rendered run with eight maximum-size images is needed to establish whether this causes a user-visible failure.
    location: >-
      web/src/App.tsx:215
    severity: medium (unverified)
  - summary: >-
      Joined browser-to-backend behavior and rendered keyboard and zoom behavior remain unverified.
    evidence: |-
      The checked UI tests mock HTTP and the backend tests use ASGI with PostgreSQL/S3. A permitted rendered end-to-end inspection would settle focus, 200% zoom and joined behavior; the user's working agreement prohibits GUI use.
    location: >-
      web/src/App.tsx
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A completed run exposes observation records through GET, but the workspace has no result view, verified source-image route, or separate series evidence. A manager cannot inspect a state against its exact source frame.

**Approach:** Expose the persisted projection and run-scoped, integrity-checked artifacts; render the backend outcome, source-bound class rows, series evidence, and an accessible frame viewer in the existing run route.

## Boundaries & Constraints

**Always:** Show `Только наблюдения` and `Правило этапа не проверялось` only for a succeeded run with backend `observations_only`. Bind every observation to its exact input ID and ordinal, including duplicate images. Translate all four closed states and known reasons without promoting a frame non-detection to site absence. Provide a separate backend-projected series block for multiple inputs, with usable count, supplied-area context, canonical order, supporting frame references and persistence wording only when justified. Read image and native artifact bytes from the requested run's committed metadata through `read_verified`; show a specific integrity error while keeping text visible. Keep native data in technical disclosure, attributed to invocation and profile, with its non-rule disclaimer. Support keyboard, narrow viewport, and 200% zoom.

**Never:** Infer an outcome or series facts in the browser; return private S3 keys, credentials, or durable signed URLs; claim physical same-area verification from a submitted text field; show native confidence as a portable rule fact; show a result projection for technical failure.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|---------------|---------------------------|----------------|
| Succeeded single image | GET run with outcome, input and two class observations | Result summary and two state rows reference `Кадр 1`; source viewer opens verified JPEG | Missing or corrupt bytes show specific integrity notice; rows persist |
| Succeeded ordered series | Distinct inputs, possibly equal checksums | Each frame and class stays distinct; separate projected aggregate shows order and bounded evidence | Insufficient frames suppress unsupported persistence wording |
| Native artifact | Completed invocation with JSON evidence | Technical disclosure identifies exact frame, invocation, profile and checksum, and marks native data non-rule-driving | Failed verification reports artifact integrity failure |
| Failed or active run | No succeeded projection | Existing pipeline remains; no result is invented | Read retry remains available |

</intent-contract>

## Code Map

- `backend/app/adapters/postgres.py:632-645,676-708` -- final transaction writes `result_projections.snapshot`; `read_ordinary` currently returns only `outcome`, inputs, observations and native IDs. Persist usable input references, bounded persistence supporting references, submitted same-area declaration, and run-scoped artifact metadata; preserve repeatable-read snapshot.
- `backend/app/adapters/artifacts.py:65-79` -- reuse `read_verified` for digest and size verification before serving bytes; distinguish proven checksum/size mismatch from an S3 read outage without weakening verification.
- `backend/app/main.py:158-168` -- GET run route; add run-scoped artifact byte route with an opaque ID, explicit 404/integrity response and no S3 URL.
- `backend/app/application/executor.py:131-162` -- frame assessability and observer invocation are recorded per input; no new provider call is needed.
- `web/src/App.tsx:4-6,493` -- extend RunSnapshot and completed workspace; support old succeeded projections without a series aggregate, show source thumbnails beside observation rows, period, and a user-activated result jump; announce viewer frame changes and let the native dialog manage Tab focus. Keep partial failed-run observations and their source/native artifacts inspectable, explicitly incomplete, without displaying a ResultProjection.
- `web/src/styles.css` -- use existing full-night tokens and breakpoints for result cards and dialog.
- `web/src/App.test.tsx`, `backend/tests/test_ordered_series.py` -- test visible result and persisted projection/artifact contracts through HTTP or store boundaries.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:101-110,130-138,160-173,193` -- read-only outcome, series, viewer and integrity wording contract.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- synchronize verified Story 1.7 status.

## Tasks & Acceptance

**Execution:**
- `backend/app/adapters/postgres.py` -- persist source-bound series evidence including exact usable and dump-truck supporting input IDs at completion; expose it with the result snapshot and resolve artifact ID within the requested run to verified metadata.
- `backend/app/main.py` -- serve verified run artifact bytes with correct media type, 404 for wrong run/ID, explicit 409 for proven integrity mismatch and retryable 503 for S3 read failure.
- `web/src/App.tsx` -- render outcome, frame/class observations beside source thumbnails, observation period, series evidence and source/native viewer without losing text on byte errors; tolerate legacy projections without `series`, keep partial failed-run source/native evidence inspectable and explicitly incomplete, and provide an activated jump to the result.
- `web/src/styles.css` -- make result and viewer responsive and keyboard-visible.
- `backend/tests/test_ordered_series.py`, `web/src/App.test.tsx` -- exercise the matrix at the API and visible UI surfaces.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- reflect the verified workflow status.

**Acceptance Criteria:**
- Given a succeeded observation-only run, when its workspace loads, then its backend outcome reads `Только наблюдения`, states `Правило этапа не проверялось`, and every requested-class row names one translated closed state, applicable reason, exact input ID and `Кадр N`.
- Given a multi-image run including duplicate bytes, when its result loads, then observations remain separate by input ID and the Series Evidence block reports backend-projected usable count, submitted-area context, ordinal order and justified supporting or persistence references without a site-wide absence claim.
- Given a source or native artifact on the run, when the user opens it, then verified bytes and source metadata appear; if verification fails, then a specific integrity error appears while the result text remains available.
- Given a failed or incomplete run, when its workspace loads, then the pipeline remains visible and no completed result is shown.
- Given a succeeded run, when the user activates `Перейти к результату`, then focus moves to the result heading; background polling never moves focus.
- Given a viewer with native evidence, when the keyboard user tabs beyond the last toolbar button or switches frames, then the native disclosure is reachable and the new frame position is announced.
- Given a succeeded run stored before the series projection field existed, when its workspace opens, then source-bound observations remain readable and absent aggregate fields are labeled unavailable rather than crashing.
- Given a temporary S3 read failure or a verified digest mismatch, when an artifact is opened, then the UI distinguishes retryable loading failure from confirmed integrity failure and keeps observation text available.
- Given an interrupted series with completed frame observations, when its workspace opens, then those observations and their source/native artifacts remain inspectable with an explicit incomplete label and no completed ResultProjection.

## Spec Change Log

### 2026-09-23 — Review loop 1
- Trigger: the first derivation omitted visible source thumbnails, period, a result jump, and exact persistence-supporting input references; the viewer's custom Tab trap blocked native evidence.
- Amendment: make those outputs explicit in the Code Map, execution tasks, and acceptance criteria while retaining the intent contract verbatim. The submitted common area is a user declaration, not visual verification.
- Avoid: a result that requires opening every frame to associate evidence, or an aggregate claim without traceable usable inputs.
- KEEP: the run-scoped verified artifact route, one committed backend outcome, distinct duplicate-input IDs, isolated source/native errors, existing pipeline, and successful PostgreSQL/S3 integration tests.

### 2026-09-23 — Review loop 2
- Trigger: old succeeded series snapshots lack `series` and crash the new view; the artifact adapter reports S3 read outages as integrity failures; partial failed-run evidence was reduced to text.
- Amendment: require legacy projection tolerance, separate proven corruption from temporary storage failure, and allow inspection of partial artifacts without creating a result projection.
- Avoid: crashing on persisted older runs, falsely claiming checksum failure during an outage, or hiding retained evidence from an interrupted run.
- KEEP: verified artifacts scoped to the run, exact source ordinals and input IDs, source thumbnails, native provenance disclosure, period, series supporting IDs, user-activated result focus, and passing isolated PostgreSQL/S3 and web checks.

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 16 findings — high 0, medium 14, low 0, false 2, maybe-false 0
- findings:
  - `[medium]` `[patch]` Viewer Tab trap skips native disclosure — the handler only lists buttons and intercepts Tab after the last button; remove the custom trap and rely on native modal focus handling.
  - `[medium]` `[patch]` Frame changes are not announced — the live region reports zoom only; include frame position there.
  - `[medium]` `[bad_spec]` Persistence wording has no exact supporting input references — the series projection carries a count and sentence but no usable IDs; require backend-bound references.
  - `[medium]` `[bad_spec]` Observation period is absent from the result and viewer — GET supplies `context.period`; require its display with source metadata.
  - `[false]` `[reject]` Failed run loses previously visible partial evidence — the prior UI had no evidence view, so this change does not remove one; technical failure has no ResultProjection and retained pipeline stages remain visible.
  - `[medium]` `[patch]` Unrequested excavator renders as `нет` in series evidence — the UI must suppress that line when the class was not requested.
  - `[medium]` `[bad_spec]` Result has no source thumbnails beside observation rows — the current button-only frame card does not satisfy the evidence thumbnail pattern.
  - `[medium]` `[bad_spec]` Completed run lacks `Перейти к результату` — the established workspace UX requires an activated focus jump.
  - `[medium]` `[patch]` Sprint ledger still says backlog — update it at the verified workflow state.
  - `[medium]` `[patch]` Edge review independently found the native disclosure blocked by the Tab trap — same confirmed focus path as the first finding.
  - `[medium]` `[patch]` Edge review independently found the unsynchronized sprint ledger — same ledger line as the earlier finding.
  - `[medium]` `[patch]` Positive UI coverage for backend persistence wording is missing — add an assertion on a supplied statement; the current fixture only checks absence.
  - `[medium]` `[patch]` Successful native artifact text is not asserted in the viewer — assert the loaded frame-specific content.
  - `[medium]` `[patch]` Verification review independently found the Tab trap excludes `<summary>` — same confirmed focus path as the first finding.
  - `[medium]` `[patch]` Intent alignment found sprint tracking only in the spec — update the authoritative YAML ledger when status is verified.
  - `[false]` `[reject]` Same-area confirmation requires physical verification — FR4 defines explicit user-provided or confirmed area, and the UI correctly labels this a declaration rather than an image-derived fact.

### 2026-09-23 — Review pass 2
- verdicts: 15 findings — high 0, medium 11, low 0, false 2, maybe-false 2
- findings:
  - `[medium]` `[bad_spec]` Legacy succeeded series can crash — previously persisted projections have no `series`; require a readable fallback.
  - `[false]` `[reject]` Duplicate image bytes make the bounded persistence sentence false — each upload is intentionally a distinct input and the sentence is limited to those exact frames, not independent scenes or site absence.
  - `[medium]` `[bad_spec]` Partial failed-run source/native artifacts are inaccessible in the workspace — GET and the artifact route retain them; require an explicitly incomplete viewer.
  - `[medium]` `[patch]` Partial failed-run reasons are omitted — render the persisted reason with its observation.
  - `[maybe-false]` `[defer]` Eager full-image thumbnail loading could exceed mobile memory — quantify with eight maximum-size images on a low-memory device; the checked tests and static diff cannot establish the failure threshold.
  - `[medium]` `[patch]` Retrying one artifact revokes all rendered object URLs — isolate the retry to the failed artifact so healthy images stay available.
  - `[medium]` `[patch]` CSS transform zoom can clip an image outside scrollable layout — give the enlarged image a scrollable layout box.
  - `[medium]` `[bad_spec]` Storage read outages are reported as integrity failures — distinguish proven mismatch from retrieval failure in the adapter and route.
  - `[medium]` `[bad_spec]` Edge review independently found old projections without `series` — same persisted-compatibility defect as the first finding.
  - `[medium]` `[patch]` Prior frame native JSON can briefly appear under new frame metadata — tie loaded native content to its artifact ID.
  - `[medium]` `[patch]` Failed-run partial evidence has no visible UI assertion — add a case with retained frame and input ID.
  - `[medium]` `[patch]` UI tests omit `insufficient_data`, `not_analyzed`, and their reasons — assert both translated states and reasons.
  - `[medium]` `[patch]` Native provenance fields have no visible UI assertion — assert invocation, profile, revision and checksum.
  - `[maybe-false]` `[defer]` Joined browser/backend behavior, keyboard focus, and 200% zoom remain unverified — a permitted rendered end-to-end inspection would settle it; the user's working agreement prohibits GUI use.
  - `[false]` `[reject]` Same-area declaration is weaker than physical verification — FR4 requires explicit user confirmation, and the UI states that its value is user supplied, not visually verified.

### 2026-09-23 — Review pass 3
- verdicts: 14 findings — high 0, medium 10, low 1, false 1, maybe-false 2
- findings:
  - `[false]` `[reject]` Unobserved inputs disappear from a failed result — the partial-evidence surface is explicitly limited to frames with committed observations; the input manifest remains available through GET and no completed result is claimed.
  - `[medium]` `[patch]` Series order was rendered from run inputs instead of the persisted projection — the block now uses `series.input_order` with exact input references.
  - `[medium]` `[patch]` Retrying a source retained a revoked blob URL — retry now clears the displayed URL while only that source reloads.
  - `[medium]` `[patch]` A later native read failure could be hidden by an older successful response — the current error takes precedence and retry clears stale native content.
  - `[medium]` `[patch]` Authorization revision was labeled as profile revision — disclosure now names it as an authorization revision beside the immutable profile ID.
  - `[low]` `[reject]` Native JSON starts loading before disclosure expands — it is bounded secondary data for the selected frame, and delaying the fetch needs extra state without a demonstrated user-visible problem.
  - `[maybe-false]` `[defer]` Carried: maximum-size inline thumbnails may exceed mobile memory — a low-memory rendered run remains necessary to establish the threshold.
  - `[medium]` `[patch]` Source-image alternative text omitted observation context — alt text now includes translated frame observations and reasons.
  - `[medium]` `[patch]` Integrity, missing-object, and retry regressions lacked direct checks — tests now cover a same-size digest mismatch, real S3 missing object and bucket, source retry, and native failure after prior success.
  - `[medium]` `[patch]` A generic S3 HTTP 404 could be a missing bucket — the adapter checks the object error code before classifying missing committed bytes as an integrity failure.
  - `[medium]` `[patch]` Equal-byte frame cards were not asserted separately — UI tests now use distinct states per input ID and inspect each card.
  - `[medium]` `[patch]` Excavator supporting references lacked persistence and UI assertions — mixed-detection tests verify only the detected input appears in projection and series display.
  - `[medium]` `[patch]` Missing S3 object classification was not exercised — a real isolated-store read now verifies missing object integrity and missing bucket retryable failure.
  - `[maybe-false]` `[defer]` Carried: joined browser/backend interaction, keyboard focus and 200% zoom remain unverified under the no-GUI agreement.

## Design Notes

The submitted `observation_area` is a declared common area, not visual confirmation of a shared site. Label it accordingly. A usable frame is one with a completed observer invocation; unsupported-only and unassessable frames cannot justify persistence wording.

## Verification

**Commands:**
- `cd web && npm test -- --run && npm run build` -- visible result behavior and type/build pass.
- `cd backend && uv run pytest tests/test_ordered_series.py` -- projection and artifact API behavior pass against the isolated PostgreSQL/S3 test composition.
- `git diff --check` -- patch whitespace clean.

## Auto Run Result

Status: done

Implemented a source-bound result in the Run Workspace. A succeeded observation-only run shows the backend outcome, each requested class beside a verified source thumbnail, an ordered series block with exact supporting input IDs, period, and a native evidence viewer. Older projections without a series aggregate remain readable. An interrupted run shows its retained frame evidence explicitly as partial. The run-scoped artifact route verifies bytes before serving them and distinguishes a proven integrity mismatch from an S3 read outage.

Files changed: `backend/app/adapters/postgres.py` persists and reads the series projection and resolves run-owned artifacts; `backend/app/adapters/artifacts.py` classifies verified corruption, missing objects, and storage outages; `backend/app/main.py` serves verified artifact bytes; `web/src/App.tsx` and `web/src/styles.css` provide the result, thumbnails, series, and accessible viewer; `backend/tests/test_ordered_series.py` and `web/src/App.test.tsx` cover the API and visible behaviors; `sprint-status.yaml` records Story 1.7 as done.

Review: three passes triaged 45 findings. The final pass patched 9 medium entries representing 10 findings, rejected the unobserved-input claim because partial result rows intentionally represent committed observations, and rejected eager native loading because no material user harm was demonstrated. Two previously recorded unverified items remain deferred: maximum-series mobile memory behavior and joined rendered-browser behavior. Follow-up review recommended: true after multiple medium patches; a permitted real-browser check of source loading, focus, zoom, and maximum-series memory is the specific remaining risk.

Verification: the complete backend suite passed 45/45 against isolated local PostgreSQL and MinIO with the pinned CPU snapshot; `backend/tests/test_ordered_series.py` passed 6/6; web tests passed 22/22; web build and `git diff --check` passed. GUI inspection was prohibited by the user's working agreement, so rendered responsive behavior and end-to-end browser interaction were not verified.

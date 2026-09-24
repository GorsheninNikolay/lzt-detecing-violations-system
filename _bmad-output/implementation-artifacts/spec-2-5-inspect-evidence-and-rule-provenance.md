---
title: 'Inspect Evidence and Rule Provenance'
type: 'feature'
created: '2026-09-23'
status: 'done'
baseline_revision: '6ae69aea1a42cb2e3d1acf4bb3bd246e02a16079'
baseline_commit: '6ae69aea1a42cb2e3d1acf4bb3bd246e02a16079'
review_loop_iteration: 0
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      Verify native dialog focus containment and Escape closing in a browser-level test.
    evidence: |-
      The UI test replaces showModal and close with DOM stubs; it checks initial focus and restoration but cannot exercise the browser's native Tab loop or Escape behavior. No headless browser is installed, and GUI use is prohibited by the project instructions.
    location: >-
      web/src/App.tsx and web/src/App.test.tsx
    severity: medium (unverified)
  - summary: >-
      Verify the evidence layout at 320 CSS pixels and 200% zoom in a rendered browser.
    evidence: |-
      CSS wraps long identifiers and uses a narrow-width single-column grid, but the test environment has no browser layout engine and no headless browser is installed. A rendered viewport check would settle whether metadata remains visible without overflow.
    location: >-
      web/src/styles.css and web/src/App.test.tsx
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** A succeeded analysis exposes source frames, normalized observations, series evidence, and a human check, but the current layout mixes these details and places rule details before their supporting evidence. The viewer omits the source artifact ID and per-frame usability, so a manager cannot inspect all source-bound evidence in the requested order.

**Approach:** Present successful results from the backend `ResultProjection` as ordered observation rows, series evidence, source thumbnails, rule provenance, uncertainty, and (when requested) a human check. Make each source thumbnail open an accessible viewer that exposes frame identity, usability, observation text, artifact ID, checksum, and any provider-native evidence.

## Boundaries & Constraints

**Always:** Keep result wording and decisions backend-projected; do not infer class state, rule outcome, frame usability, or a site-wide claim in the UI. Preserve upload ordinal, input ID, source artifact ID, SHA-256, and backend usability membership for each frame. Use native `<dialog>` behavior for keyboard focus containment and Escape handling, restore focus to the thumbnail opener, and retain labeled button controls for navigation, zoom, reset, and close. At narrow widths, long IDs and hashes must wrap without hiding metadata. Attribute native data to the adapter, profile revision, invocation, input, preprocessing revision when present, and checksum; label it `Данные конкретного наблюдателя. Не используются правилом этапа.` Keep the check as a human recommendation, not a violation finding.

**Never:** Recompute or rewrite a `ResultProjection`, derive rule eligibility from provider-native output, omit source evidence after artifact retrieval fails, or add another backend endpoint or persistence model when the existing run and artifact APIs supply the required fields.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Successful rule result | Projection has frames, series, rule, uncertainty, and optional recommendation | Render evidence sections in the specified order and source-bound frame details | Missing optional projection text remains explicitly unavailable; do not invent it |
| Source artifact unavailable | Frame projection and input metadata exist, artifact bytes fail or fail integrity | Keep observation and source metadata visible beside a retrieval error | Allow retry; never substitute another frame |
| Keyboard viewer use | A source thumbnail opens the evidence viewer | Modal controls navigate, zoom, reset, and close; closing restores opener focus | Native dialog contains focus and Escape closes it |

</intent-contract>

## Code Map

- `web/src/App.tsx:7-13` -- run input, frame evidence, and projection types; add frame evidence to the projection type and render successful-run results from that projection.
- `web/src/App.tsx:19-89` -- verified source artifact loading and native `<dialog>` viewer; reuse its abort/retry behavior and native modal focus semantics, adding source identity and usability details.
- `web/src/App.tsx:91-102` -- current result order combines observations and thumbnails, puts the check and rule details first, and reads some rule data from `rule_snapshot`; reorganize this component around the required evidence sequence.
- `backend/app/adapters/postgres.py:715-746,791-827` -- read-only evidence: `ResultProjection` already contains ordered frame states, source artifact IDs, series usability, rule snapshot, uncertainty, and recommendation; run inputs provide ordinal, artifact ID, and SHA-256.
- `backend/app/main.py:164-188` -- read-only evidence: existing run and run-artifact routes expose the projection and integrity-verified artifact bytes.
- `web/src/styles.css:12` -- current result and dialog rules; extend responsive wrapping and result section styles without adding a layout dependency.
- `web/src/App.test.tsx:13-240` -- result and viewer tests; extend fixtures with the persisted projection shape and cover order, metadata, modal controls, and focus restoration.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` -- Story 2.5 remains backlog until work begins; synchronize only this story to `in-progress` and then `done` after acceptance verification.

## Tasks & Acceptance

**Execution:**
- [x] `web/src/App.tsx` -- render completed observations and rule details from `ResultProjection`; separate observation rows, series evidence, thumbnails, provenance, uncertainty, and the check panel in that order. Show each frame's ordinal, projection-reported usability, input ID, source artifact ID, checksum, and accessible viewer controls.
- [x] `web/src/styles.css` -- keep all result and viewer metadata readable at 320 CSS pixels, including long IDs, and let viewer controls wrap at narrow widths.
- [x] `web/src/App.test.tsx` -- assert section order and projection-only successful results; cover frame metadata, native evidence attribution, artifact failure/retry, navigation, zoom/reset, close, and opener focus restoration.
- [x] `_bmad-output/implementation-artifacts/sprint-status.yaml` -- mark Story 2.5 `in-progress` during implementation and `done` only after verification succeeds.

**Acceptance Criteria:**
- Given a succeeded rule-evaluation run, when I inspect its details, then per-frame Observation Rows, a separate Series Evidence block, source thumbnails, rule provenance, uncertainty, and any recommended check appear in that order and use backend-projected wording.
- Given a source thumbnail, when I open its viewer, then the source ordinal, backend-reported usability, observation text, input ID, source artifact ID, and checksum remain available, and keyboard-operated previous, next, zoom, reset, and close controls work with contained focus and restoration to the opener.
- Given provider-native evidence exists, when I reveal technical details, then the adapter, profile revision, invocation, input ID, applicable preprocessing revision, and artifact checksum are attributed, with native counts, confidence, and geometry labeled as observer-only data.
- Given source bytes cannot be retrieved or verified, when the result is displayed, then projected observations and identity metadata remain visible with a retryable, frame-specific error and no substitute image.

## Spec Change Log

## Review Triage Log

### 2026-09-23 — Review pass
- verdicts: 13 findings — high 0, medium 4, low 4, false 3, maybe-false 2
- findings:
  - `[medium]` `[patch]` Completed observation rows could disagree with source thumbnails about the frame ordinal — use the projection ordinal in successful rows; a fixture with a conflicting input ordinal now verifies that rows, thumbnails, and the viewer agree.
  - `[low]` `[patch]` An incomplete analysis could be labeled as though rule evaluation had not been attempted — show an unavailable rule status until the run completes; the partial-run test verifies the wording.
  - `[false]` `[reject]` A succeeded run could lack its projection — `finish_ordinary` inserts the projection and marks the run succeeded in one transaction, while `read_ordinary` reads a repeatable-read snapshot; the state cannot be produced by the service.
  - `[low]` `[patch]` A multi-frame observation-only result could hide an unavailable series block — keep the block based on completed frame count and show its existing unavailable message; a UI regression test covers missing series data.
  - `[low]` `[patch]` A check panel could lose its declared area when series details are missing — fall back to projection and run context; tests cover both fallback sources.
  - `[medium]` `[patch]` Optional rule metadata could hide an available result reason and supporting IDs — render those fields independently; the missing-rule projection test asserts both remain visible.
  - `[maybe-false]` `[defer]` Native focus containment and Escape behavior lack a real browser check — the test stubs native dialog methods and cannot verify the browser Tab loop or Escape path; a browser-level run would settle this, but no headless browser is available and GUI use is prohibited.
  - `[maybe-false]` `[defer]` The 320 CSS pixel and 200% zoom layout lacks rendered verification — CSS rules were inspected and wrap long identifiers, but a browser viewport check is needed to establish actual visibility.
  - `[false]` `[reject]` Verification outcomes were missing from the spec — finalization records the actual 42-test, build, and diff-check outcomes under Auto Run Result.
  - `[false]` `[reject]` Excavator supporting IDs could appear without an excavator row — both `projection.frames` and `series.excavator_supporting_input_ids` are built from the same backend evidence list, so the proposed state is unreachable.
  - `[low]` `[patch]` Single-frame and incomplete results lost the observation period — render the period when the series section is hidden; UI tests cover both paths.
  - `[medium]` `[patch]` Projected frame ordinals could be overridden by the input snapshot — the same ordinal fix keeps successful observation rows tied to their projection.
  - `[medium]` `[patch]` The same ordinal mismatch could label supporting evidence inconsistently — the projection ordinal fix covers this duplicate report as well.

## Design Notes

The backend projection already contains successful frame observations and series usability; retain `run.observations` only for partial failed-run recovery. Derive a frame's displayed usability solely from its membership in `result_projection.series.usable_input_ids`. The native dialog supplies focus containment and Escape behavior; the component remains responsible for restoring focus to the exact opener after close.

## Verification

**Commands:**
- `cd web && npm test -- --run` -- expected: all UI tests pass, including ordered evidence rendering, metadata, viewer keyboard controls, focus restoration, and retrieval errors.
- `cd web && npm run build` -- expected: TypeScript and production build succeed.

## Auto Run Result

Status: done

Implemented the ordered, source-bound evidence view for completed runs. Successful observation rows, series data, rule provenance, uncertainty, and check recommendations use the backend projection; source identity and artifact bytes stay tied to the matching input. The viewer exposes per-frame usability, source metadata, and attributed observer-native data, with keyboard-operable controls and focus restoration.

Files changed:
- `web/src/App.tsx` — render ordered projection-based evidence, preserve all input thumbnails, and show source/provenance metadata in the viewer.
- `web/src/App.test.tsx` — cover projection precedence, section order, metadata, missing projection fields, source failures, viewer controls, and focus restoration.
- `web/src/styles.css` — wrap long IDs and hashes and lay out thumbnails and viewer controls at narrow widths.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — move Story 2.5 through review to done.
- This specification — record the implementation, triage, verification, and residual browser checks.

Review: six patch entries applied (two medium and four low, covering eight reviewer findings); two findings deferred as browser-level checks; three findings rejected as unreachable or already captured by finalization. The Intent Alignment Auditor and Verification Gap Reviewer were not launched because the agent-thread limit was reached. The independent matrix audit and code review layers ran; every I/O matrix row has a passing UI test for the application behavior available to the CLI suite.

Verification: `npm test -- --run` passed with 42/42 tests; `npm run build` completed successfully; `git diff --check` passed. No backend or deployment changes were needed.

Follow-up review recommendation: true. This pass fixed two medium entries; browser-level focus containment/Escape and rendered 320 CSS pixel/200% zoom behavior remain unverified because no headless browser is installed and project instructions prohibit GUI use. These checks are recorded in `deferred`.

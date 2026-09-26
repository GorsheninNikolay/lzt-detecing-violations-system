---
title: 'Photo editing, actionable signals and processing progress'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'dispatch'
baseline_commit: 'f77faa3a76d24a144db3a9f38e522870c136f237'
review_loop_iteration: 0
context:
  - 'PRODUCT.md'
  - '.agents/skills/impeccable/reference/craft-floor.md'
---

<frozen-after-approval reason="User explicitly requested implementation of the accepted plan in full">

## Intent

Implement the accepted photo correction, signals and processing UX plan completely. Preserve the dark plum palette, Onest, Radix Themes, navigation and evidence semantics. This is authorized local implementation and verification, without deployment or GUI applications. Preserve unrelated work. Use self-explanatory code, existing capabilities, standard/native features and installed dependencies. No new animation library.

## Boundaries & Constraints

- Correction opens a spacious working mode with the photograph as primary content, compact object list and selected properties beside it on desktop and below on phones. Full geometry editing on both.
- Modes: select, draw/add, pan photo; zoom in/out, fit, pinch. Select via photo/list, move boxes, resize all eight handles, reclassify, delete; draw directly in any direction then select class. Numeric coordinates only in selected-object disclosure. Preserve keyboard controls and gesture-free alternatives.
- Use one image coordinate system across scale/pan; constrain boxes to image bounds. A completed drag creates one undo operation. Pinch/pan must not mutate geometry. Preserve drafts, reload recovery, undo/redo, pending exact-body/key retry, stale-version reconciliation and immutable separate correction copies. Owner queue uses the same editor, and every edit invalidates whole-frame verification required for approval.
- Signals show server summary: attention, insufficient-data and all open counts. Zero says `Открытых сигналов нет`, never safety/compliance. Keep workflow states new/in_progress/closed distinct. Rows name the actual equipment/reason, zone/work/time and workflow state.
- Detail order: brief issue and next action, large photograph with open-photo action and frame switching/supporting-frame markings, relevant saved-plan fact, workflow/comment. Full plan, analysis, identifiers and JSON in disclosures. Russian explanation/action for all five signal kinds. Deadline means unconfirmed completion; insufficient observations asks for usable frames. No-photo signals expose plan basis. Load errors offer retry.
- Reuse the result photo viewer (extract shared component if useful): full image without cropping, zoom/pan, frame switching, toggle boxes, Escape and focus restoration. Viewer leaves selected signal/comment intact. Preserve exact revision validation, never substitute latest plan.
- GET /api/signals adds summary with open_count, attention_count, insufficient_data_count, scoped by project/zone independently of state filter and 500-row list cap. Open means new/in_progress; insufficient_observations is insufficient, all other open kinds attention. Preserve new_count and refresh summary after patch. No migration.
- Incomplete analysis leads with a large photo, actual active-stage name, brief explanation and six-stage compact route. Confirmed completed steps have checkmarks; active step accent and gentle motion. Stage title/explanation transition 180–240ms; connector motion follows confirmed completion. Recognition-only photo sweep, only received object boxes. Series thumbnails without auto-advance. Server polling is authoritative: jump immediately to latest state and never delay completion for animation. Queued, failed, skipped and disconnected have distinct explanations; disconnection stops all motion. Preserve toggle and prefers-reduced-motion; CSS transform/opacity.
- Update existing DESIGN.md, EXPERIENCE.md and decision journal. Headless-only desktop/mobile, 200% and focus verification; visual work limited to one combined inspection and one repair confirmation. Do not launch GUI apps. CLI/headless browsers are authorized. No commits/push/deploy needed.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior |
|---|---|
| Scaled/panned editor, drawing either direction, eight handles | Correct normalized geometry, clamped bounds, one undo per drag |
| Touch pinch/pan, keyboard/numeric editing | View gestures leave objects intact; equivalent accessible edits available |
| Reload, unknown response, stale review, frame switching | Drafts retained by binding; same pending key/body; no cross-frame edits; approval resets |
| All signal kinds, no photo, failed loads | Russian reason/action, saved-plan basis, retry |
| >500 signals, filters, project/zone scope and patch | Summary counts entire selected scope, refreshed after mutation |
| Sequential/skipped poll stages, immediate finish, failure/reconnect | Actual server stage shown immediately; no invented progress or completion delay |
| Motion off/reduced/disconnected | Static state remains understandable; movement stops |

</frozen-after-approval>

## Code Map

- `web/src/Annotations.tsx`, `annotations.css`: existing AnnotationEditor/Queue, validObjects, shiftBox, restoreDraft, GeometryFields. Keep persistence and review protocol; replace desktop-only geometry and single handle.
- `web/src/App.tsx`, `result.css`: SourceImage/useArtifact, EvidenceViewer, makeResultFrames, ObservationResult, RunPipeline; existing viewer has zoom/native evidence and focus behavior to retain. RunSnapshot contains inputs/objects/stages. Extract shared viewer/types as needed, avoid circular imports.
- `web/src/SignalsPage.tsx`, `signals.css`: list/detail, drafts by signal, saved plan revision validation, preview and async loading. Existing API refresh after successful save.
- `backend/app/application/signals.py`: list_signals includes scoped due-signal generation, 500-row list, independent new count. Add aggregate summary in same scoped transaction.
- `backend/tests/test_site_workflow_db.py`, `web/src/Annotations.test.tsx`, `SignalsPage.test.tsx`, `App.test.tsx`: existing regression suites to extend.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/`: canonical DESIGN.md, EXPERIENCE.md and decision journal; supersede mobile limitation and old progress rules.
- Existing headless scripts under `_bmad-output/implementation-artifacts/` demonstrate CLI browser verification. Inspect available runtime and database fixtures before choosing test commands.

## Tasks & Acceptance

- [x] Implement full responsive editor and preserve correction/review lifecycle.
- [x] Implement summary backend and actionable signal/photo UI with shared viewer.
- [x] Implement authoritative photo-first six-stage processing scene.
- [x] Update canonical UX/decision documents and add meaningful regression coverage for matrix.
- [x] Run frontend build/tests, relevant backend tests and bounded headless checks; save evidence and exact limitations.

Given existing drafts or reviews, when editing/reloading/retrying, then no original analysis or uncertain request identity changes.
Given scoped signals, when filtering, limiting or updating, then summary reflects all open signals in scope.
Given desktop/mobile/200% layout, when editing or viewing photographs, then controls remain accessible and focus returns after closing the viewer.
Given server stage updates, when polls skip states or finish immediately, then UI reflects authoritative current state without playback delays.

## Implementation Notes

User supplied the accepted plan and explicitly requested implementation through verification; no additional scope/approval checkpoint is needed. All three surfaces remain in scope. Starting worktree was clean on main. Impeccable context launcher returned permission denied; existing product/UX context is authoritative instead. Local work only.

## Spec Change Log

## Review Triage Log


Independent review completed with three context-free reviewers. Each finding was checked against current source; verification-gap evidence was accepted as filed. Repairs stay within the accepted intent and preserve the working implementation.

| ID | Verdict | Evidence and disposition |
|---|---|---|
| B1 | medium | Annotation begin prevents native focus and does not focus the selected box; click then arrows can operate the old control. Patch focus in select mode and regression. |
| B2 | medium | At 300 objects the draw branch fails its limit predicate and falls into item movement. Patch select-mode guard and explain/disable drawing at capacity. |
| B3 | low | Extreme pan can place the image outside the viewport, but the always-visible Fit control restores it without affecting geometry. Reject extra clamping state/resize complexity; the plan bounds object geometry, not view translation. |
| B4 | medium | Processing thumbnail wraps SourceImage in a button; SourceImage emits a retry button on failure. Patch invalid nested controls and verify failed-thumbnail retry. |
| B5 | medium | Viewer parent captures pointers originating on retry buttons, redirecting click. Patch exclusion for interactive descendants. |
| B6 | medium | SourceImage lacks decode-error handling; HTTP 200 invalid image leaves a broken image without retry. Exposed on the new signal photo surface; patch image error state/retry. |
| B7 | medium | SignalPhoto treats absent frames during a pending/failed linked read as authoritative no-photo state. Patch distinct loading/error/confirmed-empty states. |
| B8 | medium | SignalPhoto omits result_projection frames/usability/context and profile although result viewer uses them. Patch reuse of authoritative projection data and metadata. |
| B9 | medium | Both plan presentations omit allowed/excluded equipment; exclusions are the deciding fact for equipment_not_planned. Patch relevant fact and full disclosure. |
| B10 | false | Re-enabling motion may replay connectors, but only server-confirmed succeeded connectors animate; no pending completion is fabricated or state delayed. Requirement is confirmed completion, not animation exactly once. |
| V1 | medium | Existing all-handle test checks only valid boxes and southeast interaction. A broken west update could pass. Patch parameterized exact persisted edge/undo assertions for all handles. |
| E1 | medium | Switching away from invalid numeric geometry hides the affected object's fields while global submit remains disabled. Patch visible pending-object recovery controls. |
| E2 | medium | Same independently verified pointer-capture defect as B5; group repair with B5. |
| E3 | medium | New headless harness only logs failed booleans and exits zero. Patch nonzero exit status on any failed assertion. |

## Verification

Run `npm run build` and `npm test -- --run` in web. Run relevant backend pytest using repository environment, including database-backed summary >500/filter tests if database available. Run a CLI headless desktop/mobile/200%-zoom focus/gesture/motion check, capture one visual inspection and at most one repair confirmation. Record commands, results and gaps, without claiming deployment or physical-device verification.


### Implementation verification (2026-09-26)

Implementation is ready for independent review. Production build passed; frontend suite passed 173 tests across 8 files. Coordinator ran the isolated backend suite with 36 passing tests, including 530-row summary/filter/scope/PATCH coverage. Final headless confirmation passed 123 checks across 320/390/768/1440px, editor/signals/progress CSS 200%, keyboard/pointer/CDP pinch, owner verification, viewer focus/comment and authoritative motion states. One combined initial visual inspection and one repair confirmation completed.

Evidence and exact limitations: [verification report](photo-editor-signals-progress-verification/README.md), [frontend tests](photo-editor-signals-progress-verification/tests.txt), [build](photo-editor-signals-progress-verification/build.txt), [headless checks](photo-editor-signals-progress-verification/confirmation-checks.json). Physical devices, screen readers, real browser-toolbar zoom, deployment and live model execution remain unverified. No migration/dependency/commit/push/deploy was performed.

### Review repair verification

All accepted review findings B1/B2/B4–B9/V1/E1–E3 were repaired and covered by targeted tests; E2 shares B5's fix. B3 and B10 were rejected with evidence above. No deferred findings. Final coordinator verification: 190/190 frontend tests, successful production build, 123/123 functional headless checks with screenshots disabled, and independent viewer retry before/after evidence (false/false to true/true). Test-only TypeScript options were removed afterward; 134 affected tests and the final build passed. Backend remained unchanged after its 36-test pass. The bounded initial and confirmation screenshots were not repeated.

A local completion commit is authorized by the applied build workflow. No push, deployment or application-data mutation was performed.

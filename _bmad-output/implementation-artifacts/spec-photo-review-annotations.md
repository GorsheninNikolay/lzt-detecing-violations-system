---
title: Photo-first review, annotation correction and truthful analysis motion
type: feature
created: 2026-09-26
status: done
route: dispatch
baseline_commit: 30db3c3be44bef4faddac3223d4da3173287c341
review_loop_iteration: 0
context:
  - PRODUCT.md
  - .agents/skills/impeccable/reference/craft-floor.md
---

<frozen-after-approval reason="User explicitly requested implementation of the supplied complete plan">

## Intent

Rebuild the everyday journey: upload photos, see results, inspect objects, suggest corrections. Keep Onest, plum palette, team logo, existing workflows and evidence boundaries. Implement all three authorized deliverables: photo-first composition/accessibility, visitor-to-admin annotation review/export, and expressive server-driven analysis motion. Fine-tuning is out of scope.

## Boundaries & Constraints

Never launch or control GUI applications. Use CLI/headless verification only. Preserve unrelated work; no branch switching, deployment, commits or remote operations are required. Prefer current patterns, standard library, CSS/Web Animations; no new animation dependency. Original observations, conclusions and model boxes remain immutable. Approval records data, never promises immediate accuracy gains.

Visitor corrections edit a separate per-frame copy. Desktop supports add, move, resize, reclassify, delete; phones reclassify/delete. Synchronize image/list selection; include undo/redo, keyboard manipulation, numeric geometry, local run/frame-bound drafts, unchanged-body/key retries after unknown responses, preserved work on network failure. Submission becomes pending review. Admin has an annotation queue, original/corrected comparison, editing, approval and rejection with reason. Whole-frame review is mandatory before collection inclusion. Version records link input checksum, objects, model profile and original frame. Export only selected approved versions to ZIP with oriented images, COCO and provenance; deduplicate frames and exclude reserved evaluation materials.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior |
|---|---|
| Empty frame, repeated classes, profile without boxes | Editable empty/repeated object lists; stable object identities; text observations remain available |
| Undo, reload, unknown submit response, network failure | Restore bound draft, undo/redo actual edits, retry identical request; no data loss or duplicate proposal |
| Concurrent administrative changes | Reject stale expected revision; preserve edits and explain reload/reconcile |
| Partial visitor correction | Cannot approve/export until explicit whole-frame verification |
| Export orientation, duplicate, reserved or unapproved source | Match displayed coordinates and selected version; reject unsafe inclusion; preserve originals |
| Queued, long-running, skipped stage, instant completion | Truthful server state, current human-readable step, no synthetic boxes or artificial completion delay |
| Error, disconnect, reduced motion or disabled motion | Distinct textual states; stopped sweep during reconnect; all content usable without animation |

</frozen-after-approval>

## Code Map

- `web/src/App.tsx`: ObservationResult, SourceImage/useArtifact, RunPipeline, project overview/upload/plan; normalized xyxy boxes, current full-original thumbnail fetches.
- `web/src/Admin.tsx`, `engagement.ts`, `PublicSupport.tsx`: session/CSRF and pending-request precedents. `FramePreview.tsx` only handles local uploads.
- `web/src/{styles,premium,result}.css`, `AppHeader.tsx`: existing tokens, conflicting responsive header and skip-link layers.
- `backend/app/application/engagement.py`: router auth, CSRF, request validation, rate limits; `main.py` mounts routers and serves verified artifacts.
- `backend/app/adapters/postgres.py`, `artifacts.py`: immutable original records and verified S3 reads. `domain/observations.py`: normalized displayed/EXIF orientation.
- `backend/migrations/versions/`: add additive annotation schema using existing migration conventions.
- `evaluation_set_revisions.manifest` and `backend/admission/exclusions/held_out_evaluation.json`: reserved evaluation checksums; exclusion must fail closed.
- UX authority: `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/{DESIGN,EXPERIENCE}.md`. Existing screenshots/headless scripts under `_bmad-output/implementation-artifacts/project-workspaces-verification/`.

## Tasks & Acceptance

**Execution:**
- [x] Add separate annotation service/router, immutable version schema, admin optimistic concurrency and authenticated export; meaningful API/database tests.
- [x] Implement visitor editor and admin queue/comparison/review/export with durable draft/retry behavior and focused frontend tests.
- [x] Recompose results: short outcome, photo, linked numbered objects, disclosed basis/details. Desktop large image beside objects; phone photo before long text. Explain model score in details; capture time once per frame; unsupported classes collapsed.
- [x] Recompose projects/overview around existing projects/recent runs/attention, creation as distinct action; upload first with area nearby and extra settings disclosed. Replace plan equipment multiselects with labeled checkbox groups, retaining work/area context. Fix project time-field error association.
- [x] Fix skip-link layering, header wrapping at intermediate widths, remove masking overflow; use efficient server thumbnails, minimum 44px targets. Admin feedback phone detail gets focused screen and return to selected row.
- [x] Implement photo-centered analysis scene with sweep and compact steps tied to server state; protocol disclosed with formatted dates. Real received objects only; textual observation fallback; motion toggle and reduced-motion styling; <=500ms result transition without delay.
- [x] Update existing DESIGN.md/EXPERIENCE.md with explicit supersession of old composition/motion. Record verification evidence and remaining limits.

**Acceptance Criteria:**
- Given any result, when opened on a phone, then photo/objects precede lengthy explanation in DOM and visual order, with synchronized selection on desktop/mobile.
- Given corrected geometry, when reviewed and approved, then downloaded ZIP contains only selected approved versions and valid oriented COCO coordinates/provenance, without mutating source analysis.
- Given any processing state, when it changes or connection is lost, then scene reflects authoritative server state without simulated progress or delayed completion.
- Given widths 320/390/480/768/1024/1440, 200% zoom, long names and eight frames, when using keyboard, then controls/focus/errors and editor return remain accessible without unintended overflow.

## Implementation Notes

All goals are retained by the user's explicit instruction to implement the supplied plan. No further scope/visual approval is needed. Add migrations locally; apply only to isolated verification databases. No live dataset or inference run is authorized or needed. API naming can follow existing conventions; preserve security and immutable provenance. Bound preview generation and export size; checksum exclusion covers rotated copies by decoded/oriented content where needed.

## Spec Change Log

## Review Triage Log


| Finding | Verdict | Evidence and action |
|---|---|---|
| Blind 1: revision-keyed owner recovery | high | Storage key uses current review revision; queue reload mounts latest revision and cannot read old pending body. Recover by proposal identity; patch and regression test. |
| Blind 2: invisible export selection | medium | Checked version IDs survive queue refresh but latest-only rows remove their controls. Keep visible removable exact-version selection. |
| Blind 3: save beyond page one | medium | onSaved reloads offset zero; selected row may be absent, retaining stale revision and missing return target. Fetch detail and retain loaded rows. |
| Blind 4: concurrent queue reads | medium | load has no guard/generation; same-offset repeated clicks append duplicates. Serialize/fence reads and deduplicate IDs. |
| Blind 5: invalid displayed geometry submits old box | high | Child validation is disconnected from submit and verification state. Block decisions until displayed coordinates are valid/committed. |
| Blind 6: resize lacks live preview | low | Handle captures pointer without move handler. Share move handling and preview position; direct correction. |
| Blind 7: approval before image load | medium | Verification and approval do not depend on successful source load. Gate whole-frame confirmation on image availability. |
| Blind 8: more than 32 export versions | medium | UI selection unbounded; backend rejects above 32. Enforce and explain current server limit. |
| Blind 9: completed draft history fills storage | medium | Up to 100 full arrays retained indefinitely after success; storage quota then blocks sends. Compact completed drafts; retain unresolved request identity. |
| Blind 10: review save loses focus | medium | Revision remount removes active button while focus effect watches only proposal ID. Restore heading focus on revision change. |
| Blind 11: no-op image controls | medium | SourceImage renders buttons without selection callback in viewer/pipeline. Use passive overlays when selection is unavailable. |
| Edge 1: revision-keyed recovery | high | Same verified cause as Blind 1; same patch and test. |
| Edge 2: later page save | medium | Same verified cause as Blind 3; same patch and test. |
| Edge 3: corrupt reason crashes | medium | Draft restore validates history but not reason; render calls trim. Validate persisted fields and pending request binding. |
| Edge 4: viewer selection claim | medium | Same no-op-control cause as Blind 11. Passive evidence overlays preserve viewer semantics. |
| Edge 5: tiny edge resize | medium | max(x1+.001,min(1,...)) can exceed one for x1>.999. Clamp after minimum; regression test. |
| Gap 1: conflicting export untested | medium | Existing tests only cover matching annotations. Add real API conflicting selection rejection. |
| Gap 2: DB evaluation exclusion untested | high | Static/mocked exclusion tests miss newly persisted manifests. Add DB-only reserved/rotated/missing-byte coverage. |
| Gap 3: pending-storage failure untested | medium | No annotation-specific failed setItem test. Assert no fetch, retained edits and recoverable send. |

| Visual 1: result summary inset | medium | Confirmed in all <=768 screenshots; remove zero-padding override. Scoped source/layout verification, no new screenshot audit. |
| Visual 2: admin tabs split short words | medium | Confirmed at390; wrap tab row and keep button labels intact. |
| Root: header create action targets hidden field | medium | New creation disclosure closes when projects exist; newAnalysis only focused hidden input. Open disclosure before focus and add regression. |

| Root: second pending request after success | high | New pending request now clears completed; remount regression passes. |
| Root: image error mutates frozen approval | high | Image failure no longer changes body-bound verification while pending; remount preserves exact body/key. |

All triaged findings above were repaired. No deferrals. Independent visual verdict: ship for the two source fixes only; no fresh pixel-level confirmation claimed after the authorized two capture batches.

## Verification

- `cd web && npm test -- --run` and `npm run build`: affected behavior and regression suite pass.
- Backend pytest using existing managed uv cache and explicitly isolated database/bucket: annotation/review/export/concurrency/orientation plus relevant existing suites pass. Never target application data.
- Headless CLI: one batched render inspection across specified widths/states, one confirmation after batched fixes; record screenshots and overflow/focus assertions. Do not claim physical-device or screen-reader verification. Reuse installed tooling without GUI.

Final checks: 162 web tests, production build, 35 targeted backend tests, six existing startup/read-result HTTP checks, and diff whitespace check passed. The 137-assertion headless confirmation covered all six widths before the final review repair batch; final repairs have targeted regressions and source review without a third capture batch. See [verification report](photo-review-verification/README.md). Physical-device, screen-reader, deployment and model-quality verification are outside the checked evidence.

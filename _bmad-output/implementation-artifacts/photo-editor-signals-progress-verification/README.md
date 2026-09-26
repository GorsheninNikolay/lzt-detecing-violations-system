# Photo editor, actionable signals and progress verification

Local implementation verified 2026-09-26. No GUI applications, deployment, push, live inference or physical devices were used. A local completion commit records the verified changes.

## Implemented behavior

- Full geometry editing at every width: select/draw/pan modes; reverse-direction drawing and class selection; move, eight resize handles and keyboard/numeric alternatives; zoom/fit/pinch and keyboard photo pan. One image coordinate space accounts for transforms. Drag preview commits a single history operation; pinch cancels geometry preview without changing the durable draft. Selected properties follow image/list selection. The correction workspace hides the duplicate result photo/list while open.
- Existing immutable correction/review and durable draft protocol is retained, including exact pending key/body retry, stale revision reconciliation and whole-frame verification reset. Owner and visitor use the same editor.
- Signals include scope-wide server summaries independent of workflow filter and list cap. All five kinds have Russian explanations/actions; deadline is unconfirmed completion, insufficient data asks for usable frames. Details show large source photo, supporting frames, exact saved-plan fact and manual workflow. Full basis/plan/analysis/identities are disclosures. Shared `EvidenceViewer.tsx` retains source integrity/native evidence, adds in-viewer box toggle and pointer pan, and restores focus without losing comment/selection.
- Incomplete processing leads with the photo and actual server stage, a stage-specific explanation and six compact states. Confirmed completions earn checkmarks/connectors, only recognition sweeps, user-selected thumbnails never auto-advance, and disconnection/reduced-motion/user opt-out stop movement. Poll updates jump directly to received state; completion has no animation delay.
- Canonical DESIGN.md, EXPERIENCE.md and .memlog.md supersede the old phone geometry limitation and progress rules.

## Verified results

| Check | Result |
| --- | --- |
| `npm run build --prefix web` | PASS after review; TypeScript and Vite production build, `final-build.txt` |
| `npm test --prefix web -- --run` | PASS after review; 190 tests / 9 files, `final-tests.txt` |
| Isolated backend suite, parent-run | PASS; 36 tests, two dependency deprecation warnings, 3.44s |
| `node .../headless.cjs confirmation` | PASS; 123 visual-confirmation checks, `confirmation-checks.json`; 123 post-review functional checks without screenshots, `final-functional-checks.json` |
| `git diff --check` | PASS |

Backend command executed by the coordinator against the separately provisioned `evidence_annotations_20260926` PostgreSQL database (localhost:55432, migration `0021_annotations`) and existing isolated S3 fixture:

```sh
source /private/tmp/lzt-annotation-test-env.sh
cd backend
.venv/bin/pytest tests/test_site_workflow_db.py tests/test_annotations.py tests/test_engagement.py tests/test_detected_objects.py -q
```

The added DB regression inserts 530 signals plus two foreign-scope rows and checks the 500-row cap, independent new/open/attention/insufficient counts, new/in-progress/closed filters, project+zone intersection and refreshed counts after PATCH. Existing real annotation lifecycle tests remain green.

Frontend regressions add reverse drawing under scaled/translated bounds, one undo, all eight handles including tiny edge boxes, pinch cancellation, post-draw class focus despite synthesized clicks, server summary refresh, all five Russian next actions, shared viewer frame/box/comment/focus preservation, skipped poll states and immediate completion. Existing reload, stale review, invalid numeric geometry, whole-frame gate and exact request retry tests remain green.

## Bounded headless inspection

Vite runs on localhost:15175. The checked-in harness uses a real image and deterministic API fixtures, not a live analysis backend. Chromium is launched with `headless:true` through the CLI; no GUI application is opened or controlled. Widths: 320, 390, 768, 1440. CSS zoom: 200% on editor, signals and progress. Checks include keyboard geometry and photo pan, reverse pointer drawing, class focus, one undo, real CDP two-touch pinch without draft mutation, photo-viewer Escape/focus/comment, owner editor and approval reset, six server stages, skipped polls, thumbnail retention, recognition-only sweep, offline/reduced/disabled motion and horizontal overflow.

One initial combined screenshot batch and one repair-confirmation screenshot batch were inspected, each with phone/desktop editor, signal and progress captures. Initial findings: inherited 240px source-image cap made primary photos small; correction showed a duplicate result photograph; synthesized click after a draw could reselect the old object. These were repaired. The initial 320px draw assertion targeted the fixed bottom navigation because the harness only minimally scrolled the photo; pointer-event logging established the target, then the harness centered the photo before gestures. Functional-only diagnostics took no screenshots. `initial-checks.json` retains the original failures; final confirmation has no failed checks. Class-focus assertions await the authored animation-frame focus, rather than racing it.

No additional visual-polish rounds were performed. Full-page images include existing fixed navigation and skip-link capture artifacts; the viewport overflow, focus and functional checks are separately recorded.

## Limits

CSS 200% zoom is verified; browser-toolbar zoom, physical-device touch, assistive screen readers, deployed runtime and model quality are unverified. Fixture UI checks do not prove production behavior; real API/database tests are reported separately. No schema migration or dependency was added. The local Vite process remains available for independent review.

## Independent review and final repairs

Three context-free reviewers examined the unified change and regression coverage. Accepted findings were repaired: pointer selection focus, drawing at the object limit, visible recovery for another object's invalid coordinates, exact eight-handle geometry assertions, non-nested thumbnail retry, viewer pointer capture and decode-error recovery, distinct signal photo loading/error states, authoritative projection metadata and complete saved equipment policies. Two suggestions were rejected: extreme view translation has the existing Fit recovery; motion opt-in only replays already server-confirmed connectors. No accepted findings were deferred.

The coordinator reran the full frontend suite (190/190), production build, and all 123 functional headless checks with `NO_SCREENSHOTS=1`. TypeScript initially caught six unsupported test-only Testing Library options; these were removed and all 134 tests in those three affected files passed again before the final successful build. No application code changed after the full suite. Unchanged backend retains the separately executed 36-test pass.

`viewer-retry.cjs` independently reproduced the actual browser pointer-capture defect before the fix and confirmed a new request plus a visible image afterward; see `viewer-retry-check.json`. The headless harness now exits nonzero for any recorded failed assertion. The final functional run adds no screenshots and does not extend the visual inspection budget.

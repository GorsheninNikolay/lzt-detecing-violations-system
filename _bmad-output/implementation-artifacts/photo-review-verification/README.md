# Photo review, annotations and analysis motion verification

Verified locally on 2026-09-26. No GUI application was launched or controlled. No deployment, remote operation, live inference or training was performed. Changes are prepared for a local completion commit. Existing application data was not targeted.

## Implementation

- Additive migration `0021_annotations` creates immutable proposals and immutable review versions, with database whole-frame/rejection constraints and mutation triggers. Original model objects/results remain separate.
- Visitor submission and owner review retain exact request keys/bodies; owner reviews reject stale expected revisions. Owner reload-for-comparison preserves the draft and resets whole-frame confirmation.
- Session/CSRF-protected selected-version export produces oriented PNG, COCO pixel xywh and provenance in ZIP. It deduplicates identical decoded frames, rejects conflicting selected annotations, and excludes reserved original/derived hashes and decoded right-angle rotations.
- Trusted fingerprints cover the eleven committed held-out frames. The source archive and every member were checksum verified against `evaluation/held-out-v1.json`; archive SHA256 `215e3364701c60dcb9ebf12081083a14822b36da3ebd29484f641c8e98e88169`. Sidecar SHA256 is `e755020e71e0e10ac590d080b8ee354d2666b9943f95447c4ddc8980225c9b42`, pinned by the service. Newly reserved DB frames require verified artifact bytes or export fails closed.
- Photo-first results, numbered object selection, disclosed basis/model scores, frame-bound visitor/owner editors, history/retry recovery, checkbox equipment groups, project/upload composition, focused phone review return, responsive navigation and skip link.
- Analysis sweep uses only the server running state while connected; compact steps use actual server states. Technical protocol is disclosed. Motion toggle and reduced-motion preference remove the sweep; completion is immediate with a maximum 350 ms transition.

## Checks

| Evidence | Result |
| --- | --- |
| `cd web && npm test -- --run` | Final: 162 passed, 8 files |
| `cd web && npm run build` | TypeScript and Vite passed |
| Targeted backend tests listed below | Final: 35 passed; 2 dependency deprecation warnings |
| Existing startup/readiness/result API subset | 6 passed, 42 deselected |
| Headless confirmation | 137 checks passed, no failures |
| `git diff --check` | Passed |

Backend tests used a separately created PostgreSQL database `evidence_annotations_20260926` and S3 bucket `evidence-annotations-20260926`. Migration was applied only to that database. The private local setup script is `/private/tmp/lzt-annotation-test-env.sh`; it sets the existing localhost service configuration and separate test targets. It is not a repository artifact.

```sh
source /private/tmp/lzt-annotation-test-env.sh
cd backend
.venv/bin/pytest tests/test_annotations.py tests/test_engagement.py tests/test_detected_objects.py tests/test_site_workflow_db.py -q
```

Annotation tests exercise the real PostgreSQL/S3 API lifecycle with TestClient: immutable original evidence, identical-key retry, changed-key-body conflict, CSRF, authentication, optimistic concurrent reviews, whole-frame gate, rejection reason, exact-version COCO/image/provenance alignment after EXIF orientation, duplicate-frame provenance, thumbnail orientation and fail-closed exclusion. These are targeted suites, not a claim that the entire backend/inference suite ran.

Frontend tests include draft reload, undo/redo, stable retries after unknown responses, run/frame isolation, object selection, keyboard geometry, whole-frame reset, stale edit retention, and typed numeric geometry with associated validation errors. Existing changed-layout assertions were updated for numbered objects, photo-before-basis order, checkbox groups and formatted timestamps.

`headless.cjs` uses deterministic API fixtures and real image bytes against Vite at `http://127.0.0.1:15174`. It is UI evidence, distinct from the real API roundtrip above. The initial batch found a 320 px admin-heading overflow, unfinished control styling and asynchronous focus assertions. One batched fix was followed by `confirmation-checks.json`: widths 320/390/480/768/1024/1440, long project/area/file names, eight frames, results/editor, upload, plan checkbox groups, running/disconnected/reduced/disabled-motion states, private annotation review, feedback detail, object selection in both directions, keyboard/pointer geometry, return focus, skip-link layering, and CSS 200% zoom checks. Screenshots are prefixed `initial-` and `confirmation-`. The initial harness was corrected for complete admin overview fixtures and actual browser offline state before completing its batch.

A final numeric-input correctness fix followed screenshot confirmation: typed values commit on blur/Enter rather than rejecting transient empty/decimal strings. Default field layout is unchanged; the final 147-test suite and build include this fix. No third screenshot batch was taken.

## Scope and remaining limits

No physical-device, assistive screen-reader or real-browser toolbar zoom verification is claimed. CSS 200% zoom was checked on results/admin; actual browser-zoom behavior remains unverified. Headless screenshots use fixture data and cannot establish deployment, model quality or inference throughput. The localhost Vite process is left available for independent review.

Exclusion detects exact original/derived hashes and identical decoded images under right-angle rotations, including EXIF orientation changes. Unknown source-site groups and arbitrary recompression cannot be inferred and are not certified as disjoint. New reserved checksums without usable exclusion evidence block export. Export is bounded to 32 selected versions and 128 MB of encoded images; source images are limited to 16 MB and 40 million pixels. Approval records data only; no fine-tuning occurs.

The user-authorized `design-taste-frontend` guidance was scoped to its applicable audit/preserve, rhythm, palette and purposeful-motion principles: this is a dense Operate/admin/editor surface, so its marketing-page generators/library replacements are excluded. Design dials: variance 4, motion 3 (one scan scene), density 4. Impeccable craft-floor, existing Onest/plum/Radix identity and evidence boundaries remain the design authority.

## Final independent review and repair verification

All code review findings were triaged in the implementation spec and repaired. Added regressions cover proposal-bound owner recovery across changed revisions, frozen approval recovery after image failure, second uncertain submissions after acknowledgement, malformed local drafts, failed local storage, invalid/uncommitted numeric input, unloaded images, tiny edge resize and pointer preview, later queue pages, serialized/deduplicated reads, exact export selection/cap, and header project creation. Real PostgreSQL/S3 tests now also exercise conflicting annotations and new database-only evaluation reservations, including rotated copies and missing-byte fail-closed behavior.

The parent independently reran the full web suite (162 passed), production build, and targeted backend suite (35 passed), with final output in `final-web-tests.txt`, `final-build.txt`, and `final-backend-tests.txt`. Six existing startup/readiness/read-result HTTP tests passed separately. The initial parent backend attempt was denied localhost access by the sandbox; the authorized retry passed against the same isolated targets. An upload-test timing failure was fixed by awaiting completion of the existing asynchronous image validation rather than assuming the frame was ready immediately after file selection.

The independent visual reviewer inspected all 14 confirmation screenshots, retained the photo-first layout, and requested only two spacing/navigation fixes: result-summary inset and non-breaking admin tab labels. Both were scored resolved at source scope after correction. Final functional repairs, selected-version controls and those CSS fixes followed the confirmation screenshots; they are covered by final tests/build and source review, not a third screenshot audit. The original 137-check confirmation remains evidence of its captured revision. Physical devices, screen readers and real browser toolbar zoom remain unverified.

The named Impeccable agent definitions were not available locally; independent fresh-context reviewers/documenter used the supplied reference contracts. The Impeccable launcher and final detector both returned `permission denied`; no detector pass is claimed. Applicable design-taste guidance was used without changing the product's design system. No findings were deferred.

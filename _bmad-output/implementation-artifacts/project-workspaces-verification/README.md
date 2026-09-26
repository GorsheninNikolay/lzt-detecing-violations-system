# Project workspace verification — 2026-09-26

## Checked state

- Backend: 21 tests passed in `test_site_workflow_db.py`, `test_site_analysis.py`, and `test_single_image.py` with only `admitted_profile_http_background_cpu` deselected (real admitted CPU execution was checked separately below). This includes project creation/default area, independent workspace binding, validation before publication, history filtering/count before pagination, unknown project, mixed JPEG/PNG original preservation, retry workspace/frame-time preservation, HTTP submission guards, and publication recovery.
- PostgreSQL migrations through `0016_project_history` applied only to isolated `workspace_test_20260926`. Backend integration used the existing isolated `evidence-test` bucket. Initial broader test attempt lacked storage environment and reported setup errors; the configured rerun passed all 21 selected tests.
- Frontend final: `npm --prefix web test -- --run` passed **124 tests across 3 files**, independently rerun after both review repair passes. Tests include delayed IndexedDB recovery preserving a newer dirty plan and unassigned legacy-request handoff. Historical global-stage tests were replaced by project-workspace behavior; existing submission, artifact, and recovery regression coverage remains.
- Production web build: `npm --prefix web run build` passed TypeScript and Vite.
- `git diff --check` passed.

## Headless browser evidence

`headless.cjs` uses the existing Chromium-compatible binary strictly with `headless: true`. Vite runs on port 15173; Playwright forwards `/api` requests to the isolated real API on port 18000 without mocking response bodies. `headless.json` records 28 passing post-repair checks for desktop 1440×1000 and mobile 390×844: keyboard Tab/Enter project navigation, native-selector keyboard typeahead switching in both directions, heading-focus restoration, project overview, selected default area, comparison opt-in, independent tabs, declined browser Back, declined/accepted dirty project switch, server ownership correction, no horizontal overflow, and no uncaught page errors. The PNG files capture final overview/upload/result screens. This script adds a photo to a draft but does not trigger duplicate inference.

`live-ui.json` records the separate headless create-project → upload → real CPU result flow. `live-smoke.json` records three successful real CPU runs using the existing admitted local presence-only profile in isolated cloned database `evidence_workspace_smoke_20260926` and bucket `evidence-workspace-smoke-20260926`: two independent no-plan projects, accepted request recovery with the same key, unchanged earlier result after adding a plan, and a later run bound to the exact selected plan revision.

## Limits and retained compatibility

No application database migration, profile/model mutation, deployment, remote publication, or new admission was performed. These checks establish local behavior, not recognition quality, physical-device behavior, or a deployed release. The restarted isolated API passed planned-stage UI and immutable revision checks recorded in `planned-ui.json` and `plan-immutable.json`: saving revision 2 did not change revision 1 evidence. The profile does not provide scene-based stage hypotheses. Existing public detected boxes are retained; no blanket lack-of-boxes claim is made.

Legacy API submissions and direct legacy `/new` UI remain compatible and can create unassigned ordinary runs. Normal project navigation starts at the shared project list and submits project-bound runs; unassigned ordinary history appears only in its explicit archive. No old/evaluation/comparison evidence is reassigned. Existing legacy UI compatibility is retained rather than removing its recovery/validation regression paths.

Task-created Vite servers on ports 15173/4189 and the isolated API on port 18000 were stopped after final verification; no pre-existing user process was stopped. Isolated databases and evidence buckets remain available for readback. Native unload confirmation is implemented and browser Back is automated; the operating system's leave-page prompt was not separately automated.

## Review repairs

Upload validation, demo loading, and request preparation are fenced by upload generation. Navigation cancels loading state; stale submission responses cannot navigate or attach errors to a newer workspace. A pending request belonging to another project blocks upload with an explicit recovery link and retains its original body/key. Managed history positions restore a declined traversal with `history.go` instead of truncating Forward history.

Plan editing and area selection are disabled throughout initial loading, mutation, and readback. Area identity fences stale responses, creating an area confirms abandoning a dirty plan, and bounded GET reads expose retry without retrying mutations. Area changes reset plan-comparison opt-in. Results display saved per-frame capture times independently of plan binding and provide a scoped signals link.

Targeted edited backend workflow suite: 2 passed against `workspace_test_20260926`, including exact saved title/stage/dates after a newer revision. Added frontend regressions cover delayed validation, canceled demos, cross-project pending recovery, late accepted responses while another plan is dirty, planless area selection, saved capture times/works, plan loading/save/readback locks, initial read timeout/retry, and Back/Forward preservation.

Post-repair headless rerun passed all 28 checks with updated screenshots and no new inference. Task Vite on port 15173 was restarted in execution session 30569; the earlier session was no longer listening.

Final coordinator verification repeated backend 21/21 selected tests, frontend 124/124, production build, and headless 28/28 after repairs. All review findings were fixed; none deferred. Four real CPU runs succeeded in total: three in the API smoke and one through the real headless upload flow. These runtime checks use the existing admitted profile and do not assess AI quality.

---
title: 'Onboarding, durable feedback and private administrative statistics'
type: 'feature'
created: '2026-09-26'
status: 'done'
route: 'dispatch'
baseline_commit: '23076b8b9421d368b0a8e69791129290ed45ecc9'
review_loop_iteration: 1
context:
  - '_bmad-output/specs/spec-construction-monitoring-concepts/EXPANSION.md'
  - '_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/DESIGN.md'
---

<frozen-after-approval reason="User explicitly requested implementation of the supplied complete plan in this session">

## Intent

Deliver the user-approved combined plan locally: introduce the application before first analysis, let anyone submit durable illustrated feedback, and let the owner inspect feedback and trustworthy statistics at an unlinked `/admin`. Preserve the current project-first workflow and plum/Onest visual system. Russian user-facing copy, English repository documentation.

## Boundaries & Constraints

Always preserve existing work and immutable analysis contracts. Never open GUI apps; use headless CLI verification. No remote deployment, push or new model admission. User-triggered ordinary analysis of the tutorial photo is authorized using the configured admitted profile; never bypass its authorization, allowlist or runtime gates. Local verification may use the existing admitted local CPU profile. Migrations run only against isolated local databases for verification. Reuse `web/public/team-logo.png` in the header, favicon and apple-touch icon. Remove visible `Проект` label but retain accessible `Выбрать проект`. Public pages always expose text actions `Как пользоваться` and `Обратная связь`, including narrow screens. No public admin link.

Onboarding: five steps covering capabilities, project/default area, photos/times, reading results, optional plans/signals. Explain supported recognition limitations and model versus human judgments. Back/next/skip; ordinary navigation never creates data or starts analysis implicitly. Automatic once per browser, remembering completion or skip; manually reopenable. Never auto-open in admin, during pending-request recovery or over a dirty draft. USER UPDATE: replace the centered desktop dialog/full-screen mobile wizard with an interactive anchored tour. Each step positions its tooltip near the actual relevant control, spotlights that specific control, and dims the rest of the page. Track target geometry across responsive layout/scroll/resize; keep tooltip and controls inside the viewport without obscuring its target. Preserve keyboard navigation, Escape and focus restoration. Mobile may use a compact anchored/bottom tooltip when space is tight while keeping the spotlight visible. SECOND USER UPDATE: provide a hands-on path using a separate clearly named training project and a preloaded good, simple bundled test photograph. An explicit tour action creates/reuses that training project with its default area and stages the verified sample in its upload form. Creation retries must not duplicate the project; preserve any working-project draft. Let the visitor activate the real highlighted `Запустить анализ` button during the tour and continue to its actual persisted result. This is an ordinary server analysis and counts normally; Next never launches inference automatically. The fixture and any illustrative capture time must be labeled as educational/example data. Reuse existing demo assets and verification helpers; never alter a working project or use held-out/admission fixtures as generic tutorial data. These updates supersede static-modal/full-screen presentation and the original prohibition on tutorial data creation; feedback and admin scope remain unchanged.

Feedback: required category (problem/idea/praise/other) and nonblank text up to 5000 chars; up to five JPEG/PNG/WebP, 5 MB each, 15 MB total; preview/removal. Show optional default-included context (pathname without query, project, analysis); never automatically attach analysis photos. Tab-specific draft including pictures survives reload; lost-response retry uses identical body/key without duplicates. Validate images server-side; private S3 `feedback/` namespace separate from evidence. Success only after all attachments are stored, exact success copy `Спасибо, отзыв сохранён`; errors preserve draft and allow retry. Bound public request size/frequency; deduplicate analytics event IDs.

Admin: login `gorshenin-nik`, configured password hash only (strong salted KDF; never plaintext in code/tests/frontend). Supply a secure getpass provisioning command and fail closed until privately configured. The user subsequently supplied the initial password privately and explicitly added authenticated password change: require the current password and CSRF token, persist only the replacement hash, revoke existing sessions and require a new login. Never copy the initial password into artifacts, tests, frontend, commands/history or logs. Eight-hour server sessions, HttpOnly/SameSite cookie, revocation, persistent login throttling, CSRF protection for mutations. Require HTTPS except true localhost access. Every admin data API and attachment denies unauthenticated access. Tabs `Обзор` and `Обратная связь`; newest first/category filter/detail/context/images; opening marks read. No replies, deletion, status workflow.

Statistics: 7/30/all periods (default 30), Moscow day boundaries. Browser identity shared across tabs; visits are sessions renewed after 30 minutes inactivity, excluding admin, polls and health probes. `Посетители` explicitly means browsers, not identified people; no names/IP in analytics. Cards: visits, visitors, projects created, analyses launched/succeeded/failed, feedback/unread. Daily visits/analyses charts and all-project list with run counts/latest activity. First-use funnel: first visit → project creation → first successful analysis; wizard started/completed/skipped separately. Project/run acceptance/results are server-authoritative, retries deduplicate while distinct reanalysis counts. Only ordinary runs, excluding admission/comparison. Include historical ordinary runs in totals without inventing unknown dates or attributing them to new visitors. Analytics failures never block product actions; ownership separate from immutable run context/idempotency. Collection begins on implementation.

Public POST `/api/feedback`, `/api/analytics/events`; protected `/api/admin/overview`, `/api/admin/feedback`, attachment delivery and login/session/logout. Existing proxy strips `/api`. Separate migrations for feedback/attachments, admin sessions, anonymous sessions/events/attribution.

## I/O & Edge-Case Matrix

| Scenario | Expected behavior |
|---|---|
| First visit / skip / reopen / reload | Wizard safe auto-open once; accessible manual reopen; storage refusal degrades safely |
| Dirty plan/upload or pending recovery | No automatic interruption |
| Feedback reload/lost response | Same pictures/draft and frozen request/key; one saved feedback |
| Invalid/oversized/corrupt attachments or S3 failure | Reject without published feedback; retain retryable draft |
| Wrong login/expiry/logout/brute force/CSRF | Deny; server sessions revoke/expire; every data route protected |
| Multiple tabs / 30-minute boundary / duplicate event | Shared browser/session, deterministic server dedup, no artificial visits |
| Historical/ordinary/evaluation runs and dates | Accurate ordinary counts and Moscow buckets; no fabricated historical attribution |

</frozen-after-approval>

## Code Map

- `backend/app/main.py`: FastAPI routes/lifespan, `app.state.store.engine` and artifacts; accepted submissions and retries are server attachment points.
- `backend/app/application/site.py`: project creation transaction and default area. Add idempotency support without changing existing clients.
- `backend/app/adapters/artifacts.py`: S3 client and integrity checks; evidence read helper intentionally only accepts `sha256/`, so feedback needs a distinct safe path.
- `backend/migrations/versions/0016_project_history.py`: current migration head; ordinary run project lives in request_context, nullable historical created_at; do not modify these for analytics.
- `web/src/App.tsx`: project routing, dirty draft/navigation protection, pending IndexedDB/sessionStorage recovery; integrate safe gate and attribution headers without altering request body.
- `web/src/AppHeader.tsx`, `main.tsx`, `styles.css`, `premium.css`: shell/branding. Prefer standalone onboarding/feedback/admin modules to expanding App further. Isolate admin before mounting public App.
- `backend/tests/test_site_workflow_db.py`, `test_single_image.py`, `web/src/ProjectWorkspaces.test.tsx`, `App.test.tsx`: existing integration/frontend patterns.
- `_bmad-output/implementation-artifacts/project-workspaces-verification/README.md`: previous isolated DB/S3 and headless setup. Podman needs sandbox network escalation; do not stop existing processes. Playwright is available at `/opt/homebrew/lib/node_modules/omniroute/node_modules/playwright`, headless Chromium path from prior scripts.

## Tasks & Acceptance

- [x] `backend/migrations/versions/0017*` onward, `backend/app/application/*`: durable feedback, sessions/security, analytics/overview, accepted mutation attribution and deduplication.
- [x] `web/src/*`, `web/index.html`: wizard, branding, persistent feedback, browser analytics, admin views and accessible responsive styles.
- [x] `backend/tests/*`, `web/src/*.test.*`: executable edge matrix and regression coverage, isolated DB/S3 integration.
- [x] `scripts/*`, verification evidence: headless desktop/mobile and keyboard checks, local reviewable server instructions, secure admin hash setup command.
- [x] canonical SPEC/EXPANSION, UX DESIGN/EXPERIENCE, architecture spine/memlog and READMEs: reconcile the approved extension in place without unrelated sprint edits.

Acceptance: Given the completed local implementation, when visitors follow the project workflow or send feedback, then all approved interactions work without lost drafts or analysis contract changes. Given no admin session, when any admin data/attachment endpoint is requested directly, then it discloses no protected data. Given known server fixtures and anonymous activity, when overview periods are selected, then counts/funnel and Moscow daily buckets match authoritative records.

## Implementation Notes

- The user already authorized the combined scope and implementation; workflow re-approval/splitting checkpoints are satisfied by that instruction. No additional product decision is required.
- UI direction: established Operate surface, code-led extension. Reuse current tokens and logo without raster generation. Five-step readable dialog and compact responsive actions; admin cards are specifically requested. Impeccable context launcher returned permission denied; existing canonical DESIGN and implementation are the visual authority.
- Agent workflow: implement sequentially; do not recursively invoke bmad-build. Independent code/security and visual review follow implementation. Keep working until tests and headless evidence are complete, or report concrete external blockers.

## Spec Change Log

- 2026-09-26: user authorized initial password provisioning and added changing the password after login. Frozen admin intent updated accordingly; password value deliberately excluded.
- 2026-09-26: user replaced static onboarding with a spatial interactive tour: the hint follows relevant controls, highlights the current control, and dims the surrounding page. Preserve onboarding persistence, recovery guards and no automatic effects; revise UI/headless assertions and UX documents accordingly.
- 2026-09-26: user authorized a dedicated tutorial project with staged test photography and an optional real analysis during the tour. Add explicit idempotent creation/sample loading and actual submit/result steps; do not bypass model authorization or auto-submit on Next.

## Review Triage Log

| Finding | Verdict | Evidence / route |
|---|---|---|
| Blind 1: falsey context identifier | high | Public validator admits object/array values; Admin renders raw values. Validate all supplied IDs and defensively render legacy values. Patch. |
| Blind 2: stale trainingReady | medium | Only ever set true; later modified/blank drafts and runs inherit training claims. Bind to exact sample/run and clear on abandonment. Patch. |
| Blind 3: feedback close/reopen writes | high | Write queue is component-local while IDB key survives; delayed reads/writes can lose edits. Share serialization and fence file callbacks. Patch. |
| Blind 4: stale admin detail/pagination | medium | Mutations lack the generation/abort fence used by list effect. Patch. |
| Blind 5: S3 fixture fallback | high | New fixture falls back to application bucket instead of requiring explicit isolated target. Patch. |
| Blind 6: initial analytics ordering | medium | Attribution SELECT requires browser row, so earlier project acceptance silently misses ownership. Establish current browser/session within savepoint using authoritative acceptance time. Patch. |
| Blind 7: background tab visit | medium | Activity listeners omit visibilitychange; hidden initial load is skipped. Patch. |
| Blind 8: session-read errors | medium | Every session error becomes login without unavailable state or retry. Distinguish 401 from failed read. Patch. |
| Blind 9: last project activity | medium | Query only uses project/run creation, ignoring existing timestamped plan/confirmation/signal updates. Include recorded product activities. Patch. |
| Blind 10: feedback lifecycle regression | medium | Headless covers durable replay, but component teardown/write races and rejection recovery need focused tests. Patch. |
| Edge 1: context object crash | high | Same demonstrated root cause as Blind 1; retained as independent finding, same patch. |
| Edge 2: stale category pagination | medium | Same demonstrated root cause as Blind 4; same patch. |
| Edge 3: reopened draft races | high | Same demonstrated root cause as Blind 3; same patch. |
| Edge 4: delayed training navigation | high | Training completion does not recheck newer project draft or navigation generation. It can abandon newly typed work. Patch existing generation guard. |
| Edge 5: training remains busy | medium | No completion path when navigation/prerequisites are canceled. Clear/fence preparation on cancellation and bounded failure. Patch. |
| Edge 6: stale tutorial photo/result | medium | Same demonstrated root cause as Blind 2; same patch. |
| Verification 1: positive run funnel | medium | Submission/series/retry ownership and success funnel have no positive integration assertions. Add targeted coverage. Patch. |
| Verification 2: savepoint failure | high | No test injects actual SQL failure while asserting accepted product records commit. Add DB fault coverage. Patch. |
| Verification 3: wrong current password | high | Endpoint test only submits correct current password; deletion of verification would pass. Add negative requests/hash/session readback. Patch. |

## Verification

- `npm --prefix web test -- --run` and `npm --prefix web run build`.
- Migrate an isolated local database; run backend integration with isolated test bucket and targeted regression suites. Never claim a skipped/blocked suite passed.
- Headless Chromium desktop and mobile; use native dialog keyboard/focus, reload recovery, multiple tabs, request dedup and actual protected API behavior. Save screenshots/report locally, no GUI.
- `git diff --check`; no remote publication. Provide local review URL or precise start command; password provisioning remains private.

### Coordinator review evidence

All three independent layers returned. Their demonstrated implementation/verification defects are bounded corrections under the approved intent; retain the delivered surfaces and immutable evidence contracts. No intent gap or user decision is required. Desktop/mobile continuation to the already succeeded training run was independently verified by replaying original request keys, without new inference; 18 checks passed, screenshots recorded.

### Final verification and review closure

Coordinator reran 142 frontend tests, 44 selected backend tests, production build, 44 final headless checks and 22 same-key guided desktop/mobile result checks. The engagement module also passed 23 tests after adding real SQL fault coverage at run acceptance. All original blind-review findings were independently scored resolved; other review gaps are covered by executed assertions. Corrected actual paragraph width, mobile hit-test occlusion and canonical admin/textarea palette. Final visual verdict scored its material fixes resolved (ship); canonical UX documentation was independently reconciled. No task findings deferred. Detector unavailable with permission 126 is disclosed. Local preview remains ready with existing admitted CPU profile; no remote deployment/push/new admission.

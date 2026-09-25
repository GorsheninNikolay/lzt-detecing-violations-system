---
title: 'Story 4.2: Admit the Required Cloud Candidate'
type: 'feature'
created: '2026-09-24'
status: 'blocked'
baseline_revision: 'bd5e0cf705fac23c6a1774c1a086b54f95c1b8d9'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: [oversized]
deferred: []
---

<intent-contract>

## Intent

**Problem:** The current branch has no admitted Qwen3.6 cloud profile, while the separate `codex/yandex-cloud-ai-studio-20260924` branch has a bounded Yandex AI Studio prototype. Its historical comparison used a different image set from the accepted Story 4.1 evaluation revision.

**Approach:** Reconcile the cloud branch with current `main`, then admit an immutable Qwen3.6 profile for the owner's specifically approved prototype images using the existing profile, invocation, run, and artifact contracts. Keep the profile draft until live owner-account gates and a bounded canary pass; a changed image allowlist or prompt requires a new profile revision.

## Boundaries & Constraints

**Always:** Bind requested and returned model URI, adapter, prompt, schema, reasoning, temperature and runtime revisions, account/data evidence, authorized image hashes, authorization revision, provider request/response identity, and private artifacts. Reject unapproved images before upload or paid inference. Validate the closed two-class observation states. A timeout, malformed response, absent returned identity, quota failure, or missing account/data gate fails admission; no fallback or inferred equipment absence follows. Disclose any unpinnable hosted-model revision as an identity gap.

**Never:** Treat the prior branch pilot as the Story 4.1 campaign; use the held-out set for admission or tuning; store credentials in the repository; enable a draft profile; infer provider deletion from `store=false` or local artifact deletion; send new real-site images without separate rights/data approval; route to another provider on failure.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Missing gate or image authorization | Missing paid owner-account, model/quota/terms evidence, or image hash | Remain draft; send no image | Record the exact missing gate |
| Bounded canary succeeds | Approved input and current owner account | Record strict response, served identity, request data controls, private input/native artifacts, and admitted enabled successor | Retain evidence in ordinary contracts |
| Canary fails | Timeout, malformed output, absent identity, or artifact failure | Remain draft with failed admission run | Preserve invocation evidence; no fallback |

</intent-contract>

## Code Map

- `_bmad-output/planning-artifacts/epics.md:908` and `ARCHITECTURE-SPINE.md:169,209` — approved Story 4.2 acceptance and profile/cloud gates.
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/backend/app/profiles/cloud_api.py:47,85,162` — reusable draft, normalization, and bounded observer; its fixed 26 hashes and synthesized returned URI must be corrected, not copied as authority.
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/backend/app/application/admission.py:147` and `evaluation/comparison-report-2026-09-24.md` — historical canary flow and pilot evidence only; no current account gate or Story 4.1 campaign proof.
- `backend/app/application/admission.py` and `backend/app/adapters/postgres.py:242,272,293,417,481,652,681,950` — preserve current profile, authorization, invocation, ordinary-run, and retry contracts while adding cloud-specific checks.
- `backend/app/application/executor.py:129`, `backend/app/application/submission.py`, and `backend/app/main.py` — current local runtime, upload boundary, and composition; bind Qwen explicitly and reject unauthorized bytes before publication or inference.
- `backend/app/adapters/artifacts.py` and `backend/migrations/versions/0002_admission.py` — existing private artifact publication and immutable evidence owners; reuse before adding schema.
- `backend/app/domain/observations.py:78` — closed two-class observation-state contract.
- `backend/tests/test_admission.py`, `backend/tests/test_single_image.py`, and `backend/tests/test_ordered_series.py` — preserve local admission, run, retry, and artifact behavior.
- `evaluation/held-out-v1.json` and `backend/admission/exclusions/held_out_evaluation.json` — read-only accepted Story 4.1 identities; do not use held-out bytes for admission smoke or rewrite its frozen evidence.

## Tasks & Acceptance

**Execution:**
- `backend/app/profiles/cloud_api.py` — port the bounded Responses request and strict normalization; retain the provider's actual returned URI, reject missing identity, and keep credentials transient.
- `backend/app/application/admission.py` and `backend/app/adapters/postgres.py` — persist current owner-account, access, quota, terms, data controls, and exact image-scope evidence; reject a missing gate before any canary upload; authorize an immutable successor only after successful admission invocation and private artifact readback.
- `backend/app/application/submission.py`, `backend/app/application/executor.py`, and `backend/app/main.py` — enforce the profile's exact image hashes at submission and execution, including retry, then route only the explicitly bound enabled Qwen revision through existing reservation and completion contracts.
- `backend/tests/test_cloud_profile.py`, `backend/tests/test_admission.py`, and `backend/tests/test_single_image.py` — cover account/data gate failures, unauthorized bytes, strict response and raw served identity, canary failure, revocation, retry, and local-profile compatibility.

**Acceptance Criteria:**
- Given any missing owner-account or data gate, when admission is attempted, then the profile remains draft and no image is uploaded.
- Given an image outside an admitted profile's authorized hashes, when a run is submitted, then it is rejected before artifact publication or provider inference and the profile authorization remains unchanged.
- Given approved canary data and the evidenced paid owner account, when admission runs, then the ordinary run records strict response, served URI, request data controls, private input/native artifacts, and an admitted enabled successor without claiming provider deletion.
- Given timeout, malformed output, absent served identity, or artifact failure, when the canary ends, then admission fails and neither an absence result nor fallback candidate is produced.

## Spec Change Log

- 2026-09-24: The owner approved `sprint-change-proposal-2026-09-24.md`, replacing GigaChat with Yandex AI Studio Qwen3.6 for an allowlisted prototype. The prior GigaChat dependency block is superseded; branch integration, live account gates, and the new Story 4.1 campaign remain unverified.

## Design Notes

The earlier cloud pilot may supply an admission canary only if its exact image belongs to the owner's approved prototype scope and remains outside Story 4.1's held-out set. The admitted profile may authorize the held-out hashes for a later campaign, but Story 4.2 must not send those bytes as a canary or count historical pilot runs as campaign cells. A request setting such as `store=false` is evidence about the request, not provider deletion.

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 15 findings — high 4, medium 8, low 0, false 3, maybe-false 0
- findings:
  - `[high]` `[intent_gap]` Self-authored account evidence can enable upload — `validate_owner_evidence` accepted nonempty strings without an authoritative source for paid access, quota, terms, and rights. The intent does not choose the required source or proof format. The attempted code is saved in [the patch](spec-4-2-cloud-attempt-2026-09-24.patch.gz).
  - `[false]` `[reject]` Fixed admission manifest allegedly selects unauthorized canaries — the existing four admission frames were individually included in the owner's earlier 26-image cloud authorization, and their manifest is disjoint from the accepted held-out set. A new selection is not required by this story.
  - `[false]` `[reject]` A 24-hour proof has no renewal path — rerunning admission creates a new immutable profile and enables it after fresh evidence; an old revision is expected to expire rather than mutate.
  - `[high]` `[bad_spec]` Queued runs could invoke the provider after evidence expiry — `claim_ordinary` and `reserve_ordinary` checked the authorization row but not the current owner gate. The spec did not anchor expiry enforcement at the provider boundary.
  - `[high]` `[bad_spec]` Socket timeout was mistaken for a whole-call deadline — slow response chunks can keep `urlopen` and the admission advisory lock alive beyond the watchdog. The spec needs an enforceable wall-clock execution bound.
  - `[medium]` `[bad_spec]` Provider response reading was unbounded — `json.load` could consume excessive memory and publish unnecessary provider data; the spec did not state a byte cap and retained-field boundary.
  - `[medium]` `[bad_spec]` Returned request correlation was absent — `observer_invocations.returned_request_identity` stayed null although the response ID was stored only in native evidence. The provider identity contract needs an explicit correlation mapping.
  - `[medium]` `[patch]` Quota, access, HTTP, and transport failures collapsed into `observer_execution_failed` — the executor's safe-code set omitted the new cloud failures. A small code-list correction would preserve them.
  - `[medium]` `[bad_spec]` Real persistence and ordinary-run cloud paths lacked tests — mocked admission tests cannot establish database authorization, series, revocation, or retry behavior. The verification scope in the spec did not demand a cloud integration case.
  - `[high]` `[bad_spec]` Slowly streamed responses bypass the intended deadline — same root as the whole-call deadline finding, confirmed at the response-reading path.
  - `[medium]` `[bad_spec]` Account evidence may expire during a multi-image admission — the gate ran once before four provider calls and was not rechecked before each upload.
  - `[medium]` `[bad_spec]` Cloud database authorization gate was unverified — the successful test replaced `PostgresStore.authorize_successor` with a stub, so the persisted successor and evidence checks were never exercised.
  - `[medium]` `[bad_spec]` Authorized cloud execution was unverified — the new submission test covered rejection only, while existing worker tests used the local observer.
  - `[medium]` `[intent_gap]` No live admitted profile was demonstrated — synthetic strings, fake storage, and mocked HTTP do not establish current account, provider, or private-artifact evidence. The exact external proof required for admission remains unresolved.
  - `[false]` `[reject]` Sprint ledger was allegedly left out of sync — after preserving the attempt as a patch and reverting its code, Story 4.2 remains unimplemented and its `backlog` entry reflects the checked source state; no `done` transition is supported.

## Verification

**Commands:**
- `cd backend && uv run --extra test pytest tests/test_admission.py tests/test_cloud_profile.py tests/test_single_image.py` — expected: local and cloud admission/run contracts pass after integration.
- `git diff --check` — expected: no whitespace errors.

**Manual checks (if no CLI):**
- Read back the owner's current paid account, model access, quota, applicable data/retention terms, canary response identity, and exact allowed-image scope. Historic branch evidence does not prove the later Story 4.1 campaign.

## Auto Run Result

Status: blocked after one implementation and review pass. Blocking condition: intent gap in authoritative live owner-account gate evidence. The attempted implementation is preserved in [spec-4-2-cloud-attempt-2026-09-24.patch.gz](spec-4-2-cloud-attempt-2026-09-24.patch.gz); its code was removed from the working tree as required by the workflow. No cloud profile was admitted.

Attempt verification: 36 focused tests passed against disposable local PostgreSQL and S3 resources after one compatibility fix. These tests used mocked cloud HTTP and did not prove account access, terms, a live canary, or an enabled persisted Qwen successor. The current source tree contains the planning baseline, not that tested code.

Unresolved decision: identify the authoritative account and terms readback that must be bound to the immutable profile, and confirm the exact currently approved four admission image hashes before a live upload. The separately accepted Story 4.1 set must remain outside the admission canary.

Earlier blocking condition (superseded): the future-customer GigaChat account and upload/deletion canary were unavailable. The approved Qwen prototype has different gates. Its branch pilot is evidence for planning and integration, not proof that this Story 4.2 revision is implemented or admitted on current `main`.

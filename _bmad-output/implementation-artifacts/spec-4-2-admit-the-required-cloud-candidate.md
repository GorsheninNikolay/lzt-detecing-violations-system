---
title: 'Story 4.2: Admit the Required Cloud Candidate'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '1512020047aa5e2b2fc343f78f9881a0a2c5914c'
review_loop_iteration: 0
followup_review_recommended: true
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

**Owner decision, 2026-09-25:** The owner confirmed that the current paid Yandex Cloud account has accepted the applicable AI Studio commercial and processing/retention terms and that the prior authorization for the four JPEGs in `backend/admission/manifest.json` remains valid. That manifest's SHA-256 is `57a27283c36df6e6d2da87939bf170f641cb8440ac2f0d01d58e17fb8c5a1909`; its four image hashes match the earlier authorized admission set. Before any image leaves the machine, read back the configured folder and active service account, an active billing account bound to that cloud, and a bounded Qwen3.6 strict-schema request without an image using the same scoped transient credential. A successful no-image request establishes current model access and capacity for the sequential canary, not future quota. Retain the nonsecret readback identities, timestamps, response ID, owner decision reference, and exact image scope. Recheck freshness before each image upload and each ordinary invocation; an expired gate requires a new immutable admission revision.

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
- `backend/admission/manifest.json` — the four owner-confirmed canary hashes; preserve its exact SHA-256 and separate these frames from the held-out revision.
- `evaluation/held-out-v1.json`, `evaluation/owner-attestation-2026-09-24.json`, and `evaluation/freeze-decision-v1.json` — accepted Story 4.1's eleven cloud-authorized hashes and immutable decision; authorize their bytes for the later campaign without using them in admission.
- Yandex Cloud Billing `BillingAccount.List` and `ListBillableObjectBindings`, Resource Manager folder readback, and IAM service-account readback — authoritative account identity and active payment binding; use transient IAM authentication and persist only nonsecret evidence.
- `spec-4-2-cloud-attempt-2026-09-24.patch.gz` — reviewed implementation seed; `gzip -dc` into `git apply` after checking the exact diff, then correct the previously logged gate, timeout, identity, and test gaps.

## Tasks & Acceptance

**Execution:**
- `backend/app/profiles/cloud_api.py` — port the bounded Responses request and strict normalization; retain the provider's actual returned URI, reject missing identity, and keep credentials transient.
- `backend/app/application/admission.py` and `backend/app/adapters/postgres.py` — perform live folder, service-account, billing, and no-image model readbacks before canary upload; bind the owner decision and four exact hashes to a secret-free immutable draft; refresh the gate before each image and ordinary provider reservation; authorize a successor only after successful admission invocation and private artifact readback.
- `backend/app/application/admission.py` and `backend/app/profiles/cloud_api.py` — verify the accepted Story 4.1 manifest, freeze decision, owner cloud-use attestation, and disjointness; include its eleven hashes in the new immutable profile allowlist while retaining only the four admission hashes as canary inputs.
- `backend/app/profiles/cloud_api.py` and `backend/app/application/executor.py` — enforce a whole-call deadline and bounded response bytes, retain the returned request/response identity, and preserve distinct quota, access, timeout, transport, and malformed-response failures without a fallback.
- `backend/app/application/submission.py`, `backend/app/application/executor.py`, and `backend/app/main.py` — enforce the profile's exact image hashes at submission and execution, including retry, then route only the explicitly bound enabled Qwen revision through existing reservation and completion contracts.
- `backend/tests/test_cloud_profile.py`, `backend/tests/test_admission.py`, and `backend/tests/test_single_image.py` — cover every canary matrix row, real PostgreSQL successor authorization, an authorized ordinary cloud run, expiry, revocation, retry, response caps/deadlines, and local-profile compatibility.

**Acceptance Criteria:**
- Given any missing owner-account or data gate, when admission is attempted, then the profile remains draft and no image is uploaded.
- Given an image outside an admitted profile's authorized hashes, when a run is submitted, then it is rejected before artifact publication or provider inference and the profile authorization remains unchanged.
- Given approved canary data and the evidenced paid owner account, when admission runs, then the ordinary run records strict response, served URI, request data controls, private input/native artifacts, and an admitted enabled successor without claiming provider deletion.
- Given timeout, malformed output, absent served identity, or artifact failure, when the canary ends, then admission fails and neither an absence result nor fallback candidate is produced.
- Given the owner-confirmed four-image scope and a live active billing binding, when admission starts, then no image is sent until the same credential completes a bounded strict-schema no-image Qwen request and its account, model, and response identities are retained.
- Given a queued cloud run whose account evidence has expired or authorization has changed, when execution reaches provider reservation, then the run fails before sending image bytes to the provider and a new immutable admission revision is required.
- Given the accepted Story 4.1 revision and its owner upload attestation, when the cloud successor is admitted, then its allowlist covers the eleven held-out hashes plus four admission hashes while none of the held-out bytes are used for admission.

## Spec Change Log

- 2026-09-24: The owner approved `sprint-change-proposal-2026-09-24.md`, replacing GigaChat with Yandex AI Studio Qwen3.6 for an allowlisted prototype. The prior GigaChat dependency block is superseded; branch integration, live account gates, and the new Story 4.1 campaign remain unverified.
- 2026-09-25: The owner confirmed the paid account's accepted commercial and data terms and continued authorization of the exact four admission frames. The intent contract now fixes authoritative Billing/Resource Manager/IAM readback and a no-image model/capacity probe before image upload. This avoids the prior self-authored-string gate. Keep the existing local profile, immutable evidence, no fallback, readback, and held-out separation.

## Design Notes

The earlier cloud pilot may supply an admission canary only if its exact image belongs to the owner's approved prototype scope and remains outside Story 4.1's held-out set. The admitted profile may authorize the held-out hashes for a later campaign, but Story 4.2 must not send those bytes as a canary or count historical pilot runs as campaign cells. A request setting such as `store=false` is evidence about the request, not provider deletion.

The owner decision is recorded in revision `1512020047aa5e2b2fc343f78f9881a0a2c5914c`; bind that revision, the four canary hashes, the configured folder/service-account IDs, active billing binding, and no-image probe response ID in the profile evidence. Use the owner statement for terms and image rights, official API readback for account/payment/identity, and a successful no-image call for present model access and sequential capacity. Never accept those machine-verifiable gates as operator-supplied strings.

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

### 2026-09-25 — Review pass
- verdicts: 16 findings — high 0, medium 11, low 2, false 3, maybe-false 0
- findings:
  - `[medium]` `[patch]` A no-image probe could return detected equipment and still pass — admission now requires both classes to be `not_detected_in_frame` before any image call.
  - `[medium]` `[patch]` Admission native artifacts omitted their API key ID — each native artifact now includes the nonsecret key ID used for that canary.
  - `[medium]` `[patch]` No-image probe output was reduced to identity fields — immutable owner evidence now retains its validated states and request controls.
  - `[false]` `[reject]` Canary results were not compared with fixture labels — admission proves the observation and evidence pipeline, while accuracy against labels belongs to the later frozen comparison; the Story 4.2 acceptance asks for a closed strict response, not a detection threshold.
  - `[false]` `[reject]` Readiness lacked a live provider call — readiness verifies application dependencies and a bound profile; external provider availability is checked before each invocation and failures stay explicit, so a later provider outage does not make readiness a false pass.
  - `[medium]` `[patch]` A key with additional scopes could be recorded as solely execution-scoped — the gate now accepts only the exact execution scope set.
  - `[medium]` `[patch]` Ordinary native evidence lacked the fresh gate identity and timestamp — the private native response now binds the current nonsecret gate result and actual key ID.
  - `[low]` `[patch]` A failed image canary returned no top-level error code — the CLI result now returns the safe code recorded on its failed run.
  - `[medium]` `[patch]` Cloud series execution and partial failure had no cloud test — a PostgreSQL/S3 integration case now verifies per-frame refresh and retention of earlier evidence after later failure.
  - `[medium]` `[patch]` Child-process timeout path was untested — a stalled-child test now asserts timeout and process termination.
  - `[low]` `[reject]` A different secret could theoretically share a six-character masked suffix — the API list also binds the ID, service account and scope, and the same secret successfully performs the probe; exploiting the suffix collision is implausible, while authoritative proof of a supplied secret's ID would require replacing the credential contract.
  - `[medium]` `[patch]` Same no-image negative-state gap as the first finding — the same validation and failure test covers both findings.
  - `[medium]` `[patch]` The whole-call child-process deadline lacked a test — the same stalled-child process test covers this finding.
  - `[medium]` `[patch]` An allowed held-out image had no ordinary-run verification — an approved archive JPEG passed submission and mocked-provider execution through PostgreSQL/S3; no held-out bytes were sent to a live provider.
  - `[false]` `[reject]` Four-versus-fifteen image scope was allegedly unresolved — Story 4.1's separate owner cloud-upload attestation and Epic 4's required campaign authorize the eleven held-out hashes for later ordinary runs; the four-image restriction applies to admission only.
  - `[medium]` `[patch]` The diff lacked live admission evidence — this result record now includes account, canary, profile, artifact, and key-deletion readbacks without credentials or image bytes.

## Verification

**Commands:**
- `cd backend && uv run --extra test pytest tests/test_admission.py tests/test_cloud_profile.py tests/test_single_image.py` — expected: local and cloud admission/run contracts pass after integration.
- `git diff --check` — expected: no whitespace errors.

**Manual checks (if no CLI):**
- Read back the owner's current paid account, model access, quota, applicable data/retention terms, canary response identity, and exact allowed-image scope. Historic branch evidence does not prove the later Story 4.1 campaign.

## Auto Run Result

Status: done. Story 4.2 is implemented and the current adapter revision has live admitted profile `8c6799e9-1f24-4287-ac30-26d921a67c7c` in isolated local database `evidence_story42_20260925` and private bucket `evidence-story42-20260925`. Authoritative readback found `admitted` status, enabled authorization revision 1, the exact union of four owner-approved canary hashes and eleven accepted Story 4.1 hashes, four completed live canary invocations with response IDs, a negative strict-schema no-image probe, and eight checksum-verified private artifacts. The returned model URI was `gpt://b1gcpjp9nc4hhoffpf3a/qwen3.6-35b-a3b`. Independent IAM readback found zero API keys remaining after the transient admission key was deleted. Earlier profiles remain immutable history; this profile passed `require_authorized` against the current adapter bytes.

Changed files:
- `backend/app/profiles/cloud_api.py` — bounded Qwen observer, official account/key/payment readback, negative no-image probe, approved 15-hash scope, and strict response normalization.
- `backend/app/application/admission.py` — guarded four-image canary, private artifact publication/readback, and safe failure result.
- `backend/app/adapters/postgres.py` — immutable cloud successor, current authorization and invocation identity checks, exact allowlist and retry fences.
- `backend/app/application/submission.py`, `backend/app/application/executor.py`, `backend/app/config.py`, `backend/app/main.py` — explicit cloud submission, runtime, transient credentials, and startup routing without fallback.
- `backend/tests/test_cloud_profile.py` — gate, bounded-call, persistence, held-out, series, retry, and failure-path verification.
- `README.md` — CLI admission and credential-rotation instructions.
- This spec — owner decision, scope, review triage, and observed result.

Review: 10 shared-root patch entries were fixed (9 medium, 1 low); no findings were deferred. Four findings were rejected: label comparison belongs to the later campaign, readiness does not promise perpetual provider availability, the masked-suffix collision is negligible relative to changing the credential contract, and the eleven held-out hashes have separate owner cloud-upload authorization. Follow-up review recommended: true because nine medium patch entries changed cloud evidence and verification paths; a live ordinary run with a rotated key remains unverified.

Verification: the final full backend suite ran against fresh isolated PostgreSQL/S3 with the real Story 4.1 archive: 153 passed, 1 skipped because `TEST_HELD_OUT_IMAGE_PATH` was unset. That one approved held-out ordinary-run test was then run separately with a checksum-verified JPEG and passed. `git diff --check` and Python compilation passed. The live canary, profile authorization, exact hash scope, invocation identities, private artifact integrity, and key deletion were independently read back. Held-out bytes were not sent to the provider; Story 4.3's three-repeat comparison, deployment, and live ordinary execution remain separate work.

Status: blocked after one implementation and review pass. Blocking condition: intent gap in authoritative live owner-account gate evidence. The attempted implementation is preserved in [spec-4-2-cloud-attempt-2026-09-24.patch.gz](spec-4-2-cloud-attempt-2026-09-24.patch.gz); its code was removed from the working tree as required by the workflow. No cloud profile was admitted.

Resolution, 2026-09-25: The owner supplied the missing terms and image-scope attestation. A live read-only billing binding and active service-account readback were observed; the new admission gate is specified above. At this checkpoint, implementation resumed from the draft and no model or image request had yet been made.

Verified live admission, 2026-09-25: Local database `evidence_story42_20260925` recorded admitted profile `0f408e96-3f86-4f86-b2bb-8cbf5684feac` with four succeeded canary runs, the exact 15-hash allowlist (four admission and eleven Story 4.1 held-out hashes), eight checksum-verified private input/native artifacts, and the returned Qwen URI. Independent readback found zero remaining API keys after the transient admission key was deleted. No held-out bytes were used in admission; this result does not establish the later Story 4.1 comparison campaign.

Attempt verification: 36 focused tests passed against disposable local PostgreSQL and S3 resources after one compatibility fix. These tests used mocked cloud HTTP and did not prove account access, terms, a live canary, or an enabled persisted Qwen successor. The current source tree contains the planning baseline, not that tested code.

Prior unresolved decision (resolved 2026-09-25): identify the authoritative account and terms readback and confirm the four admission image hashes. The owner confirmation, official Billing/Resource Manager/IAM readback, and exact manifest identity now settle these gates. The separately accepted Story 4.1 set remains outside the admission canary.

Earlier blocking condition (superseded): the future-customer GigaChat account and upload/deletion canary were unavailable. The approved Qwen prototype has different gates. Its branch pilot is evidence for planning and integration, not proof that this Story 4.2 revision is implemented or admitted on current `main`.

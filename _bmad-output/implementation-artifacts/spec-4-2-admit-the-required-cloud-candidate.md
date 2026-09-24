---
title: 'Story 4.2: Admit the Required Cloud Candidate'
type: 'feature'
created: '2026-09-24'
status: 'draft'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
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
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/backend/app/profiles/cloud_api.py` — Qwen adapter and request/response normalization in the separate branch; inspect and integrate, do not assume it exists in `main`.
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/evaluation/comparison-report-2026-09-24.md` — earlier pilot, isolated local profile and run readback; prior image set is not the accepted Story 4.1 campaign.
- `backend/app/application/admission.py` and `backend/app/adapters/postgres.py` — current local smoke, profile, authorization, reservation, and completion paths; reconcile against branch's cloud changes.
- `backend/app/application/executor.py` and `backend/app/main.py` — current local-only runtime path; integrate only bound admitted cloud execution, retaining no fallback.
- `backend/app/adapters/artifacts.py` and `backend/migrations/versions/0002_admission.py` — private publication/integrity and profile, authorization, invocation evidence owners.
- `backend/app/domain/observations.py:78` — closed two-class observation-state contract.
- `backend/tests/test_admission.py` — admission, fencing, artifact, and local failure tests; preserve local behavior.
- `evaluation/held-out-v1.json` and `backend/admission/exclusions/held_out_evaluation.json` — accepted Story 4.1 image identities and exclusion scope; do not reuse prior branch comparison images as scored cells.

## Tasks & Acceptance

**Execution:**
- `backend/app/profiles/cloud_api.py` — integrate the branch's bounded Qwen request and strict-schema normalization with transient credentials and an approved-image allowlist.
- `backend/app/application/admission.py` and `backend/app/adapters/postgres.py` — reconcile branch admission with current revisions, enforce current owner-account/model/quota/terms evidence and per-image authorization, then create a new immutable admitted successor only after canary and artifact readback.
- `backend/app/application/executor.py`, `backend/app/application/submission.py`, and `backend/app/main.py` — route explicitly bound admitted Qwen revisions through ordinary runs, preserving no fallback and rejection before upload.
- `backend/tests/test_cloud_profile.py`, `backend/tests/test_admission.py`, and `backend/tests/test_single_image.py` — verify gate failures, strict response, served identity, revocation, unauthorized image rejection, and local-profile compatibility.
- `backend/admission/exclusions/held_out_evaluation.json` and `evaluation/held-out-v1.json` — reconcile the Story 4.1 identities with the cloud profile's allowed hashes without admitting held-out images as smoke or silently modifying prior profile revisions.

**Acceptance Criteria:**
- Given any missing owner-account or data gate, when admission is attempted, then the profile remains draft and no image is uploaded.
- Given an image outside an admitted profile's authorized hashes, when a run is submitted, then it is rejected before artifact publication or provider inference and the profile authorization remains unchanged.
- Given approved canary data and the evidenced paid owner account, when admission runs, then the ordinary run records strict response, served URI, request data controls, private input/native artifacts, and an admitted enabled successor without claiming provider deletion.
- Given timeout, malformed output, absent served identity, or artifact failure, when the canary ends, then admission fails and neither an absence result nor fallback candidate is produced.

## Spec Change Log

- 2026-09-24: The owner approved `sprint-change-proposal-2026-09-24.md`, replacing GigaChat with Yandex AI Studio Qwen3.6 for an allowlisted prototype. The prior GigaChat dependency block is superseded; branch integration, live account gates, and the new Story 4.1 campaign remain unverified.

## Review Triage Log

## Verification

**Commands:**
- `cd backend && uv run --extra test pytest tests/test_admission.py tests/test_cloud_profile.py tests/test_single_image.py` — expected: local and cloud admission/run contracts pass after integration.
- `git diff --check` — expected: no whitespace errors.

**Manual checks (if no CLI):**
- Read back the owner's current paid account, model access, quota, applicable data/retention terms, canary response identity, and exact allowed-image scope. Historic branch evidence does not prove the later Story 4.1 campaign.

## Auto Run Result

Status: draft after the approved course correction; implementation and admission have not yet been re-run on current `main`.

Earlier blocking condition (superseded): the future-customer GigaChat account and upload/deletion canary were unavailable. The approved Qwen prototype has different gates. Its branch pilot is evidence for planning and integration, not proof that this Story 4.2 revision is implemented or admitted on current `main`.

---
title: 'Story 4.1: Freeze the Held-Out Evaluation Set'
type: 'feature'
created: '2026-09-24'
status: 'blocked'
review_loop_iteration: 0
followup_review_recommended: false
context: []
warnings: []
deferred: []
---

<intent-contract>

## Intent

**Problem:** The eleven proposed frames are listed but have not been verified and frozen as an independent, manually labeled evaluation set. The current manifest cannot establish readiness evidence or protect later reports from changes to fixture definitions.

**Approach:** Verify source bytes, manual labels, rights, grouping, context, and sufficiency for each frame; reject overlap with all other data tiers; then persist an immutable `EvaluationSetRevision` and its freeze decision.

## Boundaries & Constraints

**Always:** Preserve the exact 1+1+3+3+2+1 scenario composition and ordered image identities. Record both supported class labels, checksums, rights, cloud permission, context, test-specific sufficiency, exclusion inventory identities, and the freeze verdict. Treat changed evidence as a new revision; retain prior revision bindings.

**Never:** Freeze provisional labels, infer site/camera identity from a filename alone, present absent source bytes as verified, reuse admission or development images, expose private image bytes in the decision record, or silently treat a public archive's `train`/`valid` split as held-out from project training and validation.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Valid freeze | Eleven verified, adjudicated images with complete provenance and distinct tier identities | Immutable revision and recorded decision | No error expected |
| Duplicate source | Matching content hash or source/site/camera/time-sequence group in another tier | No revision is frozen | Record rejection and exact conflicting identity |
| Incomplete evidence | Missing bytes, adjudication, rights, context, or sufficiency | No revision is frozen | Report missing evidence explicitly |
| Later correction | Any fixture evidence changes after a freeze | New revision; earlier bindings remain valid | Reject in-place mutation |

</intent-contract>

## Code Map

- `evaluation/held-out-v1.json` — an earlier eleven-frame candidate set with provisional labels; it differs from the selected final set.
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/evaluation/final-held-out-v1.json` — final candidate identities, hashes, and scenarios; independent human adjudication is explicitly open, and per-frame context, rights, and sufficiency are absent.
- `/private/tmp/kaggle-construction-equipment.zip` — source archive with verified SHA-256 `215e3364701c60dcb9ebf12081083a14822b36da3ebd29484f641c8e98e88169`; all eleven selected JPEG and label members match the final manifest. `/private/tmp/lzt-construction-final-11` has nine selected JPEGs and three unselected JPEGs; two selected JPEGs remain only in the archive.
- `backend/admission/exclusions/held_out_evaluation.json` — held-out tier currently has no reserved groups or fixtures.
- `backend/admission/manifest.json` and `backend/admission/exclusions/{training,validation,development_acceptance}.json` — current exclusion inputs; empty training/validation inventories do not prove the published archive's splits were unused.
- `backend/app/domain/observations.py:15` — existing admission manifest validation pattern for hashes, groups, and exclusion tiers; hardcoded four-fixture admission semantics are not the evaluation contract.
- `backend/app/adapters/postgres.py:186` and `backend/migrations/versions/0002_admission.py:36` — hashed admission snapshot persistence pattern; no `EvaluationSetRevision` store exists.
- `_bmad-output/planning-artifacts/epics.md:885` and `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md:149` — story acceptance and immutable evidence contract.

## Tasks & Acceptance

**Execution:**
- `evaluation/held-out-v1.json` — replace provisional labels and inferred group identities with verified per-frame evidence and immutable source references.
- `backend/app/domain/observations.py` — add a separate evaluation freeze validator using existing checksum and exclusion ideas without weakening admission validation.
- `backend/migrations/versions/0009_evaluation_set.py` and `backend/app/adapters/postgres.py` — persist immutable revision, evidence identities, and freeze decision.
- `backend/admission/exclusions/held_out_evaluation.json` — reserve verified held-out hashes and source groups so future admissions reject reuse.
- `backend/tests/test_evaluation_set.py` — verify the complete scenario mix, missing evidence, overlaps, and immutable revisions through the persistence boundary.

**Acceptance Criteria:**
- Given the verified initial manifest, when it is frozen, then exactly eleven images in the specified six scenario groups are bound to a revision with both-class manual labels, checksums, context, rights, upload permission, and sufficiency notes.
- Given each other data-tier manifest, when the freeze gate runs, then matching content or source/site/camera/time-sequence identity is rejected and the decision records the conflict without source bytes.
- Given a frozen revision, when any fixture evidence changes, then a new immutable revision is required and earlier report bindings remain unchanged.

## Spec Change Log

## Review Triage Log

## Auto Run Result

Status: blocked

Blocking condition: intent gap and missing adjudication/provenance. The final eleven Kaggle image and label bytes are available and their hashes verified, but manual ground truth remains explicitly provisional, and site/camera grouping plus per-frame rights, context, and sufficiency have not been verified. The supplied manifest does not establish whether its `train` and `valid` source members were used in training or validation, or whether the ongoing cloud testing preceded the intended freeze. Freezing it would assert acceptance criteria that cannot be supported.

Unanswered decisions: Which source bytes and independently adjudicated labels are authoritative for these eleven frames? What evidence establishes capture/group identities, per-image usage and upload rights, and exclusion from all training and validation material?

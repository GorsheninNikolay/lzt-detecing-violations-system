---
title: 'Story 4.1: Freeze the Held-Out Evaluation Set'
type: 'feature'
created: '2026-09-24'
status: 'done'
route: 'dispatch'
review_loop_iteration: 0
baseline_commit: '9e512546b9b6d320b6a3fe9e0583dd189108192f'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The repository has an eleven-frame candidate manifest, but no immutable evaluation revision. Its candidate labels and source identities are unadjudicated, while a later eleven-frame set has already been used for local and cloud comparison, so neither can silently become a pre-campaign held-out baseline.

**Approach:** Keep the previously compared final set as historical comparison evidence. Verify a fresh eleven-frame source set and its manual evidence, reject overlap with other fixture tiers, and freeze one immutable `EvaluationSetRevision` with a recorded decision and stable report binding.

## Boundaries & Constraints

**Always:** The first revision has exactly 1 single-both, 1 single-excavator, 3 positive-series, 3 check-request-series, 2 insufficient-series, and 1 out-of-scope images in canonical order. Every image has verified bytes and checksum, both-class adjudicated labels, explicit context, source rights, cloud-upload permission, and test-specific sufficiency notes. Record exact source/site/camera/time-sequence groups and the inventory evidence used at freeze. Changes create a new revision.

**Never:** Infer capture identity solely from filename prefix; accept provisional YOLO labels as human ground truth; treat an empty training inventory as proof of non-use; retrospectively claim a pre-run freeze for the final set already used in comparison; overwrite old revisions or report bindings; include private image bytes in the decision record.

**Decision:** The owner will inspect the new candidate JPEGs and confirm or correct both-class labels and series grouping. The existing final comparison set remains historical and is excluded from the new revision. Until that review and source/upload permission are recorded, the freeze gate stays closed.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Complete proposed set | Eleven verified, adjudicated, rights-cleared frames with documented non-overlap | Freeze a new revision and record its decision and inventory hashes | No error expected |
| Cross-tier overlap | Same original or derived checksum, or same source/site/camera/time-sequence group | No revision is frozen | Record conflicting tier and identity |
| Missing evidence | Missing bytes, labels, rights, context, sufficiency, or group provenance | No revision is frozen | Return explicit missing-field evidence |
| Post-freeze correction | Changed image, label, right, context, or sufficiency | New immutable revision | Reject in-place update |

</frozen-after-approval>

## Code Map

- `evaluation/held-out-v1.json` — new eleven-frame manifest with owner-reviewed labels, context, rights caveat, sufficiency, and hashes of the owner review and attestation.
- `/private/tmp/lzt-yandex-cloud-ai-studio-20260924/evaluation/final-held-out-v1.json` — exact later set and hashes; label caveat says independent human adjudication is open. The worktree contains three local and cloud result files for this set.
- `/private/tmp/kaggle-construction-equipment.zip` — verified source archive containing all eleven selected image and label members; nine selected JPEGs are also in `/private/tmp/lzt-construction-final-11`.
- `/private/tmp/lzt-story-4-1-review-11` — review package with exactly eleven JPEGs and the owner-completed local form. The exported answers are retained in `evaluation/human-review-2026-09-24.json`.
- `backend/admission/exclusions/*.json` and `backend/admission/manifest.json` — exclusion inputs. The held-out inventory now reserves eleven hashes and conservative groups; owner attestation covers project non-use outside known files.
- `backend/app/domain/observations.py:15` — admission-specific hash/group validator worth reusing conceptually, not by weakening its four-fixture contract.
- `backend/app/adapters/postgres.py:50` and `backend/migrations/versions/0009_evaluation_set.py` — serialized freeze, immutable revision and decision persistence, and report binding.
- `backend/app/application/evaluation.py` and `backend/pyproject.toml` — operator CLI for installing the accepted revision into a migrated application database.
- `_bmad-output/planning-artifacts/epics.md:885`, `ARCHITECTURE-SPINE.md` AD-24 — initial set composition and immutable evidence owner.

## Tasks & Acceptance

**Execution:**
- [x] `evaluation/held-out-v1.json` — replace candidate references with approved frame evidence and explicit adjudication, rights, context, group, and sufficiency fields.
- [x] `backend/app/domain/evaluation_set.py` — validate composition, bytes, manual evidence, and all exclusion tiers before freezing.
- [x] `backend/migrations/versions/0009_evaluation_set.py` and `backend/app/adapters/postgres.py` — persist immutable revision and freeze decision with inventory identities.
- [x] `backend/admission/exclusions/held_out_evaluation.json` — reserve accepted checksums and source groups for other tiers.
- [x] `backend/tests/test_evaluation_set.py` — cover valid freeze, incomplete evidence, overlaps, and revision immutability through persistence.
- [x] `backend/app/application/evaluation.py` and `backend/pyproject.toml` — expose an explicit operator freeze command so the revision can be installed in a target application database.

**Acceptance Criteria:**
- Given an approved initial manifest, when freeze succeeds, then one immutable revision binds exactly eleven images in the required six scenarios with all per-image evidence.
- Given any training, validation, contract, admission, or development material, when the freeze gate runs, then content or source-group overlap is rejected and the decision records the conflicting identity without private bytes.
- Given a frozen revision, when any fixture evidence changes, then a new revision is required and prior report bindings remain unchanged.

## Implementation Notes

- The owner reviewed all eleven images and confirmed both-class presence and usability. The two insufficient-series images were marked as different observation areas, so insufficiency is based on both the two-frame count and lack of three same-area frames. Raw answers and owner non-use/cloud-use confirmation are retained under `evaluation/` and SHA-256-bound by the manifest.
- Source rights remain a declared Kaggle CC0 license plus the owner's prototype-use approval; original capture and camera ownership are unverified. Prefixes `237` and `648` are broad exclusion groups, not claims of exact camera identity.
- The accepted manifest hash is `bbc767cb2af37b88c09447dddea9123f0a3287c8e41cd0204df8d36c0b3459c6`. An isolated PostgreSQL accepted and read back an eleven-frame revision and decision; the source exclusion inventory reserves eleven hashes and both broad prefixes. Application-database migration, deployment, and runtime installation were not verified.
- The local review form in `/private/tmp/lzt-story-4-1-review-11/review.html` passed HTML structure and JavaScript syntax checks; browser rendering was not exercised because the agent did not open GUI applications.
- `evidence-evaluation freeze` installed an earlier reviewed manifest into a second clean isolated PostgreSQL database. After review corrections, the final manifest was installed into a third clean isolated database; SQL readback returned the final hash, 11 frames, and one accepted decision.

## Spec Change Log

## Review Triage Log

| Finding | Verdict / route | Evidence and action |
| --- | --- | --- |
| Blind 1 | low / reject | The file reservation can survive a failed DB insert, but this is conservative and retryable; accepted DB state is never published without a row. Keeping the exclusion is safer than removing it after an uncertain commit. |
| Blind 2 | medium / patch | A PostgreSQL advisory lock alone does not serialize two databases sharing one checkout; add a lock on the shared inventory file. |
| Blind 3 | medium / patch | A same-image successor revision was skipped by the hash-only inventory key; retain its own manifest provenance. |
| Blind 4 | high / patch | The export identified frames only by ID; derived review evidence now binds each answer to the verified image SHA-256, and the gate must check it. |
| Blind 5 | high / patch | Owner non-use and upload approval previously named no exact image set; the attestation now lists the ordered hashes and must be checked against the manifest. |
| Blind 6 | medium / patch | Nonempty context and sufficiency text did not prove required scenario facts; validate required fields and relationships. |
| Blind 7 | medium / patch | The insufficient pair was owner-marked as different areas but had one declared area; the manifest now assigns distinct areas and requires a new freeze readback. |
| Blind 8 | medium / patch | A mixed or reordered three-frame series could pass without affirmative same-area evidence; require owner confirmation and ordered frame identity. |
| Blind 9 | medium / patch | Out-of-scope had no frozen expected outcome or requested-class check; restore and validate the scenario contract. |
| Blind 10 | medium / patch | Hash-correct arbitrary bytes could pass as a JPEG; decode and verify each image before acceptance. |
| Blind 11 | medium / patch | Declared historical hashes/groups were not checked against archive members; verify their referenced bytes. |
| Blind 12 | medium / patch | An invalid ZIP or evidence structure could abort without a recorded rejection; return a byte-free rejection. |
| Blind 13 | medium / defer | The 17 GB source archive lives only in `/private/tmp`; private durable artifact publication is required before campaign execution. This Story 4.1 revision retains hashes, while Story 4.4 must verify the artifact store reference. |
| Edge 1 | high / patch | Same root as Blind 4: compare reviewed image SHA-256 with each frame. |
| Edge 2 | medium / patch | Same root as Blind 8: require affirmative area/order review for the two three-frame scenarios. |
| Edge 3 | medium / patch | Admission reserved groups without fixture rows were ignored; include reserved groups in overlap checks. |
| Edge 4 | medium / patch | Same root as Blind 12: catch unreadable or invalid ZIP input and record rejection. |
| Edge 5 | medium / patch | Original scenario expected outcomes had been removed; they are restored in the manifest and must be checked by the gate. |
| Verification 1 | medium / patch | The real manifest had only a negative missing-archive check; add an archive-enabled positive acceptance test. |
| Verification 2 | low / reject | Same root as Blind 1: conservative reservation before an uncertain DB commit is recoverable by retry and avoids exposure. |
| Verification 3 | medium / patch | Same root as Blind 6: require concrete per-frame context and sufficiency evidence. |

## Verification

**Commands:**
- `cd backend && uv run pytest tests/test_evaluation_set.py` — expected: freeze, rejection, and immutability cases pass against the real persistence contract.
- `cd backend && uv run alembic upgrade head` — expected: evaluation revision schema applies to a disposable database.

---
title: 'Clean up health objects in versioned S3 buckets'
type: 'bugfix'
created: '2026-09-22'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The startup S3 probe reports success on a versioned bucket even though its ordinary DELETE leaves the health object's byte-bearing version behind a delete marker. This was reproduced on MinIO and contradicts the cleanup gate in Story 1.1.

**Approach:** Make the health probe remove and verify every version it created under its unique key, including the ambiguous PUT-response case, while keeping failures unready. Verify the result against real unversioned and versioned MinIO buckets.

</frozen-after-approval>

## Implementation Notes

- `backend/app/adapters/artifacts.py`: list exact health-key versions after a versioned PUT or an ambiguous PUT response, remove them by `VersionId`, and verify the list is empty. Preserve the ordinary delete path for unversioned buckets.
- `backend/tests/test_startup.py`: use a separate temporary versioned MinIO bucket for successful cleanup, lost PUT response, and failed version deletion; remove test versions in fixture cleanup.
- `README.md`: document the bucket-level version-list and health-key version-delete permissions required when versioning is enabled.

## Review Triage Log

- `[false]` Suspended versioning leaves a delete marker while readiness succeeds: a `VersionId="null"` is truthy, so the code lists versions and fails readiness if the marker remains.
- `[false]` Ambiguous PUT adds a permission-dependent readiness failure to unversioned buckets: the PUT error already makes readiness false before cleanup, regardless of version-list permission.
- `[medium]` Versioned-bucket permissions were undocumented: added the required `ListBucketVersions` and `DeleteObjectVersion` actions to `README.md`; the real MinIO versioned probe exercises both operations.

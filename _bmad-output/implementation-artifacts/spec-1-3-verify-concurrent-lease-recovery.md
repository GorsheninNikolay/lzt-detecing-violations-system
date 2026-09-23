---
title: 'Verify concurrent lease recovery for Story 1.3'
type: 'chore'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Story 1.3 has sequential lease-fencing tests, but no controlled PostgreSQL overlap between a late completion and recovery after lease expiry.

**Approach:** Add a focused concurrency test that holds the completion transaction after its row lock, lets the database lease expire, attempts recovery, and proves the losing writer cannot commit a projection or overwrite the terminal failure. Repair a confirmed code defect only if this test exposes one.

</frozen-after-approval>

## Implementation Notes

- Added one PostgreSQL integration test in `backend/tests/test_single_image.py`. It pauses a provider-path completion immediately after `SELECT ... FOR UPDATE`, proves the database lease is still live, waits for expiry, and attempts recovery from a second connection.
- Recovery reports PostgreSQL SQLSTATE `55P03` while completion holds the row lock. Once released, completion's final live-lease guard rolls back its invocation completion, native artifact reference, observations, and projection. Expired renewal is rejected; a recovery retry writes the sole terminal failure.
- The test uses the existing isolated migrated database fixture. No production code or schema change was required.
- Verification: the initial controlled race passed 10/10 repetitions; the strengthened lock, SQLSTATE, and provider-path version passed 5/5 repetitions and once more after the renewal assertion.

## Review Triage Log

- `[medium]` The lease might already have expired before the completion lock — increased the lease and asserted it was live after the row lock was acquired.
- `[medium]` A generic recovery error could hide an unrelated failure — captured and asserted PostgreSQL lock-conflict SQLSTATE `55P03`.
- `[medium]` The test bypassed provider invocation writes — exercised a reserved invocation and native publication intent, then asserted their completion/reference did not commit.

---
title: 'Wait for bounded synchronous series effects'
type: 'bugfix'
created: '2026-09-23'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** A series batch timeout currently cancels only its async wait. The synchronous PostgreSQL, S3, or observer call may keep running after the executor records a terminal failure, creating late effects that were not accounted for.

**Approach:** Bound blocking calls at their own network/database/process layer, await any call already started, then check the shared batch deadline before starting another step or recording completion. Prove that a delayed publication cannot continue in the background after the run is marked failed.

</frozen-after-approval>

## Implementation Notes

- `backend/app/application/executor.py`: wait for each synchronous series step to return, then check the shared monotonic deadline; the observer's existing child-process timeout remains in force.
- `backend/app/adapters/artifacts.py`: bound S3 connection and socket reads to 5 and 30 seconds; retain the existing retry policy.
- `backend/app/adapters/postgres.py`: bound connection establishment, statements, and lock waits to 5, 30, and 5 seconds respectively. These are adapter-wide limits, also covering startup, admission, and submission calls.
- `backend/tests/test_ordered_series.py` and `backend/tests/test_startup.py`: verify delayed publication cannot outlive terminalization and read back effective PostgreSQL/S3 timeout settings.
- Review exposed cancellation during shutdown: `ClaimLoop.stop()` now clears readiness and drains an active execution rather than cancelling its running thread. The shutdown test covers this path; the existing already-cancelled-task behavior remains supported.
- Verification: the isolated PostgreSQL/MinIO backend suite passed 73 tests in 76.62s; `git diff --check` passed. Socket read timeout limits an idle read, while PostgreSQL statement timeout applies per statement; neither is an absolute wall-clock limit for a multi-call operation.

## Review Triage Log

- `[medium]` `[patch]` Shutdown could cancel an executor awaiting `to_thread`, leaving the synchronous effect running after lease renewal stopped. `ClaimLoop.stop()` now drains active work; a shutdown regression verifies that it waits.
- `[medium]` `[defer]` A peer streaming bytes continuously can outlast the S3 socket read timeout. This accepted bounded-wait approach does not provide an absolute operation deadline; that requires a separately isolated or cooperative transport.
- `[low]` `[reject]` A 30-second PostgreSQL timeout and 30-second S3 idle timeout need separate induced-stall tests. Effective settings are read back from PostgreSQL and botocore, and the delayed-publication regression verifies executor ordering; a long fault-injection test would add time without checking a product-owned branch.

# Release deployment gate

Do not deploy the jury release until its independent model acceptance passes. A draft PR may be published before that gate and must clearly report blockers.

Observed 2026-09-26: SSH user `gorshenin-nik`, host `158.160.42.119`, application release root `/home/gorshenin-nik/apps/construction-evidence-releases/c5766cc8eaacf9a16e9006d5c294ab6567b26a5e`, Compose project `construction-evidence`. Other applications own ports 80 and 443. Never replace their configuration or containers. The current public 8096 endpoint has no access control.

Before deployment:

1. Verify current PR head CI, independent review and model report against the exact SHA; merge only after release gates pass and record the merge SHA.
2. Build a release directory from that merge SHA; record image digests. Keep the previous release and images. Never copy secrets to an artifact or repository.
3. Take a PostgreSQL custom-format dump and a consistent copy of all private image/artifact object versions. Restore into isolated resources and compare row counts, latest migration, and artifact checksums. A successful backup command alone is not restore evidence.
4. Add the jury hostname to the existing HTTPS routing only after checking its ownership and live config. Use a trusted certificate. Apply access control at the common route covering HTML, `/api/` and image reads; prevent public access to the backend and old unauthenticated 8096 route. Do not claim that TLS alone provides authentication.
5. Keep the shared code outside Git and this package. Verify wrong/missing code denies HTML, API, evidence and submission; verify correct code works. Do not put the code in URLs or logs.
6. Apply only forward data-preserving migrations after backup/restore verification. Record versions before and after.
7. Run readiness, login, new JPEG and PNG upload, genuine model completion, expected warning, history and evidence-open checks. Record analysis IDs, model/rule/plan revisions, image hashes and UTC time. Reserve the maximum call cost before inference and count retries/unknown outcomes against the budget.
8. If smoke fails, restore the previous compatible application image and configuration. Do not automatically restore/drop the database or object store. Confirm readiness and document the failure.

At the time of this report none of steps 1–8 have been completed for the new release. The old service's successful readiness check is not a substitute.

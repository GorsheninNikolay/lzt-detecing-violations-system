# Construction Evidence Service

The API accepts single JPEG and ordered JPEG-series observation runs. PostgreSQL owns structured state; private S3-compatible storage owns bytes.

## Local start

Install `uv` and Docker with Compose. From this repository:

```sh
docker compose -f infra/compose.yaml up -d --wait
curl --retry 30 --retry-connrefused --retry-delay 1 -fsS http://127.0.0.1:59000/minio/health/live
cd backend
export DATABASE_URL='postgresql+psycopg://evidence:evidence-local@127.0.0.1:55432/evidence'
export S3_ENDPOINT='http://127.0.0.1:59000'
export S3_BUCKET='evidence-local'
export S3_ACCESS_KEY='evidence-local'
export S3_SECRET_KEY='evidence-local-secret'
uv lock --check
uv sync --frozen --extra test
uv run python ../infra/create_bucket.py
uv run alembic upgrade head
uv run evidence-service
```

The API listens on `127.0.0.1:8000`. `GET /health/live` returns process liveness. `GET /health/ready` returns HTTP 503 with a stable JSON code until migration-head verification, a rolled-back PostgreSQL write/read, a unique S3 `health/` write/HEAD/read/delete, a locked publication-intent scan, and lease-aware recovery all succeed; then it returns HTTP 200 with `{"ready": true, "code": "ready"}`. Failure codes contain no endpoint or credentials.

For a versioned S3 bucket, the startup identity also needs `s3:ListBucketVersions` on the bucket and `s3:DeleteObjectVersion` for `health/*`. The probe removes its exact object versions and checks that none remain; missing permissions keep readiness false.

## Isolated integration verification

Keep the local services running. Create a separate database once, then run the remaining commands from `backend/`:

```sh
docker compose -f infra/compose.yaml exec -T postgres createdb -U evidence evidence_test
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://evidence:evidence-local@127.0.0.1:55432/evidence_test'
export TEST_S3_BUCKET='evidence-test'
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
S3_BUCKET="$TEST_S3_BUCKET" uv run python ../infra/create_bucket.py
export TEST_MODEL_SNAPSHOT_DIR='/private/tmp/grounding-dino-tiny-e08274d'
uv run pytest
```

Prepare the pinned model snapshot as described below before running the full suite. On later runs, repeat the commands from `cd backend`. The suite fails if its PostgreSQL or S3 configuration is missing, the test database is unmigrated, the model snapshot is absent, or the test database/bucket matches the application target. The real CPU admission test creates and drops its own PostgreSQL database; its published bytes remain in the isolated test bucket.

The directory boundaries are `backend/app/domain` for evidence contracts, `application` for orchestration, `ports` for external contracts, `adapters` for PostgreSQL and S3, `profiles` for observer revisions, `migrations` for schema, `web` for the responsive client, `evaluation` for separate fixtures, and `infra` for local dependencies.

## Responsive web client

After starting the ready backend with an admitted observer profile, run `cd web && npm ci && npm run dev` and open `http://127.0.0.1:5173`. The development server proxies `/api/runs/*` to backend `/runs/*` and serves `/runs/{run_id}` as a web page. The Russian New Analysis page accepts a single JPEG or an ordered series of 2–8 JPEGs, preserves duplicate frames and local order, and submits `observation_only` with scenario, area, and timezone-aware period. It routes to `/runs/{run_id}` only when the API returns an ID. See [web/README.md](web/README.md) for validation, retry, and route limits.

## Initial local observer admission

The committed `backend/admission/manifest.json` contains four JPEGs and paired YOLO labels extracted from the organizer-linked Kaggle Construction equipment archive. The card declares CC0; original site/camera provenance remains unverified. Source groups `1235`, `1233`, `1422`, and `1325` are reserved for admission and must stay out of training, validation, development acceptance, and held-out evaluation inventories. To re-extract the exact files, use the archive member paths in the Story 1.2 implementation spec and compare each output with the manifest SHA-256. Do not commit the full archive.

On the required Apple M3 Pro (12 CPU cores, 36 GB RAM), prepare the immutable model snapshot once while online. Keep the snapshot outside the repository:

```sh
cd backend
uv lock --check
uv sync --frozen --extra test
uv run evidence-admission prepare --snapshot-dir /private/tmp/grounding-dino-tiny-e08274d
```

`prepare` downloads only `IDEA-Research/grounding-dino-tiny` revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e` and writes the per-file hashes to `admission/model-files.json`. Review and commit any changed hash file with the lock. `run` compares the complete local snapshot against those hashes and loads it with Hugging Face offline mode and CPU-only execution. It rejects an incomplete exclusion inventory before creating runs.

With migrated PostgreSQL and a private S3 bucket configured as above, run:

```sh
uv run evidence-admission run \
  --snapshot-dir /private/tmp/grounding-dino-tiny-e08274d \
  --exclusion-inventory admission/exclusions/training.json \
  --exclusion-inventory admission/exclusions/validation.json \
  --exclusion-inventory admission/exclusions/development_acceptance.json \
  --exclusion-inventory admission/exclusions/held_out_evaluation.json
```

The command prints draft, run, and admitted successor IDs. A null admitted ID means at least one fixture failed; inspect `analysis_runs.error_code` and retained `analysis_stages`, `observer_invocations`, and `publication_intents`. The draft never becomes admitted in place. Only an admitted successor with enabled authorization can be bound as `OBSERVER_PROFILE_ID` for future ordinary runtime. Use a new admission run after a failure; never edit terminal evidence.

For isolated contract tests, use the `evidence_test` database, `evidence-test` bucket, and `TEST_MODEL_SNAPSHOT_DIR` described above, then run `uv run pytest`. Podman Compose can start the same `infra/compose.yaml` services when Docker Compose is unavailable; omit Docker's `--wait` option and check container health before tests.

## Qwen3.6 cloud admission

Cloud admission uses only the four JPEGs in `backend/admission/manifest.json` as canaries and the owner decision in revision `1512020047aa5e2b2fc343f78f9881a0a2c5914c`. The new profile allowlist also contains the eleven separately approved Story 4.1 held-out hashes. Admission checks `evaluation/held-out-v1.json`, `evaluation/owner-attestation-2026-09-24.json`, and `evaluation/freeze-decision-v1.json` against their accepted hashes and disjointness before any upload; it never reads or sends held-out image bytes. Supply a transient AI Studio API key with `yc.ai.foundationModels.execute`, its ID, and an IAM token with read access to the configured folder, service account, API key, and billing accounts. The API key is used for both the no-image probe and all canary requests. Neither credential is written to profile evidence.

Create a private JSON input containing only `folder_id`, `service_account_id`, and `authorization_revision` (the revision above). Set `YANDEX_AI_STUDIO_API_KEY`, `YANDEX_AI_STUDIO_API_KEY_ID`, and `YANDEX_CLOUD_IAM_TOKEN` in the process environment, then run `evidence-admission run-cloud --evidence <private-json-path> --exclusion-inventory <path>` with each of the four inventories under `backend/admission/exclusions/`. The command first checks the exact manifest, account binding, active identities, key scope, and a strict no-image model response. A failed gate leaves a draft and sends no image. Use the returned admitted profile ID as `OBSERVER_PROFILE_ID` only after reading back its persisted evidence and private artifacts.

Delete the transient admission API key after the canary. For ordinary runs, configure a new scoped API key and its ID for the same active service account. Each invocation verifies that key, the folder and billing binding, and model access before uploading an image. The admitted profile retains the admission key ID as historical evidence; each private native artifact records the key ID actually used for its invocation. An expired admission gate still requires a new profile revision.

## Single-image observations

Start the service with `OBSERVER_PROFILE_ID` set to the admitted successor ID. For a local profile, also set `OBSERVER_SNAPSHOT_DIR` to the verified offline snapshot used for admission; its observer runs in a bounded CPU child process without model download or fallback. For a cloud profile, provide current transient credentials as described above. The service refuses submissions until readiness and the profile binding succeed.

Submit one JPEG as base64 in JSON. `scenario`, `observation_area`, and `period` are required; `period` is an ISO 8601 timestamp with timezone. `requested_classes` defaults to `excavator` and `dump_truck`. Other requested class names are retained as `not_analyzed` without a provider call when no supported class is requested.

```sh
IMAGE_BASE64=$(base64 < development-image.jpg | tr -d '\n')
curl -sS -X POST http://127.0.0.1:8000/runs/single-image \
  -H 'Content-Type: application/json' -H 'Idempotency-Key: example-001' \
  -d "{\"intent\":\"observation_only\",\"scenario\":\"equipment_check\",\"observation_area\":\"north_gate\",\"period\":\"2026-09-23T12:00:00+03:00\",\"image_base64\":\"$IMAGE_BASE64\"}"
curl -sS http://127.0.0.1:8000/runs/RUN_ID
```

The submit response contains the authoritative `run_id` and current state. Reusing the key with the same logical request returns that run; changing image bytes, context, or classes returns `idempotency_key_conflict`. The read response contains six persisted stages, requested class states with source artifact IDs, a native evidence digest when inference ran, and `observations_only` only after success. It does not return S3 keys, signed URLs, or portable counts/confidence/geometry. Invalid or undecodable files return `invalid_image_file` before any run or evidence reference is created.

## Ordered-series observations

Submit 2–8 JPEGs to `POST /runs/series` with the same context and `Idempotency-Key` as the single-image request, replacing `image_base64` with an `images_base64` JSON array. Array position defines frame order; each item is limited to 16 MB of decoded bytes and 40 million pixels. The HTTP body limit is 200 MB. Reversing distinct images under the same idempotency key returns `idempotency_key_conflict`.

`GET /runs/{run_id}` returns `inputs` in zero-based order, each with a stable `input_id`, checksum, size, and source artifact ID. `observations` include that input ID and ordinal, class state, reason where needed, source artifact ID, and completed invocation ID for provider-derived states. `native_evidence_by_frame` attributes retained native evidence to its frame. Equal image bytes may share an S3 object, but retain separate input and observation references. The series projection appears only after every frame has a closed class set. A later technical failure leaves the run failed with earlier evidence visible and no projection. Results describe individual frames only; no area-wide absence is inferred.

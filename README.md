# Construction Evidence Service

Story 1.1 starts one API process with a readiness gate. It does not yet accept analysis submissions. PostgreSQL owns all structured state; private S3-compatible storage owns bytes.

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

The directory boundaries are `backend/app/domain` for evidence contracts, `application` for orchestration, `ports` for external contracts, `adapters` for PostgreSQL and S3, `profiles` for observer revisions, `migrations` for schema, `web` for the future client, `evaluation` for separate fixtures, and `infra` for local dependencies.

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

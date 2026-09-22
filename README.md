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

## Isolated integration verification

Keep the local services running. Create a separate database once, then run the remaining commands from `backend/`:

```sh
docker compose -f infra/compose.yaml exec -T postgres createdb -U evidence evidence_test
cd backend
export TEST_DATABASE_URL='postgresql+psycopg://evidence:evidence-local@127.0.0.1:55432/evidence_test'
export TEST_S3_BUCKET='evidence-test'
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
S3_BUCKET="$TEST_S3_BUCKET" uv run python ../infra/create_bucket.py
uv run pytest tests/test_startup.py
```

On later runs, repeat the commands from `cd backend`. The suite fails if its PostgreSQL or S3 configuration is missing, the test database is unmigrated, or the test database/bucket matches the application target. It changes schema and cleans health objects only in those isolated test resources.

The directory boundaries are `backend/app/domain` for evidence contracts, `application` for orchestration, `ports` for external contracts, `adapters` for PostgreSQL and S3, `profiles` for observer revisions, `migrations` for schema, `web` for the future client, `evaluation` for separate fixtures, and `infra` for local dependencies. The empty folders reserve those concerns without introducing premature APIs.

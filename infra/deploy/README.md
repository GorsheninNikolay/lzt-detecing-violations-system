# Server deployment

The deployment uses a dedicated Compose project, persistent PostgreSQL and MinIO volumes, and one public HTTP port. PostgreSQL, MinIO, and the API are internal to the Compose network. The web container proxies `/api/*` to the API. The public API exposes run evidence and can trigger paid cloud inference without authentication.

Build the web client locally with `cd web && npm ci && npm run build`. Transfer `backend/`, `evaluation/`, `infra/deploy/`, `web/dist/`, and `.dockerignore` to the server without virtual environments or `node_modules`. At the server's deployment root, create a private `.env` (`chmod 600`) containing `DEPLOY_PORT`, `POSTGRES_PASSWORD`, and `MINIO_ROOT_PASSWORD`. Use distinct random passwords with only URL-safe characters.

From that root, run:

```sh
docker compose --env-file .env -f infra/deploy/compose.yaml build backend init web
docker compose --env-file .env -f infra/deploy/compose.yaml up -d --no-build
curl -fsS http://127.0.0.1:8096/api/health/ready
```

Open `http://158.160.42.119:8096` directly.

The Linux backend image includes the Yandex Cloud observer path and excludes the macOS-only Grounding DINO runtime. An admitted cloud profile additionally requires `YANDEX_AI_STUDIO_API_KEY`, `YANDEX_AI_STUDIO_API_KEY_ID`, and `OBSERVER_PROFILE_ID` in the private `.env`. The backend obtains its refreshable IAM token from Yandex Compute Cloud VM metadata. The VM service account must be authorized to inspect its account and scoped API key, read the linked billing account, and invoke AI Studio. Cloud admission must succeed before setting `OBSERVER_PROFILE_ID`; merely starting the API does not authorize analysis. The admitted profile's image allowlist still applies to submissions.

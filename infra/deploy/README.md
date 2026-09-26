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

## Jury HTTPS overlay (not yet deployed)

The jury release must use the additional `jury.compose.yaml` overlay. It replaces
all web port bindings with HTTPS on `JURY_HTTPS_PORT` (default 8443), so the old
unauthenticated 8096 route is not published by this Compose service. It applies
HTTP Basic authentication to HTML, API and evidence routes. The shared username
is `jury`; the shared jury code is the password. Browsers show a native login
prompt. No secret is included in the image or repository.

Provide a trusted certificate chain for the selected hostname, its private key,
and a private htpasswd file through absolute `JURY_TLS_CERT`, `JURY_TLS_KEY`, and
`JURY_PASSWORD_FILE` paths. Generate the password file outside the repository with
`htpasswd -c /private/path/jury.htpasswd jury` (interactive password input), then
restrict file permissions. Do not use a self-signed certificate for final acceptance.
Configure the selected public hostname and port; existing services currently own
ports 80 and 443 on the documented host, so do not replace them.

```sh
docker compose --env-file .env -f infra/deploy/compose.yaml \
  -f infra/deploy/jury.compose.yaml config --quiet
docker compose --env-file .env -f infra/deploy/compose.yaml \
  -f infra/deploy/jury.compose.yaml up -d --no-build
```

Deploy only after the release gates and restored-backup checks in
`docs/jury-release/deployment-runbook.md` pass. Verify that unauthenticated requests
to `/`, `/api/health/ready`, `/api/runs`, and evidence endpoints return 401, that
correct credentials allow access, and that plain HTTP/8096 cannot bypass it.
Never send the jury code over the old HTTP endpoint. This configuration has not
been installed on the existing service; its presence is not proof of HTTPS access.

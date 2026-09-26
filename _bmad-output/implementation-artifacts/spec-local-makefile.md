---
title: 'Local project startup with Make'
type: 'chore'
created: '2026-09-27'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent">

## Intent

Provide a root Makefile that builds and starts the existing application locally, with simple commands to inspect and stop it while preserving data.

</frozen-after-approval>

## Implementation Notes

- Reuse infra/deploy/compose.yaml and its initialization of migrations, S3, and the source catalog. Build web/dist before the nginx image.
- Use a separate local Compose project, loopback binding, and overridable local passwords. Cloud credentials stay in the invoking environment.
- Add startup, build, shutdown, logs, status, readiness, and profile commands; document prerequisites in README.md.
- Verify Make command execution and frontend build. Full container startup requires an available Compose provider and container engine.
- Passed frontend production build, podman-compose configuration parsing, and executable-stub checks for command order, port overrides, volume preservation, and stopping after build failure.
- Podman is reachable outside the sandbox; full image build and container startup were not executed.

## Review Triage Log

- Medium, patched: installed podman-compose does not support --wait. Use up -d followed by API readiness retries.
- Medium, patched: password overrides cannot rotate credentials in an existing PostgreSQL volume. Document first-start selection and retaining the same password.
- Low, rejected: container admin-password setup is outside local startup scope, and the existing Compose HTTP admin route independently requires TLS/trusted-proxy configuration. Do not add an admin setup target that implies that login works through this route.

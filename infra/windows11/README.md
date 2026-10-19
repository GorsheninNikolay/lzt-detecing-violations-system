# LztEvidence on Windows 11

Local deployment, separate from Razryad. No Git push or CI delivery was configured.

Public URL: https://nikolay.tailaf11dc.ts.net:8443/
Windows root: `C:\ProgramData\LztEvidence`; WSL distribution: `LztEvidence`.
The Windows task `LztEvidence-Web` runs the CLI supervisor at boot, keeps WSL alive,
and restarts after failure. Linux systemd manages PostgreSQL 17, MinIO,
`lzt-backend` and `lzt-web`. HTTP binds to `127.0.0.1:3000`; backend to
`127.0.0.1:8007`; private storage to `127.0.0.1:9000`.

Production source lives under `/opt/lzt/releases`, selected by `/opt/lzt/current`.
`current.txt` on Windows records its identity. `release.json` pins every source,
asset, catalog and detector file. `package_release.py` packages an explicit
allowlist, excluding secrets, user data and previous evaluation results.
`setup_app.py` initializes only this application's isolated services.
`activate_release.py` verifies a release archive, records the previous selection,
normalizes admission files to root:lzt 0640 and restarts only this application's
backend and web server. Never edit an existing release in place.

Owner credentials are in the protected Windows file
`C:\ProgramData\LztEvidence\secrets\admin-login.json`; login `gorshenin-nik`.
DeepSeek key is in `secrets\deepseek_api_key`, transferred with explicit owner
approval. Linux configuration is in `/etc/lzt` with mode 0600. Do not print,
commit or publish these files. `probe_credentials.py` reports balance without
printing credentials. `probe_app.py` reads the administrator credential locally,
checks assets, API, project/plan/cover behavior, and optionally performs paid
synthetic analysis with `--live-analysis` and `--series`. It never retries a model
call. Run IDs and idempotency keys are saved before polling; read the existing
run before attempting further writes after a timeout.

Logs: Windows `logs\supervisor.log`, evidence JSON under `logs`; Linux
`/var/log/lzt`, plus `journalctl -u lzt-backend -u lzt-minio -u lzt-web`.
Persistent database: `/var/lib/postgresql/17/main`; object storage:
`/var/lib/lzt/artifacts`. These are newly initialized data, not copied user data.

Run `backup_app.py` as root through WSL. It temporarily stops only this app's
web/backend/MinIO, creates a PostgreSQL custom dump and storage/config archive
under `C:\ProgramData\LztEvidence\backups\<UTC stamp>`, validates the dump with
`pg_restore --list`, writes SHA-256 manifest and restarts its units in `finally`.
Backups contain secrets; preserve the restricted Windows ACL and never expose
or add them to Git.

Restore is an explicit data replacement operation: first take a new backup,
stop only this app's web/backend/MinIO, verify every selected backup checksum,
restore the custom dump into this app's database using `pg_restore --clean
--if-exists --no-owner --no-acl` and its private local credential, and restore
`artifacts` and `config` from the paired archive. Restore storage ownership to
lzt:lzt and configuration to root with 0600 secret files. Select the matching
release from the backup's release.json, start units and check readiness, source
images, plans and public HTTPS. Do not restore over another app or reset Funnel.
This procedure is documented; no destructive restore was performed.

The supplied detectors are preserved in gitignored `artifacts/Models`, including
an exact backup of the previous Kaggle file. New Kaggle SHA-256:
`d896a274a63ee80aa4ddc7e2f69afe33a7fb9f2f5d4f6f9e0e5ca16ed1f1b9e1`;
Apoce SHA-256:
`db44473297767157a13a3d534668a16b336ab18c54bd1814e39f8eab1874c705`.
The uploaded Kaggle file differs from the historical 72aca971 checkpoint;
historical quality benchmarks do not qualify this new checkpoint.

Actual Windows reboot and GUI/visual acceptance were not performed. Startup task
restart and isolated backend crash recovery were checked without rebooting Windows.
Detailed dated acceptance evidence and remote administration commands are stored
in the owner's private network project under `deployment/lzt-evidence/README.md`.

# Final Technology and Version Review

Reviewed artifact: `../ARCHITECTURE-SPINE.md`

Review date: 2026-09-21

## Verdict

**PASS.** The updated technology seed is internally coherent and proportionate for the greenfield MVP. Every exact version exists as a stable release; Node is on an LTS line; the frontend starter is pinned and reproducible through a committed lockfile; SQLite's runtime, concurrency, WAL, and storage constraints are now explicit; and Python compatibility with the deferred detector is protected by a binding verification gate.

No blocking or medium-severity technology/version findings remain.

## Remaining finding

### F1 — LOW: Pin the build tools and SQLite delivery mechanism in deployment assets

The application dependency pins and lockfiles are now reproducible, but the structural seed names `uv` without a tool version and requires SQLite 3.53.4 without identifying how the container supplies that native library. A Python 3.13.15 image does not itself prove which SQLite library `sqlite3` is linked against. AD-14's startup assertion correctly prevents an unsafe deployment, but a clean build could still fail late if the base image carries an older SQLite.

This does not require another architecture decision. In the initial deployment assets:

- pin the container base by immutable digest;
- pin the `uv` binary/version used to produce and install `uv.lock`;
- install or build SQLite 3.53.4 deterministically and verify `sqlite3.sqlite_version_info` during image build as well as startup;
- run `uv sync --locked` in the final dependency-install step;
- use the committed frontend package lock with the package manager's frozen/clean-install mode.

Primary evidence: [Python `sqlite3` runtime-version API](https://docs.python.org/3.13/library/sqlite3.html), [uv Docker reproducibility guidance](https://docs.astral.sh/uv/guides/integration/docker/), [SQLite 3.53.4 release history](https://sqlite.org/changes.html).

## Exact-pin verification

| Technology | Verified state on 2026-09-21 | MVP fit |
| --- | --- | --- |
| Python 3.13.15 | Stable supported bugfix release | Good backend baseline; detector fit is gated before AC freeze |
| FastAPI 0.141.1 | Stable release and latest in official release notes | Good for the API and built-SPA serving boundary |
| SQLAlchemy 2.0.54 | Current stable 2.0 release; 2.1 remains RC | Conservative and appropriate |
| SQLite 3.53.4 | Current stable maintenance release | Good for bounded one-host operation |
| React 19.3 | Stable release | Good for the small client-rendered jury UI |
| TypeScript 6.0.3 | Stable patch release; 7.0 is newer but has a changed compiler/tooling model | Defensible compatibility choice for this MVP |
| Vite 8.3.0 | Stable release | Good; exact version and starter are both pinned |
| Node.js 24.21.0 | LTS release | Good and satisfies Vite 8's Node requirement |
| create-vite 9.2.1 | Stable published starter release | Good with the `react-ts` template and committed lockfile |

Primary sources: [Python 3.13.15](https://www.python.org/downloads/release/python-31315/), [Python supported-version status](https://devguide.python.org/versions/), [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/), [SQLAlchemy downloads](https://www.sqlalchemy.org/download.html), [React 19.3](https://react.dev/blog/2026/09/09/react-19-3), [TypeScript releases](https://github.com/microsoft/TypeScript/releases), [Vite and create-vite releases](https://github.com/vitejs/vite/releases), [Node.js release status](https://nodejs.org/en/about/previous-releases).

## Starter reproducibility

The updated seed resolves the earlier ambiguity:

- `create-vite@9.2.1` exists and officially supports the `react-ts` template.
- Node.js 24.21.0 is an LTS version and is above Vite 8's supported Node floors.
- A committed frontend package lock makes the starter's semver ranges deterministic.
- A `uv` project with committed `uv.lock` is an official reproducible-project path.
- Keeping detector dependencies inside the same Python lock prevents an undocumented second runtime.

The prose could be implemented directly as `npm create vite@9.2.1 frontend -- --template react-ts`; spelling out the literal command in the spine is optional because the package, version, template, and lockfile contract are already unambiguous.

Primary sources: [create-vite templates and CLI](https://github.com/vitejs/vite/blob/main/packages/create-vite/README.md), [create-vite 9.2.1 release](https://github.com/vitejs/vite/releases), [uv project and lockfile features](https://docs.astral.sh/uv/getting-started/features/), [Vite 8 Node requirements](https://vite.dev/blog/announcing-vite8).

## SQLite runtime and storage coherence

AD-14 now correctly binds all material SQLite constraints:

- one host and one application-level write owner;
- short request/job-scoped SQLAlchemy sessions rather than one shared session;
- model subprocesses return typed values and never write the database;
- WAL and busy timeout are enabled and verified;
- SQLite runtime must be at least 3.51.3, while the deployment pin is the current 3.53.4;
- storage must be local or block-backed, and network filesystems are forbidden.

This is consistent with SQLite WAL's same-host requirement and its one-writer-at-a-time behavior. It is also compatible with SQLAlchemy's guidance: sessions remain local to request/job execution and inference must not hold a database transaction open. The architecture appropriately requires migration to PostgreSQL and object storage before multiple write-owning hosts/workers are introduced.

Primary sources: [SQLite WAL documentation](https://www.sqlite.org/wal.html), [SQLAlchemy 2.0 SQLite dialect](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html).

## Python detector compatibility gate

The previous unverified claim is resolved. Python 3.13.15 is now a concrete backend baseline, while the still-unselected detector is required, before acceptance-criteria decomposition, to:

1. install with its CPU inference runtime from the committed lock;
2. run an end-to-end fixture on Python 3.13.15;
3. cause the single Python pin to be revised if incompatible, rather than silently creating a second environment.

That gate is correctly timed and testable. It preserves a single deployable runtime without pretending that compatibility with an unknown native ML stack has already been proven.

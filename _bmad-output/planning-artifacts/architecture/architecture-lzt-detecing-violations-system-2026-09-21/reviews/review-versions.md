# Technology and Version Review

Reviewed artifact: `_bmad-output/planning-artifacts/architecture/architecture-lzt-detecing-violations-system-2026-09-21/ARCHITECTURE-SPINE.md`

Review date: 2026-09-21

## Verdict

**PASS WITH CHANGES.** The selected stack and single-host topology are proportionate for the greenfield MVP. All named releases exist, and none is prerelease or end-of-life. Before finalizing the spine, correct the SQLite pin and turn the unverified local-ML/Python compatibility claim into an explicit gate. The frontend combination is coherent; the seed needs one reproducibility clarification.

## Findings

### F1 — MEDIUM: SQLite `3.51.3` is a valid safety floor, but not a current exact stack pin

The spine presents SQLite `3.51.3` as the exact stack version while AD-14 says the runtime must be `3.51.3 or later`. Version 3.51.3 is important because it is the first 3.51 patch that fixes the WAL-reset corruption bug, but the current stable SQLite release is 3.53.4. The exact stack entry is therefore stale and conflicts with the intended minimum-version rule.

There is also a delivery gap: Python's `sqlite3` module reports the SQLite library it was compiled against, so pinning Python alone does not guarantee the required SQLite runtime. The clean-start check must inspect `sqlite3.sqlite_version` and fail below the chosen floor.

Recommended resolution:

- Express the architectural constraint as `SQLite >= 3.51.3`.
- Pin the deployment image to the current verified patch, presently `3.53.4`, or document why the maintained 3.51 line is deliberately retained.
- Add a startup/runtime assertion using `sqlite3.sqlite_version_info`.
- Require the SQLite database and WAL files to reside on host-local/block-backed storage, not a network filesystem; SQLite WAL requires all processes to be on the same host and does not work over network filesystems.

Evidence: [SQLite release history](https://sqlite.org/changes.html), [SQLite WAL documentation](https://www.sqlite.org/wal.html), [Python 3.13 `sqlite3` documentation](https://docs.python.org/3.13/library/sqlite3.html).

### F2 — MEDIUM: Python 3.13.15 is stable, but its fit for the local detector is not yet established

Python 3.13.15 exists, is a supported stable bugfix release, and is suitable for FastAPI and SQLAlchemy. However, the local detector/model runtime is explicitly deferred. Until that adapter and its native dependencies are selected, the architecture cannot claim that Python 3.13 is the compatible or conservative ML baseline. Native ML packages, model exporters, and CPU runtimes commonly constrain supported Python versions independently of the web stack.

Recommended resolution: retain Python 3.13.15 as a web/backend baseline only if it is marked provisional, and add a binding gate to the deferred provider decision: the selected detector and CPU inference runtime must install from a clean lockfile/container and pass one end-to-end fixture on Python 3.13.15. If they do not, change the Python pin before acceptance criteria are frozen rather than adding a second Python runtime implicitly.

Evidence: [Python 3.13.15 release](https://www.python.org/downloads/release/python-31315/), [official Python version status](https://devguide.python.org/versions/).

### F3 — LOW: TypeScript 6.0 is stable but is no longer the current compiler line, and the pin is incomplete

TypeScript 6.0 is a stable release, but the TypeScript team describes it as the bridge and final JavaScript-based release; TypeScript 7.0 is already released. Retaining 6.0 is defensible because 7.0 does not yet expose the traditional compiler API and ecosystem tooling may still require it, but the spine should not imply that 6.0 is the latest current line. `6.0` also omits a patch version while the other stack entries are exact.

Recommended resolution: either pin the actual resolved 6.0.x package in the lockfile and record that it is chosen for tooling compatibility, or prove the chosen lint/test plugins work with TypeScript 7 and use the current line. Do not adopt 7 merely for novelty; this MVP does not benefit materially from the compiler migration.

Evidence: [TypeScript 6.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-6-0/), [TypeScript 7.0 announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/).

### F4 — LOW: The structural seed is coherent, but it does not yet name a reproducible starter command

FastAPI serving a built React SPA, an application-owned executor, SQLAlchemy, SQLite, and a filesystem artifact adapter form a coherent small-MVP seed. Avoiding the official full-stack template also fits the scope because authentication, PostgreSQL, and production ingress from that template would add unused surface area.

However, `Structural Seed` is only a directory sketch. Independently implemented stories could choose incompatible Vite templates, package-manager behavior, Python packaging, and lockfiles. The current Vite repository publishes `create-vite@9.2.1`, and Vite recommends pinning within a minor when TypeScript-definition compatibility matters.

Recommended resolution: before implementation, record the exact frontend scaffold (`create-vite` React + TypeScript), package manager and committed lockfile, plus the Python project/lock mechanism. This is seed, not a new architectural abstraction.

Evidence: [official Vite releases](https://github.com/vitejs/vite/releases), [Vite release policy](https://vite.dev/releases).

## Verified technology matrix

| Technology | Verification | Fit for this MVP |
| --- | --- | --- |
| Python 3.13.15 | Exists; stable bugfix release; supported through 2029 | Good for backend; local-model fit remains unverified (F2) |
| FastAPI 0.141.1 | Exists; latest release listed in official release notes | Good; includes direct frontend serving support useful to the single-app deployment |
| SQLAlchemy 2.0.54 | Exists; current stable 2.0 release; 2.1 remains RC | Good; use explicit modern transaction control and short write transactions with SQLite |
| SQLite 3.51.3 | Exists; fixes WAL-reset bug | Valid minimum, not current exact pin; current stable is 3.53.4 (F1) |
| React 19.3 | Exists; stable release | Good; no server-component framework is required for this SPA |
| TypeScript 6.0 | Exists; stable bridge release | Usable, but superseded by 7.0 and incompletely pinned (F3) |
| Vite 8.3 | Exists; stable release | Good; pin exact package version/lockfile |
| Node.js 24.21.0 | Exists; LTS | Good; satisfies Vite 8's Node requirements |

Sources: [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/), [SQLAlchemy downloads](https://www.sqlalchemy.org/download.html), [React 19.3](https://react.dev/blog/2026/09/09/react-19-3), [Vite 8 announcement and Node requirements](https://vite.dev/blog/announcing-vite8), [Node.js release status](https://nodejs.org/en/about/previous-releases), [Node.js 24.21.0 release](https://nodejs.org/en/blog/release/v24.21.0).

## SQLite and topology coherence

The one-host, one-application write-owner boundary is the right constraint for this MVP and is consistent with SQLite's single-writer nature. The executor may use separate sessions/connections as long as all mutation is coordinated inside the one application process, transactions stay short, and model inference never holds a database transaction open. A child model process returning typed values rather than writing SQLite directly is coherent.

The phrase "one application owns SQLite writes" should not be implemented as one long-lived SQLAlchemy `Session` shared across requests/tasks. SQLAlchemy sessions are mutable transaction objects and must not be shared concurrently. Use request/job-scoped sessions, serialize lifecycle transitions at the application-service boundary, configure a busy timeout, enable and verify WAL explicitly, and test restart/checkpoint behavior on the actual persistent volume.

Evidence: [SQLAlchemy 2.0 SQLite dialect and transaction guidance](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html), [SQLite WAL documentation](https://www.sqlite.org/wal.html).

## Confirmed coherent choices

- Node.js 24 is LTS and comfortably satisfies Vite 8's requirement of Node 20.19+ or 22.12+.
- React 19.3 and Vite 8.3 are stable releases and appropriate for a small client-rendered jury interface.
- FastAPI 0.141.1 and SQLAlchemy 2.0.54 are stable current releases; selecting SQLAlchemy 2.0 instead of the 2.1 release candidate is conservative and correct.
- One built React bundle served by FastAPI is simpler than a separately deployed frontend and preserves the single public URL invariant.
- SQLite plus immutable filesystem artifacts is proportionate at the explicitly bounded one-host scale, provided the volume and runtime checks in F1 are made concrete.

# Final Technology Review — Deployment Pin Clarification

Reviewed artifact: `../ARCHITECTURE-SPINE.md`

Review date: 2026-09-21

## Verdict

**PASS.** No blocking, high, or medium technology/version findings remain.

The new pre-deployment gate closes the only residual reproducibility gap from the prior review. Before the first deployable image, the spine now requires:

- an immutable container-base digest;
- a pinned `uv` tool version;
- deterministic provision of SQLite 3.53.4;
- `sqlite3.sqlite_version_info` verification during both image build and application startup;
- frozen installation from committed Python and frontend lockfiles.

These requirements make the exact stack pins deliverable rather than merely documentary.

## Confirmed closure

- **Exact releases:** Python 3.13.15, FastAPI 0.141.1, SQLAlchemy 2.0.54, SQLite 3.53.4, React 19.3, TypeScript 6.0.3, Vite 8.3.0, Node.js 24.21.0 LTS, and create-vite 9.2.1 are real stable releases. Node 24 satisfies Vite 8's supported runtime range.
- **Starter reproducibility:** create-vite is pinned, the React + TypeScript template is identified, and both frontend and backend dependency graphs are governed by committed lockfiles and frozen installation.
- **SQLite safety:** one host, one application write owner, short request/job-scoped SQLAlchemy sessions, WAL verification, busy timeout, local/block-backed storage, and the network-filesystem prohibition form a coherent bounded topology. Multi-host expansion is explicitly gated on migration away from SQLite/filesystem storage.
- **Native runtime delivery:** the build-time SQLite check now ensures that Python's compiled/linked `sqlite3` runtime actually satisfies the declared stack version instead of assuming that the Python image provides it.
- **Detector compatibility:** the still-deferred local detector must install from the committed lock and pass an end-to-end CPU fixture on Python 3.13.15 before acceptance-criteria decomposition; otherwise the single Python pin must be revised. This prevents an implicit second runtime.

## Remaining lower-severity observations

None that require an architecture change. Concrete image digest, `uv` version, hosting provider, model/provider, and generated lockfile contents are correctly deferred to implementation/deployment artifacts with explicit revisit gates.

Primary official references used across the version review: [Python 3.13.15](https://www.python.org/downloads/release/python-31315/), [FastAPI releases](https://fastapi.tiangolo.com/release-notes/), [SQLAlchemy downloads](https://www.sqlalchemy.org/download.html), [SQLite release history](https://sqlite.org/changes.html), [SQLite WAL](https://www.sqlite.org/wal.html), [React 19.3](https://react.dev/blog/2026/09/09/react-19-3), [TypeScript releases](https://github.com/microsoft/TypeScript/releases), [Vite releases](https://github.com/vitejs/vite/releases), [Node.js release status](https://nodejs.org/en/about/previous-releases), and [uv Docker guidance](https://docs.astral.sh/uv/guides/integration/docker/).

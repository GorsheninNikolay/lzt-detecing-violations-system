# Technology and Version Review — Updated Spine

Reviewed artifact: `../ARCHITECTURE-SPINE.md`

Review date: 2026-09-21

## Verdict

**PASS WITH NON-BLOCKING NOTES.** Every concrete version in the updated spine is a real stable release, and the named stack is mutually plausible for the declared single-host MVP. No critical, high, or medium version defect was found. The two remaining notes are already bounded by explicit revisit gates: TypeScript 6 is a deliberate compatibility-line choice rather than the newest major, and detector/runtime delivery cannot be reality-checked until implementation exists.

## Verification matrix

| Spine item | Official-source result | Review conclusion |
| --- | --- | --- |
| Python 3.13.15 | Python.org identifies 3.13.15 as the fifteenth maintenance release of the 3.13 line, released 2026-08-05. Python 3.14 is the newer feature series. | Valid stable pin. Choosing 3.13 is not presented as choosing the newest feature series, and the spine explicitly gates detector compatibility on this pin. |
| FastAPI 0.141.1 | The official FastAPI release notes list 0.141.1, released 2026-07-29. | Valid stable pin. |
| SQLAlchemy 2.0.54 | The official download page labels 2.0.54 the current 2.0 release and 2.1.0rc2 a prerelease. | Valid stable pin and appropriate conservative line. |
| SQLite 3.53.4 | SQLite's official release history lists 3.53.4, released 2026-07-24. | Valid stable pin. |
| SQLite WAL minimum 3.51.3 | SQLite's WAL documentation says the WAL-reset corruption bug affects releases through 3.51.2 and is fixed in 3.51.3 and later. The same page confirms same-host/shared-memory requirements, no network filesystem, concurrent readers with only one writer, and possible `SQLITE_BUSY`. | AD-14's minimum runtime, one-host boundary, network-filesystem prohibition, and busy-timeout requirement are evidence-backed. |
| React 19.3 | React's official versions page calls 19.3 the latest version and lists v19.3.0, released 2026-09-09. | Valid current line. |
| TypeScript 6.0.3 | Microsoft's official releases list 6.0.3 as stable. TypeScript 7.0.2 is newer, but Microsoft's TypeScript 7 announcement says 7.0 has no compiler API and provides a TypeScript 6 compatibility package for tooling that still needs that API. | Valid compatibility pin, but not the newest major; see Note 1. |
| Vite 8.3.0 | Vite's official site displays v8.3.0, and the official releases page identifies 8.3 as the regularly patched line. | Valid current pin. |
| Node.js 24.21.0 LTS | Node's official release table marks v24 as LTS and the official archive identifies v24.21.0 (Krypton). | Valid LTS pin. It exceeds create-vite's declared Node requirement of `^20.19.0 || >=22.12.0`. |
| create-vite 9.2.1, React + TypeScript template | The official Vite release lists `create-vite@9.2.1`. Its tag's React/TypeScript template declares React `^19.2.8`, TypeScript `~6.0.2`, and Vite `^8.3.0`. | The chosen React 19.3, TypeScript 6.0.3, and Vite 8.3.0 all satisfy the official starter ranges. A committed package lock is still required to turn those ranges into the spine's exact resolved graph. |

## Findings and notes

### 1. Low — TypeScript 6.0.3 is compatibility-current, not latest-major current

**Evidence.** TypeScript 7.0.2 is the latest official release. However, TypeScript 7.0 ships without the compiler API, and Microsoft explicitly documents side-by-side TypeScript 6 for tools that require programmatic compiler access. The exact `create-vite@9.2.1` React + TypeScript template itself selects `typescript: ~6.0.2`, which resolves compatibly to 6.0.3.

**Impact.** No build inconsistency exists in the current spine. The risk is only that downstream prose could incorrectly call 6.0.3 the globally latest TypeScript rather than the stable line selected by the official starter.

**Disposition.** Keep 6.0.3 for convergence with the selected starter. Revisit TypeScript 7 when the chosen lint/build toolchain supports its API boundary or no longer needs the TypeScript 6 API. No spine edit is required unless the architecture wants to make that rationale explicit.

### 2. Low — Runtime fit remains prospective, not observed

**Evidence.** The repository contains no application `pyproject.toml`, `uv.lock`, frontend `package.json`, package lock, detector adapter, container image, or executable runtime to test. The spine already requires the detector to install from the committed lock and pass an end-to-end CPU fixture on Python 3.13.15, and requires deterministic SQLite 3.53.4 supply plus `sqlite3.sqlite_version_info` checks before the first deployable image.

**Impact.** Official release evidence proves that the named versions exist and that their declared boundaries are coherent; it does not prove that the eventual detector package, compiled Python SQLite binding, native wheels, or container base work together.

**Disposition.** Retain the existing Deferred gates. Treat detector installation, locked dependency resolution, and runtime SQLite checks as mandatory implementation evidence rather than as already verified architecture facts.

### 3. Informational — Deferred toolchain pins are correctly bounded

The spine names `uv` but does not assert a current version; it explicitly requires pinning the `uv` tool and container base by digest before the first deployable image. This is an acceptable deferred decision because the revisit condition precedes the first artifact whose reproducibility depends on those values. When implementation begins, use the selected official `uv` release and record it alongside the generated `uv.lock`; do not infer it from a developer workstation.

## Official primary sources

- [Python 3.13.15 release](https://www.python.org/downloads/release/python-31315/)
- [FastAPI release notes](https://fastapi.tiangolo.com/release-notes/)
- [SQLAlchemy downloads and release status](https://www.sqlalchemy.org/download.html)
- [SQLite release history](https://sqlite.org/changes.html)
- [SQLite WAL documentation](https://www.sqlite.org/wal.html)
- [React versions](https://react.dev/versions)
- [TypeScript official releases](https://github.com/microsoft/TypeScript/releases)
- [TypeScript 7.0 compatibility guidance](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)
- [Vite current version](https://vite.dev/)
- [Vite releases](https://github.com/vitejs/vite/releases)
- [create-vite 9.2.1 React/TypeScript template](https://github.com/vitejs/vite/blob/create-vite%409.2.1/packages/create-vite/template-react-ts/package.json)
- [Node.js release status](https://nodejs.org/en/about/previous-releases)
- [Node.js 24.21.0 archive](https://nodejs.org/en/download/archive/v24.21.0)


# Experiment profile and reproducibility digest

**Decision served:** define candidate admission, immutable execution-profile revisions, minimal installation/E2E smokes, and a fair later experiment for Construction Monitoring Rapid MVP. This digest does **not** select a technology winner.

**Research date / accessed:** 2026-09-22  
**Scope:** cross-cutting runtime, reproducibility, experiment design, and PostgreSQL-bound persistence assumptions.  
**Evidence boundary:** official/primary documentation only. Normative product decisions below come from the supplied brief; factual claims are listed in the claims table.

## Decision summary

Admit a candidate only after one immutable `ObserverExecutionProfileRevision` can be installed from a checked lock, can verify all referenced model/config artifacts by SHA-256, can connect to PostgreSQL (with no SQLite code path), and can complete a four-fixture contract smoke. Every local candidate must pass on an ordinary-laptop CPU profile; Apple Silicon CoreML and Windows RTX 3060 CUDA/DirectML are additional, separately revisioned modes rather than substitutes for CPU.

The later comparison uses one manually labelled, immutable 10–15-image set. It creates exactly one `AnalysisRun` for each `(experiment, candidate profile revision, fixture)` and stores repeated `ExecutionAttempt` children inside that run. The scoring contract has only four portable states: `check_required`, `no_check`, `insufficient_data`, and `out_of_scope`. Provider-native counts, confidences, and geometry may be retained as opaque evidence, but the evaluator must not use them for correctness or warning decisions.

Package locking, artifact identity, provider identity, and output stability are separate evidence layers. `uv sync --frozen` consumes the existing lock without checking whether it matches project metadata, while `uv lock --check` performs that check; therefore both are required in the clean-install smoke [S1]. A lock can be cross-platform while selected wheels remain OS/architecture-specific, so every target mode still needs a native install and E2E smoke [S1][S2]. ML frameworks also warn that results can differ across releases, platforms, and CPU/GPU even with identical seeds, which is why repeats and exact runtime fingerprints are mandatory [S6].

## Exact `ObserverExecutionProfileRevision` definition

### PostgreSQL enum domains

```sql
CREATE TYPE observer_execution_kind AS ENUM ('local_process', 'local_container', 'cloud_api');
CREATE TYPE observer_accelerator AS ENUM ('cpu', 'coreml', 'cuda', 'directml', 'provider_managed');
CREATE TYPE observer_profile_status AS ENUM ('draft', 'admitted', 'rejected', 'retired');
CREATE TYPE portable_observation_state AS ENUM (
  'check_required', 'no_check', 'insufficient_data', 'out_of_scope'
);
CREATE TYPE determinism_level AS ENUM ('enforced', 'best_effort', 'not_available');
```

### Table

`observer_execution_profile_revision` is insert-only once `status` leaves `draft`. Any change to a field below creates a new revision and a new `profile_sha256`; an `AnalysisRun` always references the revision UUID, never a mutable candidate row.

| Field | PostgreSQL type | Null | Exact meaning / constraint |
|---|---|---:|---|
| `id` | `uuid` | no | Primary key, application-generated UUIDv7 (UUIDv4 is acceptable if UUIDv7 support is unavailable). |
| `candidate_key` | `text` | no | Stable internal slug, regex `^[a-z0-9][a-z0-9._-]{1,63}$`. |
| `revision` | `integer` | no | Monotonic per candidate, `> 0`; unique with `candidate_key`. |
| `status` | `observer_profile_status` | no | Lifecycle status; default `draft`. Only `admitted` revisions may enter a scored experiment. |
| `display_name` | `text` | no | Human-readable candidate and mode name; not used as an identity. |
| `execution_kind` | `observer_execution_kind` | no | Local process, local container, or remote provider invocation. |
| `accelerator` | `observer_accelerator` | no | The requested execution mode. Local candidates require a separate admitted `cpu` revision. |
| `adapter_protocol_revision` | `text` | no | Exact internal adapter contract revision, e.g. `observer-adapter/v1`. |
| `adapter_entrypoint` | `text` | no | Import path or executable route invoked by the harness. |
| `source_revision` | `text` | no | Immutable source commit/revision for adapter and normalization code. |
| `source_tree_sha256` | `char(64)` | no | SHA-256 of the canonical source bundle used when a commit alone is insufficient (dirty trees forbidden). |
| `python_implementation` | `text` | conditional | Exact implementation, normally `CPython`; required for Python runtimes. |
| `python_version` | `text` | conditional | Full runtime version including patch, not only `3.x`; required for Python runtimes. |
| `uv_version` | `text` | conditional | Exact installer/locker version; required for Python runtimes. |
| `pyproject_sha256` | `char(64)` | conditional | SHA-256 of `pyproject.toml`; required for Python runtimes. |
| `uv_lock_sha256` | `char(64)` | conditional | SHA-256 of the committed `uv.lock`; required for Python runtimes. |
| `package_snapshot_sha256` | `char(64)` | conditional | SHA-256 of sorted, normalized installed distributions (`name==version` plus direct-source commit/digest); captured after sync. |
| `os_name` | `text` | conditional | Exact OS family reported by the host; required for local modes. |
| `os_version` | `text` | conditional | Exact OS build/release; required for local modes. |
| `architecture` | `text` | conditional | Exact machine architecture such as `x86_64` or `arm64`; required for local modes. |
| `cpu_model` | `text` | conditional | Host-reported CPU model; required for measured local runs. |
| `logical_cpu_count` | `smallint` | conditional | Available logical CPUs, `> 0`; required for measured local runs. |
| `memory_bytes` | `bigint` | conditional | Available physical memory, `> 0`; required for measured local runs. |
| `accelerator_name` | `text` | conditional | Device name; null only for plain CPU or provider-managed execution. |
| `accelerator_driver_version` | `text` | conditional | Driver version for CUDA/DirectML where the platform reports one. |
| `accelerator_runtime_version` | `text` | conditional | CUDA/cuDNN/CoreML/DirectML/runtime version string as actually reported, not inferred. |
| `runtime_backend_name` | `text` | no | Library/backend actually used, e.g. `onnxruntime`; candidate-neutral free text. |
| `runtime_backend_version` | `text` | no | Exact installed runtime version. |
| `requested_provider_order` | `jsonb` | no | JSON string array in priority order; `[]` when not applicable. |
| `available_providers` | `jsonb` | no | Sorted JSON string array observed at admission. Never infer availability from package name alone. |
| `effective_providers` | `jsonb` | no | Ordered JSON string array observed from the created session/client. CPU fallback is therefore visible. |
| `container_image_ref` | `text` | conditional | Human-readable image reference; required for `local_container`. |
| `container_image_digest` | `text` | conditional | Immutable OCI digest (`sha256:...`); required for `local_container`; mutable tags alone are rejected. |
| `artifacts` | `jsonb` | no | Array of metadata objects defined below. Binary content is never stored in PostgreSQL. At least one `model` or `remote_model_descriptor` entry. |
| `preprocess_revision` | `text` | no | Immutable preprocessing implementation/config revision. |
| `preprocess_config_sha256` | `char(64)` | no | SHA-256 of canonical preprocessing config. |
| `postprocess_revision` | `text` | no | Immutable mapping from native output to the portable result. |
| `postprocess_config_sha256` | `char(64)` | no | SHA-256 of canonical postprocessing config. |
| `taxonomy_revision` | `text` | no | Exact class vocabulary revision used for class-level scoring. |
| `prompt_template_sha256` | `char(64)` | yes | Required when a prompt/system instruction influences output; otherwise null. |
| `requested_model_id` | `text` | conditional | Exact local model name or cloud request model/deployment ID. Required for cloud; descriptive only unless paired with artifact hash or returned identity. |
| `cloud_endpoint` | `text` | conditional | Provider endpoint/region alias with secrets and query credentials removed; required for cloud. |
| `cloud_api_version` | `text` | conditional | Explicit API version when the provider offers one; otherwise null with reason in `admission_notes`. |
| `cloud_request_parameters` | `jsonb` | conditional | Canonical allowlisted non-secret inference parameters; required for cloud, `{}` allowed. |
| `random_seed` | `bigint` | yes | Seed supplied to candidate/runtime when supported; null only with explicit `determinism_level='not_available'`. |
| `determinism_level` | `determinism_level` | no | Whether deterministic algorithms are enforced, best effort, or unavailable. |
| `determinism_settings` | `jsonb` | no | Canonical allowlist of actual flags/thread settings; `{}` allowed, secrets forbidden. |
| `max_parallelism` | `smallint` | no | Experiment concurrency for this profile; initial fair experiment requires `1`. |
| `connect_timeout_ms` | `integer` | no | Positive cloud/connect deadline. |
| `attempt_timeout_ms` | `integer` | no | Positive end-to-end attempt deadline, including preprocessing/network/postprocessing. |
| `experiment_max_attempts` | `smallint` | no | Must equal `1`; failures/timeouts are results, not retried away. Live-demo retry is governed separately. |
| `output_contract_revision` | `text` | no | Must identify the four-state schema revision. |
| `portable_states` | `jsonb` | no | Must equal the canonical sorted array of the four enum values; guards adapter drift. |
| `database_dialect` | `text` | no | Must equal `postgresql`; application validation rejects `sqlite`, `sqlite3`, and missing dialects. |
| `database_driver` | `text` | no | Exact driver/dialect, e.g. `postgresql+psycopg`; SQLAlchemy is permitted but not required. |
| `database_server_version` | `text` | no | Version observed during admission DB smoke. Do not encode an unsupported minimum here until implementation chooses one. |
| `database_schema_revision` | `text` | no | Migration head used by admission and later runs. |
| `admission_smoke_report_uri` | `text` | conditional | URI to external report artifact; required when admitted/rejected. |
| `admission_smoke_report_sha256` | `char(64)` | conditional | Digest of that report; required when admitted/rejected. |
| `admission_notes` | `text` | no | Short deviations/limitations; default empty string. Never contains credentials. |
| `profile_sha256` | `char(64)` | no | SHA-256 of canonical JSON serialization of all semantic fields above except lifecycle/audit fields (`id`, `status`, report fields, timestamps, creator). |
| `created_at` | `timestamptz` | no | Server-side creation time. |
| `created_by` | `text` | no | Principal/tool identity. |
| `decided_at` | `timestamptz` | yes | Admission/rejection time. |
| `decided_by` | `text` | yes | Principal/process that applied the gate. |

`artifacts` has this exact JSON shape and is schema-validated before insert:

```json
[
  {
    "role": "model|weights|tokenizer|label_map|runtime_config|remote_model_descriptor",
    "uri": "object-store-or-local-relative-uri",
    "sha256": "64 lowercase hex characters",
    "size_bytes": 123,
    "media_type": "application/octet-stream",
    "source_revision": "publisher revision, model commit, or immutable version",
    "license_id": "SPDX identifier or reviewed proprietary marker"
  }
]
```

`size_bytes >= 0`; `uri` must be immutable or content-addressed; local artifacts are re-hashed before every admitted run. SHA-256 is available through Python's standard `hashlib`, including file hashing [S7]. Images, weights, raw provider responses, rendered overlays, logs, and smoke reports live in object/file storage; PostgreSQL stores only structured metadata, URIs, lengths, hashes, outcomes, and measurements. No vector column, vector extension, or `pgvector` dependency is admitted.

### Required per-attempt runtime identity (not profile fields)

Cloud identity is response evidence and therefore belongs on `execution_attempt`, not in the immutable requested profile:

| Field | Type | Rule |
|---|---|---|
| `provider_request_id` | `text null` | Provider/HTTP request ID if returned; null plus `identity_gap` otherwise. |
| `provider_response_id` | `text null` | Response object ID if returned. |
| `provider_returned_model` | `text null` | Returned model resource/name if present. |
| `provider_returned_model_version` | `text null` | Returned version/snapshot if present. |
| `provider_deployment_id` | `text null` | Deployment/variant ID if present. |
| `provider_identity_raw` | `jsonb` | Allowlisted identity headers/fields only; no payload, secrets, or personal data. |
| `identity_gap` | `text null` | Mandatory explanation when the provider returns no immutable model/version or request ID. |

This is deliberately provider-neutral: Vertex `PredictResponse`, for example, exposes deployed-model, model resource, and model-version fields [S8], while SageMaker exposes the invoked production variant and optional custom attributes rather than the same identity tuple [S9]. A missing provider field is preserved as a comparability gap, never manufactured from the requested model string.

## Candidate admission gates

All gates are pass/fail and precede comparative scoring.

1. **Identity and immutability:** clean source revision; checked `uv.lock`; exact Python/installer/runtime versions; profile digest; every local artifact digest verified; immutable container digest where applicable.
2. **Legal and access:** license/terms recorded for every artifact/API; credentials supplied only through the runtime secret mechanism; no credential appears in profile, logs, commands, or artifacts.
3. **PostgreSQL-only state:** connection URL parses to `postgresql`/`postgresql+<driver>`; migration head matches; transactional create/read/update smoke succeeds. The process must fail closed if PostgreSQL is absent. No SQLite package, URL, file, fallback branch, test runtime, or second implementation is allowed. SQLAlchemy's PostgreSQL dialect supports explicit `postgresql+psycopg://...` URLs [S10].
4. **Portable contract:** adapter schema-validates exactly one portable state and a set of normalized class IDs. Native count, confidence, bounding boxes, masks, polygons, and provider prose may be stored as opaque artifacts but are forbidden inputs to the experiment scorer and warning rule.
5. **Mandatory fixture smoke:** one fixture for each state—check request, no check, insufficient data, out of scope—persists an `AnalysisRun` and successful attempt with correct state. The smoke validates plumbing, not candidate quality; use controlled adapter fixtures/stubs when a real model cannot be expected to get all four right.
6. **Failure semantics:** injected timeout, adapter exception, invalid native response, and unavailable artifact/provider each end in a persisted terminal attempt state; none becomes `no_check`; no automatic experiment retry.
7. **Local CPU:** every local candidate has a separately admitted ordinary-laptop `cpu` revision and completes the 10–15-image E2E set within the declared per-attempt timeout and memory envelope. Accelerator-only local candidates are rejected.
8. **Additional modes:** Apple Silicon CoreML and Windows RTX 3060 CUDA/DirectML are separate profile revisions, installed and smoked on the named native host. Provider availability and effective provider order are read back at runtime. ONNX Runtime, if a candidate uses it, orders execution providers by priority and exposes registered/provider options [S4]; official macOS wheels can expose CoreML, but runtime enumeration remains the admission proof [S5].
9. **Cloud observability and spend:** endpoint/region/API version/request parameters recorded; returned request/model/version/deployment identifiers captured when available; usage and money fields persisted; a hard request count and budget ceiling configured before E2E.
10. **Repeatability readiness:** repeated executions can be grouped under one `AnalysisRun`; seed/determinism settings and effective backend are recorded; output and class-set disagreement can be computed. Determinism claims are scoped to one exact profile and host, never generalized across CPU/GPU or releases [S6].

## Instantiable command templates

Placeholders are environment variables so the templates remain valid once candidates are named. Commands write reports outside PostgreSQL, then persist only report metadata/hash through the application.

### POSIX clean install and profile admission

```bash
set -euo pipefail

export CANDIDATE_SLUG='replace-me'
export PROFILE_FILE="profiles/${CANDIDATE_SLUG}.json"
export PYTHON_VERSION='replace-exact-x.y.z'
export RUNTIME_EXTRA="runtime-${CANDIDATE_SLUG}-cpu"
export OBSERVER_MODULE='construction_monitoring.observer_cli'
export DATABASE_URL='postgresql+psycopg://user:password@127.0.0.1:5432/construction_monitoring'

uv --version
uv python install "${PYTHON_VERSION}"
uv lock --check
uv sync --frozen --no-editable --python "${PYTHON_VERSION}" --extra "${RUNTIME_EXTRA}"

uv run --frozen python -m "${OBSERVER_MODULE}" profile validate \
  --profile "${PROFILE_FILE}" \
  --require-database-dialect postgresql \
  --require-artifact-hashes \
  --require-clean-source

uv run --frozen python -m "${OBSERVER_MODULE}" db smoke \
  --database-url-env DATABASE_URL \
  --require-migration-head

uv run --frozen python -m "${OBSERVER_MODULE}" runtime probe \
  --profile "${PROFILE_FILE}" \
  --write-report "artifacts/admission/${CANDIDATE_SLUG}-runtime.json"

uv run --frozen python -m "${OBSERVER_MODULE}" smoke contract \
  --profile "${PROFILE_FILE}" \
  --manifest evaluation/manifests/contract-smoke-v1.json \
  --expected-states check_required,no_check,insufficient_data,out_of_scope \
  --write-report "artifacts/admission/${CANDIDATE_SLUG}-contract.json"
```

Use `uv lock --check` before `uv sync --frozen`: official uv documentation distinguishes “check lock is current” from “use lock without checking” [S1]. Exact sync is uv's default; `--no-editable` removes dependence on a mutable source checkout [S1]. A pip-based fallback is not the default workflow, but if a candidate cannot be represented in `uv.lock`, admission requires a separately reviewed, fully pinned requirements file with `--require-hashes`; pip documents both pinning and hash checking as repeatability controls [S2].

### Cross-platform artifact digest

```bash
export ARTIFACT_PATH='models/replace-me.onnx'
uv run --frozen python -c 'import hashlib,os,pathlib; p=pathlib.Path(os.environ["ARTIFACT_PATH"]); print(hashlib.file_digest(p.open("rb"), "sha256").hexdigest())'
```

Compare the printed value to `artifacts[].sha256`; mismatch is a hard failure, not a warning.

### Windows PowerShell: RTX 3060 CUDA or DirectML profile

```powershell
$ErrorActionPreference = 'Stop'
$env:CANDIDATE_SLUG = 'replace-me'
$env:PROFILE_FILE = "profiles/$($env:CANDIDATE_SLUG)-windows-rtx3060.json"
$env:PYTHON_VERSION = 'replace-exact-x.y.z'
$env:RUNTIME_EXTRA = "runtime-$($env:CANDIDATE_SLUG)-cuda" # or -directml
$env:OBSERVER_MODULE = 'construction_monitoring.observer_cli'
$env:DATABASE_URL = 'postgresql+psycopg://user:password@127.0.0.1:5432/construction_monitoring'

uv --version
uv python install $env:PYTHON_VERSION
uv lock --check
uv sync --frozen --no-editable --python $env:PYTHON_VERSION --extra $env:RUNTIME_EXTRA
uv run --frozen python -m $env:OBSERVER_MODULE runtime probe --profile $env:PROFILE_FILE --require-device-name 'NVIDIA GeForce RTX 3060'
uv run --frozen python -m $env:OBSERVER_MODULE smoke contract --profile $env:PROFILE_FILE --manifest evaluation/manifests/contract-smoke-v1.json
```

Do not preselect CUDA over DirectML. If ONNX Runtime is used, its official install matrix distinguishes CPU, CUDA, and DirectML packages and currently describes DirectML as sustained engineering; the candidate-specific compatibility decision must be revalidated from the then-current matrix and on the actual host [S3].

### Apple Silicon additional mode

```bash
export PROFILE_FILE="profiles/${CANDIDATE_SLUG}-macos-arm64-coreml.json"
export RUNTIME_EXTRA="runtime-${CANDIDATE_SLUG}-coreml"

test "$(uname -s)" = 'Darwin'
test "$(uname -m)" = 'arm64'
uv lock --check
uv sync --frozen --no-editable --python "${PYTHON_VERSION}" --extra "${RUNTIME_EXTRA}"
uv run --frozen python -m "${OBSERVER_MODULE}" runtime probe \
  --profile "${PROFILE_FILE}" \
  --require-available-provider CoreMLExecutionProvider \
  --require-effective-provider CoreMLExecutionProvider
uv run --frozen python -m "${OBSERVER_MODULE}" smoke contract \
  --profile "${PROFILE_FILE}" \
  --manifest evaluation/manifests/contract-smoke-v1.json
```

### Fair experiment execution

```bash
export EXPERIMENT_MANIFEST='evaluation/manifests/rapid-mvp-manual-v1.json'
export REPETITIONS='3'

uv run --frozen python -m "${OBSERVER_MODULE}" experiment validate-manifest \
  --manifest "${EXPERIMENT_MANIFEST}" \
  --require-images-between 10 15 \
  --require-manual-labels \
  --require-four-states

uv run --frozen python -m "${OBSERVER_MODULE}" experiment run \
  --manifest "${EXPERIMENT_MANIFEST}" \
  --admitted-profiles-file evaluation/admitted-profiles.json \
  --repetitions "${REPETITIONS}" \
  --max-parallelism 1 \
  --no-retry \
  --persist-each-attempt

uv run --frozen python -m "${OBSERVER_MODULE}" experiment report \
  --manifest "${EXPERIMENT_MANIFEST}" \
  --fail-on-any-false-warning \
  --include-errors-and-timeouts-in-denominators \
  --write-report artifacts/evaluation/rapid-mvp-manual-v1.json
```

The module and subcommands above are interface templates, not claims that those modules already exist.

## Evaluation manifest and matrix

### Immutable manifest

One person (or an adjudicated pair) manually labels one set of 10–15 images before candidates run. Freeze the manifest and image bytes; do not tune labels, prompts, mappings, or thresholds after seeing candidate outputs. Any correction creates a new manifest revision and invalidates direct comparison with earlier results.

```json
{
  "experiment_id": "rapid-mvp-manual-v1",
  "manifest_revision": 1,
  "created_at": "RFC3339 timestamp",
  "label_policy_revision": "construction-monitoring-label-policy/v1",
  "taxonomy_revision": "construction-monitoring-classes/v1",
  "portable_contract_revision": "observer-result/v1",
  "image_count": 12,
  "repetitions": 3,
  "attempt_timeout_ms": 60000,
  "max_parallelism": 1,
  "retry_policy": "none",
  "fixtures": [
    {
      "fixture_id": "fx-001",
      "image_uri": "object://evaluation/sha256/<digest>",
      "image_sha256": "64 lowercase hex",
      "image_bytes": 123456,
      "mime_type": "image/jpeg",
      "expected_state": "check_required",
      "expected_classes": ["class-id"],
      "labeler_id": "pseudonymous-id",
      "label_notes": "brief adjudication note",
      "is_mandatory_state_fixture": true
    }
  ]
}
```

Required coverage:

- at least one `check_required` fixture;
- at least one `no_check` fixture;
- at least one `insufficient_data` fixture;
- at least one `out_of_scope` fixture;
- at least two distinct positive classes across `check_required` fixtures if the MVP taxonomy contains at least two classes;
- at least one negative image likely to tempt a false detection;
- identical bytes, context, timeout, retry policy, and portable mapping revision for all candidates.

### Persistence matrix

For each admitted profile revision and fixture, create exactly one `analysis_run`:

```text
UNIQUE (experiment_id, observer_execution_profile_revision_id, fixture_id)
```

Each `analysis_run` has exactly `R=3` `execution_attempt` rows with `repeat_index IN (1,2,3)` and:

```text
UNIQUE (analysis_run_id, repeat_index)
```

An attempt terminal status is one of `succeeded`, `error`, or `timeout`. A successful attempt stores the portable state and normalized class set. Error/timeout attempts store neither a fabricated state nor a fabricated empty class set. Raw images and large/native outputs stay outside PostgreSQL and are referenced by URI and SHA-256.

Suggested execution order is a deterministic seeded shuffle of the complete `(profile revision, fixture, repeat)` matrix, with at most one active attempt. Persist the generated order before execution. This distributes temporal drift without giving a candidate a concurrency advantage. Cold-start and warm-start measurements must be separate experiments or explicit phases; do not mix them in one latency statistic.

## Measurement definitions

All primary metrics are computed over the fixed attempts denominator:

```text
N_attempts = candidates * fixtures * repetitions
```

Errors and timeouts remain in `N_attempts`.

| Measure | Exact definition |
|---|---|
| `state_correct` | `1` only when attempt succeeded and predicted portable state equals expected state; else `0`, including error/timeout. |
| `state_accuracy` | `sum(state_correct) / N_attempts`. Report overall and by expected state. |
| `check_request_recall` | Correct `check_required` attempts divided by all attempts whose fixture expects `check_required`; error/timeout is a miss. |
| `false_warning` | `1` only when attempt succeeds with `predicted_state='check_required'` while expected state is any of the other three; error/timeout is not silently treated as a warning. |
| `false_warning_rate` | `sum(false_warning)` divided by all attempts whose expected state is not `check_required`. |
| **zero-false-warnings gate** | Pass only if `sum(false_warning)=0` across every fixture and repeat. Report the numerator and denominator; do not round a small nonzero rate to zero. |
| `class_miss_count` | For a successful attempt, `|expected_classes - predicted_classes|`; for error/timeout, `|expected_classes|`. Report per class as missed expected presences / all expected presences. |
| `false_detection_count` | For a successful attempt, `|predicted_classes - expected_classes|`; for error/timeout, `0` plus separate failure accounting. Report per class as false presences / attempts where class is absent. |
| `exact_class_set_match` | `1` only for success with identical normalized class sets; else `0`. |
| `error_rate` | Attempts ending `error / N_attempts`, broken down by stable error code. |
| `timeout_rate` | Attempts ending `timeout / N_attempts`. |
| `latency_ms` | Monotonic wall-clock from immediately before adapter preprocessing/request work through response validation and postprocessing. Store every attempt. Report success-only median/p95/max and separately timeout/error elapsed times; p95 uses the nearest-rank definition. |
| `cold_start_ms` | Separate profiled phase: process/session/client construction through first terminal result. Never mix with warm latency. |
| `cost_actual` | Provider-reported billed usage converted using a snapshotted price table, or direct billed amount if exposed. Store currency, quantity/unit, price-table revision, and `actual|estimated`. |
| `cost_per_attempt_all` | Total actual/estimated experiment cost divided by `N_attempts`, including failures/timeouts. Local runs report measured wall time and energy only if actually instrumented; do not invent a currency cost. |
| `state_disagreement_rate` | Per run: `1 - max_count(portable_state_or_failure_token)/R`; aggregate mean across runs. `ERROR:<code>` and `TIMEOUT` are distinct tokens, so instability is visible. |
| `class_set_disagreement_rate` | Fraction of unordered repeat pairs whose normalized class sets differ exactly; any pair involving error/timeout counts as disagreement unless both have the same failure token. |
| `fully_reproduced_run_rate` | Fraction of `AnalysisRun`s whose R attempts have identical terminal token, portable state, and normalized class set. |
| `identity_complete_rate` | Cloud attempts with all provider identity fields that the provider contract exposes divided by cloud attempts; gaps listed, not imputed. |

Provider-native object count, confidence, score, box, polygon, mask, and geometry are excluded from all formulas above. They may only support later qualitative debugging. The warning rule is exactly `portable_state == 'check_required'`; it cannot inspect native provider fields.

Do not collapse the matrix into a single winner score. Present the zero-false-warning gate first, then state/class failures, repeated-run stability, latency, cost, and operational gaps as separate axes. With only 10–15 images, every numerator/denominator and every failed fixture should be shown; decimals alone imply more precision than the set supports.

## Repeated-run design

- Use `R=3` repetitions in the first comparison; it is the smallest design that can expose a majority outcome while keeping the small manual set affordable. This is a design choice, not a statistical guarantee.
- Keep one immutable profile revision, one manifest revision, one host allocation, one concurrency level, and one timeout across repeats.
- Restart the candidate process/session between repeats for the reproducibility pass. If warm-session stability is also important, run it as a separately named phase and never combine the two.
- Reset only ephemeral runtime caches in the restart phase. Do not delete shared downloaded artifacts between every image; instead record cache state and run a separate cold-install/cold-start smoke.
- Seed Python/NumPy/framework RNGs where supported and enable deterministic algorithms where the runtime offers them. Still measure disagreement: PyTorch explicitly states that complete reproducibility is not guaranteed across releases/platforms and can differ between CPU and GPU [S6].
- Keep CPU, CoreML, CUDA, DirectML, and cloud as distinct profiles. Agreement between two modes is a measured result, not presumed portability.
- Never retry experiment attempts. A transport retry would change cost, latency, and reliability semantics. If the cloud SDK retries internally, set it to zero or record the exact effective policy and disqualify the profile from the first fair matrix until aligned.

## Minimal installation and E2E smokes

1. **Clean-install smoke:** new environment; exact Python; `uv lock --check`; `uv sync --frozen --no-editable`; capture versions and installed snapshot; verify no undeclared distribution. The lock/install split is grounded in uv's documented behavior [S1].
2. **Artifact smoke:** download/open every declared artifact; verify byte length and SHA-256; fail on mismatch; ensure no artifact bytes are written to PostgreSQL [S7].
3. **Runtime probe:** instantiate client/session; record requested, available, and effective providers; record device and backend versions; execute one syntactically valid minimal inference.
4. **PostgreSQL smoke:** reject every non-PostgreSQL URL; connect; assert server/schema revision; insert profile/report metadata and one run/attempt in a transaction; read it back; roll back or delete through normal application cleanup. SQLAlchemy may use an explicit PostgreSQL dialect URL [S10].
5. **Four-state contract smoke:** run the four controlled mandatory fixtures, validate state enum/class IDs/schema, and persist one run per fixture.
6. **Failure smoke:** force timeout, malformed response, missing artifact, and provider error; verify terminal persistence, denominator inclusion, redacted logs, and absence of fallback output.
7. **Full-set CPU E2E:** for every local candidate, run all 10–15 images once on the declared ordinary laptop under the production adapter and deadline. Admission proves operability, not quality; later repeats produce comparison evidence.
8. **Additional-native E2E:** repeat install/runtime/four-state/full-set smokes on Apple Silicon CoreML and Windows RTX 3060 CUDA/DirectML only for modes the candidate claims to support. ONNX Runtime's common API can select ordered execution providers, but target-native probing is still required [S4].
9. **Cloud E2E:** hard request/budget caps; capture request and returned model/deployment/version identity fields; persist usage/cost basis; verify timeout and no SDK retries.

## Live-demo failure controls

- Freeze and display the exact profile revision and manifest revision before the demo; verify hashes at startup.
- Run a preflight 15–30 minutes before the demo: PostgreSQL migration/read-write, artifact hashes, runtime/provider probe, one non-scored canary, cloud quota/budget and credential presence. Never print credentials.
- Pre-cache local model artifacts and record their hashes. Cloud candidates require a provider health/canary result and a hard budget cap.
- Use per-attempt deadlines and a global demo deadline. The live UI must surface `error` and `timeout` as such; neither maps to `no_check` or `insufficient_data`.
- Permit at most one explicitly labelled **demo retry** for presentation continuity. Store both attempts, exclude the retried sequence from the fair experiment, and show that a retry occurred.
- Prepare a last-known-good recorded run for the same immutable profile/fixture. It may be shown only with an unmistakable “recorded result, timestamp, profile revision” label; never silently replace a failed live call.
- Keep a second independent viewing path for stored structured output (not a second inference runtime): if rendering fails, show the persisted PostgreSQL result plus artifact references.
- Disable automatic model/provider fallback. CPU fallback during an accelerator demo is allowed only if it is a separate declared profile; otherwise fail the runtime probe.
- Capture the full terminal record before rendering so a UI crash cannot erase the experimental evidence.

## Claims table

| ID | Claim used | Source URL | Publisher | Pub date | Accessed | Confidence | Class |
|---|---|---|---|---|---|---|---|
| S1 | uv separates lock checking (`uv lock --check`/`--locked`) from frozen use; sync is exact by default; lock resolution is designed to be portable across platforms. | https://docs.astral.sh/uv/concepts/projects/sync/ and https://docs.astral.sh/uv/concepts/resolution/ | Astral | not stated; live docs | 2026-09-22 | high for command semantics; medium for current-version compatibility until candidate pin | tooling behavior; version/compatibility |
| S2 | Fully pinned dependencies and hash checking improve repeatability; wheelhouses can be OS/architecture-specific. | https://pip.pypa.io/en/latest/topics/repeatable-installs/ | Python Packaging Authority | not stated; live docs | 2026-09-22 | high | packaging/reproducibility |
| S3 | ONNX Runtime publishes distinct CPU, CUDA, and DirectML install variants and directs users to a target compatibility matrix; DirectML is described as sustained engineering. | https://onnxruntime.ai/docs/install/ | Microsoft / ONNX Runtime project | not stated; live docs | 2026-09-22 | medium; revalidate exact candidate pins on native host | version/compatibility |
| S4 | ONNX Runtime execution providers abstract hardware backends; provider lists are ordered by priority and can be queried/set through the runtime API. | https://onnxruntime.ai/docs/execution-providers/ | Microsoft / ONNX Runtime project | not stated; live docs | 2026-09-22 | high | runtime behavior |
| S5 | Official macOS ONNX Runtime Python wheels include the CoreML EP, and runtime provider enumeration is the documented availability check. | https://onnxruntime.ai/docs/execution-providers/CoreML-ExecutionProvider.html | Microsoft / ONNX Runtime project | not stated; live docs | 2026-09-22 | medium; native smoke required and no cross-publisher version confirmation found | version/compatibility |
| S6 | Complete reproducibility is not guaranteed across PyTorch releases, commits, platforms, or CPU/GPU; seeds and deterministic-algorithm settings reduce some nondeterminism, often with performance trade-offs. | https://docs.pytorch.org/docs/2.14/notes/randomness.html | PyTorch Foundation | 2026-05-14 | 2026-09-22 | high for framework behavior; profile-specific results still require measurement | reproducibility |
| S7 | Python's standard `hashlib` provides SHA-256 and file-digest APIs suitable for computing artifact digests. | https://docs.python.org/3/library/hashlib.html | Python Software Foundation | documentation version 3.14.7; page date not stated | 2026-09-22 | high | artifact integrity |
| S8 | Vertex AI `PredictResponse` exposes deployed model ID, model resource, and model version ID. | https://cloud.google.com/nodejs/docs/reference/aiplatform/latest/aiplatform/protos.google.cloud.aiplatform.v1.predictresponse | Google Cloud | 2025 (page says 11 months before access) | 2026-09-22 | high for named response fields | cloud observability |
| S9 | SageMaker `InvokeEndpoint` exposes the invoked production variant and optional response custom attributes; its identity surface differs from Vertex. | https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html | Amazon Web Services | not stated; live docs | 2026-09-22 | high | cloud observability |
| S10 | SQLAlchemy supports PostgreSQL-specific dialect URLs, including `postgresql+psycopg://...`, for sync and async engines. | https://docs.sqlalchemy.org/en/20/dialects/postgresql.html | SQLAlchemy project | release 2.0.54, 2026-09-15 | 2026-09-22 | high for cited release; pin and retest the chosen release | version/compatibility |

## Assumptions and gaps

- **Ordinary laptop is not yet quantified.** Before admission, freeze a reference CPU class, core count, RAM ceiling, OS, and timeout. Until then, “ordinary-laptop CPU pass” is implementable but not comparable.
- **MVP class taxonomy and rule are not supplied.** This digest fixes portable states and class-set scoring, but candidate adapters cannot be finalized until the canonical class IDs and the deterministic mapping to `check_required` are versioned.
- **The four states are inferred directly from the binding fixtures.** If the product names differ, change the enum only by creating a new contract revision; do not add provider-specific states.
- **No candidate/runtime versions are selected.** All compatibility statements must be refreshed against each candidate's pinned official matrix and proven on the actual CPU/Apple/Windows host. The source pass found no independent primary publisher that can validate every ONNX Runtime/CoreML version tuple, so those claims remain medium confidence and are guarded by native smokes.
- **Cloud identity is provider-dependent.** Some providers return model/version/deployment identifiers; others expose only part of that tuple. Missing response identity is an explicit experimental limitation, not grounds to infer identity from the request.
- **Cost normalization needs candidate pricing inputs.** Freeze price-table snapshots and currency conversion time only after cloud candidates and billing units are known.
- **A 10–15-image set is a rapid-MVP diagnostic, not population-level validation.** Report exact counts and fixtures; do not attach unsupported confidence intervals or generalize to site-wide accuracy.
- **No claim is made that ONNX Runtime is required.** Its CPU/CUDA/DirectML/CoreML surfaces are examples of one candidate-neutral execution-profile pattern. Native framework or cloud candidates use equivalent requested/effective-backend and artifact/response-identity fields.
- **No performance winner can be inferred from documentation.** Latency, memory, cost, failures, class errors, false warnings, and repeat disagreement are measured only in the later frozen experiment.

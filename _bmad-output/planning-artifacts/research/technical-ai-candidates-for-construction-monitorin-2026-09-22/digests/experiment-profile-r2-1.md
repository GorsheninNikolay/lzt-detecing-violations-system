# Corrected experiment profile and reproducibility digest

**Decision served:** candidate admission and a fair, reproducible later experiment for Construction Monitoring Rapid MVP. No technology winner is selected.  
**Date / accessed:** 2026-09-22.  
**Correction status:** supersedes the semantic model and repeat layout in `experiment-profile-r1-1.md`.

## Corrected contract

The portable contract has two separate levels. They must not share one enum.

### Per-class observation state

For every class in the frozen taxonomy mapping, the state is exactly one of:

```text
detected
not_detected_in_frame
insufficient_data
not_analyzed
```

`detected` is boolean presence at the portable class level. The portable evaluator ignores provider-native object count, confidence, geometry, masks, and prose. Those values may be retained as opaque diagnostic artifacts, but they cannot alter correctness, warning, miss, or false-detection scoring.

### Top-level analysis outcome

The top-level outcome is separately exactly one of:

```text
observations_only
not_analyzed
insufficient_data
check_requested
no_check
```

The normalized class observations and explicitly versioned business rule produce the top-level outcome. Native confidence/count/geometry are forbidden rule inputs. `observations_only` means observations were returned without a check/no-check decision; it is not a class state.

Mandatory fixture categories are business scenarios, not enum members:

| Fixture category | Required expected top-level outcome | Required class-label property |
|---|---|---|
| `check_request` | `check_requested` | Manually labelled expected class states. |
| `no_check` | `no_check` | Manually labelled expected class states. |
| `insufficient_data` | `insufficient_data` | Relevant classes normally labelled `insufficient_data`; exceptions must be explicit. |
| `out_of_scope` | `not_analyzed` | All out-of-scope classes labelled `not_analyzed`. |

An additional `observations_only` fixture is recommended if that outcome is reachable in MVP, but it does not replace any mandatory fixture.

## AD-30 `ObserverExecutionProfileRevision`

This object describes how an observer candidate executes and where hybrid boundaries lie. It does not contain database-driver or persistence configuration. It becomes immutable when admitted; any semantic change creates a new revision and digest.

| Field | Type | Null | Definition |
|---|---|---:|---|
| `id` | UUID | no | Revision identity. |
| `candidate_key` | string | no | Stable candidate slug. |
| `revision` | positive integer | no | Monotonic within `candidate_key`; unique pair. |
| `status` | `draft \| admitted \| rejected \| retired` | no | Lifecycle; only admitted revisions enter planned batches. |
| `execution_kind` | `local_process \| local_container \| cloud_api \| hybrid` | no | Overall execution shape. |
| `adapter_code_ref` | string | no | Immutable source revision for the adapter/normalizer. |
| `adapter_version` | string | no | Adapter release/contract version. |
| `adapter_entrypoint` | string | no | Import path, executable, or service operation. |
| `adapter_bundle_sha256` | 64 lowercase hex | no | Digest of the exact adapter bundle/source archive. |
| `requested_model_identity` | object | no | `{provider, model, version, endpoint_or_deployment}`; unavailable members are null, never inferred. |
| `validated_returned_model_identity` | object/null | yes | Identity observed during admission: `{model, version, deployment, response_field_sources}`. Null requires `returned_identity_gap`. Per-run returned identity is still recorded independently. |
| `returned_identity_gap` | string/null | yes | Why no concrete returned model/version/deployment identity can be validated. Required when the previous field is null. |
| `model_artifacts` | array | no | Zero or more artifact descriptors below; cloud-only profiles may use none when bytes are inaccessible. |
| `preprocessing` | object | no | `{code_ref, config, config_sha256, image_decode_policy, resize_policy, color_space}`. Config is canonical JSON. |
| `inference_parameters` | object | no | Canonical, non-secret candidate parameters sent to the model/runtime. Empty object is valid. |
| `prompt` | object/null | yes | `{template_ref, template_sha256, system_text_sha256, rendering_revision}` when prompting affects output. Prompt text itself is stored as a separate hashed artifact if large/sensitive. |
| `taxonomy_mapping` | object | no | `{taxonomy_revision, mapping_revision, mapping_sha256, provider_to_portable_class}`. Every emitted portable class must belong to the frozen taxonomy. |
| `outcome_rule_revision` | string | no | Version of the deterministic mapping from normalized observations/context to the top-level outcome. |
| `runtime_profile` | object | no | Exact runtime object below. |
| `hybrid_boundaries` | ordered array | no | Exact ordered stages below; one stage is valid for non-hybrid profiles. |
| `class_state_contract_revision` | string | no | Revision whose enum is exactly the four class states above. |
| `analysis_outcome_contract_revision` | string | no | Revision whose enum is exactly the five outcomes above. |
| `profile_sha256` | 64 lowercase hex | no | SHA-256 of canonical JSON for all semantic fields above, excluding lifecycle/audit metadata. |
| `created_at` | RFC3339 timestamp | no | Creation time. |
| `created_by` | string | no | Principal/tool identity. |
| `decision_at` | RFC3339 timestamp/null | yes | Admission/rejection time. |
| `decision_report_uri` | URI/null | yes | External admission report. |
| `decision_report_sha256` | 64 lowercase hex/null | yes | Digest of that report. |

Artifact descriptor:

```json
{
  "role": "model|weights|tokenizer|label_map|runtime_config|prompt",
  "uri": "immutable-or-content-addressed-uri",
  "sha256": "64-lowercase-hex",
  "size_bytes": 123,
  "media_type": "application/octet-stream",
  "source_revision": "publisher-version-or-commit",
  "license_id": "SPDX-or-reviewed-proprietary-marker"
}
```

`runtime_profile`:

```json
{
  "python_implementation": "CPython or null",
  "python_version": "exact patch version or null",
  "uv_version": "exact version or null",
  "pyproject_sha256": "hex or null",
  "uv_lock_sha256": "hex or null",
  "package_snapshot_sha256": "hex or null",
  "os": "exact family/build or provider-managed",
  "architecture": "x86_64|arm64|provider-managed|other exact value",
  "cpu_model": "host value or null",
  "memory_bytes": 0,
  "accelerator": "cpu|coreml|cuda|directml|provider_managed",
  "accelerator_name": "device value or null",
  "driver_version": "reported value or null",
  "backend_name": "runtime/backend",
  "backend_version": "exact version",
  "requested_provider_order": [],
  "available_providers": [],
  "effective_providers": [],
  "container_image_digest": "sha256:... or null",
  "random_seed": 0,
  "determinism": "enforced|best_effort|not_available",
  "determinism_settings": {},
  "max_parallelism": 1,
  "attempt_timeout_ms": 60000,
  "sdk_retry_count": 0
}
```

`hybrid_boundaries` is ordered by `ordinal`, which must be contiguous from 1:

```json
[
  {
    "ordinal": 1,
    "boundary_id": "local-preprocess",
    "executor": "local|cloud",
    "component_ref": "immutable code/service revision",
    "requested_model_ref": "model identity or null",
    "input_contract_revision": "contract revision",
    "output_contract_revision": "contract revision",
    "crosses_network": false,
    "payload_kinds": ["image_bytes"],
    "retention_policy_ref": "policy revision"
  }
]
```

This makes local preprocessing → cloud inference → local normalization explicit rather than hiding it behind `execution_kind='hybrid'`. Images, model weights, raw responses, overlays, and logs remain outside PostgreSQL; only structured metadata, URIs, hashes, outcomes, observations, and measurements are persisted. No vector store or `pgvector` is in scope.

## Admission gates

1. **Profile integrity:** immutable adapter reference and digest; canonical profile digest; all accessible artifacts re-hash to declared SHA-256. Python's standard library supplies SHA-256/file-digest primitives [S5].
2. **Install reproducibility:** for Python profiles, `uv lock --check` succeeds before `uv sync --frozen --no-editable`; exact Python, uv, lock, project, and installed-package snapshot are recorded. uv documents that `--frozen` uses a lock without checking freshness, while `uv lock --check` performs the check [S1].
3. **Portable contract:** adapter emits only the exact per-class states and separate top-level outcomes above; schemas reject conflation. Native count/confidence/geometry cannot enter the business rule or scorer.
4. **Identity:** requested identity is concrete; returned model/version/deployment/request identifiers are captured when the provider exposes them. Vertex exposes model, model version, and deployed model fields [S6]; SageMaker exposes a production variant and a different identity surface [S7]. Gaps remain explicit.
5. **Local CPU:** every local candidate has an admitted ordinary-laptop CPU revision. Apple Silicon CoreML and Windows RTX 3060 CUDA/DirectML are additional revisions, never substitutes.
6. **Native runtime proof:** requested, available, and effective providers are read back on the target host. ONNX Runtime, if used, orders execution providers by priority and exposes runtime provider inspection [S3]; do not infer execution from a package name.
7. **PostgreSQL-only system runtime:** the application refuses any non-PostgreSQL URL, reaches migration head, and transactionally writes/reads one profile reference, run, observation set, and outcome. There is no SQLite dependency, URL, fallback, test runtime, or second persistence implementation. SQLAlchemy may be used with an explicit PostgreSQL dialect URL [S8]. This is an admission/system gate, not an execution-profile field.
8. **Four mandatory scenario smokes:** one controlled check-request, no-check, insufficient-data, and out-of-scope fixture validates plumbing and persistence. Out-of-scope expects top-level `not_analyzed`; it does not introduce an `out_of_scope` class state.
9. **Failure semantics:** forced timeout, exception, malformed response, missing artifact, and provider failure each create a terminal failed `AnalysisRun`; none is converted to a domain outcome and none is automatically retried.
10. **Fair-run readiness:** concurrency is one, SDK retries are zero, timeout is fixed, pricing inputs are snapshotted, and returned cloud request/model identity can be stored per run.

Minimal admission commands:

```bash
set -euo pipefail
export PROFILE_FILE='profiles/replace-me.json'
export PYTHON_VERSION='replace-exact-x.y.z'
export RUNTIME_EXTRA='runtime-replace-me-cpu'
export OBSERVER_MODULE='construction_monitoring.observer_cli'
export DATABASE_URL='postgresql+psycopg://user:password@127.0.0.1:5432/construction_monitoring'

uv --version
uv python install "${PYTHON_VERSION}"
uv lock --check
uv sync --frozen --no-editable --python "${PYTHON_VERSION}" --extra "${RUNTIME_EXTRA}"
uv run --frozen python -m "${OBSERVER_MODULE}" profile validate --profile "${PROFILE_FILE}" --verify-hashes
uv run --frozen python -m "${OBSERVER_MODULE}" runtime probe --profile "${PROFILE_FILE}" --write-report artifacts/admission/runtime.json
uv run --frozen python -m "${OBSERVER_MODULE}" system postgres-smoke --database-url-env DATABASE_URL --reject-non-postgresql --require-migration-head
uv run --frozen python -m "${OBSERVER_MODULE}" contract smoke --profile "${PROFILE_FILE}" --manifest evaluation/manifests/contract-smoke-v2.json
```

The module/subcommands are interface templates, not claims that code already exists. Fully pinned, hash-checked pip requirements are an evidence-backed fallback packaging pattern, but remain a separately reviewed exception to the uv workflow [S2].

## Corrected evaluation matrix

### Baseline batch

Freeze one manually labelled 10–15-image manifest before candidate execution. It contains all four mandatory fixture categories, immutable image hashes, expected top-level outcome, and one expected state for every class in the taxonomy.

For baseline batch `B1`, create exactly one `AnalysisRun` per admitted candidate profile revision × fixture:

```text
UNIQUE (evaluation_batch_id, observer_execution_profile_revision_id, fixture_id)
```

There is no mutable `ExecutionAttempt` retry collection inside the run. `AnalysisRun.execution_status` is exactly `succeeded | error | timeout`; `analysis_outcome` is nullable and populated only when succeeded. A failed run remains the planned cell and stays in every applicable denominator.

### Repeated-run batches

Reproducibility repeats are new planned runs, not retries. Create successor batches `B2` and `B3` from the same frozen manifest and profile set. Each successor again has one fresh `AnalysisRun` per candidate × fixture. Link comparable cells with:

```text
comparison_cell_key = SHA256(profile_revision_id || fixture_id || experiment_family_id)
repeat_ordinal = 1, 2, 3
predecessor_analysis_run_id = null for B1, previous run for B2/B3
```

The uniqueness constraint remains batch-local. Changing candidates, fixtures, timeout, concurrency, prompt, artifact, taxonomy mapping, outcome rule, or runtime profile creates a new experiment family or explicitly versioned matrix, not a silent repeat.

Only an explicit later architecture decision may model a planned run as a container of multiple execution attempts. Until then, retries inside one `AnalysisRun` are prohibited.

### Fixture shape

```json
{
  "fixture_id": "fx-001",
  "fixture_category": "check_request|no_check|insufficient_data|out_of_scope|observations_only",
  "image_uri": "object://evaluation/sha256/<digest>",
  "image_sha256": "64-lowercase-hex",
  "expected_analysis_outcome": "check_requested",
  "expected_class_observations": {
    "portable-class-a": "detected",
    "portable-class-b": "not_detected_in_frame"
  },
  "label_policy_revision": "label-policy/v1",
  "labeler_id": "pseudonymous-id",
  "adjudication_note": "short note"
}
```

### Measurements across B1–B3

- **False warning:** successful run returns `check_requested` while expected outcome is any other outcome. The gate is exactly zero false warnings across all planned cells; report `0 / denominator`, never a rounded rate.
- **Check-request miss:** expected `check_requested` but returned another outcome, errored, or timed out.
- **Class miss:** for each expected `detected`, observed state is anything else; error/timeout is a miss for every expected-detected class.
- **False detection:** expected `not_detected_in_frame`, but observed `detected`. `insufficient_data` and `not_analyzed` are neither silently negative nor false detections; report their confusion cells separately.
- **Outcome accuracy:** exact outcome match divided by all planned cells, with error/timeout incorrect.
- **Class exact match:** every class state exactly matches; error/timeout incorrect.
- **Repeated-run disagreement:** for each `comparison_cell_key`, disagreement exists when any B1–B3 terminal status, top-level outcome, or complete class-state map differs. Report exact stable cells / all cells plus per-field disagreement counts.
- **Latency:** monotonic wall time from preprocessing start through schema-valid normalized result or terminal failure; report success median/p95/max and failed elapsed times separately. Do not mix cold-start and warm-run phases.
- **Cost:** include all planned runs, including failures/timeouts; store provider-reported usage, snapshotted unit price, currency, and `actual|estimated`. Never invent local currency cost without measurement.
- **Identity completeness:** per cloud run, preserve request ID and returned model/version/deployment fields actually exposed; list gaps rather than copying requested identity into returned identity.

PyTorch explicitly warns that complete reproducibility is not guaranteed across releases, platforms, or CPU/GPU even with identical seeds; therefore stability is measured across exact profile revisions and never assumed across hardware profiles [S4].

## Claims table

| ID | Evidence-backed claim | Source | Publisher | Pub date | Accessed | Confidence | Class |
|---|---|---|---|---|---|---|---|
| S1 | uv distinguishes lock freshness checking from frozen lock use; exact sync and non-editable install controls are available. | https://docs.astral.sh/uv/concepts/projects/sync/ | Astral | live docs, date not stated | 2026-09-22 | high | tooling behavior |
| S2 | Pinned requirements and hash-checking improve repeatable installs; compiled wheel bundles can be platform-specific. | https://pip.pypa.io/en/latest/topics/repeatable-installs/ | Python Packaging Authority | live docs, date not stated | 2026-09-22 | high | packaging/reproducibility |
| S3 | ONNX Runtime supports ordered execution providers and runtime provider inspection. | https://onnxruntime.ai/docs/execution-providers/ | Microsoft / ONNX Runtime | live docs, date not stated | 2026-09-22 | high | runtime behavior |
| S4 | PyTorch does not guarantee complete reproducibility across releases/platforms or CPU/GPU and documents deterministic controls. | https://docs.pytorch.org/docs/2.14/notes/randomness.html | PyTorch Foundation | 2026-05-14 | 2026-09-22 | high | reproducibility |
| S5 | Python `hashlib` provides SHA-256 and file-digest APIs. | https://docs.python.org/3/library/hashlib.html | Python Software Foundation | docs 3.14.7; page date not stated | 2026-09-22 | high | artifact integrity |
| S6 | Vertex `PredictResponse` exposes deployed-model, model-resource, and model-version identity fields. | https://cloud.google.com/nodejs/docs/reference/aiplatform/latest/aiplatform/protos.google.cloud.aiplatform.v1.predictresponse | Google Cloud | page date not stated | 2026-09-22 | high | cloud observability |
| S7 | SageMaker `InvokeEndpoint` exposes invoked production variant and optional response custom attributes, demonstrating a different identity surface. | https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html | Amazon Web Services | live docs, date not stated | 2026-09-22 | high | cloud observability |
| S8 | SQLAlchemy supports explicit PostgreSQL dialect URLs including `postgresql+psycopg://...`. | https://docs.sqlalchemy.org/en/20/dialects/postgresql.html | SQLAlchemy project | release 2.0.54, 2026-09-15 | 2026-09-22 | high for cited release; pin in implementation | version/compatibility |

## Remaining gaps

- Quantify the ordinary-laptop CPU reference host and resource/timeout envelope before admission.
- Freeze the class taxonomy, class labelling policy, outcome rule, and treatment of context fields before creating B1.
- Decide whether `observations_only` is reachable in MVP; if yes, add a labelled fixture without changing mandatory fixture semantics.
- Revalidate each selected candidate's exact runtime/platform compatibility on the native host. Documentation alone is not admission evidence.
- Define price snapshots only after cloud candidates and billing units are known.
- The 10–15-image matrix is a rapid-MVP diagnostic. Report exact counts and fixtures; do not claim population accuracy or a universal winner.

---
title: 'Technical research: AI candidates for Construction Monitoring Rapid MVP'
type: 'technical'
topic: 'AI candidates for Construction Monitoring Rapid MVP'
decision: 'Select two local and two cloud candidates for a shared experiment without selecting the final execution winner from documentation'
source: 'native research; 24 official and primary sources'
status: complete
preset: 'standard'
validation: 'high'
verified_claims: 6
unverified_claims: 3
disputed_claims: 1
overturned_claims: 1
created: '2026-09-22'
updated: '2026-09-22'
---

# Technical research: AI candidates for Construction Monitoring Rapid MVP

**Decision this research serves:** select one primary and one reserve local detector, and one primary and one reserve cloud multimodal model, for a controlled comparison. Documentation qualifies candidates; it does not select a final local, cloud, or hybrid winner. Only the experiment does.

## Executive summary

The revised shortlist applies two additional hard gates: the candidate must be lawfully accessible and supportable from Russia and must be usable in a closed commercial product without silently assuming an unavailable license or foreign billing path.

1. **Local primary — custom RF-DETR Nano**, `rfdetr==1.10.0` at release commit `0f432b6`, initialized from the official `rf-detr-nano.pth` and fine-tuned to exactly `excavator` and `dump_truck`. RF-DETR's official documentation explicitly licenses both code and the core Nano–Large checkpoints under Apache-2.0 [1][2][3].
2. **Local reserve — Grounding DINO Tiny**, `IDEA-Research/grounding-dino-tiny` at immutable Hugging Face revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`, through a locked Transformers/PyTorch runtime. The exact model page is labeled Apache-2.0 and exposes a safetensors artifact [6][7].
3. **Cloud primary — GigaChat API `GigaChat-2-Max`**, using a paid corporate route. Official documentation covers Russian legal entities and individual entrepreneurs, commercial use on paid tariffs, image analysis, and strict JSON Schema output [15][16][17][18].
4. **Cloud reserve — Kimi API `kimi-k3`, test-only and conditional.** Kimi documents image input, strict JSON Schema, and commercial integration. Official material retrieved in this run does not affirm Russian-entity onboarding or Russian payment support, and its data-use pages have unresolved scope and document-hierarchy ambiguity. Kimi may enter only a non-sensitive technical canary until those gates are resolved [8][9][10][11][12][13][14].

**Ultralytics YOLO26 is not freely embeddable by default in a closed commercial product.** Ultralytics offers AGPL-3.0 or Enterprise licensing. AGPL permits commercial use when its obligations are followed, but it is not a blanket proprietary-product license; Enterprise terms and Russia procurement were not verified. YOLO26 remains a technical lead, not an admitted primary or reserve, until the owner deliberately chooses AGPL compliance or signs acceptable Enterprise terms [5].

No retrieved official source establishes excavator/dump-truck accuracy for any finalist. No comparable ordinary-laptop latency measurements exist for the two local finalists. Those are experiment questions. The final execution approach must therefore be selected only after complete shared-fixture runs, including errors and timeouts.

The system constraints remain unchanged: PostgreSQL is the sole structured-state database; SQLAlchemy may remain; images, weights, raw responses, and large evidence artifacts stay outside PostgreSQL; no `pgvector` task is substantiated. Per-class observations use only `detected`, `not_detected_in_frame`, `insufficient_data`, or `not_analyzed`. Rule evaluation never consumes provider-native counts, confidence, or geometry.

## Evidence labels

- **Verified fact:** backed by a current official or primary source retrieved in this run.
- **Project decision:** binding product or architecture constraint, not an external claim.
- **Assumption:** proposed design value requiring owner approval or measurement.
- **Experiment required:** documentation cannot answer the question.

## Candidate-admission gates

Every candidate must pass all applicable gates before a scored run:

1. **Identity:** exact package/model/adapter revision, prompt and preprocessing revision, and SHA-256 for every accessible artifact.
2. **Commercial rights:** code license, checkpoint license, API contract, and custom training-data rights recorded separately. This report is technical/licensing triage, not legal advice.
3. **Russia access:** local candidates pass a clean install/download on the intended Russian network and then a network-blocked run from an internal immutable mirror. Cloud candidates must pass lawful signup and payment checks, plus model-entitlement and API canaries, through an account owned by the actual future customer; no VPN or foreign-person workaround counts.
4. **Reproducible install:** committed `pyproject.toml` and `uv.lock`; `uv lock --check`; `uv sync --frozen --no-editable`; native smoke on every claimed platform [21].
5. **Required classes:** both `excavator` and `dump_truck` are addressable without treating generic `truck` as `dump_truck`.
6. **Portable contract:** exactly one of the four observation states per requested class. The top-level analysis outcome is a different enum.
7. **No rule leakage:** native count, confidence, boxes, masks, or model prose may be retained as attributed evidence but cannot drive the excavation rule.
8. **Local CPU:** every local candidate completes the full evaluation set on an ordinary-laptop CPU profile. Apple Silicon and RTX 3060 are additional profiles, not substitutes.
9. **PostgreSQL-only runtime (project decision):** application startup rejects non-PostgreSQL URLs; migration/read/write smoke passes; there is no SQLite fallback, package, test runtime, or second database.
10. **Failure semantics:** a timeout, provider error, malformed output, or missing artifact creates a terminal failed run. It never becomes absence, `no_check`, or `insufficient_data`.
11. **One real end-to-end fixture:** one fixture must complete the real adapter, normalization, external artifact publication, PostgreSQL state, and final projection before comparison admission.
12. **No hidden fallback:** changing provider or hardware mode creates a new immutable execution-profile revision and a new run.

## Decision matrix

Scores are screening judgments from 1–5 using the approved weights. They express readiness to test, not model accuracy, and must not be used as a final winner score.

| Candidate | Contract fit 25% | Reproducible laptop/runtime 20% | Demo reliability and revision identity 20% | Evidence and structured output 15% | Privacy 10% | Latency and cost 10% | Weighted screen | Status |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Custom RF-DETR Nano | 5 | 4 | 4 | 5 | 5 | 3 | **4.40** | Primary local candidate; conditional on data and legal smoke |
| Grounding DINO Tiny | 3 | 4 | 3 | 5 | 5 | 2 | **3.60** | Reserve local candidate |
| GigaChat-2-Max paid corporate | 3 | 3 | 4 | 2 | 3 | 4 | **3.15** | Primary cloud candidate; conditional on account and data terms |
| Kimi `kimi-k3` | 3 | 2 | 1 | 2 | 2 | 3 | **2.15** | Reserve cloud candidate; conditional and limited to non-sensitive tests |

The local and cloud totals are not directly comparable as quality scores. Local candidates score higher on reproducible identity and evidence regions; cloud candidates avoid training but introduce account, retention, and revision uncertainty.

## Local candidate profiles

### Primary: custom RF-DETR Nano

| Dimension | Profile |
|---|---|
| Exact version | `rfdetr==1.10.0`, release commit `0f432b6`; official `rf-detr-nano.pth`; resulting `checkpoint_best_total.pth` pinned by SHA-256 [1][3]. |
| Licence | Official docs state Apache-2.0 for code and core Nano–Large checkpoints. Exclude `rfdetr_plus`, XLarge, and 2XLarge, which use different terms/account requirements [1][2]. |
| Required classes | Custom two-class fine-tune to `excavator` and `dump_truck`; fine-tuning is required. |
| Training data | Use only owned/licensed construction images, with source and commercial-training rights in the manifest. A base-weight license does not grant rights in custom images. |
| CPU | Measure the mandatory PyTorch CPU profile first, then measure ONNX and OpenVINO exports separately. Published T4 figures are not laptop evidence [4]. |
| Apple Silicon | Optional MPS and CoreML/ExecuTorch-CoreML profiles; compare normalized states and evidence regions with CPU [4]. |
| RTX 3060 | CUDA FP32 first; FP16/TensorRT only as separate revisions after parity. |
| Locking | Pin Python, uv, `rfdetr`, PyTorch, export runtime, source commit, base/checkpoint hashes, dataset/split manifest, training config, and seed. |
| Latency | **Experiment required:** install time, cold start, warm p50/p95/max, peak memory, and failure rate on exact machines. |
| Evidence regions | Native boxes are useful attributed evidence. Counts, confidence, and geometry remain non-portable and non-rule-driving. |
| Structured output | Adapter emits the closed four-state class schema; native result is an immutable sidecar. |
| Cost/network | No per-call fee. Initial public downloads must be mirrored lawfully; scored inference must pass offline. |
| Privacy | Images can stay local, subject to local access control and outbound-network audit. |
| Live-demo risk | Medium until training data, target-device latency, export parity, and Russian-host install are verified. |

**Assumption, not a verified minimum:** begin planning with 500–1,000 diverse training/validation frames and at least 250 labeled instances per class, including empty frames, hard negatives, occlusion, distance, night, and adverse weather. Split by site/camera/time sequence. Learning curves, not this number, determine whether more data are required.

### Reserve: Grounding DINO Tiny

| Dimension | Profile |
|---|---|
| Exact version | `IDEA-Research/grounding-dino-tiny@e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`; prefer 692 MB `model.safetensors`; pin Transformers/PyTorch [6][7]. |
| Licence | Exact model page labels the revision Apache-2.0. Preserve notices; separately review upstream training-data provenance [6][7]. |
| Required classes | Open-vocabulary prompts make both phrases addressable; this is not evidence of accuracy. |
| Fine-tuning | Not required for initial admission. Freeze prompts and thresholds before the held-out test. |
| CPU | Mandatory; the official repository documents a CPU-only route [24]. |
| Apple Silicon | CPU mandatory; MPS experimental and must expose any CPU fallback. |
| RTX 3060 | CUDA FP32 profile; mixed precision only after parity. |
| Locking | Immutable HF revision, per-file hashes, prompt/threshold/preprocessing hashes, and platform lock. Pass offline snapshot smoke. |
| Latency | **Experiment required.** No hardware-comparable laptop or RTX 3060 result was found. |
| Evidence regions | Text-linked boxes/scores available; geometry remains human evidence only [6]. |
| Cost/network/privacy | No per-call fee; initial 1.38 GB snapshot download; fully local after lawful staging. |
| Live-demo risk | Medium-high because of artifact size, unknown CPU latency, and unverified MPS behavior. |

### Ultralytics YOLO commercial finding

Ultralytics YOLO26 remains technically attractive for a custom two-class model and likely benefits strongly from the RTX 3060. It is not in the admitted pair because the verified license choices are:

- **AGPL-3.0:** commercial activity is possible, but the actual product must comply with reciprocal license obligations; this is not the same as unrestricted proprietary embedding.
- **Enterprise:** intended by Ultralytics for proprietary/internal production that does not follow the AGPL route, but public fixed price and Russia-specific procurement were not found [5].

If the owner accepts AGPL compliance or signs an acceptable Enterprise agreement, custom YOLO26n can re-enter as a technical challenger. YOLOX code is Apache-2.0, but the reviewed official sources did not explicitly license release checkpoints separately; it was not admitted under the strict code-and-weights gate. Training YOLOX from scratch on fully licensed data remains a possible later route.

## Cloud candidate profiles

### Primary: GigaChat API `GigaChat-2-Max`

| Dimension | Profile |
|---|---|
| Russia/commercial status | Official corporate routes address Russian legal entities and individual entrepreneurs. Commercial use requires a paid package/pay-as-you-go route; freemium is non-commercial [17][18]. |
| Exact model/version | Request alias `GigaChat-2-Max`; responses may expose a served revision such as `GigaChat-2-Max:2.0.30.01`, but requestable immutable pinning is not documented [16]. |
| Image input | Model page explicitly lists image input and image analysis. Supported uploads include JPEG/PNG/TIFF/BMP; files can be deleted [15][20]. |
| Structured output | Strict JSON Schema is documented and demonstrated with GigaChat 2 Max [16]. |
| Required classes | Zero-shot or few-shot image classification with explicit class definitions. No machinery benchmark was found. |
| Fine-tuning | No verified fine-tuning path for this exact multimodal API candidate; not required for the first test. |
| Evidence regions | No guaranteed detector-grade boxes. Text explanations are secondary evidence only. |
| Revision pinning | Moving request alias; record served revision and run a frozen-fixture pre-demo canary. |
| Price | Direct corporate material lists 0.65 RUB/1,000 synchronous tokens including VAT, but since 2026-09-01 new customers are directed to Cloud.ru. Read back the actual new-account catalog and tariff before budgeting [19]. |
| Privacy/retention | The corporate agreement covers confidentiality and processing of client/representative personal data. Retrieved sources do not establish retention, training use, or personal-data treatment for uploaded construction imagery. Delete uploaded files immediately, and require written data-governance acceptance before real imagery [17][20]. |
| Network/demo risk | Medium-low relative to alternatives: Russia contracting is evidenced, but Cloud.ru onboarding drift, quota, alias movement, network, retention, and target accuracy remain open. |

### Reserve: Kimi API `kimi-k3` — test-only conditional

| Dimension | Profile |
|---|---|
| Russia/commercial status | General product/API integration is permitted by Kimi OpenPlatform terms, but official sources do not affirm Russian-entity eligibility or Russian payment methods. Sanctions/export clauses apply. It is not an approved Russia production dependency [11][14]. |
| Exact model/version | Current multimodal ID `kimi-k3`; Kimi K2.5 and old `moonshot-v1-*-vision-preview` IDs were discontinued 2026-08-31 [8]. |
| Image input | Native visual understanding; official K3 guide accepts base64/file image input [8][9][10]. |
| Structured output | Strict `json_schema` is documented [9][10]. |
| Required classes | Zero-shot or few-shot only. No excavator/dump-truck evidence was found. |
| Fine-tuning | Managed API does not expose user fine-tuning for this test; not required initially. |
| Evidence regions | No guaranteed calibrated detector geometry. |
| Revision pinning | No requestable dated snapshot; record returned model/request identity and canary drift. |
| Price/payment | K3 is token billed and requires a successful top-up; official material does not confirm Russian cards, bank transfer, ruble settlement, or Russian tax documents [14]. |
| Privacy/retention | Official pages have unresolved scope and document-hierarchy ambiguity: the API help center says API inputs/outputs are not used for training, the general terms allow broader service-improvement use, and enterprise ZDR has image-upload caveats [11][12][13]. Resolve applicability in signed terms; send no real site imagery during the technical canary. |
| Network/demo risk | High until lawful signup, payment, `GET /models`, one strict-schema image request, privacy terms, and commercial eligibility are verified from the intended Russian network/account. |

## Exact `ObserverExecutionProfileRevision`

The immutable revision describes observer execution, not database configuration.

| Field | Required content |
|---|---|
| `id`, `candidate_key`, `revision`, `status` | UUID identity, stable slug, monotonic revision, and `draft|admitted|rejected|retired`. |
| `execution_kind` | `local_process|local_container|cloud_api|hybrid`. |
| `adapter_code_ref`, `adapter_version`, `adapter_entrypoint`, `adapter_bundle_sha256` | Exact adapter identity and digest. |
| `requested_model_identity` | `{provider, model, version, endpoint_or_deployment}` with explicit nulls. |
| `validated_returned_model_identity`, `returned_identity_gap` | Admission-time returned identity or a required explanation of the gap. Per-run identity is recorded again. |
| `model_artifacts` | Array of `{role, uri, sha256, size_bytes, media_type, source_revision, license_id}`. |
| `preprocessing` | `{code_ref, config, config_sha256, image_decode_policy, resize_policy, color_space}`. |
| `inference_parameters` | Canonical non-secret parameters, including internal detector thresholds. |
| `prompt` | Nullable `{template_ref, template_sha256, system_text_sha256, rendering_revision}`. |
| `taxonomy_mapping` | `{taxonomy_revision, mapping_revision, mapping_sha256, provider_to_portable_class}`. |
| `outcome_rule_revision` | Version of normalized observations/context → analysis outcome mapping. |
| `runtime_profile` | Exact Python/uv/lock/package, OS/architecture, CPU/RAM, accelerator/device/driver, backend/provider, container digest, seed/determinism, timeout, concurrency, and SDK retries. |
| `hybrid_boundaries` | Ordered executor/component/model/input/output/network/payload/retention stages; one stage for non-hybrid profiles. |
| `class_state_contract_revision` | Contract defining exactly the four per-class states. |
| `analysis_outcome_contract_revision` | Contract defining `observations_only|not_analyzed|insufficient_data|check_requested|no_check`. |
| `profile_sha256` and audit fields | Canonical semantic digest; creator/time/decision/report URI/report hash. |

Each invocation also records the run, profile, stage, exact inputs, provider request and response IDs, served model, version and deployment fields, and native artifact references. Requested identity is never copied into a missing returned-identity field.

## Minimal installation and end-to-end smoke commands

These are **proposed CLI contracts to implement**, not commands already verified against a repository adapter.

### Shared locked install and PostgreSQL smoke

```bash
set -euo pipefail
export PROFILE_FILE='config/observers/replace-me.json'
export PYTHON_VERSION='replace-with-pinned-patch-version'
export RUNTIME_EXTRA='observer-replace-me-cpu'
export DATABASE_URL='postgresql+psycopg://user:password@127.0.0.1:5432/construction_monitoring'

uv --version
uv python install "${PYTHON_VERSION}"
uv lock --check
uv sync --frozen --no-editable --python "${PYTHON_VERSION}" --extra "${RUNTIME_EXTRA}"
uv run --frozen python -m construction_monitoring.observer_cli profile validate \
  --profile "${PROFILE_FILE}" --verify-hashes --verify-license-manifest
uv run --frozen python -m construction_monitoring.observer_cli system postgres-smoke \
  --database-url-env DATABASE_URL --reject-non-postgresql --require-migration-head
uv run --frozen python -m construction_monitoring.observer_cli contract smoke \
  --profile "${PROFILE_FILE}" --manifest evaluation/manifests/contract-smoke-v1.json
```

`uv lock --check` and `uv sync --frozen` serve different purposes: the first verifies freshness, the second consumes the locked environment [21]. SQLAlchemy documents explicit PostgreSQL dialect URLs such as `postgresql+psycopg://...` [23].

### Local offline smokes

```bash
UV_OFFLINE=1 uv run --frozen --extra observer-rfdetr-cpu \
  python -m construction_monitoring.observer_cli e2e \
  --profile config/observers/rfdetr-nano-construction-cpu.json \
  --fixture evaluation/fixtures/single-both-present.json

HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 uv run --frozen --extra observer-grounding-dino-cpu \
  python -m construction_monitoring.observer_cli e2e \
  --profile config/observers/grounding-dino-tiny-cpu.json \
  --fixture evaluation/fixtures/single-both-present.json
```

### Windows RTX 3060 smoke

```powershell
$ErrorActionPreference = 'Stop'
$env:PROFILE_FILE = 'config/observers/rfdetr-nano-construction-rtx3060.json'
uv lock --check
uv sync --frozen --no-editable --extra observer-rfdetr-cuda
uv run --frozen python -m construction_monitoring.observer_cli runtime probe `
  --profile $env:PROFILE_FILE --require-device-name 'NVIDIA GeForce RTX 3060'
uv run --frozen python -m construction_monitoring.observer_cli e2e `
  --profile $env:PROFILE_FILE `
  --fixture evaluation/fixtures/single-both-present.json
```

Grounding DINO uses a separate CUDA profile and lock fingerprint. FP16/TensorRT are separate revisions.

### Cloud canaries

```bash
GIGACHAT_CREDENTIALS="${GIGACHAT_CREDENTIALS:?missing}" \
uv run --frozen --extra observer-gigachat \
  python -m construction_monitoring.observer_cli e2e \
  --profile config/observers/gigachat-2-max.json \
  --fixture evaluation/fixtures/non-sensitive-canary.json \
  --delete-provider-file --max-requests 1 --no-sdk-retry

MOONSHOT_API_KEY="${MOONSHOT_API_KEY:?missing}" \
uv run --frozen --extra observer-kimi \
  python -m construction_monitoring.observer_cli e2e \
  --profile config/observers/kimi-k3-test-only.json \
  --fixture evaluation/fixtures/non-sensitive-canary.json \
  --max-requests 1 --no-sdk-retry
```

Secrets exist only in the process environment and must never appear in commands, reports, artifacts, or PostgreSQL.

## Comparative evaluation set

Freeze one manually labeled **11-image** evaluation set, disjoint from the training and validation data and within the required 10–15 range:

| Fixture | Images | Required purpose/outcome |
|---|---:|---|
| `single-both-present` | 1 | Class presence; `observations_only` |
| `single-excavator-only` | 1 | Single-frame non-detection never warns; `observations_only` |
| `series-positive` | 3 | Same-area ordered series with both classes; `no_check` |
| `series-check-request` | 3 | Excavator observed, dump truck not detected in all usable frames; `check_requested` |
| `series-insufficient` | 2 | Below the three-usable-image minimum; `insufficient_data` |
| `out-of-scope` | 1 | Unsupported scenario/class; `not_analyzed` |
| **Total** | **11** | Mandatory check/no-check/insufficient/out-of-scope coverage |

Every image has a content hash, manual labels for both classes, sufficiency notes, context/area metadata, source rights, and cloud-upload permission. Training/validation images for RF-DETR are separate.

Scoring rules:

- report class misses and false detections per class;
- errors/timeouts remain in every applicable denominator and count as misses for expected detections;
- `insufficient_data` and `not_analyzed` are not negatives;
- a false warning occurs when the result is `check_requested` but any other outcome is expected;
- readiness requires exactly **zero false warnings** across all planned runs and repeats;
- provider-native count/confidence/geometry is excluded from scoring and rule evaluation.

## Comparison-run plan

1. Freeze evaluation, policy, rule, taxonomy, preprocessing, prompts/thresholds, timeouts, concurrency (`1`), and SDK retries (`0`).
2. Admit RF-DETR CPU, Grounding DINO CPU, and GigaChat only after their gates pass. Kimi participates only with non-sensitive fixtures until Russia/commercial/data gates pass.
3. Run two complete two-candidate batches:
   - primary batch: RF-DETR Nano CPU × GigaChat-2-Max;
   - reserve batch: Grounding DINO Tiny CPU × Kimi K3 test-only.
4. Create exactly one `AnalysisRun` for every candidate × fixture pair in each batch. A failed cell remains in the matrix.
5. No retry inside a scored run. Then run two repeat batches with the same frozen matrices, for a total of three independent runs per comparison key.
6. Record and use a deterministic execution order, and run one cell at a time.
7. Report in this order: zero-false-warning gate; mandatory outcomes; class misses/false detections; errors/timeouts; repeated-run disagreement; latency; cost; reproducibility; identity and license gaps.
8. Do not collapse the result into one score. With 11 images, show every numerator, denominator, and failed fixture.

CPU, Apple Silicon, RTX 3060, and cloud profiles remain distinct. PyTorch does not guarantee reproducibility across releases, platforms, or CPU/GPU, even with fixed seeds [22].

## Live-demo risks

| Risk | Control |
|---|---|
| RF-DETR training artifact is late or overfits | Decide data budget now; freeze group-disjoint splits; retain Grounding DINO as zero-shot local reserve. |
| Public package/model hosts become unreachable from Russia | Fresh Russian-host install; internal content-addressed mirror; network-blocked scored run. |
| Ultralytics license is misunderstood | Keep YOLO outside the admitted shortlist until AGPL compliance or Enterprise agreement is explicit. |
| Laptop CPU is too slow | Full-set CPU admission timeout and memory gate; do not infer from T4/Xeon figures. |
| MPS/CoreML/CUDA differs from CPU | Separate profiles and per-fixture state/evidence parity before latency claims. |
| GigaChat onboarding changed to Cloud.ru | Read back model catalog, tariff, paid commercial terms, and account quota before implementation freeze. |
| Provider stores real project images | Consent-cleared fixtures; written data terms; GigaChat upload/delete verification; no real images in Kimi canary. |
| Kimi signup/payment is unavailable from Russia | Treat as optional test-only; never make it the live-demo fallback until actual account canary and written eligibility pass. |
| Cloud alias changes | Record served revision/request identity and run frozen canary 15–30 minutes before demo. |
| Network/API failure during jury demo | Hard deadline; no silent provider fallback; labeled last-known-good recorded run only. |

## Cross-dimension findings

1. The RTX 3060 materially improves training and optional CUDA inference, but does not relax the ordinary-laptop CPU admission gate.
2. Commercial clarity changes the local winner: RF-DETR's explicit code-and-core-checkpoint Apache-2.0 statement outweighs YOLO26's simpler engineering path under a closed-product requirement.
3. GigaChat is the only cloud candidate in this run with explicit Russian commercial contracting evidence. Kimi is technically interesting but not yet an approved Russia dependency.
4. Detector boxes improve human auditability but not rule semantics. Cloud models may pass the class task without grounded boxes; evidence-region availability must remain a separate matrix column.
5. Local artifacts can be fully content-addressed. Both cloud request IDs are moving aliases; reproducibility therefore requires served-version logging and repeated canaries.
6. PostgreSQL and external artifact storage are shared system gates, not candidate-ranking features. Nothing in this research justifies pgvector.

## Contrary evidence

- RF-DETR is not YOLO and still needs a substantial labeled corpus. The license advantage does not prove better accuracy or latency.
- Grounding DINO's checkpoint is explicitly Apache-2.0, but upstream training-data provenance remains a commercial diligence item.
- GigaChat is contractable in Russia, but exact retention/no-training terms for uploaded construction images and new-customer Cloud.ru pricing remain incomplete.
- Kimi documentation is internally inconsistent on data training/retention, and official Russia eligibility is absent. A successful API call would prove reachability, not contractual suitability.
- The 11-image set is a rapid-MVP diagnostic, not evidence of population accuracy.

## Recommendations

1. Prepare RF-DETR Nano and Grounding DINO Tiny locally; use the RTX 3060 for training/additional CUDA profiles while preserving CPU admission.
2. Keep Ultralytics YOLO as a licensed challenger only after an explicit AGPL-versus-Enterprise decision.
3. Open a paid GigaChat corporate/Cloud.ru path and run the upload → strict schema → delete canary before real integration.
4. Attempt Kimi K3 only with synthetic/non-sensitive imagery from the actual intended Russian network/account; stop if the signup, payment, or terms checks fail without circumvention.
5. Freeze the 11-image set before tuning prompts or thresholds. Any leakage creates a new evaluation revision.
6. Do not publish an active observer from this report. Publication requires complete comparison matrices with all failures/timeouts represented.

## Questions requiring owner decisions

1. Is the product intended to remain closed source? If not, would AGPL compliance be acceptable enough to bring custom YOLO26n back into the experiment?
2. If the product remains closed, is purchasing Ultralytics Enterprise worth exploring, or should the project standardize on Apache-licensed RF-DETR/Grounding DINO candidates?
3. Can the project obtain and label a training/validation corpus substantially larger than the 11-image held-out set, with documented commercial rights?
4. What exact machine defines the ordinary-laptop CPU baseline, and what per-image/demo timeout is acceptable?
5. Are real construction images allowed in GigaChat after contract review, and may any real image leave the laptop at all?
6. Should Kimi remain in the reserve matrix when only synthetic/non-sensitive fixtures are allowed, or should the reserve cloud slot be held until another Russia-contractable vision API is identified?
7. Is a clearly labeled recorded-result fallback acceptable during the jury demo?

## Open questions

- Actual class accuracy, abstention, repeat stability, and target-hardware latency for all four candidates.
- Minimum licensed training corpus for RF-DETR.
- Counsel approval of Apache notices, patents, and upstream checkpoint training-data provenance.
- New-customer GigaChat/Cloud.ru model catalog, tariff, retention, training use, and processing location.
- Kimi Russian customer eligibility, payment, tax documents, data terms, and live API availability.
- Exact cloud per-fixture cost and provider-returned model identity.

## Staleness map

Re-check candidate versions, model availability, SDK/runtime compatibility, Russian account entitlement, and Cloud.ru catalog **monthly**. Re-check API prices, license/contract terms, data-use and retention terms **quarterly and immediately before commitment**. Re-check ecosystem/model-card health **every six months**. Any model, prompt, artifact, driver, or hardware change invalidates latency and reproducibility evidence.

The mechanical claims ledger sets the earliest scheduled refresh to **2026-10-01**. Pricing, licensing, and privacy claims refresh by **2026-12-01**. Revalidate all cloud facts against the authoritative account immediately before a live demo.

## Source appendix

| Ref | Claim/finding supported | Publisher | Pub date | Accessed | Confidence |
|---|---|---|---|---|---|
| [1] | RF-DETR installation, training, export, Apache-2.0 code/core models | [RF-DETR official documentation](https://github.com/roboflow/rf-detr/blob/develop/docs/index.md) | Live 2026 docs | 2026-09-22 | High |
| [2] | Nano–Large Apache-2.0 versus XLarge/2XLarge PML/account distinction | [RF-DETR detection model table](https://github.com/roboflow/rf-detr/blob/develop/docs/learn/run/detection.md) | Live 2026 docs | 2026-09-22 | High |
| [3] | `rfdetr 1.10.0` and release commit | [RF-DETR releases](https://github.com/roboflow/rf-detr/releases) | 2026-09-04 | 2026-09-22 | High |
| [4] | CPU/MPS/export routes and non-comparable published performance | [RF-DETR FAQ](https://github.com/roboflow/rf-detr/blob/develop/docs/faq.md) | Live 2026 docs | 2026-09-22 | High for compatibility |
| [5] | Ultralytics AGPL-3.0/Enterprise branches | [Ultralytics documentation](https://docs.ultralytics.com/) | Live docs | 2026-09-22 | High |
| [6] | Grounding DINO open-vocabulary structured detection | [Hugging Face Transformers Grounding DINO documentation](https://huggingface.co/docs/transformers/model_doc/grounding-dino) | Live docs | 2026-09-22 | High |
| [7] | Pinned Grounding DINO Tiny revision, Apache-2.0 label, safetensors | [Hugging Face model revision](https://huggingface.co/IDEA-Research/grounding-dino-tiny/tree/e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e) | 2024-05 revision | 2026-09-22 | High |
| [8] | Current and discontinued Kimi model IDs | [Kimi official model list](https://platform.kimi.ai/docs/models) | Live docs | 2026-09-22 | High |
| [9] | Kimi K3 image and strict-schema request examples | [Kimi K3 quickstart](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart) | Live docs | 2026-09-22 | High |
| [10] | Kimi image/JSON API contract and stateless request behavior | [Kimi Chat API](https://platform.kimi.ai/docs/api/chat) | Live docs | 2026-09-22 | High |
| [11] | Kimi commercial integration, sanctions, and content-use terms | [Kimi OpenPlatform terms](https://platform.kimi.ai/docs/agreement/modeluse) | 2026-07-30 | 2026-09-22 | High; contract interpretation needs counsel |
| [12] | Kimi API help-center no-training claim | [Kimi data processing and security](https://www.kimi.ai/help/kimi-api/api-data-security) | Live docs | 2026-09-22 | Medium because broader terms conflict |
| [13] | Kimi enterprise/ZDR limitations | [Kimi zero-data-retention documentation](https://platform.kimi.ai/docs/guide/zero-data-retention) | Live docs | 2026-09-22 | Medium due document hierarchy ambiguity |
| [14] | Kimi account/payment methods and regional uncertainty | [Kimi account and payments](https://platform.kimi.ai/docs/guide/account-and-payments) | Live docs | 2026-09-22 | High for documented methods; Russia unsupported by evidence |
| [15] | GigaChat 2 Max image analysis and input modalities | [GigaChat 2 Max model page](https://developers.sber.ru/docs/ru/gigachat/models/gigachat-2-max) | Live docs | 2026-09-22 | High |
| [16] | GigaChat strict JSON Schema and served-version example | [GigaChat structured output](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output) | 2026-07-20 | 2026-09-22 | High |
| [17] | Russian corporate customer route and data/confidentiality terms | [GigaChat corporate agreement](https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-prepaid) | 2026-08-31 | 2026-09-22 | High |
| [18] | Paid-commercial versus freemium-noncommercial rule | [GigaChat commercial use](https://developers.sber.ru/docs/ru/gigachat/tariffs/commercial) | 2025-12-10 | 2026-09-22 | High |
| [19] | Corporate price evidence and Cloud.ru transition | [GigaChat corporate tariffs](https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs) | 2026-09-16 | 2026-09-22 | High; new-account readback required |
| [20] | GigaChat supported image files and deletion workflow | [GigaChat file workflow](https://developers.sber.ru/docs/ru/gigachat/guides/working-with-files) | 2026-07-17 | 2026-09-22 | High |
| [21] | uv lock freshness and frozen exact-sync behavior | [Astral uv project sync](https://docs.astral.sh/uv/concepts/projects/sync/) | Live docs | 2026-09-22 | High |
| [22] | Cross-platform/device reproducibility limitations | [PyTorch reproducibility](https://docs.pytorch.org/docs/2.14/notes/randomness.html) | 2026-05-14 | 2026-09-22 | High |
| [23] | Explicit SQLAlchemy PostgreSQL dialect URL syntax | [SQLAlchemy PostgreSQL documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) | 2.0.54, 2026-09-15 | 2026-09-22 | High |
| [24] | Grounding DINO CPU-only route and checkpoint provenance | [Grounding DINO official repository](https://github.com/IDEA-Research/GroundingDINO) | Live repository | 2026-09-22 | High |

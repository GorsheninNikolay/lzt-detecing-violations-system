# Local detector commercial/licensing correction — round 2, digest 1

**Decision served:** correct the local-detector shortlist after adding two hard gates: usable in a closed commercial product without assuming a negotiated license, and set up locally from Russia without a mandatory foreign SaaS runtime/account.

**Access date:** 2026-09-22. This is technical and licensing triage, **not legal advice**. Counsel must confirm the intended distribution/deployment model, notices, patent clauses, training-data provenance, sanctions/export-control exposure and any Russian-law requirements.

## Method and interpretation of the commercial gate

The screen separates four things that are often conflated:

1. **Source-code license.** A repository being “open source” does not by itself make it suitable for a proprietary product.
2. **Checkpoint/weight license.** Code and weights can have different terms; both must be explicit for a pretrained route.
3. **Training-data rights.** A permissive model-weight license does not automatically grant rights in every training image. The shared experiment should use owned/licensed construction images for fine-tuning and retain provenance.
4. **Operational access from Russia.** “No account required; public package and artifact download; fully local runtime” is treated as an admissible setup architecture. It is not proof that GitHub, PyPI or Hugging Face will remain reachable from every Russian network. A fresh Russian-host download test and a lawful internal artifact mirror are mandatory before relying on any candidate.

Only official documentation, repositories, releases and model cards were used. Product performance and laptop latency remain benchmark-required unless measured on comparable hardware.

## Corrected admission result

| Role | Exact candidate | Commercial/license basis | Admission |
|---|---|---|---:|
| **Primary** | **Custom RF-DETR Nano**, `rfdetr==1.10.0` (release commit `0f432b6`), initialized from official `rf-detr-nano.pth`, fine-tuned to exactly `excavator` and `dump_truck`; scored artifact is `checkpoint_best_total.pth` plus SHA-256 | Official RF-DETR documentation explicitly states that **all code and core Nano–Large models are Apache-2.0**. Nano needs no Roboflow account; XLarge/2XLarge are deliberately excluded because they use PML 1.0 and require an account. | **Admit** |
| **Reserve** | **IDEA-Research Grounding DINO Tiny**, `IDEA-Research/grounding-dino-tiny@e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`, exercised through pinned Transformers/PyTorch | The exact Hugging Face model revision is labeled Apache-2.0 and supplies safetensors; the official repository supports CPU-only local inference. No hosted inference service is required. | **Admit, with training-data diligence** |

**Ultralytics YOLO26n is demoted out of the primary/reserve pair.** AGPL-3.0 is an open-source license and can support commercial activity when its obligations are followed, but it is not a blanket permission to embed the code/models in a closed proprietary product without reciprocal-source implications. Ultralytics offers Enterprise licensing for proprietary/internal production use, but price, availability and acceptable terms are not assumed. Under the new hard gate, a candidate that depends on either accepting AGPL obligations or negotiating a paid license is conditional, so it cannot remain the default primary.

## Commercial/licensing matrix

| Candidate | Code license | Official checkpoint license | Training-data caveat | Russia-accessible setup architecture | Verdict |
|---|---|---|---|---|---|
| RF-DETR Nano | Apache-2.0 | Explicitly Apache-2.0 for core Nano–Large checkpoints | Official base checkpoint is COCO-trained and uses a DINOv2 backbone. The reviewed RF-DETR sources license the resulting core model, but do not provide a consolidated grant for every upstream training image. Use owned/licensed fine-tune data and retain provenance. | `pip/uv` package install; public checkpoint download/cache; local CPU/MPS/CUDA; ONNX/CoreML/TensorRT exports; no Roboflow account for Nano | **Primary** |
| Grounding DINO Tiny | Official repository Apache-2.0 | Exact HF model revision explicitly Apache-2.0 | Official repo names O365, GoldG and Cap4M training sources, but the model card does not provide a consolidated commercial license for all underlying datasets. Treat data provenance as residual counsel review. | Public HF snapshot; local Transformers/PyTorch; official CPU-only and CUDA paths; no hosted API/account required for local inference | **Reserve** |
| Ultralytics YOLO26n | AGPL-3.0 or Enterprise | Ultralytics states code/models use the same AGPL/Enterprise choice | COCO-pretrained base plus project fine-tune data; dataset provenance remains separate | Technically local and exportable, but closed-product use is conditional on AGPL compliance or an Enterprise agreement | **Demote / cut under unconditional commercial gate** |
| YOLOX 0.3.0 / YOLOX-Nano | Apache-2.0 repository | Official checkpoint files are release assets, but no separate first-party statement found that explicitly licenses the checkpoints under Apache-2.0 | COCO-pretrained; image rights remain distinct | Local source install, CPU/GPU demo, official ONNX/OpenVINO/TensorRT/ncnn paths; no SaaS runtime | **Cut under strict weight-license verification**; viable only if counsel accepts repo scope or the model is trained from scratch on licensed data |
| RF-DETR XLarge / 2XLarge | Separate `rfdetr_plus` terms | PML 1.0 | Same provenance questions plus platform terms | Roboflow account/platform agreement required | **Cut**: fails no-account/permissive-product gate |

## Evidence claims

| Claim | Source URL | Publisher | Pub/update date | Accessed | Confidence | Claim class |
|---|---|---|---|---|---|---|
| Ultralytics offers AGPL-3.0 and Enterprise licensing; its own documentation positions Enterprise for proprietary/internal production that does not follow the open-source route. | https://docs.ultralytics.com/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | license / commercial use |
| RF-DETR's official docs say all code and core Nano–Large models are Apache-2.0, support local pip/uv install and custom training, and export to ONNX/TensorRT. | https://github.com/roboflow/rf-detr/blob/develop/docs/index.md | Roboflow | live docs, 2026 | 2026-09-22 | high | code + checkpoint license / install |
| The official model table explicitly licenses RF-DETR Nano, Small, Medium and Large under Apache-2.0; XLarge and 2XLarge use PML 1.0 and require a Roboflow account. | https://github.com/roboflow/rf-detr/blob/develop/docs/learn/run/detection.md | Roboflow | live docs, 2026 | 2026-09-22 | high | checkpoint license / account requirement |
| Current RF-DETR release is `1.10.0`, released 2026-09-04 at commit `0f432b6`; release history also records portable export work and training/checkpoint changes. | https://github.com/roboflow/rf-detr/releases | Roboflow | 2026-09-04 | 2026-09-22 | high | version / revision |
| RF-DETR documents CPU and Apple MPS training modes and exports including ONNX, OpenVINO, TensorRT, ExecuTorch/CoreML and native CoreML. Published speed numbers are T4/TensorRT, not target-laptop evidence. | https://github.com/roboflow/rf-detr/blob/develop/docs/faq.md | Roboflow | live docs, 2026 | 2026-09-22 | high for compatibility; no laptop latency claim | compatibility / performance |
| YOLOX's official repository is Apache-2.0, provides CPU/GPU demos and lists ONNX, TensorRT, ncnn and OpenVINO deployment; official pretrained weights are linked as release assets. The reviewed official page does not state a separate weight license. | https://github.com/Megvii-BaseDetection/YOLOX | Megvii BaseDetection | live repository; latest release family 0.3.0 | 2026-09-22 | high for code/runtime; medium for negative weight-license finding | code license / checkpoint gap |
| The exact Grounding DINO Tiny revision is marked Apache-2.0, provides safetensors and documents direct local Transformers loading. | https://huggingface.co/IDEA-Research/grounding-dino-tiny/tree/e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e | IDEA Research / Hugging Face | model updated 2024-05-12 | 2026-09-22 | high | checkpoint license / revision |
| Grounding DINO's official repository supports CPU-only operation and identifies the Tiny checkpoint and its O365/GoldG/Cap4M training sources. | https://github.com/IDEA-Research/GroundingDINO | IDEA Research | live repository; CPU support announced 2023-03-27 | 2026-09-22 | high | CPU path / training provenance |

## Primary profile — custom RF-DETR Nano

### Why it replaces Ultralytics YOLO26n

RF-DETR Nano is current, small within its family, explicitly covered by the same permissive license for code and core pretrained weights, and has first-party custom-training plus portable-export paths. This removes the unresolved business dependency on either publishing a reciprocal-source product under AGPL terms or negotiating an Enterprise license. It is not a YOLO architecture, but under the commercial gate that trade is preferable to an ambiguous or conditional license.

### Exact experiment pin

- Package/source: `rfdetr==1.10.0`, release commit `0f432b6`.
- Initialization checkpoint: official `rf-detr-nano.pth`; download once, record the registry checksum and an independent SHA-256, then stage it internally.
- Custom output head: exactly two labels, `excavator` and `dump_truck`.
- Scored checkpoint: `checkpoint_best_total.pth`, hashed and bound to the dataset manifest, group split, seed, training configuration and package lock.
- Exclude `rfdetr_plus` and all XLarge/2XLarge assets from dependency resolution and artifact mirrors.

### Runtime modes

- **Ordinary laptop CPU:** mandatory PyTorch CPU smoke, followed by ONNX Runtime or OpenVINO. RF-DETR's published latency is on T4/TensorRT and is not portable evidence; measure warmed p50/p95, cold start, peak RSS and failures.
- **Apple Silicon:** mandatory CPU measurement plus experimental PyTorch MPS and native CoreML or ExecuTorch-CoreML export. First compare normalized decisions and evidence regions against CPU. MPS/CoreML support in current docs establishes a route, not target-model correctness or speed.
- **Windows RTX 3060:** PyTorch CUDA FP32 baseline; optional FP16 and TensorRT only after parity. No official RTX 3060 latency was found.

### Data and license controls

- Reuse the prior planning floor only as a starting hypothesis: 500–1,000 diverse labeled frames, at least 250 instances per class, hard negatives and leakage-resistant camera/site/time splits. Learning curves decide whether more labels are required.
- Fine-tune only on imagery the product owner is authorized to use for commercial model development. Store per-source rights/provenance in the dataset manifest.
- The Apache-2.0 checkpoint statement is strong evidence for model use, modification and distribution under that license; it does not erase third-party privacy, publicity, trademark or training-image claims. Preserve license/NOTICE materials and obtain counsel sign-off.

### Russia-access setup gate

The core route does not require a Roboflow account or hosted inference. Before experiment admission is finalized, run from a fresh Russian-host machine: resolve the hash-locked package, fetch `rf-detr-nano.pth`, export ONNX, disable network, and repeat inference. Mirror the verified wheel/source/checkpoint/export artifacts into a lawful internal registry so continued operation does not depend on foreign CDN reachability. Until that smoke succeeds, access is **architecturally eligible but not empirically confirmed**.

## Reserve profile — Grounding DINO Tiny

- Exact revision: `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`; use `model.safetensors`, record SHA-256 and pin the Transformers/PyTorch lock.
- Commercial basis: the exact model card says Apache-2.0. This is stronger than inferring a checkpoint license from a repository license.
- Classes: zero-shot prompts for `excavator` and `dump truck`; no initial fine-tune. Domain accuracy remains unproven.
- CPU: official CPU-only route. RTX 3060: CUDA through PyTorch/Transformers. Apple Silicon: CPU is mandatory; MPS is experimental with CPU fallback and requires parity testing.
- Local operation needs no hosted API or account after artifacts are staged. Perform the same Russian-host download plus network-blocked rerun and internal mirroring.
- Residual commercial risk: the official repository identifies multiple training sources but the pinned model card does not grant or summarize the rights of each underlying dataset. The weight license is explicit; training-data provenance still goes to counsel. This residual risk keeps it reserve rather than primary.

## Portable output and evidence regions

Both admitted candidates must use the same adapter:

- portable result: only `detected`, `not_detected_in_frame`, `insufficient_data`, or `not_analyzed`;
- native boxes, class IDs/text, scores, counts and model-specific tensors: audit sidecar only;
- evidence regions may be rendered for human review, but native confidence/count/geometry cannot drive downstream rules;
- every result records model/checkpoint hash, runtime artifact hash, preprocessing version and device mode.

Backend thresholds are frozen experiment configuration used inside the adapter, not portable business fields.

## Why Ultralytics is demoted

“Open source” and “free for a closed commercial product” are different statements. AGPL-3.0 is an OSI-approved open-source license and does not ban commercial activity. Its reciprocal obligations, including network-use concerns, are exactly why Ultralytics separately markets Enterprise licensing for proprietary/internal deployment. The research cannot assume that opening the relevant product source is acceptable, nor that Enterprise price/terms/procurement are acceptable in Russia. Therefore:

- Ultralytics YOLO26n remains a **technical benchmark lead**, not an admitted primary/reserve candidate;
- it can re-enter only after a documented product/legal choice: comply with AGPL for the actual architecture, or execute an acceptable Enterprise agreement;
- no engineering experiment result should be interpreted as resolving that license decision.

## Gaps and contradictions

- **Russia access:** public, account-free download architecture is evidenced; actual reachability from a Russian corporate/home network on 2026-09-22 was not measured. A mirror plan reduces continuity risk but does not cure an unlawful download or export-control restriction.
- **Permissive checkpoint versus training data:** RF-DETR core weights and Grounding DINO Tiny are explicitly Apache-2.0, yet neither reviewed model page consolidates commercial grants for every source training image. Weight license and data provenance are reported separately.
- **YOLOX ambiguity:** code license is clear; checkpoint license scope is not explicit in the reviewed official sources. Strict commercial screening therefore rejects the pretrained route rather than guessing that repository Apache terms extend to release binaries.
- **RF-DETR hardware evidence:** official docs now expose MPS/CoreML/ONNX/TensorRT routes, but published latency is T4-based. Ordinary laptop, Apple and RTX 3060 performance remains unmeasured.
- **HF availability:** the model is publicly downloadable without a hosted inference subscription, but CDN/account/export-policy availability can change. Pin and mirror only after a compliant download.

## Things searched but not found

- A first-party statement explicitly licensing YOLOX release checkpoints under Apache-2.0 separately from repository code.
- A public fixed price or Russia-specific availability commitment for Ultralytics Enterprise licensing.
- A primary-source guarantee that GitHub, PyPI, Hugging Face or Roboflow artifact CDNs are continuously reachable from Russia.
- A consolidated commercial-use license inventory for every image/source dataset used to train the RF-DETR and Grounding DINO checkpoints.
- Hardware-comparable latency for the exact fine-tuned RF-DETR Nano or Grounding DINO Tiny artifacts on an ordinary laptop, Apple Silicon and RTX 3060.

## Recommended commercial admission gates

1. Counsel signs off on Apache-2.0 notices/patent terms and the intended model-distribution form.
2. Dataset manifest proves commercial training rights for every custom frame; privacy and site permissions are separately recorded.
3. Fresh Russian-host install/download succeeds without a foreign SaaS account; artifacts are hashed and mirrored internally.
4. Network-blocked inference passes on the mirrored bundle.
5. CPU is accepted before accelerator modes; Apple MPS/CoreML and RTX 3060 CUDA/TensorRT must pass output/evidence parity before latency comparison.
6. Only after these gates run the shared accuracy/latency experiment. This digest selects candidates for that experiment, not the final local/cloud/hybrid product architecture.

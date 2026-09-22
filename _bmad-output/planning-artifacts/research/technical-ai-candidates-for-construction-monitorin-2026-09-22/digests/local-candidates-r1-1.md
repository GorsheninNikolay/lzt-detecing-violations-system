# Local detector candidates — round 1, digest 1

**Decision served:** qualify exactly one primary and one reserve local detector for a later shared experiment. This digest does **not** choose the final local/cloud/hybrid architecture.

**Access date:** 2026-09-22.

## Scope and method

The screen applied these hard gates from the research brief:

1. An ordinary-laptop CPU inference path is mandatory. Apple Silicon MPS and Windows RTX 3060 CUDA are additional experiment modes, never substitutes for CPU admission.
2. The detector must target `excavator` and `dump truck` in the rapid MVP. The required comparison is between (A) a custom fine-tuned YOLO branch and (B) a Hugging Face-hosted open-vocabulary/zero-shot branch; stock label sets must be checked rather than inferred from training data.
3. The portable decision contract is only `detected | not_detected_in_frame | insufficient_data | not_analyzed`. Native count, confidence, masks and geometry may be retained only as evidence/debug sidecars and must not drive downstream product rules.
4. A candidate must have a pinnable implementation and weights, an explicit license, a local structured-result path, and an experiment route for CPU plus additional MPS/CUDA measurements.

Two bounded source rounds were used. Round 1 mapped the current local field and decisive product/runtime facts using official documentation, repositories, releases and model documentation. Round 2 checked current versions, model revisions, MPS caveats, licensing and obvious alternatives. Only primary/official sources are cited. Published performance on server GPUs or Xeon CPUs is not treated as laptop latency evidence.

## Admission result

| Role | Exact candidate | Admission | Why |
|---|---|---:|---|
| **Primary** | **Custom fine-tuned Ultralytics YOLO26n detector**, initialized from `yolo26n.pt`, trained as exactly two classes (`excavator`, `dump_truck`) with **`ultralytics==8.4.158`** (release commit `ead936a`); scored artifact is the resulting `best.pt` plus its SHA-256 | **Admit, conditional on data + license gates** | The nano model has the clearest ordinary-laptop CPU/export route and a first-party custom fine-tuning recipe. Stock COCO is not sufficient: its 80 labels contain generic `truck`, but neither `dump truck` nor `excavator`. The primary therefore buys domain specificity at the cost of annotation/training and AGPL/Enterprise review. |
| **Reserve** | **IDEA-Research Grounding DINO Tiny**, Hugging Face model **`IDEA-Research/grounding-dino-tiny@e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`**, exercised through **`transformers==5.8.1`** | **Admit** | Permissive Apache-2.0 model card, official text-prompt object-detection interface, CPU-only path and exact immutable model revision. It is substantially larger (692 MB weights, 1.38 GB repository snapshot) and has no comparable laptop latency evidence; MPS is experimental, so it is the reserve rather than co-primary. |

This is experiment admission, not a production recommendation. The primary loses admission if legal review rejects AGPL-3.0 and no acceptable Enterprise license is available, or if the minimum labeled-data gate below cannot be met without contaminating the evaluation set. In either case, promote Grounding DINO Tiny to primary for the shared experiment. Ultralytics commercial licensing is explicitly **not assumed acceptable**.

## Screened field

| Candidate | Class route | CPU path | MPS / RTX 3060 route | Screen outcome |
|---|---|---|---|---|
| Custom YOLO26n (`yolo26n.pt` → two-class `best.pt`) | Supervised two-class head; fine-tuning required | Native PyTorch CPU; ONNX/OpenVINO export | PyTorch MPS/CoreML and CUDA/TensorRT routes; all must be measured on target machines | **Primary, conditional** |
| Grounding DINO Tiny (`IDEA-Research/grounding-dino-tiny`) | Open-set `(image, text)` detection; no initial fine-tune required | Official upstream CPU-only mode; Transformers defaults can run on CPU | CUDA example is official; MPS is only a generic Transformers/PyTorch route and needs a model-specific smoke | **Reserve** |
| YOLOv8s-WorldV2 (`yolov8s-worldv2.pt`) | Open-vocabulary custom prompts, train/predict/export | Local Ultralytics runtime | Same family-level device routes as Ultralytics | **Cut:** official current docs position YOLOE as the successor/migration target; keeping both would spend the experiment on near-duplicate stacks rather than an independent reserve. |
| Stock YOLO26n (`yolo26n.pt`) without fine-tuning | COCO fixed classes: generic `truck`, no `dump truck`, no `excavator` | Strong CPU/export path | MPS/CUDA routes | **Cut as-is:** cannot satisfy the class contract. It is admitted only after a two-class custom fine-tune. |
| RT-DETR-L (`rtdetr-l.pt`) | COCO-pretrained fixed classes; custom training supported | A CPU execution route exists through the Ultralytics/PyTorch stack | Official positioning and quoted speed evidence are CUDA/TensorRT-centric | **Cut:** needs construction-class fine-tuning and is a large model; no admission advantage over the smaller prompted candidates. |
| TorchVision Faster R-CNN / SSDLite COCO weights | Fixed COCO categories; replace/train head for custom classes | Mature PyTorch CPU path | Framework device routes exist | **Cut:** exact required classes need fine-tuning; valuable only as a later supervised control. |
| OWLv2 | Open-vocabulary transformer | Plausible local PyTorch path | Framework-dependent | **Cut for this round:** no current primary-source, hardware-comparable laptop evidence or decisive reproducibility advantage was found within budget over Grounding DINO Tiny. This is a budgeted non-selection, not a claim that OWLv2 is incapable. |

## Claims table

| Claim | Source URL | Publisher | Pub/update date | Accessed | Confidence | Claim class |
|---|---|---|---|---|---|---|
| YOLO26n is the smallest current YOLO26 detector (2.4 M fused parameters, 5.5 B FLOPs at 640), supports train/predict/export, and has CPU ONNX, T4 TensorRT, CoreML and other export routes. Its published 38.9 ms CPU number is on an Intel Xeon, not an ordinary laptop. | https://docs.ultralytics.com/models/yolo26/ | Ultralytics | 2026-01 family; live docs | 2026-09-22 | high | version / compatibility / performance |
| The COCO label set used by the stock checkpoint has 80 classes and includes `truck`; the published list contains neither `excavator` nor `dump truck`. A generic truck prediction cannot establish the required dump-truck class. | https://docs.ultralytics.com/datasets/detect/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | class support |
| First-party fine-tuning starts from `YOLO('yolo26n.pt')` and a custom dataset YAML; official guidance calls datasets under 1,000 images “small” and suggests gentler augmentation, but does not promise a minimum sufficient sample count. | https://docs.ultralytics.com/guides/yolo26-training-recipe/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | fine-tuning / dataset need |
| YOLOE accepts text/visual prompts and a prompt-free vocabulary; the current family includes `yoloe-26n-seg.pt`, and released checkpoints support predict/export. | https://docs.ultralytics.com/models/yoloe/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | version / class support |
| YOLOE text prompting can name categories never seen as fixed labels; prompts can be baked into weights and exported to ONNX, OpenVINO, TensorRT or CoreML, after which classes are static. | https://docs.ultralytics.com/models/yoloe/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | interoperability / structured output |
| YOLOE-26 text prompting performs a first-use GitHub install of `ultralytics/CLIP` and downloads `mobileclip2_b.ts` (~254 MB); both require network unless pre-staged. | https://docs.ultralytics.com/models/yoloe/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | installation / network |
| The current stable Ultralytics release at the access date is `8.4.158`, released 2026-09-21 at commit `ead936a`. | https://github.com/ultralytics/ultralytics/releases | Ultralytics | 2026-09-21 | 2026-09-22 | high | version / revision |
| YOLO26 detection can be exported to ONNX and run locally; export accepts CPU, MPS or GPU selection and controls input size/precision/NMS. | https://docs.ultralytics.com/integrations/onnx/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | compatibility / CPU path |
| Ultralytics code/models are offered under AGPL-3.0 or a commercial Enterprise license; production/internal use that cannot meet AGPL terms requires commercial review. | https://docs.ultralytics.com/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | license / cost |
| The YOLOE paper introduces open-prompt detection/segmentation and reports speed/accuracy comparisons on research hardware and benchmarks, not the target laptops. | https://arxiv.org/abs/2503.07465 | Wang et al. / arXiv | 2025-03-10 | 2026-09-22 | high | performance / architecture |
| Grounding DINO accepts `(image, text)` and outputs boxes with word-similarity scores; its official repository added CPU-only mode and publishes a Tiny checkpoint. | https://github.com/IDEA-Research/GroundingDINO | IDEA Research | CPU support announced 2023-03-27; live repo | 2026-09-22 | high | class support / CPU path |
| Transformers 5.8.1 provides `AutoModelForZeroShotObjectDetection` for `IDEA-Research/grounding-dino-tiny`, including a CUDA placement example and structured post-processing path. | https://huggingface.co/docs/transformers/v5.8.1/model_doc/grounding-dino | Hugging Face | v5.8.1 docs, 2026 | 2026-09-22 | high | version / structured output / CUDA |
| The exact model revision `e08274d...` is Apache-2.0, exposes safetensors, and contains a 692 MB model file (1.38 GB repository snapshot). | https://huggingface.co/IDEA-Research/grounding-dino-tiny/tree/e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e | IDEA Research / Hugging Face | model updated 2024-05-12 | 2026-09-22 | high | revision / license / footprint |
| PyTorch provides an Apple MPS device, but Transformers warns that unsupported operations may require CPU fallback; this is framework capability, not proof that Grounding DINO is correct/fast on MPS. | https://docs.pytorch.org/docs/main/notes/mps.html and https://huggingface.co/docs/transformers/perf_train_special | PyTorch; Hugging Face | PyTorch updated 2026-09-09; HF live docs | 2026-09-22 | high for framework, medium for candidate implication | compatibility / Apple Silicon |
| An Ultralytics issue reports silent YOLO bounding-box corruption on MPS and was closed as not planned; the report is not sufficient to generalize to fine-tuned YOLO26n, but it makes CPU-vs-MPS geometry parity a mandatory smoke. | https://github.com/ultralytics/ultralytics/issues/23140 | Ultralytics issue tracker | 2026-01-07 | 2026-09-22 | medium | compatibility risk |
| RT-DETR-L is COCO-pretrained; current official examples emphasize T4/TensorRT performance and support custom training/export. | https://docs.ultralytics.com/models/rtdetr/ | Ultralytics | live docs, n.d. | 2026-09-22 | high | landscape / fine-tuning |
| TorchVision's official pretrained detection weights are COCO weights; its API exposes structured boxes/labels/scores and documents model sizes/GFLOPs. | https://docs.pytorch.org/vision/main/models | PyTorch | live docs, n.d. | 2026-09-22 | high | landscape / structured output |

## Candidate profile: primary — custom fine-tuned YOLO26n

### Exact pin and installation

- Package baseline: `ultralytics==8.4.158`; source release commit `ead936a`.
- Initialization weight: `yolo26n.pt`. Scored model: the exact two-class `best.pt` produced by the shared training run, identified by SHA-256 and accompanied by the dataset-manifest hash, split manifest, seed and training arguments.
- Class map: exactly `{0: excavator, 1: dump_truck}`. The stock COCO `truck` label is not aliased to `dump_truck`; doing so would collapse ordinary trucks and the required subtype.
- Reproducibility gate: generate platform-specific hash-locked environments for CPU/MPS and CUDA; record Python, PyTorch, torchvision, CUDA/cuDNN and export-runtime versions. Rebuild ONNX/CoreML/TensorRT artifacts from the pinned `best.pt`, hash each artifact, and pass a clean network-blocked inference test.

### Class support and fine-tuning

Fine-tuning is mandatory because stock COCO does not contain either exact target label. The official guidance offers a recipe but no evidence-backed minimum sufficient dataset. Use the following as an explicit **experiment planning floor, not a claimed accuracy guarantee**:

- annotation tranche: 500–1,000 diverse training/validation frames total, targeting at least 250 annotated object instances per class; include empty frames and hard negatives (ordinary road trucks, loaders, bulldozers, cranes), plus small, occluded, distant, night and adverse-weather examples;
- freeze an untouched test set before training; for each class, 100 independent positive frames gives a worst-case 95% binomial proportion margin of about ±9.8 percentage points, while 400 gives about ±4.9 points. Choose based on the decision tolerance, and add a substantial negative set to estimate false-positive rate;
- group splits by camera/site/time sequence, not random adjacent frames, to avoid leakage;
- train the first tranche and plot learning curves. If validation performance is still improving materially, acquire more labels rather than declaring the planning floor sufficient.

The “under 1,000 images” boundary comes from first-party guidance only as a small-dataset regime for hyperparameters; the instance/frame targets above are protocol assumptions that must be validated by learning curves.

### Runtime modes to measure

- Ordinary laptop: PyTorch CPU first, then ONNX or OpenVINO export. Both are measured; neither inherits the other's result. The official 38.9 ms CPU ONNX figure is Xeon-only context, not laptop evidence.
- Apple Silicon: native PyTorch `mps` and CoreML export are candidate modes. Run output-parity checks against CPU before latency scoring because the issue tracker contains a silent MPS box-coordinate report.
- Windows RTX 3060: PyTorch CUDA FP32 is the reference GPU mode; FP16 and TensorRT are optional additional measurements only after output parity. No official RTX 3060 latency was found.
- **Latency status:** unmeasured. Official T4/Xeon/benchmark claims are not hardware-comparable to the target laptops. Report cold start, warmed p50/p95 per frame, peak resident memory and failure rate on the exact shared image set.

### Output and evidence regions

YOLO26 returns classed boxes. The adapter must emit only the normalized enum. Boxes, backend class ID/string, raw score, model/artifact hash and preprocessing metadata go to an audit sidecar as evidence regions. Downstream rules cannot branch on native count, score or geometry.

Recommended adapter semantics for the shared experiment:

- `detected`: inference completed and the frozen backend-local detector decision reports at least one target-class detection.
- `not_detected_in_frame`: inference completed and reports none.
- `insufficient_data`: deterministic pre-inference input validation rejects the frame (decode failure, missing pixels, or a protocol-defined minimum-quality failure).
- `not_analyzed`: model/artifact/runtime failure, timeout, unsupported device, or missing pinned dependency.

The detector's score threshold remains frozen internal experiment configuration; it is not exposed as a portable field and cannot be consumed by product rules.

### Cost, network, privacy and demo risk

- No per-frame provider fee is inherent to local execution, but AGPL compliance or an Enterprise license may create material cost/obligation. Do not interpret “local” as “license-free.”
- Initial package/checkpoint retrieval needs network; scored inference should use staged, hashed artifacts and pass a network-blocked repeat.
- Images can remain local in the designed path; this is conditional on local file inputs, staged artifacts and an outbound-network audit, not a claim that the unmodified library is network-silent.
- Official code snippets make training and local inference straightforward. Demo risk is medium-high until a labeled tranche exists: annotation quality, split leakage, training variance, legal acceptability and unresolved target-hardware latency all precede a credible demo.

## Candidate profile: reserve — Grounding DINO Tiny

### Exact pin and installation

- Runtime baseline: `transformers==5.8.1` with separately pinned PyTorch/torchvision builds per CPU/MPS/CUDA platform.
- Model: `IDEA-Research/grounding-dino-tiny` at immutable revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`; prefer `model.safetensors`, record SHA-256, and forbid floating `main` downloads in scored runs.
- Produce hash-locked platform environments and stage the complete model snapshot. A clean network-blocked inference is mandatory. The upstream model snapshot is large enough that disk/download/startup behavior must be measured, not assumed.

### Class support and fine-tuning

The official model is open-set and accepts free-text prompts, so `excavator` and `dump truck` do not require an initial custom head or fine-tune. As with YOLOE, this is class-addressability, not proven construction-domain accuracy. Fine-tuning is not required for experiment admission and was not qualified as a reproducible rapid-MVP path in this round; if zero-shot thresholds fail, reassess the current Transformers training path separately rather than improvising against the older upstream repository.

### Runtime modes to measure

- Ordinary laptop: CPU is explicitly supported by the official repository and is the admission mode.
- Windows RTX 3060: official Transformers examples support CUDA placement. Measure FP32 first; optional mixed precision follows parity.
- Apple Silicon: Transformers/PyTorch provide MPS generally, but no model-specific official compatibility or performance result was found. Run a small correctness smoke with CPU fallback enabled; if unsupported ops, numeric divergence or instability appears, record MPS as unavailable and retain Apple CPU mode.
- **Latency status:** unmeasured. No primary, hardware-comparable ordinary-laptop or RTX 3060 measurement was found. The 692 MB weights and transformer architecture make latency/memory a decisive benchmark, not an inference from model reputation.

### Output and evidence regions

Grounding DINO produces text-linked boxes/scores and Transformers exposes a structured zero-shot object-detection result. Apply the same normalized enum adapter and evidence-sidecar separation as the primary. Geometry is useful for human audit/overlays, but cannot enter portable rules.

### Cost, network, privacy and demo risk

- The pinned model card is Apache-2.0, avoiding the primary's copyleft/commercial-license branch; retain notices and have counsel confirm weight/data obligations for the intended use.
- Local inference has no per-frame provider fee. The model snapshot must be downloaded initially; scored operation should use a staged, network-blocked snapshot.
- Images can stay local under the same conditional outbound-audit requirement.
- The official repository links a Hugging Face demo and CPU demo. Demo risk is medium-high: large artifacts, old/upstream native-extension installation complexity, no qualified laptop latency, and unverified model-specific MPS behavior. The Transformers route is preferred over compiling the older upstream extension.

## Rejected candidates and cut rationale

1. **Stock YOLO26n without fine-tuning:** attractive CPU/export baseline, but COCO provides only generic `truck` and no `excavator`; it becomes the primary candidate only after the specified two-class fine-tune.
2. **YOLOE-26n / YOLOv8s-WorldV2:** technically attractive zero-shot alternatives, but the requested comparison needs an independent supervised YOLO branch and a Hugging Face-hosted zero-shot branch. YOLOE is also subject to the same Ultralytics AGPL/Enterprise licensing branch and has dynamic first-use text-encoder installation/download. It is retained only as a later ablation.
3. **RT-DETR-L/X:** official pretrained weights are COCO-oriented and large; quoted speed is T4/TensorRT, not an ordinary laptop. It adds fine-tuning cost without a compensating admission benefit.
4. **TorchVision Faster R-CNN/SSDLite:** clean and mature local baseline, but the official weights are COCO and exact construction classes need training. SSDLite may be useful as a later tiny supervised control, not the first rapid detector.
5. **OWLv2:** conceptually credible open-vocabulary alternative, but current official-source verification within this round did not establish a stronger pin/install/device/latency story than Grounding DINO Tiny. It remains a lead if either admitted candidate fails installation or license gates.
6. **SAM-family segmentation-first models:** not advanced because the decision is binary frame detection with evidence regions, and no source found a CPU-laptop advantage over the admitted purpose-built detectors.

## Contradictions and gaps

- **"Real-time" versus target hardware:** YOLOE papers/docs report benchmark advantages, but not on the specified ordinary laptops, Apple Silicon configuration or RTX 3060. All target latency is unknown until measured.
- **MPS availability versus correctness:** PyTorch and Transformers document MPS, but model support is operation-specific. An Ultralytics issue reports silent coordinate corruption for a YOLO model, while no official fine-tuned-YOLO26n-specific confirmation was found. Treat MPS as experimental and compare evidence regions to CPU.
- **Published CPU speed versus the actual primary:** the 38.9 ms figure is for the stock YOLO26n COCO model on an Intel Xeon. Fine-tuned artifact, preprocessing, laptop CPU and runtime differ; benchmark required.
- **Open-source label versus deployment obligations:** Ultralytics calls AGPL-3.0 open source and also offers Enterprise licensing for proprietary/internal production. Experiment use may be acceptable, but production suitability is a legal/product decision, not established here.
- **Supervised specificity versus data cost:** the YOLO branch can learn exactly two labels, but no source proves the proposed planning floor sufficient. The HF branch addresses both phrases immediately, but no source establishes its precision/recall on the target construction imagery.
- **Fine-tuning asymmetry:** YOLO26 has a current first-party fine-tuning recipe. A current, reproducible Grounding DINO Tiny fine-tune workflow was not validated in this source budget; reserve admission is zero-shot only.

## Leads for the shared experiment

1. Freeze one exact corpus and a class-balanced truth set with hard negatives; keep the same decoded pixels and resize policy across engines.
2. Pre-register the internal detector thresholds and prompt strings. Score binary class-wise precision/recall/F1 and abstention/failure separately; do not optimize on the test split.
3. Measure each mode independently: CPU is mandatory; Apple CPU, MPS and CoreML are separate; Windows CPU and RTX 3060 CUDA/TensorRT are separate. Record cold/warm p50/p95, peak memory, artifact size, install time and network attempts.
4. Require deterministic input validation and the four-value normalized response. Store evidence regions only in a non-rule-driving audit sidecar.
5. Add a clean-room reproducibility gate: hash-locked dependencies, immutable model revisions/checkpoint hashes, empty cache, then a network-blocked rerun.
6. Run legal review of the primary before training spend or production-oriented interpretation. If Enterprise licensing is unavailable and AGPL obligations are unacceptable, the reserve becomes the experiment primary.
7. Keep the comparison honest: the YOLO model is supervised and may use only its training/validation split; Grounding DINO is zero-shot and may not tune prompts or thresholds on the untouched test set. Report annotation/training cost alongside accuracy and latency.

## Things searched but not found

- No primary-source latency measurement for either admitted model on an ordinary consumer laptop comparable to the target machines.
- No primary-source fine-tuned `yolo26n` latency on Apple Silicon MPS/CoreML or Windows RTX 3060.
- No official, model-specific statement that Grounding DINO Tiny is fully supported and numerically validated on MPS.
- No official lockfile for either exact experiment stack. Both require an experiment-owned, hash-locked environment.
- No official excavator/dump-truck benchmark for either exact candidate on construction imagery, and no evidence-backed minimum training-set size for the custom YOLO model.
- No source proving that the unmodified local runtimes make zero outbound network calls after initial download; this requires a blocked-network test.
- No current public fixed price for an Ultralytics Enterprise license; treat commercial cost as quote-required.
- No decisive current official evidence that OWLv2 offers a better CPU/MPS/RTX 3060 rapid-MVP path than Grounding DINO Tiny.

## Source register by round

**Round 1 (8 sources):** Ultralytics YOLO26 docs; Ultralytics COCO/dataset-format docs; Ultralytics YOLO26 training/fine-tuning docs; Ultralytics releases; Ultralytics licensing/docs home; Grounding DINO official repository; Transformers 5.8.1 Grounding DINO docs; Grounding DINO Tiny official model revision.

**Round 2 (8 sources):** Ultralytics ONNX/export docs; PyTorch MPS docs; Hugging Face Apple Silicon docs; Ultralytics MPS issue #23140; Ultralytics YOLOE docs; Ultralytics RT-DETR docs; TorchVision models docs; the original YOLOE paper (architecture context only).

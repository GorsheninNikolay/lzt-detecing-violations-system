---
title: 'Technical research: Open excavator and dump-truck annotated datasets for RF-DETR MVP'
type: technical
topic: 'Open excavator and dump-truck annotated datasets for RF-DETR MVP'
decision: 'Select an open, rights-clear dataset candidate or retain no-training MVP posture.'
source: native-web-research
status: complete
preset: standard
validation: normal
created: '2026-09-22'
updated: '2026-09-22'
---

# Technical research: Open excavator and dump-truck annotated datasets for RF-DETR MVP

## Executive summary

**Do not make RF-DETR fine-tuning a prerequisite for the Rapid MVP.** Public construction datasets with the strongest direct excavator/dump-truck fit—CMOT and AIDCON—are explicitly non-commercial/research-only, so they cannot support a closed commercial training corpus without a written grant. [1][2]

The fastest *conditional* bootstrap is the fixed `keremberke/excavator-detector` mirror: it declares CC BY 4.0, has COCO boxes and separate excavator/dump-truck labels. The cited cards do not provide a sufficiently detailed raw-image provenance record for this project's risk policy, so commercial use remains pending provenance review and, preferably, written confirmation from the upstream rightsholder. [3][4]

Keep Grounding DINO as the no-training path. If RF-DETR must be demonstrated, use an isolated, clearly research-only CMOT/AIDCON experiment or the conditional CC-BY bootstrap after the rights gate; neither result proves deployment suitability on the target site camera.

## Candidate evidence

| Candidate | Exact class/annotation fit | Licence and commercial posture | Verdict |
|---|---|---|---|
| `keremberke/excavator-detector` | 2,656 images; COCO boxes; `excavators`, `dump truck`, `wheel loader`; train/valid/test 2,245/267/144. [3] | Declared CC BY 4.0; upstream Roboflow project does not establish raw-image authority or independent QA. [4] | **Conditional bootstrap.** Pin exact revision/hash; seek written grant before commercial training. |
| CMOT | 100 videos, 77k+ annotated frames, 155k instances; explicit dump-truck/excavator classes; MOT-style bounding boxes and official splits. [1][5] | CC BY-NC 4.0. | **Research-only.** Strong technical validation source, excluded from closed-MVP corpus without permission. |
| AIDCON | 2,155 UAV images, 9,563 machine instances, explicit dump truck/excavator; COCO-style `bbox` and segmentation. [2][6] | Research-only CC BY-NC 4.0. | **Research-only.** Request access for a separate experiment, not shipped weights. |
| Liebherr Product | 15k+ images, excavators and articulated dump trucks; labels are generated/pseudo-labelled. [7] | Gated non-commercial research agreement. | **Not MVP training source.** Potential later augmentation only with a new grant and QA. |
| SynDAB | CC BY 4.0 synthetic dataset with detection/segmentation data. [8] | Commercially compatible on declared licence, subject to attribution and asset-licence verification. | **Synthetic supplement only.** Excavator-viewpoint/barrel focus does not train the required two-class scene detector. |

## Technical integration and quality constraints

- Convert only a pinned source revision to a dedicated RF-DETR training manifest. Map labels exactly to `excavator` and `dump_truck`; retain other machinery as explicit negative/ignore policy rather than silently merging it.
- Split by source/video/site before any randomisation. CMOT's neighbouring frames are correlated, so frame-random splits leak scene information and overstate quality. [1][5]
- Manually QA 100 boxes per source before training, including boom/bucket extent, occlusion, raised dump beds, and target-view resemblance. The public-source dataset is not evidence of target-camera accuracy.
- Keep the held-out 11-image MVP evaluation set outside every training/validation dataset. It is a product-readiness test, not a corpus for tuning.

## Exclusions and contrary evidence

- ACID has relevant classes and rich annotations, but its publisher states both CC BY information and a separate no-commercial restriction over mixed Internet-sourced imagery. Treat the explicit restrictive statement as controlling unless written permission resolves it. [9]
- EXC Video is CC BY-NC-SA and therefore unsuitable for commercial training/deployment. [10]
- Open Images V7 is large and professionally annotated, but the cited compatible box taxonomy contains generic `Truck`, not `Excavator` or `Dump Truck`; image-level concepts do not solve two-class object detection. [11][12]
- xView and aerial-only datasets are both licensing- and viewpoint-mismatched for a ground-camera MVP. [13]
- The organizer-linked Roboflow `jejung/construction-machinery-tbosw` card is object detection and declares CC BY 4.0, but has only 78 images and its 24 published classes include `excavator-crane` and `smalldigger`, not the required exact `excavator` and `dump truck`. Its missing description/provenance makes it unsuitable as the two-class corpus. [14]

## Recommendations

1. **MVP now:** retain Grounding DINO as the no-training local path. Confidence: high; it avoids the unresolved corpus-rights gate.
2. **Parallel rights gate:** contact the `excavator-detector` upstream creator/rightsholder to document provenance and, preferably, obtain a written grant covering commercial model training, deployment, and derived weights; only then pin the mirror revision, attribution, source manifest, and 100-box QA. Confidence: medium because a dataset-card declaration is not chain-of-title proof.
3. **Research-only benchmark:** request CMOT/AIDCON under their stated terms and run a video-separated, non-shipped comparison. Project policy excludes their data and any weights trained from them from the closed-MVP artifact until a new commercial grant is obtained. Confidence: high for the restrictive data terms; the weight boundary is a conservative project policy.
4. **Architecture consumption:** revise the RF-DETR candidate from “primary” to “conditional on an approved corpus”; this does not select a model winner. The local no-training reserve stays viable.

## Open questions

- Will the upstream author/rightsholder of the CC-BY excavator dataset give a commercial ML/derived-weights grant?
- What are the target camera viewpoint, geography, lighting, and image-rights constraints? Without them, public-data transfer quality is unknown.
- Does the actual product need closed commercial deployment, or can research-only data remain confined to a non-shipped prototype experiment?
- If no rights-clear corpus arrives in time, should RF-DETR be removed from the MVP evaluation campaign rather than merely marked conditional?

## Source appendix

| Ref | Claim/finding supported | Publisher | Pub date | Accessed | Confidence |
|---|---|---|---|---|---|
| [1] | CMOT scope, classes, counts, CC BY-NC | [XZ-YAN / CMOT-Dataset](https://github.com/XZ-YAN/CMOT-Dataset) | not stated | 2026-09-22 | High |
| [2] | AIDCON access, classes, counts, research-only licence | [AI2LAB AIDCON](https://www.ai2lab.org/aidcon/) | not stated | 2026-09-22 | High |
| [3] | Excavator Detector counts, split, COCO boxes, declared CC BY | [keremberke dataset card](https://huggingface.co/datasets/keremberke/excavator-detector/blob/main/README.md) | not stated | 2026-09-22 | Medium |
| [4] | Upstream project/taxonomy/version context | [Mohamed Sabek Roboflow card](https://universe.roboflow.com/mohamed-sabek-6zmr6/excavators-cwlh0) | 2022 | 2026-09-22 | Medium |
| [5] | CMOT bbox schema and class IDs | [CMOT official visualizer](https://github.com/XZ-YAN/CMOT-Dataset/blob/main/CMOT_annotations_visualizer.py) | not stated | 2026-09-22 | High |
| [6] | AIDCON COCO annotation shape and split | [AIDCON paper](https://www.mdpi.com/2072-4292/16/17/3295) | 2024 | 2026-09-22 | High |
| [7] | Liebherr Product scope and gated non-commercial agreement | [Liebherr Product card](https://huggingface.co/datasets/Moonxc/Liebherr_Product) | 2024 | 2026-09-22 | High |
| [8] | SynDAB declared CC BY data and scope | [SynDAB dataset](https://darus.uni-stuttgart.de/dataset.xhtml?persistentId=doi:10.18419/darus-3758) | 2024-01-23 | 2026-09-22 | High |
| [9] | ACID mixed provenance and no-commercial restriction | [ACID dataset page](https://www.acidb.net/dataset) | 2025-08 | 2026-09-22 | High |
| [10] | EXC Video CC BY-NC-SA | [EXC Video card](https://huggingface.co/datasets/fuxi-robot/excavator-video) | 2025-07-23 | 2026-09-22 | High |
| [11] | Open Images V7 downloads and annotation scope | [Google Open Images V7](https://storage.googleapis.com/openimages/web/download_v7.html) | not stated | 2026-09-22 | High |
| [12] | Open Images compatible box taxonomy | [Ultralytics Open Images config](https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/datasets/open-images-v7.yaml) | live | 2026-09-22 | Medium |
| [13] | xView licence and overhead-data constraints | [xView rules](https://challenge.xviewdataset.org/rules) | live | 2026-09-22 | High |
| [14] | Organizer-linked Roboflow dataset size, task, licence, and published taxonomy | [construction machinery dataset card](https://universe.roboflow.com/jejung/construction-machinery-tbosw) | 2024-10 | 2026-09-22 | High |

## Staleness map

Re-check dataset cards, access gates, licences, and source-revision availability before downloading or training; the earliest refresh is **2026-10-22**. Obtain a fresh written grant immediately before any commercial training or deployment.

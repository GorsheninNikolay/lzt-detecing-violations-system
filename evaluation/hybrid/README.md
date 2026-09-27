# Hybrid control scenes and current quality limits

The organizer archive contains 100 original PNGs. `control-review-queue.json` selects 15 for review, without changing their bytes or assigning invented camera/site/time identities. `independent-visual-review.json` records a separate agent's inspection of 14 originals and 36 approximate boxes. Neither file is human-adjudicated ground truth. Unlisted equipment is not an exhaustive negative label.

Reproduce the selection:

```sh
python evaluation/hybrid/prepare.py --archive artifacts/dataset/Строительная_техника.zip --output output/hybrid-review/images
```

The extractor checks the archive and every image hash and refuses to overwrite different bytes. `draft-annotations.json` under the older expansion directory remains unchanged.

| Candidate | Useful evidence | Limits |
| --- | --- | --- |
| 15 | Cargo truck, partly visible excavator | Crane manipulator is unconfirmed |
| 23, 78 | Clear single excavator | A bucket pose does not prove working or idle |
| 24, 67 | Wheeled mobile crane, lifting setup | Movement/duration not established |
| 47, 48 | Several excavators, falling/transferred soil | Small/occluded machines require box review |
| 60 | Road roller on prepared soil | Roadwork is a hypothesis; active compaction unconfirmed |
| 61 | Excavators, compact loader, road-like area | Keep unsupported loader separate |
| 71 | Dump truck and excavators | No schedule or work rate evidence |
| 87 | Several machinery types | Piling rigs/tower cranes remain outside catalog |
| 97, 99, 100 | Mixer, excavators, concrete-related surroundings | Mixer presence does not establish pouring |
| 1 | Partial small excavator | Poor coverage for class absence |

## Acceptance matrix

The required matrix is excavation / concreting / roadwork × normal / grounded risk / ambiguous / unusable. Current independent candidates support observation and ambiguity checks. A synthetic blank image is appropriate for an unusable-input regression. An explicitly simulated plan can exercise HTTP binding and signal persistence, but does not establish an authentic site delay.

Authentic normal/risk labels for every scenario, reliable comparable time series, and confirmed idle cases are missing. Confident bulldozer and truck-mounted crane examples are missing in this selection. No class precision/recall, false-warning rate, or stage correctness is claimed as acceptance evidence: labels are partial and unadjudicated, and a zero from an unrun metric would be false evidence. Localization candidates are approximate, not reference-quality boxes. The quality endpoint remains blocked.

## Observed model errors and targeted next data

Both supplied checkpoints loaded and ran on 15 originals. Preserve these errors for retraining and evaluation, never move the same frames into both sets:

- Screenshot 60: APOCE produced five excavator detections on a roller scene; Kaggle predicted Trailer. Add manually reviewed rollers and soil-compaction scenes, with hard negatives for excavation machines.
- Screenshot 24: both models missed the visible mobile crane. Add wheeled mobile cranes with deployed supports, truncated booms, snow and lifting loads. Keep tower cranes and drilling rigs as separate negatives.
- Screenshot 99: APOCE returned no detections; Kaggle predicted Trailer and Mixer. Add multiple excavators and dump-truck loading scenes with overlap/occlusion. Review distinct physical machine boxes.
- Screenshot 15/87: several unsupported or confused classes. Preserve raw source classes and resolve truck, loader, trailer and crane distinctions manually.
- Kaggle checkpoint metadata records epoch 4 (fifth epoch), despite a configured 100-epoch training request. APOCE is an optimizer-stripped checkpoint (epoch -1), so that field does not prove training duration. Retain checkpoint hashes and original training metadata.

Before training, adjudicate every proposed object, scene, stage, activity and expected signal. Record reviewer/date and resolve disagreement separately. Obtain additional source scenes for the two missing classes and actual same-camera timed work/idle sequences. Split by verified site/camera/series before any fitting; unknown grouping cannot support a site-independent generalization claim. Keep organizer review scenes as a frozen diagnostic set once used to tune prompts or parameters, and acquire a separate acceptance set. Export approved labels through the existing eight-class YOLO/COCO workflow and train new checkpoints into a new output directory using `training/windows`; never replace user originals. Re-evaluate all required cases with zero false warnings before release.

## Costs and latency

`budget.json` records every paid verification reservation, actual returned token usage when available, and conservative unresolved exposure. Pricing source: https://aistudio.yandex.ru/ru/docs/ai-studio/pricing (checked 2026-09-27), RUB 0.3 / 1000 uncached input tokens and RUB 0.5 / 1000 output tokens. These are usage-based estimates, not a billing statement. A request with an unknown outcome retains its full upper reserve. The total authorized cap is RUB 1000.

`yolo-smoke-summary.json` contains measured local CPU times. Startup/import/cache time is separate from warm detector inference. This is a local hardware observation, not a server throughput guarantee. The current detector comparison is diagnostic and cannot qualify the model by itself.

> Исторические данные. Подготовка через DINO выведена из исполнения; текущий путь описан в [README](../../README.md).

# Eight-class annotation queue

`draft-annotations.json` covers all 100 organizer PNGs. It records archive/image hashes, dimensions, the pinned Grounding DINO Tiny model identity, adapter hash, and **unreviewed machine candidates**. These are not labels, training targets, or evaluation results. The archive does not establish site, camera, capture time, or sequence groups. The queue deliberately has no train/validation/held-out split.

Regenerate it offline with the verified model snapshot:

```sh
PYTHONPATH=backend uv run --project backend --extra test python scripts/prepare_expansion_annotations.py \
  --snapshot-dir /private/tmp/grounding-dino-tiny-e08274d
```

## Review protocol

1. Confirm image rights and provenance. Record the real site, camera, and series for each image. Images with unknown grouping may support demonstration or exploratory review but must not be split as if independent sites.
2. Correct or remove every equipment candidate. Draw missing instances, including multiple objects of one class. Distinguish cargo truck from dump truck, and mobile crane from truck-mounted crane. Record an `uncertain` or `unassessable` decision where the view does not support a class label.
3. Review the five scene features independently of equipment. Their boxes, where meaningful, and presence/absence need separate human decisions. Do not infer work in progress solely from a finished structure.
4. Review acceptable stage hypotheses per frame/series, including ambiguity. For each scenario, create positive, negative, ambiguous, and unusable series cases with a specific zone plan and expected signal state.
5. Keep reviewed labels in a separate, reviewer-attributed file. Do not overwrite `draft-annotations.json` or use its `equipment_candidates`, `scene_candidates`, or `stage_candidates` as ground truth.
6. Split by verified site/camera/series group. Preserve the existing two-class held-out set. Report per-class precision/recall, box localization, stage agreement, false signal rate, and CPU latency. Only then run a new profile admission.

In the current draft, the model produced 97 equipment candidates across 100 images: 42 concrete mixer truck, 38 excavator, 15 bulldozer, and 2 road roller; it produced **no** candidates for the other four classes. These are model outputs, not the archive's class distribution. On `Screenshot_87.png`, visual review found likely class confusion, so the draft cannot support readiness claims.

One organizer-linked [GitHub dataset](https://github.com/miniexcav/Construction-Machines-Images-Dataset) contains 223 excavator images with YOLO labels, but its maintainers describe web-scraped images and educational/research use with possible third-party copyrights. It cannot fill the eight-class, commercial-rights, or site-disjoint gates by itself.

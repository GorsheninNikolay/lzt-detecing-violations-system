# Zone-plan and equipment expansion

## User goal

A site manager selects a project and zone, records a versioned work plan, uploads JPEG or PNG frames with capture times, inspects located equipment and stage hypotheses, and handles evidence-bound signals. A single frame belongs to one declared zone. Parallel operations in that zone remain valid.

## Contract

- Import all 377 rows of the supplied XLSX as a source-bound catalog. Preserve row order, blank and duplicate codes/titles, raw cell values, formats, cell coordinates, nine applicability columns, and file SHA-256. This catalog does not provide dates or required equipment.
- A plan revision is an immutable full snapshot of a zone's operations. Each operation names a catalog row, timezone-aware start/end, completion state, optional stage, and user-confirmed expected, allowed, and explicitly excluded equipment. Optimistic revision numbers prevent silent overwrite.
- A run binds project, zone, exact plan revision, and every frame's capture time before input publication. Revisions and original image bytes remain available to old runs and retries.
- The expanded local observer has eight distinct classes: dump truck, excavator, road roller, truck-mounted crane, concrete mixer truck, bulldozer, cargo truck, and mobile crane. Other catalog equipment is marked unsupported. A new profile revision and independently labeled evaluation are required before this observer may be advertised as admitted.
- Public object evidence contains class, model score, oriented-image normalized `xyxy` box, frame ID, and invocation ID. Multiple objects of one class remain distinct. The cloud profile retains presence-only evidence without invented boxes.
- Scene features are excavation/trench, formwork, reinforcement, concrete surface, and road base/surface. A stage hypothesis requires equipment and a relevant scene feature in the same frame. Excavation, concreting, and roadwork are the initial hypothesis set; ambiguity or absent corroboration remains explicit. Human confirmation is separate from model output and does not edit the plan.
- Signals distinguish expected equipment missing across at least three assessable same-zone frames, explicitly excluded equipment across every concurrent active operation, confirmed stage/plan disagreement, elapsed plan date with completion unconfirmed, and insufficient observations. Signals bind their run or calendar basis, zone, plan revision, work entry where applicable, rule revision, supporting frames, and recommendation. Reprocessing does not duplicate a signal; a later quiet run does not close one.
- Signal state is new, in progress, or closed with comment. Calendar state is never presented as a photograph-proven delay.

## Release evidence

An eight-class profile needs rights-cleared, site/series-disjoint labels for every class, boxes, scene features, acceptable stage hypotheses, and expected signals. Report classification, localization, false-signal rate, and CPU latency separately from the old two-class held-out set. Test positive, negative, ambiguous, and unusable cases for each of the three scenarios; missing camera view or unsupported equipment must not become a missing-equipment warning.

The demo must replay an original organizer PNG through image storage, boxes, stage hypothesis, plan comparison, and an explainable signal, with the exact profile and rule revisions visible. A separate jury-access check, target-computer launch check, presentation, accompanying document, camera-placement guidance, and model/data limitations remain release artifacts. Camera guidance covers the work zone and entry, overlapping views, indoor viewpoints, and synchronized capture times.

External schedule import, notifications outside the app, continuous video, automatic zone segmentation, and automatic completion percentage remain outside this increment.

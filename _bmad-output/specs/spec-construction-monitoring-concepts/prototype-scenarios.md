# Prototype Scenarios

## Result states

| State | Meaning | Permitted consequence |
|---|---|---|
| `detected` | At least one instance of the requested class is observed in the usable input under analysis. | Use the observation as evidence for a rule evaluation. |
| `not detected in frame` | The class is in scope and the input is usable, but no instance is observed in that frame. | Report only in-frame non-detection; do not infer site-wide absence. |
| `insufficient data` | The requested analysis is in scope, but image quality, visibility, coverage, or series evidence is inadequate for the requested conclusion. | Withhold the rule warning and explain why the evidence is insufficient. |
| `not analyzed` | The work or equipment class is outside MVP scope or is not informative for the selected rule. | Make no observation or deviation claim. |

## Excavation rule

- Rule structure: work type → observable process → equipment classified as continuously expected, periodically expected, or not informative.
- Scenario: excavation-pit soil removal with haulage from one controlled loading area.
- Expectation: an excavator is continuously expected; a dump truck is periodically expected.
- Provenance: demonstration rule unless replaced by an identified project, normative, methodological, or expert source.
- Single-image behavior: report the excavator and dump-truck observation states; do not issue a delay warning from one-frame absence alone.
- Series behavior: when a usable series persistently does not detect a dump truck, ask the manager to check a possible soil-haulage delay. Keep this warning separate from the observations and do not label it a violation.

## Demonstration cases

| Case | Input | Expected result |
|---|---|---|
| Positive | A usable series from the controlled loading area that observes both an excavator and a dump truck consistently with the rule. | Show the supporting observations and rule; do not issue a haulage-delay warning. |
| Negative | A usable series from the same controlled loading area that observes the excavator but persistently does not detect a dump truck. | Show the supporting images, period, rule and provenance; ask the manager to check a possible haulage delay. |

## PolicyProfile

One immutable `PolicyProfile` revision governs the decisions that determine whether evidence and evaluation results are acceptable. Every analysis run records the revision and its complete applied snapshot; changing any value creates a new revision without reinterpreting prior runs.

| Policy area | Initial MVP values | Decision effect |
|---|---|---|
| Frame usability | The file has a supported image format and decodes successfully. There is no fixed resolution, visibility-percentage, or object-size threshold. | An accepted image the observer cannot assess yields `insufficient data`; it is not rejected for subjective quality and cannot yield `not detected in frame`. |
| Series sufficiency | At least three usable images from one controlled area, ordered by explicit upload ordinal. Cadence and duration are recorded when available but are not required. Persistent dump-truck non-detection means no dump truck in all three images while an excavator is observed somewhere in the series. | Fewer than three usable images yield `insufficient data`. Only the defined persistent non-detection pattern may produce the periodic-equipment check request. |
| Prototype quality | Positive, negative, insufficient-data, and out-of-scope cases are mandatory; the evaluation set permits zero false warnings. Misses, false detections, and repeated-run disagreements are recorded without blocking numeric thresholds. | A missing mandatory case, incorrect case outcome, or false warning fails readiness. Recorded baseline metrics inform a later policy revision rather than blocking this MVP. |

This initial profile deliberately avoids unsupported quality thresholds. Numeric gates may be introduced only in a later revision justified by evaluation evidence.

## Prototype readiness criteria

- The evaluation set contains 10–15 images with manual excavator and dump-truck labels and documented test-specific sufficiency conditions.
- The evaluation binds the immutable initial `PolicyProfile` revision, and every evaluated run records the same complete applied snapshot.
- Every supported image that decodes successfully is accepted for analysis; if the observer cannot assess it, the result is `insufficient data` rather than an upload failure or `not detected in frame`.
- A periodic-equipment check request requires at least three usable same-area images in explicit upload order, no dump truck in all three, and an excavator observed somewhere in the series; cadence and duration do not gate the initial MVP.
- Every requested class result uses one state from the result-state table and points to the evaluated input.
- Single-image non-detection never produces a site-wide absence claim or a delay warning by itself.
- The positive case completes with the expected observations and no haulage-delay warning.
- The negative case completes with the expected observations and the specified check request.
- Every warning exposes its supporting observations, observation period, rule, provenance, recommendation, and uncertainty.
- A reviewer can identify the reason for each warning and the recommended check; the evaluation records whether the warning was understood.
- The evaluation produces zero false warnings across the evaluation set.
- Misses, false detections, and repeated-run disagreements are recorded separately as baseline evidence rather than hidden by aggregate wording; they do not have blocking numeric thresholds in the initial MVP.
- At least one inadequate-evidence fixture yields `insufficient data`, and at least one out-of-scope fixture yields `not analyzed`, without a warning.
- No output declares a legal or contractual violation or initiates management action.

The execution approach is selected only after comparing a ready local detector and one cloud multimodal model on the same evaluation set; that selection is not part of MVP readiness.

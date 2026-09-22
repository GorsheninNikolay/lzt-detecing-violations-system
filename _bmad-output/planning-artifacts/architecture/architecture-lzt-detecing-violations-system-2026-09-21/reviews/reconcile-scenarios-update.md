# Reconciliation Update — Prototype Scenarios vs Architecture Spine

## Verdict

**Mostly aligned, but not yet exact enough to call fully reconciled.** The updated spine now carries the scenario's four-state observation contract, initial `PolicyProfile` semantics, warning eligibility, mandatory readiness fixtures, evidence fields, and reproducible provider comparison. No paradigm or structural rewrite is needed. Four bounded ambiguities remain; the first can produce a direct acceptance/readiness contradiction, while the others can make independently built units disagree at edge cases.

## Findings

### F1 — High: upload admission can contradict the initial frame-usability policy

**Scenario evidence:** `prototype-scenarios.md:34,44` says the initial profile accepts every supported image that decodes successfully, has no fixed resolution threshold, and maps observer inability to `insufficient data` rather than upload failure.

**Spine evidence:** AD-8 repeats the supported-format-plus-decode rule (`ARCHITECTURE-SPINE.md:80-84`), but AD-16 requires media-type and size limits, and AD-28 requires byte-size and pixel-dimension validation before a run is created (`:128-132,188-192`).

**Mismatch:** A supported, decodable image can be rejected because of byte or pixel bounds, while the source readiness criterion says every such image is accepted for analysis. The spine does not distinguish security/resource admission from domain frame usability or constrain the readiness set to the admitted envelope.

**Required reconciliation:** Define an explicit pre-analysis admission envelope and say that the PolicyProfile applies only after admission, then update the inherited readiness wording accordingly; or remove admission criteria that go beyond supported format and successful decode. If pixel dimensions are merely parsed rather than thresholded, say so. This is the only finding that requires reconciling the upstream wording as well as the spine.

### F2 — Medium: `at least three` images conflicts with `all three` in longer series

**Scenario evidence:** `prototype-scenarios.md:35,45` defines a sufficient series as **at least three** usable same-area images, but defines persistent non-detection as no dump truck in **all three** images.

**Spine evidence:** AD-8 preserves the same combination (`ARCHITECTURE-SPINE.md:80-84`), while AD-21 sharpens the warning rule to no dump truck in “all three initial-profile images” (`:152-156`). AD-31 fixes canonical ordering but does not select a three-image window (`:200-204`).

**Mismatch:** For four or more usable images, builders can reasonably choose incompatible behavior: require absence across the entire series, inspect only the first three, inspect any consecutive three, or reject the series as outside the profile. This changes warning eligibility.

**Required reconciliation:** Bind one rule for longer series. The least surprising interpretation is: a series is sufficient at three or more usable images, and persistent non-detection requires no dump truck in every usable image in the evaluated series, with an excavator observed at least once. If the intent is a fixed three-image window, define exactly which canonical ordinals form it.

### F3 — Medium: `not_informative` is not explicitly mapped to `not_analyzed`

**Scenario evidence:** `prototype-scenarios.md:10` gives `not analyzed` two exact causes: the class is outside MVP scope **or is not informative for the selected rule**; neither observation nor deviation claim is permitted.

**Spine evidence:** AD-12 allows a rule to classify equipment as `not_informative` and says unsupported classes are outside analysis (`ARCHITECTURE-SPINE.md:104-108`). AD-22 explicitly maps unsupported classes to `not_analyzed` (`:158-162`). AD-20 lists `not_analyzed` and suppresses warnings, but does not bind the `not_informative` mapping (`:146-150`).

**Mismatch:** One implementation may skip observation and return `not_analyzed` for a supported-but-not-informative class, while another may still invoke the observer and return `detected` or `not_detected_in_frame`. Both can claim compliance with the current AD wording.

**Required reconciliation:** State that a requested class marked `not_informative` by the bound rule revision yields `not_analyzed`, does not invoke observation for rule purposes, and cannot contribute an observation or deviation claim. Provider-native incidental detections may remain attributed secondary evidence only if they are not projected as the requested-class result.

### F4 — Medium: the model-comparison boundary is semantically aligned but not fully bound

**Scenario evidence:** `prototype-scenarios.md:57` requires comparison of **one ready local detector and one cloud multimodal model** on the same evaluation set before selecting the execution approach, and explicitly says that selection is not part of MVP readiness.

**Spine evidence:** AD-7 compares “each ready provider” in distinct runs over the same evaluation-set and policy identities and fixes one non-selectable default in the jury flow (`ARCHITECTURE-SPINE.md:74-78`). AD-30 locks the comparison identities and accounts for failures (`:194-198`). Deferred postpones provider selection until comparative evidence exists (`:333-337`).

**Mismatch:** The spine does not explicitly require the comparison batch to contain exactly the local/cloud pair, nor does an AD explicitly state that provider selection is excluded from the readiness verdict. “Each ready provider” permits a one-provider batch if the other adapter is not declared ready, and an implementation could fold the post-comparison selection into readiness despite the source boundary.

**Required reconciliation:** Amend AD-7 or AD-24 to require one ready local detector and one ready cloud multimodal adapter in the comparison batch, define readiness-for-comparison separately from prototype readiness, and state that the selection decision is a post-readiness/deployment choice rather than a readiness criterion. Retain distinct runs, the shared locked identities, failure accounting, and the non-selectable jury default.

## Confirmed alignments

| Scenario contract | Spine coverage | Assessment |
| --- | --- | --- |
| Closed four-state result vocabulary and input reference | AD-20, AD-33 | Aligned; snake_case codes are a consistent transport representation of the spaced scenario labels. |
| Observer inability yields `insufficient_data`; insufficiency suppresses warnings | AD-8, AD-20, AD-21, AD-26 | Aligned after admission; F1 remains at the pre-run boundary. |
| Single-frame non-detection is not site-wide absence and cannot warn | AD-20, AD-21 | Aligned. |
| Initial series minimum, explicit upload order, cadence/duration non-gating | AD-8, AD-21, AD-31 | Aligned for exactly three inputs; F2 remains for longer series. |
| Positive and negative cases plus inadequate/out-of-scope fixtures | AD-8, AD-24 | Aligned. |
| Zero false warnings is blocking; misses, false detections, and disagreements are non-blocking baselines | AD-8, AD-24 | Aligned. |
| Warning evidence, uncertainty, provenance, reason, and human recommendation | AD-21, conventions | Aligned; spine additionally binds area and stable reason code. |
| No legal/contractual violation claim or automatic action | AD-21 | Aligned. |
| Provider isolation, no fusion/fallback, reproducible comparison identities | AD-7, AD-18, AD-30, AD-33 | Aligned, subject to F4's candidate and readiness boundary. |

## Reconciliation priority

1. Resolve admission versus “every decodable supported image” (F1), because it can make a readiness test impossible to interpret.
2. Fix semantics for series longer than three images (F2), because this changes warning eligibility.
3. Bind `not_informative -> not_analyzed` (F3), because it closes the last result-state meaning gap.
4. Make the local/cloud pair and non-readiness selection boundary explicit (F4).

After those amendments, `prototype-scenarios.md` and the architecture spine would be mutually consistent on the requested result-state, initial-policy, readiness, and model-comparison boundaries.

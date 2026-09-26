# Hybrid delivery verification, 2026-09-27

Engineering disposition: **COMPLETED_WITH_GAPS**. Product/model quality: **BLOCKED**. The local prototype implements both YOLO checkpoints, photo-bearing DeepSeek reconciliation/assessment, frozen plans, activity evidence and atomic project signals. This report does not declare the project ready for final quality acceptance.

The machine-readable evidence is [HYBRID_VERIFICATION.json](HYBRID_VERIFICATION.json); the [control review pack](../evaluation/hybrid/README.md) documents source images, gaps and targeted next training data. All organizer originals, checkpoints, older profiles/results and existing application data were preserved. No remote server deployment was performed.

## Checked layers

| Layer | Actual evidence |
| --- | --- |
| Full backend | 300 passed, 1 historical archive-dependent skip, 0 failures |
| Full frontend | 203 passed, 0 failures |
| Frontend production build | Passed |
| Linux ARM64 CPU image | Final build and embedded profile/report hash verification passed |
| Real YOLO | Both original hashes/classes loaded; 15 organizer PNGs processed on local CPU, plus separate Linux CPU smoke |
| Real DeepSeek | Account/model/photo/strict JSON access confirmed; actual frame and assessment requests retained |
| Real HTTP | Successful normal/photo/blank analyses; saved stage mismatch under a clearly simulated road plan; exact uploaded-image SHA readback |
| Repeat/status behavior | Successful quiet live repeat created no new signals, reused its insufficiency signal and retained the closed stage signal |
| Variable AI citations | Separate DB regression passed for two successful analyses with changed boxes/citations: same stage signal, same closed state, unchanged original basis |
| PDF rendering | Both final PDFs contain 12 pages; all 24 latest rendered pages were inspected without layout defects |
| Browser/GUI visual acceptance | NOT_RUN under the no-GUI instruction |
| Windows/CUDA training | NOT_RUN |
| Model quality acceptance | BLOCKED, not equivalent to green structural tests |

The live repeat returned `risks=[]`; it is not evidence that the provider repeated an identical AI risk. Earlier development responses and prototype duplicate signals remain historical records. Strict rejection preserved several invalid outputs without successful projections; no automatic cloud replay was enabled. These failures informed the final response constraints and stable stage-signal identity.

Measured Linux CPU inference belongs to image `sha256:e1c0b75950db7e50b2e6430ef795b1582d07484a47ca221491ac5c0e4c367f6c`. The final image was rebuilt after request/publication fixes and checked against the current profile; inference was not repeated because detector code, weights and CPU dependencies did not change. [Container evidence](../evaluation/hybrid/container-smoke.json) retains both image identities separately.

## Runtime and evidence

Local demo: `http://127.0.0.1:58159`. The [machine-readable report](HYBRID_VERIFICATION.json) gives the project link and transient credential expiry. A separate `hybrid_demo_20260927` database and private bucket preserve the pre-existing application's data. The ordinary [runbook](HYBRID_PHOTO_SIGNALS.md) supports restarting the service with credentials supplied through environment variables; no runtime secret is committed.

[HTTP demonstration](../evaluation/hybrid/http-demonstration.json) identifies the successful runs and the explicitly simulated plan/time premise. [Run records](../evaluation/hybrid/results/) preserve all 14 HTTP attempts, including rejected output, source hash, raw detector results, schema/profile and observation links. [Artifact readback](../evaluation/hybrid/artifact-readback.json) confirms original image bytes through the API. Quality review candidates remain separate from model responses and approved training data.

The account/photo smoke and intermediate frame-contract smoke were separate diagnostic calls. Their token reservations are included in the final ledger, along with every application call. There were **31 paid verification requests**, an uncached usage-based estimate of **58.7845 RUB**, and **0 transport/usage-uncertain calls**. The authorized cap was 1000 RUB. Invalid model output still counts toward cost. This is not a verified billing statement. [Budget ledger](../evaluation/hybrid/budget.json) uses the [published pricing](https://aistudio.yandex.ru/ru/docs/ai-studio/pricing) checked for this run.

## Remaining acceptance work

The selection contains 15 queued images, an independent agent review of 14 and 36 approximate boxes covering six confident candidate classes. No image has been human-adjudicated for the expanded acceptance set. Bulldozer, truck-mounted crane, comparable timed idle sequences and the complete excavation/concrete/roadwork × normal/risk/ambiguous/unusable matrix remain missing. Partial candidate labels cannot justify class precision/recall, localization accuracy or a zero-false-warning claim; those measurements remain null.

Observed errors include a roller classified as excavators/Trailer, a missed mobile crane, and missed/poorly localized machines in loading scenes. DeepSeek recovered key classes but also showed output variability and unsupported suggestions that the server rejected. The [collection/review/retraining plan](../evaluation/hybrid/README.md) identifies specific scenes, hard negatives, class distinctions and separate acceptance data. Do not qualify the current model or announce final project completion until those gates pass.

# Hybrid photographs to site signals

The approved scope is [the frozen spec](../_bmad-output/implementation-artifacts/spec-hybrid-photo-signals.md). Technical checks and quality acceptance are separate. No remote deployment is part of this change.

## Reproduce locally

1. Keep the original case-sensitive files at `artifacts/Models/apoce.pt` and `artifacts/Models/kaggle.pt`. Do not rename or rewrite them. The committed `backend/app/data/yolo-manifest.json` records SHA-256, original labels, nullable class mapping, package pins and inference settings. APOCE `lifting-equipment`, piling machines and tower cranes are not automatically mapped to a crane catalog class.
2. Install the committed environment: `uv sync --project backend --extra test`. Linux uses locked CPU PyTorch wheels. Inference always requests `device=cpu`; the two models load once and share an inference lock.
3. Apply additive migrations with the application `DATABASE_URL` configured: `backend/.venv/bin/python -m alembic -c backend/alembic.ini upgrade head`. Existing runs, corrections and historical evidence remain unchanged. Downgrade refuses to erase evidence.
4. Set cloud credentials through the environment. Provision with `HYBRID_PHOTO_SIGNALS=1 backend/.venv/bin/evidence-profile`; retain the returned profile UUID as `OBSERVER_PROFILE_ID`. This creates configuration only and does not spend on cloud calls. The legacy profile is still supported when this flag is absent.
5. `make up` builds the local application. Compose mounts the weights read-only and preserves named database/S3 volumes. Missing, corrupt or wrong-class checkpoints prevent a bound hybrid runtime from becoming ready. Do not run `down --volumes`.
6. Select a project/zone, upload photos with reliable capture times and give cloud consent. A zone with a plan defaults to comparison; the selected revision is shown and the user can opt out. Later plan edits cannot change a submitted run.

A new run sends one photo-bearing reconciliation call per frame and one assessment call with the series photos. Raw detections, original classes, normalized oriented-image coordinates, confidence, checkpoint hashes and rejection reasons remain in `ai_evidence`. `result_projection.hybrid_frames` exposes reconciled observations and detector provenance. The UI can switch between reconciled, APOCE and Kaggle boxes. Activity/stage hypotheses retain source-frame navigation and work links.

## Publication boundaries

Every raw detection must receive an accepted/dismissed/unresolved disposition. A source detection cannot be assigned to two reconciled objects. Frame usability and class assessability are independent of whether equipment is detected. Uncertain identity, unassessable views and duplicate image hashes cannot create absence evidence.

Plan rules compare each frame time inclusively against every concurrent active operation. Missing-equipment rules require three independent assessable frames belonging to that operation; a concurrent operation allowing equipment suppresses the exclusion signal. Presence alone does not establish productive work. Possible idle requires independent timed frames, a comparable view, matching object observations and explicit non-work indicators, and remains a hypothesis for human checking.

The server validates current-frame observation references, usable evidence, activity grounds and work applicability against the frozen revision. Process/safety signals need a zone but may have no plan; plan risks require applicable work. Model and deterministic duplicate risks are reconciled. Signal basis includes frozen frames and plan. Fingerprints use stable source evidence, zone/revision/cause/work, never generated prose or a run ID. Signals and projection commit in one lease-fenced transaction. Later calm runs do not close existing signals; repeated evidence does not reopen a closed signal.

A reservation is committed before each cloud request. Timeouts, invalid responses, lost lease or process restart cannot trigger automatic paid replay. Invalid JSON/contract responses retain raw provider evidence and a rejection reason; no successful projection or signal is published.

## Verification and acceptance

Run `backend/.venv/bin/python -m pytest backend/tests` with a migrated isolated `TEST_DATABASE_URL`, distinct `DATABASE_URL`, private `TEST_S3_BUCKET` distinct from `S3_BUCKET`, and the S3 endpoint/credentials. Fixtures create and remove only their own temporary databases and buckets. Run `npm --prefix web test -- --run` and `npm --prefix web run build` for UI regression/build checks. GUI visual acceptance is not run.

The initial real CPU check loaded both checkpoints, but the independently inspected scenes exposed detector misses and false classes. Structural response validity does not establish correct object count, localization, activity or stage reasoning. Quality acceptance remains blocked until independently reviewed eight-class labels and excavation/concrete/roadwork normal/risk/ambiguous/unusable scenes cover the required activity and signal cases. `evaluation/expansion/draft-annotations.json` remains a machine proposal, never ground truth. Missing classes or reliable temporal sequences are missing evidence, not zero errors.

Real provider evaluation must reserve a conservative upper cost before each call, count uncertain outcomes against the RUB 1000 budget, and retain exact request profile/schema, inputs, raw responses, latency and usage. The delivery evaluation report/ledger records actual measured costs and gaps separately from mock-backed regression checks.

Current checked results, costs and exact limits are recorded in [HYBRID_VERIFICATION.md](HYBRID_VERIFICATION.md) and its JSON companion. The source-bound [review queue](../evaluation/hybrid/README.md) can be extracted without modifying organizer originals. A successful quiet repeat is distinct from an identical model answer: model output variability remains a quality limitation. Stage mismatch signal identity does not depend on changing model citations; its immutable basis still retains those citations.

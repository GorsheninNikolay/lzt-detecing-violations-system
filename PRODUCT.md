# Construction monitoring

The prototype helps a reviewer inspect construction photographs, identify visible equipment and scene features, compare observations with a zone plan, and decide what needs an on-site check. Observations, model hypotheses and human decisions remain separate. A signal does not establish a regulatory violation, a confirmed delay or the condition of the whole site.

## Workflow

A project contains zones, plans and analyses. The user selects a zone, uploads photographs in capture order, supplies capture times and consents to cloud processing. If the selected zone has a saved plan, comparison is enabled by default; the user can opt out. Each submitted analysis keeps its selected plan revision, so later plan edits cannot change its result. The work catalog supplies names and applicability, not a schedule.

The hybrid profile runs both supplied YOLO checkpoints on the server CPU. The cloud service labelled «Мультимодальная модель» in the interface reconciles their detections for each photograph, then assesses the photographs and saved context together. Original detector outputs, reconciled boxes, uncertain activity estimates, per-frame stage and work hypotheses, and persistent review signals remain inspectable. The profile using only the multimodal model is also supported.

The interface uses Onest typography, a plum palette and a shared project workflow. Visitor support, the interactive training tour and private administration should preserve this visual style and the separation between source evidence and user decisions.

## Evidence and decisions

The catalog contains eight equipment classes. Unknown types, free-form names and missing boxes or confidence values remain explicit; they do not expand the catalog automatically. Not detecting equipment in a frame does not prove its absence from the site.

A missing-equipment signal requires at least three independent, assessable frames within the relevant work interval. Concurrent work that permits the equipment prevents an exclusion signal. Visible equipment alone does not establish productive work. Possible idle requires comparable timed frames, evidence that they show the same machine, and visible non-work indicators; it remains a hypothesis for review.

Original images, model responses and saved context remain unchanged. Corrections create separate versions, and stage confirmation records a separate human decision. Repeated evidence does not reopen a closed signal; a later analysis without a risk does not automatically close earlier signals. Export for training requires explicit class mapping, whole-frame review and owner approval. Reserved evaluation images remain excluded.

Cloud calls are recorded before transmission. A call with an uncertain outcome is not automatically repeated. Retrying a lost upload response requires the same request body and idempotency key; it does not repeat model processing.

## Acceptance and access

Technical availability and model quality are assessed separately. Successful execution does not establish recognition accuracy. Missing independently reviewed coverage blocks quality acceptance; machine proposals are not ground truth. The prototype does not infer motion, idle duration or safety compliance from a single photograph.

User-facing API operations currently allow access without sign-in. Private file storage alone does not restrict application access; a restricted deployment needs external access controls. Owner administration requires a password and session, with HTTPS for remote access.

Start with [README.md](README.md) and the [documentation index](docs/README.md). See [the approach](docs/APPROACH.md), [equipment detection](docs/EQUIPMENT_DETECTION.md) and [construction stages](docs/CONSTRUCTION_STAGES.md) for the current behavior, [deployment instructions](infra/deploy/README.md) for setup and operating limits, and [the quality review guide](evaluation/hybrid/README.md) for acceptance requirements.

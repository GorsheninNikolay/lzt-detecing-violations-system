---
title: Construction Site Monitoring - Technical Assignment Digest
source: ./artifacts/spec.pdf
source_language: Russian
document_language: English
purpose: Fast, faithful context for agents working in a fresh session
---

# Construction Site Monitoring - Technical Assignment Digest

This file condenses the authoritative Russian technical assignment in [`artifacts/spec.pdf`](./artifacts/spec.pdf). It preserves requirements but does not choose an architecture or add product scope. If this digest conflicts with the PDF, the PDF wins.

## Why

Build a prototype that reduces manual review of construction-site camera images by detecting construction equipment, relating observations to the construction schedule, and showing understandable warnings about possible deviations.

The prototype should demonstrate the value of automatic image-to-schedule comparison and provide a credible foundation for future development.

## Required capabilities

### CAP-1 - Detect and classify equipment

- **Intent:** Process construction-site camera images and identify major equipment types.
- **Success:** The prototype shows which supported equipment classes were detected in the supplied image or images.

The supplied data may contain:

- dump truck;
- excavator;
- road roller;
- loader crane;
- concrete mixer truck;
- bulldozer;
- truck;
- mobile crane.

The team may support additional classes.

### CAP-2 - Relate observations to work stages

- **Intent:** Connect observed equipment to specific construction stages using a team-defined, explicit methodology such as `work stage -> required equipment`.
- **Success:** A reviewer can inspect and verify why an equipment observation is relevant to the selected stage.

Example from the assignment: excavation-pit work requires an excavator and dump trucks.

### CAP-3 - Detect deviations

- **Intent:** Automatically identify anomalies defined by the team's stage-to-equipment methodology.
- **Success:** The prototype detects and visualizes at least missing equipment required by the plan and equipment inconsistent with the current stage.

Example from the assignment: during excavation-pit work, an excavator is present but dump trucks are absent; the user receives a warning about a possible reduction in work pace, with the affected zone and supporting image or images.

### CAP-4 - Visualize results

- **Intent:** Provide the minimum interface necessary to demonstrate the mandatory functions.
- **Success:** A reviewer can quickly understand the site status, detected equipment, selected work stage, and the reason and evidence for each warning.

The final prototype may be a web interface, console application, or API with documented endpoints.

### CAP-5 - Produce a reproducible demonstration

- **Intent:** Let the jury run or inspect the complete path from image input to analysis result.
- **Success:** The final submission includes a working prototype, readable source code, setup instructions, presentation, and supporting documentation.

## Inputs and source materials

- A structured CSV or Excel example containing a hierarchical list of construction work stages.
- A common participant dataset consisting of:
  - an archive of unlabeled construction-site screenshots or images, up to 200 MB;
  - no more than five links to examples of open datasets.
- Teams may use additional public libraries, frameworks, datasets, synthetic data, or their own prior work related to computer vision, object detection, or tracking.
- No separate evaluation dataset is provided. The team must build its own evaluation set and should include variation in lighting, season, and equipment appearance where possible.

## Schedule interpretation

The assignment requires comparison with a construction schedule and refers to equipment inconsistent with the **current stage**. It does not require inferring the construction stage from the image itself.

The assignment does not define how the current stage is selected or derived. An implementation must make that mechanism explicit, for example by selecting it from the supplied plan or deriving it from schedule data when such data exists.

## Constraints

- The prototype must run or be demonstrable on a standard computer or laptop available at the event.
- A GPU is optional; it may be used when it improves prototype efficiency.
- The technology stack is unrestricted.
- Source code must be open for the final submission, structured, and readable.
- Comments should explain non-obvious logic, not narrate ordinary code.
- The architecture should be modular and allow future integration of new image types, equipment classes, and construction plans.
- Processing speed and warning latency are evaluation factors, but the assignment sets no numeric limits.

## Suggested technologies - not requirements

The assignment lists these only as examples; they do not affect scoring by themselves:

- Python, C++, or another language suitable for computer vision and machine learning;
- OpenCV, PyTorch, or TensorFlow;
- ready object detectors such as YOLO or Detectron2, optionally fine-tuned on supplied or synthetic data;
- Python with Flask or FastAPI, or Node.js for the backend;
- React, Vue.js, Streamlit, or Dash for the interface;
- PostgreSQL or MongoDB for persisted results;
- Dockerfile and `docker-compose.yml` for reproducible startup.

## Non-goals and unspecified behavior

The assignment does not require or define:

- recognition of the current construction stage from visual content;
- a specific model, framework, database, frontend, or deployment platform;
- mandatory GPU execution;
- fixed accuracy, recall, precision, or latency thresholds;
- a supplied labeled test set;
- production-scale operation, continuous video processing, or integration with a live camera system;
- a prescribed anomaly-detection algorithm beyond an explicit and verifiable stage-to-equipment methodology.

These may be added by the team, but must not displace the mandatory end-to-end demonstration.

## Required presentation

Provide a `.pptx` or `.pdf` presentation containing:

- the solution concept and architecture, including components and interactions;
- justification for the selected technologies and ML models;
- screenshots, video, or a live demonstration covering the complete flow from equipment recognition to analysis result;
- a diagram or explanation of how camera images relate to schedule stages;
- possible scaling and future-development paths;
- camera-placement recommendations for reliable analytics and better image-to-stage comparison.

## Required supporting documentation

Provide a `.doc` or `.pdf` document describing:

- the data model for equipment, work stages, deviations, and violations;
- relevant code structure and non-trivial logic;
- model training data and limitations;
- recognized equipment types;
- the work stages for which comparison logic is configured;
- step-by-step build, installation, and startup instructions.

## Submission checklist

### Intermediate submission

- Repository link on GitHub or GitLab.
- A description of no more than two pages covering:
  - the chosen approach and key technologies;
  - the equipment-detection process;
  - the stage-matching scheme;
  - current progress and the plan to final submission.

### Final submission

- Link to the open source repository.
- Link to a working prototype available to the jury.
- Link to the `.pptx` or `.pdf` presentation.
- Link to the `.doc` or `.pdf` supporting documentation.

## Evaluation priorities

Agents should optimize for the following judging criteria:

1. Completeness of the mandatory functions in the task description.
2. Recognition quality and robustness across varied examples.
3. An explicit, verifiable link between observed equipment and construction stages.
4. Clear, informative, and well-supported warnings.
5. A simple interface for quickly assessing site status.
6. Clean, readable, structured code.
7. Modular and extensible architecture.
8. Efficient image processing and low warning latency.
9. Clear documentation and a convincing, visual pitch demonstration.
10. Justified technology choices rather than technology novelty alone.

## Definition of a convincing minimum result

A reviewer can provide one or more construction-site images, select or otherwise establish the relevant schedule stage, and see:

1. detected supported equipment;
2. the explicit rule connecting that equipment to the stage;
3. any resulting deviation warning;
4. the affected zone and supporting image evidence;
5. a clear explanation of why the warning was produced.

The repository and documentation allow another person to reproduce that demonstration on ordinary event hardware.

## Open decisions left by the assignment

- How the current stage is selected from the supplied stage hierarchy or a richer schedule.
- Which stage-to-equipment rules form the minimum convincing demonstration.
- Which equipment classes are mandatory for the team's chosen scenario.
- How absence of equipment is inferred from one image versus a series of images.
- What accuracy and latency thresholds the team will use for internal acceptance.
- What interface form best demonstrates the complete flow.
- Whether persistence, Docker packaging, model fine-tuning, or a GPU are needed for the prototype.

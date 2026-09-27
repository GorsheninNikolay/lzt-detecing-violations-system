---
title: 'Multimodal model display name'
type: 'chore'
created: '2026-09-28'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="user-supplied implementation plan">

## Intent

Replace authored provider naming with «Мультимодальная модель», using appropriate Russian case and capitalization. Cover UI, cloud consent, OpenAPI descriptions, documentation, comments, specifications, reports and the two current PDFs. Keep Yandex AI Studio visible as the cloud provider. Newly generated results receive the new source text; historical results receive current UI labels without storage rewrites.

Preserve technical modules/classes, paths, database and API identifiers, errors, schema versions, real model URI, raw provider responses, experiment results and historical hashes. Do not modify the user's existing budget.json changes. No cloud calls, deployment, GUI or database migration. Verify frontend tests/build, affected mocked backend tests, OpenAPI, remaining name occurrences and CLI-rendered PDFs; record fresh checks/hashes separately from historical evidence.

</frozen-after-approval>

## Implementation Notes

The user explicitly supplied and authorized the implementation plan, including preservation of the known dirty budget file. This is a reversible copy update with no intent gaps or external effects; the existing active branch stays unchanged. Existing panel headings already label historical results independently of saved source strings. The PDF builder wraps card titles and bodies and enforces vertical bounds; inspect all rebuilt pages. Technical identifiers remain untouched.

The PDF generator encountered an existing manifest mismatch: the current Kaggle weights postdate the report. Added the exact historical manifest snapshot, retained its digest gate, and explicitly labeled PDF evidence as historical. New verification is recorded in docs/MULTIMODAL_NAME_VERIFICATION.md and its dated evidence directory; historical results/hashes remain intact. Frontend: 214 passed and build passed. Backend mocked/unit/OpenAPI: 72 passed; 12 PostgreSQL/S3 cases not verified because isolated services were not configured. All 24 updated PDF pages were CLI-rendered and visually inspected; both archive PDFs were text-checked without rewriting.

## Review Triage Log

1. Medium, patched: presentation did not distinguish historical/current weights; added explicit qualification and dated footer.
2. Medium, patched: accompanying manifest reference pointed to current file; corrected to the historical snapshot actually read.
3. Low, patched: historical metadata described current weights/environment; changed to report weights and measurement date.
4. Low, patched: mixed-language CLI error; translated explanation, preserving command and error code.
5. Low, patched: mixed-language module docstrings; translated prose while preserving executable AST.
6. Low, patched: mixed-language report gap; quoted the Russian display label in English prose.
7. Medium, fulfilled: fresh PDF hashes were pending; recorded separately in pdf-checks.json without overwriting historical identities.
8. Low, patched: added App consumer coverage for old projection.source and retained raw provider evidence coverage.
9. Low, patched: added assertion for the complete cloud consent label, including provider and model wording.

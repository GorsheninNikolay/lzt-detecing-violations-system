# Multimodal model display-name verification, 2026-09-28

The model display label is now «Мультимодальная модель», with Russian case and capitalization adjusted to context. Yandex AI Studio remains the cloud provider. UI headings, consent, progress labels, readiness copy, OpenAPI descriptions, newly published projection `source`, documentation, specifications and reports, module docstrings and the two current PDFs were updated. Historical stored results are not rewritten.

## Checks performed

| Check | Result |
| --- | --- |
| `npm --prefix web test -- --run` | 214 passed in 11 files |
| `npm --prefix web run build` | Passed; TypeScript and Vite |
| Selected backend tests, command below | 72 passed; 1 skipped; 11 deselected |
| OpenAPI direct and `/api` routes | Passed; new description and unchanged response/request contracts |
| UI successful, absent and historical assessments | Passed; historical projection source and raw response fixtures remain unchanged |
| Full cloud-consent label | Passed; includes Yandex AI Studio and the new model label |
| PDF generation | Both current PDFs rebuilt, 12 pages each |
| CLI rendering | All 24 pages rendered by Poppler and visually inspected; no clipping, overlap or broken long-name wrapping observed |
| PDF text/bounds | All four PDFs extracted with pdfplumber; no words outside page bounds; remaining name tokens only technical identifiers in the accompanying PDF |
| Compatibility | Executable AST of the three profile modules and migration unchanged after excluding module docstrings; historical report hashes unchanged |
| Existing user edit | `evaluation/hybrid/budget.json` SHA-256 unchanged from start of this task |

Backend command (no real provider requests):

```sh
backend/.venv/bin/python -m pytest backend/tests/test_deepseek.py backend/tests/test_quality_budget.py backend/tests/test_hybrid.py -q -k 'not runtime_consent and not renewal_failure and not expired_lease and not history_is and not invalid_raw_is and not persists_planless and not declared_context and not uncertain_detection_and_bound and not enabled_retired_queue'
```

The initial invocation encountered three missing-DB fixture errors and a sandbox restriction on a loopback HTTP test server. The final invocation allowed loopback binding and selected tests that do not require PostgreSQL/S3. The 12 DB/S3 cases (one skip, eleven deselections), including the added assertion for the persisted new `source`, remain unverified in this session: `TEST_DATABASE_URL` and isolated S3 settings were not configured. No database, cloud, deployment, or GUI operation was performed. UI tests run in jsdom; browser rendering was not checked.

Logs, the per-file remaining-name inventory, and new PDF SHA-256/size/page results are in [the dated evidence directory](verification/multimodal-name-2026-09-28/). The inventory covers tracked repository source and documents. Remaining references are technical paths/classes/API or database identifiers, model URI/schema versions, raw experiment evidence, historical logs, and explicit compatibility-test fixtures. Generated caches, ignored local work/video releases, dependencies and Git internals are not renamed.

## Historical PDF evidence

The existing generator initially rejected the current detector manifest: its Kaggle checkpoint was changed after the September 27 verification. This rename does not verify the new weights. The builder now reads [the exact historical manifest](pdf-inputs/yolo-manifest-2026-09-27.json), copied byte-for-byte from commit `7743ec669141e31e7bf0cc081f1a0494bf5daf79`. Its canonical JSON SHA-256 remains `cba5bbcdac16c41845cd55e29d9c52c9a987640d2e6d1cb5f6c374054e9d0256`, matching the existing report; the generator still enforces this check.

Both PDFs identify the historical verification date and this copy revision. The presentation explicitly states that current weights need separate verification; the accompanying document links the actual snapshot and states the same boundary. Existing test counts, paid-run results and old PDF hashes in `HYBRID_VERIFICATION.json` are preserved as historical evidence. Only its gap wording and PDF summary label changed. Fresh PDF hashes are recorded in [pdf-checks.json](verification/multimodal-name-2026-09-28/pdf-checks.json). The two archival PDFs were only inspected and retain their bytes.

Rebuild with Python containing reportlab, using `python scripts/build_submission_pdfs.py`. Render with `pdftoppm -scale-to 1200 -png <pdf> <prefix>`. Local generation used `/private/tmp/lzt-hybrid-docs-venv/bin/python`; rendering/extracted text are under `/private/tmp/lzt-rename-pdf`.

Independent review produced nine actionable copy, historical-evidence-labeling and test-coverage findings. All were corrected or fulfilled before completion; no findings were deferred.

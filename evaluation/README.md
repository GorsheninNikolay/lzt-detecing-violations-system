# Evaluation

Held-out evaluation fixtures and reports belong here, separately from backend integration fixtures.

`held-out-v1.json` binds the eleven reviewed frames, source archive checksums, manual labels, context, sufficiency, and the owner's prototype-use decision. `human-review-2026-09-24.json` retains the owner's answers; `owner-attestation-2026-09-24.json` records non-use and cloud-upload authorization with the original-capture provenance caveat. The manifest binds both files by SHA-256. `freeze-decision-v1.json` records the accepted gate result and inventory evidence. The source groups are conservative filename-prefix exclusion units, not verified camera identities. The archive's `train/` member names do not establish model-training use; the owner's non-use confirmation is scoped to this project.

The accepted revision and its eleven reserved fixtures were read back from an isolated local PostgreSQL database. Deployment and persistence in an application database remain separate steps. The source archive stays outside the repository at `/private/tmp/kaggle-construction-equipment.zip`.

After migrating the intended application database, install the revision through `cd backend && uv run evidence-evaluation freeze --archive /private/tmp/kaggle-construction-equipment.zip` with `DATABASE_URL` set for that database. The command returns the persisted revision ID and refuses an incomplete or overlapping set.

`historical-comparison-v1.json` records the later eleven-frame set already used for local and cloud comparison. It is excluded from a new held-out revision and is not a pre-campaign freeze.

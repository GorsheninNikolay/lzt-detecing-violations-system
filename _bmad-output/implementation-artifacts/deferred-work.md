- source_spec: `_bmad-output/implementation-artifacts/spec-f8-await-synchronous-effects.md`
  summary: Add an absolute duration bound for an S3 operation when a peer continuously streams data.
  evidence: Botocore read_timeout bounds socket inactivity, not the total operation; a trickling peer could keep the synchronous call alive. The current series waits for that call before terminalizing, so no late background effect occurs, but shutdown can wait indefinitely in this exceptional case.
- source_spec: `_bmad-output/implementation-artifacts/spec-4-1-freeze-held-out-evaluation-set-2.md`
  summary: Publish the eleven frozen JPEG bytes to the private artifact store before executing the comparison campaign.
  evidence: Story 4.1 binds source archive and frame checksums, but the only available archive is under `/private/tmp`. Story 4.4 execution must use durable, integrity-checked private references rather than relying on that temporary file.

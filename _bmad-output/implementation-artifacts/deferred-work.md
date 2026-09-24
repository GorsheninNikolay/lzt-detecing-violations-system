- source_spec: `_bmad-output/implementation-artifacts/spec-f8-await-synchronous-effects.md`
  summary: Add an absolute duration bound for an S3 operation when a peer continuously streams data.
  evidence: Botocore read_timeout bounds socket inactivity, not the total operation; a trickling peer could keep the synchronous call alive. The current series waits for that call before terminalizing, so no late background effect occurs, but shutdown can wait indefinitely in this exceptional case.

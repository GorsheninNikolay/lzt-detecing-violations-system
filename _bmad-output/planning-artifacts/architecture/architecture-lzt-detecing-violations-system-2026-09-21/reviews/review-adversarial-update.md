# Adversarial architecture final re-review

## Verdict

**PASS — no material adversarial seams remain in the three amended areas.** Independently built units now have one compatible interpretation for provider selection, run-level results, and provider-native provenance.

## Closure evidence

### Active provider and comparison runs — closed

AD-34 now separates the two creation paths explicitly:

- every ordinary run snapshots the current immutable active revision and observer profile;
- every `provider_comparison` run instead binds its frozen comparison-batch, matrix-cell, and candidate-profile identities;
- comparison runs neither read nor mutate active configuration.

The former counterexample—one unit requiring a provider winner before it can execute the comparison that chooses that winner, while another invents an exception—is no longer compliant. The exception and its identity source are now part of the rule.

### Run-level result semantics — closed

AD-35 now defines one backend-owned closed outcome kind and authoritative precedence:

- `observations_only` for observation intent;
- otherwise `not_analyzed` before `insufficient_data`, then `check_requested`, then `no_check`;
- clients may not re-derive the outcome.

The former pair—one API exposing a semantic outcome while another equated every missing check with “no warning”—can no longer both obey the AD. Per-class evidence remains available without making consumers responsible for domain classification.

### Observation-to-provider provenance — closed

AD-36 now introduces immutable `ObserverInvocation` identity, binds each invocation to its run, execution profile, stage, exact inputs, and native artifacts, and requires every normalized observation to reference exactly one invocation.

The former stage-level inheritance implementation is no longer compliant. Batched calls and multiple artifacts remain representable without losing the unique producer edge for an observation.

## Remaining findings

None material within the requested adversarial scope. Error-envelope details for attempting an ordinary run before any active revision exists can be chosen at implementation level under the existing stable API-error convention; they do not reopen provider ownership, mutation, or reproducibility semantics.

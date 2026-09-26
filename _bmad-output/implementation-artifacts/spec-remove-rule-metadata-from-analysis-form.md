---
title: 'Remove rule metadata from the analysis form'
type: 'chore'
created: '2026-09-26'
status: 'done'
route: 'oneshot'
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent">

## Intent

**Problem:** Jury members encounter internal rule names, hashes, expectations and provenance in the New Analysis form, distracting from the demonstration.

**Approach:** Remove the rule metadata card from the form while preserving the intent selector, live choice loading, demo revision checks, submission behavior and saved result evidence.

</frozen-after-approval>

## Implementation Notes

- Scope: remove the form card in `web/src/App.tsx`; adjust existing choice-loading and default-selection checks in `web/src/App.test.tsx`. No backend changes or external side effects.
- The user-provided screenshot is the visual reference. GUI applications are prohibited; validation uses DOM tests and the production build.
- Removed the complete rule metadata card from New Analysis; preserved rule evaluation and result evidence.
- Updated existing demo/default/loading tests to verify metadata is absent and submission remains enabled.
- Verification: 111 web tests passed, production build passed, and `git diff --check` passed.
- Independent reviewer found no confirmed defects. No findings deferred. Browser rendering and deployment were not verified.

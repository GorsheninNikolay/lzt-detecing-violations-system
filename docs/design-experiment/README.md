# Local design experiment

All changes and uploads in `npm run dev:demo` are in memory. No demo API requests are proxied. Demo controls and fixture middleware are absent from a normal production build. Restarting the demo server resets its state.

Run `npm ci`, `npm run dev:demo` in `web`. The branch script chooses a strict local port. Normal `npm run dev` continues to use API_PROXY_TARGET (default localhost:8000).

Verification: `npm test -- --run`, `npm run build`, `node scripts/verify-demo.mjs` (set VARIANTS to limit named variants; set CHROMIUM_PATH and PLAYWRIGHT_PACKAGE as needed; the harness uses the fixed demo ports 5174/5175/5176). Headless tooling is installed separately under `/private/tmp/lzt-design-experiment/tooling` so only motion is added as a runtime dependency.

Demo presets are available in the disclosure at the end of the page. Selecting a preset resets demo-owned pending submissions and annotation drafts on this origin. The recovery preset rejects the first upload with HTTP 503 and then accepts the exact idempotent retry. Analyzing holds an authoritative server stage for reproducible comparison. Ordinary uploads progress by server time.

The fixed photography and manually prepared boxes demonstrate interaction and evidence presentation, not model quality. No real backend write is part of verification.

Comparison, full commit manifest, screenshots and verification history are saved under `/private/tmp/lzt-design-experiment/`; start with [COMPARISON.md](../../../COMPARISON.md). Final source verification is recorded in [final-validation-summary.json](../../../final-validation-summary.json). Root DESIGN.md and .impeccable/design.json document this branch's approved visual world.

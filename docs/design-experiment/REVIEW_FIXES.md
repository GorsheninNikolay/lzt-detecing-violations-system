> Исторический материал эксперимента с интерфейсом. Результаты относятся к указанным здесь версиям и условиям, а не к текущему стенду. Команды `node scripts/*.mjs` используют локальные инструменты из `web/scripts`, которые больше не поставляются с репозиторием. Для текущих проверок интерфейса используйте `npm test -- --run` и `npm run build` из `web`.

# Review repairs — focused verification

Specs remain in-review. Root-authored Review Triage Log entries are preserved. These repairs do not modify the original workspace or the separately documented visual direction.

- Demo runs resolve the submitted revision within the submitted zone and copy the immutable plan into the run. Old revisions remain readable. Work IDs, plan revision and missing-equipment signals derive from that snapshot; detected or unrequested equipment does not produce missing-equipment signals.
- Submitted stage is consistent in top-level/context/projection fields. The photographic stage hypothesis stays explicitly illustrative. History is newest insertion first, independent of equal fixture dates. Annotation frame identity uses exact route-segment matching.
- Photo box selection returns mobile evidence mode to visible findings. OS-reduced motion disables both controls with explanatory text and preserves the saved user preference.
- Annotation numbers use the appropriate foreground token. Actual dashboard contrast is 12.66:1 (photo 11.73:1, 3D 12.48:1). The dashboard editor was recaptured.
- The More menu stacks the motion control with links instead of overlaying them. First-use onboarding passed at doubled text without a code change. Short-viewport menu checks cover 390/1440 widths and 560px height.
- Target audits now measure both dimensions of buttons, summaries, fields, effective checkbox/radio/file-label targets and navigation. The focused report records 447 target measurements and 108 explicit inline-link/geometry exceptions. Previous broad-pass height-only results must not be interpreted as complete target coverage.
- Marquee checks sample changing computed transforms while active, then identical transforms offscreen and disabled. Actual DemoPanel preset-button reset clears the retained upload, annotation and IndexedDB drafts, reaches the selected route, removes old recovery and preserves unrelated preferences.

Focused Vitest selections: dashboard 8 passed, photo 9 passed, 3D 8 passed; unrelated tests were skipped intentionally. Files selected: demo/server.test.ts, src/MotionPreference.test.tsx, and matching pipeline/photo cases in src/App.test.tsx. Full-suite/build validation is delegated to the root reviewer after return.

Headless evidence: `/private/tmp/lzt-design-experiment/evidence/review-fixes/report.json` (29/29); `/private/tmp/lzt-design-experiment/evidence/interaction-checks.json` (13/13, strengthened actual-transform assertions). The pre-fix More overlap is retained in `evidence/overlay-probe.json`. Commands: `node scripts/verify-review-fixes.mjs` and `node scripts/verify-interactions.mjs`. No broad visual pass was rerun.

# F6 rendered UI verification

- Result: **PASS** (26/26 checks).
- Browser: 153.0.8010.53; headless via Playwright at `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; Vite announced `http://127.0.0.1:4179`.
- Fixture: local completed-run response for `12345678-1234-1234-1234-123456789abc`; source artifact served from the bundled JPEG bytes.
- Phone: 320 CSS px, device scale 1; document width 320px; labels fit, no clipped content, no browser zoom.
- Touch emulation: tapping the scenario field produced a `touch` pointer event and focused the field; this is emulated input, not physical-device verification.
- 200% equivalent: 640 CSS px, device scale 2, 1280 rendered screenshot pixels; text spacing 0.12em / 0.16em / 1.5 / 2em; form and result have no clipped content and measured targets stay in the viewport.
- JPEG: 272405 bytes, SHA-256 `2dadb850e7a78cca8691763df50d1096d441b7837b1334a26e95d612123aaf9a`, intrinsic 1215 x 811; browser decoded 1215 x 811.
- Dialog: keyboard activation opened the native modal, forward/reverse boundary traversal stayed inside while open, Escape closed it, opener focus restored: true.
- Failure messages: integrity and unavailable messages both matched the UI.
- Scope limit: local fixture evidence only; no backend/API service, model accuracy, production, browser-toolbar zoom, or physical-device touch was verified.

Screenshots:
- `f6-phone-320-css.png` (320 x 2479 PNG)
- `f6-200-equivalent-form-640-css-dsf2.png` (1280 x 3702 PNG)
- `f6-200-equivalent-completed-run-640-css-dsf2.png` (1280 x 5562 PNG)
- `f6-native-evidence-dialog-640-css-dsf2.png` (1280 x 1800 PNG)

# Premium frontend headless verification

**Result:** 96/96 browser checks passed with no page errors in headless Chromium 153.0.8010.53. `npm run build` passed before the final capture. The browser loaded the production Vite bundle, local API fixtures, and actual JPEG bytes from `web/public/demo`.

## Screenshots

| CSS viewport | New analysis | Result | Signals |
| --- | --- | --- | --- |
| 1440×900 | [PNG](new-1440x900.png) | [PNG](result-1440x900.png) | [PNG](signals-1440x900.png) |
| 1366×768 | [PNG](new-1366x768.png) | [PNG](result-1366x768.png) | [PNG](signals-1366x768.png) |
| 768×1024 | [PNG](new-768x1024.png) | [PNG](result-768x1024.png) | [PNG](signals-768x1024.png) |
| 390×844 | [PNG](new-390x844.png) | [PNG](result-390x844.png) | [PNG](signals-390x844.png) |
| 320×844 | [PNG](new-320x844.png) | [PNG](result-320x844.png) | [PNG](signals-320x844.png) |
| 640×900, device scale 2 | [PNG](new-640x900-dsf2.png) | [PNG](result-640x900-dsf2.png) | [PNG](signals-640x900-dsf2.png) |

Full-page mobile captures: [new analysis](new-390x844-full.png), [result](result-390x844-full.png), [signals](signals-390x844-full.png). The 640 CSS-pixel, device-scale-2 run is a **200% rendered-size equivalent** on a 1280-pixel display; browser-toolbar zoom itself was not operated.

Separate CSS `zoom: 200%` captures at a 1280×900 CSS viewport: [new analysis](new-css-zoom-200-1280x900.png), [result](result-css-zoom-200-1280x900.png), [signals](signals-css-zoom-200-1280x900.png). None showed measured horizontal overflow. CSS zoom leaves the desktop media query active, so its navigation wraps vertically; this synthetic stress case is not equivalent to browser-toolbar zoom or the 640 CSS-pixel responsive reflow check.

## Render and interaction evidence

- At every viewport, the document and body widths equal the CSS viewport width. The 390px and 320px phone layouts show the compact header and labelled bottom navigation; larger layouts show the desktop navigation. Both local Onest font faces loaded, including Cyrillic.
- The new-analysis form decoded all three selected local previews. At 390px, scenario, zone, period, and the last frame's remove action remained clickable after scrolling past the sticky action panel. The primary action remained visible above the bottom navigation.
- The completed result decoded the source image, selected frame 2 from the thumbnail strip, opened the native viewer, focused a viewer control, and returned focus to its opener on Escape. The supporting label appears only on fixture-linked frames.
- Signals initially displayed 20 of 25 fixture records; “Show more” displayed all 25. The closed filter returned the one closed fixture record, and selecting the calendar signal showed that it has no linked frames. The details follow the selected row on mobile.
- The “More” disclosure opened from Enter and retained a visible focus outline. The reduced-motion media preference was active and the upload-zone transition duration was below 1 ms. The other routes (`/`, `/analyses`, `/plan`, `/about`, `/readiness`, `/provider-comparison`) rendered their headings.
- Static contrast calculations for shipped token pairs: primary text on canvas 16.02:1, secondary text on raised surface 7.57:1, dark text on violet primary button 6.19:1, amber notice text on its surface 8.52:1, red error text on its surface 7.92:1, and focus outline on canvas 9.00:1. This checks tokens rather than every text-over-image combination.

## Other local gates

The integration owner reported that the full frontend Vitest suite passed **111 tests**. The API agent reported one focused signal database test passing against a temporary PostgreSQL 14 instance, with Ruff and Python `compileall` passing. These are separate local checks; the browser run above used fixtures and did not connect to that database or a live service. I independently ran the frontend production build for the captured revision.

## Comparison with UX references

The rendered [new-analysis reference](reference-new-analysis-desktop.png) and [result reference](reference-result-desktop.png) are captures of the repository's HTML mockups. The implemented new-analysis screen retains their plum palette, rounded controls, approximately one-third context / two-thirds frame layout, clear manifest order, and restrained amber notice. It uses the current product copy and real demonstration image previews. The completed result retains the amber recommendation hierarchy and provenance sections; its larger selected image and right-hand basis column follow the updated brief, so it is intentionally not a pixel copy of the older result mockup. On mobile the result flows from outcome to basis to image. The signals screen has no matching HTML reference; its row/detail composition follows the brief.

## Limits

These are local, fixture-backed browser renders. They do not prove live backend integration, persisted model output, production deployment, physical-device behavior, browser-toolbar zoom, or assistive-technology operation. The [JSON measurements](measurements.json) and [reproducible verifier](verify.mjs) record the exact checks. Full-page screenshots capture the sticky action and bottom navigation at their initial viewport positions; the separate click checks confirm the form controls remain reachable after scrolling.

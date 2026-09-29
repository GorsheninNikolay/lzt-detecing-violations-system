---
name: "Контроль строительства — 3D Experience"
description: "A dark plum introduction with dimensional covers and a stable operational evidence plane."
colors:
  border: "#604d65"
  essential: "#a78aae"
  selected: "#523b58"
  warning: "#ffe1aa"
  warning-surface: "#443328"
  danger: "#ffc0ca"
  danger-surface: "#4b2938"
  canvas: "#201524"
  surface: "#2a1d30"
  raised: "#35273c"
  text: "#f8f0f7"
  secondary: "#d0bfce"
  accent: "#ddb6d4"
  focus: "#f2d9e9"
  on-accent: "#2e1732"
typography:
  display:
    fontFamily: "Onest, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "clamp(3rem, 6vw, 5.3rem)"
    fontWeight: 700
    lineHeight: 1.05
    letterSpacing: "-0.03em"
  title:
    fontFamily: "Onest, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1.8rem"
    fontWeight: 700
    lineHeight: 1.3
  panel-title:
    fontFamily: "Onest, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "22px"
    fontWeight: 700
    lineHeight: 1.3
  body:
    fontFamily: "Onest, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.65
  label:
    fontFamily: "Onest, system-ui, -apple-system, BlinkMacSystemFont, \"Segoe UI\", sans-serif"
    fontSize: ".875rem"
    fontWeight: 600
    lineHeight: 1.5
rounded:
  control: "8px"
  panel: "12px"
  cover: "18px"
  upload: "16px"
  image: "4px"
spacing:
  compact: "8px"
  control-gap: "12px"
  small: "16px"
  section: "24px"
  page: "32px"
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.on-accent}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.focus}"
    textColor: "{colors.on-accent}"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
  input:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  navigation-active:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.panel}"
    padding: "24px"
  object-selection:
    backgroundColor: "{colors.selected}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    padding: "10px 14px"
  dimensional-cover:
    backgroundColor: "#38273c"
    rounded: "{rounded.cover}"
    height: "240px"

---

# Design System: Контроль строительства — 3D Experience

## Overview

**Creative North Star: "The Architectural Introduction"**

Dark plum surfaces, large Onest headlines and illustrated architectural covers give project entry a spatial character. Depth belongs to introductory decoration and project presentation. The workflow settles into legible, stable surfaces when the user uploads photographs, inspects geometry or reviews evidence.

In the selected integration, each project card shows its uploaded public cover photograph when present and retains the architectural drawing as the empty-state fallback. The decorative entrance marquee keeps its cube grid: one slot fills for each project, the first four projects occupy the visible third row, and unfilled slots remain outlined. A supplied cover sits behind the cube outline. Project covers are presentation assets; working analysis photographs and annotation geometry remain outside transformed containers.

This is the implemented visual system of this approved experiment, extracted from source and saved headless renders. The metaphor names the approved direction; it does not introduce another concept decision. Product behavior remains governed by [PRODUCT.md](PRODUCT.md) and the approved [experiment brief](docs/design-experiment/SPEC.md).

**Key Characteristics:**

- Dark plum foundations with pale rose-plum actions.
- Large project-entry typography and dimensional architectural covers.
- Decorative motion gated by pointer, viewport, visibility and motion preference.

## Colors

The frontmatter records the final variant palette after the shared stylesheet cascade; use these roles consistently.

### Primary

- **Pale rose-plum** (`accent`): primary actions, text links and interactive emphasis.
- **Focus emphasis** (`focus`): hover color and keyboard-focus outline.
- **On-accent ink** (`on-accent`): readable primary-action labels.

### Neutral

- **Canvas / surface / raised:** page ground, supporting panels and control surfaces.
- **Text / secondary:** main copy and supporting labels.
- **Border / essential:** quiet structural dividers and stronger interactive boundaries.
- **Selected:** a tonal state for selected objects, tabs and shared navigation.

Warning and danger each have explicit foreground and surface roles. Use them for actual attention and error states, accompanied by text. They are semantic feedback, not additional brand accents.

## Typography

Use local Onest for display, body and controls, with the frontmatter fallback stack. Cyrillic and Latin WOFF2 files in `web/src/assets/fonts/` cover weights 400–700; there is no separate display face.

Display identifies the project or main page; title identifies a project card; panel-title identifies a work section. Body is the 16px base with relaxed paragraph leading; label is the smaller supporting field role. Controls use 1rem text and buttons use weight 600. The entry headline scale is not a universal size for all work screens.

**The Local Brand Rule.** Preserve the Russian product name, team logo and locally served Onest fonts across screens.

## Layout

Pages have a 1460px maximum width; the header allows 1500px. Project cards use two columns with 40px gaps, reduced to 24px at 1023px. Entry decoration occupies 53% of the desktop intro with a 340px scene. At 767px and below project cards stack; the scene becomes a 140px-high block in document flow, headlines become 3rem, and cover height reduces from 240px to 200px. Overview uses the shared 1.5:1 grid with a full-width illustrated presentation above it, then collapses at 1023px.

Shared page gutters are 32px on wide screens, 24px in the intermediate layout and 16px on mobile. The mobile page ends with 48px padding. Use the existing 8/12/16/24/32px rhythm; individual evidence geometry is not a spacing token. The mobile section navigation uses auto-fitting columns with an 8rem preferred minimum, wraps labels and stays in normal flow. At 360px and below project selection and the main action can each occupy the full row.

## Elevation & Depth

Perspective and soft ambient shadows distinguish architectural presentation from operational evidence. Project covers use 1100px perspective; overview presentation uses 1000px. Evidence results, stage confirmation and pipeline deliberately have no box shadow. The floating More menu keeps the shared overlay shadow.

**The Stable Evidence Plane Rule.** Keep the working photograph and its object geometry in an untransformed, non-animated container.

Fine pointers at widths of at least 900px may tilt decorative covers with a spring (stiffness 170, damping 24). Visible marquee columns travel ±32px over 12s/15s with easeInOut and reverse repetition. Offscreen, reduced or user-disabled motion returns the decoration to rest. Overview presentation maps scroll progress 0–0.6 to rotation 14°–0° and scale 0.94–1 only while eligible and visible. All decorative motion stops under OS reduction or the saved user-disable preference. The disabled system-override control explains why the saved choice cannot currently apply. Exact shadow and motion values live in the sidecar.

## Shapes

Dimensional covers and overview illustrations use broad 18px curves; the upload zone uses 16px. Work controls retain 8px corners, panels 12px and the working image only a restrained 4px radius. Project-card text remains outside the cover frame. Border contrast follows the border/essential roles instead of adding decorative outlines everywhere.

## Components

### Buttons

Primary buttons use accent with on-accent text, 8px 16px padding and the control radius. Hover moves to focus emphasis. Secondary buttons use raised surfaces and essential borders, changing to selected on hover. Standalone controls keep at least 44px height. Keyboard focus uses a 3px outline with 2px offset; disabled controls use 0.62 opacity and a not-allowed cursor. Preserve explicit disabled states rather than encoding them only through color.

### Inputs / Fields

Fields use raised surfaces, essential borders, control corners and 8px 12px padding. Labels precede the field; invalid fields use danger borders and explanatory copy. Editor fields can use the canvas surface and their existing 3px accent focus outline with 3px offset. Preserve the editor-specific geometry rather than forcing a general form pattern onto it.

### Navigation

The plum top header keeps project selection, primary routes and a pale action together. Active routes use the selected plum surface. Mobile navigation wraps in normal document flow rather than covering the working photograph. The More menu is a bounded, scrollable surface; its motion toggle is in normal flow alongside links. It closes on navigation and Escape returns focus to its summary. Preserve text labels and project scope.

### Cards / Containers

Project cards have transparent, borderless outer containers. Their illustrated covers carry the border, 18px radius and shadow; text uses 24px 4px padding. The overview illustration uses a two-column image/copy composition, becoming one column on mobile. Supporting shared panels use surface backgrounds and border-role outlines, with 24px desktop padding and 18px mobile padding unless a workspace-specific open container overrides them.

### Object selection and evidence

Object controls use raised backgrounds, essential borders and 10px 14px padding. Selection changes to the selected surface with accent emphasis; the working box and description refer to the same object. Frame strips remain directly associated with the image. On the photo-workspace mobile layout, choosing a box also reveals its findings description. Status/attention copy remains explicit prose rather than a newly invented badge vocabulary.

### Verification scope

Source checked: `web/src/variant.css`, `VariantDesign.tsx`, `main.tsx`, `AppHeader.tsx`, shared `styles.css`, `premium.css`, `MotionPreference.tsx` and annotation styles. Approved direction and product context were read directly; the Impeccable context launcher was not successfully run. There is no approved raster comp.

Saved headless evidence: `../evidence/confirmation/` contains the three worlds at desktop/mobile sizes; `../evidence/review-fixes/report.json` and adjacent PNGs cover final More-menu layout, editor-number contrast and actual motion gating. This documentation pass inspected representative renders and read the recorded checks; it did not rerun browsers or claim deployment, physical-device, model-quality or sidecar-panel validation.

## Do's and Don'ts

### Do:

- Do keep Russian product and team branding and load Onest from the bundled Cyrillic and Latin WOFF2 files.
- Do retain visible keyboard focus and allow long Russian labels to wrap.
- Do let mobile section navigation occupy normal document flow and let the More menu scroll within the viewport.
- Do preserve explicit selection between a photo object and its description, including on mobile.
- Do respect both the operating-system motion setting and the saved user preference.

### Don't:

- Don't use decorative imagery as evidence or label demo photographs as model-quality validation.
- Don't transform or decoratively animate working photographs and their annotation geometry.
- Don't add eyebrow labels as a recurring visual convention; the implemented variant hides them.
- Don't delay API completion to finish a decorative animation.
- Don't enable cover tilt or marquee travel on touch/coarse-pointer layouts.

---
title: 'Explain the Prototype and Its Limits'
type: 'feature'
created: '2026-09-24'
status: 'done'
baseline_revision: '0c4a733e806df1905e89caf0723341a724754602'
review_loop_iteration: 1
followup_review_recommended: true
context: []
warnings: []
deferred:
  - summary: >-
      The Stages Overview still lacks the supplied team mark in a spacious attribution area.
    evidence: |-
      DESIGN.md calls for the intact logo on Stages Overview and About Project. The pre-existing Stages surface only shows team text in the compact header; this story adds the About mark.
    location: >-
      web/src/App.tsx:954
    severity: medium
  - summary: >-
      Rendered phone layout and logo legibility remain unverified.
    evidence: |-
      Component tests and build pass, but they cannot establish actual 320 CSS pixel layout or visual legibility. A permitted rendered-browser check would settle this; GUI use is prohibited here.
    location: >-
      web/src/styles.css:20
    severity: medium (unverified)
---

<intent-contract>

## Intent

**Problem:** Users can inspect run evidence but have no concise project explanation to distinguish a source-bound observation and a human-check recommendation from a confirmed site-wide violation.

**Approach:** Add a Russian About Project route in the existing application shell, reachable from secondary navigation and team attribution, with an accurate account of the method, source provenance, scope, and limits.

## Boundaries & Constraints

**Always:** Identify `Контроль строительства` as the product and `17 мгновений ИИ` as the team. Explain the excavation scenario, source images and ordered series, supported excavator and dump-truck classes, frame observation states, evidence and immutable rule provenance, and what a human-check request means. Describe demonstration material as illustrative and retain exact source attribution. Keep semantic headings, keyboard focus after navigation, readable mobile order, and text attribution if the supplied logo cannot remain legible or load.

**Never:** Claim a check request proves a violation, that non-detection proves area-wide absence, or that the prototype tracks construction schedules, camera feeds, automatic current stage, trends, or project health. Do not invent a team mark or assert that a demonstration rule is a normative requirement.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| About route | Direct `/about`, secondary navigation, or team attribution | Russian explanation, correct title/team, focusable heading, return path | No API request or run polling |
| Logo unavailable or compact view | Missing asset or insufficient display space | Exact team text remains, without replacement icon | Hide failed image |
| Human-check explanation | `check_requested` or frame non-detection | Recommendation for human review, not a violation or area-wide absence | Explicit limitation text |

</intent-contract>

## Code Map

- `web/src/App.tsx:382` routes paths; add `/about` and exclude it from run reads and retry.
- `web/src/App.tsx:657` sets focus and document title after navigation; extend the title for About.
- `web/src/App.tsx:950` renders the shared brand, navigation and route branches; add links from secondary navigation and team attribution, and a semantic About surface.
- `web/src/styles.css:1` holds the dark shell and phone breakpoints; add only About layout rules needed for 320 CSS pixels and clear attribution.
- `web/src/App.test.tsx` exercises route, focus and content using jsdom; add an outer-surface route test including direct entry and attribution.
- `web/src/demoCases.json` records organizer archive paths, source groups and illustrative dates for demonstration samples; read-only provenance source for truthful copy.
- `backend/app/domain/rule.py:47` defines the three-usable-frame gate, positive result, and persistent non-detection check; `backend/app/domain/observations.py:80` defines frame states. Read-only sources for About wording.
- `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/imports/team-17-mgnoveniy-ii-logo.png` is the supplied complete logo; use it only at a legible size.
- `_bmad-output/planning-artifacts/epics.md:863` and `_bmad-output/planning-artifacts/ux-designs/ux-lzt-detecing-violations-system-2026-09-21/EXPERIENCE.md:53` define Story 3.4 and About navigation; read-only contract.

## Tasks & Acceptance

**Execution:**
- `web/src/App.tsx` — add `/about` routing, secondary and attribution links, page title/focus, return navigation, and Russian method/scope/limits content; distinguish observation-only, each observation state, `no_check`, `check_requested`, and the actual three-usable-frame rule gate; do not trigger run fetching on About.
- `web/public/team-logo.png` — copy the supplied complete logo for spacious About attribution, with exact team text always present.
- `web/src/styles.css` — make the explanation and team attribution readable at phone and laptop sizes using the existing shell tokens.
- `web/src/App.test.tsx` — cover route entry, navigation/focus, critical content, and no run API request.
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — synchronize only Story 3.4 after the final verified result.

**Acceptance Criteria:**
- Given any application page or a direct `/about` URL, when I open `О проекте` from navigation or `17 мгновений ИИ` attribution, then I see a Russian page naming the product/team and describing excavation, two supported classes, source images, observation states, rule provenance, human review and excluded capabilities.
- Given a small viewport or failed team logo, when About renders, then exact team text remains readable, no invented mark appears, and heading/focus/reading order remain usable.
- Given the explanation of non-detection and check requests, when I read About, then it states the evidence boundary and that a check request is a human recommendation rather than proof of a violation.
- Given the About method explanation, when I compare observation-only and rule-check modes and their outcomes, then I can tell when a class was not analyzed or a frame was insufficient, what `no_check` means, and which bounded series evidence can lead to a human-check request.

## Spec Change Log

### 2026-09-24 — Clarify outcome interpretation
- Trigger: review found that the first About draft listed observation states and mentioned a check request without explaining observation-only mode, the positive outcome, or the actual series rule gate.
- Amendment: the App task and acceptance criterion now require distinct explanations grounded in the domain rule and observation contracts.
- Avoided bad state: readers could mistake `no_check` for site-wide compliance or frame non-detection for a qualified series result.
- KEEP: `/about` routing, secondary and team links, direct-entry fallback, no run fetch, semantic heading/focus, complete supplied logo with exact team text, and the source-bound limits copy.

## Review Triage Log

### 2026-09-24 — Review pass
- verdicts: 9 findings — high 0, medium 5, low 1, false 2, maybe-false 1
- findings:
  - `[medium]` `[bad_spec]` About omits the three-usable-frame and equipment gate — `backend/app/domain/rule.py` requires the bounded series conditions; amended the App task and acceptance criterion.
  - `[medium]` `[bad_spec]` About lists frame states without their distinct meanings — `backend/app/domain/observations.py` separates insufficient data and not analyzed from non-detection; amended the App task and acceptance criterion.
  - `[medium]` `[bad_spec]` About omits observation-only mode — that mode does not evaluate the stage rule; amended the App task and acceptance criterion.
  - `[medium]` `[bad_spec]` About omits `no_check` semantics — a positive rule outcome is bounded to the submitted series, not site-wide compliance; amended the App task and acceptance criterion.
  - `[low]` `[reject]` Example source paths are plain text — About identifies provenance and the included demo form opens the JPEGs; adding a second viewer or link list is not required for everyday interpretation.
  - `[medium]` `[defer]` The supplied logo is absent from the Stages Overview — the design spine asks for it, but that earlier surface predates this story; address its attribution in a separate Stages change.
  - `[false]` `[reject]` Sprint status is still backlog in the review diff — the spec explicitly schedules ledger synchronization after the final verified result, so this is not a final-state mismatch.
  - `[false]` `[reject]` Intent audit repeats the sprint-status divergence — synchronization is a post-review workflow task and has not yet been reached.
  - `[maybe-false]` `[defer]` Mobile layout and logo legibility lack rendered-browser proof — jsdom and build cannot settle the visual result, and GUI use is prohibited in this workspace.

### 2026-09-24 — Review pass
- verdicts: 12 findings — high 0, medium 7, low 3, false 1, maybe-false 1
- findings:
  - `[medium]` `[patch]` Three usable frames alone do not suffice if another required-class observation is unassessable — About now states the all-submitted-observations gate from `backend/app/domain/rule.py`.
  - `[medium]` `[patch]` Supporting frames were described as stored for every run — About now separates retained source images from support frames selected for qualified rule outcomes.
  - `[low]` `[patch]` Archive PNG sources were named without their JPEG conversion — About now identifies the included JPEG copies.
  - `[medium]` `[patch]` Return link pushed another history entry — in-app return now uses browser history and direct-entry fallback uses Stages.
  - `[medium]` `[patch]` Production fallback guidance omitted `/about` — `web/README.md` now names it.
  - `[medium]` `[patch]` About appeared in primary navigation — its link now sits in a labeled secondary navigation region.
  - `[medium]` `[defer]` carried: Stages Overview still lacks the intact logo called for by the design spine; this pre-existing surface remains outside Story 3.4.
  - `[low]` `[patch]` About omitted JPEG-only upload scope — the source explanation now names the accepted format.
  - `[low]` `[patch]` The removed brand span left dead CSS — the obsolete selector is gone.
  - `[false]` `[reject]` Intent audit reports sprint status absent from the review diff — this workflow synchronizes the verified story after review, before final commit.
  - `[maybe-false]` `[defer]` carried: rendered phone layout and logo legibility still need a permitted visual check; jsdom cannot establish them.
  - `[medium]` `[patch]` Intent audit repeats the primary-navigation placement — the same secondary navigation correction addresses it.

## Verification

**Commands:**
- `cd web && npm test -- --run` — existing and new component tests pass.
- `cd web && npm run build` — TypeScript and production build pass.

## Auto Run Result

Status: done

Implemented: A Russian `/about` page explains the excavation method, bounded observation and rule outcomes, example provenance, and prototype limits. The secondary navigation and team attribution open it; the supplied logo retains exact text attribution when unavailable or small.

Files changed:
- `web/src/App.tsx` — route, navigation, return behavior, and About content.
- `web/src/styles.css` — About and attribution layout.
- `web/src/App.test.tsx` — direct route, semantics, fallback, focus, and history checks.
- `web/public/team-logo.png` — exact supplied artwork.
- `web/README.md` — production history fallback for `/about`.
- `sprint-status.yaml` — only Story 3.4 moved to `done` with a timestamp update.

Review: The first pass identified four content gaps and re-derived the page from an amended spec. The final pass patched seven entries (five medium, two low); two entries remain deferred (the earlier Stages logo placement and rendered mobile verification). Rejected findings were: a second example viewer was unnecessary because provenance and the demo flow already expose examples; sprint status was scheduled after review and is now synchronized. The repeated secondary-navigation finding shared its applied patch. Follow-up review is recommended because five medium entries required patches; the remaining unverified risk is actual phone rendering and logo legibility.

Verification: `npm test -- --run` passed 77/77; `npm run build` passed; `git diff --check` passed. Logo checksum matches the supplied asset. Sprint status parsed and read back as Story 3.4 `done`, Epic 3 `in-progress`. Rendered-browser and deployed-route behavior were not verified under the no-GUI constraint.

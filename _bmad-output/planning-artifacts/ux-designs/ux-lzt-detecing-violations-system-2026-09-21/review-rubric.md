# Spine Pair Review - Construction Monitoring Rapid MVP

## Overall verdict

The pair is an adequate, unusually disciplined draft: the canonical CAP-1 through CAP-6 contract is represented by named-protagonist flows, every token reference resolves, the core evidence semantics remain intact, and the required spine shapes are present. It is not yet safe as a final downstream contract because a stated non-text contrast claim is false, several load and recovery states are missing, and the two declared requirements sources reuse CAP-1 through CAP-5 for different meanings without an explicit precedence or mapping.

## 1. Flow coverage - adequate

Checked both declared capability sets, the prototype scenarios, architecture-bound CAP-1 through CAP-6, the six IA surfaces, and all four Key Flows. The canonical Rapid MVP capabilities are covered: Flow 2 covers single-image observation; Flows 1 and 3 cover ordered series, result semantics, and rule evaluation; Flow 1 covers the two demonstration outcomes; Flow 4 covers readiness. Every flow has a named protagonist, numbered steps, a climax, and an applicable failure path.

### Findings

- **medium** `About Project` is a declared IA surface that owns team identity, method, scope, limitations, and provenance, but no Key Flow lands there; therefore surface closure is not demonstrated for a stated need (`EXPERIENCE.md:32-46`, `EXPERIENCE.md:200-260`). *Fix:* Add a short named-protagonist path to `О проекте`, or explicitly fold this content into a surfaced step of the jury flow and remove it as a standalone destination.

## 2. Token completeness - adequate

Extracted all color, typography, radius, spacing, and component tokens and all `{path.to.token}` references from both spines. All 20 color tokens are literal hex values; all 28 unique token references resolve; typography and dimensions conform to the working DESIGN.md type rules. The primary text, action, focus, and semantic text/surface pairs meet their stated text-contrast targets.

### Findings

- **high** `{colors.border}` is used as the visible boundary for secondary buttons, panels, inputs, evidence frames, history rows, readiness rows, and notices, but it measures only about 2.10:1 against `{colors.canvas}` and 1.91:1 against `{colors.surface}`. This contradicts the declared 3:1 non-text-boundary target and can erase load-bearing control boundaries (`DESIGN.md:19`, `DESIGN.md:96-116`, `DESIGN.md:142-215`, `DESIGN.md:241`, `DESIGN.md:278`). *Fix:* Introduce a stronger control/boundary token that reaches 3:1 on every adjacent surface, or reserve the current low-contrast border for non-essential separators and specify an additional 3:1 cue for each interactive component.

## 3. Component coverage - adequate

The 23 product components named in the two Components sections have matching visual and behavioral rules, including the uploader, manifest, six-step route, observations, result, check request, evidence viewer, history, readiness, comparison, and mobile navigation. Radix Themes inheritance is stated in both spines.

### Findings

- **medium** The machine-readable component registry and the prose registries do not use one exact component vocabulary. `top-bar`, `panel`, `evidence-frame`, and `focus-ring` exist under frontmatter `components` without same-named behavioral rows, while prose-level `Status Label` and `Input Field` have no same-named frontmatter entries (`DESIGN.md:91-216`, `DESIGN.md:271-295`, `EXPERIENCE.md:75-103`). *Fix:* Establish one canonical component-name table across frontmatter and both Components sections; classify visual-only values such as focus-ring as tokens or inherited Radix primitives instead of product components.

## 4. State coverage - thin

Walked Stages Overview, New Analysis, Run Workspace, Analysis History, Prototype Readiness, About Project, and the Evidence Viewer. Run lifecycle, polling disconnection, restart interruption, domain outcomes, insufficient evidence, upload decode failure, duplicate inputs, empty history, incomplete readiness, incomplete provider comparison, and missing logo are covered.

### Findings

- **high** Several surfaces lack the cold-load, retrieval failure, offline, or permission-denied states relevant to a reproducible live demo: New Analysis has no camera-permission fallback or submission/API failure treatment; Analysis History and Prototype Readiness have no loading or fetch-error treatment; Evidence Viewer has no artifact-load or integrity-failure treatment; About Project has only a logo fallback (`EXPERIENCE.md:105-147`, `EXPERIENCE.md:176-198`). *Fix:* Add a compact state matrix for each affected surface, preserving accepted inputs and last persisted evidence, with retry/fallback behavior and Russian copy.

## 5. Visual reference coverage - strong

Both files in `imports/` are linked inline and their purpose is stated. All three `.working/` HTML boards are linked from the visual lineage: the selected C+B direction, the selected full-night theme, and the superseded light themes. The spine-wins-on-conflict rule is stated once in EXPERIENCE.md. No `mockups/` or `wireframes/` directory exists yet, so there are no promoted artifacts or orphans to reconcile at this review point.

### Findings

No misses.

## 6. Bloat & overspecification - strong

The pair is detailed where downstream implementation needs exact evidence semantics and remains summary-first elsewhere. Repetition of non-violation wording, client-does-not-derive rules, and pipeline truth is load-bearing rather than decorative. Tables are used for IA, state, responsive, voice, and component contracts; source product scope is referenced instead of broadly recopied.

### Findings

No material bloat finding.

## 7. Inheritance discipline - thin

All four frontmatter source paths resolve. Result-state codes, lifecycle states, pipeline ordering, rule/check separation, retry lineage, and provider/readiness separation agree with the canonical SPEC, scenarios, and architecture. Component names in the two prose component sections are materially consistent, and every EXPERIENCE.md token reference resolves to DESIGN.md.

### Findings

- **high** Two declared sources assign different meanings to the same identifiers CAP-1 through CAP-5. The technical-assignment digest defines CAP-3 as deviation detection including equipment inconsistent with the current stage, while the canonical SPEC defines CAP-3 as the four-state result contract and narrows the MVP to excavation, excavator, and dump truck. Key Flows cite only the bare IDs, so a downstream consumer cannot tell which requirement set is covered (`spec.md:19-63`, `_bmad-output/specs/spec-construction-monitoring-concepts/SPEC.md:17-36`, `EXPERIENCE.md:202-250`). *Fix:* State source precedence in both spines and add a traceability table with disambiguated names, for example `TA-CAP-*` mapped to canonical `CAP-*`, including any assignment requirement intentionally deferred or narrowed.

## 8. Shape fit - adequate

DESIGN.md follows the canonical order exactly: Brand & Style, Colors, Typography, Layout & Spacing, Elevation & Depth, Shapes, Components, Do's and Don'ts. EXPERIENCE.md contains every required default section, plus the earned evidence-semantics section and the triggered Responsive & Platform section.

### Findings

- **medium** `Inspiration & Anti-patterns` is triggered by the imported hackathon reference, selected design boards, superseded light directions, and explicit rejected event-page patterns, but it is absent from EXPERIENCE.md. The rationale exists only across DESIGN.md and reconciliation files, so the behavioral spine does not preserve which reference behaviors were retained or rejected (`DESIGN.md:220-228`, `EXPERIENCE.md:15-30`, `reconcile-hackathon-reference.md:1-29`). *Fix:* Add a concise Inspiration & Anti-patterns section that links the reference and reconciliation files and records only behaviorally relevant retained/rejected patterns.

## Mechanical notes

- Frontmatter is syntactically regular and contains required `name`, `description`, `sources`, `status`, and `updated` fields.
- All declared source paths resolve from both spine locations.
- All 28 unique `{...}` token references resolve to frontmatter definitions.
- Every color token has a six-digit hex value; no light/dark pair is required because the contract explicitly selects dark-only.
- Existing visual files are all linked inline with a stated role; there are no mockup or wireframe files yet.
- No Mermaid blocks occur in either UX spine, so there is no Mermaid syntax to validate.
- Finding counts: critical 0, high 3, medium 3, low 0.

## Resolution verification

- **Resolved - About Project flow closure (prior medium).** The jury journey now explicitly opens `О проекте` to verify the team, method, supported scope, and limitations before the climax (`EXPERIENCE.md:244-260`, especially `EXPERIENCE.md:257`).
- **Partial - Essential boundary contrast (prior high).** `{colors.border-essential}` is defined and measures approximately 4.46:1 against canvas, 4.07:1 against surface, 3.47:1 against raised surface, and 3.10:1 against selected surface. It is applied to load-bearing component tokens and the decorative role of `{colors.border}` is explicit (`DESIGN.md:19-20`, `DESIGN.md:106-203`, `DESIGN.md:225-230`, `DESIGN.md:250`). One direct contradiction remains: the Secondary Button prose still specifies a `{colors.border}` boundary even though its machine-readable component token correctly uses `{colors.border-essential}` (`DESIGN.md:106-111`, `DESIGN.md:267`). Resolve by changing that prose reference to `{colors.border-essential}`.
- **Resolved - Component vocabulary alignment (prior medium).** The frontmatter now uses the same canonical product-component names as both prose registries, including `application-shell`, `status-label`, `series-evidence`, and `input-field`; the former orphan names `top-bar`, `panel`, `evidence-frame`, and `focus-ring` are gone, with focus values owned by Application Shell (`DESIGN.md:92-203`, `DESIGN.md:260-285`, `EXPERIENCE.md:86-115`).
- **Resolved - Surface state coverage (prior high).** The state matrix now specifies camera-permission fallback, submission/API failure recovery, Analysis History and Prototype Readiness loading/fetch failures, Evidence Viewer artifact and integrity failures, and the pre-submission offline state while preserving recoverable context (`EXPERIENCE.md:142-165`).
- **Resolved - Capability source inheritance (prior high).** EXPERIENCE.md now declares canonical-source precedence, reserves `TA-CAP-*` for the technical-assignment digest, and maps all five assignment capabilities to canonical CAP coverage or explicit deferral (`EXPERIENCE.md:30-38`).
- **Resolved - Inspiration & Anti-patterns shape (prior medium).** The triggered section now records retained, transformed, and rejected visual and behavioral decisions and links both reconciliation files (`EXPERIENCE.md:234-240`).

Resolution counts: resolved 5, partial 1, unresolved 0.

Final verification: **resolved** - Secondary Button now uses `{colors.border-essential}` consistently in both its machine-readable token and prose specification (`DESIGN.md:106-111`, `DESIGN.md:267`). Final counts: resolved 6, partial 0, unresolved 0.

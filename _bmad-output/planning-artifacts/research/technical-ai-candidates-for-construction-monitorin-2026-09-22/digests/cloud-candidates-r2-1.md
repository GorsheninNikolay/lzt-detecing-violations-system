# Cloud multimodal candidates — correction round 2

**Research/access date:** 2026-09-22  
**Decision served:** correct round 1 and admit exactly one primary plus one reserve cloud model to a later shared experiment. This is not the final local/cloud/hybrid selection.

## Correction outcome

- **Primary:** Google Gemini API `gemini-3.7-flash`.
- **Reserve:** OpenAI API `gpt-5.6-terra`.
- **Retracted:** `gemini-3.8-flash`. Round 1 treated a search-rendered/current catalog mention and copied pricing as a complete model-specific evidence chain. The exact pricing page has no `gemini-3.8-flash` section; it prices `gemini-3.7-flash` and separately prices `gemini-3.8-live`. The claim and admission are withdrawn.
- **Corrected OpenAI URL:** use `https://developers.openai.com/api/docs/models/gpt-5.6-sol`, not the round-1 legacy/404 path `https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4`.

No official source retrieved here reports excavator or dump-truck accuracy for either admitted model. Recognition quality remains experiment-only.

## Scope and method

The task is independent frame-level classification of `excavator` and `dump_truck`. The only portable per-class outputs are `detected`, `not_detected_in_frame`, `insufficient_data`, and `not_analyzed`. Counts, confidence, boxes, regions, and other provider-native geometry may be retained as diagnostic evidence but cannot drive rules.

This correction rechecked exact first-party model pages, pricing pages, structured-output support, data controls, and model/version naming. It compared Gemini 3.7 Flash with OpenAI GPT-5.6 Sol, Terra, and Luna. General positioning and price are not treated as evidence of construction-class accuracy.

## Overturned claims and URL mismatches

| Round-1 statement | Correction | Why overturned | Authoritative current URL |
|---|---|---|---|
| `gemini-3.8-flash` is the primary and costs $0.75/M input, $3.75/M output. | **Withdrawn.** Those prices belong to the exact `gemini-3.7-flash` section. | The current pricing page has a `Gemini 3.7 Flash` section and a separate `Gemini 3.8 Live` section, but no priced `Gemini 3.8 Flash` section. A catalog mention alone is insufficient. | https://ai.google.dev/gemini-api/docs/pricing |
| The cited OpenAI catalog path verifies `gpt-5.6-sol`. | **URL invalidated.** Model facts must cite the current exact model page. | The prior `platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4` path was verified as 404/outdated. | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
| OpenAI reserve should be `gpt-5.6-sol`. | **Replaced by `gpt-5.6-terra`.** | Sol is a $4/$20 flagship; Terra is explicitly the intelligence/cost balance at $2/$12 and has the same required image-input and Structured Outputs capability. No domain evidence justifies paying for Sol before the shared eval. | https://developers.openai.com/api/docs/models/gpt-5.6-terra |
| The model IDs were effectively pinned snapshots. | **Narrowed.** | Gemini calls `gemini-3.7-flash` stable but says stable models “usually” do not change. OpenAI labels its identifiers under Snapshots but exposes no dated immutable suffix on the exact pages. Both require metadata logging and pre-demo canaries. | https://ai.google.dev/gemini-api/docs/models ; https://developers.openai.com/api/docs/models/gpt-5.6-terra |

## Claims table

| Claim | Source URL | Publisher | Pub. date | Accessed | Confidence | Claim class |
|---|---|---|---|---|---|---|
| `gemini-3.7-flash` is a stable model updated 2026-08-13; it accepts image input, returns text, and supports Structured Outputs. | https://ai.google.dev/gemini-api/docs/models/gemini-3.7-flash | Google | 2026-08-13 | 2026-09-22 | High | Direct fact |
| The exact Gemini 3.7 pricing section lists standard paid rates through 2026-12-31 of $0.75/M input tokens and $3.75/M output tokens; Google AI Studio is linked for trial. | https://ai.google.dev/gemini-api/docs/pricing | Google | Undated live pricing | 2026-09-22 | High | Direct fact |
| The same pricing page says paid-tier content is not used to improve Google's products. | https://ai.google.dev/gemini-api/docs/pricing | Google | Undated live pricing | 2026-09-22 | High | Direct fact |
| Paid Gemini API prompts, files including images, and responses are not used to improve products; limited abuse-monitoring logging applies, and guaranteed ZDR/DPA workloads are directed to Vertex AI. | https://ai.google.dev/gemini-api/docs/zdr | Google | Undated live policy | 2026-09-22 | High | Direct fact |
| Gemini Interactions stores state by default unless `store=false`; Search/Maps grounding stores content for 30 days, File API objects persist until deletion/expiry, and implicit RAM cache has a 24-hour TTL. | https://ai.google.dev/gemini-api/docs/zdr | Google | Undated live policy | 2026-09-22 | High | Direct fact |
| Gemini “stable” points to a specific stable model, but the docs say stable models *usually* do not change; this is not proof of immutable artifact pinning. | https://ai.google.dev/gemini-api/docs/models | Google | Undated live documentation | 2026-09-22 | High | Direct fact + limitation |
| `gpt-5.6-terra` accepts image input, supports Structured Outputs, does not support fine-tuning, and costs $2/M input plus $12/M output tokens. | https://developers.openai.com/api/docs/models/gpt-5.6-terra | OpenAI | Undated live model page | 2026-09-22 | High | Direct fact |
| OpenAI describes Terra as balancing intelligence and cost. This supports experiment admission, not a machinery-accuracy claim. | https://developers.openai.com/api/docs/models/gpt-5.6-terra | OpenAI | Undated live model page | 2026-09-22 | High | Direct fact + decision inference |
| Terra's page lists tier-dependent limits: Tier 1 500 RPM/500k TPM; higher tiers scale upward. Free is unsupported. | https://developers.openai.com/api/docs/models/gpt-5.6-terra | OpenAI | Undated live model page | 2026-09-22 | High | Direct fact |
| OpenAI's Terra page places `gpt-5.6-terra` under Snapshots but shows no dated alternate identifier; the page's repeated same string does not establish immutable revision pinning. | https://developers.openai.com/api/docs/models/gpt-5.6-terra | OpenAI | Undated live model page | 2026-09-22 | Medium-high | Direct fact + limitation |
| OpenAI API inputs are not used to train/improve models unless explicitly opted in. Responses and Chat Completions have up to 30-day abuse-monitoring retention by default; ZDR eligibility has documented exceptions, including safety handling of images/files. | https://developers.openai.com/api/docs/guides/your-data | OpenAI | Live policy; training statement effective since 2023-03-01 | 2026-09-22 | High | Direct fact |
| `gpt-5.6-sol` is the flagship, accepts image input, supports Structured Outputs, does not support fine-tuning, and costs $4/M input plus $20/M output. | https://developers.openai.com/api/docs/models/gpt-5.6-sol | OpenAI | Undated live model page | 2026-09-22 | High | Direct fact |
| `gpt-5.6-luna` is positioned for cost-sensitive high-volume work, accepts image input, supports Structured Outputs, does not support fine-tuning, and costs $0.20/M input plus $1.20/M output. | https://developers.openai.com/api/docs/models/gpt-5.6-luna | OpenAI | Undated live model page | 2026-09-22 | High | Direct fact |

## Screened field and cuts

| Candidate | Decision | Rationale |
|---|---|---|
| `gemini-3.7-flash` | **Primary** | Exact stable model page verifies image input and Structured Outputs; exact pricing and trial path exist; lower evidenced price than Terra. |
| `gpt-5.6-terra` | **Reserve** | Independent provider; exact page verifies all required interface capabilities; middle OpenAI tier avoids both unproven flagship premium and premature nano-tier optimization. |
| `gpt-5.6-sol` | Cut from the two admitted slots | Strongest OpenAI positioning but 2× Terra input price and 1.67× output price. No direct construction evidence establishes enough gain to justify the premium before evaluation. |
| `gpt-5.6-luna` | Cut from first experiment | Very low price and higher published rate limits, but explicitly cost-sensitive/nano-tier positioning. Test later if Terra passes accuracy gates and cost dominates. |
| `gemini-3.8-flash` | **Retracted / not admitted** | Model catalog and structured-output examples mention it, but the exact pricing page lacks its model section while separately pricing 3.8 Live. The evidence chain is internally inconsistent for this decision. |
| Gemini 3.6/3.5/Lite | Cut | Older or efficiency-first alternatives. No direct machinery evidence supports substituting them for the current exact 3.7 baseline. |

## Candidate profiles

### Primary — Google Gemini API `gemini-3.7-flash`

- **Exact availability:** official model page marks the exact code stable, last updated 2026-08-13, and links a Google AI Studio trial. API/account/region access was not exercised.
- **Image and output:** image input and text output are explicit. Structured Outputs is explicitly supported. Require a closed JSON schema with exactly two class keys and the four portable enum states, then validate again in application code.
- **Evidence/regions:** no detector-grade region or grounded-box contract was found on the model page. Optional narrative evidence or geometry is evaluator-only and cannot affect the portable state.
- **Revision pinning:** use exactly `gemini-3.7-flash`; log provider metadata and timestamp. “Stable” is not immutable because Google says these models *usually* do not change. Run frozen-corpus canaries before every reported experiment/demo.
- **Pricing:** standard paid pricing is $0.75/M input and $3.75/M output tokens through 2026-12-31. Measure image-token use on the actual corpus.
- **Network/access:** requires cloud network egress, API credentials, supported geography, quota, and billing tier. AI Studio availability is a demonstration aid, not proof the experiment's API account works.
- **Privacy/retention:** use paid tier. Do not use Search/Maps grounding, stateful storage, File API persistence, or explicit caching for this task. Set `store=false` where applicable. If guaranteed ZDR/DPA is required, route through Vertex AI and verify account controls before real imagery.
- **Timeout/rate limit:** no fixed request-timeout SLA or guaranteed ordinary capacity was found. Read account limits immediately before the run; impose a client deadline, bounded retry/backoff, and map exhausted transport/provider failures to `not_analyzed`.
- **Fine-tuning:** exact model fine-tuning support was not established and is not needed for admission. Begin zero-/few-shot; a failed accuracy gate triggers a separate trained-detector/tuning decision.
- **Live-demo risk:** medium: a stable exact page and AI Studio path reduce setup risk, but region/account access, capacity, semantic accuracy, and model drift remain unverified.

### Reserve — OpenAI API `gpt-5.6-terra`

- **Exact availability:** exact current model page exists; free tier is unsupported. Playground is linked, but the future organization's model entitlement was not exercised.
- **Image and output:** image input and Structured Outputs are explicit. Apply the identical two-class/four-state JSON contract and reject or retry malformed/semantically incomplete results.
- **Evidence/regions:** no detector-grade evidence/region guarantee was found. Any text explanation or coordinates are diagnostic only.
- **Revision pinning:** call exactly `gpt-5.6-terra`, never an unsuffixed moving family alias. The page calls it a snapshot but supplies no dated immutable identifier; log returned model metadata and run canaries.
- **Pricing:** $2/M input and $12/M output tokens. This is cheaper than Sol but costlier than primary Gemini 3.7.
- **Network/access:** public cloud API, working organization/project, billing, model entitlement, and egress are required. Actual regional access was not verified.
- **Privacy/retention:** API data is no-training unless opted in. Default abuse logs may persist up to 30 days; Responses application state may persist when stored. Confirm organizational ZDR/MAM settings and image-scanning exceptions before real site data.
- **Timeout/rate limit:** Tier 1 is 500 RPM and 500k TPM; limits rise by tier. No fixed latency/request-timeout guarantee was found. Apply client timeout, retry budget, and `not_analyzed` on exhaustion.
- **Fine-tuning:** explicitly unsupported for this exact model and unnecessary for the rapid first experiment.
- **Live-demo risk:** medium: exact model/interface docs are good, but no free tier, account entitlement, retention configuration, network, latency, and construction accuracy remain unverified.

## Experiment admission

Run only `gemini-3.7-flash` and `gpt-5.6-terra` on the same frozen, consent-cleared corpus, identical prompts/schema, identical image preprocessing, and identical retry/deadline policy. Record exact request model string, returned metadata, UTC timestamp, image hash, token usage, latency, retries, and raw response. Measure each class independently; separate semantic abstention (`insufficient_data`) from operational failure (`not_analyzed`). Do not use counts, confidence, or geometry in the decision rule.

## Contradictions and remaining gaps

1. Google's current general catalog and structured-output examples may mention `gemini-3.8-flash`, but the pricing page has no exact 3.8 Flash section while it does have 3.7 Flash and 3.8 Live. This unresolved documentation mismatch is why 3.8 Flash is not admitted.
2. No direct official precision/recall evidence exists for excavator or dump-truck recognition by either finalist.
3. Neither finalist offers a clearly dated immutable revision identifier in the exact retrieved page.
4. No fixed timeout, p95 latency, or guaranteed on-demand capacity was found.
5. Per-frame cost is unknown until actual image tokenization and reasoning-token use are measured.
6. Regional/account availability and data-control settings were not tested with the eventual credentials.
7. No guaranteed object-region evidence contract was found; regions cannot be relied on for audit or rules.

## Leads

- First live gate: list/get the exact model with the eventual credentials, send one synthetic non-sensitive frame, validate schema, log returned model/version, and read current quota/data controls.
- Use paid tiers for privacy evaluation; do not mistake free playground access for paid API data terms.
- Build the corpus around hard negatives, small/distant/occluded equipment, night/weather, empty/corrupt frames, and simultaneous classes.
- Pre-register pass/fail thresholds before comparing vendors. Do not promote Sol or Luna based on vendor tier names; add either only after measured Terra failure or cost pressure.

## Things searched but not found

- Official excavator/dump-truck metrics for Gemini 3.7 Flash or GPT-5.6 Terra/Sol/Luna.
- An exact `gemini-3.8-flash` pricing section matching its catalog mention.
- Dated immutable snapshot IDs for the two admitted candidates.
- Fine-tuning support for either admitted exact model.
- Detector-grade bounding-box/region guarantees for either admitted model.
- Fixed request timeout or contractual latency for ordinary API usage.
- Verified access in the actual experiment account, region, and billing tier.

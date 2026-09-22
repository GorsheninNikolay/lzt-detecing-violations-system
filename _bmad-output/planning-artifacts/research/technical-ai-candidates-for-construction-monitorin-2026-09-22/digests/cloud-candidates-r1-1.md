# Cloud multimodal candidates — round 1

**Research date / access date:** 2026-09-22  
**Decision served:** admit exactly one primary and one reserve cloud multimodal model to a later shared experiment. This digest does **not** select the final local/cloud/hybrid architecture.

## Scope and method

The required task is frame-level classification for two independent classes, `excavator` and `dump_truck`. Each class must be reduced by the application to one portable value: `detected`, `not_detected_in_frame`, `insufficient_data`, or `not_analyzed`. Provider-native counts, confidence scores, boxes, polygons, and other geometry are diagnostic evidence only and must not drive product rules.

I screened current first-party model catalogs and API documentation for OpenAI, Google/Gemini, Anthropic, and Azure/Vertex-hosted alternatives. Admission required image input, a usable API, constrained structured output, disclosed pricing, and enough privacy/retention evidence to plan a bounded experiment. Model-specific excavator/dump-truck accuracy was searched for but not found in the retrieved official material; therefore every accuracy expectation below is **experiment-only**. No project material or prior belief is used as evidence.

## Screened field

| Provider / candidate | Screen result | Reason |
|---|---|---|
| Google Gemini API — `gemini-3.8-flash` | **Admit as primary** | Current named model, image-priced input, JSON Schema structured output, low introductory price, paid-tier no-training statement, and AI Studio trial link. Main gaps: no immutable dated snapshot established; region/account access and construction-class accuracy require live checks. |
| OpenAI API — `gpt-5.6-sol` | **Admit as reserve** | Current flagship model with image input, Structured Outputs, explicit API no-training/default-retention terms, and independent provider diversity. Higher price and no immutable dated snapshot found. |
| Google Gemini — `gemini-3.5-flash-lite` / `gemini-3.1-flash-lite` | Cut | Cheaper, but official descriptions emphasize routine/simple high-throughput work. With no direct construction evidence, saving cost before measuring recall/abstention is premature. |
| Anthropic Claude 5 / 4.6 family | Cut from this round | Official deprecation page establishes active versions, but this bounded retrieval did not establish the complete model-specific chain for image input, strict structured output, pricing, privacy/retention, and live access. A candidate with incomplete decisive evidence is not admitted. |
| Azure model catalog wrappers | Cut | Adds deployment/region/account setup while the retrieved catalog privacy page does not establish a better model-specific MVP proposition. Could be reconsidered if organizational Azure residency is mandatory. |
| Vertex AutoML image object detection | Cut for this rapid generative-model experiment | It returns labels, confidence, and normalized boxes and requires a trained detector workflow. Those native signals cannot drive the portable rule contract, and training is outside a zero-/few-shot rapid comparison. |

## Claims and evidence

| Claim | Source URL | Publisher | Pub. date | Accessed | Confidence | Claim class |
|---|---|---|---|---|---|---|
| OpenAI's current catalog names `gpt-5.6-sol` as the flagship; the page lists image input support for latest models and prices Sol at $4/M input tokens and $20/M output tokens. | https://platform.openai.com/docs/models/gpt-4-turbo-and-gpt-4 | OpenAI | Undated live documentation | 2026-09-22 | High | Direct fact |
| OpenAI Structured Outputs supports schema-constrained output; the documented schema limits allow far more than the four required enum values. | https://developers.openai.com/api/docs/guides/structured-outputs | OpenAI | Undated live documentation | 2026-09-22 | High | Direct fact |
| OpenAI warns that vision models can make mistakes. This supports an explicit `insufficient_data` route and empirical evaluation, not an accuracy claim. | https://developers.openai.com/api/docs/guides/images-vision | OpenAI | Undated live documentation | 2026-09-22 | High | Direct fact + design inference |
| OpenAI API data is not used to train/improve models unless the customer opts in. Responses and Chat Completions show 30-day abuse-monitoring retention by default and are ZDR-eligible with documented limitations. | https://developers.openai.com/api/docs/guides/your-data | OpenAI | Policy effective statement includes 2023-03-01; live page otherwise undated | 2026-09-22 | High | Direct fact |
| OpenAI limits vary by model and are applied at organization/project level; actual account limits must be read from the developer console. | https://developers.openai.com/api/docs/guides/rate-limits | OpenAI | Undated live documentation | 2026-09-22 | High | Direct fact |
| OpenAI says model behavior changes between snapshots/families. Current fine-tuning is being wound down for new users; vision fine-tuning is documented only for `gpt-4o-2024-08-06`, not `gpt-5.6-sol`. | https://developers.openai.com/api/docs/guides/model-optimization | OpenAI | Undated live documentation | 2026-09-22 | High | Direct fact |
| Gemini API lists `gemini-3.8-flash` and introductory paid pricing through 2026-12-31 of $0.75/M input tokens and $3.75/M output tokens; the paid tier says submitted content is not used to improve products. | https://ai.google.dev/gemini-api/docs/pricing | Google | Undated live pricing | 2026-09-22 | High | Direct fact |
| Gemini pricing treats the model's standard input as multimodal, and the current catalog provides an AI Studio “try it” link. | https://ai.google.dev/gemini-api/docs/pricing | Google | Undated live pricing | 2026-09-22 | High | Direct fact |
| Gemini Structured Outputs supports a subset of JSON Schema including object, required fields, string enum, and `additionalProperties`; Google still tells clients to validate semantically. | https://ai.google.dev/gemini-api/docs/structured-output | Google | Undated live documentation | 2026-09-22 | High | Direct fact |
| Gemini API rate limits vary by model/tier, active limits are shown in AI Studio, and stated capacity is not guaranteed. | https://ai.google.dev/gemini-api/docs/rate-limits | Google | Undated live documentation | 2026-09-22 | High | Direct fact |
| On paid Gemini Developer API services, prompts/files/responses are not used to improve products; abuse-monitoring logging may still apply. Google directs workloads needing guaranteed ZDR or enterprise DPAs to Vertex AI. | https://ai.google.dev/gemini-api/docs/zdr | Google | Undated live documentation | 2026-09-22 | High | Direct fact |
| Vertex AI says customer data is not used to train/fine-tune managed models without permission; limited abuse logging can apply, and zero-retention may require an exception. In-memory caching has a 24-hour TTL. | https://docs.cloud.google.com/gemini-enterprise-agent-platform/resources/zero-data-retention | Google Cloud | Undated live documentation | 2026-09-22 | High | Direct fact |
| Gemini's Models API can return a model's version number and supported metadata, but the retrieved docs do not prove an immutable dated `gemini-3.8-flash` snapshot identifier. | https://ai.google.dev/api/models | Google | Undated live API reference | 2026-09-22 | Medium | Direct fact + documented gap |
| Claude's official deprecation table lists active Claude 5 and 4.6 versions and retirement floors, but does not by itself establish the complete multimodal/privacy/pricing chain needed here. | https://docs.anthropic.com/en/docs/about-claude/model-deprecations | Anthropic | Continuously updated; dated entries through 2026 | 2026-09-22 | High | Direct fact + screening decision |
| Vertex object detection returns labels, confidence, and normalized boxes. These outputs are unsuitable as portable business-rule inputs under this experiment's contract. | https://docs.cloud.google.com/vertex-ai/docs/image-data/object-detection/interpret-results | Google Cloud | Undated live documentation | 2026-09-22 | High | Direct fact + scope decision |

## Admitted candidate profiles

### Primary: Google Gemini API `gemini-3.8-flash`

- **Why admitted:** lowest evidenced price among the two finalists, current named model, accepts image-priced input, supports schema-constrained JSON, and has an official AI Studio trial path. This is admission to an experiment, not a claim that it recognizes construction machinery reliably.
- **Required output contract:** request exactly two class records with an enum restricted to `detected`, `not_detected_in_frame`, `insufficient_data`, `not_analyzed`; reject/retry syntactically invalid or semantically incomplete responses. Ignore all counts/confidences/geometry in decision logic.
- **Image evidence / regions:** no provider-guaranteed grounding region or detector-grade geometry contract was established for this model. If the model supplies a short textual observation or optional box, retain it only for evaluator inspection. Never use it to determine the portable status.
- **Revision pinning:** use the exact request string `gemini-3.8-flash` and log the Models API metadata/version with every run. An immutable dated snapshot was **not** established; rerun a canary before demos and record output drift.
- **Pricing:** $0.75/M input and $3.75/M output tokens through 2026-12-31 for standard paid usage. Image cost is tokenized, so measure actual token usage on the shared frame corpus rather than projecting from text alone.
- **Network / regional and account accessibility:** public cloud HTTPS/API-key path; therefore internet egress and a working billing/account region are prerequisites. Official pages show AI Studio/free and paid access, but this research did not verify availability from the eventual demo account or geography.
- **Privacy / use / retention:** use paid service only; paid content is not used to improve products. For construction imagery that requires guaranteed ZDR/DPA, use Vertex AI and obtain the needed abuse-monitoring exception rather than assuming the Developer API is zero-retention.
- **Timeouts / rate limits:** no model-specific request-timeout guarantee was found. Limits vary by tier and visible account state; client must set its own bounded timeout, exponential backoff for 429/5xx, and a per-frame `not_analyzed` result after exhausted retries. Read live limits immediately before the experiment.
- **Fine-tuning:** no model-specific fine-tuning support was established. It is **not needed for admission**: first measure zero-/few-shot performance on the shared labeled corpus. If error rates fail the agreed gate, revisit a trained detector or supported tuning product as a separate decision.
- **Live-demo risk:** medium. AI Studio offers a quick manual trial, but API key, paid-tier status, geography, capacity, alias drift, and network are unverified. Cache a fixed demo corpus and retain a prerecorded result path; do not misrepresent that fallback as live inference.

### Reserve: OpenAI API `gpt-5.6-sol`

- **Why admitted:** independent-provider reserve with current documented image input, strong schema control, clear default API data-use/retention documentation, and a current flagship model identifier. Its role is resilience and comparative evidence, not an assumed accuracy advantage.
- **Required output contract:** the same two-record enum-only JSON contract as the primary. Structured Outputs reduces syntax variance, but application validation and allowed-value enforcement remain mandatory.
- **Image evidence / regions:** vision can describe images but is explicitly fallible. No detector-grade evidence/region guarantee was established. Optional textual evidence may be logged for adjudication; counts, confidence, and geometry remain non-authoritative.
- **Revision pinning:** call `gpt-5.6-sol` exactly and record model identifiers returned by the API. The retrieved current model page exposed `gpt-5.6-sol` plus alias `gpt-5.6`, but did not expose an immutable dated Sol snapshot; avoid the moving alias and run a pre-demo canary.
- **Pricing:** $4/M input and $20/M output tokens, materially above the primary. Measure actual image-token accounting on the same corpus.
- **Network / regional and account accessibility:** public cloud HTTPS and an enabled OpenAI API organization/project are required. Data-residency support is region-, endpoint-, model-, and approval-dependent; the target demo account/region was not verified.
- **Privacy / use / retention:** API content is not used for training unless opted in. Responses/Chat Completions default to 30-day abuse-monitoring retention and are ZDR-eligible with limitations; image/file safety scanning has documented exceptions. Confirm the actual organization's data-control status before sending real site imagery.
- **Timeouts / rate limits:** no fixed request-timeout SLA was established. Limits are account/project/model dependent. Apply a client deadline, retry budget, and `not_analyzed` fallback; read current console limits before the run.
- **Fine-tuning:** `gpt-5.6-sol` vision fine-tuning is not documented. OpenAI says fine-tuning access is winding down for new users and documents vision tuning only for the older `gpt-4o-2024-08-06`. Therefore tuning is neither available evidence for this candidate nor required for the rapid MVP experiment.
- **Live-demo risk:** medium-high because cost is higher, account limits are variable, an immutable snapshot was not found, and account access was not exercised. Keep it as a reserve/API comparison rather than the sole stage demo dependency.

## Experiment admission decision

Admit **primary `gemini-3.8-flash`** and **reserve `gpt-5.6-sol`** only. Run both on the same frozen, consent-cleared frame set, same class definitions, same four-state schema, and the same client timeout/retry policy. Score per-class recall/precision plus abstention (`insufficient_data`) and operational failure (`not_analyzed`) separately. The experiment—not general vendor claims—must determine whether either is viable.

## Rejected candidates and cuts

- **Claude 5/4.6:** not rejected as incapable; rejected from this admission round because the bounded official-source retrieval did not complete decisive model-specific evidence for all required dimensions. This is an evidence-gap cut.
- **Gemini Flash-Lite variants:** cost-first alternatives, but no direct machinery evidence justifies risking quality before the baseline. Reconsider after the primary establishes an error/cost frontier.
- **Azure-hosted catalog models:** potentially useful for enterprise governance, but the retrieved evidence did not identify a uniquely better rapid-MVP model. Extra deployment/account setup raises demo risk.
- **Vertex AutoML object detection:** requires a labeled-training workflow and naturally exposes confidence/boxes. It belongs in a later trained-detector comparison, not this cloud foundation-model admission.

## Contradictions and gaps

1. Both finalists are marketed as current multimodal models, but neither retrieved catalog page proves direct excavator or dump-truck accuracy. No such accuracy claim is made here.
2. Both providers expose stable-looking model IDs, yet immutable dated revision pinning was not established for the exact finalists. Request-string pinning plus metadata logging is weaker than artifact immutability.
3. Pricing is token-based and image tokenization depends on image/detail handling. Per-frame cost cannot be responsibly stated before measuring the shared corpus.
4. Provider documentation describes variable account-tier rate limits, not guaranteed experiment throughput. Neither fixed p95 latency nor hard request timeout was found.
5. Google Developer API paid usage is no-training, but guaranteed ZDR/enterprise DPA points to Vertex AI; OpenAI has default 30-day abuse retention unless approved controls apply. Real construction imagery requires an account-specific privacy gate.
6. AI Studio provides an official trial path for Gemini, but regional/account availability was not exercised. A browser demo link is not proof that the planned API account works.
7. No authoritative guarantee of grounded regions/bounding boxes was found for either finalist. Any generated region is evaluator evidence only and may be absent or wrong.

## Leads for the shared experiment

- Before uploading real site frames, verify the exact project/account, billing tier, allowed geography, current rate limits, retention mode, and whether imagery contains people, plates, site plans, or other sensitive data.
- Capture request model string, provider-returned model/version metadata, UTC timestamp, image hash, schema version, latency, token usage, retry count, and raw response for every sample.
- Include hard negatives (other heavy equipment), partial/occluded vehicles, distant/small objects, night/weather, multiple machines, empty frames, corrupt images, and classes absent independently.
- Define the semantic boundary between `not_detected_in_frame`, `insufficient_data`, and `not_analyzed` before scoring. Provider refusal, timeout, rate limit, malformed output, and transport failure map to `not_analyzed`, not to absence.
- Disable provider-native confidence/count/geometry in downstream rules even if collected for diagnosis.

## Things searched but not found

- Official, model-specific excavator or dump-truck precision/recall for either finalist.
- Immutable dated snapshot IDs for `gemini-3.8-flash` or `gpt-5.6-sol`.
- Contractual detector-grade bounding boxes/regions for either finalist.
- Fixed API timeout and guaranteed latency/throughput for ordinary on-demand use.
- Verified availability from the future experiment's actual region, organization, billing tier, and credentials.
- Fine-tuning support for either exact finalist; current OpenAI evidence instead limits documented vision tuning to an older model and says new-user access is winding down.
- A complete, current official-source evidence chain sufficient to admit an Anthropic model within this bounded round.

# Cloud multimodal candidates — Russia/commercial gate, round 3

**Research/access date:** 2026-09-22  
**Decision served:** admit exactly one primary and one reserve cloud candidate under the new requirement: usable from Russia and usable in a commercial product. Previous Gemini/OpenAI recommendations are withdrawn; this round does not select the final local/cloud/hybrid winner.

## Decision

- **Primary — GigaChat API `GigaChat-2-Max`: officially contractable in Russia.** Official Sber documentation supports Russian legal entities and individual entrepreneurs, ruble invoicing/offer or contract, paid commercial use, image analysis, and strict JSON Schema output.
- **Reserve — Kimi API `kimi-k3`: test-only, conditional admission.** Official Kimi documentation supports image input and strict structured output and requires a successful minimum-$1 top-up. The retrieved official sources do **not** establish that Russian IPs, residents, bank cards, or Russian legal entities are accepted, nor do they establish Russian commercial contracting or data-retention terms. It may enter only a non-sensitive live account/billing canary; it cannot enter a commercial pilot until those gates pass in writing/account checkout.

No retrieved primary source reports excavator or dump-truck accuracy for either candidate. Both are experiment-only for the target classes.

## Scope and research firewall

Each image must yield two independent class results (`excavator`, `dump_truck`) and only one portable state per class: `detected`, `not_detected_in_frame`, `insufficient_data`, or `not_analyzed`. Counts, probabilities, boxes, regions, and provider-native geometry may be logged for diagnosis but cannot drive product rules.

The screen used only current provider documentation, tariffs, and contract pages. Website reachability is not evidence of account availability, payment acceptance, legal support, or commercial rights. Training-data or general benchmark claims are not used to infer machinery accuracy.

## Availability-status separation

| Status | Candidates | Meaning |
|---|---|---|
| **Officially contractable in Russia** | `GigaChat-2-Max` | Corporate offer explicitly addresses Russian legal entities/Russian individual entrepreneurs; service is paid in rubles, with Russian VAT/accounting documents. Paid use is the documented route for commercial use. |
| **Live-canary technically reachable, contractual status unverified** | `kimi-k3` — **canary not yet executed** | Official API endpoint, API-key flow, image example, Playground and $1 unlock are documented. A live Russian-IP signup/top-up/inference canary is still required. Successful inference would prove only technical/account reachability, not commercial rights for a Russian entity. |
| **Unavailable/unsupported under this evidence gate** | `kimi-k2.5`; prior Gemini/OpenAI candidates; Yandex/Cloud.ru candidates not qualified in this round | Kimi K2.5 was discontinued 2026-08-31. Gemini/OpenAI were withdrawn because this round has no official proof of Russia contracting/payment. Yandex/Cloud.ru are Russian-contractable platforms, but the retrieved sources did not establish one exact current image-understanding model with the complete model/version + structured-output chain needed for admission. This status means “unsupported by current evidence,” not necessarily network-blocked. |

## Claims table

| Claim | Source URL | Publisher | Pub. date | Accessed | Confidence | Claim class |
|---|---|---|---|---|---|---|
| GigaChat 2 Max accepts text, image, and audio input; it explicitly lists image analysis. The API request ID is `GigaChat-2-Max`. | https://developers.sber.ru/docs/ru/gigachat/models/gigachat-2-max | Sber Developers | Undated live model page | 2026-09-22 | High | Direct fact |
| The GigaChat file workflow accepts JPEG/PNG/TIFF/BMP images up to 15 MB, stores them privately by user/client ID, attaches them to generation requests, and provides an explicit delete endpoint. | https://developers.sber.ru/docs/ru/gigachat/guides/working-with-files | Sber Developers | Updated 2026-07-17 | 2026-09-22 | High | Direct fact |
| GigaChat supports strict JSON Schema output. Official examples use `GigaChat-2-Max`, `json_schema`, and `strict: true`; responses expose a runtime revision such as `GigaChat-2-Max:2.0.30.01`. | https://developers.sber.ru/docs/ru/gigachat/guides/structured-output | Sber Developers | Updated 2026-07-20 | 2026-09-22 | High | Direct fact |
| GigaChat's corporate offer defines the client as a Russian legal entity or Russian individual entrepreneur and accepts the agreement through invoice payment. | https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-prepaid | Sber / SDevices | Updated 2026-08-31 | 2026-09-22 | High | Direct fact |
| Corporate GigaChat payments are in Russian rubles; VAT and Russian accounting documents are addressed in the offer. | https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-prepaid | Sber / SDevices | Updated 2026-08-31 | 2026-09-22 | High | Direct fact |
| Paid commercial use is allowed; freemium content is personal/non-commercial only. | https://developers.sber.ru/docs/ru/gigachat/tariffs/commercial | Sber Developers | Updated 2025-12-10 | 2026-09-22 | High | Direct fact |
| GigaChat 2 Max corporate synchronous pay-as-you-go price is 0.65 RUB per 1,000 tokens including VAT, with a 600 RUB minimum in a month when the service is used; packages and contract/invoice routes are also listed. | https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs | Sber Developers | Updated 2026-09-16 | 2026-09-22 | High | Direct fact |
| The GigaChat corporate offer covers confidentiality and personal data of the client/representatives under Russian law, but the retrieved text does not state a concrete retention period or a no-training commitment for uploaded construction images. | https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-prepaid | Sber / SDevices | Updated 2026-08-31 | 2026-09-22 | High for stated terms; medium for gap | Direct fact + documented gap |
| Kimi's current model list names `kimi-k3` as a native visual-understanding model; `kimi-k2.5` was discontinued on 2026-08-31. | https://platform.kimi.ai/docs/models | Kimi / Moonshot AI | Undated live documentation | 2026-09-22 | High | Direct fact |
| Kimi K3 accepts base64 image input via the Moonshot API and supports strict JSON Schema structured output. | https://platform.kimi.ai/docs/guide/kimi-k3-quickstart | Kimi / Moonshot AI | Undated live documentation | 2026-09-22 | High | Direct fact |
| Kimi K3 unlocks after a successful top-up of at least $1; account tier determines rate limits. This does not prove that a Russian payment method or legal entity will be accepted. | https://platform.kimi.ai/docs/guide/kimi-k3-quickstart | Kimi / Moonshot AI | Undated live documentation | 2026-09-22 | High fact; high caveat | Direct fact + non-inference |
| Kimi Chat Completions is documented at `https://api.moonshot.ai/v1`, supports image messages and `json_schema`, is stateless for conversation history, and uses automatic cache entries with documented short TTL behavior. | https://platform.kimi.ai/docs/api/chat | Kimi / Moonshot AI | Undated live API reference | 2026-09-22 | High | Direct fact |
| Kimi's official pricing page describes token billing and tax-at-checkout but the retrieved page did not expose exact K3 numeric rates. | https://platform.kimi.ai/docs/pricing/chat | Kimi / Moonshot AI | Undated live pricing | 2026-09-22 | High | Direct fact + retrieval gap |
| Cloud.ru's Russian contract for Evolution Foundation Models covers pay-as-you-go multimodal token service and says locally hosted open models cannot send customer tokens outside its infrastructure, but the retrieved contract did not identify a complete exact image-understanding candidate for this experiment. | https://cloud.ru/documents/contracts/terms-of-service/evolution/foundation-models/description-foundation-models | Cloud.ru | Updated 2026-04-30; effective 2026-05-12 | 2026-09-22 | High | Direct fact + screening gap |

## Primary profile — `GigaChat-2-Max`

- **Russia/commercial status:** officially contractable for a Russian legal entity or individual entrepreneur. Use a paid corporate package or pay-as-you-go contract/invoice path; freemium must not be used for a commercial product.
- **Exact model/version:** request `GigaChat-2-Max`. Responses expose a more specific runtime revision string, but the retrieved documentation does not show how to request/pin that revision. Record it on every inference; treat the request ID as a moving alias and rerun canaries before demos.
- **Image input:** official model page lists image input and image analysis. Images are uploaded to the file store and attached to a generation request; supported formats and size limits are documented.
- **Structured output:** use strict JSON Schema with exactly two fixed class keys and a four-value enum. Validate application-side as well. Provider counts/confidence/geometry are ignored by business logic.
- **Excavator/dump-truck path:** zero-/few-shot frame classification through image analysis with explicit class definitions and abstention criteria. There is no direct official machinery benchmark, so performance must be measured on the shared labeled corpus.
- **Fine-tuning:** no official evidence of fine-tuning this exact multimodal model was found. It is not needed for the rapid test. If the baseline fails, evaluate a trained detector as a separate track.
- **Pricing/payment/account:** 0.65 RUB/1,000 tokens including VAT for synchronous corporate pay-as-you-go in the retrieved tariff, with the documented minimum charge rule. New-client routing to Cloud.ru after 2026-09-01 creates onboarding drift; confirm which contract/catalog exposes `GigaChat-2-Max` before purchase.
- **Privacy/data use/retention:** the corporate offer covers confidentiality and personal-data processing, and files can be explicitly deleted. No specific file retention period, no prompt/image no-training statement, and no construction-content processing region were found. Contract/security review and immediate file deletion after inference are mandatory before real site imagery.
- **Region/network:** provider is Russian and contracts with Russian entities; public API network access and provider certificates are required. Exact data-center region was not established.
- **Timeouts/limits:** fixed request timeout and account quotas were not established in the retrieved sources. Client must impose a deadline, bounded retries, and map exhausted provider/transport failures to `not_analyzed`.
- **Image evidence/regions:** no guaranteed detector-grade bounding boxes/regions were found. Optional explanations are evaluator-only.
- **Live-demo risk:** **medium-low relative to alternatives**, because Russia contracting and ruble payment are documented. Residual risks are onboarding migration to Cloud.ru, moving model revision, account quota, file retention, network, and unmeasured machinery accuracy.

## Reserve profile — Kimi API `kimi-k3` (test-only conditional)

- **Russia/commercial status:** official sources retrieved here do not prove support for Russian IPs, users, payment cards, or legal entities, and do not provide a Russian commercial contract. A successful technical canary is necessary but insufficient. Commercial pilot use remains blocked pending written terms/account eligibility.
- **Exact model/version:** current request ID is `kimi-k3`. No dated immutable API snapshot was found; log returned model metadata and rerun a frozen-corpus canary before every comparison.
- **Image input:** native visual understanding is documented; the exact quickstart sends a base64 image to `https://api.moonshot.ai/v1/chat/completions` with `model="kimi-k3"`.
- **Structured output:** strict `json_schema` is documented. Use the same two-class/four-state schema and application validation as the primary.
- **Excavator/dump-truck path:** zero-/few-shot image classification only. No direct construction-equipment accuracy evidence was found.
- **Fine-tuning:** no K3 API fine-tuning support was found. The published availability of open weights is not evidence that the managed API can be fine-tuned, and self-hosting is outside this cloud-candidate decision.
- **Pricing/payment/account:** the model requires a successful minimum-$1 top-up; numeric K3 rates were not recoverable from the rendered official pricing table in this round. Russian payment acceptance and tax/legal checkout must be tested with a non-sensitive account canary without evasion or foreign-person substitution.
- **Privacy/data use/retention:** Chat Completions is stateless for conversation history, but automatic prompt caching is documented. The retrieved official sources did not establish a no-training commitment, full prompt/image retention, deletion guarantees for inline images, cross-border processing regions, or a DPA suitable for a Russian commercial entity. Do not send real site imagery.
- **Region/network:** API endpoint is documented, but Russian network/IP availability has not been live-tested and official regional support is not stated.
- **Timeouts/limits:** tier-dependent RPM/TPM/concurrency is stated, but exact account values require successful top-up/account inspection. No fixed timeout SLA was found.
- **Image evidence/regions:** vision docs say the model understands shapes/visual content, not that it returns calibrated detector geometry. Any region or explanation is non-authoritative.
- **Live-demo risk:** **high** until signup, Russian-IP access, top-up, model listing, one image call, structured-output validation, privacy terms, and commercial contracting are all verified. Admit only to a non-sensitive technical test, never as a silent production fallback.

## Rejected/withdrawn candidates

- **Kimi K2.5:** officially discontinued on 2026-08-31; not a current candidate.
- **Kimi K2.6:** still documented for vision, but K3 is the current flagship and the model list directs discontinued K2.5 users to K3. With only one Kimi slot, use K3.
- **Gemini/OpenAI candidates from rounds 1–2:** withdrawn from recommendation. No official Russia account/payment/commercial contract evidence was established under the new gate.
- **Yandex AI Studio:** clearly a Russian commercial AI platform, but this bounded round did not establish one exact current synchronous multimodal model page that simultaneously proves image understanding, structured output, exact request ID/version, and pricing. Do not infer that YandexGPT text models accept images from general Model Gallery statements.
- **Cloud.ru Evolution Foundation Models:** credible Russian contract/privacy deployment alternative, but its contract allows changing model catalogs and this round did not obtain an exact qualifying multimodal model/interface chain. Keep as a procurement lead, not an admitted model.

## Required canaries and gates

### GigaChat commercial canary

1. Confirm whether the new account is purchased directly or through Cloud.ru and that `GigaChat-2-Max` is present in `GET /models`.
2. Confirm corporate paid tariff and commercial-use terms in the actual account/order.
3. Upload one synthetic, non-sensitive construction image; invoke strict schema; record returned runtime revision, latency, tokens, and quota headers; delete the file and verify deletion.
4. Obtain written answers for content retention, training use, processing location, incident handling, and DPA/security requirements before real images.

### Kimi non-sensitive technical canary

1. From the intended Russian network and actual future account owner, attempt signup, API-key creation, and lawful $1+ top-up. Do not bypass regional/payment restrictions.
2. List/confirm `kimi-k3`, call one synthetic image with strict JSON Schema, and record returned model string, latency, rate limits, and billing.
3. Separately obtain official written confirmation of Russian legal-entity eligibility, commercial API rights, content ownership, no-training/data-use rules, retention/deletion, processing regions, taxes, and support. Until then the result remains test-only.

## Contradictions and gaps

1. GigaChat's own tariff page routes new customers after 2026-09-01 to Cloud.ru, while its existing corporate tariff still lists direct model IDs and prices. Account/catalog readback is required.
2. GigaChat exposes a runtime revision in responses but documents only a generic request ID; immutable revision pinning is not established.
3. Kimi documents a global API and $1 top-up but does not, in retrieved official sources, say Russia is accepted. Reachability must not be mistaken for contractual support.
4. Kimi's rendered pricing table did not expose numeric K3 prices to the research extractor.
5. Neither candidate has direct official excavator/dump-truck metrics, calibrated confidence, or guaranteed region evidence.
6. Exact retention/no-training terms for construction image content are incomplete for GigaChat and absent from the retrieved Kimi sources.
7. Fixed request timeouts, p95 latency, and guaranteed ordinary capacity were not found.

## Things searched but not found

- Official excavator/dump-truck precision or recall for either candidate.
- A Kimi statement explicitly accepting Russian IPs, residents, bank cards, or Russian legal entities.
- Kimi commercial-use terms/DPA and complete prompt/image training-use and retention terms applicable to a Russian customer.
- Numeric K3 rates visible in the retrieved official pricing-page text.
- A dated immutable API snapshot for `kimi-k3` or a pinnable GigaChat 2 Max revision.
- Fine-tuning support for either exact managed multimodal API model.
- Guaranteed detector boxes/regions for either candidate.
- Exact GigaChat uploaded-file default retention period or explicit no-training commitment for customer images.
- One exact Yandex/Cloud.ru current multimodal model chain satisfying every required field within this bounded round.

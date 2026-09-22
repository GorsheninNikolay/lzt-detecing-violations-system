# RF cloud verifier — Kimi/Moonshot and GigaChat

Date checked: 2026-09-22 (Europe/Moscow)

Scope: official vendor API documentation, pricing, terms, privacy, model catalogue and change logs only. No inference from benchmarks, reputation, third-party aggregators, or training data. No authenticated live API call was possible in this pass.

## Bottom line

| Candidate | Image analysis + structured output | Commercial product right | Russia account/payment evidence | Immutable model revision | Verdict for a Russia-based product |
|---|---|---|---|---|---|
| Kimi API (`kimi-k3`, `kimi-k2.6`) | Officially documented | Generally permitted by Kimi terms | **Not established.** Terms impose sanctions/export restrictions; billing docs do not affirm Russia and consumer top-up is WeChat Pay/Alipay | **No documented requestable immutable revision** | Technically suitable on paper, but **not an approved Russia deployment dependency** until written eligibility/payment confirmation and an authenticated canary |
| GigaChat API (`GigaChat-2-Max`) | Officially documented | Paid use expressly permits commercial use | **Yes for Russian legal entities / individual entrepreneurs**, subject to provider acceptance; new customers since 2026-09-01 are directed to Cloud.ru | Response exposes a concrete served version, but docs only show an alias in requests; pinning is not established | Credible Russia-native reserve; still needs a paid-account image+JSON canary and data-governance acceptance |

The decisive disconfirmation is that `kimi-k2.5` and all `moonshot-v1-*-vision-preview` IDs are no longer current: Kimi says they were discontinued on 2026-08-31. Any design naming those models is stale.

## 1. Kimi / Moonshot API

### Current model IDs and capabilities

The official current model catalogue groups these under “Multi-modal Model”:

- `kimi-k3` — native visual understanding, 1M-token context.
- `kimi-k2.7-code` — code-focused, 256K context.
- `kimi-k2.7-code-highspeed` — same code model family, higher serving speed.
- `kimi-k2.6` — explicit visual and text input, 256K context.

For construction-image extraction, only `kimi-k3` and `kimi-k2.6` have first-party examples directly demonstrating general image understanding. The two K2.7 IDs are listed as multimodal but are code-specialized; their suitability for site-photo analysis requires a task canary, not inference from catalogue placement.

Official sources: [model list](https://platform.kimi.ai/docs/models), [Kimi K3 guide](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart), [Kimi K2.6 guide](https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart).

Discontinued IDs (do not use): `kimi-k2.5`; `moonshot-v1-8k`, `moonshot-v1-32k`, `moonshot-v1-128k`, `moonshot-v1-auto`, and their `-vision-preview` variants; the K2 preview/thinking family. The catalogue gives discontinuation dates and recommends K3. [Official model list](https://platform.kimi.ai/docs/models).

### API contract

- Base URL: `https://api.moonshot.ai/v1`.
- Chat endpoint: `POST https://api.moonshot.ai/v1/chat/completions`.
- Image input: an array-valued message `content` containing `{"type":"image_url","image_url":{"url":"data:image/...;base64,..."}}`; file references use `ms://<file_id>`. K3 explicitly does not accept public image URLs; use base64 or file ID.
- Structured output: `response_format` supports `json_object` and strict `json_schema`. K3’s guide provides a `strict: true` schema example; the JSON-mode guide says replacing the model with `kimi-k2.6` is supported, subject to model parameter differences.

Official sources: [Chat Completions API](https://platform.kimi.ai/docs/api/chat), [K3 image and strict-schema examples](https://platform.kimi.ai/docs/guide/kimi-k3-quickstart), [JSON mode](https://platform.kimi.ai/docs/guide/use-json-mode-feature-of-kimi-api), [parameter matrix](https://platform.kimi.ai/docs/api/models-overview).

### Pricing (current public pay-as-you-go display)

Prices are USD per 1M tokens, excluding applicable taxes:

| Model | Cache hit | Uncached input | Output | Cache write shown |
|---|---:|---:|---:|---:|
| `kimi-k3` | $0.30 | $3.00 | $15.00 | $3.00 |
| `kimi-k2.6` | $0.16 | $0.95 | $4.00 | not shown on the public landing-card excerpt |

Vision is token-billed; Kimi says image token use is dynamic and increases with resolution, and exposes a token-estimation API. The pricing documentation also distinguishes cache-write TTL tiers, so production costing must be measured with representative images rather than derived from image count alone.

Official sources: [Kimi API public pricing cards](https://platform.kimi.ai/), [pricing explanation](https://platform.kimi.ai/docs/pricing/chat), [K2.6 vision billing guidance](https://platform.kimi.ai/docs/guide/kimi-k2-6-quickstart).

### Commercial terms and IP

The Kimi OpenPlatform terms are expressly for businesses/developers. They grant a non-exclusive right to integrate the API into the customer’s own applications/products/services and offer those applications to end users. The customer retains ownership of input/output; Kimi disclaims uniqueness and accuracy and restricts some high-impact uses. This is adequate evidence of general commercial-product permission, not evidence that a Russia-based customer is eligible.

Official source: [Kimi OpenPlatform Terms, updated 2026-07-30](https://platform.kimi.ai/docs/agreement/modeluse).

### Data retention and training use

The default position is not acceptable to summarize as “no training / no retention”:

- The Terms say Moonshot may use customer content to provide, maintain, develop, support and improve the services; customers needing training/improvement restrictions should negotiate an enterprise arrangement or written agreement.
- The Privacy Policy says user content (including images/videos/files) is collected and may be used to train/refine underlying technology. Account, input and payment information are retained while the account is active; other periods are purpose- and law-dependent, with no fixed default API-content TTL stated.
- A newer ZDR page says enterprise data is not used for training by default, and requested ZDR deletes prompts/responses after inference. This is narrower than the general Terms and creates a contract/document hierarchy ambiguity that must be resolved in the signed enterprise order/DPA.
- ZDR explicitly cannot be guaranteed for images or videos submitted through direct file upload; operational/security/billing data is outside ZDR. For image workloads, base64 input may avoid the direct-upload carve-out, but that conclusion still needs written confirmation.

Official sources: [Terms, Content section](https://platform.kimi.ai/docs/agreement/modeluse), [Privacy Policy](https://platform.kimi.ai/docs/agreement/userprivacy), [ZDR](https://platform.kimi.ai/docs/guide/zero-data-retention).

### Russia eligibility, payment, and reachability

**Contractual availability: not established.** The terms require that a user not be subject to trade restrictions/sanctions and prohibit use/export/access in violation of US, Singapore, EU and other applicable sanctions, including comprehensively sanctioned regions or license-required use. They do not publish an affirmative supported-country list or specifically approve Russian individuals or entities. A Russian-language landing page is localization, not contractual eligibility.

**Payment: not established for Russia.** Individual top-up officially supports WeChat Pay and Alipay QR payments. Business payment may be online or bank transfer depending on account region and billing setup. No official source retrieved confirms Russian-issued cards, Russian bank transfer, ruble settlement, Russian tax documents, or onboarding of a Russian legal entity.

**Technical reachability: requires live canary.** The API hostname and endpoint are published, but unauthenticated network reachability would not prove account eligibility, model access, payment, image handling, or sustained production availability. Required canary: onboard the actual Russian contracting entity, top up through an approved method, then send one representative image to both `kimi-k3` and `kimi-k2.6` with strict JSON Schema and record HTTP status, response model field, latency, usage and billing.

Official sources: [Terms, eligibility/export and sanctions](https://platform.kimi.ai/docs/agreement/modeluse), [account and billing](https://platform.kimi.ai/docs/guide/account-and-payments).

### Revision immutability / provenance

No official documentation retrieved exposes a dated/snapshot ID for `kimi-k3` or `kimi-k2.6`, or promises that those IDs pin immutable weights. They are therefore floating product IDs for reproducibility purposes. Kimi’s request-signature endpoint can prove that the official API accepted a request for the exact **string** supplied in `model`; the documentation explicitly limits that proof and does not bind a weight/checkpoint revision. Signature verification is useful provenance, not model immutability.

Official source: [Verify Request Signature](https://platform.kimi.ai/docs/api/signatures-verify).

## 2. Russia-native reserve: GigaChat API

### Functional fit

`GigaChat-2-Max` is an official multimodal model with text/image/audio input, image analysis, a 128K context, functions, and text/image output. The REST API accepts uploaded image file IDs through `attachments`; one message may contain one image and one request up to ten images. File formats include JPEG, PNG, TIFF and BMP; one image is limited to 15 MB and the aggregate request with image/audio attachments to 80 MB.

Structured output is official: `POST /v1/chat/completions` and `/v2/chat/completions` support `response_format.type=json_schema`, schema and `strict=true`. The official example uses `GigaChat-2-Max` and returns a JSON string.

Official sources: [GigaChat 2 Max model card](https://developers.sber.ru/docs/ru/gigachat/models/gigachat-2-max), [chat endpoint/image limits](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat), [file formats and limits](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/files-storage), [structured output](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output).

### Endpoint, commercial availability, and price

- Current target base: `https://api.giga.chat`; chat is `POST /v1/chat/completions` (or v2). OAuth scopes include `GIGACHAT_API_B2B` for paid packages and `GIGACHAT_API_CORP` for pay-as-you-go.
- The corporate agreement defines the customer as a Russian legal entity or Russian individual entrepreneur and permits embedding the service in the customer’s own products/services for users (without reselling API credentials). Provider acceptance remains discretionary.
- Commercial use is allowed only after buying a paid service package; freemium output is personal/non-commercial.
- Published legacy/direct corporate pay-as-you-go for Max is 0.65 RUB per 1,000 tokens synchronous or 0.325 RUB asynchronous, VAT included, with a 600 RUB minimum charge in a used month. A 30M-token Max package is 19,500 RUB/month. Crucial transition: since 2026-09-01, new customers are directed to Cloud.ru for model purchase/pricing, so those direct tariffs should not be assumed for a new account without Cloud.ru readback.

Official sources: [authorization and endpoint](https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/gigachat-api), [corporate agreement](https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-beta), [commercial-use rule](https://developers.sber.ru/docs/ru/gigachat/tariffs/commercial), [corporate tariffs and Cloud.ru transition](https://developers.sber.ru/docs/ru/gigachat/tariffs/legal-tariffs).

### Data governance and immutable revision

The corporate agreement says customer content may be used only as needed to process it/provide the service and not for unrelated provider purposes; confidentiality survives five years. However, the retrieved official materials do **not** state a precise request/image retention period, a zero-retention mode, or an explicit “not used for model training” clause. They also say the agreement does not contemplate the customer transmitting personal or biometric data. Construction images must therefore be screened for people/faces/plates and the use case cleared contractually before production.

Requests use the alias `GigaChat-2-Max`; official response examples disclose a served version such as `GigaChat-2-Max:2.0.30.01`. The docs do not show that the colon-qualified version can be requested or guaranteed, while the agreement permits service/model updates. Treat the response version as audit metadata, not an immutable selectable revision.

Official sources: [corporate agreement, content rights and purpose limitation](https://developers.sber.ru/docs/ru/policies/gigachat-agreement/corporate-clients-beta), [structured-output response version](https://developers.sber.ru/docs/ru/gigachat/guides/structured-output), [model updates](https://developers.sber.ru/docs/ru/gigachat/models/updates).

## 3. Required gates before selection

1. **Kimi legal/payment gate:** obtain written Moonshot confirmation that the exact Russian person/entity may contract, pay and use the API commercially under the sanctions clause; obtain accepted payment/tax-document path.
2. **Kimi data gate:** signed enterprise terms/DPA must resolve the conflict between general Terms and the ZDR page, forbid training/improvement use, state retention/deletion for base64 image input, subprocessors and processing locations.
3. **Authenticated Kimi canary:** representative construction image + strict JSON Schema on `kimi-k3` and `kimi-k2.6`; record model ID, request signature, usage, price and errors. A mere HTTP handshake is insufficient.
4. **GigaChat commercial gate:** read back the actual Cloud.ru offer/tariff for a new Russian entity; confirm the exact model ID and image billing.
5. **GigaChat data gate:** written retention/training and personal-data treatment, especially images containing people, faces, vehicle plates or location metadata.
6. **GigaChat canary:** upload/delete lifecycle plus `GigaChat-2-Max` image analysis with strict schema; record response `model` revision and verify schema adherence.

## Evidence classification

- **Officially supported:** both vendors document image input and structured output; both generally allow paid commercial integration. GigaChat explicitly contracts with Russian legal entities/IPs.
- **Requires live canary:** actual endpoint reachability from the deployment network, account/model entitlement, image-quality fitness, strict-schema reliability, latency, rate limits and billed cost.
- **Unsupported / not established:** Kimi onboarding/payment for Russian users/entities; immutable Kimi snapshot IDs; requestable immutable GigaChat revisions; fixed default Kimi content TTL; GigaChat request/image retention and explicit training exclusion.


# Qwen3.6 target and annotation authorization

Owner decision, 2026-09-26: use Qwen3.6 for preliminary labels of the100 organizer images and target Qwen3.6 for all model analysis. This supersedes the local-vs-cloud selection direction for the target release; Grounding DINO results remain historical comparisons. No historical profiles or analyses are rewritten.

The owner approved a separate limit of1000RUB for this new annotation run from an account balance they reported as8000RUB. This does not authorize other infrastructure spending or imply a measured billing balance. Previous experimental spend is outside this newly approved batch budget.

Use the selected `qwen3.6-35b-a3b` model through Yandex AI Studio. Proposed labels and boxes must remain machine suggestions until reviewed. The user has authorized upload of the current organizer corpus for this task. Keep source hashes, raw model responses, usage, prompt/schema identity, and reviewer decisions distinct. Preserve old annotation files and browser progress.

Execution: a five-image pilot, inspect returned classes/boxes and usage, then resume the remaining images if valid. A persistent SQLite ledger reserves conservative maximum request cost before every call; unknown/aborted attempts retain their reserve and are never automatically retried. No cache discount is assumed for the reservation. API keys remain transient and are deleted after the run.

Published tariff checked in this conversation:0.20RUB/1000input tokens and0.30RUB/1000output tokens including VAT. Context ceiling262144 and max_output_tokens4096 give a deliberately loose reserve53.6576RUB per request. Settled usage is a tariff calculation, not billing-statement verification.

Sources:
- https://aistudio.yandex.ru/ru/docs/ai-studio/pricing
- https://aistudio.yandex.ru/ru/docs/ai-studio/concepts/generation/models
- https://aistudio.yandex.ru/ru/docs/ai-studio/operations/generation/multimodels-request-responses

The earlier requirement for a separately accepted local Grounding DINO release is superseded by the owner’s Qwen-first direction; local application startup can still use the cloud model and therefore requires network access. Offline local inference is no longer the target of this increment.

The current production adapter only supports two-class presence and remains blocked pending its own implementation and budget integration. This annotation runner does not activate a new production profile. Extended model acceptance, independently justified evaluation groups, and deployment are still separate release gates.

## Superseding owner decision: DeepSeek comparison

The owner clarified DeepSeek V4.1 Flash (not V4 Flash), authorized a separate400RUB ceiling and overall1000RUB ceiling for the run, and requested two reasoning modes to balance latency and quality. Stop new Qwen calls. The only paid Qwen work so far is three calls with0.9178RUB computed usage; one response failed semantic validation and no automatic retry occurred.

Target a ten-image paired comparison of no reasoning versus moderate reasoning, only where the Yandex endpoint supports those modes and genuine image input. Verify provider-returned model identity and image capability before any batch. Existing evidence and ground truth remain separate. V4.1 is listed in the current account, but published Yandex documentation says subscription-only through27September2026, token billing from28September. No subscription purchase is authorized. An explicit API denial is a blocker, not permission to select another model/provider or buy a subscription.

DeepSeek published rates:0.30RUB/1000input and0.50RUB/1000output including VAT. Reserve full1,048,576 input context plus4096maximum output:316.6208RUB before a request, settle known usage, retain uncertain outcomes. This deliberately loose reserve may prevent completing a batch under400RUB despite low expected usage; do not weaken it without a verified tighter input bound.

## Verified DeepSeek access and first-ten scope

Despite the published subscription-only notice, a real request on2026-09-26 succeeded through the owner's Yandex account without any subscription purchase: returned model `deepseek-v4.1-flash/latest`, reasoning.effort `none`, reasoning_tokens0. The preflight frame023 used1922 input/220 output tokens,5.504084seconds and0.6866RUB tariff-calculated usage. This observed access takes precedence over the earlier documentation-only assumption for this account.

Owner narrowed the next step to the first10 frames in original order. Run only organizer-png-001 through010 with none; stop after presenting results. Do not process the remaining90 or second reasoning mode before discussing observed quality with the owner. Keep preflight frame023 separate from the ten-frame result.

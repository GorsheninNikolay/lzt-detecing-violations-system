# Yandex Cloud cost and image-model assessment — 2026-09-24

## Evidence and access

- CLI: `yc` updated from 0.135.0 to 1.37.0. The active `default` profile points to cloud `b1g74p2d0h7jtvfj5uqc` and folder `b1gcpjp9nc4hhoffpf3a`. Read-only cloud, folder, VM, disk, network, IAM, and Models API calls succeeded without a GUI outside the restricted network sandbox. Inside the sandbox, `yc resource-manager folder get ... --retry 0` returned `error dialing endpoint 'api.cloud.yandex.net:443': context deadline exceeded`.
- Billing CSV: `/Users/gorshenin-nik/Downloads/20260624-20260924.csv`, SHA-256 `9bb80b219de2887f58a229840e38c2a53f99b1de07344f05e8bb9c1f6a522c9f`, exported 2026-09-24 15:22:34 UTC. It has 988 rows, one billing account (`dn2r9rlvblv7hnab3tmm`), one folder, RUB, and daily SKU-level charges from June 24 through September 24 inclusive (93 days). It has **no resource ID column**.
- BillingAccount REST API returned `active: true` and `balance: 7.02` RUB. This is the personal account balance, **not the grant balance**. Owner-provided Billing screenshots on September 24 show an **active grant, 8,392 RUB remaining of 18,000 RUB, valid September 2–October 2, 2026**. The only three excluded services are BareMetal, BareMetal Custom, and BareMetal GO; AI Studio is covered. The screenshots' capture time and grant balance at later calls are unknown. [BillingAccount API](https://yandex.cloud/en/docs/billing/api-ref/BillingAccount/list); [grant semantics](https://yandex.cloud/en/docs/billing/concepts/bonus-account).

## Charges and grant use

Amounts below sum unrounded CSV decimals and then round to kopecks; displayed rounded rows can differ from displayed totals by 0.01 RUB.

| Period | Gross charges | Grant credit | Other credits | Final expense |
| --- | ---: | ---: | ---: | ---: |
| Full CSV, 93 days | 38,935.51 | -38,935.51 | 0.00 | 0.00 |
| Requested latest 90 days, June 27–September 24 | 37,716.73 | -37,716.73 | 0.00 | 0.00 |
| July | 12,774.70 | -12,774.70 | 0.00 | 0.00 |
| August | 13,076.69 | -13,076.69 | 0.00 | 0.00 |
| Latest 30 days, August 26–September 24 | 12,853.56 | -12,853.56 | 0.00 | 0.00 |

The CSV `credit` equals `monetary_grant_credit` in every aggregate; volume incentive, committed-use discount, and miscellaneous credit columns sum to zero. Thus the observed invoice expense is zero while the grant is consumed by the gross charges. The separate screenshot confirms the grant remainder at capture. At the latest 30-day rate, 8,392 RUB would cover about **19.6 days**, but the **October 2 expiry comes first**: approximately 3,427.62 RUB would be consumed over eight days at this rate, leaving roughly 4,964 RUB unused if spending and terms stay unchanged. These are projections, not a live billing balance.

| Service, latest 90 days | Gross RUB | Share |
| --- | ---: | ---: |
| Compute Cloud | 31,593.24 | 83.8% |
| Virtual Private Cloud | 6,123.48 | 16.2% |
| Cloud DNS | 0.00 | 0% |

The latest 30-day gross rate is 428.45 RUB/day. Its SKU breakdown is 5,371.75 RUB for vCPU, 2,403.58 RUB for RAM, 2,699.18 RUB for SSD, 1,720.41 RUB for outbound traffic, 376.42 RUB for public IPs, and 282.24 RUB for NAT. Inbound traffic and DNS are zero. Resource-level attribution below is an **estimate**, because the CSV lacks IDs; the two VM platforms and disk capacities in the live inventory match the distinct billing quantities.

## Ranked savings candidates

Live inventory: `my-own-machine` is running on AMD Zen 4 with 4 vCPU/8 GiB RAM, a 160 GiB network SSD and one reserved public IPv4. `openvpn-own-machine` is running on Intel Ice Lake with 2 vCPU/2 GiB RAM, a 30 GiB network SSD and one reserved public IPv4. There is one NAT gateway. Its default route is attached to `default-obs-subnet-a`, the subnet of `my-own-machine`. The two VM purposes are inferred from names; actual traffic, users, and workloads were not measured.

| Rank | Candidate | Estimated 30-day reduction | Impact and prerequisite | Check after an approved change |
| --- | --- | ---: | --- | --- |
| 1 | Stop `my-own-machine` when its workloads can be paused | 5,532.36 RUB for vCPU and RAM | Stops everything hosted there. Its disk and reserved IP continue to accrue charges. Verify active services, access paths, and recovery first. | VM state `STOPPED`; daily AMD CPU/RAM charges cease; disk/IP rows persist. |
| 2 | Stop `openvpn-own-machine` if VPN access is no longer needed | 2,242.96 RUB for vCPU and RAM | Breaks VPN connectivity; verify clients and alternative access first. Disk/IP remain billable. | VM state `STOPPED`; daily Intel CPU/RAM charges cease. |
| 3 | Rebuild the 160 GiB boot disk at 64 GiB after measuring used space | About 1,363.79 RUB | Capacity reduction requires recreation/migration and a validated restore path. It cannot be shrunk in place. | New 64 GiB disk attached; old disk retired only after recovery check; SSD daily charge falls by ~96/190. |
| 4 | Investigate 1,311.56 GiB outbound traffic in the latest 30 days | Up to 1,720.41 RUB | Source and necessity are unknown; do not treat the whole amount as removable. Attribute by VM/network traffic and application logs first. | Daily outbound GiB and charges fall without loss of required traffic. |
| 5 | Remove the NAT gateway after replacing/removing its subnet route | 282.24 RUB | Despite near-zero billed NAT egress, `default-obs-subnet-a` still has a default route to this gateway. Removing it first would break private egress. | Route table no longer points to gateway; private egress test passes; NAT hourly charge stops. |
| 6 | Release a no-longer-needed reserved public IPv4 | ~188.21 RUB per address at the observed active rate | Breaks inbound access and may alter allowlists. A stopped VM's reserved IP may cost **more** than this active-rate estimate. | Address is absent; related daily IP charge stops or changes as predicted. |

The estimated 30-day whole-resource cost of `my-own-machine` is 7,993.56 RUB (compute 5,532.36 + allocated SSD 2,272.99 + half the public-IP charge 188.21). For `openvpn-own-machine` it is 2,857.36 RUB (compute 2,242.96 + allocated SSD 426.19 + IP 188.21). SSD split uses 160/190 and 30/190 GiB, and IP split uses two equally active addresses. These are not savings from merely stopping the VMs. Outbound traffic and NAT are separate. [Stopped VM and disk billing](https://yandex.cloud/en/docs/compute/pricing); [public IP billing](https://yandex.cloud/en/docs/vpc/pricing); [boot-disk downsizing](https://yandex.cloud/en/docs/troubleshooting/compute/how-to/shrink-instance-disk).

No cloud resources were stopped, resized, released, or deleted.

## AI Studio decision

The folder's live Models API lists 28 models. The only listed model with current documented image input is `gpt://b1gcpjp9nc4hhoffpf3a/qwen3.6-35b-a3b/latest`; the documented family URI omits `/latest`. Historical VL models appear in batch pricing but are not in this folder's synchronous Models API list. Qwen3.6 accepts Base64 images via Responses API and returns text or structured output. Its synchronous RUB price is 0.20 per 1,000 input tokens, 0.05 per 1,000 cached tokens, and 0.30 per 1,000 output tokens, VAT included. The image's token count and actual cost per frame must be measured from the response; image size alone does not establish it. [Model catalog](https://aistudio.yandex.ru/en/docs/ai-studio/concepts/generation/models); [image request](https://aistudio.yandex.ru/ru/docs/ai-studio/operations/generation/multimodels-request-responses); [pricing](https://aistudio.yandex.ru/ru/docs/ai-studio/pricing).

Created isolated service account `construction-vlm-eval` (`ajevni98nioe4p94isa1`) and verified it has only folder role `ai.languageModels.user`. An earlier `ai-studio-9ec493` account has broader `ai.editor`, MCP, workflow and search roles and an existing expiring key; it was left untouched and was not used for this experiment. Trial keys were restricted to `yc.ai.foundationModels.execute`, expired September 26, existed only in process memory, and were deleted after each run. Final `yc iam api-key list` returned `[]` for the evaluation account. [API-key scopes](https://yandex.cloud/en/docs/iam/concepts/authorization/api-key).

User permission to upload the four admission frames to AI Studio was obtained on September 24. Their manifest documents CC0 and prior **local-only** prototype approval; the additional cloud-upload permission is in the conversation, not the manifest. The isolated evaluation adapter requests `store: false` and `x-data-logging-enabled: false`, does not log API keys or images, and turns invalid output and transport timeout into terminal errors. `store: false` prevents 30-day Responses context retention; the logging header excludes improvement logging, but service/audit logs and other API handling still apply. [Data retention](https://aistudio.yandex.ru/ru/docs/ai-studio/concepts/security/data-storage); [disable logging](https://aistudio.yandex.ru/ru/docs/ai-studio/operations/disable-logging).

### Same-frame pilot, September 24

One first prompt-only response was rejected by the strict parser. A diagnostic repeat returned Markdown-fenced JSON. The final pilot therefore used a `construction_presence` JSON schema with exactly two boolean fields. The first frame was run once with that schema before the complete four-frame run; both structured responses agreed. The diagnostic call reported 2,098 input and 85 output tokens, equivalent to about 0.4451 RUB at published rates. The first rejected call's usage was not captured, so its cost is unknown. Prices below are **estimates from response tokens and tariff**, not post-billing readback.

The raw structured model response and the manifest labels appear together below. `E` = excavator, `D` = dump truck. Latency is wall time for the HTTPS call; local latency is `GroundingDinoCpu.observe()` on the same Apple M3 Pro CPU with the pinned `IDEA-Research/grounding-dino-tiny` revision `e08274d3760f8fcfc53dcbb9ca3ed0a29fa9c40e`, model loaded once before the four calls. It excludes local model loading; the cloud figure includes network time.

| Fixture prefix | Label | Qwen JSON response | Qwen miss / false detection | Qwen latency | Input / cached / output tokens | Estimated RUB | Response ID | Grounding DINO result | Local latency |
| --- | --- | --- | --- | ---: | --- | ---: | --- | --- | ---: |
| `1235` | E+D | `{"dump_truck":true,"excavator":true}` | none | 13.08 s | 2,082 / 2,048 / 1,704 | 0.6204 | `7a383ba1-3736-463e-bd60-7c724f4522ba` | E+D, correct | 2.86 s |
| `1233` | D | `{"dump_truck":false,"excavator":true}` | miss D, false E | 9.60 s | 4,074 / 0 / 619 | 1.0005 | `c685c648-626e-4649-962b-79b18f56d9a0` | E+D, false E | 2.14 s |
| `1422` | E | `{"dump_truck":false,"excavator":true}` | none | 53.91 s | 4,074 / 0 / 9,112 | 3.5484 | `1e475cc9-4ce4-40de-bac6-5f1287f37785` | E+D, false D | 2.12 s |
| `1325` | neither | `{"dump_truck":false,"excavator":false}` | none | 3.91 s | 2,082 / 0 / 175 | 0.4689 | `da2433a8-9f51-4448-9ad2-5f9dfe01c40b` | E, false E | 1.97 s |

Qwen was exact on 3/4 frames: one missed class and one false detection, both on `1233`. Grounding DINO was exact on 1/4: no missed classes and three false detections. Cloud median latency was 11.34 s (range 3.91–53.91 s), against 2.13 s (range 1.97–2.86 s) for the already-loaded local model. The four cloud calls used an estimated **5.6382 RUB**, or 1.4096 RUB/frame; another structured repeat of `1235` cost an estimated 0.4422 RUB and took 1.85 s. One Qwen response used 9,112 output tokens for a two-boolean JSON result, making response latency and cost highly variable. The local result has secondary boxes/scores; Qwen provides presence booleans but no geometry. Both can map to the presence-only portable class states, while provider-native evidence remains separate.

**Decision:** do not create or activate a production `cloud_api` observer profile. Neither candidate met the zero-false-warning requirement on these four smoke frames, and this set is not the planned independent 11-image evaluation. Qwen's prompt/schema and reasoning settings require a separately versioned evaluation if revised. The existing local profile remains unchanged; no winner is selected. The paid pilot also does not establish the post-billing grant debit yet.

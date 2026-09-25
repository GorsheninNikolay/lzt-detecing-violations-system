"""Byte-free, ordered comparison campaign plan."""

import math

from app.domain.evaluation_set import EXPECTED_SCENARIOS, SCENARIOS
from app.domain.observations import CLASSES
from app.domain.rule import RULE, RULE_POLICY
from app.profiles import cloud_api, grounding_dino


class CampaignGateError(RuntimeError):
    pass


def build_manifest(revision: dict, local: dict, cloud: dict) -> dict:
    frames = revision.get("frames")
    scenarios = revision.get("scenarios")
    if (not isinstance(frames, list) or len(frames) != 11
            or [frame.get("scenario") for frame in frames] != SCENARIOS
            or scenarios != {name: {"expected_outcome": outcome, "requested_classes": classes}
                             for name, (outcome, classes) in EXPECTED_SCENARIOS.items()}):
        raise CampaignGateError("evaluation_contract_invalid")
    if (local.get("kind") != "local_process" or local.get("adapter", {}).get("code") != "grounding_dino"
            or local.get("requested_model_identity") != {"id": grounding_dino.MODEL_ID,
                                                            "revision": grounding_dino.MODEL_REVISION}
            or local.get("runtime", {}).get("os") != "Darwin"
            or local.get("runtime", {}).get("architecture") != "arm64"
            or local.get("runtime", {}).get("device") != "cpu"
            or local.get("runtime", {}).get("cpu_cores") != 12
            or local.get("runtime", {}).get("memory_bytes") != 36 * 1024**3
            or local.get("runtime", {}).get("driver") != "PyTorch CPU"
            or cloud.get("kind") != "cloud_api"
            or cloud.get("adapter", {}).get("code") != "yandex_ai_studio"
            or cloud.get("requested_model_identity", {}).get("id") !=
                f"gpt://{cloud.get('folder_id')}/{cloud_api.MODEL}"):
        raise CampaignGateError("candidate_identity_invalid")
    for profile in (local, cloud):
        runtime = profile.get("runtime", {})
        if (runtime.get("concurrency") != 1 or runtime.get("sdk_retries") != 0
                or any(not isinstance(runtime.get(key), (int, float))
                       or isinstance(runtime[key], bool) or not math.isfinite(runtime[key])
                       or runtime[key] <= 0
                       for key in ("per_image_timeout_seconds", "batch_timeout_seconds"))):
            raise CampaignGateError("candidate_runtime_invalid")
    fixtures = []
    for scenario in dict.fromkeys(SCENARIOS):
        selected = [frame for frame in frames if frame["scenario"] == scenario]
        contract = scenarios[scenario]
        if any(frame.get("ordinal") != ordinal or frame.get("context", {}).get("expected_outcome") != contract["expected_outcome"]
               or frame["context"].get("requested_classes") != contract["requested_classes"]
               or frame["context"].get("analysis_intent") !=
                    ("excavation_rule" if scenario.endswith("_series") else "observations_only")
               or not frame["context"].get("observation_area")
               or not isinstance(frame.get("image", {}).get("sha256"), str)
               for ordinal, frame in zip((i for i, f in enumerate(frames) if f["scenario"] == scenario), selected)):
            raise CampaignGateError("evaluation_frame_invalid")
        fixtures.append({"ordinal": len(fixtures), "scenario": scenario,
            "expected_outcome": contract["expected_outcome"],
            "requested_classes": contract["requested_classes"],
            "frames": [{"ordinal": frame["ordinal"], "id": frame["id"],
                        "image": frame["image"], "context": frame["context"]} for frame in selected]})
    if sorted(frame["ordinal"] for fixture in fixtures for frame in fixture["frames"]) != list(range(11)):
        raise CampaignGateError("evaluation_frame_invalid")
    return {"schema_revision": "comparison-campaign-v1", "repeats": 3,
        "concurrency": 1, "sdk_retries": 0,
        "candidates": [{"ordinal": 0, "kind": "grounding_dino", "snapshot": local},
                       {"ordinal": 1, "kind": "qwen3.6", "snapshot": cloud}],
        "fixtures": fixtures, "rule": RULE, "rule_policy": RULE_POLICY,
        "observation_policy": {"intent": "observation_only", "revision": "observations-only-v1"},
        "taxonomy": {"portable_classes": list(CLASSES), "revision": "presence-only-v1"}}

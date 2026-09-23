import hashlib
import json


def revisioned_snapshot(kind: str, snapshot: dict) -> dict:
    content = {key: value for key, value in snapshot.items() if key != "revision"}
    canonical = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return {**content, "revision": f"{kind}-{hashlib.sha256(canonical.encode()).hexdigest()}"}


RULE = revisioned_snapshot("rule", {
    "name": "Проверка вывоза грунта на этапе земляных работ",
    "expectation": "Экскаватор работает постоянно, самосвалы появляются периодически.",
    "provenance": "demonstration rule",
    "recommendation": "Проверить организацию вывоза грунта на участке вручную.",
    "required_activity_class": "excavator",
    "periodic_arrival_class": "dump_truck",
})
RULE_POLICY = revisioned_snapshot("policy", {
    "minimum_usable_same_area_frames": 3,
    "classes": ["excavator", "dump_truck"],
    "admission": "supported_decodable_images",
    "supported_media_types": ["image/jpeg"],
    "frame_order": "upload_order",
    "area_scope": "one_declared_observation_area",
    "unassessable_frame": "insufficient_data",
    "observer_inability": "insufficient_data",
    "image_quality_threshold": None,
    "subjective_resolution_threshold": None,
    "visibility_threshold": None,
    "object_size_threshold": None,
    "cadence_threshold": None,
    "duration_threshold": None,
    "miss_rate_threshold": None,
    "false_detection_threshold": None,
    "stability_threshold": None,
})
ANALYSIS_CHOICES = {"stages": [
    {"id": "excavation", "label": "Земляные работы", "rule": RULE},
    {"id": "other", "label": "Другой этап", "rule": None},
]}


def evaluate_rule(frames: list[dict], usable_ids: list[str], policy: dict, rule: dict,
                  context: dict) -> dict:
    states = {(str(item["input_id"]), item["class_name"]): item["state"] for item in frames}
    excavator, dump_truck = rule["required_activity_class"], rule["periodic_arrival_class"]
    if any(item["state"] == "insufficient_data" and item["class_name"] in policy["classes"]
           for item in frames):
        outcome, reason = "insufficient_data", "Наблюдатель не смог оценить один из обязательных классов техники."
    elif len(usable_ids) < policy["minimum_usable_same_area_frames"]:
        minimum = policy["minimum_usable_same_area_frames"]
        outcome, reason = "insufficient_data", f"Для проверки правила нужны минимум {minimum} пригодных кадров одной зоны."
    elif any((input_id, name) not in states or states[input_id, name] == "not_analyzed"
             for input_id in usable_ids for name in policy["classes"]):
        outcome, reason = "not_analyzed", "Один из обязательных классов техники не анализировался."
    elif (any(states[input_id, excavator] == "detected" for input_id in usable_ids)
          and any(states[input_id, dump_truck] == "detected" for input_id in usable_ids)):
        outcome, reason = "no_check", "Самосвал обнаружен в пригодной серии; запрос проверки не сформирован."
    elif (all(states[input_id, dump_truck] == "not_detected_in_frame" for input_id in usable_ids)
          and any(states[input_id, excavator] == "detected" for input_id in usable_ids)):
        outcome, reason = "check_requested", "Экскаватор обнаружен, самосвал не обнаружен ни в одном пригодном кадре."
    else:
        outcome, reason = "insufficient_data", "Наблюдения не подтверждают работу экскаватора для оценки вывоза грунта."
    return {"outcome": outcome, "reason": reason, "rule": rule, "policy": policy,
            "context": context, "supporting_input_ids": usable_ids if outcome == "check_requested" else [],
            "uncertainty": "Необнаружение в кадре не доказывает отсутствие техники на всей площадке.",
            "recommendation": rule["recommendation"] if outcome == "check_requested" else None}

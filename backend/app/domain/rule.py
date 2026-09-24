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
    unassessable_ids = list(dict.fromkeys(str(item["input_id"]) for item in frames
        if item["state"] == "insufficient_data" and item["class_name"] in policy["classes"]))
    unsupported_ids = list(dict.fromkeys(str(item["input_id"]) for item in frames
        if item["state"] == "not_analyzed"))
    missing_required = any((input_id, name) not in states
                           for input_id in usable_ids for name in policy["classes"])
    if unsupported_ids or missing_required:
        outcome, reason = "not_analyzed", ("Запрошенный класс техники не анализировался; проверка правила недоступна. "
            f"Затронутые кадры: {', '.join(unsupported_ids)}." if unsupported_ids else
            "Один из обязательных классов техники не анализировался; проверка правила недоступна.")
    elif unassessable_ids:
        outcome, reason = "insufficient_data", ("Наблюдатель не смог оценить один из обязательных классов техники "
            f"в кадрах: {', '.join(unassessable_ids)}.")
    elif len(usable_ids) < policy["minimum_usable_same_area_frames"]:
        minimum = policy["minimum_usable_same_area_frames"]
        outcome, reason = "insufficient_data", f"Для проверки правила нужны минимум {minimum} пригодных кадров одной зоны."
    elif (any(states[input_id, excavator] == "detected" for input_id in usable_ids)
          and any(states[input_id, dump_truck] == "detected" for input_id in usable_ids)):
        outcome, reason = "no_check", "Самосвал обнаружен в пригодной серии; запрос проверки не сформирован."
    elif (all(states[input_id, dump_truck] == "not_detected_in_frame" for input_id in usable_ids)
          and any(states[input_id, excavator] == "detected" for input_id in usable_ids)):
        outcome, reason = "check_requested", ("Есть повод проверить возможную задержку вывоза грунта: "
            "экскаватор обнаружен хотя бы в одном пригодном кадре, самосвал не обнаружен ни в одном пригодном кадре.")
    else:
        outcome, reason = "insufficient_data", "Наблюдения не подтверждают работу экскаватора для оценки вывоза грунта."
    supporting_ids = []
    if outcome == "check_requested":
        supporting_ids = usable_ids
    elif outcome == "no_check":
        supporting_ids = [input_id for input_id in usable_ids
                          if states[input_id, excavator] == "detected" or states[input_id, dump_truck] == "detected"]
    return {"outcome": outcome, "reason": reason, "rule": rule, "policy": policy,
            "context": context, "supporting_input_ids": supporting_ids,
            "uncertainty": "Необнаружение в кадре не доказывает отсутствие техники на всей площадке.",
            "recommendation": rule["recommendation"] if outcome == "check_requested" else None}

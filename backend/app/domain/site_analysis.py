"""Conservative, revision-bound comparisons for one declared zone."""

from datetime import datetime


def compare_equipment(entries: list[dict], frame_times: list[str], observations: list[dict],
                      usable_ids: list[str], supported: set[str]) -> list[dict]:
    if not entries or not frame_times:
        return []
    active = [entry for entry in entries if all(entry["starts_at"] <= datetime.fromisoformat(time)
              <= entry["ends_at"] for time in frame_times) and entry["state"] == "active"]
    if not active:
        return []
    if len(usable_ids) < 3:
        return [{"kind": "insufficient_observations", "entry_id": None,
                 "reason": "At least three assessable frames of the active zone are required."}]
    seen = {item["class_name"] for item in observations
            if item["input_id"] in usable_ids and item["state"] == "detected"}
    states = {(item["input_id"], item["class_name"]): item["state"] for item in observations}
    signals = []
    for entry in active:
        for name in entry["expected_equipment"]:
            if (name == "concrete_mixer_truck" and entry.get("stage_key") != "concreting"
                    or name == "road_roller" and entry.get("stage_key") != "roadwork"):
                continue
            if name in supported and name not in seen and all(
                    states.get((input_id, name)) == "not_detected_in_frame" for input_id in usable_ids):
                signals.append({"kind": "expected_equipment_missing", "entry_id": entry["id"],
                                "class_name": name, "reason": "Expected equipment was not detected in the assessable series."})
    allowed = set().union(*(set(entry["expected_equipment"]) | set(entry["allowed_equipment"]) for entry in active))
    explicitly_excluded = set.intersection(*(set(entry["excluded_equipment"]) for entry in active))
    for name in sorted((seen & explicitly_excluded) - allowed):
        signals.append({"kind": "equipment_not_planned", "entry_id": None, "class_name": name,
                        "reason": "All concurrent active operations explicitly exclude this equipment."})
    return signals

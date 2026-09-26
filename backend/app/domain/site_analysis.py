"""Conservative, revision-bound comparisons for one declared zone."""

from datetime import datetime, timezone


def compare_equipment(entries: list[dict], frame_times: list[str], observations: list[dict],
                      usable_ids: list[str], supported: set[str],
                      input_ids: list[str] | None = None,
                      input_hashes: dict[str, str] | None = None) -> list[dict]:
    if not entries or not frame_times:
        return [{"kind": "insufficient_observations", "entry_id": None, "supporting_input_ids": input_ids or list(dict.fromkeys(item["input_id"] for item in observations)),
                 "reason": "Нет подтверждённых ожиданий или времени съёмки кадров."}]
    # Production callers pass the complete input order, including unassessable frames.
    input_ids = input_ids if input_ids is not None else list(dict.fromkeys(
        item["input_id"] for item in observations))
    if len(input_ids) != len(frame_times):
        return [{"kind": "insufficient_observations", "entry_id": None,
                 "reason": "Время съёмки не удаётся сопоставить с исходными кадрами.",
                 "supporting_input_ids": []}]
    frames = list(zip(input_ids, map(datetime.fromisoformat, frame_times)))
    states = {(item["input_id"], item["class_name"]): item["state"] for item in observations}
    usable = set(usable_ids)
    active = [entry for entry in entries if entry["state"] == "active"]
    signals = []
    for entry in active:
        relevant = [input_id for input_id, time in frames if entry["starts_at"] <= time <= entry["ends_at"]]
        if not relevant:
            continue
        if not entry["expected_equipment"] and not entry["excluded_equipment"]:
            signals.append({"kind": "insufficient_observations", "entry_id": entry["id"],
                            "supporting_input_ids": relevant,
                            "reason": "Для этой работы не подтверждена связь с ожидаемой или исключённой техникой."})
        elif not entry["expected_equipment"] and (len(relevant) < 3 or not set(relevant) <= usable):
            signals.append({"kind": "insufficient_observations", "entry_id": entry["id"],
                            "supporting_input_ids": relevant, "reason": "Нужны минимум три пригодных кадра в период этой работы."})
        for name in entry["expected_equipment"]:
            assessable = [input_id for input_id in relevant if input_id in usable
                          and states.get((input_id, name)) != "insufficient_data"]
            basis = {"entry_id": entry["id"], "class_name": name, "supporting_input_ids": assessable}
            known = [states.get((input_id, name)) for input_id in assessable]
            if (name not in supported or len({input_hashes[item] for item in assessable if item in input_hashes}
                                             if input_hashes is not None else set(assessable)) < 3
                    or any(state not in {"detected", "not_detected_in_frame"} for state in known)):
                signals.append({**basis, "kind": "insufficient_observations",
                                "reason": "Нужны минимум три пригодных кадра в период работы и наблюдения поддерживаемого класса техники."})
            elif all(state == "not_detected_in_frame" for state in known):
                signals.append({**basis, "kind": "expected_equipment_missing",
                                "reason": "Ожидаемая техника не обнаружена ни в одном из пригодных кадров за период работы."})
    excluded_frames: dict[str, list[str]] = {}
    unevaluable_exclusions: dict[str, list[str]] = {}
    uncovered = []
    for input_id, time in frames:
        concurrent = [entry for entry in active if entry["starts_at"] <= time <= entry["ends_at"]]
        if not concurrent:
            uncovered.append(input_id)
            continue
        allowed = set().union(*(set(entry["expected_equipment"]) | set(entry["allowed_equipment"])
                                for entry in concurrent))
        excluded = set().union(*(set(entry["excluded_equipment"]) for entry in concurrent))
        for name in sorted(excluded - allowed):
            state = states.get((input_id, name))
            if name not in supported or input_id not in usable or state not in {"detected", "not_detected_in_frame"}:
                unevaluable_exclusions.setdefault(name, []).append(input_id)
            elif state == "detected":
                excluded_frames.setdefault(name, []).append(input_id)
    for name, supporting in sorted(excluded_frames.items()):
        signals.append({"kind": "equipment_not_planned", "entry_id": None, "class_name": name,
                        "supporting_input_ids": supporting,
                        "reason": "Активная работа явно исключает эту технику; параллельные работы её не допускают."})
    for name, supporting in sorted(unevaluable_exclusions.items()):
        signals.append({"kind": "insufficient_observations", "entry_id": None, "class_name": name,
                        "supporting_input_ids": supporting,
                        "reason": "Нельзя оценить исключённую технику: класс не поддерживается или наблюдение отсутствует/непригодно."})
    if uncovered:
        signals.append({"kind": "insufficient_observations", "entry_id": None,
                        "supporting_input_ids": uncovered, "reason": "Время съёмки этих кадров не попадает в период активных работ."})
    return signals


def utc_frame_times(values: list[str]) -> list[str]:
    return [datetime.fromisoformat(value).astimezone(timezone.utc).isoformat() for value in values]

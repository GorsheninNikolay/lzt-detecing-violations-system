import hashlib
import json
import math
from pathlib import Path
from urllib.parse import urlsplit


CLASSES = ("excavator", "dump_truck")
STAGES = ("input_registration", "frame_usability", "equipment_observation", "series_aggregation", "rule_evaluation", "result_projection")


class ManifestError(ValueError):
    pass


def validate_manifest(path: Path, exclusion_inventories: list[Path]) -> tuple[dict, list[tuple[dict, bytes]]]:
    try:
        manifest = json.loads(path.read_text())
        if manifest["schema_revision"] != "admission-fixtures-v1" or manifest["declared_license"] != "CC0":
            raise ManifestError("fixture_manifest_invalid")
        source_url = urlsplit(manifest["source_url"])
        if source_url.scheme != "https" or not source_url.hostname or source_url.username or source_url.password or source_url.query or source_url.fragment:
            raise ManifestError("fixture_manifest_invalid")
        fixtures = manifest["fixtures"]
        if len(fixtures) != 4 or len({f["id"] for f in fixtures}) != 4:
            raise ManifestError("fixture_manifest_invalid")
        groups = set(manifest["reserved_source_groups"])
        if groups != {f["source_group"] for f in fixtures} or len(groups) != 4:
            raise ManifestError("fixture_manifest_invalid")
        occupied_hashes, occupied_groups, tiers, exclusion_evidence = set(), set(), set(), []
        for inventory_path in exclusion_inventories:
            inventory = json.loads(inventory_path.read_text())
            if inventory.get("schema_revision") != "exclusion-inventory-v1":
                raise ManifestError("exclusion_inventory_invalid")
            tier = inventory.get("tier")
            if tier in tiers:
                raise ManifestError("exclusion_inventory_invalid")
            tiers.add(tier)
            exclusion_evidence.append({"tier": tier, "sha256": hashlib.sha256(
                json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()})
            occupied_groups.update(inventory.get("reserved_source_groups", []))
            for item in inventory.get("fixtures", []):
                occupied_groups.add(item["source_group"])
                if item.get("source_site_camera_time_sequence_group"):
                    occupied_groups.add(item["source_site_camera_time_sequence_group"])
                occupied_hashes.add(item["image"]["sha256"])
        if tiers != {"training", "validation", "development_acceptance", "held_out_evaluation"}:
            raise ManifestError("exclusion_inventory_incomplete")
        result, local_hashes = [], set()
        for fixture in fixtures:
            if not all(fixture.get(key) for key in ("source_group", "source_site_camera_time_sequence_group", "context", "image", "label")):
                raise ManifestError("fixture_manifest_invalid")
            if {fixture["source_group"], fixture["source_site_camera_time_sequence_group"]} & occupied_groups:
                raise ManifestError("fixture_group_overlap")
            paths = []
            for extension in ("image", "label"):
                entry = fixture[extension]
                relative = Path(entry["path"])
                if relative.is_absolute() or ".." in relative.parts:
                    raise ManifestError("fixture_manifest_invalid")
                payload = (path.parent / relative).read_bytes()
                if len(payload) != entry["size"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                    raise ManifestError("fixture_hash_mismatch")
                paths.append(payload)
            label_ids = {int(line.split()[0]) for line in paths[1].decode().splitlines() if line.strip()}
            expected_classes = sorted(name for label_id, name in ((0, "dump_truck"), (1, "excavator")) if label_id in label_ids)
            if sorted(fixture.get("expected_classes", [])) != expected_classes:
                raise ManifestError("fixture_label_mismatch")
            if fixture["image"]["sha256"] in occupied_hashes or fixture["image"]["sha256"] in local_hashes:
                raise ManifestError("fixture_checksum_overlap")
            local_hashes.add(fixture["image"]["sha256"])
            result.append((fixture, paths[0]))
        return {**manifest, "exclusion_inventories": sorted(exclusion_evidence, key=lambda item: item["tier"])}, result
    except ManifestError:
        raise
    except Exception:
        raise ManifestError("fixture_manifest_invalid") from None


def normalized_states(native_states: dict, supported_classes: tuple[str, ...] = CLASSES) -> dict[str, str]:
    if set(native_states) != set(supported_classes) or any(value not in ("detected", "not_detected_in_frame", "insufficient_data") for value in native_states.values()):
        raise ValueError("observation_normalization_failed")
    return {name: native_states[name] for name in supported_classes}


def closed_observations(states: dict, requested_classes: list[str], source_artifact_id: str,
                        supported_classes: tuple[str, ...] = CLASSES) -> list[dict]:
    if not isinstance(states, dict) or set(states) != set(supported_classes):
        raise ValueError("observation_normalization_failed")
    if any(value not in ("detected", "not_detected_in_frame", "insufficient_data") for value in states.values()):
        raise ValueError("observation_normalization_failed")
    return [{"class_name": name, "state": states[name] if name in supported_classes else "not_analyzed",
             "reason": ("unsupported_class" if name not in supported_classes else
                        "frame_unassessable" if states[name] == "insufficient_data" else None),
             "source_artifact_id": source_artifact_id}
            for name in requested_classes]


def normalized_objects(native: dict, prompts: dict[str, str], orientation: int = 1) -> list[dict]:
    width, height = native["image_size"]
    if width <= 0 or height <= 0 or orientation not in range(1, 9):
        raise ValueError("observation_normalization_failed")
    transforms = {
        1: lambda x, y: (x, y), 2: lambda x, y: (1 - x, y),
        3: lambda x, y: (1 - x, 1 - y), 4: lambda x, y: (x, 1 - y),
        5: lambda x, y: (y, x), 6: lambda x, y: (1 - y, x),
        7: lambda x, y: (1 - y, 1 - x), 8: lambda x, y: (y, 1 - x),
    }
    classes = {label: name for name, label in prompts.items()}
    objects = []
    for detection in native["detections"]:
        name = classes.get(detection["label"])
        if name is None:
            continue
        x1, y1, x2, y2 = detection["box"]
        score = detection["score"]
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2, score)) or not 0 <= score <= 1:
            raise ValueError("observation_normalization_failed")
        corners = [transforms[orientation](x, y) for x in (x1 / width, x2 / width)
                   for y in (y1 / height, y2 / height)]
        box = [max(0.0, min(1.0, min(x for x, _ in corners))),
               max(0.0, min(1.0, min(y for _, y in corners))),
               max(0.0, min(1.0, max(x for x, _ in corners))),
               max(0.0, min(1.0, max(y for _, y in corners)))]
        if box[0] >= box[2] or box[1] >= box[3]:
            continue
        objects.append({"class_name": name, "score": score, "box": box,
                        "image_size": [height, width] if orientation >= 5 else [width, height]})
    return objects


def scene_features(native: dict, prompts: dict[str, str]) -> list[dict]:
    labels = {label: name for name, label in prompts.items()}
    return [{"feature_name": labels[item["label"]], "score": item["score"]}
            for item in native["detections"] if item["label"] in labels]


def stage_hypotheses(objects: list[dict], features: list[dict]) -> list[dict]:
    evidence = (
        ("excavation", "excavator", {"excavation_or_trench"}),
        ("concreting", "concrete_mixer_truck", {"formwork", "rebar", "concrete_surface"}),
        ("roadwork", "road_roller", {"road_base_or_surface"}),
    )
    hypotheses = []
    for stage, machine, required in evidence:
        supporting = []
        visible = set()
        for item in objects:
            if item["class_name"] != machine:
                continue
            matches = {feature["feature_name"] for feature in features
                       if feature["input_id"] == item["input_id"] and feature["feature_name"] in required}
            if matches:
                supporting.append(item["input_id"])
                visible.update(matches)
        if supporting:
            hypotheses.append({"stage": stage, "equipment": machine,
                               "scene_features": sorted(visible),
                               "supporting_input_ids": sorted(set(supporting))})
    return hypotheses

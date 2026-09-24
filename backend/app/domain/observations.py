import hashlib
import json
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


def normalized_states(native_states: dict) -> dict[str, str]:
    if set(native_states) != set(CLASSES) or any(value not in ("detected", "not_detected_in_frame", "insufficient_data") for value in native_states.values()):
        raise ValueError("observation_normalization_failed")
    return {name: native_states[name] for name in CLASSES}


def closed_observations(states: dict, requested_classes: list[str], source_artifact_id: str) -> list[dict]:
    if not isinstance(states, dict) or set(states) != set(CLASSES):
        raise ValueError("observation_normalization_failed")
    if any(value not in ("detected", "not_detected_in_frame", "insufficient_data") for value in states.values()):
        raise ValueError("observation_normalization_failed")
    return [{"class_name": name, "state": states[name] if name in CLASSES else "not_analyzed",
             "reason": ("unsupported_class" if name not in CLASSES else
                        "frame_unassessable" if states[name] == "insufficient_data" else None),
             "source_artifact_id": source_artifact_id}
            for name in requested_classes]

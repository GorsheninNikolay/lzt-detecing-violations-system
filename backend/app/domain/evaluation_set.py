"""Evidence gate for a held-out evaluation revision."""

import hashlib
import io
import json
import os
import tempfile
import zipfile
import zlib
from pathlib import Path

from PIL import Image, UnidentifiedImageError


SCENARIOS = (
    ["single_both", "single_excavator"]
    + ["positive_series"] * 3
    + ["check_request_series"] * 3
    + ["insufficient_series"] * 2
    + ["out_of_scope"]
)
TIERS = {"training", "validation", "contract", "development_acceptance", "held_out_evaluation"}
EXPECTED_SCENARIOS = {
    "single_both": ("observations_only", ["excavator", "dump_truck"]),
    "single_excavator": ("observations_only", ["excavator", "dump_truck"]),
    "positive_series": ("no_check", ["excavator", "dump_truck"]),
    "check_request_series": ("check_requested", ["excavator", "dump_truck"]),
    "insufficient_series": ("insufficient_data", ["excavator", "dump_truck"]),
    "out_of_scope": ("not_analyzed", ["crane"]),
}


def canonical_hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def rejected_input_hash(manifest_path: Path) -> str:
    try:
        payload = manifest_path.read_bytes()
    except OSError:
        payload = str(manifest_path).encode()
    return hashlib.sha256(payload).hexdigest()


def inspect_evaluation_set(manifest_path: Path, archive_path: Path, inventory_paths: list[Path],
                           contract_path: Path, admission_path: Path, historical_path: Path) -> dict:
    try:
        return _inspect_evaluation_set(manifest_path, archive_path, inventory_paths,
                                       contract_path, admission_path, historical_path)
    except (AttributeError, EOFError, KeyError, TypeError, ValueError, UnicodeError, zipfile.BadZipFile, zlib.error):
        return {"status": "rejected", "manifest_hash": rejected_input_hash(manifest_path), "inventory_evidence": [],
                "errors": [{"code": "evidence_invalid"}], "manifest": None}


def _inspect_evaluation_set(manifest_path: Path, archive_path: Path, inventory_paths: list[Path],
                            contract_path: Path, admission_path: Path, historical_path: Path) -> dict:
    """Return a byte-free decision. An approval cannot be inferred from archive labels."""
    try:
        manifest = json.loads(manifest_path.read_text())
        if not isinstance(manifest, dict):
            raise ValueError("manifest must be an object")
    except (OSError, ValueError, UnicodeError):
        return {"status": "rejected", "manifest_hash": rejected_input_hash(manifest_path), "inventory_evidence": [],
                "errors": [{"code": "manifest_invalid"}], "manifest": None}
    evidence = []
    errors = []
    occupied_hashes: dict[str, set[str]] = {}
    occupied_groups: dict[str, set[str]] = {}
    tiers = set()
    for path in [*inventory_paths, contract_path]:
        try:
            inventory = json.loads(path.read_text())
            if not isinstance(inventory, dict):
                raise ValueError("inventory must be an object")
        except (OSError, ValueError, UnicodeError):
            errors.append({"code": "inventory_unavailable", "name": path.name})
            continue
        tier = inventory.get("tier")
        evidence.append({"name": tier, "sha256": canonical_hash(inventory)})
        if inventory.get("schema_revision") != "exclusion-inventory-v1" or tier in tiers:
            errors.append({"code": "inventory_invalid", "tier": tier})
        tiers.add(tier)
        for group in inventory.get("reserved_source_groups", []):
            occupied_groups.setdefault(group, set()).add(tier)
        for item in inventory.get("fixtures", []):
            for group in (item.get("source_group"), item.get("source_site_camera_time_sequence_group")):
                if group:
                    occupied_groups.setdefault(group, set()).add(tier)
            for image in (item.get("image"), item.get("derived_image")):
                if image and image.get("sha256"):
                    occupied_hashes.setdefault(image["sha256"], set()).add(tier)
    if tiers != TIERS:
        errors.append({"code": "inventory_incomplete", "tiers": sorted(TIERS - tiers)})
    historical = None
    for name, path in (("admission", admission_path), ("historical_comparison", historical_path)):
        try:
            material = json.loads(path.read_text())
            if not isinstance(material, dict):
                raise ValueError("material must be an object")
        except (OSError, ValueError, UnicodeError):
            errors.append({"code": "material_unavailable", "name": name})
            continue
        if name == "historical_comparison":
            historical = material
            if material.get("source_archive_sha256") != manifest.get("source_archive_sha256"):
                errors.append({"code": "historical_archive_mismatch"})
        evidence.append({"name": name, "sha256": canonical_hash(material)})
        for group in material.get("reserved_source_groups", []):
            occupied_groups.setdefault(group, set()).add(name)
        for item in material.get("fixtures", material.get("frames", [])):
            for group in (item.get("source_group"), item.get("source_group_candidate"),
                          item.get("source_site_camera_time_sequence_group")):
                if group:
                    occupied_groups.setdefault(group, set()).add(name)
            for image in (item.get("image"), item.get("derived_image")):
                if image and image.get("sha256"):
                    occupied_hashes.setdefault(image["sha256"], set()).add(name)
    frames = manifest.get("frames", [])
    if not isinstance(frames, list) or any(not isinstance(frame, dict) for frame in frames):
        errors.append({"code": "composition_invalid"})
        frames = []
    if manifest.get("schema_revision") != "held-out-evaluation-v1" or [f.get("scenario") for f in frames] != SCENARIOS:
        errors.append({"code": "composition_invalid"})
    scenarios = manifest.get("scenarios")
    if (not isinstance(scenarios, dict) or set(scenarios) != set(EXPECTED_SCENARIOS)
            or any(scenarios.get(name) != {"expected_outcome": outcome, "requested_classes": classes}
                   for name, (outcome, classes) in EXPECTED_SCENARIOS.items())):
        errors.append({"code": "scenario_contract_invalid"})
    for name in ("positive_series", "check_request_series", "insufficient_series"):
        selected = [frame for frame in frames if frame.get("scenario") == name]
        ids = [frame.get("id") for frame in selected]
        if any(not isinstance(frame_id, str) for frame_id in ids) or ids != sorted(ids) or len(ids) != len(set(ids)):
            errors.append({"code": "series_order_invalid", "scenario": name})
        if name != "insufficient_series" and len({frame.get("context", {}).get("observation_area")
                                                   for frame in selected if isinstance(frame.get("context"), dict)}) != 1:
            errors.append({"code": "series_area_invalid", "scenario": name})
    artifacts = manifest.get("evidence_artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    loaded_evidence = {}
    for name in ("human_review_export", "human_review", "owner_attestation"):
        reference = artifacts.get(name, {})
        if not isinstance(reference, dict):
            reference = {}
        raw_path = reference.get("path")
        if not isinstance(raw_path, str):
            errors.append({"code": "evidence_unavailable", "name": name})
            continue
        relative = Path(raw_path)
        if not relative.name or relative.is_absolute() or len(relative.parts) != 1:
            errors.append({"code": "evidence_unavailable", "name": name})
            continue
        try:
            payload = (manifest_path.parent / relative).read_bytes()
        except OSError:
            errors.append({"code": "evidence_unavailable", "name": name})
            continue
        if hashlib.sha256(payload).hexdigest() != reference.get("sha256"):
            errors.append({"code": "evidence_hash_mismatch", "name": name})
            continue
        try:
            loaded_evidence[name] = json.loads(payload)
        except (ValueError, UnicodeDecodeError):
            errors.append({"code": "evidence_invalid", "name": name})
    review = loaded_evidence.get("human_review", {})
    export = loaded_evidence.get("human_review_export", {})
    attestation = loaded_evidence.get("owner_attestation", {})
    if not isinstance(review, dict):
        review = {}
    if not isinstance(attestation, dict):
        attestation = {}
    owner_review = attestation.get("human_review") if isinstance(attestation.get("human_review"), dict) else {}
    if not isinstance(export, dict) or not isinstance(export.get("frames"), list):
        errors.append({"code": "human_review_export_invalid"})
        export = {}
    if (review.get("source_export_sha256") != artifacts.get("human_review_export", {}).get("sha256")
            or owner_review.get("source_export_sha256") != artifacts.get("human_review_export", {}).get("sha256")):
        errors.append({"code": "human_review_export_mismatch"})
    if (review.get("review_schema") != "story-4-1-human-review-v1"
            or not isinstance(review.get("frames"), list) or len(review["frames"]) != len(frames)):
        errors.append({"code": "human_review_invalid"})
    else:
        labels = {"Да": "yes", "Нет": "no"}
        for ordinal, (frame, answer) in enumerate(zip(frames, review["frames"])):
            if not isinstance(answer, dict):
                errors.append({"code": "human_review_invalid", "ordinal": ordinal})
                continue
            if (answer.get("ordinal"), answer.get("id"), answer.get("scenario")) != (ordinal, frame.get("id"), frame.get("scenario")):
                errors.append({"code": "human_review_identity_mismatch", "ordinal": ordinal})
            if answer.get("image_sha256") != frame.get("image", {}).get("sha256"):
                errors.append({"code": "human_review_image_mismatch", "ordinal": ordinal})
            if ordinal < len(export.get("frames", [])):
                raw_answer = export["frames"][ordinal]
                if not isinstance(raw_answer, dict) or any(raw_answer.get(key) != answer.get(key)
                    for key in ("ordinal", "id", "scenario", "excavator", "dump_truck", "usable", "same_area")):
                    errors.append({"code": "human_review_export_mismatch", "ordinal": ordinal})
            if frame.get("manual_labels") != {name: labels.get(answer.get(name)) for name in ("excavator", "dump_truck")}:
                errors.append({"code": "human_review_label_mismatch", "ordinal": ordinal})
            if frame.get("usable") != (answer.get("usable") == "Да"):
                errors.append({"code": "human_review_usability_mismatch", "ordinal": ordinal})
            group_evidence = frame.get("group_evidence")
            if not isinstance(group_evidence, dict) or group_evidence.get("same_area_response") != answer.get("same_area"):
                errors.append({"code": "human_review_area_mismatch", "ordinal": ordinal})
            if (frame.get("scenario") in ("positive_series", "check_request_series") and answer.get("same_area") != "Да"
                    or frame.get("scenario") == "insufficient_series" and answer.get("same_area") not in ("Да", "Нет")):
                errors.append({"code": "series_area_unconfirmed", "ordinal": ordinal})
    if len(export.get("frames", [])) != len(frames):
        errors.append({"code": "human_review_export_mismatch"})
    non_use = attestation.get("non_use") if isinstance(attestation.get("non_use"), dict) else {}
    prototype_use = attestation.get("prototype_use_and_cloud_upload") if isinstance(attestation.get("prototype_use_and_cloud_upload"), dict) else {}
    if (owner_review.get("sha256") != artifacts.get("human_review", {}).get("sha256")
            or non_use.get("confirmed") is not True
            or prototype_use.get("approved") is not True
            or attestation.get("source_archive_sha256") != manifest.get("source_archive_sha256")
            or attestation.get("selected_image_sha256") != [frame.get("image", {}).get("sha256") for frame in frames]):
        errors.append({"code": "owner_attestation_invalid"})
    upload = manifest.get("cloud_upload_authorization")
    if not isinstance(upload, dict) or upload.get("granted") is not True or not upload.get("evidence"):
        errors.append({"code": "missing_evidence", "field": "cloud_upload_authorization"})
    non_use = manifest.get("source_non_use_attestation")
    if not isinstance(non_use, dict) or non_use.get("confirmed") is not True or not non_use.get("evidence"):
        errors.append({"code": "missing_evidence", "field": "source_non_use_attestation"})
    archive_hash = None
    try:
        archive_digest = hashlib.sha256()
        with archive_path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                archive_digest.update(chunk)
        archive_hash = archive_digest.hexdigest()
    except OSError:
        errors.append({"code": "archive_unavailable"})
    if archive_hash != manifest.get("source_archive_sha256"):
        errors.append({"code": "archive_hash_mismatch"})
    archive = None
    if archive_hash == manifest.get("source_archive_sha256"):
        try:
            archive = zipfile.ZipFile(archive_path)
        except (OSError, zipfile.BadZipFile):
            errors.append({"code": "archive_invalid"})
    local_hashes = set()
    try:
        if archive is not None:
            for historical_frame in (historical or {}).get("frames", []):
                image = historical_frame.get("image", {})
                try:
                    payload = archive.read(image["archive_member"])
                    if len(payload) != image["size"] or hashlib.sha256(payload).hexdigest() != image["sha256"]:
                        errors.append({"code": "historical_content_mismatch", "identity": historical_frame.get("id")})
                except (EOFError, KeyError, OSError, RuntimeError, zipfile.BadZipFile, zlib.error):
                    errors.append({"code": "historical_content_unavailable", "identity": historical_frame.get("id")})
        for ordinal, frame in enumerate(frames):
            if frame.get("ordinal") != ordinal:
                errors.append({"code": "ordinal_invalid", "ordinal": ordinal})
            scenario = frame.get("scenario")
            context = frame.get("context")
            expected_contract = EXPECTED_SCENARIOS.get(scenario)
            group_evidence = frame.get("group_evidence") if isinstance(frame.get("group_evidence"), dict) else {}
            if (not isinstance(context, dict) or not expected_contract
                    or context.get("expected_outcome") != expected_contract[0]
                    or context.get("requested_classes") != expected_contract[1]
                    or context.get("analysis_intent") != ("excavation_rule" if scenario.endswith("_series") else "observations_only")
                    or not context.get("observation_area")
                    or context.get("area_relation") != (
                        group_evidence.get("same_area_response") if scenario.endswith("_series") else "single_frame")):
                errors.append({"code": "frame_context_invalid", "ordinal": ordinal})
            for key in ("source_site_camera_time_sequence_group", "group_evidence", "context",
                        "source_rights", "cloud_upload_permission", "sufficiency_notes",
                        "adjudicator", "adjudicated_at", "usable"):
                if not frame.get(key):
                    errors.append({"code": "missing_evidence", "ordinal": ordinal, "field": key})
            rights = frame.get("source_rights")
            if not isinstance(rights, dict) or rights.get("status") != "owner_approved_with_caveat" or not rights.get("evidence") or not rights.get("caveat"):
                errors.append({"code": "rights_not_cleared", "ordinal": ordinal})
            if frame.get("cloud_upload_permission") not in (True, None):
                errors.append({"code": "upload_permission_denied", "ordinal": ordinal})
            if frame.get("usable") not in (True, None):
                errors.append({"code": "frame_unusable", "ordinal": ordinal})
            labels = frame.get("manual_labels", {})
            for cls in ("excavator", "dump_truck"):
                if labels.get(cls) not in ("yes", "no", "unclear") or labels.get(cls) == "unclear":
                    errors.append({"code": "missing_evidence", "ordinal": ordinal, "field": f"manual_labels.{cls}"})
            expected = {
                "single_both": ("yes", "yes"), "single_excavator": ("yes", "no"),
                "positive_series": ("yes", "yes"), "check_request_series": ("yes", "no"),
                "insufficient_series": ("no", "no"), "out_of_scope": ("no", "no"),
            }.get(frame.get("scenario"))
            if expected and (labels.get("excavator"), labels.get("dump_truck")) != expected:
                errors.append({"code": "scenario_label_mismatch", "ordinal": ordinal})
            verified_group = frame.get("source_site_camera_time_sequence_group")
            candidate_group = frame.get("source_group_candidate")
            if not isinstance(verified_group, str) or not verified_group.strip():
                errors.append({"code": "missing_evidence", "ordinal": ordinal,
                               "field": "source_site_camera_time_sequence_group"})
            if candidate_group is not None and (not isinstance(candidate_group, str) or not candidate_group.strip()):
                errors.append({"code": "group_candidate_invalid", "ordinal": ordinal})
            for group in sorted({value for value in (verified_group, candidate_group) if isinstance(value, str) and value}):
                for tier in sorted(occupied_groups.get(group, set()) - {"held_out_evaluation"}):
                    errors.append({"code": "group_overlap", "ordinal": ordinal, "tier": tier, "identity": group})
            for part in ("image", "label"):
                member = frame.get(part, {})
                member_path = member.get("archive_member", "")
                if not member_path or member_path.startswith("/") or ".." in Path(member_path).parts or archive is None:
                    errors.append({"code": "bytes_unavailable", "ordinal": ordinal, "part": part})
                    continue
                try:
                    payload = archive.read(member_path)
                except (EOFError, KeyError, OSError, RuntimeError, zipfile.BadZipFile, zlib.error):
                    errors.append({"code": "bytes_unavailable", "ordinal": ordinal, "part": part})
                    continue
                if len(payload) != member.get("size") or hashlib.sha256(payload).hexdigest() != member.get("sha256"):
                    errors.append({"code": "content_mismatch", "ordinal": ordinal, "part": part})
                if part == "image":
                    try:
                        with Image.open(io.BytesIO(payload)) as decoded:
                            decoded.load()
                            if decoded.format != "JPEG":
                                raise ValueError("not a JPEG")
                    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
                        errors.append({"code": "jpeg_invalid", "ordinal": ordinal})
            image_hash = frame.get("image", {}).get("sha256")
            for tier in sorted(occupied_hashes.get(image_hash, set()) - {"held_out_evaluation"}):
                errors.append({"code": "checksum_overlap", "ordinal": ordinal,
                               "tier": tier, "identity": image_hash})
            if image_hash in local_hashes:
                errors.append({"code": "duplicate_frame", "ordinal": ordinal, "identity": image_hash})
            local_hashes.add(image_hash)
    finally:
        if archive:
            archive.close()
    return {"status": "accepted" if not errors else "rejected", "manifest_hash": canonical_hash(manifest),
            "inventory_evidence": sorted(evidence, key=lambda item: item["name"]), "errors": errors,
            "manifest": manifest if not errors else None}


def reserve_held_out_inventory(path: Path, manifest: dict, manifest_hash: str) -> None:
    inventory = json.loads(path.read_text())
    if inventory.get("schema_revision") != "exclusion-inventory-v1" or inventory.get("tier") != "held_out_evaluation":
        raise ValueError("held_out_inventory_invalid")
    known = {(item.get("manifest_hash"), item["image"]["sha256"]) for item in inventory["fixtures"]}
    for frame in manifest["frames"]:
        image = frame["image"]
        identity = (manifest_hash, image["sha256"])
        if identity not in known:
            inventory["fixtures"].append({"manifest_hash": manifest_hash, "source_group": frame.get("source_group_candidate") or frame["source_site_camera_time_sequence_group"],
                "source_site_camera_time_sequence_group": frame["source_site_camera_time_sequence_group"],
                "image": {"sha256": image["sha256"]}})
            known.add(identity)
    inventory["reserved_source_groups"] = sorted(set(inventory["reserved_source_groups"]) |
        {f["source_site_camera_time_sequence_group"] for f in manifest["frames"]} |
        {f["source_group_candidate"] for f in manifest["frames"] if f.get("source_group_candidate")})
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(json.dumps(inventory, indent=2) + "\n")
            output.flush()
            os.fsync(output.fileno())
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)

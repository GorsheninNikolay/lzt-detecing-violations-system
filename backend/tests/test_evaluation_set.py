import hashlib
import io
import json
import os
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text

from app.adapters import postgres as postgres_adapter
from app.adapters.postgres import EvaluationStoreError
from app.domain.evaluation_set import EXPECTED_SCENARIOS, SCENARIOS, inspect_evaluation_set, reserve_held_out_inventory
from test_startup import database


ROOT = Path(__file__).resolve().parents[2]
INVENTORY_NAMES = ("training", "validation", "development_acceptance", "held_out_evaluation")


def evidence(tmp_path, salt=b"", group_prefix="site-camera-series"):
    tmp_path.mkdir(parents=True, exist_ok=True)
    archive = tmp_path / "source.zip"
    frames = []
    historical_frames = []
    with zipfile.ZipFile(archive, "w") as output:
        for ordinal, scenario in enumerate(SCENARIOS):
            color = tuple(hashlib.sha256(salt + bytes([ordinal])).digest()[:3])
            image = io.BytesIO()
            Image.new("RGB", (2, 2), color).save(image, format="JPEG")
            payload = image.getvalue()
            label = b""
            frame_id = f"100_{ordinal:02d}"
            output.writestr(f"images/{frame_id}.jpg", payload)
            output.writestr(f"labels/{frame_id}.txt", label)
            frames.append({"ordinal": ordinal, "id": frame_id, "scenario": scenario,
                "source_group_candidate": "100",
                "source_site_camera_time_sequence_group": f"{group_prefix}-{ordinal // 3}",
                "group_evidence": {"same_area_response": ("Да" if scenario in ("positive_series", "check_request_series") else
                                                          "Нет" if scenario == "insufficient_series" else None),
                                   "source": "owner verified source record", "conservative_source_prefix": "100"},
                "context": {"analysis_intent": "excavation_rule" if scenario.endswith("_series") else "observations_only",
                            "requested_classes": EXPECTED_SCENARIOS[scenario][1],
                            "expected_outcome": EXPECTED_SCENARIOS[scenario][0],
                            "observation_area": scenario if scenario != "insufficient_series" else f"insufficient-{ordinal}",
                            "area_relation": ("Да" if scenario in ("positive_series", "check_request_series") else
                                              "Нет" if scenario == "insufficient_series" else "single_frame")},
                "source_rights": {"status": "owner_approved_with_caveat", "evidence": "owner approved prototype use of declared CC0 source", "caveat": "original capture ownership unverified"},
                "cloud_upload_permission": True, "sufficiency_notes": "owner checked visibility and sequence",
                "adjudicator": "human owner", "adjudicated_at": "2026-09-24", "usable": True,
                "manual_labels": {"excavator": "yes" if scenario not in ("insufficient_series", "out_of_scope") else "no",
                                  "dump_truck": "yes" if scenario in ("single_both", "positive_series") else "no"},
                "image": {"archive_member": f"images/{frame_id}.jpg", "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)},
                "label": {"archive_member": f"labels/{frame_id}.txt", "sha256": hashlib.sha256(label).hexdigest(), "size": 0}})
        for ordinal in range(22):
            cohort = "initial_comparison" if ordinal < 11 else "final_comparison"
            frame_id = f"900_{ordinal:02d}"
            payload = b"historical" + salt + bytes([ordinal])
            member = f"history/{frame_id}.jpg"
            output.writestr(member, payload)
            historical_frames.append({"cohort": cohort, "id": frame_id, "source_group_candidate": "900",
                "image": {"archive_member": member, "sha256": hashlib.sha256(payload).hexdigest(), "size": len(payload)}})
    manifest = {"schema_revision": "held-out-evaluation-v1", "source_archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "cloud_upload_authorization": {"granted": True, "evidence": "owner authorized provider upload"},
        "source_non_use_attestation": {"confirmed": True, "evidence": "owner checked all model training sources"},
        "scenarios": {name: {"expected_outcome": outcome, "requested_classes": classes}
                      for name, (outcome, classes) in EXPECTED_SCENARIOS.items()},
        "frames": frames}
    review = {"review_schema": "story-4-1-human-review-v1", "frames": [
        {"ordinal": f["ordinal"], "id": f["id"], "scenario": f["scenario"],
         "excavator": "Да" if f["manual_labels"]["excavator"] == "yes" else "Нет",
         "dump_truck": "Да" if f["manual_labels"]["dump_truck"] == "yes" else "Нет", "usable": "Да",
         **({"same_area": f["group_evidence"]["same_area_response"]} if f["scenario"].endswith("_series") else {}),
         "image_sha256": f["image"]["sha256"]}
        for f in frames]}
    export = {"review_schema": review["review_schema"], "frames": [
        {key: value for key, value in answer.items() if key != "image_sha256"} for answer in review["frames"]]}
    export_bytes = json.dumps(export).encode()
    (tmp_path / "human_review_export.json").write_bytes(export_bytes)
    export_hash = hashlib.sha256(export_bytes).hexdigest()
    review["source_export_sha256"] = export_hash
    review_bytes = json.dumps(review).encode()
    (tmp_path / "human_review.json").write_bytes(review_bytes)
    review_hash = hashlib.sha256(review_bytes).hexdigest()
    attestation_bytes = json.dumps({"human_review": {"sha256": review_hash, "source_export_sha256": export_hash},
                                    "non_use": {"confirmed": True},
                                    "prototype_use_and_cloud_upload": {"approved": True},
                                    "source_archive_sha256": manifest["source_archive_sha256"],
                                    "selected_image_sha256": [f["image"]["sha256"] for f in frames]}).encode()
    (tmp_path / "owner_attestation.json").write_bytes(attestation_bytes)
    manifest["evidence_artifacts"] = {
        "human_review_export": {"path": "human_review_export.json", "sha256": export_hash},
        "human_review": {"path": "human_review.json", "sha256": review_hash},
        "owner_attestation": {"path": "owner_attestation.json", "sha256": hashlib.sha256(attestation_bytes).hexdigest()}}
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    inventories = []
    for tier in INVENTORY_NAMES:
        path = tmp_path / f"{tier}.json"
        path.write_text(json.dumps({"schema_revision": "exclusion-inventory-v1", "tier": tier,
                                    "reserved_source_groups": [], "fixtures": []}))
        inventories.append(path)
    admission = tmp_path / "admission.json"
    admission.write_text(json.dumps({"fixtures": []}))
    contract = tmp_path / "contract.json"
    contract.write_text(json.dumps({"schema_revision": "exclusion-inventory-v1", "tier": "contract",
                                    "reserved_source_groups": [], "fixtures": []}))
    historical = tmp_path / "historical.json"
    historical.write_text(json.dumps({"schema_revision": "historical-comparison-v1",
        "source_archive_sha256": manifest["source_archive_sha256"],
        "cohorts": {"initial_comparison": 11, "final_comparison": 11},
        "source_manifest_evidence": [{"cohort": cohort, "canonical_sha256": "a" * 64}
                                     for cohort in ("initial_comparison", "final_comparison")],
        "frames": historical_frames}))
    return manifest, manifest_path, archive, inventories, contract, admission, historical


def inspect(parts):
    _, path, archive, inventories, contract, admission, historical = parts
    return inspect_evaluation_set(path, archive, inventories, contract, admission, historical)


def reseal_evidence(parts):
    manifest, path, _, _, _, _, _ = parts
    root = path.parent
    export_bytes = (root / "human_review_export.json").read_bytes()
    export_hash = hashlib.sha256(export_bytes).hexdigest()
    review_path = root / "human_review.json"
    review = json.loads(review_path.read_text())
    review["source_export_sha256"] = export_hash
    review_bytes = json.dumps(review).encode()
    review_path.write_bytes(review_bytes)
    review_hash = hashlib.sha256(review_bytes).hexdigest()
    attestation_path = root / "owner_attestation.json"
    attestation = json.loads(attestation_path.read_text())
    attestation["human_review"]["sha256"] = review_hash
    attestation["human_review"]["source_export_sha256"] = export_hash
    attestation["source_archive_sha256"] = manifest["source_archive_sha256"]
    attestation["selected_image_sha256"] = [frame["image"]["sha256"] for frame in manifest["frames"]]
    attestation_bytes = json.dumps(attestation).encode()
    attestation_path.write_bytes(attestation_bytes)
    manifest["evidence_artifacts"] = {
        "human_review_export": {"path": "human_review_export.json", "sha256": export_hash},
        "human_review": {"path": "human_review.json", "sha256": review_hash},
        "owner_attestation": {"path": "owner_attestation.json", "sha256": hashlib.sha256(attestation_bytes).hexdigest()}}
    path.write_text(json.dumps(manifest))


def test_valid_freeze_evidence_and_missing_archive_stays_closed(tmp_path):
    parts = evidence(tmp_path)
    decision = inspect(parts)
    assert decision["status"] == "accepted" and len(decision["manifest"]["frames"]) == 11
    assert len(decision["inventory_evidence"]) == 7
    actual = inspect_evaluation_set(ROOT / "evaluation/held-out-v1.json", tmp_path / "missing.zip",
        sorted((ROOT / "backend/admission/exclusions").glob("*.json")),
        ROOT / "evaluation/contract-inventory.json",
        ROOT / "backend/admission/manifest.json", ROOT / "evaluation/historical-comparison-v1.json")
    assert actual["status"] == "rejected"
    assert any(error["code"] == "archive_hash_mismatch" for error in actual["errors"])


@pytest.mark.skipif(not os.getenv("EVALUATION_ARCHIVE_PATH"), reason="Set EVALUATION_ARCHIVE_PATH for real archive acceptance")
def test_checked_in_manifest_accepts_verified_archive():
    decision = inspect_evaluation_set(ROOT / "evaluation/held-out-v1.json", Path(os.environ["EVALUATION_ARCHIVE_PATH"]),
        sorted((ROOT / "backend/admission/exclusions").glob("*.json")),
        ROOT / "evaluation/contract-inventory.json", ROOT / "backend/admission/manifest.json",
        ROOT / "evaluation/historical-comparison-v1.json")
    assert decision["status"] == "accepted", decision["errors"]


@pytest.mark.parametrize("hash_field", ["image", "derived_image"])
def test_missing_evidence_and_overlap_record_identity(tmp_path, hash_field):
    parts = evidence(tmp_path)
    manifest, path, _, inventories, _, _, _ = parts
    manifest["frames"][0]["manual_labels"]["excavator"] = None
    path.write_text(json.dumps(manifest))
    inventory = json.loads(inventories[0].read_text())
    inventory["fixtures"] = [{"source_group": "other", "source_site_camera_time_sequence_group":
        manifest["frames"][0]["source_site_camera_time_sequence_group"],
        hash_field: {"sha256": manifest["frames"][1]["image"]["sha256"]}}]
    inventories[0].write_text(json.dumps(inventory))
    decision = inspect(parts)
    assert decision["status"] == "rejected" and decision["manifest"] is None
    assert {error["code"] for error in decision["errors"]} >= {"missing_evidence", "group_overlap", "checksum_overlap"}
    assert any(error.get("tier") == "training" and error.get("identity") for error in decision["errors"])


def test_changed_bytes_rejected(tmp_path):
    parts = evidence(tmp_path)
    parts[2].write_bytes(parts[2].read_bytes() + b"changed")
    assert any(error["code"] == "archive_hash_mismatch" for error in inspect(parts)["errors"])


def test_changed_human_review_rejected(tmp_path):
    parts = evidence(tmp_path)
    (tmp_path / "human_review.json").write_text("changed")
    assert any(error["code"] == "evidence_hash_mismatch" and error["name"] == "human_review"
               for error in inspect(parts)["errors"])


def test_malformed_manifest_records_rejection(database, tmp_path):
    parts = evidence(tmp_path)
    parts[1].write_text("{")
    decision, revision = database.freeze_evaluation_set(*parts[1:])
    assert decision["status"] == "rejected" and revision is None
    assert len(decision["manifest_hash"]) == 64
    with database.engine.connect() as connection:
        assert "rejected" in connection.execute(text("SELECT status FROM evaluation_freeze_decisions WHERE manifest_hash = :hash"),
                                                 {"hash": decision["manifest_hash"]}).scalars().all()


def test_review_image_hash_and_export_binding(tmp_path):
    parts = evidence(tmp_path)
    review_path = tmp_path / "human_review.json"
    review = json.loads(review_path.read_text())
    review["frames"][0]["image_sha256"] = "0" * 64
    review_path.write_text(json.dumps(review))
    reseal_evidence(parts)
    assert any(error["code"] == "human_review_image_mismatch" for error in inspect(parts)["errors"])
    parts = evidence(tmp_path / "export")
    (parts[1].parent / "human_review_export.json").write_text("{}")
    assert any(error["code"] == "evidence_hash_mismatch" and error["name"] == "human_review_export"
               for error in inspect(parts)["errors"])


def test_attestation_must_name_exact_archive_and_ordered_images(tmp_path):
    parts = evidence(tmp_path)
    attestation_path = tmp_path / "owner_attestation.json"
    attestation = json.loads(attestation_path.read_text())
    attestation["source_archive_sha256"] = "0" * 64
    attestation["selected_image_sha256"] = list(reversed(attestation["selected_image_sha256"]))
    payload = json.dumps(attestation).encode()
    attestation_path.write_bytes(payload)
    parts[0]["evidence_artifacts"]["owner_attestation"]["sha256"] = hashlib.sha256(payload).hexdigest()
    parts[1].write_text(json.dumps(parts[0]))
    assert any(error["code"] == "owner_attestation_invalid" for error in inspect(parts)["errors"])


def test_series_area_order_and_context_contract(tmp_path):
    parts = evidence(tmp_path)
    parts[0]["scenarios"]["positive_series"]["expected_outcome"] = "check_requested"
    parts[0]["frames"][2]["context"]["requested_classes"] = ["excavator"]
    parts[0]["frames"][2]["image"]["archive_member"], parts[0]["frames"][3]["image"]["archive_member"] = (
        parts[0]["frames"][3]["image"]["archive_member"], parts[0]["frames"][2]["image"]["archive_member"])
    parts[1].write_text(json.dumps(parts[0]))
    codes = {error["code"] for error in inspect(parts)["errors"]}
    assert {"scenario_contract_invalid", "frame_context_invalid", "series_order_invalid"} <= codes
    parts = evidence(tmp_path / "area")
    review_path = parts[1].parent / "human_review.json"
    review = json.loads(review_path.read_text())
    review["frames"][2]["same_area"] = "Нет"
    review_path.write_text(json.dumps(review))
    parts[0]["frames"][2]["group_evidence"]["same_area_response"] = "Нет"
    parts[0]["frames"][2]["context"]["area_relation"] = "Нет"
    reseal_evidence(parts)
    assert any(error["code"] == "series_area_unconfirmed" for error in inspect(parts)["errors"])


def test_admission_reserved_group_without_fixture_blocks_freeze(tmp_path):
    parts = evidence(tmp_path)
    parts[0]["frames"][0]["source_group_candidate"] = "admission-reserved"
    parts[1].write_text(json.dumps(parts[0]))
    parts[5].write_text(json.dumps({"reserved_source_groups": ["admission-reserved"], "fixtures": []}))
    assert any(error["code"] == "group_overlap" and error.get("tier") == "admission"
               for error in inspect(parts)["errors"])


def test_invalid_jpeg_zip_and_malformed_evidence_reject_without_exception(tmp_path):
    parts = evidence(tmp_path)
    archive = parts[2]
    with zipfile.ZipFile(archive) as source:
        members = {name: source.read(name) for name in source.namelist()}
    members[parts[0]["frames"][0]["image"]["archive_member"]] = b"not a jpeg"
    with zipfile.ZipFile(archive, "w") as output:
        for name, payload in members.items():
            output.writestr(name, payload)
    parts[0]["frames"][0]["image"]["sha256"] = hashlib.sha256(b"not a jpeg").hexdigest()
    parts[0]["frames"][0]["image"]["size"] = len(b"not a jpeg")
    parts[0]["source_archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    review_path = tmp_path / "human_review.json"
    review = json.loads(review_path.read_text())
    review["frames"][0]["image_sha256"] = parts[0]["frames"][0]["image"]["sha256"]
    review_path.write_text(json.dumps(review))
    parts[6].write_text(json.dumps({"source_archive_sha256": parts[0]["source_archive_sha256"], "frames": []}))
    reseal_evidence(parts)
    assert any(error["code"] == "jpeg_invalid" for error in inspect(parts)["errors"])
    archive.write_bytes(b"invalid zip")
    parts[0]["source_archive_sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
    parts[6].write_text(json.dumps({"source_archive_sha256": parts[0]["source_archive_sha256"], "frames": []}))
    reseal_evidence(parts)
    assert any(error["code"] == "archive_invalid" for error in inspect(parts)["errors"])
    (tmp_path / "human_review.json").write_text("{")
    parts[0]["evidence_artifacts"]["human_review"]["sha256"] = hashlib.sha256(b"{").hexdigest()
    parts[1].write_text(json.dumps(parts[0]))
    assert any(error["code"] == "evidence_invalid" for error in inspect(parts)["errors"])


def test_historical_member_hash_checked_against_archive(tmp_path):
    parts = evidence(tmp_path)
    historical = json.loads(parts[6].read_text())
    historical["frames"][0]["image"]["sha256"] = "0" * 64
    parts[6].write_text(json.dumps(historical))
    assert any(error["code"] == "historical_content_mismatch" for error in inspect(parts)["errors"])


def test_historical_cohorts_must_be_complete(tmp_path):
    parts = evidence(tmp_path)
    historical = json.loads(parts[6].read_text())
    historical["frames"].pop()
    parts[6].write_text(json.dumps(historical))
    assert any(error["code"] == "historical_manifest_invalid" for error in inspect(parts)["errors"])


@pytest.mark.parametrize("bad_field", ["reserved_string", "reserved_nonstring", "fixtures_string"])
def test_malformed_exclusion_inventory_rejected(tmp_path, bad_field):
    parts = evidence(tmp_path)
    inventory = json.loads(parts[3][0].read_text())
    if bad_field == "reserved_string":
        inventory["reserved_source_groups"] = "100"
    elif bad_field == "reserved_nonstring":
        inventory["reserved_source_groups"] = [100]
    else:
        inventory["fixtures"] = "invalid"
    parts[3][0].write_text(json.dumps(inventory))
    decision = inspect(parts)
    assert decision["status"] == "rejected"
    assert any(error["code"] == "inventory_invalid" and error.get("tier") == "training"
               for error in decision["errors"])


def test_frame_member_and_source_prefix_identity(tmp_path):
    parts = evidence(tmp_path)
    parts[0]["frames"][0]["id"] = "101_00"
    parts[0]["frames"][1]["source_group_candidate"] = "999"
    parts[0]["frames"][2]["group_evidence"]["conservative_source_prefix"] = "999"
    parts[1].write_text(json.dumps(parts[0]))
    codes = {error["code"] for error in inspect(parts)["errors"]}
    assert {"frame_member_identity_mismatch", "group_candidate_invalid", "group_evidence_mismatch"} <= codes


def test_contract_inventory_overlap(tmp_path):
    parts = evidence(tmp_path)
    contract = json.loads(parts[4].read_text())
    contract["fixtures"] = [{"source_group": "external", "image": parts[0]["frames"][0]["image"]}]
    parts[4].write_text(json.dumps(contract))
    assert any(error.get("tier") == "contract" and error["code"] == "checksum_overlap"
               for error in inspect(parts)["errors"])


def test_candidate_group_is_conservative_overlap_identity(tmp_path):
    parts = evidence(tmp_path)
    parts[0]["frames"][0]["source_group_candidate"] = "occupied-prefix"
    parts[1].write_text(json.dumps(parts[0]))
    training = json.loads(parts[3][0].read_text())
    training["reserved_source_groups"] = ["occupied-prefix"]
    parts[3][0].write_text(json.dumps(training))
    assert any(error["code"] == "group_overlap" and error.get("identity") == "occupied-prefix"
               and error.get("tier") == "training" for error in inspect(parts)["errors"])


def test_reservation_keeps_candidate_and_verified_groups(tmp_path):
    parts = evidence(tmp_path)
    parts[0]["frames"][0]["source_group_candidate"] = "archive-prefix"
    reserve_held_out_inventory(parts[3][-1], parts[0], "manifest-hash")
    inventory = json.loads(parts[3][-1].read_text())
    assert "archive-prefix" in inventory["reserved_source_groups"]
    assert inventory["fixtures"][0]["source_group"] == "archive-prefix"
    assert inventory["fixtures"][0]["source_site_camera_time_sequence_group"] == parts[0]["frames"][0]["source_site_camera_time_sequence_group"]
    reserve_held_out_inventory(parts[3][-1], parts[0], "later-manifest")
    inventory = json.loads(parts[3][-1].read_text())
    assert len(inventory["fixtures"]) == 22
    assert {item["manifest_hash"] for item in inventory["fixtures"]} == {"manifest-hash", "later-manifest"}


def test_revision_and_report_binding_are_immutable(database, tmp_path):
    parts = evidence(tmp_path)
    decision, first = database.freeze_evaluation_set(*parts[1:])
    assert decision["status"] == "accepted" and first is not None
    held_out = json.loads(parts[3][-1].read_text())
    assert len(held_out["fixtures"]) == 11
    assert {item["manifest_hash"] for item in held_out["fixtures"]} == {decision["manifest_hash"]}
    assert {item["source_group"] for item in held_out["fixtures"]} == {"100"}
    assert {item["source_site_camera_time_sequence_group"] for item in held_out["fixtures"]} == {
        item["source_site_camera_time_sequence_group"] for item in parts[0]["frames"]}
    report = uuid.uuid4()
    database.bind_evaluation_report(report, first)
    with pytest.raises(EvaluationStoreError, match="evaluation_revision_already_frozen"):
        database.freeze_evaluation_set(*parts[1:])
    manifest = parts[0]
    manifest["frames"][0]["sufficiency_notes"] = "owner corrected notes"
    parts[1].write_text(json.dumps(manifest))
    _, second = database.freeze_evaluation_set(*parts[1:])
    assert second != first
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT revision_id FROM evaluation_report_bindings WHERE report_id = :id"),
                                  {"id": report}).scalar_one() == first
        with pytest.raises(Exception, match="immutable"):
            connection.execute(text("UPDATE evaluation_set_revisions SET manifest_hash = 'changed' WHERE id = :id"), {"id": first})


def test_concurrent_freezes_preserve_both_reservations(database, tmp_path, monkeypatch):
    first = evidence(tmp_path / "first", salt=b"first", group_prefix="first-series")
    second = evidence(tmp_path / "second", salt=b"second", group_prefix="second-series")
    second[3][-1] = first[3][-1]
    original = postgres_adapter.inspect_evaluation_set
    counter = {"active": 0, "maximum": 0}
    counter_lock = threading.Lock()

    def observed_inspection(*args):
        with counter_lock:
            counter["active"] += 1
            counter["maximum"] = max(counter["maximum"], counter["active"])
        try:
            time.sleep(0.05)
            return original(*args)
        finally:
            with counter_lock:
                counter["active"] -= 1

    monkeypatch.setattr(postgres_adapter, "inspect_evaluation_set", observed_inspection)
    start = threading.Barrier(3)

    def freeze(parts):
        start.wait()
        return database.freeze_evaluation_set(*parts[1:])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(freeze, parts) for parts in (first, second)]
        start.wait()
        outcomes = [future.result() for future in futures]
    assert counter["maximum"] == 1
    assert all(decision["status"] == "accepted" and revision for decision, revision in outcomes)
    inventory = json.loads(first[3][-1].read_text())
    assert len(inventory["fixtures"]) == 22
    assert len({item["image"]["sha256"] for item in inventory["fixtures"]}) == 22
    assert not list(first[3][-1].parent.glob(".held_out_evaluation.json.*.tmp"))

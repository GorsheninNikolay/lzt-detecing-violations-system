import base64
import io
import json
import shutil
import uuid
from datetime import datetime, timezone

import pytest
from PIL import Image

from app.application.submission import SubmissionError, submit
from app.application import admission
from app.profiles import cloud_api
from app.profiles.cloud_api import CloudObserverError, validate_owner_evidence


def test_missing_gate_rejects_before_canary():
    with pytest.raises(CloudObserverError, match="cloud_account_id_missing"):
        validate_owner_evidence({}, ["a" * 64], ["a" * 64])


def test_valid_evidence_binds_exact_canary_and_scope():
    image_hash = "a" * 64
    evidence = {key: "checked" for key in ("account_id", "cloud_id", "service_account_id",
                                            "api_key_id", "model_probe_response_id")}
    evidence.update(folder_id="folder", model_probe_returned_uri="gpt://folder/qwen3.6-35b-a3b",
                    authorization_revision=cloud_api.OWNER_DECISION_REVISION,
                    folder_status="ACTIVE", service_account_status="ACTIVE",
                    api_key_scope="yc.ai.foundationModels.execute",
                    model_probe_states={"excavator": "not_detected_in_frame",
                                        "dump_truck": "not_detected_in_frame"},
                    model_probe_request_data_controls={"store": False, "x-data-logging-enabled": "false"})
    evidence.update(checked_at=datetime.now(timezone.utc).isoformat(), paid_account=True,
                    canary_image_sha256=[image_hash], allowed_image_sha256=[image_hash])
    validate_owner_evidence(evidence, [image_hash], [image_hash])
    with pytest.raises(CloudObserverError, match="cloud_upload_scope_invalid"):
        validate_owner_evidence(evidence, [image_hash], ["b" * 64])


def test_expired_gate_rejects_enabled_snapshot():
    image_hash = "a" * 64
    evidence = {"account_id": "billing", "cloud_id": "cloud", "folder_id": "folder",
                "service_account_id": "service", "api_key_id": "key-id", "paid_account": True,
                "folder_status": "ACTIVE", "service_account_status": "ACTIVE",
                "api_key_scope": "yc.ai.foundationModels.execute",
                "model_probe_response_id": "response-1",
                "model_probe_returned_uri": "gpt://folder/qwen3.6-35b-a3b",
                "authorization_revision": cloud_api.OWNER_DECISION_REVISION,
                "canary_image_sha256": [image_hash], "allowed_image_sha256": [image_hash],
                "checked_at": "2020-01-01T00:00:00+00:00"}
    with pytest.raises(CloudObserverError, match="cloud_account_evidence_stale"):
        validate_owner_evidence(evidence, [image_hash], [image_hash])


def test_retired_cloud_profile_rejected_before_publication():
    image = Image.new("RGB", (2, 2), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    body = {"intent": "observation_only", "scenario": "test", "observation_area": "test",
            "period": "2026-09-24T12:00:00+00:00", "image_base64": base64.b64encode(buffer.getvalue()).decode()}
    class Unused:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected side effect: {name}")
    with pytest.raises(SubmissionError, match="profile_retired"):
        submit(Unused(), Unused(), "key", body, uuid.uuid4(), 1,
               {"kind": "cloud_api", "allowed_input_sha256": ["0" * 64]})


@pytest.mark.parametrize("changed,expected", [
    ("owner-attestation-2026-09-24.json", "cloud_held_out_evidence_invalid"),
    ("freeze-decision-v1.json", "cloud_held_out_evidence_invalid"),
    ("held-out-v1.json", "cloud_held_out_evidence_invalid"),
    ("missing-owner", "cloud_held_out_evidence_missing"),
])
def test_held_out_scope_rejects_tampered_or_missing_authorization(tmp_path, changed, expected):
    source = admission.HERE.parent / "evaluation"
    target = tmp_path / "evaluation"
    target.mkdir()
    for name in ("held-out-v1.json", "owner-attestation-2026-09-24.json", "freeze-decision-v1.json"):
        shutil.copyfile(source / name, target / name)
    inventory = admission.ADMISSION / "exclusions" / "held_out_evaluation.json"
    manifest = json.loads((admission.ADMISSION / "manifest.json").read_text())
    canary = [item["image"]["sha256"] for item in manifest["fixtures"]]
    if changed == "missing-owner":
        (target / "owner-attestation-2026-09-24.json").unlink()
    else:
        path = target / changed
        document = json.loads(path.read_text())
        if changed == "owner-attestation-2026-09-24.json":
            document["prototype_use_and_cloud_upload"]["approved"] = False
        elif changed == "freeze-decision-v1.json":
            document["status"] = "rejected"
        else:
            document["frames"][0]["image"]["sha256"] = "0" * 64
        path.write_text(json.dumps(document))
    with pytest.raises(CloudObserverError, match=expected):
        cloud_api.read_held_out_scope(target, inventory, manifest, canary)

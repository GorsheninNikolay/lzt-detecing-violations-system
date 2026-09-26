import base64
import asyncio
import hashlib
import io
import json
import multiprocessing
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from app.application.submission import SubmissionError, submit, submit_series
from app.application import admission
from app.application.executor import ClaimLoop
from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.config import Config
from app.profiles import cloud_api
from app.profiles.cloud_api import CloudObserverError, normalize_response, validate_owner_evidence
from test_admission import isolated_admission_database
from test_startup import database, integration


def _stalled_cloud_worker(_output, _image, _folder, _key, _seconds, _reasoning):
    time.sleep(10)


def test_missing_gate_rejects_before_canary():
    with pytest.raises(CloudObserverError, match="cloud_account_id_missing"):
        validate_owner_evidence({}, ["a" * 64], ["a" * 64])


def test_vm_iam_token_requires_metadata_identity(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    def metadata(http_request, **_kwargs):
        assert http_request.full_url == (
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token")
        assert http_request.get_header("Metadata-flavor") == "Google"
        return Response(b'{"access_token":"short-lived","token_type":"Bearer"}')

    monkeypatch.setattr(cloud_api.request, "urlopen", metadata)
    assert cloud_api._vm_iam_token() == "short-lived"
    monkeypatch.setattr(cloud_api.request, "urlopen", lambda *_args, **_kwargs:
                        Response(b'{"token_type":"Bearer"}'))
    with pytest.raises(CloudObserverError, match="cloud_credential_missing"):
        cloud_api._vm_iam_token()


def test_owner_gate_uses_vm_token_when_no_token_is_configured(monkeypatch):
    monkeypatch.setattr(cloud_api, "_vm_iam_token", lambda: "short-lived")

    class ReachedCloud(RuntimeError):
        pass

    def read(_url, token):
        assert token == "short-lived"
        raise ReachedCloud

    monkeypatch.setattr(cloud_api, "_get", read)
    with pytest.raises(ReachedCloud):
        cloud_api.read_owner_gate("folder", "service", "key-id", "api-key", None, ["a" * 64])


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


def test_response_keeps_raw_served_identity_and_rejects_malformed():
    uri = "gpt://folder/qwen3.6-35b-a3b"
    payload = {"id": "response-1", "status": "completed", "model": uri + "/latest",
               "output_text": '{"excavator":true,"dump_truck":false}',
               "usage": {"input_tokens": 10, "output_tokens": 5}}
    result = normalize_response(payload, uri, 5)
    assert result["model"] == uri + "/latest"
    assert result["states"] == {"excavator": "detected", "dump_truck": "not_detected_in_frame"}
    assert result["provider_response"] is payload
    with pytest.raises(CloudObserverError, match="observation_normalization_failed"):
        normalize_response({**payload, "model": ""}, uri, 5)
    with pytest.raises(CloudObserverError, match="observation_normalization_failed"):
        normalize_response({**payload, "output_text": '{"excavator":false}'}, uri, 5)


def test_response_cap_and_whole_read_deadline(monkeypatch):
    class Response(io.BytesIO):
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.close()

    monkeypatch.setattr(cloud_api.request, "urlopen", lambda *_args, **_kwargs:
                        Response(b"x" * (cloud_api.MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(CloudObserverError, match="observer_response_too_large"):
        cloud_api._read_json(cloud_api.request.Request("https://example.test"), 1)

    class SlowResponse(Response):
        def read(self, size=-1):
            time.sleep(0.02)
            return super().read(size)

    monkeypatch.setattr(cloud_api.request, "urlopen", lambda *_args, **_kwargs:
                        SlowResponse(b'{"ok":true}'))
    with pytest.raises(CloudObserverError, match="observer_timeout"):
        cloud_api._read_json(cloud_api.request.Request("https://example.test"), 0.01)


def test_child_process_deadline_terminates_stalled_worker(monkeypatch):
    monkeypatch.setattr(cloud_api, "_observe_worker", _stalled_cloud_worker)
    before = {child.pid for child in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(CloudObserverError, match="observer_timeout"):
        cloud_api.observe_bounded(None, "folder", "unused", 0.2)
    assert time.monotonic() - started < 3
    assert {child.pid for child in multiprocessing.active_children()} == before


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


def test_unapproved_bytes_rejected_before_publication(monkeypatch):
    monkeypatch.setattr(cloud_api, "paid_call_block_reason", lambda: None)
    image = Image.new("RGB", (2, 2), "white")
    buffer = io.BytesIO()
    image.save(buffer, "JPEG")
    body = {"intent": "observation_only", "scenario": "test", "observation_area": "test",
            "period": "2026-09-24T12:00:00+00:00", "image_base64": base64.b64encode(buffer.getvalue()).decode()}
    class Unused:
        def __getattr__(self, name):
            raise AssertionError(f"unexpected side effect: {name}")
    with pytest.raises(SubmissionError, match="cloud_image_not_authorized"):
        submit(Unused(), Unused(), "key", body, uuid.uuid4(), 1,
               {"kind": "cloud_api", "allowed_input_sha256": ["0" * 64]})


def _cloud_admission_fixture(monkeypatch, tmp_path, response=None, artifact_failure=False, extra=None):
    inventories = [admission.ADMISSION / "exclusions" / f"{tier}.json" for tier in
                   ("training", "validation", "development_acceptance", "held_out_evaluation")]
    _, fixtures = admission.validate_manifest(admission.ADMISSION / "manifest.json", inventories)
    hashes = sorted(fixture["image"]["sha256"] for fixture, _ in fixtures)
    evidence = {"folder_id": "folder", "service_account_id": "service",
                "authorization_revision": cloud_api.OWNER_DECISION_REVISION}
    evidence.update({key: value for key, value in (extra or {}).items()
                     if key not in {"paid_account", "probe_failure", "probe_detected", "extra_scope"}})
    evidence_path = tmp_path / "evidence.json"
    evidence_path.write_text(json.dumps(evidence))

    class Guard:
        def execute(self, statement):
            return self
        def scalar_one(self):
            return True
        def commit(self):
            pass
        def close(self):
            pass

    class Store:
        def __init__(self, url):
            self.engine = self
            self.snapshot = None
            self.failed = []
            self.completed = []
            self.finished = []
            self.successor = None
        def connect(self):
            return Guard()
        def close(self):
            pass
        def create_admission_runs(self, snapshot, manifest, fixtures, watchdog):
            self.snapshot = snapshot
            self.run_ids = [uuid.uuid4() for _ in fixtures]
            return uuid.uuid4(), self.run_ids
        def fail_admission_run(self, run_id, code):
            self.failed.append((run_id, code))
        def reserve_admission_invocation(self, run_id, image):
            return uuid.uuid4()
        def complete_invocation(self, run_id, invocation_id, result):
            self.completed.append(result)
        def create_publication_intent(self, run_id, media_type, key):
            return uuid.uuid4()
        def publication_content_verified(self, *args):
            pass
        def publication_object_published(self, *args):
            pass
        def finish_admission_run(self, run_id, invocation_id, native_intent, input_intent):
            self.finished.append(run_id)
        def authorize_successor(self, profile_id, run_ids):
            assert len(self.finished) == len(run_ids) == 4
            self.successor = uuid.uuid4()
            return self.successor

    class Artifacts:
        def __init__(self, config):
            self.objects = {}
            self.reads = []
        def upload_temporary(self, intent_id, payload, media_type):
            return f"tmp/{intent_id}", hashlib.sha256(payload).hexdigest(), len(payload)
        def publish_final(self, intent_id, payload, media_type, digest, size):
            self.objects[f"sha256/{digest}"] = payload
        def read_verified(self, key, digest, size):
            if artifact_failure:
                raise RuntimeError("artifact_integrity_failed")
            payload = self.objects[key]
            assert hashlib.sha256(payload).hexdigest() == digest and len(payload) == size
            self.reads.append(key)
            return payload

    store, artifacts = Store("unused"), Artifacts(None)
    monkeypatch.setattr(admission, "PostgresStore", lambda url: store)
    monkeypatch.setattr(admission, "ArtifactStore", lambda config: artifacts)
    monkeypatch.setattr(admission.Config, "from_env", lambda: type("Config", (), {
        "database_url": "unused", "cloud_api_key": "transient-test-key",
        "cloud_iam_token": "transient-iam-token", "cloud_api_key_id": "key-id"})())
    requests = []
    def urlopen(http_request, timeout):
        url = http_request.full_url
        if "resource-manager" in url:
            return io.BytesIO(json.dumps({"id": "folder", "cloudId": "cloud", "status": "ACTIVE"}).encode())
        if "/serviceAccounts/" in url:
            return io.BytesIO(json.dumps({"id": "service", "folderId": "folder", "status": "ACTIVE"}).encode())
        if "/apiKeys?" in url:
            return io.BytesIO(json.dumps({"apiKeys": [{"id": "key-id", "serviceAccountId": "service",
                "scopes": (["yc.ai.foundationModels.execute", "yc.ai.translate.execute"]
                           if (extra or {}).get("extra_scope") else ["yc.ai.foundationModels.execute"]),
                "maskedSecret": "****st-key"}]}).encode())
        if "/billableObjectBindings" in url:
            return io.BytesIO(json.dumps({"billableObjectBindings": [{"billableObject":
                {"id": "cloud", "type": "cloud"}}]}).encode())
        if "/billingAccounts" in url:
            return io.BytesIO(json.dumps({"billingAccounts": [{"id": "billing", "active": extra != {"paid_account": False}}]}).encode())
        call = json.loads(http_request.data)
        requests.append(call)
        if (extra or {}).get("probe_failure") and not any(
                item["type"] == "input_image" for item in call["input"][0]["content"]):
            raise extra["probe_failure"]
        if isinstance(response, Exception) and any(item["type"] == "input_image" for item in call["input"][0]["content"]):
            raise response
        uri = "gpt://folder/qwen3.6-35b-a3b"
        has_image = any(item["type"] == "input_image" for item in call["input"][0]["content"])
        payload = (response if response is not None and has_image
                   else {
            "id": "response-1", "status": "completed", "model": uri + "/latest",
            "output_text": ('{"excavator":true,"dump_truck":false}' if has_image or
                            (extra or {}).get("probe_detected") else '{"excavator":false,"dump_truck":false}'),
            "usage": {"input_tokens": 10, "output_tokens": 5}})
        return io.BytesIO(json.dumps(payload).encode())
    read_json = cloud_api._read_json
    monkeypatch.setattr(cloud_api, "_read_json", lambda req, seconds: read_json(req, seconds, transport=urlopen))
    monkeypatch.setattr(cloud_api, "observe_bounded", cloud_api.observe)
    return store, artifacts, requests, inventories, evidence_path


def test_admission_missing_gate_keeps_draft_and_sends_nothing(monkeypatch, tmp_path):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(
        monkeypatch, tmp_path, extra={"paid_account": False})
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None
    assert result["error_code"] == "cloud_paid_account_missing"
    assert len(store.failed) == 4 and not store.completed
    assert not requests and not artifacts.objects


def test_no_image_probe_failure_keeps_draft_and_sends_no_image(monkeypatch, tmp_path):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(
        monkeypatch, tmp_path, extra={"probe_failure": TimeoutError()})
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None
    assert result["error_code"] == "observer_timeout"
    assert len(store.failed) == 4 and not artifacts.objects
    assert len(requests) == 1 and not any(
        item["type"] == "input_image" for item in requests[0]["input"][0]["content"])


@pytest.mark.parametrize("extra,code,request_count", [
    ({"probe_detected": True}, "cloud_model_probe_invalid", 1),
    ({"extra_scope": True}, "cloud_key_scope_invalid", 0),
])
def test_probe_or_key_scope_rejects_before_image(monkeypatch, tmp_path, extra, code, request_count):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(
        monkeypatch, tmp_path, extra=extra)
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None and result["error_code"] == code
    assert len(store.failed) == 4 and len(requests) == request_count and not artifacts.objects
    assert all(not any(item["type"] == "input_image" for item in request_["input"][0]["content"])
               for request_ in requests)


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


def test_missing_held_out_authorization_keeps_draft_and_sends_nothing(monkeypatch, tmp_path):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(monkeypatch, tmp_path)
    def rejected(*_args):
        raise CloudObserverError("cloud_held_out_evidence_missing")
    monkeypatch.setattr(admission, "read_held_out_scope", rejected)
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None
    assert result["error_code"] == "cloud_held_out_evidence_missing"
    assert len(store.failed) == 4 and not requests and not artifacts.objects


def test_extra_evidence_cannot_persist_credentials(monkeypatch, tmp_path):
    store, _, requests, inventories, evidence_path = _cloud_admission_fixture(
        monkeypatch, tmp_path, extra={"api_key": "must-not-persist"})
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None
    assert result["error_code"] == "cloud_owner_decision_missing"
    assert not requests
    assert "must-not-persist" not in json.dumps(store.snapshot)


def test_admission_canary_reads_private_artifacts_and_enables_successor(monkeypatch, tmp_path):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(monkeypatch, tmp_path)
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] == str(store.successor)
    assert len(store.snapshot["allowed_input_sha256"]) == 15
    assert len(store.snapshot["owner_evidence"]["canary_image_sha256"]) == 4
    assert len(store.snapshot["rights"]["held_out"]["image_sha256"]) == 11
    assert not store.failed and len(store.completed) == len(store.finished) == 4
    assert len(requests) == 9
    assert store.snapshot["owner_evidence"]["model_probe_states"] == {
        "excavator": "not_detected_in_frame", "dump_truck": "not_detected_in_frame"}
    assert store.snapshot["owner_evidence"]["model_probe_request_data_controls"] == {
        "store": False, "x-data-logging-enabled": "false"}
    assert all(item["returned_model_identity"] == "gpt://folder/qwen3.6-35b-a3b/latest"
               for item in store.completed)
    assert all(item["states"] == {"excavator": "detected", "dump_truck": "not_detected_in_frame"}
               for item in store.completed)
    assert all(call["store"] is False and call["text"]["format"]["strict"] is True for call in requests)
    assert sum(any(item["type"] == "input_image" for item in call["input"][0]["content"]) for call in requests) == 4
    assert len(artifacts.reads) == 8
    native = [json.loads(payload) for payload in artifacts.objects.values() if payload.startswith(b"{")]
    assert native and native[0]["response"]["provider_response"]["model"].endswith("/latest")
    assert native[0]["request_data_controls"] == {"store": False, "x-data-logging-enabled": "false"}
    assert all(json.loads(payload)["credential_key_id"] == "key-id" for payload in artifacts.objects.values()
               if payload.startswith(b'{"credential_key_id"'))


@pytest.mark.parametrize("response,artifact_failure,expected_code", [
    (TimeoutError(), False, "observer_timeout"),
    ({"id": "response-1", "status": "completed", "model": "gpt://folder/qwen3.6-35b-a3b",
      "output_text": '{"excavator":1,"dump_truck":false}', "usage": {"input_tokens": 1, "output_tokens": 1}}, False,
     "observation_normalization_failed"),
    ({"id": "response-1", "status": "completed", "model": "",
      "output_text": '{"excavator":true,"dump_truck":false}', "usage": {"input_tokens": 1, "output_tokens": 1}}, False,
     "observation_normalization_failed"),
    (None, True, "artifact_integrity_failed"),
])
def test_failed_canary_stays_draft_without_fallback(monkeypatch, tmp_path, response, artifact_failure, expected_code):
    store, artifacts, requests, inventories, evidence_path = _cloud_admission_fixture(
        monkeypatch, tmp_path, response, artifact_failure)
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", inventories, evidence_path, 60)
    assert result["admitted_profile_id"] is None and store.successor is None
    assert result["error_code"] == expected_code
    assert len(requests) == 3 and len(store.failed) == 4
    assert all(code == "admission_canary_failed" for _, code in store.failed[1:])
    assert not store.finished


def test_persisted_cloud_successor_held_out_and_series(isolated_admission_database, integration, monkeypatch, tmp_path):
    held_path = os.getenv("TEST_HELD_OUT_IMAGE_PATH")
    if not held_path:
        pytest.skip("Set TEST_HELD_OUT_IMAGE_PATH to the approved first held-out JPEG")
    _, fixtures = admission.validate_manifest(admission.ADMISSION / "manifest.json", [
        admission.ADMISSION / "exclusions" / f"{tier}.json" for tier in
        ("training", "validation", "development_acceptance", "held_out_evaluation")])
    hashes = sorted(fixture["image"]["sha256"] for fixture, _ in fixtures)
    held_out, _ = cloud_api.read_held_out_scope(admission.HERE.parent / "evaluation",
        admission.ADMISSION / "exclusions" / "held_out_evaluation.json",
        json.loads((admission.ADMISSION / "manifest.json").read_text()), hashes)
    allowed = sorted(hashes + held_out)
    evidence = {"account_id": "billing", "cloud_id": "cloud", "folder_id": "folder",
                "service_account_id": "service", "api_key_id": "key-id", "paid_account": True,
                "folder_status": "ACTIVE", "service_account_status": "ACTIVE",
                "api_key_scope": "yc.ai.foundationModels.execute", "model_probe_response_id": "probe-1",
                "model_probe_returned_uri": "gpt://folder/qwen3.6-35b-a3b/latest",
                "model_probe_states": {"excavator": "not_detected_in_frame",
                                       "dump_truck": "not_detected_in_frame"},
                "model_probe_request_data_controls": {"store": False, "x-data-logging-enabled": "false"},
                "authorization_revision": cloud_api.OWNER_DECISION_REVISION,
                "canary_image_sha256": hashes, "allowed_image_sha256": allowed,
                "checked_at": datetime.now(timezone.utc).isoformat()}
    monkeypatch.setattr(admission, "read_owner_gate", lambda *_: evidence)
    from app.application import executor
    gate_calls = []
    fail_gate_at = [None]
    def fresh_gate(_folder, _service, key_id, key, _token, _hashes, allowed_hashes):
        assert key_id == "rotated-key" and key == "rotated-secret"
        assert allowed_hashes == allowed
        gate_calls.append(key_id)
        if len(gate_calls) == fail_gate_at[0]:
            raise CloudObserverError("observer_quota_failed")
        return {**evidence, "api_key_id": key_id, "model_probe_response_id": "rotated-probe"}
    monkeypatch.setattr(executor, "read_owner_gate", fresh_gate)
    observed_keys = []
    observed_hashes = []
    def observed(self, image, timeout_seconds):
        observed_keys.append(self.api_key)
        observed_hashes.append(hashlib.sha256(image).hexdigest())
        return {"states": {"excavator": "detected", "dump_truck": "not_detected_in_frame"},
                "returned_model_identity": "gpt://folder/qwen3.6-35b-a3b/latest",
                "returned_request_identity": "response-1", "actual_device": "remote_unreported",
                "preprocessing_revision": cloud_api.PREPROCESSING_REVISION, "latency_ms": 1.0,
                "peak_memory_bytes": None,
                "native": {"response_id": "response-1", "request_data_controls": {"store": False}}}
    monkeypatch.setattr(cloud_api.CloudObserver, "observe", observed)
    monkeypatch.setattr(cloud_api, "paid_call_block_reason", lambda: None)
    monkeypatch.setenv("YANDEX_AI_STUDIO_API_KEY", "transient-test-key")
    monkeypatch.setenv("YANDEX_CLOUD_IAM_TOKEN", "transient-iam-token")
    monkeypatch.setenv("YANDEX_AI_STUDIO_API_KEY_ID", "key-id")
    owner_path = tmp_path / "owner.json"
    owner_path.write_text(json.dumps({"folder_id": "folder", "service_account_id": "service",
                                      "authorization_revision": cloud_api.OWNER_DECISION_REVISION}))
    result = admission.admit_cloud(admission.ADMISSION / "manifest.json", [
        admission.ADMISSION / "exclusions" / f"{tier}.json" for tier in
        ("training", "validation", "development_acceptance", "held_out_evaluation")], owner_path, 60)
    assert result["admitted_profile_id"]
    store = PostgresStore(isolated_admission_database)
    config = Config.from_env()
    artifacts = ArtifactStore(config)
    try:
        profile_id = uuid.UUID(result["admitted_profile_id"])
        snapshot, revision = store.require_authorized(profile_id)
        assert revision == 1 and snapshot["owner_evidence"]["model_probe_response_id"] == "probe-1"
        assert snapshot["owner_evidence"]["api_key_id"] == "key-id"
        assert snapshot["allowed_input_sha256"] == allowed
        assert len(result["run_ids"]) == 4
        monkeypatch.setenv("YANDEX_AI_STUDIO_API_KEY", "rotated-secret")
        monkeypatch.setenv("YANDEX_AI_STUDIO_API_KEY_ID", "rotated-key")
        image = fixtures[0][1]
        body = {"intent": "observation_only", "scenario": "admission fixture",
                "observation_area": "test", "period": "2026-09-25T12:00:00+00:00",
                "image_base64": base64.b64encode(image).decode()}
        _, run_id = submit(store, artifacts, "cloud-" + uuid.uuid4().hex, body, profile_id, revision, snapshot)
        work = store.claim_ordinary(profile_id, revision, 60)
        loop = ClaimLoop()
        loop.store, loop.artifacts = store, artifacts
        asyncio.run(loop._execute(work, revision))
        ordinary = store.read_ordinary(run_id)
        assert ordinary["state"] == "succeeded"
        assert ordinary["outcome"] == "observations_only"
        assert ordinary["native_evidence"] is not None
        assert observed_keys[-1] == "rotated-secret"
        native_ref = ordinary["native_evidence"]
        native = json.loads(artifacts.read_verified("sha256/" + native_ref["sha256"],
            native_ref["sha256"], native_ref["size"]))
        assert native["response"]["credential_key_id"] == "rotated-key"
        assert native["response"]["owner_gate"]["model_probe_response_id"] == "rotated-probe"
        assert native["response"]["owner_gate"]["account_id"] == "billing"
        assert native["response"]["owner_gate"]["checked_at"] == evidence["checked_at"]
        held_frame = json.loads((admission.HERE.parent / "evaluation" / "held-out-v1.json").read_text())["frames"][0]
        held_image = Path(held_path).read_bytes()
        assert hashlib.sha256(held_image).hexdigest() == held_frame["image"]["sha256"]
        held_body = {**body, "image_base64": base64.b64encode(held_image).decode()}
        _, held_run = submit(store, artifacts, "cloud-" + uuid.uuid4().hex,
                             held_body, profile_id, revision, snapshot)
        asyncio.run(loop._execute(store.claim_ordinary(profile_id, revision, 60), revision))
        assert store.read_ordinary(held_run)["state"] == "succeeded"
        assert observed_hashes[-1] == held_frame["image"]["sha256"]

        series_body = {key: value for key, value in body.items() if key != "image_base64"}
        series_body["images_base64"] = [base64.b64encode(fixtures[index][1]).decode() for index in (0, 1)]
        _, series_run = submit_series(store, artifacts, "cloud-" + uuid.uuid4().hex,
                                      series_body, profile_id, revision, snapshot)
        before_series_gates = len(gate_calls)
        fail_gate_at[0] = before_series_gates + 2
        asyncio.run(loop._execute(store.claim_ordinary(profile_id, revision, 60), revision))
        fail_gate_at[0] = None
        series = store.read_ordinary(series_run)
        assert series["state"] == "failed" and series["error_code"] == "observer_quota_failed"
        assert len(series["observations"]) == 2 and len(series["native_evidence_by_frame"]) == 1
        assert len(gate_calls) == before_series_gates + 2
        first_native = series["native_evidence_by_frame"][0]
        assert artifacts.read_verified("sha256/" + first_native["sha256"],
                                       first_native["sha256"], first_native["size"])
        _, failed_source = submit(store, artifacts, "cloud-" + uuid.uuid4().hex,
                                  body, profile_id, revision, snapshot)
        failed_work = store.claim_ordinary(profile_id, revision, 60)
        store.fail_ordinary(failed_source, failed_work["owner"], "observer_timeout")
        retry_id = store.retry_ordinary(failed_source, profile_id, revision, snapshot, artifacts)
        assert store.read_ordinary(retry_id)["state"] == "queued"
        retry_work = store.claim_ordinary(profile_id, revision, 60)
        class FutureDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                from datetime import timedelta
                return datetime.now(tz) + timedelta(days=2)
        monkeypatch.setattr(cloud_api, "datetime", FutureDateTime)
        asyncio.run(loop._execute(retry_work, revision))
        assert store.read_ordinary(retry_id)["error_code"] == "profile_owner_evidence_expired"
        store.revoke_authorization(profile_id, revision, "owner_revoked")
        with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
            store.require_authorized(profile_id)
    finally:
        store.close()


def test_paid_transport_fails_closed_before_network(monkeypatch):
    def unexpected_network(*args, **kwargs):
        pytest.fail("Paid request reached the network without an upper-bound reservation")
    monkeypatch.setattr(cloud_api.request, "urlopen", unexpected_network)
    with pytest.raises(CloudObserverError, match="cloud_budget_reservation_unavailable"):
        cloud_api._read_json(cloud_api.request.Request(cloud_api.ENDPOINT), 1)

"""Yandex AI Studio presence-only image observer."""

import base64
import hashlib
import json
import multiprocessing
import platform
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request
from urllib.parse import quote

from app.domain.evaluation_set import canonical_hash


MODEL = "qwen3.6-35b-a3b"
ADAPTER_VERSION = "qwen3.6-presence-v2"
PREPROCESSING_REVISION = "base64-jpeg-v1"
ENDPOINT = "https://ai.api.cloud.yandex.net/v1/responses"
OWNER_DECISION_REVISION = "1512020047aa5e2b2fc343f78f9881a0a2c5914c"
ADMISSION_MANIFEST_SHA256 = "57a27283c36df6e6d2da87939bf170f641cb8440ac2f0d01d58e17fb8c5a1909"
FREEZE_DECISION_SHA256 = "3ea6c7ce52a7cd589ec58c50874e0b25f2eae0444317678af2deae1ec85d74af"
OWNER_ATTESTATION_SHA256 = "18363ef09c6e75a29da7d21a4d4e9d5430f4c726452d74a64cfeae11f7b0ad89"
MAX_RESPONSE_BYTES = 65536
GATE_SECONDS = 30
TEMPERATURE = 0
PROMPT = (
    'Inspect this construction-site image. Mark each class true only if it is visibly present. '
    'Do not infer hidden equipment. Return the two requested booleans.'
)
RESPONSE_FORMAT = {"type": "json_schema", "name": "construction_presence", "strict": True,
                   "schema": {"type": "object", "properties": {
                       "excavator": {"type": "boolean"}, "dump_truck": {"type": "boolean"}},
                       "required": ["excavator", "dump_truck"], "additionalProperties": False}}


class CloudObserverError(RuntimeError):
    pass


EVIDENCE_FIELDS = frozenset({
    "account_id", "cloud_id", "folder_id", "service_account_id", "api_key_id",
    "checked_at", "paid_account", "folder_status", "service_account_status",
    "api_key_scope", "model_probe_response_id", "model_probe_returned_uri",
    "model_probe_states", "model_probe_request_data_controls",
    "authorization_revision", "canary_image_sha256", "allowed_image_sha256",
})


def validate_owner_evidence(evidence: dict, canary_hashes: list[str], allowed_hashes: list[str]) -> None:
    required = ("account_id", "cloud_id", "folder_id", "service_account_id", "api_key_id",
                "checked_at", "model_probe_response_id", "model_probe_returned_uri")
    if not isinstance(evidence, dict):
        raise CloudObserverError("cloud_owner_account_gate_missing")
    if set(evidence) - EVIDENCE_FIELDS:
        raise CloudObserverError("cloud_owner_evidence_extra_fields")
    for field in required:
        if not isinstance(evidence.get(field), str) or not evidence[field].strip():
            raise CloudObserverError("cloud_" + field + "_missing")
    try:
        checked = datetime.fromisoformat(evidence["checked_at"])
        if checked.tzinfo is None or not 0 <= (datetime.now(timezone.utc) - checked).total_seconds() <= 86400:
            raise ValueError
    except ValueError:
        raise CloudObserverError("cloud_account_evidence_stale") from None
    if evidence.get("paid_account") is not True:
        raise CloudObserverError("cloud_paid_account_missing")
    if evidence.get("folder_status") != "ACTIVE" or evidence.get("service_account_status") != "ACTIVE":
        raise CloudObserverError("cloud_account_identity_invalid")
    if evidence.get("api_key_scope") != "yc.ai.foundationModels.execute":
        raise CloudObserverError("cloud_key_scope_invalid")
    if evidence.get("authorization_revision") != OWNER_DECISION_REVISION:
        raise CloudObserverError("cloud_owner_decision_missing")
    if evidence.get("model_probe_returned_uri") not in (
            f"gpt://{evidence.get('folder_id')}/{MODEL}",
            f"gpt://{evidence.get('folder_id')}/{MODEL}/latest"):
        raise CloudObserverError("observer_identity_invalid")
    if (evidence.get("model_probe_states") != {"excavator": "not_detected_in_frame",
                                                "dump_truck": "not_detected_in_frame"}
            or evidence.get("model_probe_request_data_controls") !=
            {"store": False, "x-data-logging-enabled": "false"}):
        raise CloudObserverError("cloud_model_probe_invalid")
    if evidence.get("canary_image_sha256") != sorted(canary_hashes):
        raise CloudObserverError("cloud_canary_authorization_missing")
    if evidence.get("allowed_image_sha256") != sorted(allowed_hashes):
        raise CloudObserverError("cloud_upload_scope_invalid")


def paid_call_block_reason() -> str | None:
    return "cloud_budget_reservation_unavailable"


def _read_json(http_request: request.Request, seconds: float, *, transport=None) -> dict:
    if http_request.full_url == ENDPOINT and transport is None and paid_call_block_reason():
        # Token usage after a response cannot reserve an upper bound before a paid call.
        raise CloudObserverError("cloud_budget_reservation_unavailable")
    started = time.monotonic()
    try:
        with (transport or request.urlopen)(http_request, timeout=seconds) as response:
            chunks = bytearray()
            while True:
                remaining = seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise CloudObserverError("observer_timeout")
                socket = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
                if socket is not None:
                    socket.settimeout(remaining)
                chunk = response.read(min(8192, MAX_RESPONSE_BYTES + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise CloudObserverError("observer_response_too_large")
            if time.monotonic() - started > seconds:
                raise CloudObserverError("observer_timeout")
            payload = json.loads(chunks)
            if not isinstance(payload, dict):
                raise ValueError
            return payload
    except error.HTTPError as exc:
        raise CloudObserverError("observer_quota_failed" if exc.code == 429 else
                                 "observer_access_failed" if exc.code in (401, 403) else
                                 "observer_http_failed") from None
    except error.URLError as exc:
        raise CloudObserverError("observer_timeout" if isinstance(exc.reason, TimeoutError)
                                 else "observer_transport_failed") from None
    except (TimeoutError, OSError) as exc:
        raise CloudObserverError("observer_timeout" if isinstance(exc, TimeoutError)
                                 else "observer_transport_failed") from None
    except (ValueError, UnicodeError):
        raise CloudObserverError("observation_normalization_failed") from None


def _get(url: str, iam_token: str) -> dict:
    return _read_json(request.Request(url, headers={"Authorization": "Bearer " + iam_token}), GATE_SECONDS)


def _vm_iam_token() -> str:
    try:
        payload = _read_json(request.Request(
            "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"}), 3)
        token = payload.get("access_token")
        if payload.get("token_type") != "Bearer" or not isinstance(token, str) or not token:
            raise ValueError
        return token
    except (CloudObserverError, ValueError):
        raise CloudObserverError("cloud_credential_missing") from None


def read_owner_gate(folder_id: str, service_account_id: str, api_key_id: str,
                    api_key: str, iam_token: str | None, canary_hashes: list[str],
                    allowed_hashes: list[str] | None = None) -> dict:
    if not all((folder_id, service_account_id, api_key_id, api_key)):
        raise CloudObserverError("cloud_credential_missing")
    iam_token = iam_token or _vm_iam_token()
    folder = _get("https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders/" + quote(folder_id), iam_token)
    service = _get("https://iam.api.cloud.yandex.net/iam/v1/serviceAccounts/" + quote(service_account_id), iam_token)
    if (folder.get("id") != folder_id or folder.get("status") != "ACTIVE"
            or service.get("id") != service_account_id or service.get("folderId") != folder_id
            or service.get("status") != "ACTIVE"):
        raise CloudObserverError("cloud_account_identity_invalid")
    cloud_id = folder.get("cloudId")
    if not isinstance(cloud_id, str) or not cloud_id:
        raise CloudObserverError("cloud_account_identity_invalid")
    accounts = _get("https://billing.api.cloud.yandex.net/billing/v1/billingAccounts?pageSize=1000", iam_token)
    if accounts.get("nextPageToken"):
        raise CloudObserverError("cloud_billing_readback_incomplete")
    account_id = None
    for account in accounts.get("billingAccounts", []):
        if account.get("active") is not True:
            continue
        candidate_id = account.get("id")
        bindings = _get("https://billing.api.cloud.yandex.net/billing/v1/billingAccounts/"
                        + quote(candidate_id) + "/billableObjectBindings?pageSize=1000", iam_token)
        if bindings.get("nextPageToken"):
            raise CloudObserverError("cloud_billing_readback_incomplete")
        if any(item.get("billableObject") == {"id": cloud_id, "type": "cloud"}
               for item in bindings.get("billableObjectBindings", [])):
            account_id = candidate_id
            break
    if not account_id:
        raise CloudObserverError("cloud_paid_account_missing")
    keys = _get("https://iam.api.cloud.yandex.net/iam/v1/apiKeys?serviceAccountId="
                + quote(service_account_id) + "&pageSize=1000", iam_token)
    if keys.get("nextPageToken"):
        raise CloudObserverError("cloud_key_readback_incomplete")
    matching = [item for item in keys.get("apiKeys", []) if item.get("id") == api_key_id]
    scopes = matching[0].get("scopes") if matching else None
    if scopes is None and matching:
        scopes = [matching[0].get("scope")]
    if (len(matching) != 1 or matching[0].get("serviceAccountId") != service_account_id
            or scopes != ["yc.ai.foundationModels.execute"]
            or (matching[0].get("scope") is not None
                and matching[0]["scope"] != "yc.ai.foundationModels.execute")
            or not isinstance(matching[0].get("maskedSecret"), str)
            or matching[0]["maskedSecret"][-6:] != api_key[-6:]):
        raise CloudObserverError("cloud_key_scope_invalid")
    expires = matching[0].get("expiresAt")
    if expires and datetime.fromisoformat(expires.replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        raise CloudObserverError("cloud_key_scope_invalid")
    probe = observe_bounded(None, folder_id, api_key, GATE_SECONDS, "none")
    if probe["states"] != {"excavator": "not_detected_in_frame",
                           "dump_truck": "not_detected_in_frame"}:
        raise CloudObserverError("cloud_model_probe_invalid")
    allowed = allowed_hashes if allowed_hashes is not None else canary_hashes
    evidence = {"account_id": account_id, "cloud_id": cloud_id, "folder_id": folder_id,
                "service_account_id": service_account_id, "api_key_id": api_key_id,
                "checked_at": datetime.now(timezone.utc).isoformat(), "paid_account": True,
                "folder_status": "ACTIVE", "service_account_status": "ACTIVE",
                "api_key_scope": "yc.ai.foundationModels.execute",
                "model_probe_response_id": probe["response_id"],
                "model_probe_returned_uri": probe["model"],
                "model_probe_states": probe["states"],
                "model_probe_request_data_controls": probe["request_data_controls"],
                "authorization_revision": OWNER_DECISION_REVISION,
                "canary_image_sha256": sorted(canary_hashes), "allowed_image_sha256": sorted(allowed)}
    validate_owner_evidence(evidence, canary_hashes, allowed)
    return evidence


def read_held_out_scope(evaluation_dir: Path, exclusion_path: Path,
                        canary_manifest: dict, canary_hashes: list[str]) -> tuple[list[str], dict]:
    try:
        manifest = json.loads((evaluation_dir / "held-out-v1.json").read_bytes())
        owner_bytes = (evaluation_dir / "owner-attestation-2026-09-24.json").read_bytes()
        owner = json.loads(owner_bytes)
        freeze_bytes = (evaluation_dir / "freeze-decision-v1.json").read_bytes()
        freeze = json.loads(freeze_bytes)
        inventory = json.loads(exclusion_path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise CloudObserverError("cloud_held_out_evidence_missing") from None
    try:
        frames = manifest["frames"]
        hashes = [frame["image"]["sha256"] for frame in frames]
        owner_hash = digest(owner_bytes)
        freeze_hash = digest(freeze_bytes)
        manifest_hash = canonical_hash(manifest)
        inventory_hash = canonical_hash(inventory)
        referenced_owner = manifest["evidence_artifacts"]["owner_attestation"]
        freeze_inventory = {item["name"]: item["sha256"] for item in freeze["inventory_evidence"]}
        occupied_groups = set(canary_manifest["reserved_source_groups"])
        occupied_groups.update(fixture["source_site_camera_time_sequence_group"]
                               for fixture in canary_manifest["fixtures"])
        if (not isinstance(frames, list) or len(frames) != 11 or len(set(hashes)) != 11
                or len(set(canary_hashes)) != 4 or set(hashes) & set(canary_hashes)
                or any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
                       for value in hashes)
                or manifest.get("schema_revision") != "held-out-evaluation-v1"
                or manifest["cloud_upload_authorization"] != {"granted": True,
                    "evidence": "owner-attestation-2026-09-24.json"}
                or manifest["source_non_use_attestation"]["confirmed"] is not True
                or any(frame.get("cloud_upload_permission") is not True
                       or frame.get("source_rights", {}).get("status") != "owner_approved_with_caveat"
                       or frame.get("source_group_candidate") in occupied_groups
                       or frame.get("source_site_camera_time_sequence_group") in occupied_groups
                       for frame in frames)
                or referenced_owner != {"path": "owner-attestation-2026-09-24.json", "sha256": owner_hash}
                or owner_hash != OWNER_ATTESTATION_SHA256
                or owner.get("schema_revision") != "evaluation-owner-attestation-v1"
                or owner["prototype_use_and_cloud_upload"]["approved"] is not True
                or owner["non_use"]["confirmed"] is not True
                or owner["selected_image_sha256"] != hashes
                or freeze_hash != FREEZE_DECISION_SHA256 or freeze.get("status") != "accepted"
                or freeze.get("errors") != [] or freeze.get("manifest_hash") != manifest_hash
                or freeze.get("reserved_frame_count") != 11
                or freeze_inventory.get("held_out_evaluation") != inventory_hash
                or inventory.get("tier") != "held_out_evaluation"
                or len(inventory["fixtures"]) != 11
                or {item["image"]["sha256"] for item in inventory["fixtures"]} != set(hashes)
                or any(item.get("manifest_hash") != manifest_hash for item in inventory["fixtures"])):
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError):
        raise CloudObserverError("cloud_held_out_evidence_invalid") from None
    return hashes, {"manifest_hash": manifest_hash, "owner_attestation_sha256": owner_hash,
                    "freeze_decision_sha256": freeze_hash, "inventory_hash": inventory_hash,
                    "image_sha256": sorted(hashes)}


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def draft_snapshot(lock_file: Path, fixture_manifest: dict, folder_id: str, service_account_id: str,
                   allowed_image_hashes: list[str], evidence: dict,
                   held_out_evidence: dict | None = None) -> dict:
    if (not allowed_image_hashes or len(set(allowed_image_hashes)) != len(allowed_image_hashes)
            or any(len(value) != 64 or any(char not in "0123456789abcdef" for char in value)
                   for value in allowed_image_hashes)):
        raise CloudObserverError("cloud_upload_scope_invalid")
    model_uri = f"gpt://{folder_id}/{MODEL}"
    return {
        "kind": "cloud_api",
        "adapter": {"code": "yandex_ai_studio", "version": ADAPTER_VERSION,
                    "entrypoint": "app.profiles.cloud_api.CloudObserver",
                    "bundle_sha256": digest(Path(__file__).read_bytes())},
        "requested_model_identity": {"id": model_uri},
        "returned_model_identity": None,
        "identity_gap": "hosted_model_revision_unpinnable",
        "endpoint": ENDPOINT,
        "service_account_id": service_account_id,
        "folder_id": folder_id,
        "api_key_scope": "yc.ai.foundationModels.execute",
        "request_identity": model_uri,
        "preprocessing": PREPROCESSING_REVISION,
        "prompt": PROMPT,
        "response_format": RESPONSE_FORMAT,
        "reasoning_effort": "none",
        "temperature": TEMPERATURE,
        "allowed_input_sha256": sorted(allowed_image_hashes),
        "owner_evidence": evidence,
        "taxonomy": {"excavator": "excavator", "dump_truck": "dump_truck"},
        "observation_contract": "presence-only-v1", "outcome_contract": "observations-only-v1",
        "rights": {"fixtures": fixture_manifest["declared_license"],
                   "manifest_sha256": digest(canonical_bytes(fixture_manifest)),
                   "cloud_upload_authorization": evidence.get("authorization_revision"),
                   "held_out": held_out_evidence},
        "runtime": {"python": platform.python_version(), "sdk_retries": 0, "concurrency": 1,
                    "device": "remote_unreported", "uv_lock_sha256": digest(lock_file.read_bytes())},
    }


def normalize_response(payload: dict, model_uri: str, latency_ms: float) -> dict:
    try:
        returned_uri = payload["model"]
        if (payload["status"] != "completed" or not isinstance(returned_uri, str)
                or returned_uri not in (model_uri, model_uri + "/latest")):
            raise ValueError
        output = payload.get("output_text")
        if not isinstance(output, str):
            parts = [part["text"] for item in payload["output"] if item.get("type") == "message"
                     for part in item["content"] if part.get("type") == "output_text"]
            if len(parts) != 1:
                raise ValueError
            output = parts[0]
        labels = json.loads(output)
        if set(labels) != {"excavator", "dump_truck"} or any(type(value) is not bool for value in labels.values()):
            raise ValueError
        usage = payload["usage"]
        incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
        outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
        details = usage.get("input_tokens_details", usage.get("prompt_tokens_details", {}))
        cached = details.get("cached_tokens", 0)
        if type(incoming) is not int or type(outgoing) is not int or incoming < 0 or outgoing < 0:
            raise ValueError
        if type(cached) is not int or not 0 <= cached <= incoming:
            raise ValueError
        response_id = payload["id"]
        if not isinstance(response_id, str) or not response_id:
            raise ValueError
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        raise CloudObserverError("observation_normalization_failed") from None
    return {
        "response_id": response_id, "model": returned_uri, "response": output,
        "provider_response": payload,
        "states": {name: "detected" if value else "not_detected_in_frame" for name, value in labels.items()},
        "latency_ms": latency_ms,
        "usage": {"input_tokens": incoming, "cached_tokens": cached, "output_tokens": outgoing},
    }


def observe(image: bytes | None, folder_id: str, api_key: str, timeout_seconds: float = 60,
            reasoning_effort: str = "medium") -> dict:
    if reasoning_effort not in {"none", "medium"}:
        raise ValueError("unsupported_reasoning_effort")
    model_uri = f"gpt://{folder_id}/{MODEL}"
    content = [{"type": "input_text", "text": PROMPT if image is not None else
                "No image is attached. Return false for both classes using the required schema."}]
    if image is not None:
        content.append({"type": "input_image", "image_url": "data:image/jpeg;base64," + base64.b64encode(image).decode(),
                        "detail": "auto"})
    body = json.dumps({
        "model": model_uri, "store": False, "text": {"format": RESPONSE_FORMAT},
        "temperature": TEMPERATURE,
        "reasoning": {"effort": reasoning_effort},
        "input": [{"role": "user", "content": content}],
    }).encode()
    http_request = request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": "Api-Key " + api_key, "OpenAI-Project": folder_id,
                 "Content-Type": "application/json", "x-data-logging-enabled": "false"},
    )
    started = time.monotonic()
    payload = _read_json(http_request, timeout_seconds)
    result = normalize_response(payload, model_uri, (time.monotonic() - started) * 1000)
    result["reasoning_effort"] = reasoning_effort
    result["request_data_controls"] = {"store": False, "x-data-logging-enabled": "false"}
    return result


def _observe_worker(output, image: bytes | None, folder_id: str, api_key: str,
                    seconds: float, reasoning_effort: str) -> None:
    try:
        output.send(("ok", observe(image, folder_id, api_key, seconds, reasoning_effort)))
    except CloudObserverError as exc:
        output.send(("error", str(exc)))
    except Exception:
        output.send(("error", "observer_execution_failed"))
    finally:
        output.close()


def observe_bounded(image: bytes | None, folder_id: str, api_key: str, seconds: float,
                    reasoning_effort: str = "none") -> dict:
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(False)
    process = context.Process(target=_observe_worker,
        args=(child, image, folder_id, api_key, seconds, reasoning_effort))
    process.start()
    child.close()
    try:
        if not parent.poll(seconds):
            raise CloudObserverError("observer_timeout")
        try:
            status, result = parent.recv()
        except EOFError:
            raise CloudObserverError("observer_execution_failed") from None
        if status != "ok":
            raise CloudObserverError(result)
        return result
    finally:
        if process.is_alive():
            process.terminate()
        process.join(5)
        if process.is_alive():
            process.kill()
            process.join()
        parent.close()


class CloudObserver:
    def __init__(self, snapshot: dict, api_key: str):
        if (snapshot.get("kind") != "cloud_api" or snapshot.get("endpoint") != ENDPOINT
                or snapshot.get("reasoning_effort") != "none" or snapshot.get("temperature") != TEMPERATURE
                or not api_key
                or snapshot.get("prompt") != PROMPT or snapshot.get("response_format") != RESPONSE_FORMAT
                or snapshot.get("requested_model_identity") != {"id": f"gpt://{snapshot.get('folder_id')}/{MODEL}"}
                or not snapshot.get("allowed_input_sha256")):
            raise CloudObserverError("cloud_profile_invalid")
        self.snapshot = snapshot
        self.api_key = api_key

    def observe(self, image: bytes, timeout_seconds: float) -> dict:
        if digest(image) not in self.snapshot["allowed_input_sha256"]:
            raise CloudObserverError("cloud_image_not_authorized")
        result = observe_bounded(image, self.snapshot["folder_id"], self.api_key, timeout_seconds,
                         self.snapshot["reasoning_effort"])
        if result["model"] not in (self.snapshot["requested_model_identity"]["id"],
                                   self.snapshot["requested_model_identity"]["id"] + "/latest"):
            raise CloudObserverError("observer_identity_invalid")
        if self.snapshot.get("returned_model_identity") and result["model"] != self.snapshot["returned_model_identity"]:
            raise CloudObserverError("observer_identity_invalid")
        return {"returned_model_identity": result["model"],
                "returned_request_identity": result["response_id"], "actual_device": "remote_unreported",
                "preprocessing_revision": PREPROCESSING_REVISION,
                "latency_ms": result["latency_ms"], "peak_memory_bytes": None,
                "states": result["states"],
                "native": {"response_id": result["response_id"], "response": result["response"],
                           "provider_response": result["provider_response"],
                           "request_data_controls": result["request_data_controls"],
                           "usage": result["usage"]}}

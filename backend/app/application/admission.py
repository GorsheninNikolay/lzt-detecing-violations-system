"""Operator entrypoint for the pinned local observer admission."""

import argparse
import hashlib
import io
import json
import os
import signal
import subprocess
import time
import uuid
from pathlib import Path
from PIL import Image
from sqlalchemy import text

from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import PostgresStore
from app.config import Config
from app.domain.observations import ManifestError, validate_manifest
from app.profiles.cloud_api import (ADMISSION_MANIFEST_SHA256, OWNER_DECISION_REVISION, CloudObserver, CloudObserverError,
                                    canonical_bytes as cloud_bytes, draft_snapshot as cloud_snapshot,
                                    read_held_out_scope, read_owner_gate, validate_owner_evidence)
from app.profiles.grounding_dino import (
    PREPROCESSING_REVISION, GroundingDinoCpu, ObserverError, canonical_bytes,
    draft_snapshot, prepare_snapshot, verify_snapshot,
)


HERE = Path(__file__).resolve().parents[2]
ADMISSION = HERE / "admission"
SAFE_FAILURE_CODES = {
    "bootstrap_watchdog_expired", "cpu_baseline_platform_mismatch", "cpu_baseline_unverifiable",
    "model_snapshot_incomplete", "model_snapshot_hash_mismatch", "model_weight_mapping_failed",
    "actual_device_mismatch", "observation_normalization_failed", "fixture_manifest_invalid",
    "fixture_group_overlap", "fixture_checksum_overlap", "exclusion_inventory_invalid",
    "exclusion_inventory_incomplete", "fixture_hash_mismatch", "observer_execution_failed",
    "frame_decode_failed",
    "observer_timeout", "cloud_owner_account_gate_missing", "cloud_account_evidence_stale",
    "cloud_paid_account_missing", "cloud_canary_authorization_missing", "cloud_upload_scope_invalid",
    "cloud_credential_missing", "observer_transport_failed", "observer_identity_or_device_invalid",
    "observer_quota_failed", "observer_access_failed", "observer_http_failed",
    "observer_response_too_large", "cloud_account_identity_invalid", "cloud_key_scope_invalid",
    "cloud_billing_readback_incomplete", "cloud_key_readback_incomplete",
    "cloud_owner_decision_missing", "cloud_manifest_identity_invalid",
    "observer_identity_invalid",
    "cloud_held_out_evidence_missing", "cloud_held_out_evidence_invalid",
    "cloud_model_probe_invalid",
    "artifact_integrity_failed",
}


def verify_cpu_baseline() -> None:
    import platform

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ObserverError("cpu_baseline_platform_mismatch")
    try:
        hardware = subprocess.check_output(["system_profiler", "SPHardwareDataType", "-json"], text=True)
        details = json.loads(hardware)["SPHardwareDataType"][0]
        cpu = int(subprocess.check_output(["sysctl", "-n", "hw.ncpu"], text=True).strip())
        memory = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip())
    except Exception:
        raise ObserverError("cpu_baseline_unverifiable") from None
    if details.get("chip_type") != "Apple M3 Pro" or cpu != 12 or memory != 36 * 1024**3:
        raise ObserverError("cpu_baseline_platform_mismatch")


def _timeout(_signum, _frame) -> None:
    raise TimeoutError("bootstrap_watchdog_expired")


def _publish(store: PostgresStore, artifacts: ArtifactStore, run_id: uuid.UUID,
             name: str, payload: bytes, media_type: str) -> uuid.UUID:
    intent_id = store.create_publication_intent(run_id, media_type, f"{run_id}:{name}")
    _, sha256, size = artifacts.upload_temporary(intent_id, payload, media_type)
    final_key = f"sha256/{sha256}"
    store.publication_content_verified(intent_id, sha256, size, final_key)
    try:
        artifacts.publish_final(intent_id, payload, media_type, sha256, size)
    except ArtifactGateError as exc:
        if str(exc) == "artifact_integrity_failed":
            store.publication_failed_integrity(intent_id)
        raise
    store.publication_object_published(intent_id)
    return intent_id


def admit(manifest_path: Path, inventories: list[Path], snapshot_dir: Path,
          model_hashes_path: Path, watchdog_seconds: int) -> dict:
    raise ValueError("profile_retired")
    if watchdog_seconds <= 0:
        raise ValueError("bootstrap_watchdog_invalid")
    manifest, fixtures = validate_manifest(manifest_path, inventories)
    expected = json.loads(model_hashes_path.read_text())
    snapshot = draft_snapshot(HERE / "uv.lock", manifest, expected)
    config = Config.from_env()
    store = PostgresStore(config.database_url)
    artifacts = ArtifactStore(config)
    guard = store.engine.connect()
    try:
        if not guard.execute(text("SELECT pg_try_advisory_lock(804298270114)")).scalar_one():
            raise ValueError("admission_executor_busy")
        guard.commit()
        profile_id, run_ids = store.create_admission_runs(snapshot, manifest, fixtures, watchdog_seconds)
        try:
            verify_cpu_baseline()
            verify_snapshot(snapshot_dir, expected)
        except Exception as exc:
            code = str(exc) if str(exc) in SAFE_FAILURE_CODES else "admission_failed"
            for run_id in run_ids:
                store.fail_admission_run(run_id, code)
            return {"draft_profile_id": str(profile_id), "run_ids": [str(value) for value in run_ids],
                    "admitted_profile_id": None}
        observer = None
        failed = False
        for run_id, (fixture, image_bytes) in zip(run_ids, fixtures):
            try:
                with Image.open(io.BytesIO(image_bytes)) as image:
                    image.load()
            except Exception:
                failed = True
                store.fail_admission_run(run_id, "frame_decode_failed", failed_stage_ordinal=1)
                continue
            try:
                invocation_id = store.reserve_admission_invocation(run_id, image_bytes)
                call_started = time.perf_counter()
                previous = signal.signal(signal.SIGALRM, _timeout)
                signal.setitimer(signal.ITIMER_REAL, watchdog_seconds)
                try:
                    if observer is None:
                        observer = GroundingDinoCpu(snapshot_dir, expected)
                    result = observer.observe(image_bytes)
                    result["latency_ms"] = (time.perf_counter() - call_started) * 1000
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, previous)
                result["preprocessing_revision"] = PREPROCESSING_REVISION
                store.complete_invocation(run_id, invocation_id, result)
                native = canonical_bytes({"detections": result["native"],
                    "returned_model_identity": result["returned_model_identity"],
                    "actual_device": result["actual_device"], "latency_ms": result["latency_ms"],
                    "peak_memory_bytes": result["peak_memory_bytes"]})
                input_intent = _publish(store, artifacts, run_id, "input", image_bytes, "image/jpeg")
                native_intent = _publish(store, artifacts, run_id, "native", native, "application/json")
                store.finish_admission_run(run_id, invocation_id, native_intent, input_intent)
            except Exception as exc:
                failed = True
                code = str(exc) if str(exc) in SAFE_FAILURE_CODES else "admission_failed"
                store.fail_admission_run(run_id, code)
        successor = None if failed else store.authorize_successor(profile_id, run_ids)
        return {"draft_profile_id": str(profile_id), "run_ids": [str(value) for value in run_ids],
                "admitted_profile_id": str(successor) if successor else None}
    finally:
        guard.execute(text("SELECT pg_advisory_unlock(804298270114)"))
        guard.close()
        store.close()


def admit_cloud(manifest_path: Path, inventories: list[Path], evidence_path: Path,
                watchdog_seconds: int) -> dict:
    raise ValueError("profile_retired")
    if watchdog_seconds <= 0:
        raise ValueError("bootstrap_watchdog_invalid")
    manifest, fixtures = validate_manifest(manifest_path, inventories)
    try:
        owner_input = json.loads(evidence_path.read_text())
    except (OSError, ValueError):
        owner_input = {}
    if not isinstance(owner_input, dict):
        owner_input = {}
    canary_hashes = [fixture["image"]["sha256"] for fixture, _ in fixtures]
    config = Config.from_env()
    gate_error = None
    evidence = {}
    held_out_evidence = None
    allowed = canary_hashes
    try:
        if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != ADMISSION_MANIFEST_SHA256:
            raise CloudObserverError("cloud_manifest_identity_invalid")
        held_out_hashes, held_out_evidence = read_held_out_scope(HERE.parent / "evaluation",
            ADMISSION / "exclusions" / "held_out_evaluation.json", manifest, canary_hashes)
        allowed = canary_hashes + held_out_hashes
        if (set(owner_input) != {"folder_id", "service_account_id", "authorization_revision"}
                or owner_input["authorization_revision"] != OWNER_DECISION_REVISION):
            raise CloudObserverError("cloud_owner_decision_missing")
        evidence = read_owner_gate(owner_input["folder_id"], owner_input["service_account_id"],
            config.cloud_api_key_id, config.cloud_api_key, config.cloud_iam_token, canary_hashes, allowed)
    except Exception as exc:
        gate_error = str(exc) if str(exc) in SAFE_FAILURE_CODES else "cloud_owner_account_gate_missing"
    snapshot = cloud_snapshot(HERE / "uv.lock", manifest, owner_input.get("folder_id", ""),
                              owner_input.get("service_account_id", ""), allowed,
                              evidence if gate_error is None else {"gate_error": gate_error}, held_out_evidence)
    store = PostgresStore(config.database_url)
    artifacts = ArtifactStore(config)
    guard = store.engine.connect()
    try:
        if not guard.execute(text("SELECT pg_try_advisory_lock(804298270114)")).scalar_one():
            raise ValueError("admission_executor_busy")
        guard.commit()
        profile_id, run_ids = store.create_admission_runs(snapshot, manifest, fixtures, watchdog_seconds)
        try:
            if gate_error is not None:
                raise CloudObserverError(gate_error)
            validate_owner_evidence(evidence, canary_hashes, allowed)
            observer = CloudObserver(snapshot, config.cloud_api_key)
        except Exception as exc:
            code = str(exc) if str(exc).isidentifier() else "admission_failed"
            for run_id in run_ids:
                store.fail_admission_run(run_id, code)
            return {"draft_profile_id": str(profile_id), "run_ids": [str(value) for value in run_ids],
                    "admitted_profile_id": None, "error_code": code}
        failed = False
        failure_code = None
        for index, (run_id, (_, image_bytes)) in enumerate(zip(run_ids, fixtures)):
            try:
                fresh = read_owner_gate(owner_input["folder_id"], owner_input["service_account_id"],
                    config.cloud_api_key_id, config.cloud_api_key, config.cloud_iam_token, canary_hashes, allowed)
                if any(fresh[key] != evidence[key] for key in
                       ("account_id", "cloud_id", "folder_id", "service_account_id", "api_key_id")):
                    raise CloudObserverError("cloud_account_identity_invalid")
                invocation_id = store.reserve_admission_invocation(run_id, image_bytes)
                result = observer.observe(image_bytes, watchdog_seconds)
                store.complete_invocation(run_id, invocation_id, result)
                native = cloud_bytes({"response": result["native"],
                    "returned_model_identity": result["returned_model_identity"],
                    "credential_key_id": fresh["api_key_id"],
                    "request_data_controls": {"store": False, "x-data-logging-enabled": "false"}})
                input_intent = _publish(store, artifacts, run_id, "input", image_bytes, "image/jpeg")
                native_intent = _publish(store, artifacts, run_id, "native", native, "application/json")
                for payload, intent in ((image_bytes, input_intent), (native, native_intent)):
                    digest = hashlib.sha256(payload).hexdigest()
                    artifacts.read_verified(f"sha256/{digest}", digest, len(payload))
                store.finish_admission_run(run_id, invocation_id, native_intent, input_intent)
            except Exception as exc:
                failed = True
                code = str(exc) if str(exc) in SAFE_FAILURE_CODES else "admission_failed"
                failure_code = code
                store.fail_admission_run(run_id, code)
                for remaining in run_ids[index + 1:]:
                    store.fail_admission_run(remaining, "admission_canary_failed")
                break
        successor = None if failed else store.authorize_successor(profile_id, run_ids)
        return {"draft_profile_id": str(profile_id), "run_ids": [str(value) for value in run_ids],
                "admitted_profile_id": str(successor) if successor else None,
                **({"error_code": failure_code} if failure_code else {})}
    finally:
        guard.execute(text("SELECT pg_advisory_unlock(804298270114)"))
        guard.close()
        store.close()


def main() -> None:
    raise SystemExit("profile_retired: используйте evidence-profile для настройки мультимодальной модели")

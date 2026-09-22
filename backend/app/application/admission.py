"""Operator entrypoint for the pinned local observer admission."""

import argparse
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


def main() -> None:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command", required=True)
    prepare = subcommands.add_parser("prepare")
    prepare.add_argument("--snapshot-dir", type=Path, required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--exclusion-inventory", type=Path, action="append", required=True)
    run.add_argument("--snapshot-dir", type=Path, required=True)
    run.add_argument("--bootstrap-watchdog-seconds", type=int, default=600)
    args = parser.parse_args()
    if args.command == "prepare":
        files = prepare_snapshot(args.snapshot_dir)
        (ADMISSION / "model-files.json").write_text(json.dumps(files, indent=2) + "\n")
        print(json.dumps({"prepared": True, "files": len(files)}))
        return
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        print(json.dumps(admit(ADMISSION / "manifest.json", args.exclusion_inventory, args.snapshot_dir,
            ADMISSION / "model-files.json", args.bootstrap_watchdog_seconds)))
    except Exception as exc:
        code = str(exc) if str(exc) in SAFE_FAILURE_CODES else "admission_failed"
        parser.exit(1, code + "\n")

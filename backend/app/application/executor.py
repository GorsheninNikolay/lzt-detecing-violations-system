import asyncio
import io
import math
import multiprocessing
import os
import uuid
from queue import Empty
from pathlib import Path

from PIL import Image

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.config import Config
from app.domain.observations import CLASSES, closed_observations, normalized_states
from app.profiles.grounding_dino import PREPROCESSING_REVISION, GroundingDinoCpu, canonical_bytes


def _observe_worker(snapshot_dir: str, hashes: dict, image: bytes, output) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        output.put(("ok", GroundingDinoCpu(Path(snapshot_dir), hashes).observe(image)))
    except Exception:
        output.put(("error", None))


def _observe_bounded(snapshot_dir: str, hashes: dict, image: bytes, seconds: float) -> dict:
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(target=_observe_worker, args=(snapshot_dir, hashes, image, output))
    process.start()
    try:
        try:
            status, result = output.get(timeout=seconds)
        except Empty:
            if not process.is_alive():
                raise RuntimeError("observer_execution_failed") from None
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
            raise RuntimeError("observer_timeout")
        process.join(5)
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
            raise RuntimeError("observer_execution_failed")
        if process.exitcode != 0:
            raise RuntimeError("observer_execution_failed")
        if status != "ok":
            raise RuntimeError("observer_execution_failed")
        return result
    finally:
        if process.is_alive():
            process.terminate()
            process.join(5)
            if process.is_alive():
                process.kill()
                process.join()
        else:
            process.join(0)
        output.close()


def _unassessable(image: bytes) -> bool:
    with Image.open(io.BytesIO(image)) as source:
        rgb = source.convert("RGB")
        if min(rgb.size) < 64:
            return True
        return all(high - low < 5 for low, high in rgb.getextrema())


def _validate_result(result: dict) -> None:
    try:
        normalized_states(result["states"])
        native = result["native"]
        detections = native["detections"]
        dimensions = native["image_size"]
        if (not isinstance(detections, list) or len(detections) > 10000
                or not isinstance(dimensions, list) or len(dimensions) != 2
                or any(not isinstance(value, int) or value <= 0 for value in dimensions)
                or not math.isfinite(result["latency_ms"]) or result["latency_ms"] < 0
                or not isinstance(result["peak_memory_bytes"], int) or result["peak_memory_bytes"] < 0):
            raise ValueError
        for item in detections:
            if (not isinstance(item["label"], str) or not math.isfinite(item["score"])
                    or not 0 <= item["score"] <= 1 or len(item["box"]) != 4
                    or any(not math.isfinite(value) for value in item["box"])):
                raise ValueError
        expected = {"excavator": "an excavator", "dump_truck": "a dump truck"}
        for name, label in expected.items():
            detected = any(item["label"] == label for item in detections)
            if (result["states"][name] == "detected") != detected:
                raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("observation_normalization_failed") from None


class ClaimLoop:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.runtime_binding: tuple[uuid.UUID, int] | None = None
        self.store: PostgresStore | None = None
        self.artifacts: ArtifactStore | None = None
        self.snapshot_dir: str | None = None

    def bind_runtime(self, store: PostgresStore, profile_id: uuid.UUID) -> None:
        _, authorization_revision = store.require_authorized(profile_id)
        self.runtime_binding = profile_id, authorization_revision
        self.store = store

    def start(self, ready: asyncio.Event, artifacts: ArtifactStore | None = None, snapshot_dir: str | None = None) -> None:
        if self.task is not None:
            raise RuntimeError("claim_loop_already_started")
        self.artifacts = artifacts
        self.snapshot_dir = snapshot_dir
        self.task = asyncio.create_task(self._run(ready))

    async def _renew(self, run_id: uuid.UUID, owner: str, revision: int) -> None:
        while True:
            await asyncio.sleep(10)
            await asyncio.to_thread(self.store.renew_ordinary, run_id, owner, revision, 30)

    async def _execute(self, work: dict, revision: int) -> None:
        run_id, owner = work["id"], work["owner"]
        renewal = asyncio.create_task(self._renew(run_id, owner, revision))
        try:
            for frame in work["frames"]:
                image = await asyncio.to_thread(self.artifacts.read_verified, frame["key"], frame["sha256"], frame["size"])
                assessable = not await asyncio.to_thread(_unassessable, image)
                supported = bool(set(work["requested_classes"]) & set(CLASSES))
                invocation = await asyncio.to_thread(self.store.reserve_ordinary, run_id, owner, revision,
                    frame["sha256"], assessable and supported, frame["input_id"])
                if invocation is None:
                    states = {name: "insufficient_data" for name in CLASSES}
                    result, native_intent = None, None
                else:
                    timeout = float(work["profile_snapshot"]["runtime"]["per_image_timeout_seconds"])
                    result = await asyncio.to_thread(_observe_bounded, self.snapshot_dir,
                        work["profile_snapshot"]["model_files"], image, timeout)
                    _validate_result(result)
                    result["preprocessing_revision"] = PREPROCESSING_REVISION
                    native = canonical_bytes({"detections": result["native"],
                        "returned_model_identity": result["returned_model_identity"],
                        "actual_device": result["actual_device"], "latency_ms": result["latency_ms"],
                        "peak_memory_bytes": result["peak_memory_bytes"]})
                    native_intent = await asyncio.to_thread(self.store.create_publication_intent,
                        run_id, "application/json", f"{run_id}:native:{frame['input_id']}")
                    _, hash_, size = await asyncio.to_thread(self.artifacts.upload_temporary, native_intent, native, "application/json")
                    await asyncio.to_thread(self.store.publication_content_verified, native_intent, hash_, size, f"sha256/{hash_}")
                    await asyncio.to_thread(self.artifacts.publish_final, native_intent, native, "application/json", hash_, size)
                    await asyncio.to_thread(self.store.publication_object_published, native_intent)
                    await asyncio.to_thread(self.artifacts.read_verified, f"sha256/{hash_}", hash_, size)
                    states = result["states"]
                observations = closed_observations(states, work["requested_classes"], str(frame["artifact_id"]))
                await asyncio.to_thread(self.store.finish_ordinary, run_id, owner, revision,
                    invocation, result, native_intent, observations, frame["input_id"])
        except Exception as exc:
            code = str(exc)
            if code not in {"observer_timeout", "artifact_integrity_failed", "observer_identity_or_device_invalid",
                            "ordinary_completion_rejected", "ordinary_reservation_rejected", "ordinary_lease_rejected"}:
                code = "observer_execution_failed"
            await asyncio.to_thread(self.store.fail_ordinary, run_id, owner, code)
        finally:
            renewal.cancel()
            try:
                await renewal
            except asyncio.CancelledError:
                pass

    async def _run(self, ready: asyncio.Event) -> None:
        try:
            while ready.is_set():
                if self.store:
                    await asyncio.to_thread(self.store.fail_unauthorized_queued)
                    if await asyncio.to_thread(self.store.recover):
                        await asyncio.to_thread(self.store.reconcile, self.artifacts, runtime=True)
                if self.runtime_binding and self.artifacts and self.snapshot_dir:
                    profile_id, revision = self.runtime_binding
                    work = await asyncio.to_thread(self.store.claim_ordinary, profile_id, revision, 30)
                    if work:
                        await self._execute(work, revision)
                        if await asyncio.to_thread(self.store.recover):
                            await asyncio.to_thread(self.store.reconcile, self.artifacts, runtime=True)
                        continue
                await asyncio.sleep(1)
        except Exception:
            ready.clear()
            raise

    async def stop(self) -> None:
        if self.task is not None:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

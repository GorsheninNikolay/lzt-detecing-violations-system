import asyncio
import hashlib
import io
import math
import multiprocessing
import os
import uuid
import zipfile
import zlib
from queue import Empty
from pathlib import Path
from time import monotonic

from PIL import Image

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.config import Config
from app.domain.observations import CLASSES, closed_observations, normalized_states
from app.profiles.grounding_dino import PREPROCESSING_REVISION, GroundingDinoCpu, canonical_bytes
from app.profiles.grounding_dino_v2 import GroundingDinoCpuV2, EQUIPMENT_PROMPTS
from app.profiles.cloud_api import CloudObserver, read_owner_gate
from app.domain.comparison_campaign import CampaignGateError
from app.adapters.postgres import LOCK_ID
from sqlalchemy import text


def _observe_worker(snapshot_dir: str, hashes: dict, image: bytes, output, extended: bool = False) -> None:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        observer = (GroundingDinoCpuV2 if extended else GroundingDinoCpu)(Path(snapshot_dir), hashes)
        output.put(("ok", observer.observe(image)))
    except Exception:
        output.put(("error", None))


def _observe_bounded(snapshot_dir: str, hashes: dict, image: bytes, seconds: float,
                     extended: bool = False) -> dict:
    context = multiprocessing.get_context("spawn")
    output = context.Queue(maxsize=1)
    process = context.Process(target=_observe_worker, args=(snapshot_dir, hashes, image, output, extended))
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


def _decode_image(image: bytes) -> None:
    with Image.open(io.BytesIO(image)) as source:
        source.load()


def _validate_result(result: dict, prompts: dict[str, str] | None = None) -> None:
    try:
        prompts = prompts or {"excavator": "an excavator", "dump_truck": "a dump truck"}
        normalized_states(result["states"], tuple(prompts))
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
        for name, label in prompts.items():
            detected = any(item["label"] == label for item in detections)
            if (result["states"][name] == "detected") != detected:
                raise ValueError
    except (KeyError, TypeError, ValueError, OverflowError):
        raise ValueError("observation_normalization_failed") from None


class ClaimLoop:
    def __init__(self) -> None:
        self.task: asyncio.Task | None = None
        self.ready: asyncio.Event | None = None
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
        self.ready = ready
        self.artifacts = artifacts
        self.snapshot_dir = snapshot_dir
        self.task = asyncio.create_task(self._run(ready))

    async def _renew(self, run_id: uuid.UUID, owner: str, revision: int,
                     campaign: bool = False) -> None:
        while True:
            await asyncio.sleep(10)
            if campaign:
                await asyncio.to_thread(self.store.renew_comparison, run_id, owner, revision, 30)
            else:
                await asyncio.to_thread(self.store.renew_ordinary, run_id, owner, revision, 30)

    async def _execute(self, work: dict, revision: int) -> None:
        run_id, owner = work["id"], work["owner"]
        campaign = work.get("campaign", False)
        renewal = asyncio.create_task(self._renew(run_id, owner, revision, campaign))
        try:
            deadline = (monotonic() + float(work["profile_snapshot"]["runtime"]["batch_timeout_seconds"])
                        if len(work["frames"]) > 1 else None)

            def remaining_batch() -> float:
                remaining = deadline - monotonic() if deadline is not None else float("inf")
                if remaining <= 0:
                    raise RuntimeError("observer_timeout")
                return remaining

            async def run_step(func, *args):
                if renewal.done():
                    raise RuntimeError("campaign_lease_rejected" if campaign else "ordinary_lease_rejected")
                remaining_batch()
                result = await asyncio.to_thread(func, *args)
                if renewal.done():
                    raise RuntimeError("campaign_lease_rejected" if campaign else "ordinary_lease_rejected")
                remaining_batch()
                return result

            async def run_provider(func, *args):
                if not campaign:
                    return await run_step(func, *args)
                if renewal.done():
                    raise RuntimeError("campaign_lease_rejected")
                remaining_batch()
                task = asyncio.create_task(asyncio.to_thread(func, *args))
                async def settle():
                    settlement = asyncio.create_task(asyncio.to_thread(
                        self.store.settle_comparison_invocation, run_id, owner, invocation))
                    while not settlement.done():
                        try:
                            await asyncio.shield(settlement)
                        except asyncio.CancelledError:
                            continue
                    settlement.result()
                try:
                    result = await asyncio.shield(task)
                except asyncio.CancelledError:
                    while not task.done():
                        try:
                            await asyncio.shield(task)
                        except asyncio.CancelledError:
                            continue
                        except Exception:
                            break
                    await settle()
                    raise
                except Exception:
                    await settle()
                    raise
                await settle()
                if renewal.done():
                    raise RuntimeError("campaign_lease_rejected")
                remaining_batch()
                return result

            single_image = None
            snapshot = work["profile_snapshot"]
            cloud = snapshot.get("kind") == "cloud_api"
            for frame in work["frames"]:
                if cloud and frame["sha256"] not in snapshot.get("allowed_input_sha256", []):
                    raise RuntimeError("cloud_image_not_authorized")
                image = await run_step(self.artifacts.read_verified, frame["key"], frame["sha256"], frame["size"])
                if cloud and hashlib.sha256(image).hexdigest() not in snapshot["allowed_input_sha256"]:
                    raise RuntimeError("cloud_image_not_authorized")
                await run_step(_decode_image, image)
                if len(work["frames"]) == 1:
                    single_image = image
                del image
            supported_classes = (tuple(EQUIPMENT_PROMPTS) if snapshot.get("observation_contract") == "equipment-boxes-v2"
                                 else CLASSES)
            extended = supported_classes != CLASSES
            prompts = EQUIPMENT_PROMPTS if extended else None
            supported = bool(set(work["requested_classes"]) & set(supported_classes))
            for frame in work["frames"]:
                if supported:
                    image = (single_image if single_image is not None else
                             await run_step(self.artifacts.read_verified, frame["key"], frame["sha256"], frame["size"]))
                if cloud and supported:
                    evidence = snapshot["owner_evidence"]
                    config = Config.from_env()
                    fresh = await run_step(read_owner_gate, snapshot["folder_id"], snapshot["service_account_id"],
                        config.cloud_api_key_id, config.cloud_api_key, config.cloud_iam_token,
                        evidence["canary_image_sha256"], snapshot["allowed_input_sha256"])
                    if any(fresh[key] != evidence[key] for key in
                           ("account_id", "cloud_id", "folder_id", "service_account_id")):
                        raise RuntimeError("cloud_account_identity_invalid")
                invocation = await run_step(self.store.reserve_ordinary, run_id, owner, revision,
                    frame["sha256"], supported, frame["input_id"], campaign)
                if invocation is None:
                    states = {name: "insufficient_data" for name in supported_classes}
                    result, native_intent = None, None
                else:
                    timeout = min(float(work["profile_snapshot"]["runtime"]["per_image_timeout_seconds"]),
                                  remaining_batch())
                    if cloud:
                        if not config.cloud_api_key:
                            raise RuntimeError("cloud_credential_missing")
                        result = await run_provider(
                            lambda: CloudObserver(snapshot, config.cloud_api_key).observe(image, timeout))
                        normalized_states(result["states"], supported_classes)
                        result["native"]["credential_key_id"] = fresh["api_key_id"]
                        result["native"]["owner_gate"] = fresh
                    else:
                        observer_args = (self.snapshot_dir, snapshot["model_files"], image, timeout)
                        result = await run_provider(_observe_bounded, *observer_args, True) if extended else await run_provider(
                            _observe_bounded, *observer_args)
                        _validate_result(result, prompts)
                        if not extended:
                            with Image.open(io.BytesIO(image)) as source:
                                orientation = source.getexif().get(274, 1)
                                result["source_orientation"] = orientation if orientation in range(1, 9) else 1
                        result["preprocessing_revision"] = PREPROCESSING_REVISION
                    native = canonical_bytes({"response" if cloud else "detections": result["native"],
                        "returned_model_identity": result["returned_model_identity"],
                        "actual_device": result["actual_device"], "latency_ms": result["latency_ms"],
                        "peak_memory_bytes": result["peak_memory_bytes"]})
                    native_intent = await run_step(self.store.create_publication_intent,
                        run_id, "application/json", f"{run_id}:native:{frame['input_id']}")
                    _, hash_, size = await run_step(self.artifacts.upload_temporary, native_intent, native, "application/json")
                    await run_step(self.store.publication_content_verified, native_intent, hash_, size, f"sha256/{hash_}")
                    await run_step(self.artifacts.publish_final, native_intent, native, "application/json", hash_, size)
                    await run_step(self.store.publication_object_published, native_intent)
                    await run_step(self.artifacts.read_verified, f"sha256/{hash_}", hash_, size)
                    states = result["states"]
                remaining_batch()
                observations = closed_observations(states, work["requested_classes"], str(frame["artifact_id"]), supported_classes)
                if renewal.done():
                    raise RuntimeError("campaign_lease_rejected" if campaign else "ordinary_lease_rejected")
                await asyncio.to_thread(self.store.finish_ordinary, run_id, owner, revision,
                    invocation, result, native_intent, observations, frame["input_id"], deadline, campaign)
        except Exception as exc:
            code = str(exc)
            if code not in {"observer_timeout", "artifact_integrity_failed", "observer_identity_or_device_invalid",
                            "cloud_image_not_authorized", "cloud_credential_missing", "observation_normalization_failed",
                            "ordinary_completion_rejected", "ordinary_reservation_rejected", "ordinary_lease_rejected",
                            "observer_quota_failed", "observer_access_failed", "observer_http_failed",
                            "observer_transport_failed", "observer_response_too_large",
                            "cloud_account_identity_invalid", "cloud_paid_account_missing",
                            "cloud_account_evidence_stale", "cloud_key_scope_invalid",
                            "profile_owner_evidence_expired", "observer_identity_invalid",
                            "profile_unauthorized", "authorization_revision_changed"}:
                code = "observer_execution_failed"
            if campaign:
                if renewal.done():
                    raise RuntimeError("campaign_ownership_uncertain") from exc
                for _ in range(3600):
                    try:
                        await asyncio.to_thread(self.store.fail_comparison_cell, run_id, code, owner)
                        break
                    except Exception as failure:
                        if str(failure) != "campaign_provider_may_be_active":
                            raise
                        await asyncio.sleep(1)
                else:
                    raise RuntimeError("campaign_provider_may_be_active") from exc
            else:
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
                if self.runtime_binding and self.artifacts:
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
            self.ready.clear()
            try:
                await self.task
            except asyncio.CancelledError:
                pass


def _verified_campaign_archive(source, manifest: dict) -> dict[int, bytes]:
    measured = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        measured.update(chunk)
    if measured.hexdigest() != manifest.get("source_archive_sha256"):
        raise CampaignGateError("archive_hash_mismatch")
    source.seek(0)
    images = {}
    try:
        with zipfile.ZipFile(source) as archive:
            for frame in manifest["frames"]:
                for kind in ("image", "label"):
                    item = frame[kind]
                    payload = archive.read(item["archive_member"])
                    if len(payload) != item["size"] or hashlib.sha256(payload).hexdigest() != item["sha256"]:
                        raise CampaignGateError("archive_content_mismatch")
                    if kind == "image":
                        images[frame["ordinal"]] = payload
    except CampaignGateError:
        raise
    except (KeyError, OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error):
        raise CampaignGateError("archive_content_unavailable") from None
    return images


async def execute_comparison_campaign(store: PostgresStore, artifacts: ArtifactStore,
                                      campaign_id: uuid.UUID, archive_path: Path,
                                      snapshot_dir: str | None = None) -> dict:
    lock = store.comparison_execution_lock()
    try:
        lock_pid = lock.execute(text("SELECT pg_backend_pid()")).scalar_one()
        lock.commit()
        store.require_comparison_execution_exclusive(campaign_id)
        store.recover_comparison_campaign(campaign_id)
        readback = store.read_comparison_campaign(campaign_id)
        if readback["accounting"]["missing"] == 0:
            return readback
        source = store.comparison_source(campaign_id)
        try:
            archive = archive_path.open("rb")
        except OSError:
            raise CampaignGateError("archive_content_unavailable") from None
        with archive:
            images = _verified_campaign_archive(archive, source)
            runner = ClaimLoop()
            runner.store, runner.artifacts, runner.snapshot_dir = store, artifacts, snapshot_dir
            while cell := store.next_comparison_cell(campaign_id):
                if lock.execute(text("SELECT pg_backend_pid()")).scalar_one() != lock_pid:
                    raise CampaignGateError("campaign_ownership_uncertain")
                lock.commit()
                if cell["state"] == "running":
                    raise CampaignGateError("campaign_ownership_uncertain")
                fixture = readback["manifest"]["fixtures"][cell["fixture_ordinal"]]
                try:
                    store.require_comparison_authorized(cell["run_id"])
                    for frame in fixture["frames"]:
                        original = source["frames"][frame["ordinal"]]
                        if (original["id"] != frame["id"] or
                                original["source_rights"]["status"] != "owner_approved_with_caveat" or
                                (cell["candidate_ordinal"] == 1 and original["cloud_upload_permission"] is not True)):
                            raise CampaignGateError("fixture_rights_not_cleared")
                        store.require_comparison_authorized(cell["run_id"])
                        store.publish_comparison_input(cell["run_id"], frame,
                                                       images[frame["ordinal"]], artifacts)
                    work = store.claim_comparison_cell(cell["run_id"], len(fixture["frames"]))
                except Exception as exc:
                    code = str(exc)
                    if not code.isidentifier():
                        code = "campaign_preparation_failed"
                    store.fail_comparison_cell(cell["run_id"], code)
                    continue
                await runner._execute(work, work["authorization_revision"])
            return store.read_comparison_campaign(campaign_id)
    finally:
        try:
            lock.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID + 3})
            lock.commit()
        except Exception:
            pass
        lock.close()

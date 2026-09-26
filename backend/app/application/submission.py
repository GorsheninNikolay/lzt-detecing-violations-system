"""Single-image request validation and verified publication."""

import base64
import binascii
import hashlib
import io
import json
import time
import uuid
from datetime import datetime

from PIL import Image, UnidentifiedImageError

from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore


class SubmissionError(ValueError):
    pass


def wait_for_submission(store: PostgresStore, key: str, request_hash: str, media_type: str) -> tuple[str, uuid.UUID | None, str | None]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        time.sleep(0.1)
        state, run_id, _, error = store.begin_submission(key, request_hash, media_type)
        if state != "publishing":
            return state, run_id, error
    raise SubmissionError("submission_in_progress")


def validate_request(body: dict) -> tuple[bytes, dict, list[str], str]:
    images, context, requested, request_hash = validate_images(body, False)
    return images[0], context, requested, request_hash


def image_media_type(image: bytes) -> str:
    return "image/png" if image.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"


def validate_images(body: dict, series: bool) -> tuple[list[bytes], dict, list[str], str]:
    if not isinstance(body, dict) or body.get("intent") not in ("observation_only", "rule_evaluation"):
        raise SubmissionError("invalid_observation_intent")
    if "stage_id" in body and (body["stage_id"] != "excavation"
                               or ("stage" in body and body["stage"] != body["stage_id"])):
        raise SubmissionError("invalid_stage_id")
    stage = body.get("stage", body.get("stage_id"))
    if body["intent"] == "rule_evaluation" and stage != "excavation":
        raise SubmissionError("rule_not_applicable")
    if "stage" in body and body["stage"] not in ("excavation", "other"):
        raise SubmissionError("invalid_stage")
    context = {key: body.get(key) for key in ("scenario", "observation_area", "period")}
    if not all(isinstance(value, str) and 0 < len(value.strip()) <= 256 for value in context.values()):
        raise SubmissionError("invalid_observation_context")
    if "stage_id" in body:
        context["stage_id"] = body["stage_id"]
    try:
        period = datetime.fromisoformat(context["period"])
        if period.tzinfo is None:
            raise ValueError
    except ValueError:
        raise SubmissionError("invalid_observation_context") from None
    requested = body.get("requested_classes", ["excavator", "dump_truck"])
    if (not isinstance(requested, list) or not requested or len(requested) > 32
            or any(not isinstance(name, str) or not name.isidentifier() or len(name) > 64 for name in requested)
            or len(set(requested)) != len(requested)):
        raise SubmissionError("invalid_requested_classes")
    if body["intent"] == "rule_evaluation" and not {"excavator", "dump_truck"}.issubset(requested):
        raise SubmissionError("invalid_requested_classes")
    raw_images = body.get("images_base64") if series else [body.get("image_base64")]
    if not isinstance(raw_images, list) or (series and not 2 <= len(raw_images) <= 8):
        raise SubmissionError("invalid_image_file")
    plan_keys = ("project_id", "zone_id", "capture_times")
    if any(key in body for key in (*plan_keys, "plan_revision_id")):
        try:
            if not all(key in body for key in plan_keys):
                raise ValueError
            for key in plan_keys[:2]:
                context[key] = str(uuid.UUID(body[key]))
            if "plan_revision_id" in body:
                context["plan_revision_id"] = str(uuid.UUID(body["plan_revision_id"]))
            times = body["capture_times"]
            if not isinstance(times, list) or len(times) != len(raw_images):
                raise ValueError
            for value in times:
                if not isinstance(value, str) or datetime.fromisoformat(value).utcoffset() is None:
                    raise ValueError
            context["capture_times"] = times
        except (TypeError, ValueError):
            raise SubmissionError("invalid_plan_binding") from None
    images = []
    for raw in raw_images:
        if not isinstance(raw, str) or len(raw) > 25_000_000:
            raise SubmissionError("invalid_image_file")
        try:
            image = base64.b64decode(raw, validate=True)
            if len(image) > 16_000_000 or not image or not (
                    image.startswith(b"\xff\xd8\xff") or image.startswith(b"\x89PNG\r\n\x1a\n")):
                raise SubmissionError("invalid_image_file")
            with Image.open(io.BytesIO(image)) as decoded:
                if decoded.format not in ("JPEG", "PNG") or decoded.width * decoded.height > 40_000_000:
                    raise SubmissionError("invalid_image_file")
                decoded.load()
        except (binascii.Error, ValueError, UnidentifiedImageError, OSError):
            raise SubmissionError("invalid_image_file") from None
        images.append(image)
    if body["intent"] == "rule_evaluation" and any(image_media_type(image) != "image/jpeg" for image in images):
        raise SubmissionError("rule_not_applicable")
    image_hashes = [hashlib.sha256(image).hexdigest() for image in images]
    identity = {"context": context, "requested_classes": sorted(requested),
                "image_sha256": image_hashes if series else image_hashes[0]}
    if body["intent"] != "observation_only" or "stage" in body:
        identity.update({"intent": body["intent"], "stage": stage})
    canonical = json.dumps(identity,
                           sort_keys=True, separators=(",", ":"))
    return images, context, requested, hashlib.sha256(canonical.encode()).hexdigest()


def submit(store: PostgresStore, artifacts: ArtifactStore, key: str, body: dict,
           profile_id: uuid.UUID, revision: int, snapshot: dict, browser_id: str | None = None) -> tuple[str, uuid.UUID | None]:
    if not isinstance(key, str) or not 0 < len(key) <= 128 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise SubmissionError("invalid_idempotency_key")
    image, context, requested, request_hash = validate_request(body)
    if body["intent"] == "rule_evaluation" and snapshot.get("observation_contract") == "equipment-boxes-v2":
        raise SubmissionError("rule_not_applicable")
    if "project_id" in context:
        try:
            store.validate_plan_binding(context)
        except AdmissionStoreError:
            raise SubmissionError("invalid_plan_binding") from None
    media_type = image_media_type(image)
    if snapshot.get("kind") == "cloud_api" and media_type != "image/jpeg":
        raise SubmissionError("invalid_image_file")
    if snapshot.get("kind") == "cloud_api" and hashlib.sha256(image).hexdigest() not in snapshot["allowed_input_sha256"]:
        raise SubmissionError("cloud_image_not_authorized")
    try:
        state, existing_run, intent_id, error = store.begin_submission(key, request_hash, media_type)
    except AdmissionStoreError as exc:
        if str(exc) == "idempotency_key_conflict":
            raise SubmissionError("idempotency_key_conflict") from None
        raise
    if state == "accepted":
        return "queued", existing_run
    if state == "failed":
        raise SubmissionError(error)
    if state == "publishing":
        state, existing_run, error = wait_for_submission(store, key, request_hash, media_type)
        if state == "accepted":
            return "queued", existing_run
        raise SubmissionError(error)
    try:
        _, image_hash, size = artifacts.upload_temporary(intent_id, image, media_type)
        store.publication_content_verified(intent_id, image_hash, size, f"sha256/{image_hash}")
        artifacts.publish_final(intent_id, image, media_type, image_hash, size)
        store.publication_object_published(intent_id)
        artifacts.read_verified(f"sha256/{image_hash}", image_hash, size)
        run_id = store.commit_submission(key, profile_id, revision, snapshot, context, requested, image_hash, size,
            **({"browser_id": browser_id} if browser_id else {}),
            **({"intent": body["intent"], "stage": body.get("stage", body.get("stage_id"))}
               if "stage" in body or "stage_id" in body else {}))
        return "queued", run_id
    except Exception as exc:
        code = "profile_unauthorized" if str(exc) == "profile_unauthorized" else "submission_publication_failed"
        store.fail_submission(key, code)
        raise SubmissionError(code) from None


def submit_series(store: PostgresStore, artifacts: ArtifactStore, key: str, body: dict,
                  profile_id: uuid.UUID, revision: int, snapshot: dict, browser_id: str | None = None) -> tuple[str, uuid.UUID | None]:
    if not isinstance(key, str) or not 0 < len(key) <= 128 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise SubmissionError("invalid_idempotency_key")
    images, context, requested, request_hash = validate_images(body, True)
    if body["intent"] == "rule_evaluation" and snapshot.get("observation_contract") == "equipment-boxes-v2":
        raise SubmissionError("rule_not_applicable")
    if "project_id" in context:
        try:
            store.validate_plan_binding(context)
        except AdmissionStoreError:
            raise SubmissionError("invalid_plan_binding") from None
    media_types = [image_media_type(image) for image in images]
    if snapshot.get("kind") == "cloud_api" and any(media != "image/jpeg" for media in media_types):
        raise SubmissionError("invalid_image_file")
    if snapshot.get("kind") == "cloud_api" and any(
            hashlib.sha256(image).hexdigest() not in snapshot["allowed_input_sha256"] for image in images):
        raise SubmissionError("cloud_image_not_authorized")
    try:
        state, existing_run, first_intent, error = store.begin_submission(key, request_hash, media_types[0])
    except AdmissionStoreError as exc:
        if str(exc) == "idempotency_key_conflict":
            raise SubmissionError("idempotency_key_conflict") from None
        raise
    if state == "publishing":
        state, existing_run, error = wait_for_submission(store, key, request_hash, media_types[0])
    if state == "accepted":
        return "queued", existing_run
    if state == "failed":
        raise SubmissionError(error)
    try:
        manifest = []
        for ordinal, (image, media_type) in enumerate(zip(images, media_types)):
            intent_id = first_intent if ordinal == 0 else store.create_submission_intent(key, media_type)
            _, image_hash, size = artifacts.upload_temporary(intent_id, image, media_type)
            store.publication_content_verified(intent_id, image_hash, size, f"sha256/{image_hash}")
            artifacts.publish_final(intent_id, image, media_type, image_hash, size)
            store.publication_object_published(intent_id)
            artifacts.read_verified(f"sha256/{image_hash}", image_hash, size)
            manifest.append((intent_id, image_hash, size))
        return "queued", store.commit_series_submission(
            key, profile_id, revision, snapshot, context, requested, manifest,
            **({"browser_id": browser_id} if browser_id else {}),
            **({"intent": body["intent"], "stage": body.get("stage", body.get("stage_id"))}
               if "stage" in body or "stage_id" in body else {}))
    except Exception as exc:
        code = "profile_unauthorized" if str(exc) == "profile_unauthorized" else "submission_publication_failed"
        store.fail_submission(key, code)
        raise SubmissionError(code) from None

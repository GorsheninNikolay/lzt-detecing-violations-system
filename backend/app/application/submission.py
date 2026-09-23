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


def validate_request(body: dict) -> tuple[bytes, dict, list[str], str]:
    if not isinstance(body, dict) or body.get("intent") != "observation_only":
        raise SubmissionError("invalid_observation_intent")
    context = {key: body.get(key) for key in ("scenario", "observation_area", "period")}
    if not all(isinstance(value, str) and 0 < len(value.strip()) <= 256 for value in context.values()):
        raise SubmissionError("invalid_observation_context")
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
    raw = body.get("image_base64")
    if not isinstance(raw, str) or len(raw) > 25_000_000:
        raise SubmissionError("invalid_image_file")
    try:
        image = base64.b64decode(raw, validate=True)
        if len(image) > 16_000_000 or not image or image[:3] != b"\xff\xd8\xff":
            raise SubmissionError("invalid_image_file")
        with Image.open(io.BytesIO(image)) as decoded:
            if decoded.format != "JPEG" or decoded.width * decoded.height > 40_000_000:
                raise SubmissionError("invalid_image_file")
            decoded.load()
    except (binascii.Error, ValueError, UnidentifiedImageError, OSError):
        raise SubmissionError("invalid_image_file") from None
    canonical = json.dumps({"context": context, "requested_classes": sorted(requested),
                            "image_sha256": hashlib.sha256(image).hexdigest()}, sort_keys=True, separators=(",", ":"))
    return image, context, requested, hashlib.sha256(canonical.encode()).hexdigest()


def submit(store: PostgresStore, artifacts: ArtifactStore, key: str, body: dict,
           profile_id: uuid.UUID, revision: int, snapshot: dict) -> tuple[str, uuid.UUID | None]:
    if not isinstance(key, str) or not 0 < len(key) <= 128 or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise SubmissionError("invalid_idempotency_key")
    image, context, requested, request_hash = validate_request(body)
    try:
        state, existing_run, intent_id, error = store.begin_submission(key, request_hash, "image/jpeg")
    except AdmissionStoreError as exc:
        if str(exc) == "idempotency_key_conflict":
            raise SubmissionError("idempotency_key_conflict") from None
        raise
    if state == "accepted":
        return "queued", existing_run
    if state == "failed":
        raise SubmissionError(error)
    if state == "publishing":
        while True:
            time.sleep(0.1)
            state, existing_run, _, error = store.begin_submission(key, request_hash, "image/jpeg")
            if state == "accepted":
                return "queued", existing_run
            if state == "failed":
                raise SubmissionError(error)
    try:
        _, image_hash, size = artifacts.upload_temporary(intent_id, image, "image/jpeg")
        store.publication_content_verified(intent_id, image_hash, size, f"sha256/{image_hash}")
        artifacts.publish_final(intent_id, image, "image/jpeg", image_hash, size)
        store.publication_object_published(intent_id)
        artifacts.read_verified(f"sha256/{image_hash}", image_hash, size)
        run_id = store.commit_submission(key, profile_id, revision, snapshot, context, requested, image_hash, size)
        return "queued", run_id
    except Exception as exc:
        code = "profile_unauthorized" if str(exc) == "profile_unauthorized" else "submission_publication_failed"
        store.fail_submission(key, code)
        raise SubmissionError(code) from None

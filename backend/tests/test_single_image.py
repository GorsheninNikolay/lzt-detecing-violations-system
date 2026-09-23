import asyncio
import base64
import io
import json
import multiprocessing
import os
import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import text

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import PostgresStore
from app.application import executor
from app.application import admission, submission
from app.application.submission import SubmissionError, validate_request
from app.config import Config
from app.main import MAX_HTTP_BODY_BYTES, create_app
from test_admission import isolated_admission_database
from test_startup import database, integration


def jpeg(color) -> bytes:
    image = Image.new("RGB", (96, 96), color)
    if color != (0, 0, 0):
        ImageDraw.Draw(image).rectangle((16, 16, 72, 72), fill=(240, 200, 20))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


def request_body(image: bytes, classes=None) -> dict:
    body = {"intent": "observation_only", "scenario": "equipment_check", "observation_area": "north_gate",
            "period": "2026-09-23T12:00:00+03:00", "image_base64": base64.b64encode(image).decode()}
    if classes is not None:
        body["requested_classes"] = classes
    return body


def test_validation_before_publication():
    for body in (request_body(b"bad"), request_body(jpeg((0, 0, 0))) | {"period": "yesterday"},
                 request_body(jpeg((0, 0, 0))) | {"intent": "evaluate_rule"}):
        with pytest.raises(SubmissionError):
            validate_request(body)
    image = jpeg((0, 0, 0))
    assert validate_request(request_body(image))[2] == ["excavator", "dump_truck"]


def test_rejects_large_dimensions_before_pixel_load(monkeypatch):
    class Oversized:
        format, width, height = "JPEG", 10_000, 10_000

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def load(self):
            raise AssertionError("pixel decode must not start")

    monkeypatch.setattr(submission.Image, "open", lambda *_: Oversized())
    with pytest.raises(SubmissionError, match="invalid_image_file"):
        validate_request(request_body(b"\xff\xd8\xff"))


def test_duplicate_waits_for_original_without_mutating_it(monkeypatch):
    run = uuid.uuid4()

    class Store:
        calls = 0

        def begin_submission(self, *_):
            self.calls += 1
            return ("publishing", None, None, None) if self.calls == 1 else ("accepted", run, None, None)

        def fail_submission(self, *_):
            raise AssertionError("duplicate cannot fail the owner")

    monkeypatch.setattr(submission.time, "sleep", lambda *_: None)
    assert submission.submit(Store(), None, "same-key", request_body(jpeg((0, 0, 0))), uuid.uuid4(), 1, {}) == ("queued", run)


def test_http_submission_and_guarded_execution(isolated_admission_database, integration, monkeypatch):
    config, _, _ = integration
    config = Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                    config.s3_access_key, config.s3_secret_key)
    store, artifacts = PostgresStore(isolated_admission_database), ArtifactStore(config)
    profile, parent = uuid.uuid4(), uuid.uuid4()
    snapshot = {"model_files": {"model.safetensors": "a" * 64},
                "runtime": {"per_image_timeout_seconds": 2}}
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, '{}'::jsonb)"),
                           {"id": parent, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, '{}'::jsonb, :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""), {"id": profile})
    monkeypatch.setattr(store, "require_authorized", lambda *_: (snapshot, 1))
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, artifacts
    loop = executor.ClaimLoop()
    loop.store, loop.artifacts, loop.snapshot_dir = store, artifacts, "unused"
    loop.runtime_binding = profile, 1
    app.state.claim_loop = loop
    image = jpeg((12, 120, 220))
    body = request_body(image, ["excavator", "dump_truck", "tower_crane"])

    def observed(*_):
        return {"states": {"excavator": "detected", "dump_truck": "not_detected_in_frame"},
                "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
                "latency_ms": 1.0, "peak_memory_bytes": 1024,
                "native": {"detections": [{"label": "an excavator", "score": 0.8, "box": [1, 2, 3, 4]}],
                           "image_size": [96, 96]}}

    monkeypatch.setattr(executor, "_observe_bounded", observed)

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            async def oversized():
                yield b"{"
                yield b"x" * MAX_HTTP_BODY_BYTES

            too_large = await client.post("/runs/single-image", content=oversized())
            assert too_large.status_code == 400 and too_large.json() == {"code": "invalid_image_file"}
            invalid = await client.post("/runs/single-image", headers={"Idempotency-Key": "invalid"}, json=request_body(b"bad"))
            assert invalid.status_code == 400 and invalid.json() == {"code": "invalid_image_file"}
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM submission_requests")).scalar_one() == 0
            key = uuid.uuid4().hex
            first, duplicate = await asyncio.gather(*(
                client.post("/runs/single-image", headers={"Idempotency-Key": key}, json=body) for _ in range(2)))
            assert first.status_code == duplicate.status_code == 202
            run = uuid.UUID(first.json()["run_id"])
            assert duplicate.json()["run_id"] == str(run)
            conflict = await client.post("/runs/single-image", headers={"Idempotency-Key": key},
                                         json=body | {"observation_area": "south_gate"})
            assert conflict.status_code == 409 and conflict.json() == {"code": "idempotency_key_conflict"}
            queued = (await client.get(f"/runs/{run}")).json()
            assert queued["state"] == "queued" and queued["outcome"] is None
            work = store.claim_ordinary(profile, 1, 30)
            assert work["id"] == run
            await loop._execute(work, 1)
            done = (await client.get(f"/runs/{run}")).json()
            assert done["state"] == "succeeded" and done["outcome"] == "observations_only"
            assert len(done["stages"]) == 6 and done["native_evidence"]["sha256"]
            assert {item["class_name"]: item["state"] for item in done["observations"]} == {
                "excavator": "detected", "dump_truck": "not_detected_in_frame", "tower_crane": "not_analyzed"}
            assert all(item["source_artifact_id"] for item in done["observations"])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"), {"run": run}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"), {"run": run}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"), {"run": run}).scalar_one() == 1
            black = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                      json=request_body(jpeg((0, 0, 0))))
            black_run = uuid.UUID(black.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            insufficient = (await client.get(f"/runs/{black_run}")).json()
            assert insufficient["state"] == "succeeded" and all(
                item["state"] == "insufficient_data" and item["reason"] for item in insufficient["observations"])
            assert insufficient["outcome"] == "observations_only"
            unsupported = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                            json=request_body(jpeg((33, 111, 222)), ["tower_crane"]))
            unsupported_run = uuid.UUID(unsupported.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            unsupported_state = (await client.get(f"/runs/{unsupported_run}")).json()
            assert unsupported_state["state"] == "succeeded" and unsupported_state["outcome"] == "observations_only"
            assert unsupported_state["observations"][0]["state"] == "not_analyzed"
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"),
                                          {"run": unsupported_run}).scalar_one() == 0
            failing = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            failed_run = uuid.UUID(failing.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", lambda *_: (_ for _ in ()).throw(RuntimeError("provider_secret")))
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            failure = (await client.get(f"/runs/{failed_run}")).json()
            assert failure["state"] == "failed" and failure["outcome"] is None
            assert failure["error_code"] == "observer_execution_failed" and "provider_secret" not in str(failure)
            malformed = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            malformed_run = uuid.UUID(malformed.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", lambda *_: observed() | {"states": {"excavator": "unknown"}})
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            malformed_state = (await client.get(f"/runs/{malformed_run}")).json()
            assert malformed_state["state"] == "failed" and malformed_state["outcome"] is None
            contradictory = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            contradictory_run = uuid.UUID(contradictory.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", lambda *_: observed() | {
                "states": {"excavator": "not_detected_in_frame", "dump_truck": "not_detected_in_frame"}})
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            contradictory_state = (await client.get(f"/runs/{contradictory_run}")).json()
            assert contradictory_state["state"] == "failed" and contradictory_state["outcome"] is None
            timeout = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            timeout_run = uuid.UUID(timeout.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", lambda *_: (_ for _ in ()).throw(RuntimeError("observer_timeout")))
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            timeout_state = (await client.get(f"/runs/{timeout_run}")).json()
            assert timeout_state["state"] == "failed" and timeout_state["error_code"] == "observer_timeout"
            assert timeout_state["outcome"] is None
            missing = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                        json=request_body(jpeg((54, 111, 223))))
            missing_run = uuid.UUID(missing.json()["run_id"])
            work = store.claim_ordinary(profile, 1, 30)
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=work["key"])
            await loop._execute(work, 1)
            missing_state = (await client.get(f"/runs/{missing_run}")).json()
            assert missing_state["state"] == "failed" and missing_state["error_code"] == "artifact_integrity_failed"
            assert missing_state["outcome"] is None
            stale = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            stale_run = uuid.UUID(stale.json()["run_id"])
            work = store.claim_ordinary(profile, 1, 30)
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE analysis_runs SET lease_expires_at = clock_timestamp() - interval '1 second' WHERE id = :run"),
                                   {"run": stale_run})
            await loop._execute(work, 1)
            store.recover()
            stale_state = (await client.get(f"/runs/{stale_run}")).json()
            assert stale_state["state"] == "failed" and stale_state["outcome"] is None
            upload = artifacts.upload_temporary
            monkeypatch.setattr(artifacts, "upload_temporary", lambda *_: (_ for _ in ()).throw(RuntimeError("upload_failed")))
            bad_key = uuid.uuid4().hex
            bad_first = await client.post("/runs/single-image", headers={"Idempotency-Key": bad_key}, json=body)
            bad_repeat = await client.post("/runs/single-image", headers={"Idempotency-Key": bad_key}, json=body)
            assert bad_first.json() == bad_repeat.json() == {"code": "submission_publication_failed"}
            monkeypatch.setattr(artifacts, "upload_temporary", upload)
            interrupted, interrupted_key = uuid.uuid4(), uuid.uuid4().hex
            with store.engine.begin() as connection:
                connection.execute(text("""INSERT INTO publication_intents (id, idempotency_key, media_type, state)
                    VALUES (:id, :key, 'image/jpeg', 'pending_upload')"""),
                    {"id": interrupted, "key": f"submission:{interrupted_key}"})
                connection.execute(text("""INSERT INTO submission_requests (idempotency_key, request_hash, state, intent_id)
                    VALUES (:key, 'interrupted', 'publishing', :intent)"""),
                    {"key": interrupted_key, "intent": interrupted})
            store.reconcile()
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                          {"id": interrupted}).scalar_one() == "quarantined"
                assert connection.execute(text("SELECT error_code FROM submission_requests WHERE idempotency_key = :key"),
                                          {"key": interrupted_key}).scalar_one() == "submission_interrupted"
            revoked = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            revoked_run = uuid.UUID(revoked.json()["run_id"])
            work = store.claim_ordinary(profile, 1, 30)
            store.revoke_authorization(profile, 1, "test_revocation")
            await loop._execute(work, 1)
            overlap = (await client.get(f"/runs/{revoked_run}")).json()
            assert overlap["state"] == "failed" and overlap["outcome"] is None
            other_parent, other_profile, orphaned_run = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            with store.engine.begin() as connection:
                connection.execute(text("""INSERT INTO observer_profiles (id, status, profile_hash, snapshot)
                    VALUES (:id, 'draft', :hash, '{}'::jsonb)"""), {"id": other_parent, "hash": uuid.uuid4().hex})
                connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
                    VALUES (:id, :parent, 'admitted', :hash, '{}'::jsonb, :audit)"""),
                    {"id": other_profile, "parent": other_parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex})
                connection.execute(text("""INSERT INTO profile_authorizations
                    (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
                    SELECT :id, 2, 'revoked', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""),
                    {"id": other_profile})
                connection.execute(text("""INSERT INTO analysis_runs (id, state, purpose, profile_id, authorization_revision)
                    VALUES (:run, 'queued', 'ordinary', :profile, 1)"""), {"run": orphaned_run, "profile": other_profile})
                connection.execute(text("INSERT INTO analysis_stages (run_id, ordinal, state) VALUES (:run, 0, 'pending'), (:run, 1, 'pending')"),
                                   {"run": orphaned_run})
            store.fail_unauthorized_queued()
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT state FROM analysis_runs WHERE id = :run"),
                                          {"run": orphaned_run}).scalar_one() == "failed"

    try:
        asyncio.run(scenario())
    finally:
        store.close()


def test_admitted_profile_http_background_cpu(isolated_admission_database, integration, monkeypatch):
    snapshot_dir = os.getenv("TEST_MODEL_SNAPSHOT_DIR")
    if not snapshot_dir:
        pytest.fail("Set TEST_MODEL_SNAPSHOT_DIR to the pinned offline Grounding DINO snapshot")
    admission_dir = Path(__file__).resolve().parents[1] / "admission"
    inventories = sorted((admission_dir / "exclusions").glob("*.json"))
    admitted = admission.admit(admission_dir / "manifest.json", inventories, Path(snapshot_dir),
                               admission_dir / "model-files.json", 600)
    assert admitted["admitted_profile_id"]
    monkeypatch.setenv("OBSERVER_PROFILE_ID", admitted["admitted_profile_id"])
    monkeypatch.setenv("OBSERVER_SNAPSHOT_DIR", snapshot_dir)
    app = create_app()
    image = jpeg((64, 124, 192))

    async def scenario():
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                for _ in range(100):
                    if (await client.get("/health/ready")).status_code == 200:
                        break
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail(f"service never became ready: {app.state.readiness.code}")
                assert app.state.claim_loop.task and not app.state.claim_loop.task.done()
                submitted = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                              json=request_body(image))
                assert submitted.status_code == 202
                run_id = uuid.UUID(submitted.json()["run_id"])
                for _ in range(900):
                    result = (await client.get(f"/runs/{run_id}")).json()
                    if result["state"] in {"succeeded", "failed"}:
                        break
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail("background loop did not reach a terminal state")
                assert result["state"] == "succeeded", result
                assert result["outcome"] == "observations_only" and result["native_evidence"]
                assert len(result["observations"]) == 2
                assert all(row["state"] in {"detected", "not_detected_in_frame"} for row in result["observations"])
                assert result["stages"][2]["state"] == "succeeded"
                with app.state.store.engine.connect() as connection:
                    invocation = connection.execute(text("""SELECT state, actual_device, native_artifact_id
                        FROM observer_invocations WHERE run_id = :run"""), {"run": run_id}).one()
                    refs = connection.execute(text("SELECT key, sha256, size FROM artifact_metadata WHERE run_id = :run"),
                                              {"run": run_id}).all()
                assert invocation.state == "completed" and invocation.actual_device == "cpu"
                assert invocation.native_artifact_id and len(refs) == 2
                for ref in refs:
                    app.state.artifacts.read_verified(ref.key, ref.sha256, ref.size)

    asyncio.run(scenario())
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(RuntimeError, match="observer_timeout"):
        executor._observe_bounded(snapshot_dir, json.loads((admission_dir / "model-files.json").read_text()),
                                  image, 0.001)
    assert {child.pid for child in multiprocessing.active_children()} == before

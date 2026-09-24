import asyncio
import base64
import io
import json
import multiprocessing
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import event, text

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore, RecoveryGateError
from app.application import executor
from app.application import admission, submission
from app.application.submission import SubmissionError, validate_request
from app.config import Config
from app.main import MAX_HTTP_BODY_BYTES, create_app
from app.profiles.grounding_dino import PREPROCESSING_REVISION
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


def test_ordinary_history_orders_and_guards_outcome(database):
    store = database
    first, second, running, failed, unprojected, admission, defaulted = [uuid.uuid4() for _ in range(7)]
    with store.engine.begin() as connection:
        for identifier, state, purpose, age, predecessor in (
            (first, "succeeded", "ordinary", 3, None),
            (second, "queued", "ordinary", 2, first),
            (running, "running", "ordinary", 1, None),
            (failed, "failed", "ordinary", 0, None),
            (unprojected, "succeeded", "ordinary", 4, None),
            (admission, "succeeded", "profile_admission", 0, None),
        ):
            connection.execute(text("""INSERT INTO analysis_runs
                (id, state, purpose, analysis_intent, stage_key, request_context, retry_predecessor_id, created_at)
                VALUES (:id, :state, :purpose, 'observation_only', :stage, CAST(:context AS jsonb), :predecessor,
                        clock_timestamp() - (:age * interval '1 hour'))"""),
                {"id": identifier, "state": state, "purpose": purpose, "age": age, "predecessor": predecessor,
                 "stage": None if identifier == second else "excavation",
                 "context": json.dumps({"stage_id": "excavation"} if identifier == second else {})})
        for identifier in (first, running, failed, admission):
            connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
                VALUES (:id, 'observations_only', '{"outcome":"observations_only"}'::jsonb)"""), {"id": identifier})
        connection.execute(text("UPDATE analysis_runs SET created_at = NULL WHERE id = :id"), {"id": unprojected})
        default_created_at = connection.execute(text("""INSERT INTO analysis_runs
            (id, state, purpose, analysis_intent, stage_key)
            VALUES (:id, 'queued', 'ordinary', 'observation_only', 'excavation') RETURNING created_at"""),
            {"id": defaulted}).scalar_one()
    try:
        all_rows = []
        offset = 0
        while True:
            page = store.list_ordinary(offset)
            all_rows.extend(page["runs"])
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
        assert str(admission) not in {row["run_id"] for row in all_rows}
        assert next(row for row in all_rows if row["run_id"] == str(defaulted))["created_at"] == default_created_at.isoformat()
        rows = [row for row in all_rows if row["run_id"] in {str(first), str(second), str(running), str(failed), str(unprojected)}]
        assert [row["run_id"] for row in rows] == [str(failed), str(running), str(second), str(first), str(unprojected)]
        assert [row["outcome"] for row in rows] == [None, None, None, "observations_only", None]
        assert rows[-1]["created_at"] is None
        assert rows[2]["retry_predecessor_id"] == str(first)
        assert rows[2]["stage"] == "excavation"
        assert store.read_ordinary(second)["stage"] == "excavation"
        assert rows[2]["retry_of_run_id"] == str(first)
        assert rows[3]["retry_successor_id"] == str(second)
        assert rows[3]["successor_run_id"] == str(second)
        assert store.read_ordinary(first)["retry_successor_id"] == str(second)
        assert store.read_ordinary(first)["successor_run_id"] == str(second)
        assert store.read_ordinary(second)["retry_predecessor_id"] == str(first)
        assert store.read_ordinary(second)["retry_of_run_id"] == str(first)
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM result_projections WHERE run_id = ANY(:ids)"), {"ids": [first, second, running, failed, unprojected, admission]})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": [second, first, running, failed, unprojected, admission, defaulted]})


def test_history_route_reads_store_without_starting_observer():
    class Store:
        def list_ordinary(self, offset=0):
            return {"runs": [{"run_id": "persisted", "state": "queued", "outcome": None}], "next_offset": None}

    async def check():
        app = create_app()
        app.state.store = Store()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/runs")
            assert response.status_code == 200
            assert response.json() == {"runs": [{"run_id": "persisted", "state": "queued", "outcome": None}], "next_offset": None}

    asyncio.run(check())


@pytest.mark.parametrize("after_execute", [False, True], ids=["pre-claim", "post-execution"])
@pytest.mark.parametrize("series", [False, True], ids=["single", "series"])
def test_runtime_recovery_preserves_active_submission(isolated_admission_database, integration, monkeypatch,
                                                      series, after_execute):
    config, _, _ = integration
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                                     config.s3_access_key, config.s3_secret_key))
    parent, profile, expired = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    snapshot = {"runtime": {"per_image_timeout_seconds": 2}}
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, '{}'::jsonb)"),
                           {"id": parent, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, '{}'::jsonb, :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""),
            {"id": profile})
        connection.execute(text("""INSERT INTO analysis_runs (id, state, lease_owner, lease_expires_at)
            VALUES (:id, 'running', 'expired-owner', clock_timestamp() + (:seconds * interval '1 second'))"""),
            {"id": expired, "seconds": 3600 if after_execute else -1})
    orphan = store.create_publication_intent(expired, "application/json", uuid.uuid4().hex)
    worker_key = uuid.uuid4().hex if after_execute else None
    worker_run = submission.submit(store, artifacts, worker_key, request_body(jpeg((77, 88, 99))),
                                   profile, 1, snapshot)[1] if after_execute else None
    key = uuid.uuid4().hex
    image_a, image_b = jpeg((11, 22, 33)), jpeg((44, 55, 66))
    body = request_body(image_a) if not series else {
        **{k: v for k, v in request_body(image_a).items() if k != "image_base64"},
        "images_base64": [base64.b64encode(image).decode() for image in (image_a, image_b)]}
    ready_to_pause, resume = threading.Event(), threading.Event()
    upload = artifacts.upload_temporary
    calls = 0

    def paused_upload(*args):
        nonlocal calls
        calls += 1
        if calls == (2 if series else 1):
            ready_to_pause.set()
            assert resume.wait(10)
        return upload(*args)

    monkeypatch.setattr(artifacts, "upload_temporary", paused_upload)
    from concurrent.futures import ThreadPoolExecutor

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            publish = pool.submit(submission.submit_series if series else submission.submit,
                                  store, artifacts, key, body, profile, 1, snapshot)
            assert ready_to_pause.wait(10)
            with store.engine.connect() as connection:
                live_intents = connection.execute(text("SELECT id, state FROM publication_intents WHERE submission_key = :key ORDER BY id"),
                                                  {"key": key}).all()
            assert len(live_intents) == (2 if series else 1)
            assert all(row.state != "quarantined" for row in live_intents)

            async def recover_in_loop():
                ready = asyncio.Event()
                ready.set()
                loop = executor.ClaimLoop()
                loop.store, loop.artifacts = store, artifacts
                executed = False
                if after_execute:
                    loop.runtime_binding = profile, 1

                    async def expire_after_execute(work, revision):
                        nonlocal executed
                        assert work["id"] == worker_run and revision == 1
                        with store.engine.begin() as connection:
                            connection.execute(text("""UPDATE analysis_runs
                                SET lease_expires_at = clock_timestamp() - interval '1 second' WHERE id = :id"""),
                                {"id": expired})
                        executed = True

                    monkeypatch.setattr(loop, "_execute", expire_after_execute)
                loop.start(ready, artifacts, "unused" if after_execute else None)
                try:
                    for _ in range(50):
                        with store.engine.connect() as connection:
                            states = connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                                        {"id": orphan}).scalar_one()
                        if states == "quarantined":
                            break
                        await asyncio.sleep(0.1)
                    assert states == "quarantined"
                    assert executed == after_execute
                    assert ready.is_set()
                finally:
                    ready.clear()
                    await loop.stop()

            asyncio.run(recover_in_loop())
            resume.set()
            status, published_run = publish.result(timeout=10)
            assert status == "queued"
        retry = submission.submit_series if series else submission.submit
        _, run_id = retry(store, artifacts, key, body, profile, 1, snapshot)
        assert run_id == published_run
        with store.engine.connect() as connection:
            request = connection.execute(text("SELECT state, run_id, error_code FROM submission_requests WHERE idempotency_key = :key"),
                                         {"key": key}).one()
            states = connection.execute(text("SELECT state, run_id FROM publication_intents WHERE submission_key = :key"),
                                        {"key": key}).all()
        assert request == ("accepted", run_id, None)
        assert len(states) == (2 if series else 1)
        assert all(row == ("referenced", run_id) for row in states)
    finally:
        resume.set()
        with store.engine.connect() as connection:
            keys = connection.execute(text("SELECT id FROM publication_intents WHERE submission_key IN (:key, :worker_key)"),
                                      {"key": key, "worker_key": worker_key}).scalars().all()
        for intent in keys:
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=f"tmp/{intent}")
        store.close()


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
    observed_images = []

    def observed(_snapshot_dir, _hashes, image_bytes, _seconds):
        observed_images.append(image_bytes)
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
            assert observed_images == [image]
            assert len(done["stages"]) == 6 and done["native_evidence"]["sha256"]
            assert {item["class_name"]: item["state"] for item in done["observations"]} == {
                "excavator": "detected", "dump_truck": "not_detected_in_frame", "tower_crane": "not_analyzed"}
            assert all(item["source_artifact_id"] for item in done["observations"])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"), {"run": run}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"), {"run": run}).scalar_one() == 1
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"), {"run": run}).scalar_one() == 1
            black_image = jpeg((0, 0, 0))
            black = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                      json=request_body(black_image))
            black_run = uuid.UUID(black.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            low_range = (await client.get(f"/runs/{black_run}")).json()
            assert low_range["state"] == "succeeded" and low_range["outcome"] == "observations_only"
            assert observed_images[-1] == black_image
            assert {item["class_name"]: item["state"] for item in low_range["observations"]} == {
                "excavator": "detected", "dump_truck": "not_detected_in_frame"}
            assert all(item["reason"] is None for item in low_range["observations"])
            with store.engine.connect() as connection:
                invocation = connection.execute(text("""SELECT v.input_sha256, i.sha256
                    FROM observer_invocations v JOIN run_inputs i
                    ON i.run_id = v.run_id AND i.input_id = v.input_id WHERE v.run_id = :run"""),
                    {"run": black_run}).one()
            assert invocation.input_sha256 == invocation.sha256
            unsupported = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex},
                                            json=request_body(jpeg((33, 111, 222)), ["tower_crane"]))
            unsupported_run = uuid.UUID(unsupported.json()["run_id"])
            observed_count = len(observed_images)
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            unsupported_state = (await client.get(f"/runs/{unsupported_run}")).json()
            assert unsupported_state["state"] == "succeeded" and unsupported_state["outcome"] == "observations_only"
            assert unsupported_state["observations"][0]["state"] == "not_analyzed"
            assert len(observed_images) == observed_count
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
            monkeypatch.setattr(executor, "_observe_bounded", lambda *args: observed(*args) | {"states": {"excavator": "unknown"}})
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            malformed_state = (await client.get(f"/runs/{malformed_run}")).json()
            assert malformed_state["state"] == "failed" and malformed_state["outcome"] is None
            contradictory = await client.post("/runs/single-image", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body)
            contradictory_run = uuid.UUID(contradictory.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", lambda *args: observed(*args) | {
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
            store.reconcile(artifacts)
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


def test_expired_lease_fences_completion_during_recovery(isolated_admission_database, request):
    store = PostgresStore(isolated_admission_database)
    request.addfinalizer(store.close)
    parent, profile = uuid.uuid4(), uuid.uuid4()
    image_hash = "a" * 64
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, '{}'::jsonb)"),
                           {"id": parent, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, '{}'::jsonb, :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""), {"id": profile})
    key = uuid.uuid4().hex
    _, _, intent, _ = store.begin_submission(key, uuid.uuid4().hex, "image/jpeg")
    store.publication_content_verified(intent, image_hash, 1, f"sha256/{image_hash}")
    store.publication_object_published(intent)
    snapshot = {"model_files": {"model.safetensors": image_hash}}
    run_id = store.commit_submission(key, profile, 1, snapshot, {}, ["excavator", "dump_truck"], image_hash, 1)
    work = store.claim_ordinary(profile, 1, 3)
    assert work["id"] == run_id
    invocation = store.reserve_ordinary(run_id, work["owner"], 1, image_hash)
    native_intent = store.create_publication_intent(run_id, "application/json", f"{run_id}:native")
    store.publication_content_verified(native_intent, "b" * 64, 2, f"sha256/{'b' * 64}")
    store.publication_object_published(native_intent)
    result = {"returned_model_identity": f"checkpoint-sha256:{image_hash}", "actual_device": "cpu",
              "preprocessing_revision": PREPROCESSING_REVISION, "latency_ms": 1.0, "peak_memory_bytes": 1}
    observations = [{"class_name": name, "state": "not_detected_in_frame", "reason": None,
                     "source_artifact_id": str(work["artifact_id"])} for name in ("excavator", "dump_truck")]
    locked, release = threading.Event(), threading.Event()
    lock_error_states = []

    def hold_completion_after_lock(_conn, _cursor, statement, _params, _context, _many):
        if "SELECT r.profile_snapshot, r.state, r.lease_owner" in statement:
            locked.set()
            assert release.wait(10), "completion lock was not released"

    def capture_recovery_error(context):
        if context.statement and "FOR UPDATE NOWAIT" in context.statement:
            lock_error_states.append(getattr(context.original_exception, "sqlstate", None))

    event.listen(store.engine, "after_cursor_execute", hold_completion_after_lock)
    event.listen(store.engine, "handle_error", capture_recovery_error)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            completion = pool.submit(store.finish_ordinary, run_id, work["owner"], 1,
                                     invocation, result, native_intent, observations)
            assert locked.wait(5), "completion did not acquire the run lock"
            with store.engine.connect() as connection:
                live = connection.execute(text("SELECT lease_expires_at > clock_timestamp() FROM analysis_runs WHERE id = :id"),
                                          {"id": run_id}).scalar_one()
            assert live, "lease expired before completion acquired its lock"
            deadline = time.monotonic() + 5
            while True:
                with store.engine.connect() as connection:
                    expired = connection.execute(text("SELECT lease_expires_at <= clock_timestamp() FROM analysis_runs WHERE id = :id"),
                                                 {"id": run_id}).scalar_one()
                if expired:
                    break
                assert time.monotonic() < deadline, "lease did not expire"
                time.sleep(0.02)
            with pytest.raises(RecoveryGateError, match="recovery_gate_failed"):
                store.recover()
            assert lock_error_states == ["55P03"]
            release.set()
            with pytest.raises(AdmissionStoreError, match="ordinary_completion_rejected"):
                completion.result(timeout=10)
    finally:
        release.set()
        event.remove(store.engine, "after_cursor_execute", hold_completion_after_lock)
        event.remove(store.engine, "handle_error", capture_recovery_error)
    with pytest.raises(AdmissionStoreError, match="ordinary_lease_rejected"):
        store.renew_ordinary(run_id, work["owner"], 1, 30)
    store.recover()
    with store.engine.connect() as connection:
        run = connection.execute(text("SELECT state, error_code, lease_owner FROM analysis_runs WHERE id = :id"),
                                 {"id": run_id}).one()
        stages = connection.execute(text("SELECT ordinal, state, reason FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"),
                                    {"id": run_id}).all()
        projections = connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :id"),
                                         {"id": run_id}).scalar_one()
        persisted_observations = connection.execute(text("SELECT count(*) FROM observations WHERE run_id = :id"),
                                                    {"id": run_id}).scalar_one()
        invocation_state = connection.execute(text("SELECT state, native_artifact_id FROM observer_invocations WHERE id = :id"),
                                              {"id": invocation}).one()
        native_references = connection.execute(text("SELECT count(*) FROM artifact_metadata WHERE intent_id = :id"),
                                               {"id": native_intent}).scalar_one()
    assert run == ("failed", "executor_interrupted", None)
    assert stages[2] == (2, "failed", "executor_interrupted")
    assert all(state == "skipped" and reason == "dependency_failed" for _, state, reason in stages[3:])
    assert projections == persisted_observations == 0
    assert invocation_state == ("failed", None)
    assert native_references == 0

import asyncio
import base64
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.application import executor, submission
from app.config import Config
from app.main import create_app
from test_admission import isolated_admission_database
from test_single_image import jpeg
from test_startup import database, integration


BACKEND = Path(__file__).resolve().parents[1]


def test_stalled_duplicate_has_bounded_retry(monkeypatch):
    class Store:
        calls = 0

        def begin_submission(self, *_):
            self.calls += 1
            return "publishing", None, None, None

        def fail_submission(self, *_):
            raise AssertionError("duplicate must not mutate publisher")

    ticks = iter((0, 0, 3))
    monkeypatch.setattr(submission.time, "monotonic", lambda: next(ticks, 3))
    monkeypatch.setattr(submission.time, "sleep", lambda *_: None)
    store = Store()
    with pytest.raises(submission.SubmissionError, match="submission_in_progress"):
        submission.submit_series(store, None, "stalled", body(jpeg((0, 0, 0)), jpeg((0, 0, 0))),
                                 uuid.uuid4(), 1, {})
    assert store.calls == 2


def test_run_artifact_route_verifies_scoped_bytes():
    run_id, artifact_id = uuid.uuid4(), uuid.uuid4()

    class Store:
        def resolve_run_artifact(self, requested_run, requested_artifact):
            if (requested_run, requested_artifact) == (run_id, artifact_id):
                return {"key": "sha256/abc", "sha256": "abc", "size": 4, "media_type": "image/jpeg"}
            return None

    class Artifacts:
        error = None

        def read_verified(self, key, digest, size):
            assert (key, digest, size) == ("sha256/abc", "abc", 4)
            if self.error:
                raise ArtifactGateError(self.error)
            return b"data"

    app = create_app()
    app.state.store, app.state.artifacts = Store(), Artifacts()

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            url = f"/runs/{run_id}/artifacts/{artifact_id}"
            response = await client.get(url)
            assert response.status_code == 200 and response.content == b"data"
            assert response.headers["content-type"].startswith("image/jpeg")
            assert (await client.get(f"/runs/{uuid.uuid4()}/artifacts/{artifact_id}")).status_code == 404
            for code, status in (("artifact_integrity_failed", 409), ("artifact_read_unavailable", 503)):
                app.state.artifacts.error = code
                response = await client.get(url)
                assert response.status_code == status and response.json() == {"code": code}

    asyncio.run(scenario())


def test_verified_artifact_read_distinguishes_outage_from_corruption():
    import hashlib

    payload = b"data"
    digest = hashlib.sha256(payload).hexdigest()
    artifact = ArtifactStore.__new__(ArtifactStore)
    artifact.bucket = "test"
    artifact.client = SimpleNamespace(
        head_object=lambda **_: {"ContentLength": len(payload)},
        get_object=lambda **_: {"Body": SimpleNamespace(read=lambda: payload)},
    )
    assert artifact.read_verified(f"sha256/{digest}", digest, len(payload)) == payload
    with pytest.raises(ArtifactGateError, match="artifact_integrity_failed"):
        artifact.read_verified(f"sha256/{digest}", digest, len(payload) + 1)
    artifact.client.get_object = lambda **_: {"Body": SimpleNamespace(read=lambda: b"deta")}
    with pytest.raises(ArtifactGateError, match="artifact_integrity_failed"):
        artifact.read_verified(f"sha256/{digest}", digest, len(payload))
    artifact.client.head_object = lambda **_: (_ for _ in ()).throw(ConnectionError("S3 unavailable"))
    with pytest.raises(ArtifactGateError, match="artifact_read_unavailable"):
        artifact.read_verified(f"sha256/{digest}", digest, len(payload))
    def missing(code):
        return ClientError({"Error": {"Code": code, "Message": code}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "HeadObject")
    artifact.client.head_object = lambda **_: (_ for _ in ()).throw(missing("404"))
    artifact.client.get_object = lambda **_: (_ for _ in ()).throw(missing("NoSuchKey"))
    with pytest.raises(ArtifactGateError, match="artifact_integrity_failed"):
        artifact.read_verified(f"sha256/{digest}", digest, len(payload))
    artifact.client.get_object = lambda **_: (_ for _ in ()).throw(missing("NoSuchBucket"))
    with pytest.raises(ArtifactGateError, match="artifact_read_unavailable"):
        artifact.read_verified(f"sha256/{digest}", digest, len(payload))


def test_interrupted_series_reconciliation_reaches_readiness(isolated_admission_database, integration):
    config, _, artifacts = integration
    store = PostgresStore(isolated_admission_database)
    key = uuid.uuid4().hex
    _, _, first, _ = store.begin_submission(key, uuid.uuid4().hex, "image/jpeg")
    second, third = store.create_submission_intent(key), store.create_submission_intent(key)
    store.fail_submission(key, "submission_interrupted")
    try:
        store.reconcile(artifacts)
        with store.engine.connect() as connection:
            rows = connection.execute(text("SELECT id, state FROM publication_intents WHERE id IN (:a, :b, :c)"),
                {"a": first, "b": second, "c": third}).all()
            assert {row.id for row in rows} == {first, second, third}
            assert all(row.state == "quarantined" for row in rows)
            assert connection.execute(text("SELECT status FROM reconciliation_runs ORDER BY id DESC LIMIT 1")).scalar_one() == "succeeded"
        async def check_ready():
            app = create_app()
            async with app.router.lifespan_context(app):
                await app.state.startup_task
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.get("/health/ready")
                    assert response.status_code == 200
                    assert response.json() == {"ready": True, "code": "ready"}

        asyncio.run(check_ready())
    finally:
        store.close()


def test_populated_single_image_upgrade_preserves_associations(integration, monkeypatch):
    config, _, _ = integration
    database_name = f"series_upgrade_{uuid.uuid4().hex}"
    database_url = make_url(config.database_url).set(database=database_name).render_as_string(hide_password=False)
    admin = create_engine(config.database_url, isolation_level="AUTOCOMMIT")
    migrations = AlembicConfig(str(BACKEND / "alembic.ini"))
    migrations.set_main_option("script_location", str(BACKEND / "migrations"))
    migrations.set_main_option("path_separator", "os")
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        monkeypatch.setenv("DATABASE_URL", database_url)
        command.upgrade(migrations, "0003_single_image")
        engine = create_engine(database_url)
        try:
            profile = uuid.uuid4()
            run_ids = [uuid.uuid4(), uuid.uuid4()]
            invocations = [uuid.uuid4(), uuid.uuid4()]
            with engine.begin() as connection:
                connection.execute(text("""INSERT INTO observer_profiles (id, status, profile_hash, snapshot)
                    VALUES (:id, 'draft', :hash, '{}'::jsonb)"""), {"id": profile, "hash": uuid.uuid4().hex})
                for purpose, run_id, invocation_id in zip(("profile_admission", "ordinary"), run_ids, invocations):
                    connection.execute(text("""INSERT INTO analysis_runs (id, state, purpose, profile_id)
                        VALUES (:run, 'succeeded', :purpose, :profile)"""),
                        {"run": run_id, "purpose": purpose, "profile": profile})
                    connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, fixture_id, sha256, size, context)
                        VALUES (:run, 0, :fixture, :hash, 1, '{}'::jsonb)"""),
                        {"run": run_id, "fixture": "fixture" if purpose == "profile_admission" else None,
                         "hash": "a" * 64})
                    connection.execute(text("""INSERT INTO observer_invocations
                        (id, run_id, fence, profile_id, stage_ordinal, input_sha256, intended_request_identity, state)
                        VALUES (:id, :run, 1, :profile, 2, :hash, 'local-grounding-dino-cpu', 'completed')"""),
                        {"id": invocation_id, "run": run_id, "profile": profile, "hash": "a" * 64})
                    for name in ("excavator", "dump_truck"):
                        connection.execute(text("""INSERT INTO observations
                            (run_id, class_name, state, input_sha256, invocation_id)
                            VALUES (:run, :name, 'not_detected_in_frame', :hash, :invocation)"""),
                            {"run": run_id, "name": name, "hash": "a" * 64, "invocation": invocation_id})
            command.upgrade(migrations, "0004_ordered_series")
            with engine.connect() as connection:
                rows = connection.execute(text("""SELECT r.run_id, r.input_id, i.input_id AS invocation_input,
                    o.input_id AS observation_input FROM run_inputs r
                    JOIN observer_invocations i ON i.run_id = r.run_id
                    JOIN observations o ON o.run_id = r.run_id
                    ORDER BY r.run_id""")).all()
            assert len(rows) == 4
            assert {row.run_id for row in rows} == set(run_ids)
            assert all(row.input_id == row.invocation_input == row.observation_input for row in rows)
            with engine.connect() as connection:
                input_ids = dict(connection.execute(text("SELECT run_id, input_id FROM run_inputs")).all())
            for table in ("observer_invocations", "observations"):
                with pytest.raises(IntegrityError), engine.begin() as connection:
                    connection.execute(text(f"UPDATE {table} SET input_id = :other WHERE run_id = :run"),
                                       {"other": input_ids[run_ids[1]], "run": run_ids[0]})
        finally:
            engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        admin.dispose()


def body(*images):
    return {"intent": "observation_only", "scenario": "equipment_check",
            "observation_area": "north_gate", "period": "2026-09-23T12:00:00+03:00",
            "images_base64": [base64.b64encode(image).decode() for image in images]}


def test_ordered_series_http_postgres_s3(isolated_admission_database, integration, monkeypatch):
    config, _, _ = integration
    config = Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                    config.s3_access_key, config.s3_secret_key)
    store, artifacts = PostgresStore(isolated_admission_database), ArtifactStore(config)
    absent_digest = uuid.uuid4().hex + uuid.uuid4().hex
    with pytest.raises(ArtifactGateError, match="artifact_integrity_failed"):
        artifacts.read_verified(f"sha256/{absent_digest}", absent_digest, 1)
    missing_bucket = ArtifactStore.__new__(ArtifactStore)
    missing_bucket.bucket, missing_bucket.client = f"missing-{uuid.uuid4().hex}", artifacts.client
    with pytest.raises(ArtifactGateError, match="artifact_read_unavailable"):
        missing_bucket.read_verified(f"sha256/{absent_digest}", absent_digest, 1)
    parent, profile = uuid.uuid4(), uuid.uuid4()
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
    first, second, black = jpeg((12, 120, 220)), jpeg((33, 111, 222)), jpeg((0, 0, 0))
    calls = 0

    def observed(*_):
        nonlocal calls
        calls += 1
        return {"states": {"excavator": "detected" if calls % 2 else "not_detected_in_frame",
                           "dump_truck": "not_detected_in_frame"},
                "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
                "latency_ms": 1.0, "peak_memory_bytes": 1024,
                "native": {"detections": ([{"label": "an excavator", "score": 0.8, "box": [1, 2, 3, 4]}]
                                          if calls % 2 else []),
                           "image_size": [96, 96]}}

    monkeypatch.setattr(executor, "_observe_bounded", observed)

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for invalid in (body(first), body(first, b"bad"), body(first, second) | {"period": "yesterday"}):
                response = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex}, json=invalid)
                assert response.status_code == 400
            pending_key = uuid.uuid4().hex
            pending_body = body(first, second)
            _, _, _, pending_hash = submission.validate_images(pending_body, True)
            store.begin_submission(pending_key, pending_hash, "image/jpeg")
            original_wait = submission.wait_for_submission
            monkeypatch.setattr(submission, "wait_for_submission", lambda *_: (_ for _ in ()).throw(
                submission.SubmissionError("submission_in_progress")))
            pending = await client.post("/runs/series", headers={"Idempotency-Key": pending_key}, json=pending_body)
            assert pending.status_code == 202 and pending.json() == {"code": "submission_in_progress"}
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT state FROM submission_requests WHERE idempotency_key = :key"),
                                          {"key": pending_key}).scalar_one() == "publishing"
            store.fail_submission(pending_key, "submission_interrupted")
            monkeypatch.setattr(submission, "wait_for_submission", original_wait)
            key = uuid.uuid4().hex
            submitted = await client.post("/runs/series", headers={"Idempotency-Key": key}, json=body(first, second))
            assert submitted.status_code == 202
            run = uuid.UUID(submitted.json()["run_id"])
            duplicate = await client.post("/runs/series", headers={"Idempotency-Key": key}, json=body(first, second))
            assert duplicate.json()["run_id"] == str(run)
            reversed_order = await client.post("/runs/series", headers={"Idempotency-Key": key}, json=body(second, first))
            assert reversed_order.status_code == 409 and reversed_order.json() == {"code": "idempotency_key_conflict"}
            queued = (await client.get(f"/runs/{run}")).json()
            assert [item["ordinal"] for item in queued["inputs"]] == [0, 1]
            assert queued["inputs"][0]["sha256"] != queued["inputs"][1]["sha256"]
            with store.engine.connect() as connection:
                persisted = connection.execute(text("SELECT input_id, ordinal, artifact_id FROM run_inputs WHERE run_id = :run ORDER BY ordinal"),
                                               {"run": run}).all()
                assert [(str(i), n, str(a)) for i, n, a in persisted] == [
                    (item["input_id"], item["ordinal"], item["artifact_id"]) for item in queued["inputs"]]
                refs = connection.execute(text("""SELECT a.key, a.sha256, a.size FROM artifact_metadata a
                    JOIN run_inputs i ON i.artifact_id = a.id WHERE i.run_id = :run ORDER BY i.ordinal"""),
                    {"run": run}).all()
            assert [artifacts.read_verified(*ref) for ref in refs] == [first, second]
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            done = (await client.get(f"/runs/{run}")).json()
            assert done["state"] == "succeeded" and done["outcome"] == "observations_only", done["error_code"]
            assert done["result_projection"]["series"]["usable_input_ids"] == [item["input_id"] for item in done["inputs"]]
            assert done["result_projection"]["series"]["usable_count"] == 2
            assert done["result_projection"]["series"]["excavator_supporting_input_ids"] == [done["inputs"][0]["input_id"]]
            assert done["result_projection"]["series"]["declared_observation_area"] == "north_gate"
            assert done["result_projection"]["series"]["dump_truck_persistence_input_ids"] == [item["input_id"] for item in done["inputs"]]
            assert done["result_projection"]["series"]["dump_truck_persistence_text"] == "Самосвал не обнаружен ни в одном из 2 пригодных кадров."
            image_response = await client.get(f"/runs/{run}/artifacts/{done['inputs'][0]['artifact_id']}")
            assert image_response.status_code == 200 and image_response.content == first
            assert image_response.headers["content-type"].startswith("image/jpeg")
            assert (await client.get(f"/runs/{uuid.uuid4()}/artifacts/{done['inputs'][0]['artifact_id']}")).status_code == 404
            native_response = await client.get(f"/runs/{run}/artifacts/{done['native_evidence_by_frame'][0]['artifact_id']}")
            assert native_response.status_code == 200 and b"detections" in native_response.content
            verified_read = artifacts.read_verified
            for code, status in (("artifact_integrity_failed", 409), ("artifact_read_unavailable", 503)):
                monkeypatch.setattr(artifacts, "read_verified", lambda *_args, code=code: (_ for _ in ()).throw(ArtifactGateError(code)))
                error_response = await client.get(f"/runs/{run}/artifacts/{done['inputs'][0]['artifact_id']}")
                assert error_response.status_code == status and error_response.json() == {"code": code}
            monkeypatch.setattr(artifacts, "read_verified", verified_read)
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE result_projections SET snapshot = snapshot - 'series' WHERE run_id = :run"), {"run": run})
            assert (await client.get(f"/runs/{run}")).json()["result_projection"] == {"outcome": "observations_only", "frames": done["result_projection"]["frames"]}
            assert done["stages"][3]["state"] == "succeeded"
            assert [item["ordinal"] for item in done["observations"]] == [0, 0, 1, 1]
            assert {item["input_id"] for item in done["observations"]} == {item["input_id"] for item in done["inputs"]}
            assert all(item["invocation_id"] for item in done["observations"])
            assert len(done["native_evidence_by_frame"]) == 2
            assert [item["ordinal"] for item in done["native_evidence_by_frame"]] == [0, 1]
            with store.engine.connect() as connection:
                invocations = connection.execute(text("""SELECT v.id, v.input_id, i.ordinal FROM observer_invocations v
                    JOIN run_inputs i ON i.run_id = v.run_id AND i.input_id = v.input_id
                    WHERE v.run_id = :run ORDER BY i.ordinal"""), {"run": run}).all()
                native_refs = connection.execute(text("""SELECT a.key, a.sha256, a.size
                    FROM observer_invocations v JOIN artifact_metadata a ON a.id = v.native_artifact_id
                    JOIN run_inputs i ON i.input_id = v.input_id
                    WHERE v.run_id = :run ORDER BY i.ordinal"""), {"run": run}).all()
            for ordinal, (invocation_id, input_id, _) in enumerate(invocations):
                assert done["native_evidence_by_frame"][ordinal]["input_id"] == str(input_id)
                assert done["inputs"][ordinal]["input_id"] == str(input_id)
                assert {item["invocation_id"] for item in done["observations"] if item["ordinal"] == ordinal} == {str(invocation_id)}
            assert all(artifacts.read_verified(*ref) for ref in native_refs)

            same = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body(first, first))
            same_run = uuid.UUID(same.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            equal = (await client.get(f"/runs/{same_run}")).json()
            assert [item["ordinal"] for item in equal["inputs"]] == [0, 1]
            assert equal["inputs"][0]["sha256"] == equal["inputs"][1]["sha256"]
            assert equal["inputs"][0]["input_id"] != equal["inputs"][1]["input_id"]
            assert len(equal["observations"]) == 4
            assert equal["result_projection"]["series"]["input_order"] == [item["input_id"] for item in equal["inputs"]]
            assert {item["source_artifact_id"] for item in equal["observations"]} == {
                item["artifact_id"] for item in equal["inputs"]}

            mixed = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body(first, black))
            mixed_run = uuid.UUID(mixed.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            result = (await client.get(f"/runs/{mixed_run}")).json()
            assert result["state"] == "succeeded" and result["outcome"] == "observations_only"
            assert all(item["state"] == "insufficient_data" and item["reason"] == "frame_unassessable"
                       for item in result["observations"] if item["ordinal"] == 1)
            assert "absence" not in str(result)
            assert result["result_projection"]["series"]["usable_count"] == 1
            assert result["result_projection"]["series"]["dump_truck_persistence_text"] is None

            all_black = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                          json=body(black, black))
            all_black_run = uuid.UUID(all_black.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            all_black_done = (await client.get(f"/runs/{all_black_run}")).json()
            assert all_black_done["state"] == "succeeded"
            assert all_black_done["stages"][2]["reason"] == "no_assessable_frame_or_supported_class"
            assert all(item["state"] == "insufficient_data" for item in all_black_done["observations"])
            assert all_black_done["result_projection"]["series"]["usable_count"] == 0

            failing = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body(first, second))
            failing_run = uuid.UUID(failing.json()["run_id"])
            before = calls

            def fail_later(*args):
                if calls > before:
                    raise RuntimeError("provider_secret")
                return observed(*args)

            monkeypatch.setattr(executor, "_observe_bounded", fail_later)
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            failed = (await client.get(f"/runs/{failing_run}")).json()
            assert failed["state"] == "failed" and failed["outcome"] is None
            assert failed["error_code"] == "observer_execution_failed"
            assert len(failed["observations"]) == 2 and len(failed["native_evidence_by_frame"]) == 1
            assert failed["result_projection"] is None
            assert (await client.get(f"/runs/{failing_run}/artifacts/{failed['inputs'][0]['artifact_id']}")).status_code == 200
            assert failed["stages"][2]["state"] == "failed"
            assert all(stage["state"] == "skipped" for stage in failed["stages"][3:])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": failing_run}).scalar_one() == 0
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run AND state = 'completed'"),
                                          {"run": failing_run}).scalar_one() == 1

            unreadable = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                           json=body(first, second))
            unreadable_run = uuid.UUID(unreadable.json()["run_id"])
            work = store.claim_ordinary(profile, 1, 30)
            original_read = artifacts.read_verified

            def fail_second_frame(key, digest, size):
                if key == work["frames"][1]["key"]:
                    raise RuntimeError("artifact_integrity_failed")
                return original_read(key, digest, size)

            monkeypatch.setattr(executor, "_observe_bounded", observed)
            monkeypatch.setattr(artifacts, "read_verified", fail_second_frame)
            await loop._execute(work, 1)
            unreadable_result = (await client.get(f"/runs/{unreadable_run}")).json()
            assert unreadable_result["state"] == "failed" and unreadable_result["outcome"] is None
            assert unreadable_result["error_code"] == "artifact_integrity_failed"
            assert len(unreadable_result["observations"]) == 2
            assert len(unreadable_result["native_evidence_by_frame"]) == 1
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": unreadable_run}).scalar_one() == 0

            owner_key, foreign_key = "x", "x:1"
            _, _, owner_intent, _ = store.begin_submission(owner_key, uuid.uuid4().hex, "image/jpeg")
            _, _, foreign_intent, _ = store.begin_submission(foreign_key, uuid.uuid4().hex, "image/jpeg")
            second_owner_intent = store.create_submission_intent(owner_key)
            with store.engine.connect() as connection:
                intent_keys = connection.execute(text("""SELECT idempotency_key FROM publication_intents
                    WHERE id IN (:first, :second, :third)"""),
                    {"first": owner_intent, "second": foreign_intent, "third": second_owner_intent}).scalars().all()
            assert len(set(intent_keys)) == 3
            for intent in (owner_intent, foreign_intent, second_owner_intent):
                store.publication_content_verified(intent, "a" * 64, 1, f"sha256/{'a' * 64}")
                store.publication_object_published(intent)
            with pytest.raises(AdmissionStoreError, match="publication_incomplete"):
                store.commit_series_submission(owner_key, profile, 1, snapshot, {}, ["excavator"],
                                               [(owner_intent, "a" * 64, 1), (foreign_intent, "a" * 64, 1)])
            store.fail_submission(owner_key, "submission_interrupted")
            store.fail_submission(foreign_key, "submission_interrupted")

    try:
        asyncio.run(scenario())
    finally:
        store.close()

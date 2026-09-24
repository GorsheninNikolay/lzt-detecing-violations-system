import asyncio
import base64
import hashlib
import json
import io
import threading
from concurrent.futures import ThreadPoolExecutor
import uuid
from types import SimpleNamespace
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from botocore.exceptions import ClientError
from httpx import ASGITransport, AsyncClient
from PIL import Image, ImageDraw
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from app.adapters import postgres
from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.application import executor, submission
from app.config import Config
from app.main import create_app
from app import main
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
            command.upgrade(migrations, "head")
            with engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM analysis_runs WHERE created_at IS NULL")).scalar_one() == 2
        finally:
            engine.dispose()
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        admin.dispose()


@pytest.mark.parametrize("branch,column", [
    ("0005_retry", "retry_of_run_id"),
    ("0007_run_history", "retry_predecessor_id"),
])
def test_retry_branch_upgrade_preserves_lineage(integration, monkeypatch, branch, column):
    config, _, _ = integration
    database_name = f"retry_upgrade_{uuid.uuid4().hex}"
    database_url = make_url(config.database_url).set(database=database_name).render_as_string(hide_password=False)
    admin = create_engine(config.database_url, isolation_level="AUTOCOMMIT")
    migrations = AlembicConfig(str(BACKEND / "alembic.ini"))
    migrations.set_main_option("script_location", str(BACKEND / "migrations"))
    migrations.set_main_option("path_separator", "os")
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
        monkeypatch.setenv("DATABASE_URL", database_url)
        command.upgrade(migrations, branch)
        engine = create_engine(database_url)
        try:
            source, successor = uuid.uuid4(), uuid.uuid4()
            with engine.begin() as connection:
                connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:id, 'failed', 'ordinary')"),
                                   {"id": source})
                connection.execute(text(f"""INSERT INTO analysis_runs (id, state, purpose, {column})
                    VALUES (:id, 'queued', 'ordinary', :source)"""), {"id": successor, "source": source})
            command.upgrade(migrations, "head")
            with engine.connect() as connection:
                assert connection.execute(text("SELECT retry_predecessor_id FROM analysis_runs WHERE id = :id"),
                                          {"id": successor}).scalar_one() == source
                assert not connection.execute(text("""SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'analysis_runs' AND column_name = 'retry_of_run_id'""")).first()
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


def test_stage_binding_is_explicit_and_changes_request_identity():
    request = {key: value for key, value in body(jpeg((1, 2, 3))).items() if key != "images_base64"}
    request["image_base64"] = body(jpeg((1, 2, 3)))["images_base64"][0]
    _, legacy_context, _, legacy_hash = submission.validate_request(request)
    assert "stage_id" not in legacy_context
    _, context, _, bound_hash = submission.validate_request({**request, "stage_id": "excavation"})
    assert context["stage_id"] == "excavation" and bound_hash != legacy_hash
    with pytest.raises(submission.SubmissionError, match="invalid_stage_id"):
        submission.validate_request({**request, "stage_id": "foundation"})


@pytest.mark.parametrize("series", [False, True])
def test_observation_stage_id_reuses_published_request_hash(series):
    image = jpeg((1, 2, 3))
    request = body(image, image) if series else {
        **{key: value for key, value in body(image).items() if key != "images_base64"},
        "image_base64": base64.b64encode(image).decode(),
    }
    request["stage_id"] = "excavation"
    _, context, requested, actual_hash = submission.validate_images(request, series)
    legacy_identity = {
        "context": context,
        "requested_classes": sorted(requested),
        "image_sha256": [hashlib.sha256(image).hexdigest()] * 2 if series else hashlib.sha256(image).hexdigest(),
    }
    canonical = json.dumps(legacy_identity, sort_keys=True, separators=(",", ":"))
    assert actual_hash == hashlib.sha256(canonical.encode()).hexdigest()


def test_stage_summary_route_returns_stable_error():
    app = create_app()

    class Store:
        def stage_summary(self):
            raise RuntimeError("database unavailable")

    app.state.store = Store()

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/stages/summary")
            assert response.status_code == 503
            assert response.json() == {"code": "stage_summary_unavailable"}

    asyncio.run(scenario())


def test_stage_summary_separates_projection_and_newer_lifecycle(isolated_admission_database):
    store = PostgresStore(isolated_admission_database)
    legacy, admission, result, no_projection = [uuid.uuid4() for _ in range(4)]
    newer = [uuid.uuid4() for _ in range(51)]
    try:
        with store.engine.begin() as connection:
            for run_id, purpose, state, context, age in (
                (legacy, "ordinary", "succeeded", {}, 10),
                (admission, "profile_admission", "succeeded", {"stage_id": "excavation"}, 9),
                (result, "ordinary", "succeeded", {}, 98),
                (no_projection, "ordinary", "succeeded", {"stage_id": "excavation"}, 97),
                *((run_id, "ordinary", "failed", {"stage_id": "excavation"}, 96 - index)
                  for index, run_id in enumerate(newer)),
            ):
                connection.execute(text("""INSERT INTO analysis_runs
                    (id, purpose, state, request_context, stage_key, created_at)
                    VALUES (:id, :purpose, :state, CAST(:context AS jsonb), :stage,
                    '2026-09-24T10:00:00Z'::timestamptz - (:age * interval '1 minute'))"""),
                    {"id": run_id, "purpose": purpose, "state": state,
                     "context": json.dumps(context), "stage": "excavation" if run_id == result else None,
                     "age": age})
            for run_id in (legacy, admission, result):
                connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
                    VALUES (:id, 'observations_only', '{"outcome":"observations_only"}'::jsonb)"""), {"id": run_id})
        summary = store.stage_summary()["stages"]
        excavation = next(stage for stage in summary if stage["stage_id"] == "excavation")
        assert excavation["latest_result"] == {"run_id": str(result), "created_at": "2026-09-24T08:22:00+00:00",
                                                "projection": {"outcome": "observations_only"}}
        assert excavation["latest_lifecycle"]["run_id"] == str(newer[-1])
        assert all(not stage["supported"] and stage["latest_result"] is None for stage in summary if stage is not excavation)
    finally:
        store.close()


@pytest.mark.parametrize("series", [False, True], ids=["single", "series"])
def test_failed_retry_is_linear_and_keeps_source(isolated_admission_database, integration, monkeypatch, series):
    config, _, _ = integration
    config = Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                    config.s3_access_key, config.s3_secret_key)
    store, artifacts = PostgresStore(isolated_admission_database), ArtifactStore(config)
    parent, profile = uuid.uuid4(), uuid.uuid4()
    snapshot = {"model_files": {"model.safetensors": "a" * 64},
                "runtime": {"per_image_timeout_seconds": 2, "batch_timeout_seconds": 10}}
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, '{}'::jsonb)"),
                           {"id": parent, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, CAST(:snapshot AS jsonb), :audit)"""),
            {"id": profile, "parent": parent, "hash": uuid.uuid4().hex, "audit": uuid.uuid4().hex,
             "snapshot": json.dumps(snapshot)})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            SELECT :id, 1, 'enabled', 'test', audit_hash, false FROM observer_profiles WHERE id = :id"""), {"id": profile})
    monkeypatch.setattr(store, "require_authorized", lambda *_: (snapshot, 1))
    monkeypatch.setattr(main, "verify_snapshot", lambda *_: None)
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, artifacts
    loop = executor.ClaimLoop()
    loop.runtime_binding, loop.snapshot_dir = (profile, 1), "unused"
    loop.store, loop.artifacts = store, artifacts
    app.state.claim_loop = loop
    monkeypatch.setattr(executor, "_observe_bounded", lambda *_: {
        "states": {"excavator": "not_detected_in_frame", "dump_truck": "not_detected_in_frame"},
        "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
        "latency_ms": 1.0, "peak_memory_bytes": 1024,
        "native": {"detections": [], "image_size": [96, 96]},
    })
    first, second = jpeg((12, 120, 220)), jpeg((33, 111, 222))
    submit = submission.submit_series if series else submission.submit
    request = body(first, second) if series else {**{key: value for key, value in body(first).items()
                                                 if key != "images_base64"}, "image_base64": base64.b64encode(first).decode()}
    request["stage_id"] = "excavation"
    _, source = submit(store, artifacts, uuid.uuid4().hex, request, profile, 1, snapshot)
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE analysis_runs SET state = 'failed', error_code = 'observer_timeout' WHERE id = :id"),
                           {"id": source})
    original = store.read_ordinary(source)

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get(f"/runs/{source}")).json()["retry_eligible"] is True
            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(store.retry_ordinary, source, profile, 1, snapshot, artifacts) for _ in range(2)]
                successors = [future.result(timeout=20) for future in futures]
            assert successors[0] == successors[1]
            successor = successors[0]
            assert (await client.post(f"/runs/{source}/retry")).json()["run_id"] == str(successor)
            assert (await client.get(f"/runs/{successor}")).json()["retry_predecessor_id"] == str(source)
            assert (await client.get(f"/runs/{successor}")).json()["retry_of_run_id"] == str(source)
            assert (await client.get(f"/runs/{successor}")).json()["retry_eligible"] is False
            history = (await client.get("/runs")).json()["runs"]
            assert len(history) == 2 and next(item for item in history if item["id"] == str(source))["retry_successor_id"] == str(successor)
            assert next(item for item in history if item["id"] == str(source))["successor_run_id"] == str(successor)
            assert next(item for item in history if item["id"] == str(successor))["retry_of_run_id"] == str(source)
            predecessor = (await client.get(f"/runs/{source}")).json()
            descendant = (await client.get(f"/runs/{successor}")).json()
            assert predecessor["successor_run_id"] == predecessor["retry_successor_id"] == str(successor)
            assert descendant["retry_of_run_id"] == descendant["retry_predecessor_id"] == str(source)
            assert predecessor["retry_of_run_id"] is None
            assert descendant["successor_run_id"] is None
            assert predecessor["inputs"] == original["inputs"]
            assert predecessor["stages"] == original["stages"]
            assert predecessor["error_code"] == original["error_code"]
            assert descendant["context"] == predecessor["context"]
            assert descendant["context"]["stage_id"] == "excavation"
            stage = next(item for item in (await client.get("/stages/summary")).json()["stages"]
                         if item["stage_id"] == "excavation")
            assert stage["latest_result"] is None
            assert stage["latest_lifecycle"]["run_id"] == str(successor)
            assert descendant["requested_classes"] == predecessor["requested_classes"]
            with store.engine.connect() as connection:
                runs = connection.execute(text("""SELECT id, request_context, policy_snapshot,
                    taxonomy_snapshot, requested_classes FROM analysis_runs WHERE id IN (:source, :successor)"""),
                    {"source": source, "successor": successor}).mappings().all()
                original_fields = next(dict(row) for row in runs if row["id"] == source)
                successor_fields = next(dict(row) for row in runs if row["id"] == successor)
                for field in ("request_context", "policy_snapshot", "taxonomy_snapshot", "requested_classes"):
                    assert successor_fields[field] == original_fields[field]
                manifests = {}
                for run_id in (source, successor):
                    manifests[run_id] = connection.execute(text("""SELECT i.ordinal, i.sha256, i.size, i.context,
                        a.key, a.media_type FROM run_inputs i JOIN artifact_metadata a ON a.id = i.artifact_id
                        WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).all()
                assert manifests[source] == manifests[successor]
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :id"), {"id": successor}).scalar_one() == 0
                assert connection.execute(text("SELECT count(*) FROM analysis_stages WHERE run_id = :id AND state = 'pending'"), {"id": successor}).scalar_one() == 6
                inherited = connection.execute(text("""SELECT a.id, a.source_artifact_id FROM artifact_metadata a
                    JOIN run_inputs i ON i.artifact_id = a.id WHERE i.run_id = :id"""), {"id": successor}).all()
            assert len(inherited) == (2 if series else 1) and all(item.source_artifact_id for item in inherited)
            assert (await client.get(f"/runs/{successor}/artifacts/{inherited[0].id}")).status_code == 200
            work = store.claim_ordinary(profile, 1, 30)
            assert work and work["id"] == successor
            await loop._execute(work, 1)
            completed = (await client.get(f"/runs/{successor}")).json()
            assert completed["state"] == "succeeded"
            assert completed["result_projection"]["outcome"] == "observations_only"
            assert (await client.get(f"/runs/{source}")).json()["stages"] == original["stages"]
            for state in ("queued", "running", "succeeded"):
                with store.engine.begin() as connection:
                    connection.execute(text("UPDATE analysis_runs SET state = :state WHERE id = :id"),
                                       {"state": state, "id": successor})
                assert (await client.post(f"/runs/{successor}/retry")).json()["code"] == "retry_ineligible"
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE analysis_runs SET state = 'failed' WHERE id = :id"), {"id": successor})
            third = (await client.post(f"/runs/{successor}/retry")).json()["run_id"]
            assert (await client.get(f"/runs/{third}")).json()["retry_predecessor_id"] == str(successor)
            assert (await client.post(f"/runs/{uuid.uuid4()}/retry")).status_code == 404
            admission_run = uuid.uuid4()
            with store.engine.begin() as connection:
                connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:id, 'failed', 'profile_admission')"),
                                   {"id": admission_run})
            assert (await client.post(f"/runs/{admission_run}/retry")).status_code == 404
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE analysis_runs SET state = 'failed' WHERE id = :id"), {"id": third})
                connection.execute(text("UPDATE profile_authorizations SET state = 'revoked' WHERE profile_id = :id"), {"id": profile})
            assert (await client.post(f"/runs/{third}/retry")).status_code == 503
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE profile_authorizations SET state = 'enabled' WHERE profile_id = :id"), {"id": profile})
                third_artifact = connection.execute(text("SELECT artifact_id FROM run_inputs WHERE run_id = :id AND ordinal = 0"),
                                                    {"id": uuid.UUID(third)}).scalar_one()
                connection.execute(text("UPDATE artifact_metadata SET sha256 = :hash WHERE id = :id"),
                                   {"hash": "0" * 64, "id": third_artifact})
            assert (await client.post(f"/runs/{third}/retry")).status_code == 409
            assert len((await client.get("/runs")).json()["runs"]) == 3
            with store.engine.begin() as connection:
                connection.execute(text("UPDATE artifact_metadata SET sha256 = (SELECT sha256 FROM run_inputs WHERE artifact_id = :id) WHERE id = :id"),
                                   {"id": third_artifact})
            entered, release = threading.Event(), threading.Event()
            verified_read = artifacts.read_verified

            def paused_read(*args):
                entered.set()
                assert release.wait(5)
                return verified_read(*args)

            monkeypatch.setattr(artifacts, "read_verified", paused_read)
            with ThreadPoolExecutor(max_workers=1) as pool:
                attempt = pool.submit(store.retry_ordinary, uuid.UUID(third), profile, 1, snapshot, artifacts)
                assert entered.wait(5)
                with store.engine.begin() as connection:
                    connection.execute(text("UPDATE analysis_runs SET error_code = 'changed_during_verification' WHERE id = :id"),
                                       {"id": uuid.UUID(third)})
                release.set()
                with pytest.raises(AdmissionStoreError, match="retry_source_unavailable"):
                    attempt.result(timeout=5)
            monkeypatch.setattr(artifacts, "read_verified", verified_read)
            with store.engine.begin() as connection:
                for _ in range(55):
                    connection.execute(text("INSERT INTO analysis_runs (id, state, purpose) VALUES (:id, 'queued', 'ordinary')"),
                                       {"id": uuid.uuid4()})
            first_page = (await client.get("/runs")).json()
            assert len(first_page["runs"]) == 50 and first_page["next_offset"] == 50
            second_page = (await client.get("/runs?offset=50")).json()
            assert len(second_page["runs"]) == 8 and second_page["next_offset"] is None
            assert {row["id"] for row in first_page["runs"]}.isdisjoint(row["id"] for row in second_page["runs"])
            assert (await client.get("/runs?offset=bad")).status_code == 400

    asyncio.run(scenario())
    store.close()


def jpeg_with_size(width, height, color):
    image = Image.new("RGB", (width, height), color)
    ImageDraw.Draw(image).rectangle((0, 0, 8, 8), fill=(220, 240, 250))
    output = io.BytesIO()
    image.save(output, format="JPEG")
    return output.getvalue()


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
                "runtime": {"per_image_timeout_seconds": 2, "batch_timeout_seconds": 600}}
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
    first, second, low_range = jpeg((12, 120, 220)), jpeg((33, 111, 222)), jpeg((0, 0, 0))
    small = jpeg_with_size(32, 48, (20, 40, 60))
    calls = 0
    observed_images = []

    def observed(*args):
        nonlocal calls
        image_bytes = args[2]
        observed_images.append(image_bytes)
        calls += 1
        with Image.open(io.BytesIO(image_bytes)) as image:
            image_size = list(image.size)
        return {"states": {"excavator": "detected" if calls % 2 else "not_detected_in_frame",
                           "dump_truck": "not_detected_in_frame"},
                "returned_model_identity": f"checkpoint-sha256:{'a' * 64}", "actual_device": "cpu",
                "latency_ms": 1.0, "peak_memory_bytes": 1024,
                "native": {"detections": ([{"label": "an excavator", "score": 0.8, "box": [1, 2, 3, 4]}]
                                          if calls % 2 else []),
                           "image_size": image_size}}

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
            checking, allow_check = threading.Event(), threading.Event()
            original_decode = executor._decode_image
            decoded = 0

            def pause_second_decode(image):
                nonlocal decoded
                decoded += 1
                if decoded == 2:
                    checking.set()
                    assert allow_check.wait(30)
                return original_decode(image)

            monkeypatch.setattr(executor, "_decode_image", pause_second_decode)
            work = store.claim_ordinary(profile, 1, 30)
            execution = asyncio.create_task(loop._execute(work, 1))
            try:
                assert await asyncio.wait_for(asyncio.to_thread(checking.wait, 5), 6)
                checking_run = (await client.get(f"/runs/{run}")).json()
                assert checking_run["state"] == "running"
                assert [stage["state"] for stage in checking_run["stages"][1:3]] == ["running", "pending"]
                with store.engine.connect() as connection:
                    assert connection.execute(text("SELECT state FROM analysis_stages WHERE run_id = :run ORDER BY ordinal"),
                                              {"run": run}).scalars().all()[1:3] == ["running", "pending"]
                    assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"),
                                              {"run": run}).scalar_one() == 0
                observing, allow_observation = threading.Event(), threading.Event()

                def pause_first_observation(*args):
                    observing.set()
                    assert allow_observation.wait(30)
                    return observed(*args)

                monkeypatch.setattr(executor, "_observe_bounded", pause_first_observation)
            finally:
                allow_check.set()
            try:
                assert await asyncio.wait_for(asyncio.to_thread(observing.wait, 5), 6)
                observing_run = (await client.get(f"/runs/{run}")).json()
                assert observing_run["state"] == "running"
                assert [stage["state"] for stage in observing_run["stages"][1:3]] == ["succeeded", "running"]
                with store.engine.connect() as connection:
                    assert connection.execute(text("SELECT state FROM analysis_stages WHERE run_id = :run ORDER BY ordinal"),
                                              {"run": run}).scalars().all()[1:3] == ["succeeded", "running"]
            finally:
                allow_observation.set()
            await execution
            monkeypatch.setattr(executor, "_decode_image", original_decode)
            monkeypatch.setattr(executor, "_observe_bounded", observed)
            done = (await client.get(f"/runs/{run}")).json()
            assert done["state"] == "succeeded" and done["outcome"] == "observations_only", done["error_code"]
            assert observed_images[:2] == [first, second]
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

            def assert_completed_invocations(run_id, expected_input_count):
                with store.engine.connect() as connection:
                    rows = connection.execute(text("""SELECT i.input_id AS run_input_id, i.sha256,
                        v.input_id AS invocation_input_id, v.input_sha256, v.state
                        FROM run_inputs i LEFT JOIN observer_invocations v
                        ON i.run_id = v.run_id AND i.input_id = v.input_id
                        WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).all()
                assert len(rows) == expected_input_count
                assert all(row.invocation_input_id == row.run_input_id and row.input_sha256 == row.sha256
                           and row.state == "completed" for row in rows)

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
            assert_completed_invocations(same_run, 2)

            observed_start = len(observed_images)
            small_series = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                             json=body(small, second))
            small_series_run = uuid.UUID(small_series.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            small_done = (await client.get(f"/runs/{small_series_run}")).json()
            assert small_done["state"] == "succeeded" and small_done["result_projection"]["series"]["usable_count"] == 2
            assert observed_images[observed_start:observed_start + 2] == [small, second]
            assert_completed_invocations(small_series_run, 2)

            observed_start = len(observed_images)
            mixed = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex}, json=body(first, low_range))
            mixed_run = uuid.UUID(mixed.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            result = (await client.get(f"/runs/{mixed_run}")).json()
            assert result["state"] == "succeeded" and result["outcome"] == "observations_only"
            assert observed_images[observed_start:observed_start + 2] == [first, low_range]
            assert result["result_projection"]["series"]["usable_count"] == 2
            assert_completed_invocations(mixed_run, 2)

            observed_start = len(observed_images)
            all_low_range = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                              json=body(low_range, low_range))
            all_low_range_run = uuid.UUID(all_low_range.json()["run_id"])
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            all_low_range_done = (await client.get(f"/runs/{all_low_range_run}")).json()
            assert all_low_range_done["state"] == "succeeded"
            assert all_low_range_done["result_projection"]["series"]["usable_count"] == 2
            assert observed_images[observed_start:observed_start + 2] == [low_range, low_range]
            assert_completed_invocations(all_low_range_run, 2)

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
            second_reads = 0

            def fail_second_frame(key, digest, size):
                nonlocal second_reads
                if key == work["frames"][1]["key"]:
                    second_reads += 1
                    if second_reads == 2:
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
            assert second_reads == 2
            assert [stage["state"] for stage in unreadable_result["stages"][1:]] == [
                "succeeded", "failed", "skipped", "skipped", "skipped"]
            assert unreadable_result["result_projection"] is None
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": unreadable_run}).scalar_one() == 0
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run AND state = 'completed'"),
                                          {"run": unreadable_run}).scalar_one() == 1
                assert connection.execute(text("SELECT state FROM analysis_stages WHERE run_id = :run ORDER BY ordinal"),
                                          {"run": unreadable_run}).scalars().all()[1:] == [
                                              "succeeded", "failed", "skipped", "skipped", "skipped"]

            monkeypatch.setattr(artifacts, "read_verified", original_read)
            preflight = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                          json=body(first, second))
            preflight_run = uuid.UUID(preflight.json()["run_id"])
            preflight_work = store.claim_ordinary(profile, 1, 30)

            def fail_preflight(key, digest, size):
                if key == preflight_work["frames"][1]["key"]:
                    raise RuntimeError("artifact_integrity_failed")
                return original_read(key, digest, size)

            monkeypatch.setattr(artifacts, "read_verified", fail_preflight)
            await loop._execute(preflight_work, 1)
            preflight_result = (await client.get(f"/runs/{preflight_run}")).json()
            assert preflight_result["state"] == "failed"
            assert preflight_result["error_code"] == "artifact_integrity_failed"
            assert [stage["state"] for stage in preflight_result["stages"][1:]] == [
                "failed", "skipped", "skipped", "skipped", "skipped"]
            assert preflight_result["observations"] == []
            assert preflight_result["result_projection"] is None
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"),
                                          {"run": preflight_run}).scalar_one() == 0
                assert connection.execute(text("SELECT state FROM analysis_stages WHERE run_id = :run ORDER BY ordinal"),
                                          {"run": preflight_run}).scalars().all()[1:] == [
                                              "failed", "skipped", "skipped", "skipped", "skipped"]
            monkeypatch.setattr(artifacts, "read_verified", original_read)

            snapshot["runtime"]["batch_timeout_seconds"] = 3
            clock = [0.0]
            monkeypatch.setattr(executor, "monotonic", lambda: clock[0])
            original_monotonic = postgres.monotonic
            monkeypatch.setattr(postgres, "monotonic", lambda: clock[0])
            allowances = []

            def consume_first_frame(*args):
                allowances.append(args[-1])
                if len(allowances) == 1:
                    clock[0] = 1.5
                return observed(*args)

            monkeypatch.setattr(executor, "_observe_bounded", consume_first_frame)
            within = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                       json=body(first, second))
            within_run = uuid.UUID(within.json()["run_id"])
            snapshot["runtime"]["batch_timeout_seconds"] = 600
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            snapshot["runtime"]["batch_timeout_seconds"] = 3
            within_result = (await client.get(f"/runs/{within_run}")).json()
            assert within_result["state"] == "succeeded"
            assert len(within_result["observations"]) == 4
            assert allowances == pytest.approx([2, 1.5])

            clock[0] = 0
            allowances.clear()
            timeout = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                        json=body(first, second))
            timeout_run = uuid.UUID(timeout.json()["run_id"])

            def exhaust_second_frame(*args):
                result = consume_first_frame(*args)
                if len(allowances) == 2:
                    clock[0] = 3
                return result

            monkeypatch.setattr(executor, "_observe_bounded", exhaust_second_frame)
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            timeout_result = (await client.get(f"/runs/{timeout_run}")).json()
            assert timeout_result["state"] == "failed" and timeout_result["error_code"] == "observer_timeout"
            assert timeout_result["outcome"] is None and timeout_result["result_projection"] is None
            assert len(timeout_result["observations"]) == 2
            assert allowances == pytest.approx([2, 1.5])

            monkeypatch.setattr(executor, "_observe_bounded", consume_first_frame)
            clock[0] = 0
            allowances.clear()
            native_publish = artifacts.publish_final
            published = 0

            def expire_during_publication(*args):
                nonlocal published
                result = native_publish(*args)
                published += 1
                if published == 2:
                    clock[0] = 3
                return result

            expired = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                        json=body(first, second))
            expired_run = uuid.UUID(expired.json()["run_id"])
            monkeypatch.setattr(artifacts, "publish_final", expire_during_publication)
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            expired_result = (await client.get(f"/runs/{expired_run}")).json()
            assert expired_result["state"] == "failed" and expired_result["error_code"] == "observer_timeout"
            assert expired_result["outcome"] is None and expired_result["result_projection"] is None
            assert len(expired_result["observations"]) == 2
            assert allowances == pytest.approx([2, 1.5])
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": expired_run}).scalar_one() == 0
            monkeypatch.setattr(artifacts, "publish_final", native_publish)

            clock[0] = 0
            allowances.clear()
            preflight = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                          json=body(first, second))
            preflight_run = uuid.UUID(preflight.json()["run_id"])
            preflight_work = store.claim_ordinary(profile, 1, 30)

            def expire_during_preflight(key, digest, size):
                image = original_read(key, digest, size)
                if key == preflight_work["frames"][1]["key"]:
                    clock[0] = 3
                return image

            monkeypatch.setattr(artifacts, "read_verified", expire_during_preflight)
            await loop._execute(preflight_work, 1)
            preflight_expired = (await client.get(f"/runs/{preflight_run}")).json()
            assert preflight_expired["state"] == "failed" and preflight_expired["error_code"] == "observer_timeout"
            assert preflight_expired["observations"] == [] and preflight_expired["result_projection"] is None
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": preflight_run}).scalar_one() == 0
            monkeypatch.setattr(artifacts, "read_verified", original_read)

            clock[0] = 0
            delayed = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                        json=body(first, second))
            delayed_run = uuid.UUID(delayed.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", observed)
            original_verified = store.publication_content_verified
            started, release, completed = threading.Event(), threading.Event(), threading.Event()

            def nearly_expired(*args):
                result = original_verified(*args)
                clock[0] = 2.95
                return result

            def delayed_publish(*args):
                started.set()
                assert release.wait(5)
                result = native_publish(*args)
                clock[0] = 3
                completed.set()
                return result

            monkeypatch.setattr(store, "publication_content_verified", nearly_expired)
            monkeypatch.setattr(artifacts, "publish_final", delayed_publish)
            execution = asyncio.create_task(loop._execute(store.claim_ordinary(profile, 1, 30), 1))
            try:
                assert await asyncio.to_thread(started.wait, 5)
                await asyncio.sleep(0.1)
                assert not execution.done()
                assert (await client.get(f"/runs/{delayed_run}")).json()["state"] == "running"
            finally:
                release.set()
                await execution
            delayed_result = (await client.get(f"/runs/{delayed_run}")).json()
            assert completed.is_set()
            assert delayed_result["state"] == "failed" and delayed_result["error_code"] == "observer_timeout"
            assert delayed_result["result_projection"] is None
            monkeypatch.setattr(store, "publication_content_verified", original_verified)
            monkeypatch.setattr(artifacts, "publish_final", native_publish)

            clock[0] = 0
            allowances.clear()
            final = await client.post("/runs/series", headers={"Idempotency-Key": uuid.uuid4().hex},
                                      json=body(first, second))
            final_run = uuid.UUID(final.json()["run_id"])
            monkeypatch.setattr(executor, "_observe_bounded", observed)
            completion_checks = 0

            def expire_in_completion():
                nonlocal completion_checks
                completion_checks += 1
                return 3 if completion_checks == 2 else 0

            monkeypatch.setattr(postgres, "monotonic", expire_in_completion)
            await loop._execute(store.claim_ordinary(profile, 1, 30), 1)
            final_expired = (await client.get(f"/runs/{final_run}")).json()
            assert completion_checks == 2
            assert final_expired["state"] == "failed" and final_expired["error_code"] == "observer_timeout"
            assert len(final_expired["observations"]) == 2 and final_expired["result_projection"] is None
            with store.engine.connect() as connection:
                assert connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :run"),
                                          {"run": final_run}).scalar_one() == 0
            monkeypatch.setattr(postgres, "monotonic", original_monotonic)
            snapshot["runtime"]["batch_timeout_seconds"] = 600

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

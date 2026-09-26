import asyncio
import base64
import hashlib
import json
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
                                 uuid.uuid4(), 1, {"kind":"deepseek"})
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
    return {"cloud_processing_consent": True, "intent": "observation_only", "scenario": "equipment_check",
            "observation_area": "north_gate", "period": "2026-09-23T12:00:00+03:00",
            "images_base64": [base64.b64encode(image).decode() for image in images]}


def test_series_order_is_bound_to_idempotency_key(isolated_admission_database, integration):
    from app.application.deepseek_runtime import provision
    config, _, artifacts = integration
    store = PostgresStore(isolated_admission_database)
    profile = provision(store, 'mock-folder')
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, artifacts
    app.state.claim_loop = SimpleNamespace(runtime_binding=(profile, 1))
    first, second = jpeg((11, 23, 37)), jpeg((53, 71, 89))
    key = uuid.uuid4().hex

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            submitted = await client.post('/runs/series', headers={'Idempotency-Key':key}, json=body(first, second))
            assert submitted.status_code == 202
            run_id = submitted.json()['run_id']
            duplicate = await client.post('/runs/series', headers={'Idempotency-Key':key}, json=body(first, second))
            assert duplicate.status_code == 202 and duplicate.json()['run_id'] == run_id
            reversed_frames = await client.post('/runs/series', headers={'Idempotency-Key':key}, json=body(second, first))
            assert reversed_frames.status_code == 409
            assert reversed_frames.json() == {'code':'idempotency_key_conflict'}
            run = (await client.get(f'/runs/{run_id}')).json()
            assert [frame['ordinal'] for frame in run['inputs']] == [0, 1]
            assert [frame['sha256'] for frame in run['inputs']] == [hashlib.sha256(image).hexdigest() for image in (first, second)]
            with store.engine.connect() as connection:
                assert connection.execute(text('SELECT count(*) FROM analysis_runs')).scalar_one() == 1
                assert connection.execute(text('SELECT count(*) FROM deepseek_calls')).scalar_one() == 0
    try:
        asyncio.run(scenario())
    finally:
        store.close()


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
def test_pre_provider_retry_is_linear_and_keeps_source(isolated_admission_database, integration, monkeypatch, series):
    config, _, _ = integration
    config = Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                    config.s3_access_key, config.s3_secret_key)
    store, artifacts = PostgresStore(isolated_admission_database), ArtifactStore(config)
    from app.application.deepseek_runtime import provision
    profile = provision(store, 'mock-folder')
    snapshot, _ = store.require_authorized(profile)
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'mock-only-never-sent')
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, artifacts
    loop = executor.ClaimLoop()
    loop.runtime_binding = profile, 1
    loop.store, loop.artifacts = store, artifacts
    app.state.claim_loop = loop
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

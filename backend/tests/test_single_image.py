import asyncio
import base64
import io
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

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


def png(color) -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (96, 96), color).save(output, format="PNG")
    return output.getvalue()


def request_body(image: bytes, classes=None) -> dict:
    body = {"cloud_processing_consent": True, "intent": "observation_only", "scenario": "equipment_check", "observation_area": "north_gate",
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
    from app.application.deepseek_runtime import provision
    profile = provision(store, 'mock-folder')
    snapshot, _ = store.require_authorized(profile)
    expired = uuid.uuid4()
    with store.engine.begin() as connection:
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
                loop.start(ready, artifacts)
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
    assert validate_request(request_body(png((0, 0, 0))))[0] == png((0, 0, 0))
    with pytest.raises(SubmissionError, match="rule_not_applicable"):
        validate_request(request_body(png((0, 0, 0))) | {"intent": "rule_evaluation", "stage": "excavation"})


def test_mixed_format_submission_passes_each_media_type_to_publication():
    originals = [jpeg((1, 2, 3)), png((4, 5, 6))]
    body = {key: value for key, value in request_body(originals[0]).items() if key != "image_base64"}
    body["images_base64"] = [base64.b64encode(image).decode() for image in originals]
    published = []

    class Store:
        def begin_submission(self, key, request_hash, media_type):
            assert media_type == "image/jpeg"
            return "created", None, uuid.uuid4(), None

        def create_submission_intent(self, key, media_type):
            assert media_type == "image/png"
            return uuid.uuid4()

        def publication_content_verified(self, *args):
            pass

        def publication_object_published(self, *args):
            pass

        def commit_series_submission(self, key, profile, revision, snapshot, context, requested, manifest, **kwargs):
            assert len(manifest) == 2
            return uuid.uuid4()

    class Artifacts:
        def upload_temporary(self, intent, image, media_type):
            published.append((image, media_type))
            return "temporary", uuid.uuid4().hex, len(image)

        def publish_final(self, intent, image, media_type, digest, size):
            assert (image, media_type) in published

        def read_verified(self, key, digest, size):
            pass

    assert submission.submit_series(Store(), Artifacts(), "mixed", body, uuid.uuid4(), 1, {"kind":"deepseek"})[0] == "queued"
    assert published == list(zip(originals, ("image/jpeg", "image/png")))


def test_mixed_image_formats_preserve_originals_and_retry(isolated_admission_database, integration):
    config, _, _ = integration
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(Config(isolated_admission_database, config.s3_endpoint, config.s3_bucket,
                                     config.s3_access_key, config.s3_secret_key))
    from app.application.deepseek_runtime import provision
    profile = provision(store, 'test-folder')
    profile_snapshot, _ = store.require_authorized(profile)
    project, zone = uuid.uuid4(), uuid.uuid4()
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO site_projects (id,name,timezone) VALUES (:id,'Retry workspace','UTC')"), {'id': project})
        connection.execute(text("INSERT INTO site_zones (id,project_id,name) VALUES (:id,:project,'Main')"), {'id': zone, 'project': project})
    originals = [jpeg((1, 2, 3)), png((4, 5, 6))]
    body = {key: value for key, value in request_body(originals[0]).items() if key != "image_base64"}
    body["images_base64"] = [base64.b64encode(image).decode() for image in originals]
    body.update(project_id=str(project), zone_id=str(zone),
                capture_times=['2026-09-26T12:00:00+03:00', '2026-09-26T12:01:00+03:00'])
    try:
        _, run_id = submission.submit_series(store, artifacts, uuid.uuid4().hex, body, profile, 1, profile_snapshot)
        with store.engine.connect() as connection:
            rows = connection.execute(text("""SELECT a.key, a.sha256, a.size, a.media_type
                FROM run_inputs i JOIN artifact_metadata a ON a.id = i.artifact_id
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).all()
        assert [row.media_type for row in rows] == ["image/jpeg", "image/png"]
        assert [artifacts.read_verified(row.key, row.sha256, row.size) for row in rows] == originals
        with store.engine.begin() as connection:
            connection.execute(text("UPDATE analysis_runs SET state = 'failed' WHERE id = :run"), {"run": run_id})
        retried = store.retry_ordinary(run_id, profile, 1, profile_snapshot, artifacts)
        with store.engine.connect() as connection:
            retry_types = connection.execute(text("""SELECT a.media_type FROM run_inputs i
                JOIN artifact_metadata a ON a.id = i.artifact_id
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": retried}).scalars().all()
        assert retry_types == ["image/jpeg", "image/png"]
        original, successor = store.read_ordinary(run_id), store.read_ordinary(retried)
        assert successor['project_id'] == original['project_id'] == str(project)
        assert successor['zone_id'] == original['zone_id'] == str(zone)
        assert successor['context'] == original['context']
        assert successor['context']['capture_times'] == body['capture_times']
        assert successor['plan_binding'] is None
    finally:
        store.close()


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
    assert submission.submit(Store(), None, "same-key", request_body(jpeg((0, 0, 0))), uuid.uuid4(), 1, {"kind":"deepseek"}) == ("queued", run)


def test_http_submission_and_guarded_execution(isolated_admission_database, integration, monkeypatch):
    from app.application.deepseek_runtime import provision
    from app.profiles import deepseek
    from test_deepseek import annotation, assessment, response
    config, _, _ = integration
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(config)
    profile = provision(store, 'mock-folder')
    monkeypatch.setenv('YANDEX_AI_STUDIO_API_KEY', 'mock-only-never-sent')
    app = create_app()
    app.state.readiness.ready.set()
    app.state.store, app.state.artifacts = store, artifacts
    loop = executor.ClaimLoop()
    loop.store, loop.artifacts, loop.runtime_binding = store, artifacts, (profile, 1)
    app.state.claim_loop = loop
    calls = []
    observed = annotation()
    observed['objects'][0].update(type_ru='экскаватор', type_en='excavator', catalog_class='excavator')

    def provider(request, timeout):
        payload = json.loads(request.data)
        calls.append(payload['text']['format']['name'])
        return response(observed if calls[-1] == 'frame' else assessment())

    monkeypatch.setattr(deepseek, '_read_json', provider)
    image = jpeg((12, 120, 220))
    body = request_body(image, ['excavator', 'dump_truck', 'tower_crane'])

    async def scenario():
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            async def oversized():
                yield b'{'
                yield b'x' * MAX_HTTP_BODY_BYTES
            too_large = await client.post('/runs/single-image', content=oversized())
            assert too_large.status_code == 400 and too_large.json() == {'code':'invalid_image_file'}
            invalid = await client.post('/runs/single-image', headers={'Idempotency-Key':'invalid'},
                                        json=request_body(b'bad'))
            assert invalid.status_code == 400 and invalid.json() == {'code':'invalid_image_file'}
            assert calls == []
            with store.engine.connect() as connection:
                assert connection.execute(text('SELECT count(*) FROM submission_requests')).scalar_one() == 0
            key = uuid.uuid4().hex
            first, duplicate = await asyncio.gather(*(
                client.post('/runs/single-image', headers={'Idempotency-Key':key}, json=body) for _ in range(2)))
            assert first.status_code == duplicate.status_code == 202
            run = uuid.UUID(first.json()['run_id'])
            assert duplicate.json()['run_id'] == str(run)
            conflict = await client.post('/runs/single-image', headers={'Idempotency-Key':key},
                                         json=body | {'observation_area':'south_gate'})
            assert conflict.status_code == 409 and conflict.json() == {'code':'idempotency_key_conflict'}
            assert (await client.get(f'/runs/{run}')).json()['state'] == 'queued'
            work = store.claim_ordinary(profile, 1, 30)
            assert work['id'] == run
            await loop._execute(work, 1)
            done = (await client.get(f'/runs/{run}')).json()
            assert done['state'] == 'succeeded', done['error_code']
            assert calls == ['frame','assessment']
            assert len(done['ai_evidence']) == 2 and done['ai_assessment']
            assert {item['class_name']:item['state'] for item in done['observations']} == {
                'excavator':'detected','dump_truck':'not_detected_in_frame','tower_crane':'not_analyzed'}
            assert all(item['source_artifact_id'] for item in done['observations'])
            artifact = done['inputs'][0]
            source = await client.get(f"/runs/{run}/artifacts/{artifact['artifact_id']}")
            assert source.status_code == 200 and source.content == image
            upload = artifacts.upload_temporary
            monkeypatch.setattr(artifacts, 'upload_temporary', lambda *_: (_ for _ in ()).throw(RuntimeError('upload_failed')))
            bad_key = uuid.uuid4().hex
            bad_first = await client.post('/runs/single-image',headers={'Idempotency-Key':bad_key},json=body)
            bad_repeat = await client.post('/runs/single-image',headers={'Idempotency-Key':bad_key},json=body)
            assert bad_first.status_code == bad_repeat.status_code == 503
            assert bad_first.json() == bad_repeat.json() == {'code':'submission_publication_failed'}
            assert calls == ['frame','assessment']
            monkeypatch.setattr(artifacts, 'upload_temporary', upload)
    try:
        asyncio.run(scenario())
    finally:
        store.close()

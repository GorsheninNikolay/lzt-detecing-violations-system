import asyncio
import hashlib
import http.client
import os
import threading
import uuid
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from httpx import ASGITransport, AsyncClient
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app.adapters.artifacts import ArtifactGateError, ArtifactStore
from app.adapters.postgres import DatabaseGateError, LOCK_ID, PostgresStore, ReconciliationGateError, RecoveryGateError
from app.config import Config, ConfigurationError
from app.main import create_app


MIGRATIONS = str(Path(__file__).resolve().parents[1] / "migrations")


def test_non_postgresql_rejected_before_adapters(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///unwanted.db")
    with pytest.raises(ConfigurationError, match="invalid_database_dialect"):
        Config.from_env()


def test_live_while_readiness_pending():
    async def check():
        app = create_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/health/live")).json() == {"live": True}
            response = await client.get("/health/ready")
            assert response.status_code == 503
            assert response.json() == {"ready": False, "code": "startup_pending"}

    asyncio.run(check())


@pytest.mark.parametrize("code", ["NoSuchKey", "404", "NotFound"])
def test_reconciliation_inspector_distinguishes_missing_object(code):
    artifact = object.__new__(ArtifactStore)
    artifact.bucket = "test"
    error = ClientError({"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": 404}}, "GetObject")
    artifact.client = SimpleNamespace(
        get_object=lambda **_: (_ for _ in ()).throw(error), head_bucket=lambda **_: {})
    assert artifact.inspect_reconciliation("tmp/missing") == ("missing", None)
    artifact.client.head_bucket = lambda **_: (_ for _ in ()).throw(error)
    if code != "NoSuchKey":
        with pytest.raises(ArtifactGateError, match="artifact_read_unavailable"):
            artifact.inspect_reconciliation("tmp/missing")


@pytest.fixture(scope="module")
def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set TEST_DATABASE_URL to an isolated migrated PostgreSQL database")
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg")
    app_url = os.getenv("DATABASE_URL")
    if app_url:
        test_target, app_target = make_url(url), make_url(app_url)
        if (test_target.host, test_target.port, test_target.database) == (app_target.host, app_target.port, app_target.database):
            pytest.fail("TEST_DATABASE_URL must target a different database than DATABASE_URL")
    store = PostgresStore(url)
    with store.engine.connect() as connection:
        actual = MigrationContext.configure(connection).get_current_revision()
    if actual != ScriptDirectory(MIGRATIONS).get_current_head():
        store.close()
        pytest.fail("Migrate the isolated test database with DATABASE_URL=$TEST_DATABASE_URL uv run alembic upgrade head")
    yield store
    store.close()


@pytest.fixture(scope="module")
def integration(database):
    url = os.getenv("TEST_DATABASE_URL")
    bucket = os.getenv("TEST_S3_BUCKET")
    endpoint = os.getenv("S3_ENDPOINT")
    access = os.getenv("S3_ACCESS_KEY")
    secret = os.getenv("S3_SECRET_KEY")
    if not all((url, bucket, endpoint, access, secret)):
        pytest.fail("Set TEST_S3_BUCKET and S3_ENDPOINT/S3_ACCESS_KEY/S3_SECRET_KEY for integration tests")
    if bucket == os.getenv("S3_BUCKET"):
        pytest.fail("TEST_S3_BUCKET must differ from the application S3_BUCKET")
    config = Config(url, endpoint, bucket, access, secret)
    artifacts = ArtifactStore(config)
    try:
        artifacts.client.head_bucket(Bucket=bucket)
    except ClientError as exc:
        if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
            raise
        artifacts.client.create_bucket(Bucket=bucket)
    yield config, database, artifacts


def test_database_head_smoke_and_reconciliation(database):
    store = database
    store.check_head_and_smoke(MIGRATIONS)
    with store.engine.connect() as connection:
        before = connection.execute(text("SELECT count(*) FROM startup_smoke")).scalar_one()
    store.reconcile()
    store.reconcile()
    with store.engine.connect() as connection:
        after = connection.execute(text("SELECT count(*) FROM startup_smoke")).scalar_one()
        passes = connection.execute(text("SELECT count(*) FROM reconciliation_runs WHERE status = 'succeeded' AND intent_count = 0")).scalar_one()
    assert before == after
    assert passes >= 2


def test_database_migration_mismatch_and_smoke_failure(database):
    store = database
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'wrong_head'"))
    try:
        with pytest.raises(DatabaseGateError, match="database_migration_mismatch"):
            store.check_head_and_smoke(MIGRATIONS)
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": ScriptDirectory(MIGRATIONS).get_current_head()})
    with store.engine.begin() as connection:
        connection.execute(text("ALTER TABLE startup_smoke RENAME TO startup_smoke_hidden"))
    try:
        with pytest.raises(DatabaseGateError, match="database_smoke_failed"):
            store.check_head_and_smoke(MIGRATIONS)
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("ALTER TABLE startup_smoke_hidden RENAME TO startup_smoke"))


def test_reconciliation_lock_fences_pass(database):
    store = database
    with store.engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID})
        try:
            with pytest.raises(ReconciliationGateError, match="reconciliation_lock_unavailable"):
                store.reconcile()
        finally:
            transaction.rollback()


def test_reconciliation_quarantines_interrupted_states_without_touching_bytes(integration):
    config, store, artifacts = integration
    run_ids = [uuid.uuid4() for _ in range(3)]
    with store.engine.begin() as connection:
        for run_id in run_ids:
            connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    intents = []
    keys = []
    try:
        for index, run_id in enumerate(run_ids):
            intent = store.create_publication_intent(run_id, "application/json", uuid.uuid4().hex)
            payload = f"interrupted-{intent}".encode()
            temporary, digest, size = artifacts.upload_temporary(intent, payload, "application/json")
            keys.append(temporary)
            if index:
                store.publication_content_verified(intent, digest, size, f"sha256/{digest}")
            if index == 2:
                final = artifacts.publish_final(intent, payload, "application/json", digest, size)
                keys.append(final)
                store.publication_object_published(intent)
            intents.append(intent)
        original = {key: artifacts.client.get_object(Bucket=config.s3_bucket, Key=key)["Body"].read() for key in keys}
        store.reconcile(artifacts)
        store.reconcile(artifacts)
        with store.engine.connect() as connection:
            states = connection.execute(text("SELECT state FROM publication_intents WHERE id = ANY(:ids)"), {"ids": intents}).scalars().all()
            last = connection.execute(text("SELECT intent_count, status FROM reconciliation_runs ORDER BY id DESC LIMIT 2")).all()
        assert states == ["quarantined"] * 3
        assert last[0] == (0, "succeeded")
        assert last[1].status == "succeeded" and last[1].intent_count >= 3
        assert {key: artifacts.client.get_object(Bucket=config.s3_bucket, Key=key)["Body"].read() for key in keys} == original
    finally:
        for key in keys:
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=key)
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id = ANY(:ids)"), {"ids": intents})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": run_ids})


@pytest.mark.parametrize("final_state,intent_state", [
    ("missing", "object_published"),
    ("mismatched", "object_published"),
    ("mismatched", "content_verified"),
])
def test_reconciliation_integrity_failure_blocks_gate(integration, monkeypatch, final_state, intent_state):
    config, store, artifacts = integration
    run_id = uuid.uuid4()
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    intent = store.create_publication_intent(run_id, "application/json", uuid.uuid4().hex)
    payload = uuid.uuid4().bytes
    temporary, digest, size = artifacts.upload_temporary(intent, payload, "application/json")
    final = f"sha256/{digest}"
    store.publication_content_verified(intent, digest, size, final)
    if final_state == "mismatched":
        artifacts.client.put_object(Bucket=config.s3_bucket, Key=final, Body=b"wrong",
                                    Metadata={"publication_intent_id": str(intent)})
    if intent_state == "object_published":
        store.publication_object_published(intent)
    try:
        with pytest.raises(ReconciliationGateError, match="reconciliation_integrity_failed"):
            store.reconcile(artifacts)
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"), {"id": intent}).scalar_one() == "failed_integrity"
            assert connection.execute(text("SELECT count(*) FROM artifact_metadata WHERE intent_id = :id"),
                                      {"id": intent}).scalar_one() == 0
            assert connection.execute(text("SELECT status, error_code FROM reconciliation_runs ORDER BY id DESC LIMIT 1")).one() == ("failed", "reconciliation_integrity_failed")
        set_service_env(monkeypatch, config)
        assert_service_gate("reconciliation_integrity_failed")
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT status, error_code FROM reconciliation_runs ORDER BY id DESC LIMIT 1")).one() == ("failed", "reconciliation_integrity_failed")
    finally:
        for key in (temporary, final):
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=key)
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id = :id"), {"id": intent})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = :id"), {"id": run_id})


def test_reconciliation_rejects_wrong_temporary_creator(integration, monkeypatch):
    config, store, artifacts = integration
    run_id = uuid.uuid4()
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    intent = store.create_publication_intent(run_id, "application/json", uuid.uuid4().hex)
    payload = uuid.uuid4().bytes
    digest = hashlib.sha256(payload).hexdigest()
    temporary = f"tmp/{intent}"
    artifacts.client.put_object(Bucket=config.s3_bucket, Key=temporary, Body=payload,
                                Metadata={"publication_intent_id": str(uuid.uuid4())})
    store.publication_content_verified(intent, digest, len(payload), f"sha256/{digest}")
    try:
        with pytest.raises(ReconciliationGateError, match="reconciliation_integrity_failed"):
            store.reconcile(artifacts)
        set_service_env(monkeypatch, config)
        assert_service_gate("reconciliation_integrity_failed")
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"),
                                      {"id": intent}).scalar_one() == "failed_integrity"
            assert connection.execute(text("SELECT status, error_code FROM reconciliation_runs ORDER BY id DESC LIMIT 1")).one() == ("failed", "reconciliation_integrity_failed")
    finally:
        artifacts.client.delete_object(Bucket=config.s3_bucket, Key=temporary)
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id = :id"), {"id": intent})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = :id"), {"id": run_id})


def test_reconciliation_s3_outage_blocks_readiness(integration, monkeypatch):
    config, store, _ = integration
    run_id = uuid.uuid4()
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    intent = store.create_publication_intent(run_id, "application/json", uuid.uuid4().hex)
    try:
        set_service_env(monkeypatch, config)
        monkeypatch.setattr(ArtifactStore, "inspect_reconciliation",
                            lambda *_args, **_kwargs: (_ for _ in ()).throw(ArtifactGateError("artifact_read_unavailable")))
        assert_service_gate("reconciliation_artifact_unavailable")
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM publication_intents WHERE id = :id"), {"id": intent}).scalar_one() == "pending_upload"
            assert connection.execute(text("SELECT status, error_code FROM reconciliation_runs ORDER BY id DESC LIMIT 1")).one() == ("failed", "reconciliation_artifact_unavailable")
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id = :id"), {"id": intent})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = :id"), {"id": run_id})


def test_duplicate_content_keeps_first_creator(integration):
    config, store, artifacts = integration
    run_ids = [uuid.uuid4(), uuid.uuid4()]
    with store.engine.begin() as connection:
        for run_id in run_ids:
            connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    intents = []
    payload = uuid.uuid4().bytes
    digest = hashlib.sha256(payload).hexdigest()
    final = f"sha256/{digest}"
    try:
        for run_id in run_ids:
            intent = store.create_publication_intent(run_id, "application/octet-stream", uuid.uuid4().hex)
            artifacts.upload_temporary(intent, payload, "application/octet-stream")
            store.publication_content_verified(intent, digest, len(payload), final)
            assert artifacts.publish_final(intent, payload, "application/octet-stream", digest, len(payload)) == final
            store.publication_object_published(intent)
            intents.append(intent)
        before = artifacts.client.head_object(Bucket=config.s3_bucket, Key=final)["Metadata"]
        assert before["publication_intent_id"] == str(intents[0])
        store.reconcile(artifacts)
        after = artifacts.client.head_object(Bucket=config.s3_bucket, Key=final)["Metadata"]
        assert after == before
        with store.engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM artifact_metadata WHERE intent_id = ANY(:ids)"),
                                      {"ids": intents}).scalar_one() == 0
    finally:
        for intent in intents:
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=f"tmp/{intent}")
        artifacts.client.delete_object(Bucket=config.s3_bucket, Key=final)
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id = ANY(:ids)"), {"ids": intents})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": run_ids})


def test_reconciliation_attaches_verified_deduplicated_reference(integration):
    config, store, artifacts = integration
    creator_run, attached_run = uuid.uuid4(), uuid.uuid4()
    with store.engine.begin() as connection:
        for run_id in (creator_run, attached_run):
            connection.execute(text("INSERT INTO analysis_runs (id, state) VALUES (:id, 'failed')"), {"id": run_id})
    payload = uuid.uuid4().bytes
    digest = hashlib.sha256(payload).hexdigest()
    final = f"sha256/{digest}"
    creator = store.create_publication_intent(creator_run, "application/octet-stream", uuid.uuid4().hex)
    later = store.create_publication_intent(attached_run, "application/octet-stream", uuid.uuid4().hex)
    artifact_id = uuid.uuid4()
    try:
        for intent in (creator, later):
            artifacts.upload_temporary(intent, payload, "application/octet-stream")
            store.publication_content_verified(intent, digest, len(payload), final)
            artifacts.publish_final(intent, payload, "application/octet-stream", digest, len(payload))
            store.publication_object_published(intent)
        with store.engine.begin() as connection:
            connection.execute(text("""INSERT INTO artifact_metadata
                (id, run_id, intent_id, key, sha256, size, media_type)
                VALUES (:id, :run, :intent, :key, :hash, :size, 'application/octet-stream')"""),
                {"id": artifact_id, "run": attached_run, "intent": later, "key": final,
                 "hash": digest, "size": len(payload)})
        store.reconcile(artifacts)
        with store.engine.connect() as connection:
            states = dict(connection.execute(text("SELECT id, state FROM publication_intents WHERE id IN (:creator, :later)"),
                                             {"creator": creator, "later": later}).all())
        assert states == {creator: "quarantined", later: "referenced"}
        assert artifacts.client.head_object(Bucket=config.s3_bucket, Key=final)["Metadata"]["publication_intent_id"] == str(creator)
    finally:
        for intent in (creator, later):
            artifacts.client.delete_object(Bucket=config.s3_bucket, Key=f"tmp/{intent}")
        artifacts.client.delete_object(Bucket=config.s3_bucket, Key=final)
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM artifact_metadata WHERE id = :id"), {"id": artifact_id})
            connection.execute(text("DELETE FROM publication_intents WHERE id IN (:creator, :later)"),
                               {"creator": creator, "later": later})
            connection.execute(text("DELETE FROM analysis_runs WHERE id IN (:creator, :later)"),
                               {"creator": creator_run, "later": attached_run})


def test_reconciliation_preserves_live_owner_before_recovery(integration):
    _, store, artifacts = integration
    live, expired = uuid.uuid4(), uuid.uuid4()
    with store.engine.begin() as connection:
        connection.execute(text("""INSERT INTO analysis_runs (id, state, lease_owner, lease_expires_at)
            VALUES (:live, 'running', 'live-owner', clock_timestamp() + interval '1 hour'),
                   (:expired, 'running', 'expired-owner', clock_timestamp() - interval '1 hour')"""),
            {"live": live, "expired": expired})
    live_intent = store.create_publication_intent(live, "application/json", uuid.uuid4().hex)
    expired_intent = store.create_publication_intent(expired, "application/json", uuid.uuid4().hex)
    try:
        store.reconcile(artifacts)
        store.recover()
        with store.engine.connect() as connection:
            runs = {row.id: (row.state, row.lease_owner) for row in connection.execute(text(
                "SELECT id, state, lease_owner FROM analysis_runs WHERE id IN (:live, :expired)"),
                {"live": live, "expired": expired})}
            intents = dict(connection.execute(text("SELECT id, state FROM publication_intents WHERE id IN (:live, :expired)"),
                                              {"live": live_intent, "expired": expired_intent}).all())
        assert runs == {live: ("running", "live-owner"), expired: ("failed", None)}
        assert intents == {live_intent: "pending_upload", expired_intent: "quarantined"}
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM publication_intents WHERE id IN (:live, :expired)"),
                               {"live": live_intent, "expired": expired_intent})
            connection.execute(text("DELETE FROM analysis_runs WHERE id IN (:live, :expired)"),
                               {"live": live, "expired": expired})


def test_guarded_recovery(database):
    store = database
    queued, active, expired, unknown = (uuid.uuid4() for _ in range(4))
    with store.engine.begin() as connection:
        connection.execute(text("INSERT INTO analysis_runs (id, state, lease_owner, lease_expires_at) VALUES (:queued, 'queued', NULL, NULL), (:active, 'running', 'owner', clock_timestamp() + interval '1 hour'), (:expired, 'running', 'owner', clock_timestamp() - interval '1 hour'), (:unknown, 'running', 'owner', NULL)"), {"queued": queued, "active": active, "expired": expired, "unknown": unknown})
        connection.execute(text("INSERT INTO analysis_stages (run_id, ordinal, state) VALUES (:expired, 0, 'running'), (:expired, 1, 'pending')"), {"expired": expired})
    try:
        with pytest.raises(RecoveryGateError, match="recovery_unknown_ownership"):
            store.recover()
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM analysis_runs WHERE id = :unknown"), {"unknown": unknown})
        with store.engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SELECT id FROM analysis_runs WHERE id = :id FOR UPDATE"), {"id": active})
            try:
                store.recover()
            finally:
                transaction.rollback()
        with store.engine.connect() as connection:
            rows = {row.id: (row.state, row.lease_owner) for row in connection.execute(
                text("SELECT id, state, lease_owner FROM analysis_runs WHERE id IN (:queued, :active, :expired)"),
                {"queued": queued, "active": active, "expired": expired})}
            stages = connection.execute(text("SELECT state, reason FROM analysis_stages WHERE run_id = :expired ORDER BY ordinal"), {"expired": expired}).all()
        assert rows == {queued: ("queued", None), active: ("running", "owner"), expired: ("failed", None)}
        assert stages == [("failed", "executor_interrupted"), ("skipped", "dependency_failed")]
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("DELETE FROM analysis_stages WHERE run_id = :expired"), {"expired": expired})
            connection.execute(text("DELETE FROM analysis_runs WHERE id IN (:queued, :active, :expired, :unknown)"),
                               {"queued": queued, "active": active, "expired": expired, "unknown": unknown})


def test_artifact_probe_success_and_missing_bucket(integration):
    config, _, artifacts = integration
    artifacts.probe()
    listing = artifacts.client.list_objects_v2(Bucket=config.s3_bucket, Prefix="health/")
    assert listing.get("KeyCount", 0) == 0
    missing = Config(config.database_url, config.s3_endpoint, f"missing-{uuid.uuid4().hex}", config.s3_access_key, config.s3_secret_key)
    with pytest.raises(ArtifactGateError, match="artifact_gate_failed"):
        ArtifactStore(missing).probe()


def test_versioned_artifact_probe_removes_versions(integration):
    config, _, artifacts = integration
    bucket = f"health-versioned-{uuid.uuid4().hex[:16]}"
    client = artifacts.client
    client.create_bucket(Bucket=bucket)
    client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
    try:
        versioned = Config(config.database_url, config.s3_endpoint, bucket, config.s3_access_key, config.s3_secret_key)
        ArtifactStore(versioned).probe()
        assert not health_versions(client, bucket)

        with failing_s3_proxy(config.s3_endpoint, "PUT_AFTER_COMMIT") as endpoint:
            faulty = Config(config.database_url, endpoint, bucket, config.s3_access_key, config.s3_secret_key)
            with pytest.raises(ArtifactGateError, match="artifact_gate_failed"):
                ArtifactStore(faulty).probe()
        assert not health_versions(client, bucket)

        with failing_s3_proxy(config.s3_endpoint, "DELETE") as endpoint:
            faulty = Config(config.database_url, endpoint, bucket, config.s3_access_key, config.s3_secret_key)
            with pytest.raises(ArtifactGateError, match="artifact_gate_failed"):
                ArtifactStore(faulty).probe()
        assert health_versions(client, bucket)
    finally:
        for item in health_versions(client, bucket):
            client.delete_object(Bucket=bucket, Key=item["Key"], VersionId=item["VersionId"])
        client.delete_bucket(Bucket=bucket)


def health_versions(client, bucket):
    page = client.list_object_versions(Bucket=bucket, Prefix="health/")
    return page.get("Versions", []) + page.get("DeleteMarkers", [])


@pytest.mark.parametrize("fault", ["PUT", "PUT_AFTER_COMMIT", "HEAD", "GET", "DELETE", "DELETE_404", "CORRUPT_GET"])
def test_artifact_verification_and_cleanup_failures(integration, fault):
    config, _, artifacts = integration
    with failing_s3_proxy(config.s3_endpoint, fault) as endpoint:
        faulty = ArtifactStore(Config(config.database_url, endpoint, config.s3_bucket, config.s3_access_key, config.s3_secret_key))
        with pytest.raises(ArtifactGateError, match="artifact_gate_failed"):
            faulty.probe()
    if fault == "PUT_AFTER_COMMIT":
        assert artifacts.client.list_objects_v2(Bucket=config.s3_bucket, Prefix="health/").get("KeyCount", 0) == 0
    for item in artifacts.client.list_objects_v2(Bucket=config.s3_bucket, Prefix="health/").get("Contents", []):
        artifacts.client.delete_object(Bucket=config.s3_bucket, Key=item["Key"])


@contextmanager
def failing_s3_proxy(endpoint: str, fault: str):
    upstream = urlsplit(endpoint)

    class Handler(BaseHTTPRequestHandler):
        def do_PUT(self):
            self.forward()

        def do_HEAD(self):
            self.forward()

        def do_GET(self):
            self.forward()

        def do_DELETE(self):
            self.forward()

        def forward(self):
            if "/health/" in self.path and (self.command == fault or (self.command == "DELETE" and fault == "DELETE_404")):
                self.send_response(404 if fault == "DELETE_404" else 503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else None
            connection = http.client.HTTPConnection(upstream.hostname, upstream.port)
            try:
                connection.request(self.command, self.path, body=body, headers=dict(self.headers))
                response = connection.getresponse()
                content = response.read()
                if fault == "PUT_AFTER_COMMIT" and self.command == "PUT" and "/health/" in self.path:
                    self.send_response(503)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if fault == "CORRUPT_GET" and self.command == "GET" and "/health/" in self.path:
                    content = bytes(byte ^ 1 for byte in content)
                self.send_response(response.status)
                for name, value in response.getheaders():
                    if name.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(name, value)
                self.end_headers()
                self.wfile.write(content)
            finally:
                connection.close()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_ready_health(integration, monkeypatch):
    config, _, _ = integration
    set_service_env(monkeypatch, config)

    async def check():
        app = create_app()
        assert app.state.readiness.code == "startup_pending"
        assert not app.state.readiness.ready.is_set()
        async with app.router.lifespan_context(app):
            await app.state.startup_task
            assert app.state.readiness.ready.is_set()
            assert app.state.readiness.code == "ready"
            assert app.state.claim_loop.task is not None
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get("/health/live")).json() == {"live": True}
                assert (await client.get("/health/ready")).json() == {"ready": True, "code": "ready"}
                app.state.claim_loop.task.cancel()
                try:
                    await app.state.claim_loop.task
                except asyncio.CancelledError:
                    pass
                await asyncio.sleep(0)
                response = await client.get("/health/ready")
                assert response.status_code == 503
                assert response.json() == {"ready": False, "code": "claim_loop_failed"}

    asyncio.run(check())


def test_database_mismatch_blocks_http_readiness(integration, monkeypatch):
    config, store, _ = integration
    set_service_env(monkeypatch, config)
    with store.engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = 'wrong_head'"))
    try:
        assert_service_gate("database_migration_mismatch")
    finally:
        with store.engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": ScriptDirectory(MIGRATIONS).get_current_head()})


def test_artifact_failure_blocks_http_readiness(integration, monkeypatch):
    config, _, _ = integration
    missing = Config(config.database_url, config.s3_endpoint, f"missing-{uuid.uuid4().hex}", config.s3_access_key, config.s3_secret_key)
    set_service_env(monkeypatch, missing)
    assert_service_gate("artifact_gate_failed")


def test_reconciliation_lock_blocks_http_readiness(integration, monkeypatch):
    config, store, _ = integration
    set_service_env(monkeypatch, config)
    with store.engine.connect() as connection:
        transaction = connection.begin()
        connection.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID})
        try:
            assert_service_gate("reconciliation_lock_unavailable")
        finally:
            transaction.rollback()


def set_service_env(monkeypatch, config):
    for key, value in {
        "DATABASE_URL": config.database_url,
        "S3_ENDPOINT": config.s3_endpoint,
        "S3_BUCKET": config.s3_bucket,
        "S3_ACCESS_KEY": config.s3_access_key,
        "S3_SECRET_KEY": config.s3_secret_key,
    }.items():
        monkeypatch.setenv(key, value)


def assert_service_gate(code):
    async def check():
        app = create_app()
        async with app.router.lifespan_context(app):
            await app.state.startup_task
            assert app.state.claim_loop.task is None
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                assert (await client.get("/health/live")).json() == {"live": True}
                response = await client.get("/health/ready")
                assert response.status_code == 503
                assert response.json() == {"ready": False, "code": code}

    asyncio.run(check())

import json
import sys
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.adapters.postgres import AdmissionStoreError
from app.domain.observations import ManifestError, normalized_states, validate_manifest
from app.application import admission
from app.application.executor import ClaimLoop
from test_startup import database, integration


ADMISSION = Path(__file__).resolve().parents[1] / "admission"
BACKEND = ADMISSION.parent
INVENTORIES = [ADMISSION / "exclusions" / f"{tier}.json" for tier in
               ("training", "validation", "development_acceptance", "held_out_evaluation")]


def test_fixture_manifest_disjoint_and_closed_states(tmp_path):
    manifest, fixtures = validate_manifest(ADMISSION / "manifest.json", INVENTORIES)
    assert len(fixtures) == 4
    assert {f["source_group"] for f, _ in fixtures} == set(manifest["reserved_source_groups"])
    assert normalized_states({"excavator": "detected", "dump_truck": "not_detected_in_frame"}) == {
        "excavator": "detected", "dump_truck": "not_detected_in_frame"}
    with pytest.raises(ValueError, match="observation_normalization_failed"):
        normalized_states({"excavator": "detected"})
    overlap = tmp_path / "overlap.json"
    overlap.write_text(json.dumps({"schema_revision": "exclusion-inventory-v1", "tier": "training",
        "reserved_source_groups": [fixtures[0][0]["source_group"]], "fixtures": []}))
    with pytest.raises(ManifestError, match="fixture_group_overlap"):
        validate_manifest(ADMISSION / "manifest.json", [overlap, *[p for p in INVENTORIES if p.stem != "training"]])
    overlap.write_text(json.dumps({"schema_revision": "exclusion-inventory-v1", "tier": "training",
        "reserved_source_groups": [], "fixtures": [{"source_group": "other", "image": fixtures[0][0]["image"]}]}))
    with pytest.raises(ManifestError, match="fixture_checksum_overlap"):
        validate_manifest(ADMISSION / "manifest.json", [overlap, *[p for p in INVENTORIES if p.stem != "training"]])
    overlap.write_text(json.dumps({"schema_revision": "exclusion-inventory-v1", "tier": "training",
        "reserved_source_groups": [], "fixtures": [{"source_group": "other",
        "source_site_camera_time_sequence_group": fixtures[0][0]["source_group"],
        "image": {"sha256": "0" * 64}}]}))
    with pytest.raises(ManifestError, match="fixture_group_overlap"):
        validate_manifest(ADMISSION / "manifest.json", [overlap, *[p for p in INVENTORIES if p.stem != "training"]])
    with pytest.raises(ManifestError, match="exclusion_inventory_incomplete"):
        validate_manifest(ADMISSION / "manifest.json", INVENTORIES[:1])


def test_incomplete_manifest_rejects_unknown_license(tmp_path):
    manifest = json.loads((ADMISSION / "manifest.json").read_text())
    manifest["declared_license"] = "unknown"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with pytest.raises(ManifestError, match="fixture_manifest_invalid"):
        validate_manifest(path, INVENTORIES)


@pytest.mark.parametrize("flag", ["--manifest", "--model-hashes"])
def test_runtime_cli_rejects_manifest_overrides(monkeypatch, flag):
    monkeypatch.setattr(sys, "argv", ["evidence-admission", "run", "--snapshot-dir", "/private/tmp/model",
        "--exclusion-inventory", str(INVENTORIES[0]), flag, "/private/tmp/override.json"])
    with pytest.raises(SystemExit) as error:
        admission.main()
    assert str(error.value.code).startswith("profile_retired:")


def test_s3_publication_integrity_and_secret_free_failures(integration):
    _, _, artifacts = integration
    intent = uuid.uuid4()
    payload = b'{"safe":"native"}'
    _, sha256, size = artifacts.upload_temporary(intent, payload, "application/json")
    key = artifacts.publish_final(intent, payload, "application/json", sha256, size)
    assert artifacts.read_verified(key, sha256, size) == payload
    with pytest.raises(Exception, match="artifact_integrity_failed"):
        artifacts.read_verified(key, "0" * 64, size)


@pytest.fixture
def isolated_admission_database(integration, monkeypatch):
    config, _, _ = integration
    database_name = f"admission_test_{uuid.uuid4().hex}"
    database_url = make_url(config.database_url).set(database=database_name).render_as_string(hide_password=False)
    admin = create_engine(config.database_url, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')
            connection.exec_driver_sql(f'ALTER DATABASE "{database_name}" SET timezone TO \'UTC\'')
        monkeypatch.setenv("DATABASE_URL", database_url)
        monkeypatch.setenv("S3_ENDPOINT", config.s3_endpoint)
        monkeypatch.setenv("S3_BUCKET", config.s3_bucket)
        monkeypatch.setenv("S3_ACCESS_KEY", config.s3_access_key)
        monkeypatch.setenv("S3_SECRET_KEY", config.s3_secret_key)
        migrations = AlembicConfig(str(BACKEND / "alembic.ini"))
        migrations.set_main_option("script_location", str(BACKEND / "migrations"))
        migrations.set_main_option("path_separator", "os")
        command.upgrade(migrations, "head")
        yield database_url
    finally:
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        admin.dispose()


def test_test_observer_cannot_bind_even_with_enabled_authorization(database):
    draft_id, test_id = uuid.uuid4(), uuid.uuid4()
    audit_hash = uuid.uuid4().hex
    with database.engine.begin() as connection:
        connection.execute(text("""INSERT INTO observer_profiles (id, status, profile_hash, snapshot)
            VALUES (:id, 'draft', :hash, '{}'::jsonb)"""), {"id": draft_id, "hash": uuid.uuid4().hex})
        connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
            VALUES (:id, :parent, 'admitted', :hash, '{"adapter":{"code":"test_observer"}}'::jsonb, :audit)"""),
            {"id": test_id, "parent": draft_id, "hash": uuid.uuid4().hex, "audit": audit_hash})
        connection.execute(text("""INSERT INTO profile_authorizations
            (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
            VALUES (:id, 1, 'enabled', 'test', :audit, false)"""), {"id": test_id, "audit": audit_hash})
    try:
        executor = ClaimLoop()
        with pytest.raises(AdmissionStoreError, match="profile_retired"):
            executor.bind_runtime(database, test_id)
        assert executor.runtime_binding is None
    finally:
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM profile_authorizations WHERE profile_id = :id"), {"id": test_id})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": test_id})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": draft_id})

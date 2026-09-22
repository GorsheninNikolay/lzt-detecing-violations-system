import hashlib
import json
import math
import os
import sys
import uuid
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.adapters.artifacts import ArtifactStore
from app.adapters.postgres import AdmissionStoreError, PostgresStore
from app.domain.observations import ManifestError, normalized_states, validate_manifest
from app.application import admission
from app.application.executor import ClaimLoop
from app.profiles.grounding_dino import GroundingDinoCpu, ObserverError
from test_startup import database, integration


ADMISSION = Path(__file__).resolve().parents[1] / "admission"
BACKEND = ADMISSION.parent
INVENTORIES = sorted((ADMISSION / "exclusions").glob("*.json"))


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


def test_incomplete_manifest_has_no_database_effect(database, tmp_path):
    manifest = json.loads((ADMISSION / "manifest.json").read_text())
    manifest["declared_license"] = "unknown"
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    with database.engine.connect() as connection:
        before = connection.execute(text("SELECT count(*) FROM admission_fixture_sets")).scalar_one()
    with pytest.raises(ManifestError, match="fixture_manifest_invalid"):
        admission.admit(path, INVENTORIES, tmp_path, tmp_path / "missing-model-hashes.json", 60)
    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM admission_fixture_sets")).scalar_one() == before


@pytest.mark.parametrize("flag", ["--manifest", "--model-hashes"])
def test_runtime_cli_rejects_manifest_overrides(monkeypatch, flag):
    monkeypatch.setattr(sys, "argv", ["evidence-admission", "run", "--snapshot-dir", "/private/tmp/model",
        "--exclusion-inventory", str(INVENTORIES[0]), flag, "/private/tmp/override.json"])
    with pytest.raises(SystemExit) as error:
        admission.main()
    assert error.value.code == 2


def test_failed_run_retains_reservation_and_rejects_draft(database):
    manifest, fixtures = validate_manifest(ADMISSION / "manifest.json", INVENTORIES)
    snapshot = {"adapter": {"code": "grounding_dino"}, "runtime": {"device": "cpu"}}
    profile, runs = database.create_admission_runs(snapshot, manifest, fixtures, 60)
    try:
        invocation = database.reserve_admission_invocation(runs[0], fixtures[0][1])
        database.fail_admission_run(runs[0], "observer_execution_failed")
        with database.engine.connect() as connection:
            state = connection.execute(text("SELECT state, error_code FROM analysis_runs WHERE id = :id"), {"id": runs[0]}).one()
            stages = connection.execute(text("SELECT state, reason FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"), {"id": runs[0]}).all()
            reservation = connection.execute(text("SELECT state FROM observer_invocations WHERE id = :id"), {"id": invocation}).scalar_one()
            projection = connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = :id"), {"id": runs[0]}).scalar_one()
        assert state == ("failed", "observer_execution_failed")
        assert stages[2] == ("failed", "observer_execution_failed")
        assert all(stage == ("skipped", "dependency_failed") for stage in stages[3:])
        assert reservation == "reserved"
        assert projection == 0
        with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
            database.require_authorized(profile)
        with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
            ClaimLoop().bind_runtime(database, profile)
        with pytest.raises(AdmissionStoreError, match="admission_incomplete"):
            database.authorize_successor(profile, runs)
    finally:
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM observer_invocations WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_stages WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM run_inputs WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": profile})


def test_invocation_completion_requires_exact_identity_and_live_fence(database):
    manifest, fixtures = validate_manifest(ADMISSION / "manifest.json", INVENTORIES)
    checkpoint = "a" * 64
    snapshot = {"model_files": {"model.safetensors": checkpoint}, "nonce": str(uuid.uuid4())}
    profile, runs = database.create_admission_runs(snapshot, manifest, fixtures, 60)
    run_id = runs[0]
    try:
        invocation = database.reserve_admission_invocation(run_id, fixtures[0][1])
        result = {"states": {"excavator": "detected", "dump_truck": "not_detected_in_frame"},
            "returned_model_identity": f"checkpoint-sha256:{'b' * 64}", "actual_device": "cpu",
            "preprocessing_revision": "test", "latency_ms": 1.0, "peak_memory_bytes": 1}
        with pytest.raises(AdmissionStoreError, match="observer_identity_or_device_invalid"):
            database.complete_invocation(run_id, invocation, result)
        result["returned_model_identity"] = f"checkpoint-sha256:{checkpoint}"
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE analysis_runs SET lease_owner = 'other' WHERE id = :id"), {"id": run_id})
        with pytest.raises(AdmissionStoreError, match="invocation_completion_rejected"):
            database.complete_invocation(run_id, invocation, result)
        with database.engine.begin() as connection:
            connection.execute(text("UPDATE analysis_runs SET lease_owner = :owner, lease_expires_at = clock_timestamp() - interval '1 second' WHERE id = :id"),
                {"owner": str(invocation), "id": run_id})
        with pytest.raises(AdmissionStoreError, match="invocation_completion_rejected"):
            database.complete_invocation(run_id, invocation, result)
        database.fail_admission_run(run_id, "executor_interrupted")
        with pytest.raises(AdmissionStoreError, match="invocation_completion_rejected"):
            database.complete_invocation(run_id, invocation, result)
        with database.engine.connect() as connection:
            assert connection.execute(text("SELECT state FROM observer_invocations WHERE id = :id"), {"id": invocation}).scalar_one() == "reserved"
            assert connection.execute(text("SELECT count(*) FROM observations WHERE run_id = :id"), {"id": run_id}).scalar_one() == 0
    finally:
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM observer_invocations WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_stages WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM run_inputs WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": profile})


def test_grounding_dino_rejects_misaligned_native_arrays():
    class Inputs(dict):
        input_ids = None

    class Processor:
        def __call__(self, **_kwargs):
            return Inputs()

        def post_process_grounded_object_detection(self, *_args, **_kwargs):
            return [{"text_labels": ["an excavator"], "scores": [], "boxes": [[0, 0, 1, 1]]}]

    class Model:
        def __call__(self, **_kwargs):
            return None

        def parameters(self):
            return iter([SimpleNamespace(device="cpu")])

    observer = GroundingDinoCpu.__new__(GroundingDinoCpu)
    observer.processor = Processor()
    observer.model = Model()
    observer.torch = SimpleNamespace(no_grad=nullcontext)
    observer.returned_identity = "checkpoint-sha256:" + "a" * 64
    image = (ADMISSION / "fixtures" / "1235_08_47_31_983151-2023-11-10.jpg").read_bytes()
    with pytest.raises(ObserverError, match="observation_normalization_failed"):
        observer.observe(image)


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


def test_offline_cpu_admission_publishes_and_authorizes(isolated_admission_database, monkeypatch):
    snapshot_dir = os.getenv("TEST_MODEL_SNAPSHOT_DIR")
    if not snapshot_dir:
        pytest.fail("Set TEST_MODEL_SNAPSHOT_DIR to the pinned offline Grounding DINO snapshot")
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    result = admission.admit(ADMISSION / "manifest.json", INVENTORIES, Path(snapshot_dir),
        ADMISSION / "model-files.json", 600)
    assert result["admitted_profile_id"] is not None
    assert len(result["run_ids"]) == 4
    profile_id = uuid.UUID(result["admitted_profile_id"])
    run_ids = [uuid.UUID(value) for value in result["run_ids"]]
    store = PostgresStore(isolated_admission_database)
    artifacts = ArtifactStore(admission.Config.from_env())
    try:
        snapshot, revision = store.require_authorized(profile_id)
        with store.engine.connect() as connection:
            profile = connection.execute(text("SELECT status, parent_id, audit_hash FROM observer_profiles WHERE id = :id"),
                {"id": profile_id}).one()
            authorization = connection.execute(text("SELECT state, revision, audit_hash FROM profile_authorizations WHERE profile_id = :id"),
                {"id": profile_id}).one()
            runs = connection.execute(text("""SELECT id, state, purpose, profile_id, binding_kind,
                bootstrap_watchdog_seconds, latency_ms, peak_memory_bytes FROM analysis_runs WHERE id = ANY(:ids)"""),
                {"ids": run_ids}).all()
            assert profile.status == "admitted" and profile.parent_id == uuid.UUID(result["draft_profile_id"])
            assert authorization == ("enabled", 1, profile.audit_hash) and revision == 1
            assert len(runs) == 4
            for run in runs:
                assert run.state == "succeeded" and run.purpose == run.binding_kind == "profile_admission"
                assert run.profile_id == profile.parent_id and run.bootstrap_watchdog_seconds == 600
                assert run.latency_ms > 0 and run.peak_memory_bytes > 0
                stages = connection.execute(text("SELECT state, reason FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"),
                    {"id": run.id}).all()
                observations = connection.execute(text("SELECT class_name, state, invocation_id FROM observations WHERE run_id = :id"),
                    {"id": run.id}).all()
                invocation = connection.execute(text("SELECT id, state, actual_device, returned_model_identity FROM observer_invocations WHERE run_id = :id"),
                    {"id": run.id}).one()
                projection = connection.execute(text("SELECT outcome FROM result_projections WHERE run_id = :id"),
                    {"id": run.id}).scalars().all()
                references = connection.execute(text("SELECT key, sha256, size FROM artifact_metadata WHERE run_id = :id"),
                    {"id": run.id}).all()
                intents = connection.execute(text("SELECT state FROM publication_intents WHERE run_id = :id"),
                    {"id": run.id}).scalars().all()
                assert stages == [("succeeded", None)] * 3 + [("skipped", "not_applicable")] * 2 + [("succeeded", None)]
                assert {row.class_name for row in observations} == {"excavator", "dump_truck"}
                assert all(row.state in {"detected", "not_detected_in_frame"} and row.invocation_id == invocation.id for row in observations)
                assert invocation.state == "completed" and invocation.actual_device == "cpu"
                committed_hash = json.loads((ADMISSION / "model-files.json").read_text())["model.safetensors"]
                assert invocation.returned_model_identity == f"checkpoint-sha256:{committed_hash}"
                assert projection == ["observations_only"]
                assert len(references) == 2 and intents == ["referenced", "referenced"]
                for reference in references:
                    artifacts.read_verified(reference.key, reference.sha256, reference.size)
        latencies = sorted(run.latency_ms / 1000 for run in runs)
        assert snapshot["runtime"]["per_image_timeout_seconds"] == pytest.approx(max(2 * latencies[math.ceil(0.95 * len(latencies)) - 1], 60))
        assert snapshot["runtime"]["batch_timeout_seconds"] == pytest.approx(max(2 * sum(latencies), 600))
        ClaimLoop().bind_runtime(store, profile_id)
        store.revoke_authorization(profile_id, revision, "test_revocation")
        with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
            ClaimLoop().bind_runtime(store, profile_id)
    finally:
        store.close()


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
        with pytest.raises(AdmissionStoreError, match="profile_unauthorized"):
            executor.bind_runtime(database, test_id)
        assert executor.runtime_binding is None
    finally:
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM profile_authorizations WHERE profile_id = :id"), {"id": test_id})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": test_id})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": draft_id})


@pytest.mark.parametrize("failure", ["observer", "snapshot", "decode"])
def test_failure_retains_four_failed_runs_without_secret(integration, monkeypatch, tmp_path, failure):
    config, database, _ = integration
    secret = "admissionsecretvalue"
    monkeypatch.setenv("DATABASE_URL", config.database_url)
    monkeypatch.setenv("S3_ENDPOINT", config.s3_endpoint)
    monkeypatch.setenv("S3_BUCKET", config.s3_bucket)
    monkeypatch.setenv("S3_ACCESS_KEY", config.s3_access_key)
    monkeypatch.setenv("S3_SECRET_KEY", config.s3_secret_key)
    monkeypatch.setenv("PROFILE_SECRET", secret)
    monkeypatch.setattr(admission, "verify_cpu_baseline", lambda: None)
    if failure == "snapshot":
        def fail_snapshot(*_):
            raise admission.ObserverError("model_snapshot_hash_mismatch")
        monkeypatch.setattr(admission, "verify_snapshot", fail_snapshot)
    else:
        monkeypatch.setattr(admission, "verify_snapshot", lambda *_: None)
    hashes = {"model.safetensors": "0" * 64}
    hash_file = tmp_path / "hashes.json"
    hash_file.write_text(json.dumps(hashes))
    monkeypatch.setattr(admission, "draft_snapshot", lambda *_: {"model_files": hashes, "nonce": str(uuid.uuid4())})
    manifest_path = ADMISSION / "manifest.json"
    if failure == "decode":
        manifest = json.loads(manifest_path.read_text())
        for fixture in manifest["fixtures"]:
            for kind in ("image", "label"):
                relative = Path(fixture[kind]["path"])
                output = tmp_path / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes((ADMISSION / relative).read_bytes())
        broken = b"not a decodable JPEG"
        first_image = manifest["fixtures"][0]["image"]
        (tmp_path / first_image["path"]).write_bytes(broken)
        first_image["sha256"] = hashlib.sha256(broken).hexdigest()
        first_image["size"] = len(broken)
        manifest_path = tmp_path / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))

    class FailingObserver:
        def __init__(self, *_):
            raise RuntimeError(secret)

    monkeypatch.setattr(admission, "GroundingDinoCpu", FailingObserver)
    result = admission.admit(manifest_path, INVENTORIES, tmp_path, hash_file, 60)
    profile = uuid.UUID(result["draft_profile_id"])
    runs = [uuid.UUID(value) for value in result["run_ids"]]
    try:
        assert result["admitted_profile_id"] is None
        with database.engine.connect() as connection:
            rows = connection.execute(text("SELECT id, state, error_code, profile_snapshot::text FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": runs}).all()
            projections = connection.execute(text("SELECT count(*) FROM result_projections WHERE run_id = ANY(:ids)"), {"ids": runs}).scalar_one()
            authorizations = connection.execute(text("SELECT count(*) FROM profile_authorizations WHERE profile_id = :id"), {"id": profile}).scalar_one()
            stages = {run: connection.execute(text("SELECT state FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"),
                {"id": run}).scalars().all() for run in runs}
            reservations = connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = ANY(:ids) AND state = 'reserved'"),
                {"ids": runs}).scalar_one()
        expected_code = "model_snapshot_hash_mismatch" if failure == "snapshot" else "admission_failed"
        assert len(rows) == 4 and all(row.state == "failed" for row in rows)
        assert all(row.error_code == ("frame_decode_failed" if failure == "decode" and row.id == runs[0] else expected_code) for row in rows)
        assert all(secret not in row.profile_snapshot for row in rows)
        assert projections == authorizations == 0
        if failure == "snapshot":
            assert reservations == 0 and all(states == ["failed"] + ["skipped"] * 5 for states in stages.values())
        elif failure == "decode":
            assert reservations == 3
            assert stages[runs[0]] == ["succeeded", "failed"] + ["skipped"] * 4
            assert all(stages[run] == ["succeeded", "succeeded", "failed"] + ["skipped"] * 3 for run in runs[1:])
        else:
            assert reservations == 4 and all(states == ["succeeded", "succeeded", "failed"] + ["skipped"] * 3 for states in stages.values())
    finally:
        with database.engine.begin() as connection:
            connection.execute(text("DELETE FROM observer_invocations WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_stages WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM run_inputs WHERE run_id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": runs})
            connection.execute(text("DELETE FROM observer_profiles WHERE id = :id"), {"id": profile})

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import json
import math
import uuid
from pathlib import Path
from time import monotonic

from app.domain.observations import CLASSES, STAGES, normalized_states
from app.profiles import grounding_dino
from app.profiles.grounding_dino import canonical_bytes, digest
from app.adapters.artifacts import ArtifactGateError, ArtifactStore


class DatabaseGateError(RuntimeError):
    pass


class ReconciliationGateError(RuntimeError):
    pass


class RecoveryGateError(RuntimeError):
    pass


class AdmissionStoreError(RuntimeError):
    pass


LOCK_ID = 804298270113


class PostgresStore:
    def __init__(self, url: str):
        self.engine: Engine = create_engine(url, pool_pre_ping=True)

    def close(self) -> None:
        self.engine.dispose()

    def check_head_and_smoke(self, migrations_path: str) -> None:
        try:
            expected = ScriptDirectory(migrations_path).get_current_head()
            with self.engine.begin() as connection:
                actual = MigrationContext.configure(connection).get_current_revision()
            if actual != expected or expected is None:
                raise DatabaseGateError("database_migration_mismatch")
            with self.engine.connect() as connection:
                transaction = connection.begin()
                try:
                    marker = connection.execute(text("INSERT INTO startup_smoke (nonce) VALUES (gen_random_uuid()) RETURNING nonce")).scalar_one()
                    observed = connection.execute(text("SELECT nonce FROM startup_smoke WHERE nonce = :nonce"), {"nonce": marker}).scalar_one()
                    if observed != marker:
                        raise DatabaseGateError("database_smoke_failed")
                finally:
                    transaction.rollback()
        except DatabaseGateError:
            raise
        except Exception:
            raise DatabaseGateError("database_smoke_failed") from None

    def reconcile(self, artifacts: ArtifactStore | None = None, *, runtime: bool = False) -> None:
        observed_count = 0
        try:
            with self.engine.begin() as connection:
                locked = connection.execute(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": LOCK_ID}).scalar_one()
                if not locked:
                    raise ReconciliationGateError("reconciliation_lock_unavailable")
                integrity_failed = bool(connection.execute(text(
                    "SELECT 1 FROM publication_intents WHERE state = 'failed_integrity' LIMIT 1")).first())
                rows = connection.execute(text("""SELECT i.id, i.state, i.run_id, i.sha256, i.size, i.final_key,
                    i.media_type
                    FROM publication_intents i
                    WHERE i.state NOT IN ('referenced', 'quarantined', 'failed_integrity')
                      AND (:runtime = false OR i.run_id IS NOT NULL) FOR UPDATE OF i"""),
                    {"runtime": runtime}).all()
                observed_count = len(rows)
                def inspect_final(row):
                    status, creator = artifacts.inspect_reconciliation(row.final_key, row.sha256, row.size)
                    if status == "verified" and not connection.execute(text("""SELECT 1 FROM publication_intents
                        WHERE id = :creator AND sha256 = :hash AND size = :size AND final_key = :key"""),
                        {"creator": uuid.UUID(creator), "hash": row.sha256, "size": row.size,
                         "key": row.final_key}).first():
                        raise ArtifactGateError("artifact_integrity_failed")
                    return status

                for row in rows:
                    if row.run_id is not None:
                        run = connection.execute(text("""SELECT state, lease_expires_at > clock_timestamp() AS lease_live
                            FROM analysis_runs WHERE id = :id FOR UPDATE NOWAIT"""), {"id": row.run_id}).one()
                        if run.state == "running" and run.lease_live:
                            continue
                    if artifacts is None:
                        raise ReconciliationGateError("reconciliation_inspector_missing")
                    try:
                        if row.state == "pending_upload":
                            artifacts.inspect_reconciliation(f"tmp/{row.id}", creator=row.id)
                        elif row.state == "content_verified":
                            if row.sha256 is None or row.size is None or row.final_key != f"sha256/{row.sha256}":
                                raise ArtifactGateError("artifact_integrity_failed")
                            artifacts.inspect_reconciliation(f"tmp/{row.id}", row.sha256, row.size, row.id)
                            inspect_final(row)
                        elif row.state == "object_published":
                            if row.sha256 is None or row.size is None or row.final_key != f"sha256/{row.sha256}":
                                raise ArtifactGateError("artifact_integrity_failed")
                            if inspect_final(row) == "missing":
                                raise ArtifactGateError("artifact_integrity_failed")
                        else:
                            raise ReconciliationGateError("reconciliation_unknown_state")
                    except ArtifactGateError as exc:
                        if str(exc) != "artifact_integrity_failed":
                            raise ReconciliationGateError("reconciliation_artifact_unavailable") from None
                        connection.execute(text("""UPDATE publication_intents SET state = 'failed_integrity',
                            error_code = 'artifact_integrity_failed' WHERE id = :id"""), {"id": row.id})
                        integrity_failed = True
                        continue
                    reference = None
                    if row.state == "object_published" and row.run_id is not None:
                        reference = connection.execute(text("""SELECT 1 FROM artifact_metadata a
                            WHERE a.intent_id = :id AND a.run_id = :run AND a.key = :key AND a.sha256 = :hash
                              AND a.size = :size AND a.media_type = :media
                              AND (EXISTS (SELECT 1 FROM run_inputs i WHERE i.run_id = a.run_id AND i.artifact_id = a.id)
                                OR EXISTS (SELECT 1 FROM observer_invocations v
                                   WHERE v.run_id = a.run_id AND v.native_artifact_id = a.id)
                                OR EXISTS (SELECT 1 FROM result_projections p WHERE p.run_id = a.run_id
                                   AND p.snapshot->'evidence' @> jsonb_build_array(jsonb_build_object(
                                     'key', a.key, 'sha256', a.sha256, 'size', a.size))))"""),
                            {"id": row.id, "run": row.run_id, "key": row.final_key, "hash": row.sha256,
                             "size": row.size, "media": row.media_type}).first()
                    connection.execute(text("UPDATE publication_intents SET state = :state WHERE id = :id"),
                                       {"id": row.id, "state": "referenced" if reference else "quarantined"})
                if not runtime:
                    connection.execute(text("""UPDATE submission_requests SET state = 'failed', error_code = 'submission_interrupted'
                        WHERE state = 'publishing'"""))
                connection.execute(text("""INSERT INTO reconciliation_runs (started_at, completed_at, intent_count, status, error_code)
                    VALUES (clock_timestamp(), clock_timestamp(), :count, :status, :error)"""),
                    {"count": observed_count, "status": "failed" if integrity_failed else "succeeded",
                     "error": "reconciliation_integrity_failed" if integrity_failed else None})
            if integrity_failed:
                raise ReconciliationGateError("reconciliation_integrity_failed")
        except ReconciliationGateError as exc:
            if str(exc) != "reconciliation_integrity_failed":
                self._record_reconciliation_failure(str(exc), observed_count)
            raise
        except Exception:
            self._record_reconciliation_failure("reconciliation_gate_failed", observed_count)
            raise ReconciliationGateError("reconciliation_gate_failed") from None

    def _record_reconciliation_failure(self, code: str, intent_count: int) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(text("INSERT INTO reconciliation_runs (started_at, completed_at, intent_count, status, error_code) VALUES (clock_timestamp(), clock_timestamp(), :count, 'failed', :code)"), {"count": intent_count, "code": code})
        except Exception:
            pass

    def recover(self) -> int:
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '1s'"))
                rows = connection.execute(text("SELECT id, lease_owner, lease_expires_at, clock_timestamp() AS db_now FROM analysis_runs WHERE state = 'running' AND (lease_expires_at IS NULL OR lease_expires_at <= clock_timestamp()) FOR UPDATE NOWAIT")).all()
                for run_id, owner, expiry, db_now in rows:
                    if expiry is None or owner is None:
                        raise RecoveryGateError("recovery_unknown_ownership")
                    if expiry > db_now:
                        continue
                    updated = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = 'executor_interrupted',
                        lease_owner = NULL, lease_expires_at = NULL WHERE id = :id AND state = 'running'
                        AND lease_owner = :owner AND lease_expires_at = :expiry
                        AND lease_expires_at <= clock_timestamp()"""),
                        {"id": run_id, "owner": owner, "expiry": expiry})
                    if updated.rowcount != 1:
                        raise RecoveryGateError("recovery_lease_changed")
                    connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :id AND state = 'reserved'"), {"id": run_id})
                    connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'executor_interrupted' WHERE run_id = :id AND state = 'running'"), {"id": run_id})
                    connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :id AND state = 'pending'"), {"id": run_id})
                return len(rows)
        except RecoveryGateError:
            raise
        except Exception:
            raise RecoveryGateError("recovery_gate_failed") from None

    def create_admission_runs(self, snapshot: dict, manifest: dict, fixtures: list[tuple[dict, bytes]], watchdog_seconds: int) -> tuple[uuid.UUID, list[uuid.UUID]]:
        if watchdog_seconds <= 0:
            raise AdmissionStoreError("bootstrap_watchdog_invalid")
        profile_hash = digest(canonical_bytes(snapshot))
        manifest_hash = digest(canonical_bytes(manifest))
        profile_id, fixture_set_id = uuid.uuid4(), uuid.uuid4()
        run_ids = [uuid.uuid4() for _ in fixtures]
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO observer_profiles (id, status, profile_hash, snapshot) VALUES (:id, 'draft', :hash, CAST(:snapshot AS jsonb)) ON CONFLICT (profile_hash) DO NOTHING"),
                {"id": profile_id, "hash": profile_hash, "snapshot": json.dumps(snapshot)})
            profile_id = connection.execute(text("SELECT id FROM observer_profiles WHERE profile_hash = :hash AND status = 'draft'"), {"hash": profile_hash}).scalar_one()
            connection.execute(text("INSERT INTO admission_fixture_sets (id, manifest_hash, manifest) VALUES (:id, :hash, CAST(:manifest AS jsonb)) ON CONFLICT (manifest_hash) DO NOTHING"),
                {"id": fixture_set_id, "hash": manifest_hash, "manifest": json.dumps(manifest)})
            fixture_set_id = connection.execute(text("SELECT id FROM admission_fixture_sets WHERE manifest_hash = :hash"), {"hash": manifest_hash}).scalar_one()
            for run_id, (fixture, _) in zip(run_ids, fixtures):
                image = fixture["image"]
                connection.execute(text("""INSERT INTO analysis_runs
                    (id, state, purpose, profile_id, binding_kind, fixture_set_id, fixture_id, bootstrap_watchdog_seconds, profile_snapshot)
                    VALUES (:id, 'queued', 'profile_admission', :profile, 'profile_admission', :set_id, :fixture, :watchdog, CAST(:snapshot AS jsonb))"""),
                    {"id": run_id, "profile": profile_id, "set_id": fixture_set_id, "fixture": fixture["id"],
                     "watchdog": watchdog_seconds, "snapshot": json.dumps(snapshot)})
                connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, fixture_id, sha256, size, context)
                    VALUES (:run, 0, :fixture, :hash, :size, CAST(:context AS jsonb))"""),
                    {"run": run_id, "fixture": fixture["id"], "hash": image["sha256"], "size": image["size"],
                     "context": json.dumps(fixture["context"])})
                for ordinal, name in enumerate(STAGES):
                    connection.execute(text("INSERT INTO analysis_stages (run_id, ordinal, name, state) VALUES (:run, :ordinal, :name, 'pending')"),
                        {"run": run_id, "ordinal": ordinal, "name": name})
        return profile_id, run_ids

    def reserve_admission_invocation(self, run_id: uuid.UUID, input_bytes: bytes) -> uuid.UUID:
        invocation_id = uuid.uuid4()
        input_hash = digest(input_bytes)
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.profile_id, r.bootstrap_watchdog_seconds, i.sha256, i.size, i.input_id, p.status
                FROM analysis_runs r JOIN run_inputs i ON i.run_id = r.id JOIN observer_profiles p ON p.id = r.profile_id
                WHERE r.id = :id AND r.purpose = 'profile_admission' AND r.state = 'queued' FOR UPDATE OF r"""), {"id": run_id}).one_or_none()
            if not row or row.status != "draft" or row.sha256 != input_hash or row.size != len(input_bytes) or row.bootstrap_watchdog_seconds <= 0:
                raise AdmissionStoreError("admission_reservation_rejected")
            connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = :owner,
                lease_expires_at = clock_timestamp() + (:watchdog * interval '1 second') WHERE id = :id"""),
                {"owner": str(invocation_id), "watchdog": row.bootstrap_watchdog_seconds, "id": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :id AND ordinal IN (0, 1)"), {"id": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :id AND ordinal = 2"), {"id": run_id})
            connection.execute(text("""INSERT INTO observer_invocations
                (id, run_id, input_id, fence, profile_id, stage_ordinal, input_sha256, intended_request_identity, state)
                VALUES (:id, :run, :input_id, 1, :profile, 2, :hash, 'local-grounding-dino-cpu', 'reserved')"""),
                {"id": invocation_id, "run": run_id, "input_id": row.input_id,
                 "profile": row.profile_id, "hash": input_hash})
        return invocation_id

    def complete_invocation(self, run_id: uuid.UUID, invocation_id: uuid.UUID, result: dict) -> None:
        states = normalized_states(result["states"])
        with self.engine.begin() as connection:
            reservation = connection.execute(text("""SELECT r.state AS run_state, r.lease_owner,
                r.lease_expires_at > clock_timestamp() AS lease_live,
                r.profile_snapshot->'model_files'->>'model.safetensors' AS checkpoint_sha256,
                i.state AS invocation_state, i.fence
                FROM analysis_runs r JOIN observer_invocations i ON i.run_id = r.id
                WHERE r.id = :run AND i.id = :id FOR UPDATE OF r, i"""),
                {"run": run_id, "id": invocation_id}).one_or_none()
            if (not reservation or reservation.run_state != "running" or reservation.lease_owner != str(invocation_id)
                    or not reservation.lease_live or reservation.invocation_state != "reserved" or reservation.fence != 1):
                raise AdmissionStoreError("invocation_completion_rejected")
            if (not reservation.checkpoint_sha256
                    or result.get("returned_model_identity") != f"checkpoint-sha256:{reservation.checkpoint_sha256}"
                    or result.get("actual_device") != "cpu"):
                raise AdmissionStoreError("observer_identity_or_device_invalid")
            changed = connection.execute(text("""UPDATE observer_invocations SET state = 'completed',
                returned_model_identity = :identity, actual_device = :device, preprocessing_revision = :preprocessing
                WHERE id = :id AND run_id = :run AND state = 'reserved' AND fence = 1"""),
                {"identity": result["returned_model_identity"], "device": result["actual_device"],
                 "preprocessing": result["preprocessing_revision"], "id": invocation_id, "run": run_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("invocation_completion_rejected")
            measured = connection.execute(text("""UPDATE analysis_runs SET latency_ms = :latency, peak_memory_bytes = :memory
                WHERE id = :run AND state = 'running' AND lease_owner = :owner
                  AND lease_expires_at > clock_timestamp()"""),
                {"latency": result["latency_ms"], "memory": result["peak_memory_bytes"],
                 "run": run_id, "owner": str(invocation_id)})
            if measured.rowcount != 1:
                raise AdmissionStoreError("invocation_completion_rejected")
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 2 AND state = 'running'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'not_applicable' WHERE run_id = :run AND ordinal IN (3, 4) AND state = 'pending'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 5 AND state = 'pending'"), {"run": run_id})
            input_id, input_hash = connection.execute(text("SELECT input_id, sha256 FROM run_inputs WHERE run_id = :run AND ordinal = 0"), {"run": run_id}).one()
            for name in CLASSES:
                connection.execute(text("""INSERT INTO observations (run_id, input_id, class_name, state, input_sha256, invocation_id)
                    VALUES (:run, :input_id, :name, :state, :hash, :invocation)"""),
                    {"run": run_id, "input_id": input_id, "name": name,
                     "state": states[name], "hash": input_hash, "invocation": invocation_id})

    def create_publication_intent(self, run_id: uuid.UUID, media_type: str, idempotency_key: str) -> uuid.UUID:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO publication_intents (id, run_id, idempotency_key, media_type, state)
                VALUES (:id, :run, :key, :media, 'pending_upload')"""),
                {"id": intent_id, "run": run_id, "key": idempotency_key, "media": media_type})
        return intent_id

    def create_submission_intent(self, key: str) -> uuid.UUID:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            connection.execute(text("""INSERT INTO publication_intents
                (id, idempotency_key, submission_key, media_type, state)
                VALUES (:id, :intent_key, :key, 'image/jpeg', 'pending_upload')"""),
                {"id": intent_id, "intent_key": f"submission-intent:{intent_id}", "key": key})
        return intent_id

    def publication_content_verified(self, intent_id: uuid.UUID, sha256: str, size: int, final_key: str) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE publication_intents SET state = 'content_verified',
                sha256 = :hash, size = :size, final_key = :key WHERE id = :id AND state = 'pending_upload'"""),
                {"hash": sha256, "size": size, "key": final_key, "id": intent_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("publication_state_changed")

    def publication_object_published(self, intent_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("UPDATE publication_intents SET state = 'object_published' WHERE id = :id AND state = 'content_verified'"), {"id": intent_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("publication_state_changed")

    def publication_failed_integrity(self, intent_id: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""UPDATE publication_intents SET state = 'failed_integrity',
                error_code = 'artifact_integrity_failed' WHERE id = :id AND state = 'content_verified'"""),
                {"id": intent_id})

    def finish_admission_run(self, run_id: uuid.UUID, invocation_id: uuid.UUID, native_intent: uuid.UUID, input_intent: uuid.UUID) -> None:
        with self.engine.begin() as connection:
            intents = connection.execute(text("SELECT id, media_type, sha256, size, final_key FROM publication_intents WHERE id IN (:native, :input) AND run_id = :run AND state = 'object_published' FOR UPDATE"),
                {"native": native_intent, "input": input_intent, "run": run_id}).all()
            if len(intents) != 2:
                raise AdmissionStoreError("publication_incomplete")
            for row in intents:
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, :media)"""),
                    {"id": uuid.uuid4(), "run": run_id, "intent": row.id, "key": row.final_key,
                     "hash": row.sha256, "size": row.size, "media": row.media_type})
            native_artifact_id = connection.execute(text("SELECT id FROM artifact_metadata WHERE intent_id = :intent"), {"intent": native_intent}).scalar_one()
            connection.execute(text("UPDATE observer_invocations SET native_artifact_id = :artifact WHERE id = :id AND state = 'completed'"),
                {"artifact": native_artifact_id, "id": invocation_id})
            observations = connection.execute(text("SELECT class_name, state FROM observations WHERE run_id = :run"), {"run": run_id}).all()
            if len(observations) != 2:
                raise AdmissionStoreError("observation_incomplete")
            projection = {"outcome": "observations_only", "classes": dict(observations),
                "evidence": [{"key": row.final_key, "sha256": row.sha256, "size": row.size} for row in intents]}
            connection.execute(text("INSERT INTO result_projections (run_id, outcome, snapshot) VALUES (:run, 'observations_only', CAST(:snapshot AS jsonb))"),
                {"run": run_id, "snapshot": json.dumps(projection)})
            connection.execute(text("UPDATE publication_intents SET state = 'referenced' WHERE id IN (:native, :input)"),
                {"native": native_intent, "input": input_intent})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 5 AND state = 'running'"), {"run": run_id})
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL, lease_expires_at = NULL
                WHERE id = :run AND state = 'running' AND lease_expires_at > clock_timestamp()"""), {"run": run_id})
            if changed.rowcount != 1:
                raise AdmissionStoreError("admission_watchdog_expired")

    def fail_admission_run(self, run_id: uuid.UUID, code: str, failed_stage_ordinal: int | None = None) -> None:
        if not code.isidentifier():
            code = "admission_failed"
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = :code,
                lease_owner = NULL, lease_expires_at = NULL WHERE id = :run AND state IN ('queued', 'running')"""),
                {"run": run_id, "code": code})
            if changed.rowcount:
                stage_failure = connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = :code WHERE run_id = :run AND state = 'running'"), {"run": run_id, "code": code})
                if not stage_failure.rowcount:
                    if failed_stage_ordinal == 1:
                        connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 0 AND state = 'pending'"), {"run": run_id})
                    connection.execute(text("""UPDATE analysis_stages SET state = 'failed', reason = :code
                        WHERE run_id = :run AND ordinal = (SELECT min(ordinal) FROM analysis_stages WHERE run_id = :run AND state = 'pending')"""),
                        {"run": run_id, "code": code})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"), {"run": run_id})

    def authorize_successor(self, profile_id: uuid.UUID, run_ids: list[uuid.UUID]) -> uuid.UUID:
        if not run_ids:
            raise AdmissionStoreError("admission_incomplete")
        with self.engine.begin() as connection:
            draft = connection.execute(text("SELECT snapshot FROM observer_profiles WHERE id = :id AND status = 'draft' FOR UPDATE"), {"id": profile_id}).one_or_none()
            if not draft:
                raise AdmissionStoreError("admission_draft_missing")
            if connection.execute(text("SELECT 1 FROM observer_profiles WHERE parent_id = :id AND status = 'admitted'"), {"id": profile_id}).first():
                raise AdmissionStoreError("admission_successor_exists")
            rows = connection.execute(text("""SELECT id, state, latency_ms, peak_memory_bytes FROM analysis_runs
                WHERE id = ANY(:ids) AND profile_id = :profile AND purpose = 'profile_admission' FOR UPDATE"""),
                {"ids": run_ids, "profile": profile_id}).all()
            if len(rows) != len(run_ids) or any(row.state != "succeeded" or row.latency_ms is None or row.peak_memory_bytes is None for row in rows):
                raise AdmissionStoreError("admission_incomplete")
            fixtures = connection.execute(text("SELECT fixture_id, fixture_set_id FROM analysis_runs WHERE id = ANY(:ids)"), {"ids": run_ids}).all()
            if len({row.fixture_set_id for row in fixtures}) != 1 or len({row.fixture_id for row in fixtures}) != len(run_ids):
                raise AdmissionStoreError("admission_incomplete")
            total = connection.execute(text("SELECT count(*) FROM admission_fixture_sets s, jsonb_array_elements(s.manifest->'fixtures') f WHERE s.id = :id"),
                {"id": fixtures[0].fixture_set_id}).scalar_one()
            if total != len(run_ids):
                raise AdmissionStoreError("admission_incomplete")
            actual_devices = connection.execute(text("SELECT actual_device, returned_model_identity, native_artifact_id FROM observer_invocations WHERE run_id = ANY(:ids)"), {"ids": run_ids}).all()
            if len(actual_devices) != len(run_ids) or any(row.actual_device != "cpu" or not row.returned_model_identity or not row.native_artifact_id for row in actual_devices):
                raise AdmissionStoreError("admission_incomplete")
            identities = {row.returned_model_identity for row in actual_devices}
            expected_adapter_hash = digest(Path(grounding_dino.__file__).read_bytes())
            expected_lock_hash = digest((Path(__file__).resolve().parents[2] / "uv.lock").read_bytes())
            adapter = draft.snapshot.get("adapter", {})
            runtime = draft.snapshot.get("runtime", {})
            identity = draft.snapshot.get("requested_model_identity", {})
            if (len(identities) != 1 or adapter.get("code") != "grounding_dino"
                    or adapter.get("bundle_sha256") != expected_adapter_hash
                    or runtime.get("uv_lock_sha256") != expected_lock_hash
                    or runtime.get("device") != "cpu"
                    or identity != {"id": grounding_dino.MODEL_ID, "revision": grounding_dino.MODEL_REVISION}):
                raise AdmissionStoreError("admission_identity_invalid")
            latencies = sorted(row.latency_ms / 1000 for row in rows)
            p95 = latencies[math.ceil(0.95 * len(latencies)) - 1]
            image_timeout = max(2 * p95, 60)
            batch_timeout = max(2 * sum(latencies), 600)
            audit = {"run_ids": [str(value) for value in run_ids], "latency_seconds": latencies,
                "peak_memory_bytes": [row.peak_memory_bytes for row in rows], "actual_device": "cpu", "errors": []}
            audit_hash = digest(canonical_bytes(audit))
            snapshot = dict(draft.snapshot)
            snapshot["returned_model_identity"] = identities.pop()
            snapshot["identity_gap"] = "local checkpoint digest identifies loaded bytes; no remote model identity was returned"
            snapshot["audit_hash"] = audit_hash
            snapshot["audit_run_ids"] = audit["run_ids"]
            snapshot["runtime"] = {**snapshot["runtime"], "per_image_timeout_seconds": image_timeout,
                "batch_timeout_seconds": batch_timeout}
            successor_id = uuid.uuid4()
            snapshot["audit_uri"] = f"postgresql:observer_profiles/{successor_id}"
            snapshot["audit_report"] = audit
            successor_hash = digest(canonical_bytes(snapshot))
            connection.execute(text("""INSERT INTO observer_profiles (id, parent_id, status, profile_hash, snapshot, audit_hash)
                VALUES (:id, :parent, 'admitted', :hash, CAST(:snapshot AS jsonb), :audit)"""),
                {"id": successor_id, "parent": profile_id, "hash": successor_hash,
                 "snapshot": json.dumps(snapshot), "audit": audit_hash})
            connection.execute(text("""INSERT INTO profile_authorizations
                (profile_id, revision, state, reason, audit_hash, interactive_retry_allowed)
                VALUES (:id, 1, 'enabled', 'complete_cpu_admission', :audit, false)"""),
                {"id": successor_id, "audit": audit_hash})
            return successor_id

    def require_authorized(self, profile_id: uuid.UUID, expected_revision: int | None = None) -> tuple[dict, int]:
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT p.status, p.parent_id, p.profile_hash, p.snapshot, p.audit_hash,
                a.state, a.revision, a.audit_hash AS authorization_audit
                FROM observer_profiles p LEFT JOIN profile_authorizations a ON a.profile_id = p.id
                WHERE p.id = :id FOR UPDATE OF p"""), {"id": profile_id}).one_or_none()
            if not row or row.status != "admitted" or not row.audit_hash or row.state != "enabled" or row.authorization_audit != row.audit_hash:
                raise AdmissionStoreError("profile_unauthorized")
            if expected_revision is not None and row.revision != expected_revision:
                raise AdmissionStoreError("authorization_revision_changed")
            if row.snapshot.get("adapter", {}).get("code") != "grounding_dino":
                raise AdmissionStoreError("profile_unauthorized")
            run_ids = row.snapshot.get("audit_run_ids", [])
            if (not row.parent_id or not isinstance(run_ids, list) or len(run_ids) != 4
                    or not all(isinstance(value, str) for value in run_ids) or len(set(run_ids)) != 4
                    or digest(canonical_bytes(row.snapshot)) != row.profile_hash
                    or digest(canonical_bytes(row.snapshot.get("audit_report"))) != row.audit_hash):
                raise AdmissionStoreError("profile_admission_evidence_missing")
            evidenced = connection.execute(text("""SELECT count(*) FROM analysis_runs r
                JOIN observer_invocations i ON i.run_id = r.id
                JOIN result_projections p ON p.run_id = r.id
                WHERE r.id = ANY(:ids) AND r.profile_id = :parent AND r.purpose = 'profile_admission'
                  AND r.state = 'succeeded' AND i.state = 'completed' AND i.actual_device = 'cpu'
                  AND p.outcome = 'observations_only'"""), {"ids": [uuid.UUID(value) for value in run_ids], "parent": row.parent_id}).scalar_one()
            if evidenced != 4:
                raise AdmissionStoreError("profile_admission_evidence_missing")
            adapter_hash = digest(Path(grounding_dino.__file__).read_bytes())
            lock_hash = digest((Path(__file__).resolve().parents[2] / "uv.lock").read_bytes())
            if row.snapshot.get("adapter", {}).get("bundle_sha256") != adapter_hash or row.snapshot.get("runtime", {}).get("uv_lock_sha256") != lock_hash:
                raise AdmissionStoreError("profile_runtime_mismatch")
            return row.snapshot, row.revision

    def revoke_authorization(self, profile_id: uuid.UUID, expected_revision: int, reason: str) -> None:
        if not reason.isidentifier():
            raise AdmissionStoreError("authorization_reason_invalid")
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE profile_authorizations SET state = 'revoked', revision = revision + 1,
                reason = :reason WHERE profile_id = :id AND revision = :expected AND state = 'enabled'"""),
                {"reason": reason, "id": profile_id, "expected": expected_revision})
            if changed.rowcount != 1:
                raise AdmissionStoreError("authorization_revision_changed")

    def begin_submission(self, key: str, request_hash: str, media_type: str) -> tuple[str, uuid.UUID | None, uuid.UUID | None, str | None]:
        intent_id = uuid.uuid4()
        with self.engine.begin() as connection:
            created = connection.execute(text("""INSERT INTO submission_requests (idempotency_key, request_hash, state)
                VALUES (:key, :hash, 'publishing') ON CONFLICT DO NOTHING RETURNING idempotency_key"""),
                {"key": key, "hash": request_hash}).first()
            row = connection.execute(text("SELECT * FROM submission_requests WHERE idempotency_key = :key FOR UPDATE"), {"key": key}).one()
            if row.request_hash != request_hash:
                raise AdmissionStoreError("idempotency_key_conflict")
            if not created:
                return row.state, row.run_id, row.intent_id, row.error_code
            connection.execute(text("""INSERT INTO publication_intents
                (id, idempotency_key, submission_key, media_type, state)
                VALUES (:id, :intent_key, :key, :media, 'pending_upload')"""),
                {"id": intent_id, "intent_key": f"submission-intent:{intent_id}", "key": key, "media": media_type})
            connection.execute(text("UPDATE submission_requests SET intent_id = :intent WHERE idempotency_key = :key"),
                {"intent": intent_id, "key": key})
            return "created", None, intent_id, None

    def fail_submission(self, key: str, code: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(text("""UPDATE submission_requests SET state = 'failed', error_code = :code
                WHERE idempotency_key = :key AND state = 'publishing'"""), {"key": key, "code": code})

    def commit_submission(self, key: str, profile_id: uuid.UUID, revision: int, snapshot: dict,
                          context: dict, requested_classes: list[str], image_hash: str, image_size: int) -> uuid.UUID:
        with self.engine.connect() as connection:
            intent_id = connection.execute(text("SELECT intent_id FROM submission_requests WHERE idempotency_key = :key"), {"key": key}).scalar_one()
        return self.commit_series_submission(key, profile_id, revision, snapshot, context, requested_classes,
                                             [(intent_id, image_hash, image_size)])

    def commit_series_submission(self, key: str, profile_id: uuid.UUID, revision: int, snapshot: dict,
                                 context: dict, requested_classes: list[str],
                                 manifest: list[tuple[uuid.UUID, str, int]]) -> uuid.UUID:
        run_id = uuid.uuid4()
        with self.engine.begin() as connection:
            request = connection.execute(text("""SELECT * FROM submission_requests
                WHERE idempotency_key = :key FOR UPDATE"""), {"key": key}).one()
            if request.state != "publishing":
                raise AdmissionStoreError("submission_state_changed")
            authorization = connection.execute(text("""SELECT p.status, a.state, a.revision FROM observer_profiles p
                JOIN profile_authorizations a ON a.profile_id = p.id WHERE p.id = :id FOR UPDATE OF a"""),
                {"id": profile_id}).one_or_none()
            if not authorization or authorization.status != "admitted" or authorization.state != "enabled" or authorization.revision != revision:
                raise AdmissionStoreError("profile_unauthorized")
            if not manifest or manifest[0][0] != request.intent_id or len({item[0] for item in manifest}) != len(manifest):
                raise AdmissionStoreError("publication_incomplete")
            intents = []
            for intent_id, image_hash, image_size in manifest:
                intent = connection.execute(text("""SELECT sha256, size, final_key FROM publication_intents
                    WHERE id = :id AND submission_key = :key AND run_id IS NULL
                      AND state = 'object_published' FOR UPDATE"""),
                    {"id": intent_id, "key": key}).one_or_none()
                if not intent or intent.sha256 != image_hash or intent.size != image_size or intent.final_key != f"sha256/{image_hash}":
                    raise AdmissionStoreError("publication_incomplete")
                intents.append(intent)
            connection.execute(text("""INSERT INTO analysis_runs
                (id, state, purpose, profile_id, authorization_revision, binding_kind, profile_snapshot,
                 request_context, policy_snapshot, taxonomy_snapshot, requested_classes)
                VALUES (:run, 'queued', 'ordinary', :profile, :revision, 'admitted_profile',
                    CAST(:snapshot AS jsonb), CAST(:context AS jsonb), CAST(:policy AS jsonb),
                    CAST(:taxonomy AS jsonb), CAST(:classes AS jsonb))"""),
                {"run": run_id, "profile": profile_id, "revision": revision,
                 "snapshot": json.dumps(snapshot), "context": json.dumps(context),
                 "policy": json.dumps({"intent": "observation_only", "revision": "observations-only-v1"}),
                 "taxonomy": json.dumps({"portable_classes": list(CLASSES), "revision": "presence-only-v1"}),
                 "classes": json.dumps(requested_classes)})
            for ordinal, ((intent_id, image_hash, image_size), intent) in enumerate(zip(manifest, intents)):
                artifact_id = uuid.uuid4()
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, 'image/jpeg')"""),
                    {"id": artifact_id, "run": run_id, "intent": intent_id, "key": intent.final_key,
                     "hash": image_hash, "size": image_size})
                connection.execute(text("""INSERT INTO run_inputs (run_id, ordinal, sha256, size, context, artifact_id)
                    VALUES (:run, :ordinal, :hash, :size, CAST(:context AS jsonb), :artifact)"""),
                    {"run": run_id, "ordinal": ordinal, "hash": image_hash, "size": image_size,
                     "context": json.dumps(context), "artifact": artifact_id})
                connection.execute(text("UPDATE publication_intents SET run_id = :run, state = 'referenced' WHERE id = :id"),
                    {"run": run_id, "id": intent_id})
            for ordinal, name in enumerate(STAGES):
                connection.execute(text("""INSERT INTO analysis_stages (run_id, ordinal, name, state)
                    VALUES (:run, :ordinal, :name, 'pending')"""),
                    {"run": run_id, "ordinal": ordinal, "name": name})
            connection.execute(text("UPDATE submission_requests SET run_id = :run, state = 'accepted' WHERE idempotency_key = :key"),
                {"run": run_id, "key": key})
        return run_id

    def claim_ordinary(self, profile_id: uuid.UUID, revision: int, lease_seconds: int) -> dict | None:
        owner = str(uuid.uuid4())
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.id, r.profile_snapshot, r.requested_classes, r.authorization_revision,
                i.sha256, i.size, a.key, a.id AS artifact_id, i.input_id, i.ordinal
                FROM analysis_runs r JOIN run_inputs i ON i.run_id = r.id AND i.ordinal = 0
                JOIN artifact_metadata a ON a.id = i.artifact_id
                JOIN profile_authorizations auth ON auth.profile_id = r.profile_id
                WHERE r.state = 'queued' AND r.purpose = 'ordinary' AND r.profile_id = :profile
                  AND r.authorization_revision = :revision AND auth.state = 'enabled' AND auth.revision = :revision
                ORDER BY r.id FOR UPDATE OF r SKIP LOCKED LIMIT 1"""),
                {"profile": profile_id, "revision": revision}).one_or_none()
            if not row:
                return None
            connection.execute(text("""UPDATE analysis_runs SET state = 'running', lease_owner = :owner,
                lease_expires_at = clock_timestamp() + (:seconds * interval '1 second') WHERE id = :run"""),
                {"run": row.id, "owner": owner, "seconds": lease_seconds})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 0"), {"run": row.id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 1"), {"run": row.id})
            frames = connection.execute(text("""SELECT i.input_id, i.ordinal, i.sha256, i.size,
                a.key, a.id AS artifact_id FROM run_inputs i JOIN artifact_metadata a ON a.id = i.artifact_id
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": row.id}).mappings().all()
            return {**row._mapping, "owner": owner, "frames": [dict(frame) for frame in frames]}

    def renew_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, lease_seconds: int) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs r SET lease_expires_at = clock_timestamp() + (:seconds * interval '1 second')
                FROM profile_authorizations a WHERE r.id = :run AND r.profile_id = a.profile_id AND r.purpose = 'ordinary'
                AND r.state = 'running' AND r.lease_owner = :owner AND r.lease_expires_at > clock_timestamp()
                AND r.authorization_revision = :revision AND a.state = 'enabled' AND a.revision = :revision"""),
                {"run": run_id, "owner": owner, "revision": revision, "seconds": lease_seconds})
            if changed.rowcount != 1:
                raise AdmissionStoreError("ordinary_lease_rejected")

    def reserve_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, image_hash: str,
                         call_provider: bool = True, input_id: uuid.UUID | None = None) -> uuid.UUID | None:
        invocation = uuid.uuid4()
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.state, r.lease_owner, r.lease_expires_at > clock_timestamp() AS live,
                r.authorization_revision, a.state AS auth_state, a.revision AS auth_revision, i.sha256, i.input_id
                FROM analysis_runs r JOIN profile_authorizations a ON a.profile_id = r.profile_id
                JOIN run_inputs i ON i.run_id = r.id AND i.input_id = COALESCE(:input_id, (SELECT input_id FROM run_inputs WHERE run_id = :run AND ordinal = 0))
                WHERE r.id = :run FOR UPDATE OF r, a"""), {"run": run_id, "input_id": input_id}).one_or_none()
            if (not row or row.state != "running" or row.lease_owner != owner or not row.live
                    or row.authorization_revision != revision or row.auth_state != "enabled"
                    or row.auth_revision != revision or row.sha256 != image_hash):
                raise AdmissionStoreError("ordinary_reservation_rejected")
            existing = connection.execute(text("SELECT 1 FROM observations WHERE run_id = :run AND input_id = :input_id LIMIT 1"),
                                          {"run": run_id, "input_id": row.input_id}).first()
            if existing:
                raise AdmissionStoreError("ordinary_reservation_rejected")
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 1 AND state = 'running'"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 2 AND state = 'pending'"), {"run": run_id})
            if call_provider:
                connection.execute(text("""INSERT INTO observer_invocations
                (id, run_id, input_id, fence, profile_id, authorization_revision, stage_ordinal, input_sha256,
                 intended_request_identity, state)
                SELECT :id, :run, :input_id, 1, profile_id, :revision, 2, :hash, 'local-grounding-dino-cpu', 'reserved'
                FROM analysis_runs WHERE id = :run"""),
                {"id": invocation, "run": run_id, "input_id": row.input_id,
                 "revision": revision, "hash": image_hash})
        return invocation if call_provider else None

    def finish_ordinary(self, run_id: uuid.UUID, owner: str, revision: int, invocation: uuid.UUID | None,
                        result: dict | None, native_intent: uuid.UUID | None, observations: list[dict],
                        input_id: uuid.UUID | None = None, batch_deadline: float | None = None) -> None:
        with self.engine.begin() as connection:
            row = connection.execute(text("""SELECT r.profile_snapshot, r.state, r.lease_owner,
                r.lease_expires_at > clock_timestamp() AS live, r.authorization_revision,
                a.state AS auth_state, a.revision AS auth_revision, i.state AS invocation_state
                FROM analysis_runs r JOIN profile_authorizations a ON a.profile_id = r.profile_id
                LEFT JOIN observer_invocations i ON i.run_id = r.id AND i.id = :invocation
                WHERE r.id = :run FOR UPDATE OF r, a"""), {"run": run_id, "invocation": invocation}).one_or_none()
            if (not row or row.state != "running" or row.lease_owner != owner or not row.live
                    or row.authorization_revision != revision or row.auth_state != "enabled" or row.auth_revision != revision):
                raise AdmissionStoreError("ordinary_completion_rejected")
            expected_classes = connection.execute(text("SELECT requested_classes FROM analysis_runs WHERE id = :run"), {"run": run_id}).scalar_one()
            source = connection.execute(text("""SELECT input_id, ordinal, artifact_id, sha256 FROM run_inputs
                WHERE run_id = :run AND input_id = COALESCE(:input_id,
                    (SELECT input_id FROM run_inputs WHERE run_id = :run AND ordinal = 0))"""),
                {"run": run_id, "input_id": input_id}).one_or_none()
            if source is None:
                raise AdmissionStoreError("ordinary_completion_rejected")
            source_artifact_id = source.artifact_id
            if (len(observations) != len(expected_classes)
                    or {item["class_name"] for item in observations} != set(expected_classes)
                    or any(item["source_artifact_id"] != str(source_artifact_id) for item in observations)
                    or connection.execute(text("SELECT 1 FROM observations WHERE run_id = :run AND input_id = :input_id LIMIT 1"),
                                          {"run": run_id, "input_id": source.input_id}).first() is not None
                    or (invocation is not None and connection.execute(text("SELECT input_id FROM observer_invocations WHERE id = :id"),
                        {"id": invocation}).scalar_one_or_none() != source.input_id)
                    or (result is None) != (invocation is None)
                    or (result is None and any(item["state"] not in ("insufficient_data", "not_analyzed") for item in observations))):
                raise AdmissionStoreError("observation_normalization_failed")
            native_artifact_id = None
            if result is not None:
                expected = row.profile_snapshot["model_files"]["model.safetensors"]
                if (row.invocation_state != "reserved" or result.get("returned_model_identity") != f"checkpoint-sha256:{expected}"
                        or result.get("actual_device") != "cpu" or result.get("preprocessing_revision") != grounding_dino.PREPROCESSING_REVISION):
                    raise AdmissionStoreError("observer_identity_or_device_invalid")
                intent = connection.execute(text("""SELECT * FROM publication_intents WHERE id = :id AND run_id = :run
                    AND state = 'object_published' FOR UPDATE"""), {"id": native_intent, "run": run_id}).one_or_none()
                if not intent:
                    raise AdmissionStoreError("publication_incomplete")
                native_artifact_id = uuid.uuid4()
                connection.execute(text("""INSERT INTO artifact_metadata (id, run_id, intent_id, key, sha256, size, media_type)
                    VALUES (:id, :run, :intent, :key, :hash, :size, :media)"""),
                    {"id": native_artifact_id, "run": run_id, "intent": native_intent, "key": intent.final_key,
                     "hash": intent.sha256, "size": intent.size, "media": intent.media_type})
                connection.execute(text("""UPDATE observer_invocations SET state = 'completed',
                    returned_model_identity = :identity, actual_device = 'cpu', preprocessing_revision = :pre,
                    native_artifact_id = :artifact WHERE id = :id AND state = 'reserved'"""),
                    {"identity": result["returned_model_identity"], "pre": result["preprocessing_revision"],
                     "artifact": native_artifact_id, "id": invocation})
                connection.execute(text("""UPDATE analysis_runs SET latency_ms = COALESCE(latency_ms, 0) + :latency,
                    peak_memory_bytes = GREATEST(COALESCE(peak_memory_bytes, 0), :memory) WHERE id = :run"""),
                    {"latency": result["latency_ms"], "memory": result["peak_memory_bytes"], "run": run_id})
                connection.execute(text("UPDATE publication_intents SET state = 'referenced' WHERE id = :id"), {"id": native_intent})
            for observation in observations:
                connection.execute(text("""INSERT INTO observations
                    (run_id, input_id, class_name, state, reason, input_sha256, invocation_id, source_artifact_id)
                    VALUES (:run, :input_id, :class_name, :state, :reason, :hash, :invocation, :source_artifact_id)"""),
                    {"run": run_id, "input_id": source.input_id, "hash": source.sha256,
                     "invocation": invocation, **observation})
            inputs = connection.execute(text("SELECT count(*) FROM run_inputs WHERE run_id = :run"), {"run": run_id}).scalar_one()
            completed = connection.execute(text("""SELECT count(DISTINCT input_id) FROM observations
                WHERE run_id = :run"""), {"run": run_id}).scalar_one()
            if completed != inputs:
                if batch_deadline is not None and monotonic() >= batch_deadline:
                    raise RuntimeError("observer_timeout")
                return
            if connection.execute(text("SELECT count(*) FROM observations WHERE run_id = :run"),
                                  {"run": run_id}).scalar_one() != inputs * len(expected_classes):
                raise AdmissionStoreError("observation_incomplete")
            if connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run AND state != 'completed'"),
                                  {"run": run_id}).scalar_one():
                raise AdmissionStoreError("observation_incomplete")
            calls = connection.execute(text("SELECT count(*) FROM observer_invocations WHERE run_id = :run"),
                                       {"run": run_id}).scalar_one()
            connection.execute(text("""UPDATE analysis_stages SET state = :state, reason = :reason
                WHERE run_id = :run AND ordinal = 2 AND state = 'running'"""),
                {"run": run_id, "state": "succeeded" if calls else "skipped",
                 "reason": None if calls else "no_assessable_frame_or_supported_class"})
            connection.execute(text("""UPDATE analysis_stages SET state = :state, reason = :reason
                WHERE run_id = :run AND ordinal = 3"""),
                {"run": run_id, "state": "succeeded" if inputs > 1 else "skipped",
                 "reason": None if inputs > 1 else "not_applicable"})
            connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'not_applicable' WHERE run_id = :run AND ordinal = 4"), {"run": run_id})
            connection.execute(text("UPDATE analysis_stages SET state = 'running' WHERE run_id = :run AND ordinal = 5"), {"run": run_id})
            evidence = connection.execute(text("""SELECT i.input_id, i.ordinal, o.class_name, o.state, o.reason,
                o.source_artifact_id, o.invocation_id FROM run_inputs i JOIN observations o
                ON o.run_id = i.run_id AND o.input_id = i.input_id
                WHERE i.run_id = :run ORDER BY i.ordinal, o.class_name"""), {"run": run_id}).mappings().all()
            usable = connection.execute(text("""SELECT i.input_id FROM run_inputs i JOIN observer_invocations v
                ON v.run_id = i.run_id AND v.input_id = i.input_id AND v.state = 'completed'
                WHERE i.run_id = :run ORDER BY i.ordinal"""), {"run": run_id}).scalars().all()
            usable_ids = [str(item) for item in usable]
            excavator_ids = [str(item["input_id"]) for item in evidence
                             if item["class_name"] == "excavator" and item["state"] == "detected"]
            dump_truck_ids = [str(item["input_id"]) for item in evidence
                              if item["class_name"] == "dump_truck" and item["state"] == "not_detected_in_frame"
                              and str(item["input_id"]) in usable_ids]
            area = connection.execute(text("SELECT request_context->>'observation_area' FROM analysis_runs WHERE id = :run"),
                                      {"run": run_id}).scalar_one()
            series = {"usable_count": len(usable_ids), "usable_input_ids": usable_ids,
                      "declared_observation_area": area,
                      "input_order": [str(item["input_id"]) for item in sorted(evidence, key=lambda item: item["ordinal"])
                                      if item["class_name"] == expected_classes[0]],
                      "excavator_supporting_input_ids": excavator_ids,
                      "dump_truck_persistence_input_ids": dump_truck_ids if len(usable_ids) > 1 and len(dump_truck_ids) == len(usable_ids) else [],
                      "dump_truck_persistence_text": (f"Самосвал не обнаружен ни в одном из {len(usable_ids)} пригодных кадров."
                          if "dump_truck" in expected_classes and len(usable_ids) > 1 and len(dump_truck_ids) == len(usable_ids) else None)}
            projection = {"outcome": "observations_only", "frames": [
                {**dict(item), "input_id": str(item["input_id"]),
                 "source_artifact_id": str(item["source_artifact_id"]),
                 "invocation_id": str(item["invocation_id"]) if item["invocation_id"] else None}
                for item in evidence], "series": series}
            connection.execute(text("""INSERT INTO result_projections (run_id, outcome, snapshot)
                VALUES (:run, 'observations_only', CAST(:snapshot AS jsonb))"""),
                {"run": run_id, "snapshot": json.dumps(projection)})
            connection.execute(text("UPDATE analysis_stages SET state = 'succeeded' WHERE run_id = :run AND ordinal = 5"), {"run": run_id})
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'succeeded', lease_owner = NULL,
                lease_expires_at = NULL WHERE id = :run AND state = 'running' AND lease_owner = :owner
                AND lease_expires_at > clock_timestamp()"""), {"run": run_id, "owner": owner})
            if changed.rowcount != 1:
                raise AdmissionStoreError("ordinary_completion_rejected")
            if batch_deadline is not None and monotonic() >= batch_deadline:
                raise RuntimeError("observer_timeout")

    def fail_ordinary(self, run_id: uuid.UUID, owner: str, code: str) -> None:
        with self.engine.begin() as connection:
            changed = connection.execute(text("""UPDATE analysis_runs SET state = 'failed', error_code = :code,
                lease_owner = NULL, lease_expires_at = NULL WHERE id = :run AND state = 'running'
                AND lease_owner = :owner AND lease_expires_at > clock_timestamp()"""),
                {"run": run_id, "owner": owner, "code": code})
            if changed.rowcount:
                connection.execute(text("UPDATE observer_invocations SET state = 'failed' WHERE run_id = :run AND state = 'reserved'"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = :code WHERE run_id = :run AND state = 'running'"), {"run": run_id, "code": code})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND state = 'pending'"), {"run": run_id})

    def fail_unauthorized_queued(self) -> None:
        with self.engine.begin() as connection:
            rows = connection.execute(text("""SELECT r.id FROM analysis_runs r
                LEFT JOIN profile_authorizations a ON a.profile_id = r.profile_id
                WHERE r.purpose = 'ordinary' AND r.state = 'queued'
                  AND (a.state IS DISTINCT FROM 'enabled' OR a.revision IS DISTINCT FROM r.authorization_revision)
                FOR UPDATE OF r SKIP LOCKED""")).scalars().all()
            for run_id in rows:
                connection.execute(text("UPDATE analysis_runs SET state = 'failed', error_code = 'profile_unauthorized' WHERE id = :run"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'profile_unauthorized' WHERE run_id = :run AND ordinal = 0"), {"run": run_id})
                connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :run AND ordinal > 0"), {"run": run_id})

    def read_ordinary(self, run_id: uuid.UUID) -> dict | None:
        with self.engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            row = connection.execute(text("""SELECT id, state, error_code, request_context, requested_classes
                FROM analysis_runs WHERE id = :id AND purpose = 'ordinary'"""), {"id": run_id}).one_or_none()
            if not row:
                return None
            stages = connection.execute(text("SELECT name, state, reason FROM analysis_stages WHERE run_id = :id ORDER BY ordinal"), {"id": run_id}).mappings().all()
            inputs = connection.execute(text("""SELECT input_id, ordinal, sha256, size, artifact_id
                FROM run_inputs WHERE run_id = :id ORDER BY ordinal"""), {"id": run_id}).mappings().all()
            observations = connection.execute(text("""SELECT o.class_name, o.state, o.reason, o.input_sha256,
                o.source_artifact_id, o.input_id, i.ordinal, o.invocation_id
                FROM observations o JOIN run_inputs i ON i.input_id = o.input_id
                WHERE o.run_id = :id ORDER BY i.ordinal, o.class_name"""), {"id": run_id}).mappings().all()
            projection = connection.execute(text("SELECT snapshot FROM result_projections WHERE run_id = :id"), {"id": run_id}).scalar_one_or_none()
            native = connection.execute(text("""SELECT a.id, a.sha256, a.size, i.input_id, i.id AS invocation_id,
                i.preprocessing_revision, i.authorization_revision, i.profile_id, r.ordinal
                FROM observer_invocations i JOIN artifact_metadata a ON a.id = i.native_artifact_id
                JOIN run_inputs r ON r.input_id = i.input_id
                WHERE i.run_id = :id ORDER BY r.ordinal"""), {"id": run_id}).mappings().all()
            return {"run_id": str(row.id), "state": row.state, "error_code": row.error_code,
                    "context": row.request_context, "requested_classes": row.requested_classes,
                    "stages": [dict(item) for item in stages],
                    "inputs": [{**item, "input_id": str(item["input_id"]),
                                "artifact_id": str(item["artifact_id"]) if item["artifact_id"] else None}
                               for item in inputs],
                    "observations": [{**item, "input_id": str(item["input_id"]),
                                      "source_artifact_id": str(item["source_artifact_id"]) if item["source_artifact_id"] else None,
                                      "invocation_id": str(item["invocation_id"]) if item["invocation_id"] else None}
                                     for item in observations],
                    "native_evidence": ({"artifact_id": str(native[0]["id"]), "sha256": native[0]["sha256"],
                                         "size": native[0]["size"]} if len(inputs) == 1 and native else None),
                    "native_evidence_by_frame": [{"artifact_id": str(item["id"]), "sha256": item["sha256"],
                                                  "size": item["size"], "ordinal": item["ordinal"],
                                                  "input_id": str(item["input_id"]), "invocation_id": str(item["invocation_id"]),
                                                  "profile_id": str(item["profile_id"]), "profile_revision": item["authorization_revision"],
                                                  "preprocessing_revision": item["preprocessing_revision"]} for item in native],
                    "outcome": projection["outcome"] if projection and row.state == "succeeded" else None,
                    "result_projection": projection if projection and row.state == "succeeded" else None}

    def resolve_run_artifact(self, run_id: uuid.UUID, artifact_id: uuid.UUID) -> dict | None:
        with self.engine.connect() as connection:
            row = connection.execute(text("""SELECT a.key, a.sha256, a.size, a.media_type FROM artifact_metadata a
                JOIN analysis_runs r ON r.id = a.run_id AND r.purpose = 'ordinary'
                WHERE a.run_id = :run AND a.id = :artifact AND
                  (EXISTS (SELECT 1 FROM run_inputs i WHERE i.run_id = :run AND i.artifact_id = a.id)
                   OR EXISTS (SELECT 1 FROM observer_invocations v WHERE v.run_id = :run AND v.native_artifact_id = a.id))"""),
                {"run": run_id, "artifact": artifact_id}).mappings().one_or_none()
            return dict(row) if row else None

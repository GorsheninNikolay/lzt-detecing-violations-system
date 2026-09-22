from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


class DatabaseGateError(RuntimeError):
    pass


class ReconciliationGateError(RuntimeError):
    pass


class RecoveryGateError(RuntimeError):
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

    def reconcile(self) -> None:
        observed_count = 0
        try:
            with self.engine.begin() as connection:
                locked = connection.execute(text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": LOCK_ID}).scalar_one()
                if not locked:
                    raise ReconciliationGateError("reconciliation_lock_unavailable")
                counts = connection.execute(text("SELECT state, count(*) FROM publication_intents GROUP BY state")).all()
                observed_count = sum(row[1] for row in counts)
                if counts:
                    raise ReconciliationGateError("reconciliation_pending_intents")
                connection.execute(text("INSERT INTO reconciliation_runs (started_at, completed_at, intent_count, status) VALUES (clock_timestamp(), clock_timestamp(), :count, 'succeeded')"), {"count": observed_count})
        except ReconciliationGateError as exc:
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

    def recover(self) -> None:
        try:
            with self.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '1s'"))
                rows = connection.execute(text("SELECT id, lease_expires_at, clock_timestamp() AS db_now FROM analysis_runs WHERE state = 'running' AND (lease_expires_at IS NULL OR lease_expires_at <= clock_timestamp()) FOR UPDATE NOWAIT")).all()
                for run_id, expiry, db_now in rows:
                    if expiry is None:
                        raise RecoveryGateError("recovery_unknown_ownership")
                    if expiry > db_now:
                        continue
                    updated = connection.execute(text("UPDATE analysis_runs SET state = 'failed', error_code = 'executor_interrupted', lease_owner = NULL, lease_expires_at = NULL WHERE id = :id AND state = 'running' AND lease_expires_at <= clock_timestamp()"), {"id": run_id})
                    if updated.rowcount != 1:
                        raise RecoveryGateError("recovery_lease_changed")
                    connection.execute(text("UPDATE analysis_stages SET state = 'failed', reason = 'executor_interrupted' WHERE run_id = :id AND state = 'running'"), {"id": run_id})
                    connection.execute(text("UPDATE analysis_stages SET state = 'skipped', reason = 'dependency_failed' WHERE run_id = :id AND state = 'pending'"), {"id": run_id})
        except RecoveryGateError:
            raise
        except Exception:
            raise RecoveryGateError("recovery_gate_failed") from None

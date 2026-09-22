"""Admission evidence and immutable observer bindings."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0002_admission"
down_revision = "0001_seed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "observer_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("parent_id", UUID(as_uuid=True), sa.ForeignKey("observer_profiles.id")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("profile_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("audit_hash", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('draft', 'admitted', 'rejected')"),
        sa.CheckConstraint("(status = 'admitted') = (parent_id IS NOT NULL AND audit_hash IS NOT NULL)"),
    )
    op.create_table(
        "profile_authorizations",
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("observer_profiles.id"), primary_key=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("audit_hash", sa.Text(), nullable=False),
        sa.Column("interactive_retry_allowed", sa.Boolean(), nullable=False),
        sa.CheckConstraint("state IN ('enabled', 'revoked')"),
    )
    op.create_table(
        "admission_fixture_sets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("manifest_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("manifest", JSONB, nullable=False),
    )
    op.add_column("analysis_runs", sa.Column("purpose", sa.Text(), nullable=False, server_default="ordinary"))
    op.add_column("analysis_runs", sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("observer_profiles.id")))
    op.add_column("analysis_runs", sa.Column("authorization_revision", sa.BigInteger()))
    op.add_column("analysis_runs", sa.Column("binding_kind", sa.Text()))
    op.add_column("analysis_runs", sa.Column("fixture_set_id", UUID(as_uuid=True), sa.ForeignKey("admission_fixture_sets.id")))
    op.add_column("analysis_runs", sa.Column("fixture_id", sa.Text()))
    op.add_column("analysis_runs", sa.Column("bootstrap_watchdog_seconds", sa.Integer()))
    op.add_column("analysis_runs", sa.Column("profile_snapshot", JSONB))
    op.add_column("analysis_runs", sa.Column("latency_ms", sa.Float()))
    op.add_column("analysis_runs", sa.Column("peak_memory_bytes", sa.BigInteger()))
    op.add_column("analysis_stages", sa.Column("name", sa.Text()))
    op.create_table(
        "run_inputs",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("ordinal", sa.Integer(), primary_key=True),
        sa.Column("fixture_id", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("context", JSONB, nullable=False),
    )
    op.create_table(
        "observer_invocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), nullable=False, unique=True),
        sa.Column("fence", sa.BigInteger(), nullable=False),
        sa.Column("profile_id", UUID(as_uuid=True), sa.ForeignKey("observer_profiles.id"), nullable=False),
        sa.Column("authorization_revision", sa.BigInteger()),
        sa.Column("stage_ordinal", sa.SmallInteger(), nullable=False),
        sa.Column("input_sha256", sa.Text(), nullable=False),
        sa.Column("intended_request_identity", sa.Text(), nullable=False),
        sa.Column("returned_model_identity", sa.Text()),
        sa.Column("returned_request_identity", sa.Text()),
        sa.Column("actual_device", sa.Text()),
        sa.Column("preprocessing_revision", sa.Text()),
        sa.Column("native_artifact_id", UUID(as_uuid=True)),
        sa.Column("state", sa.Text(), nullable=False),
        sa.CheckConstraint("state IN ('reserved', 'completed', 'failed')"),
    )
    op.create_table(
        "artifact_metadata",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), nullable=False),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("publication_intents.id"), nullable=False, unique=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("media_type", sa.Text(), nullable=False),
    )
    op.create_table(
        "observations",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("class_name", sa.Text(), primary_key=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("input_sha256", sa.Text(), nullable=False),
        sa.Column("invocation_id", UUID(as_uuid=True), sa.ForeignKey("observer_invocations.id"), nullable=False),
        sa.CheckConstraint("class_name IN ('excavator', 'dump_truck')"),
        sa.CheckConstraint("state IN ('detected', 'not_detected_in_frame', 'insufficient_data', 'not_analyzed')"),
    )
    op.create_table(
        "result_projections",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.CheckConstraint("outcome = 'observations_only'"),
    )
    for name, type_, nullable in (
        ("run_id", UUID(as_uuid=True), False), ("idempotency_key", sa.Text(), False),
        ("media_type", sa.Text(), False), ("sha256", sa.Text(), True),
        ("size", sa.BigInteger(), True), ("final_key", sa.Text(), True),
        ("error_code", sa.Text(), True),
    ):
        op.add_column("publication_intents", sa.Column(name, type_, nullable=nullable))
    op.create_foreign_key("publication_intents_run_id_fkey", "publication_intents", "analysis_runs", ["run_id"], ["id"])
    op.create_unique_constraint("publication_intents_idempotency_key_key", "publication_intents", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("publication_intents_idempotency_key_key", "publication_intents")
    op.drop_constraint("publication_intents_run_id_fkey", "publication_intents")
    for name in ("error_code", "final_key", "size", "sha256", "media_type", "idempotency_key", "run_id"):
        op.drop_column("publication_intents", name)
    for table in ("result_projections", "observations", "artifact_metadata", "observer_invocations", "run_inputs"):
        op.drop_table(table)
    op.drop_column("analysis_stages", "name")
    for name in ("peak_memory_bytes", "latency_ms", "profile_snapshot", "bootstrap_watchdog_seconds", "fixture_id", "fixture_set_id", "binding_kind", "authorization_revision", "profile_id", "purpose"):
        op.drop_column("analysis_runs", name)
    op.drop_table("admission_fixture_sets")
    op.drop_table("profile_authorizations")
    op.drop_table("observer_profiles")

"""Persist public, source-bound bounding boxes without rewriting old runs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0015_detected_objects"
down_revision = "0014_site_plan"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "detected_objects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("input_id", UUID(as_uuid=True), nullable=False),
        sa.Column("invocation_id", UUID(as_uuid=True), sa.ForeignKey("observer_invocations.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("class_name", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("box", JSONB, nullable=False),
        sa.Column("image_size", JSONB, nullable=False),
        sa.ForeignKeyConstraint(["run_id", "input_id"], ["run_inputs.run_id", "run_inputs.input_id"]),
        sa.UniqueConstraint("run_id", "input_id", "ordinal"),
        sa.CheckConstraint("score >= 0 AND score <= 1"),
    )
    op.create_table(
        "detected_scene_features",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), nullable=False),
        sa.Column("input_id", UUID(as_uuid=True), nullable=False),
        sa.Column("invocation_id", UUID(as_uuid=True), sa.ForeignKey("observer_invocations.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("feature_name", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["run_id", "input_id"], ["run_inputs.run_id", "run_inputs.input_id"]),
        sa.UniqueConstraint("run_id", "input_id", "ordinal"),
        sa.CheckConstraint("score >= 0 AND score <= 1"),
    )
    op.create_table(
        "run_plan_bindings",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("site_zones.id"), nullable=False),
        sa.Column("revision_id", UUID(as_uuid=True), sa.ForeignKey("zone_plan_revisions.id"), nullable=False),
        sa.Column("frame_times", JSONB, nullable=False),
    )
    op.create_table(
        "stage_confirmations",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("stage", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
    )
    op.create_table(
        "site_signals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("fingerprint", sa.Text(), nullable=False, unique=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id")),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("site_zones.id"), nullable=False),
        sa.Column("revision_id", UUID(as_uuid=True), sa.ForeignKey("zone_plan_revisions.id"), nullable=False),
        sa.Column("work_entry_id", UUID(as_uuid=True), sa.ForeignKey("zone_plan_entries.id")),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False, server_default="new"),
        sa.Column("basis", JSONB, nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("state IN ('new', 'in_progress', 'closed')"),
    )
    for table in ("detected_objects", "detected_scene_features", "run_plan_bindings", "stage_confirmations"):
        op.execute(f"""CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$""")
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()")
    op.execute("""CREATE FUNCTION guard_site_signal_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'site_signal_basis_immutable';
            END IF;
            IF NEW.id IS DISTINCT FROM OLD.id OR NEW.fingerprint IS DISTINCT FROM OLD.fingerprint
               OR NEW.run_id IS DISTINCT FROM OLD.run_id
               OR NEW.zone_id IS DISTINCT FROM OLD.zone_id
               OR NEW.revision_id IS DISTINCT FROM OLD.revision_id
               OR NEW.work_entry_id IS DISTINCT FROM OLD.work_entry_id
               OR NEW.kind IS DISTINCT FROM OLD.kind
               OR NEW.basis IS DISTINCT FROM OLD.basis
               OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
                RAISE EXCEPTION 'site_signal_basis_immutable';
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER site_signal_basis_guard BEFORE UPDATE OR DELETE ON site_signals
        FOR EACH ROW EXECUTE FUNCTION guard_site_signal_update()""")


def downgrade() -> None:
    if any(op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first()
           for table in ("detected_objects", "detected_scene_features", "run_plan_bindings",
                         "stage_confirmations", "site_signals")):
        raise RuntimeError("detected_object_evidence_exists")
    op.execute("DROP TRIGGER site_signal_basis_guard ON site_signals")
    op.execute("DROP FUNCTION guard_site_signal_update()")
    for table in ("detected_objects", "detected_scene_features", "run_plan_bindings", "stage_confirmations"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION reject_{table}_mutation()")
    op.drop_table("site_signals")
    op.drop_table("stage_confirmations")
    op.drop_table("run_plan_bindings")
    op.drop_table("detected_scene_features")
    op.drop_table("detected_objects")

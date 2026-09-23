"""Single-image submission and source-linked observations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0003_single_image"
down_revision = "0002_admission"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("request_context", JSONB))
    op.add_column("analysis_runs", sa.Column("policy_snapshot", JSONB))
    op.add_column("analysis_runs", sa.Column("taxonomy_snapshot", JSONB))
    op.add_column("analysis_runs", sa.Column("requested_classes", JSONB))
    op.add_column("run_inputs", sa.Column("artifact_id", UUID(as_uuid=True), sa.ForeignKey("artifact_metadata.id")))
    op.alter_column("run_inputs", "fixture_id", nullable=True)
    op.add_column("observations", sa.Column("reason", sa.Text()))
    op.add_column("observations", sa.Column("source_artifact_id", UUID(as_uuid=True), sa.ForeignKey("artifact_metadata.id")))
    op.alter_column("observations", "invocation_id", nullable=True)
    op.drop_constraint("observations_class_name_check", "observations", type_="check")
    op.create_check_constraint("observations_reason_check", "observations",
        "(state IN ('insufficient_data', 'not_analyzed')) = (reason IS NOT NULL)")
    op.alter_column("publication_intents", "run_id", nullable=True)
    op.create_table("submission_requests",
        sa.Column("idempotency_key", sa.Text(), primary_key=True),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id")),
        sa.Column("intent_id", UUID(as_uuid=True), sa.ForeignKey("publication_intents.id")),
        sa.Column("error_code", sa.Text()),
        sa.CheckConstraint("state IN ('publishing', 'accepted', 'failed')"),
        sa.CheckConstraint("(state = 'accepted') = (run_id IS NOT NULL)"),
    )


def downgrade() -> None:
    op.drop_table("submission_requests")
    op.alter_column("publication_intents", "run_id", nullable=False)
    op.drop_constraint("observations_reason_check", "observations", type_="check")
    op.create_check_constraint("observations_class_name_check", "observations", "class_name IN ('excavator', 'dump_truck')")
    op.drop_column("observations", "source_artifact_id")
    op.drop_column("observations", "reason")
    op.alter_column("observations", "invocation_id", nullable=False)
    op.alter_column("run_inputs", "fixture_id", nullable=False)
    op.drop_column("run_inputs", "artifact_id")
    for name in ("requested_classes", "taxonomy_snapshot", "policy_snapshot", "request_context"):
        op.drop_column("analysis_runs", name)

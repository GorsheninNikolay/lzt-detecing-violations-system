"""Linear failed-run successors and run-local inherited source artifacts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005_retry"
down_revision = "0004_ordered_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("retry_of_run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id")))
    op.execute("ALTER TABLE analysis_runs ADD COLUMN IF NOT EXISTS created_at timestamptz")
    op.alter_column("analysis_runs", "created_at", server_default=sa.text("clock_timestamp()"))
    op.create_unique_constraint("analysis_runs_retry_of_run_id_key", "analysis_runs", ["retry_of_run_id"])
    op.create_index("analysis_runs_ordinary_created_at_idx", "analysis_runs", ["created_at"],
                    postgresql_where=sa.text("purpose = 'ordinary'"))
    op.alter_column("artifact_metadata", "intent_id", nullable=True)
    op.add_column("artifact_metadata", sa.Column("source_artifact_id", UUID(as_uuid=True),
                                                  sa.ForeignKey("artifact_metadata.id")))
    op.create_check_constraint("artifact_metadata_origin_check", "artifact_metadata",
                               "(intent_id IS NOT NULL) <> (source_artifact_id IS NOT NULL)")


def downgrade() -> None:
    op.drop_constraint("artifact_metadata_origin_check", "artifact_metadata", type_="check")
    op.drop_column("artifact_metadata", "source_artifact_id")
    op.alter_column("artifact_metadata", "intent_id", nullable=False)
    op.drop_index("analysis_runs_ordinary_created_at_idx", table_name="analysis_runs")
    op.drop_constraint("analysis_runs_retry_of_run_id_key", "analysis_runs", type_="unique")
    op.drop_column("analysis_runs", "created_at")
    op.drop_column("analysis_runs", "retry_of_run_id")

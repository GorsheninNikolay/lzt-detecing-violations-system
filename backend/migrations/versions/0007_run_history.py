"""Add durable retry lineage for ordinary run history."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0007_run_history"
down_revision = "0006_immutable_run_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("created_at", sa.DateTime(timezone=True)))
    op.alter_column("analysis_runs", "created_at", server_default=sa.text("clock_timestamp()"))
    op.add_column("analysis_runs", sa.Column("retry_predecessor_id", UUID(as_uuid=True),
                                               sa.ForeignKey("analysis_runs.id")))
    op.create_unique_constraint("analysis_runs_retry_predecessor_unique", "analysis_runs", ["retry_predecessor_id"])
    op.create_check_constraint("analysis_runs_retry_not_self", "analysis_runs", "retry_predecessor_id IS DISTINCT FROM id")


def downgrade() -> None:
    op.drop_constraint("analysis_runs_retry_not_self", "analysis_runs", type_="check")
    op.drop_constraint("analysis_runs_retry_predecessor_unique", "analysis_runs", type_="unique")
    op.drop_column("analysis_runs", "retry_predecessor_id")
    op.drop_column("analysis_runs", "created_at")

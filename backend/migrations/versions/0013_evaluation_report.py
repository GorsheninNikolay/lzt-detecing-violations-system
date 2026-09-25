"""Immutable criterion reports for comparison evidence snapshots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0013_evaluation_report"
down_revision = "0012_comparison_completion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("evaluation_reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("comparison_campaigns.id"), nullable=False),
        sa.Column("evaluation_revision_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_set_revisions.id"), nullable=False),
        sa.Column("policy_revision", sa.Text(), nullable=False),
        sa.Column("evidence_digest", sa.Text(), nullable=False),
        sa.Column("content_sha256", sa.Text(), nullable=False),
        sa.Column("content_size", sa.BigInteger(), nullable=False),
        sa.Column("artifact_key", sa.Text(), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("clock_timestamp()")),
        sa.UniqueConstraint("campaign_id", "policy_revision", "evidence_digest"))
    op.create_table("evaluation_report_criteria",
        sa.Column("report_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_reports.id"), primary_key=True),
        sa.Column("criterion_key", sa.Text(), primary_key=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detail", JSONB, nullable=False),
        sa.CheckConstraint("status IN ('pass', 'fail', 'not_evaluated')"))
    for table in ("evaluation_reports", "evaluation_report_criteria"):
        op.execute(f"""CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$""")
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()")


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM evaluation_reports LIMIT 1")).first():
        raise RuntimeError("evaluation_report_evidence_exists")
    for table in ("evaluation_report_criteria", "evaluation_reports"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION reject_{table}_mutation()")
        op.drop_table(table)

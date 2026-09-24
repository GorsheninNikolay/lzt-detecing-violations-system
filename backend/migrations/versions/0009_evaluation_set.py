"""Immutable held-out revisions, freeze decisions, and report bindings."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0009_evaluation_set"
down_revision = "0008_merge_retry_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_set_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("manifest_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("inventory_evidence", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )
    op.create_table(
        "evaluation_freeze_decisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_set_revisions.id")),
        sa.Column("manifest_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("inventory_evidence", JSONB, nullable=False),
        sa.Column("errors", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
        sa.CheckConstraint("status IN ('accepted', 'rejected')"),
        sa.CheckConstraint("(status = 'accepted') = (revision_id IS NOT NULL)"),
    )
    op.create_table(
        "evaluation_report_bindings",
        sa.Column("report_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_set_revisions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")),
    )
    for table in ("evaluation_set_revisions", "evaluation_freeze_decisions", "evaluation_report_bindings"):
        op.execute(f"""CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$""")
        op.execute(f"""CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()""")


def downgrade() -> None:
    for table in ("evaluation_report_bindings", "evaluation_freeze_decisions", "evaluation_set_revisions"):
        op.drop_table(table)
        op.execute(f"DROP FUNCTION reject_{table}_mutation()")

"""Seed startup evidence and future claim namespaces."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001_seed"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("startup_smoke", sa.Column("nonce", UUID(as_uuid=True), primary_key=True))
    op.create_table(
        "publication_intents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.Text(), nullable=False),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.Text()),
    )
    op.create_table(
        "analysis_stages",
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), primary_key=True),
        sa.Column("ordinal", sa.SmallInteger(), primary_key=True),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text()),
    )
    op.create_table(
        "reconciliation_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("intent_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("error_code", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("reconciliation_runs")
    op.drop_table("analysis_stages")
    op.drop_table("analysis_runs")
    op.drop_table("publication_intents")
    op.drop_table("startup_smoke")

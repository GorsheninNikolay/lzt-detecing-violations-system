"""Index ordinary project history without assigning historical evidence."""

from alembic import op

revision = "0016_project_history"
down_revision = "0015_detected_objects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE INDEX ordinary_project_history ON analysis_runs
        ((request_context->>'project_id'), created_at DESC NULLS LAST, id DESC)
        WHERE purpose = 'ordinary'""")


def downgrade() -> None:
    op.drop_index("ordinary_project_history", table_name="analysis_runs")

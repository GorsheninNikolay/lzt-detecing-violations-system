"""Merge published retry and rule/history lineages without losing retries."""

from alembic import op

revision = "0008_merge_retry_history"
down_revision = ("0005_retry", "0007_run_history")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM analysis_runs
                WHERE retry_of_run_id IS NOT NULL
                  AND retry_predecessor_id IS NOT NULL
                  AND retry_of_run_id IS DISTINCT FROM retry_predecessor_id
            ) THEN
                RAISE EXCEPTION 'conflicting_retry_lineage';
            END IF;
        END $$
    """)
    op.execute("""
        UPDATE analysis_runs SET retry_predecessor_id = retry_of_run_id
        WHERE retry_of_run_id IS NOT NULL AND retry_predecessor_id IS NULL
    """)
    op.drop_constraint("analysis_runs_retry_of_run_id_key", "analysis_runs", type_="unique")
    op.drop_column("analysis_runs", "retry_of_run_id")


def downgrade() -> None:
    raise RuntimeError("merging retry histories cannot be reversed without losing lineage")

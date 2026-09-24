"""Bind an explicit analysis intent and permit rule outcomes."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_rule_intent"
down_revision = "0004_ordered_series"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("analysis_intent", sa.Text()))
    op.add_column("analysis_runs", sa.Column("stage_key", sa.Text()))
    op.add_column("analysis_runs", sa.Column("rule_snapshot", JSONB()))
    op.execute("UPDATE analysis_runs SET analysis_intent = 'observation_only' WHERE purpose = 'ordinary'")
    op.create_check_constraint("analysis_runs_intent_check", "analysis_runs",
        "analysis_intent IS NULL OR analysis_intent IN ('observation_only', 'rule_evaluation')")
    op.drop_constraint("result_projections_outcome_check", "result_projections", type_="check")
    op.create_check_constraint("result_projections_outcome_check", "result_projections",
        "outcome IN ('observations_only', 'not_analyzed', 'insufficient_data', 'check_requested', 'no_check')")


def downgrade() -> None:
    op.drop_constraint("result_projections_outcome_check", "result_projections", type_="check")
    op.create_check_constraint("result_projections_outcome_check", "result_projections", "outcome = 'observations_only'")
    op.drop_constraint("analysis_runs_intent_check", "analysis_runs", type_="check")
    op.drop_column("analysis_runs", "rule_snapshot")
    op.drop_column("analysis_runs", "stage_key")
    op.drop_column("analysis_runs", "analysis_intent")

"""Immutable comparison plans and protected planned runs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "0010_comparison_campaign"
down_revision = "0009_evaluation_set"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("comparison_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_number", sa.Integer(), nullable=False, unique=True),
        sa.Column("evaluation_revision_id", UUID(as_uuid=True), sa.ForeignKey("evaluation_set_revisions.id"), nullable=False),
        sa.Column("manifest_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("manifest", JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("clock_timestamp()")))
    op.create_check_constraint("analysis_runs_comparison_binding_check", "analysis_runs",
        "(purpose IS DISTINCT FROM 'comparison_campaign' OR binding_kind IS NOT DISTINCT FROM 'comparison_cell') "
        "AND (binding_kind IS DISTINCT FROM 'comparison_cell' OR purpose IS NOT DISTINCT FROM 'comparison_campaign')")
    op.create_table("comparison_cells",
        sa.Column("campaign_id", UUID(as_uuid=True), sa.ForeignKey("comparison_campaigns.id"), primary_key=True),
        sa.Column("repeat_ordinal", sa.SmallInteger(), primary_key=True),
        sa.Column("fixture_ordinal", sa.SmallInteger(), primary_key=True),
        sa.Column("candidate_ordinal", sa.SmallInteger(), primary_key=True),
        sa.Column("run_id", UUID(as_uuid=True), sa.ForeignKey("analysis_runs.id"), nullable=False, unique=True),
        sa.CheckConstraint("repeat_ordinal BETWEEN 0 AND 2"),
        sa.CheckConstraint("fixture_ordinal BETWEEN 0 AND 5"),
        sa.CheckConstraint("candidate_ordinal BETWEEN 0 AND 1"))
    for table in ("comparison_campaigns", "comparison_cells"):
        op.execute(f"CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ "
                   f"BEGIN RAISE EXCEPTION '{table}_immutable'; END $$")
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()")
    op.execute("""CREATE FUNCTION guard_comparison_run() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) THEN
                    RAISE EXCEPTION 'comparison_run_immutable';
                END IF;
                RETURN OLD;
            END IF;
            IF TG_OP = 'UPDATE' AND EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) THEN
                IF NEW.id IS DISTINCT FROM OLD.id OR NEW.purpose IS DISTINCT FROM OLD.purpose
                   OR NEW.binding_kind IS DISTINCT FROM OLD.binding_kind
                   OR NEW.profile_id IS DISTINCT FROM OLD.profile_id
                   OR NEW.authorization_revision IS DISTINCT FROM OLD.authorization_revision
                   OR NEW.profile_snapshot IS DISTINCT FROM OLD.profile_snapshot
                   OR NEW.request_context IS DISTINCT FROM OLD.request_context
                   OR NEW.policy_snapshot IS DISTINCT FROM OLD.policy_snapshot
                   OR NEW.rule_snapshot IS DISTINCT FROM OLD.rule_snapshot
                   OR NEW.taxonomy_snapshot IS DISTINCT FROM OLD.taxonomy_snapshot
                   OR NEW.requested_classes IS DISTINCT FROM OLD.requested_classes
                   OR NEW.analysis_intent IS DISTINCT FROM OLD.analysis_intent
                   OR NEW.stage_key IS DISTINCT FROM OLD.stage_key
                   OR NEW.state IS DISTINCT FROM OLD.state THEN
                    RAISE EXCEPTION 'comparison_run_immutable';
                END IF;
            END IF;
            RETURN NEW;
        END $$""")
    op.execute("""CREATE TRIGGER comparison_run_guard BEFORE UPDATE OR DELETE ON analysis_runs
        FOR EACH ROW EXECUTE FUNCTION guard_comparison_run()""")
    op.execute("""DO $$ DECLARE definition text;
        BEGIN
            SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
                WHERE conname = 'analysis_runs_rule_binding_complete_check';
            definition := replace(definition, $txt$binding_kind = 'admitted_profile'::text$txt$,
                                  $txt$binding_kind IN ('admitted_profile'::text, 'comparison_cell'::text)$txt$);
            definition := replace(definition, $txt$binding_kind = 'admitted_profile'$txt$,
                                  $txt$binding_kind IN ('admitted_profile', 'comparison_cell')$txt$);
            IF definition NOT LIKE '%comparison_cell%' THEN
                RAISE EXCEPTION 'analysis_run_constraint_unexpected';
            END IF;
            ALTER TABLE analysis_runs DROP CONSTRAINT analysis_runs_rule_binding_complete_check;
            EXECUTE 'ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_rule_binding_complete_check ' || definition;
        END $$""")
    op.execute("""DO $$ DECLARE definition text;
        BEGIN
            SELECT pg_get_functiondef('guard_analysis_run_binding()'::regprocedure) INTO definition;
            definition := replace(definition,
                'NEW.binding_kind IS DISTINCT FROM ''admitted_profile''',
                'NEW.binding_kind NOT IN (''admitted_profile'', ''comparison_cell'')');
            EXECUTE definition;
        END $$""")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM comparison_campaigns LIMIT 1")).first():
        raise RuntimeError("comparison_campaign_evidence_exists")
    op.execute("DROP TRIGGER comparison_run_guard ON analysis_runs")
    op.drop_constraint("analysis_runs_comparison_binding_check", "analysis_runs", type_="check")
    op.execute("DROP FUNCTION guard_comparison_run()")
    for table in ("comparison_cells", "comparison_campaigns"):
        op.drop_table(table)
        op.execute(f"DROP FUNCTION reject_{table}_mutation()")
    op.execute("""DO $$ DECLARE definition text;
        BEGIN
            SELECT pg_get_constraintdef(oid) INTO definition FROM pg_constraint
                WHERE conname = 'analysis_runs_rule_binding_complete_check';
            definition := replace(definition, $txt$binding_kind IN ('admitted_profile'::text, 'comparison_cell'::text)$txt$,
                                  $txt$binding_kind = 'admitted_profile'::text$txt$);
            definition := replace(definition, $txt$binding_kind IN ('admitted_profile', 'comparison_cell')$txt$,
                                  $txt$binding_kind = 'admitted_profile'$txt$);
            ALTER TABLE analysis_runs DROP CONSTRAINT analysis_runs_rule_binding_complete_check;
            EXECUTE 'ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_rule_binding_complete_check ' || definition;
        END $$""")
    op.execute("""DO $$ DECLARE definition text;
        BEGIN
            SELECT pg_get_functiondef('guard_analysis_run_binding()'::regprocedure) INTO definition;
            definition := replace(definition,
                'NEW.binding_kind NOT IN (''admitted_profile'', ''comparison_cell'')',
                'NEW.binding_kind IS DISTINCT FROM ''admitted_profile''');
            EXECUTE definition;
        END $$""")

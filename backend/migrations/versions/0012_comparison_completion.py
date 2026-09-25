"""Require complete evidence before comparison success."""

from alembic import op


revision = "0012_comparison_completion"
down_revision = "0011_comparison_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""CREATE FUNCTION guard_comparison_completion() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE input_count integer; expected_count integer; class_count integer;
    BEGIN
      IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = NEW.id)
         AND OLD.state <> 'succeeded' AND NEW.state = 'succeeded' THEN
        SELECT count(*) INTO input_count FROM run_inputs WHERE run_id = NEW.id;
        SELECT jsonb_array_length(fixture.value->'frames') INTO expected_count
          FROM comparison_cells c JOIN comparison_campaigns p ON p.id = c.campaign_id,
          LATERAL jsonb_array_elements(p.manifest->'fixtures') fixture
          WHERE c.run_id = NEW.id AND (fixture.value->>'ordinal')::integer = c.fixture_ordinal;
        class_count := jsonb_array_length(NEW.requested_classes);
        IF input_count = 0 OR expected_count IS NULL OR input_count <> expected_count
           OR (SELECT count(*) FROM observations WHERE run_id = NEW.id) <> input_count * class_count
           OR (SELECT count(DISTINCT input_id) FROM observations WHERE run_id = NEW.id) <> input_count
           OR EXISTS (SELECT 1 FROM run_inputs i,
              LATERAL jsonb_array_elements_text(NEW.requested_classes) requested(class_name)
              WHERE i.run_id = NEW.id AND NOT EXISTS
                (SELECT 1 FROM observations o WHERE o.run_id = NEW.id
                 AND o.input_id = i.input_id AND o.class_name = requested.class_name))
           OR EXISTS (SELECT 1 FROM observations o WHERE o.run_id = NEW.id
              AND o.invocation_id IS DISTINCT FROM
                (SELECT v.id FROM observer_invocations v
                 WHERE v.run_id = o.run_id AND v.input_id = o.input_id))
           OR (SELECT count(*) FROM result_projections WHERE run_id = NEW.id) <> 1
           OR EXISTS (SELECT 1 FROM result_projections p WHERE p.run_id = NEW.id
              AND (p.snapshot->>'outcome' IS DISTINCT FROM p.outcome
                OR jsonb_array_length(p.snapshot->'frames') IS DISTINCT FROM input_count * class_count))
           OR EXISTS (SELECT 1 FROM observations o WHERE o.run_id = NEW.id AND NOT EXISTS
              (SELECT 1 FROM result_projections p,
                LATERAL jsonb_array_elements(p.snapshot->'frames') frame
               WHERE p.run_id = o.run_id AND frame->>'input_id' = o.input_id::text
                 AND frame->>'class_name' = o.class_name AND frame->>'state' = o.state
                 AND frame->>'source_artifact_id' = o.source_artifact_id::text
                 AND frame->>'invocation_id' IS NOT DISTINCT FROM o.invocation_id::text))
           OR (SELECT count(*) FROM analysis_stages WHERE run_id = NEW.id) <> 6
           OR EXISTS (SELECT 1 FROM analysis_stages WHERE run_id = NEW.id
              AND state NOT IN ('succeeded', 'skipped'))
           OR (SELECT count(*) FROM observer_invocations WHERE run_id = NEW.id) <>
              (CASE WHEN EXISTS (SELECT 1 FROM jsonb_array_elements_text(NEW.requested_classes) requested_class(value)
                WHERE requested_class.value IN ('excavator', 'dump_truck')) THEN input_count ELSE 0 END)
           OR EXISTS (SELECT 1 FROM observer_invocations WHERE run_id = NEW.id AND
              (state <> 'completed' OR provider_settled_at IS NULL OR returned_model_identity IS NULL
               OR actual_device IS NULL OR preprocessing_revision IS NULL OR native_artifact_id IS NULL)) THEN
          RAISE EXCEPTION 'comparison_evidence_incomplete';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER comparison_completion_guard BEFORE UPDATE ON analysis_runs
        FOR EACH ROW EXECUTE FUNCTION guard_comparison_completion()""")
    op.execute("""CREATE FUNCTION guard_completed_comparison_invocation() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.state = 'completed' AND EXISTS
         (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
        RAISE EXCEPTION 'comparison_invocation_immutable';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER completed_comparison_invocation_guard
        BEFORE UPDATE OR DELETE ON observer_invocations
        FOR EACH ROW EXECUTE FUNCTION guard_completed_comparison_invocation()""")


def downgrade() -> None:
    op.execute("DROP TRIGGER completed_comparison_invocation_guard ON observer_invocations")
    op.execute("DROP FUNCTION guard_completed_comparison_invocation()")
    op.execute("DROP TRIGGER comparison_completion_guard ON analysis_runs")
    op.execute("DROP FUNCTION guard_comparison_completion()")

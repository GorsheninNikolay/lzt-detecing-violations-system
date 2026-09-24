"""Enforce complete and immutable rule-run configuration bindings."""

from alembic import op

revision = "0006_immutable_run_configuration"
down_revision = "0005_rule_intent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "analysis_runs_rule_binding_complete_check",
        "analysis_runs",
        """analysis_intent IS DISTINCT FROM 'rule_evaluation' OR ((
            stage_key = 'excavation'
            AND binding_kind = 'admitted_profile'
            AND profile_id IS NOT NULL
            AND authorization_revision IS NOT NULL
            AND profile_snapshot IS NOT NULL
            AND jsonb_typeof(profile_snapshot) = 'object'
            AND request_context IS NOT NULL
            AND jsonb_typeof(request_context) = 'object'
            AND request_context ?& ARRAY['scenario', 'observation_area', 'period']
            AND COALESCE(btrim(request_context->>'scenario'), '') <> ''
            AND COALESCE(btrim(request_context->>'observation_area'), '') <> ''
            AND COALESCE(btrim(request_context->>'period'), '') <> ''
            AND policy_snapshot IS NOT NULL
            AND jsonb_typeof(policy_snapshot) = 'object'
            AND COALESCE(btrim(policy_snapshot->>'revision'), '') <> ''
            AND policy_snapshot ?& ARRAY[
                'revision', 'minimum_usable_same_area_frames', 'classes', 'admission', 'unassessable_frame']
            AND jsonb_typeof(policy_snapshot->'minimum_usable_same_area_frames') = 'number'
            AND policy_snapshot->'minimum_usable_same_area_frames' >= '3'::jsonb
            AND policy_snapshot->>'admission' = 'supported_decodable_images'
            AND policy_snapshot->'classes' = '["excavator", "dump_truck"]'::jsonb
            AND rule_snapshot IS NOT NULL
            AND jsonb_typeof(rule_snapshot) = 'object'
            AND COALESCE(btrim(rule_snapshot->>'revision'), '') <> ''
            AND rule_snapshot ?& ARRAY[
                'name', 'revision', 'expectation', 'provenance', 'recommendation',
                'required_activity_class', 'periodic_arrival_class']
            AND rule_snapshot->>'required_activity_class' = 'excavator'
            AND rule_snapshot->>'periodic_arrival_class' = 'dump_truck'
            AND taxonomy_snapshot IS NOT NULL
            AND jsonb_typeof(taxonomy_snapshot) = 'object'
            AND COALESCE(btrim(taxonomy_snapshot->>'revision'), '') <> ''
            AND taxonomy_snapshot ?& ARRAY['revision', 'portable_classes']
            AND taxonomy_snapshot->'portable_classes' = '["excavator", "dump_truck"]'::jsonb
            AND requested_classes IS NOT NULL
            AND requested_classes @> '["excavator", "dump_truck"]'::jsonb
        ) IS TRUE)""",
    )
    op.execute("""
        CREATE FUNCTION guard_analysis_run_binding() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                IF OLD.request_context IS DISTINCT FROM NEW.request_context
                   OR OLD.profile_id IS DISTINCT FROM NEW.profile_id
                   OR OLD.authorization_revision IS DISTINCT FROM NEW.authorization_revision
                   OR OLD.binding_kind IS DISTINCT FROM NEW.binding_kind
                   OR OLD.profile_snapshot IS DISTINCT FROM NEW.profile_snapshot
                   OR OLD.policy_snapshot IS DISTINCT FROM NEW.policy_snapshot
                   OR OLD.rule_snapshot IS DISTINCT FROM NEW.rule_snapshot
                   OR OLD.analysis_intent IS DISTINCT FROM NEW.analysis_intent
                   OR OLD.stage_key IS DISTINCT FROM NEW.stage_key
                   OR OLD.taxonomy_snapshot IS DISTINCT FROM NEW.taxonomy_snapshot
                   OR OLD.requested_classes IS DISTINCT FROM NEW.requested_classes THEN
                    RAISE EXCEPTION 'analysis_run_binding_immutable'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN NEW;
            END IF;

            IF NEW.analysis_intent = 'rule_evaluation' AND (
                NEW.stage_key IS DISTINCT FROM 'excavation'
                OR NEW.binding_kind IS DISTINCT FROM 'admitted_profile'
                OR NEW.profile_id IS NULL
                OR NEW.authorization_revision IS NULL
                OR NOT EXISTS (
                    SELECT 1 FROM observer_profiles p
                    JOIN profile_authorizations a ON a.profile_id = p.id
                    WHERE p.id = NEW.profile_id AND p.status = 'admitted'
                      AND p.snapshot = NEW.profile_snapshot
                      AND a.state = 'enabled' AND a.revision = NEW.authorization_revision)
                OR NEW.profile_snapshot IS NULL
                OR jsonb_typeof(NEW.profile_snapshot) IS DISTINCT FROM 'object'
                OR COALESCE(btrim(NEW.policy_snapshot->>'revision'), '') = ''
                OR COALESCE(btrim(NEW.rule_snapshot->>'revision'), '') = ''
                OR COALESCE(btrim(NEW.taxonomy_snapshot->>'revision'), '') = ''
                OR jsonb_typeof(NEW.request_context) IS DISTINCT FROM 'object'
                OR NOT (NEW.request_context ?& ARRAY['scenario', 'observation_area', 'period'])
                OR COALESCE(btrim(NEW.request_context->>'scenario'), '') = ''
                OR COALESCE(btrim(NEW.request_context->>'observation_area'), '') = ''
                OR COALESCE(btrim(NEW.request_context->>'period'), '') = ''
                OR NOT (NEW.policy_snapshot ?& ARRAY[
                    'revision', 'minimum_usable_same_area_frames', 'classes', 'admission',
                    'supported_media_types', 'frame_order', 'area_scope', 'unassessable_frame',
                    'observer_inability', 'image_quality_threshold', 'subjective_resolution_threshold', 'visibility_threshold',
                    'object_size_threshold', 'cadence_threshold', 'duration_threshold',
                    'miss_rate_threshold', 'false_detection_threshold', 'stability_threshold'])
                OR jsonb_typeof(NEW.policy_snapshot->'minimum_usable_same_area_frames') IS DISTINCT FROM 'number'
                OR NEW.policy_snapshot->'minimum_usable_same_area_frames' < '3'::jsonb
                OR NEW.policy_snapshot->>'admission' IS DISTINCT FROM 'supported_decodable_images'
                OR NEW.policy_snapshot->'classes' IS DISTINCT FROM '["excavator", "dump_truck"]'::jsonb
                OR NEW.policy_snapshot->'supported_media_types' IS DISTINCT FROM '["image/jpeg"]'::jsonb
                OR NEW.policy_snapshot->>'frame_order' IS DISTINCT FROM 'upload_order'
                OR NEW.policy_snapshot->>'area_scope' IS DISTINCT FROM 'one_declared_observation_area'
                OR NEW.policy_snapshot->>'unassessable_frame' IS DISTINCT FROM 'insufficient_data'
                OR NEW.policy_snapshot->>'observer_inability' IS DISTINCT FROM 'insufficient_data'
                OR NEW.policy_snapshot->'image_quality_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'subjective_resolution_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'visibility_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'object_size_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'cadence_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'duration_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'miss_rate_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'false_detection_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NEW.policy_snapshot->'stability_threshold' IS DISTINCT FROM 'null'::jsonb
                OR NOT (NEW.rule_snapshot ?& ARRAY[
                    'name', 'revision', 'expectation', 'provenance', 'recommendation',
                    'required_activity_class', 'periodic_arrival_class'])
                OR COALESCE(btrim(NEW.rule_snapshot->>'name'), '') = ''
                OR COALESCE(btrim(NEW.rule_snapshot->>'expectation'), '') = ''
                OR COALESCE(btrim(NEW.rule_snapshot->>'provenance'), '') = ''
                OR COALESCE(btrim(NEW.rule_snapshot->>'recommendation'), '') = ''
                OR NEW.rule_snapshot->>'required_activity_class' IS DISTINCT FROM 'excavator'
                OR NEW.rule_snapshot->>'periodic_arrival_class' IS DISTINCT FROM 'dump_truck'
                OR NOT (NEW.taxonomy_snapshot ?& ARRAY['revision', 'portable_classes'])
                OR jsonb_typeof(NEW.taxonomy_snapshot) IS DISTINCT FROM 'object'
                OR NEW.taxonomy_snapshot->'portable_classes' IS DISTINCT FROM '["excavator", "dump_truck"]'::jsonb
                OR NOT (NEW.requested_classes @> '["excavator", "dump_truck"]'::jsonb)
            ) THEN
                RAISE EXCEPTION 'analysis_run_rule_binding_incomplete'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER analysis_runs_binding_guard
            BEFORE INSERT OR UPDATE ON analysis_runs
            FOR EACH ROW EXECUTE FUNCTION guard_analysis_run_binding()
    """)
    op.execute("""
        CREATE FUNCTION guard_accepted_run_input() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                IF EXISTS (
                    SELECT 1 FROM submission_requests
                    WHERE state = 'accepted' AND run_id = OLD.run_id
                ) THEN
                    RAISE EXCEPTION 'accepted_run_manifest_immutable'
                        USING ERRCODE = 'check_violation';
                END IF;
                RETURN OLD;
            END IF;

            IF TG_OP = 'UPDATE' AND EXISTS (
                SELECT 1 FROM submission_requests
                WHERE state = 'accepted' AND run_id = OLD.run_id
            ) THEN
                RAISE EXCEPTION 'accepted_run_manifest_immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            IF EXISTS (
                SELECT 1 FROM submission_requests
                WHERE state = 'accepted' AND run_id = NEW.run_id
            ) THEN
                RAISE EXCEPTION 'accepted_run_manifest_immutable'
                    USING ERRCODE = 'check_violation';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER run_inputs_accepted_guard
            BEFORE INSERT OR UPDATE OR DELETE ON run_inputs
            FOR EACH ROW EXECUTE FUNCTION guard_accepted_run_input()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER run_inputs_accepted_guard ON run_inputs")
    op.execute("DROP FUNCTION guard_accepted_run_input()")
    op.execute("DROP TRIGGER analysis_runs_binding_guard ON analysis_runs")
    op.execute("DROP FUNCTION guard_analysis_run_binding()")
    op.drop_constraint("analysis_runs_rule_binding_complete_check", "analysis_runs", type_="check")

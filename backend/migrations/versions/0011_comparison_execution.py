"""Guard execution and evidence of frozen comparison cells."""

from alembic import op
import sqlalchemy as sa

revision = "0011_comparison_execution"
down_revision = "0010_comparison_campaign"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analysis_runs", sa.Column("provider_safe_after", sa.DateTime(timezone=True)))
    op.add_column("observer_invocations", sa.Column("provider_settled_at", sa.DateTime(timezone=True)))
    op.execute("""CREATE OR REPLACE FUNCTION guard_comparison_run() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) THEN
          RAISE EXCEPTION 'comparison_run_immutable';
        END IF;
        RETURN OLD;
      END IF;
      IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) THEN
        IF NEW.state IN ('succeeded', 'failed') AND EXISTS
           (SELECT 1 FROM observer_invocations v WHERE v.run_id = OLD.id
            AND v.state = 'reserved' AND v.provider_settled_at IS NULL)
           AND (OLD.provider_safe_after IS NULL OR OLD.provider_safe_after > clock_timestamp()) THEN
          RAISE EXCEPTION 'comparison_provider_may_be_active';
        END IF;
        IF ROW(NEW.id, NEW.purpose, NEW.binding_kind, NEW.profile_id, NEW.authorization_revision,
               NEW.profile_snapshot, NEW.request_context, NEW.policy_snapshot, NEW.rule_snapshot,
               NEW.taxonomy_snapshot, NEW.requested_classes, NEW.analysis_intent, NEW.stage_key,
               NEW.retry_predecessor_id) IS DISTINCT FROM
           ROW(OLD.id, OLD.purpose, OLD.binding_kind, OLD.profile_id, OLD.authorization_revision,
               OLD.profile_snapshot, OLD.request_context, OLD.policy_snapshot, OLD.rule_snapshot,
               OLD.taxonomy_snapshot, OLD.requested_classes, OLD.analysis_intent, OLD.stage_key,
               OLD.retry_predecessor_id)
           OR OLD.state IN ('succeeded', 'failed')
           OR (OLD.state = 'planned' AND NEW.state NOT IN ('planned', 'running', 'failed'))
           OR (OLD.state = 'running' AND NEW.state NOT IN ('running', 'succeeded', 'failed'))
           OR (OLD.state = 'running' AND NEW.state = 'running' AND
               (NEW.lease_owner IS DISTINCT FROM OLD.lease_owner
                OR NEW.lease_expires_at < OLD.lease_expires_at
                OR (NEW.provider_safe_after < OLD.provider_safe_after AND EXISTS
                    (SELECT 1 FROM observer_invocations v WHERE v.run_id = OLD.id
                     AND v.state = 'reserved' AND v.provider_settled_at IS NULL))
                OR (OLD.provider_safe_after IS NOT NULL AND NEW.provider_safe_after IS NULL)))
           OR (NEW.state = 'running' AND (NEW.lease_owner IS NULL OR NEW.lease_expires_at IS NULL))
           OR (NEW.state IN ('succeeded', 'failed') AND
               (NEW.lease_owner IS NOT NULL OR NEW.lease_expires_at IS NOT NULL))
        THEN RAISE EXCEPTION 'comparison_run_immutable'; END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE FUNCTION guard_comparison_input() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE expected jsonb;
    BEGIN
      IF TG_OP IN ('UPDATE', 'DELETE') THEN
        IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
          RAISE EXCEPTION 'comparison_input_immutable';
        END IF;
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = NEW.run_id) THEN
        IF TG_OP = 'UPDATE' OR NOT EXISTS (SELECT 1 FROM analysis_runs
            WHERE id = NEW.run_id AND state = 'planned') THEN
          RAISE EXCEPTION 'comparison_input_immutable';
        END IF;
        SELECT frame.value INTO expected FROM comparison_cells c
          JOIN comparison_campaigns p ON p.id = c.campaign_id,
          LATERAL jsonb_array_elements(p.manifest->'fixtures') fixture,
          LATERAL jsonb_array_elements(fixture.value->'frames') frame
          WHERE c.run_id = NEW.run_id
            AND (fixture.value->>'ordinal')::integer = c.fixture_ordinal
            AND (frame.value->>'ordinal')::integer = NEW.ordinal;
        IF expected IS NULL OR NEW.sha256 IS DISTINCT FROM expected->'image'->>'sha256'
           OR NEW.size IS DISTINCT FROM (expected->'image'->>'size')::bigint
           OR NEW.context IS DISTINCT FROM expected->'context'
           OR NOT EXISTS (SELECT 1 FROM artifact_metadata a
               JOIN publication_intents p ON p.id = a.intent_id WHERE a.id = NEW.artifact_id
               AND a.run_id = NEW.run_id AND a.sha256 = NEW.sha256 AND a.size = NEW.size
               AND a.key = 'sha256/' || NEW.sha256 AND a.media_type = 'image/jpeg'
               AND p.run_id = NEW.run_id AND p.state IN ('object_published', 'referenced')
               AND p.sha256 = a.sha256 AND p.size = a.size AND p.final_key = a.key
               AND p.media_type = a.media_type) THEN
          RAISE EXCEPTION 'comparison_input_mismatch';
        END IF;
      END IF;
      RETURN NEW;
    END $$""")
    op.execute("""CREATE TRIGGER comparison_input_guard BEFORE INSERT OR UPDATE OR DELETE ON run_inputs
        FOR EACH ROW EXECUTE FUNCTION guard_comparison_input()""")
    op.execute("""CREATE FUNCTION guard_comparison_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE old_run uuid; new_run uuid;
    BEGIN
      IF TG_OP <> 'INSERT' THEN old_run := OLD.run_id; END IF;
      IF TG_OP <> 'DELETE' THEN new_run := NEW.run_id; END IF;
      IF TG_TABLE_NAME = 'publication_intents' AND TG_OP <> 'INSERT' THEN
        IF EXISTS (SELECT 1 FROM artifact_metadata a JOIN comparison_cells c ON c.run_id = a.run_id
            WHERE a.intent_id = OLD.id AND
            (EXISTS (SELECT 1 FROM run_inputs i WHERE i.artifact_id = a.id) OR
             EXISTS (SELECT 1 FROM observer_invocations v WHERE v.native_artifact_id = a.id))) THEN
          RAISE EXCEPTION 'comparison_evidence_immutable';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'artifact_metadata' AND TG_OP <> 'INSERT' AND
         EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
        IF EXISTS (SELECT 1 FROM run_inputs WHERE artifact_id = OLD.id) OR
           EXISTS (SELECT 1 FROM observer_invocations WHERE native_artifact_id = OLD.id) THEN
          RAISE EXCEPTION 'comparison_evidence_immutable';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'observer_invocations' AND TG_OP = 'DELETE' THEN
        IF OLD.state = 'reserved' AND
           EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
          RAISE EXCEPTION 'comparison_invocation_immutable';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'observer_invocations' AND TG_OP = 'UPDATE' THEN
        IF NEW.state = 'completed' AND NEW.provider_settled_at IS NULL AND
           EXISTS (SELECT 1 FROM comparison_cells WHERE run_id IN (OLD.run_id, NEW.run_id)) THEN
          RAISE EXCEPTION 'comparison_provider_not_settled';
        END IF;
        IF OLD.state = 'reserved' AND OLD.provider_settled_at IS NULL AND NEW.state = 'failed'
           AND EXISTS (SELECT 1 FROM analysis_runs r JOIN comparison_cells c ON c.run_id = r.id
               WHERE r.id = OLD.run_id AND
               (r.provider_safe_after IS NULL OR r.provider_safe_after > clock_timestamp())) THEN
          RAISE EXCEPTION 'comparison_provider_may_be_active';
        END IF;
        IF OLD.state = 'reserved' AND ROW(NEW.id, NEW.run_id, NEW.input_id, NEW.fence, NEW.profile_id,
             NEW.authorization_revision, NEW.stage_ordinal, NEW.input_sha256,
             NEW.intended_request_identity) IS DISTINCT FROM
         ROW(OLD.id, OLD.run_id, OLD.input_id, OLD.fence, OLD.profile_id,
             OLD.authorization_revision, OLD.stage_ordinal, OLD.input_sha256,
             OLD.intended_request_identity) AND
         EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
          RAISE EXCEPTION 'comparison_invocation_immutable';
        END IF;
        IF OLD.provider_settled_at IS NOT NULL AND
           NEW.provider_settled_at IS DISTINCT FROM OLD.provider_settled_at AND
           EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.run_id) THEN
          RAISE EXCEPTION 'comparison_invocation_immutable';
        END IF;
      END IF;
      IF TG_TABLE_NAME = 'observer_invocations' AND TG_OP = 'INSERT' THEN
        IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = NEW.run_id) AND
           NOT EXISTS (SELECT 1 FROM analysis_runs r WHERE r.id = NEW.run_id
              AND r.state = 'running' AND r.lease_expires_at > clock_timestamp()
              AND r.provider_safe_after > clock_timestamp()) THEN
          RAISE EXCEPTION 'comparison_reservation_unfenced';
        END IF;
      END IF;
      IF EXISTS (SELECT 1 FROM analysis_runs r WHERE r.id IN (old_run, new_run)
          AND r.purpose = 'comparison_campaign' AND r.state IN ('succeeded', 'failed')) THEN
        RAISE EXCEPTION 'comparison_evidence_immutable';
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$""")
    for table in ("artifact_metadata", "publication_intents", "observer_invocations",
                  "observations", "analysis_stages", "result_projections"):
        op.execute(f"CREATE TRIGGER comparison_{table}_guard BEFORE INSERT OR UPDATE OR DELETE ON {table} "
                   "FOR EACH ROW EXECUTE FUNCTION guard_comparison_evidence()")


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT 1 FROM comparison_campaigns LIMIT 1")).first():
        raise RuntimeError("comparison_campaign_evidence_exists")
    for table in ("artifact_metadata", "publication_intents", "observer_invocations",
                  "observations", "analysis_stages", "result_projections"):
        op.execute(f"DROP TRIGGER comparison_{table}_guard ON {table}")
    op.execute("DROP FUNCTION guard_comparison_evidence()")
    op.execute("DROP TRIGGER comparison_input_guard ON run_inputs")
    op.execute("DROP FUNCTION guard_comparison_input()")
    op.execute("""CREATE OR REPLACE FUNCTION guard_comparison_run() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'DELETE' THEN
        IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) THEN
          RAISE EXCEPTION 'comparison_run_immutable';
        END IF;
        RETURN OLD;
      END IF;
      IF EXISTS (SELECT 1 FROM comparison_cells WHERE run_id = OLD.id) AND
         ROW(NEW.id, NEW.purpose, NEW.binding_kind, NEW.profile_id, NEW.authorization_revision,
             NEW.profile_snapshot, NEW.request_context, NEW.policy_snapshot, NEW.rule_snapshot,
             NEW.taxonomy_snapshot, NEW.requested_classes, NEW.analysis_intent, NEW.stage_key, NEW.state)
         IS DISTINCT FROM
         ROW(OLD.id, OLD.purpose, OLD.binding_kind, OLD.profile_id, OLD.authorization_revision,
             OLD.profile_snapshot, OLD.request_context, OLD.policy_snapshot, OLD.rule_snapshot,
             OLD.taxonomy_snapshot, OLD.requested_classes, OLD.analysis_intent, OLD.stage_key, OLD.state) THEN
        RAISE EXCEPTION 'comparison_run_immutable';
      END IF;
      RETURN NEW;
    END $$""")
    op.drop_column("observer_invocations", "provider_settled_at")
    op.drop_column("analysis_runs", "provider_safe_after")

"""Controlled hard deletion, object cleanup and membership authority."""
from alembic import op

revision = '0029_management'
down_revision = '0028_video_authorization'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE project_membership_audit (
        id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES site_projects(id),
        actor_id uuid REFERENCES account_users(id), user_id uuid NOT NULL REFERENCES account_users(id),
        previous_role text NOT NULL CHECK(previous_role IN ('owner','editor','viewer')),
        next_role text CHECK(next_role IN ('editor','viewer')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())''')

    op.execute('''CREATE TABLE deletion_operations (
        id uuid PRIMARY KEY, target_kind text NOT NULL CHECK(target_kind IN ('project','run')),
        target_id uuid NOT NULL, requester_id uuid REFERENCES account_users(id),
        state text NOT NULL CHECK(state IN ('cleaning','completed')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(target_kind,target_id))''')
    op.execute('''CREATE TABLE deletion_objects (
        deletion_id uuid NOT NULL REFERENCES deletion_operations(id), object_key text NOT NULL,
        PRIMARY KEY(deletion_id,object_key))''')
    op.execute('''CREATE TABLE deletion_row_authorizations (
        deletion_id uuid NOT NULL REFERENCES deletion_operations(id),
        table_name text NOT NULL, row_key jsonb NOT NULL)''')
    op.execute('''CREATE TABLE deleted_request_keys (
        kind text NOT NULL, request_key text NOT NULL, project_id uuid,
        PRIMARY KEY(kind,request_key))''')
    op.execute('''CREATE TABLE video_admissions (project_id uuid NOT NULL REFERENCES site_projects(id),
        request_key text NOT NULL, request_hash text NOT NULL, source_key text NOT NULL,
        state text NOT NULL CHECK(state IN ('publishing','failed')), PRIMARY KEY(project_id,request_key))''')
    op.execute('CREATE TABLE video_artifacts (job_id uuid NOT NULL REFERENCES video_jobs(id), object_key text NOT NULL, PRIMARY KEY(job_id,object_key))')
    op.execute('CREATE TABLE deleted_receipt_ids (id uuid PRIMARY KEY)')
    op.execute('ALTER TABLE submission_requests ADD COLUMN project_id uuid REFERENCES site_projects(id)')
    op.execute('''UPDATE submission_requests s SET project_id=(r.request_context->>'project_id')::uuid
        FROM analysis_runs r WHERE r.id=s.run_id AND r.request_context ? 'project_id' ''')
    # Lineage retains the original identity without keeping deleted evidence alive.
    for table, column in (('analysis_runs','retry_of_run_id'), ('analysis_runs','retry_predecessor_id'),
                          ('artifact_metadata','source_artifact_id'), ('video_jobs','retry_of')):
        op.execute(f'''DO $$ DECLARE item record; BEGIN
            FOR item IN SELECT conname FROM pg_constraint
                WHERE conrelid='{table}'::regclass AND contype='f'
                AND conkey=ARRAY[(SELECT attnum FROM pg_attribute WHERE attrelid='{table}'::regclass
                    AND attname='{column}')]::smallint[]
            LOOP EXECUTE format('ALTER TABLE {table} DROP CONSTRAINT %I',item.conname); END LOOP;
            END $$''')
    # Cycles between publication intents, submissions and source artifacts are deleted atomically.
    op.execute('''DO $$ DECLARE item record; BEGIN
        FOR item IN SELECT conrelid::regclass AS relation, conname FROM pg_constraint
            WHERE contype='f' AND connamespace=current_schema()::regnamespace
        LOOP EXECUTE format('ALTER TABLE %s ALTER CONSTRAINT %I DEFERRABLE INITIALLY IMMEDIATE',
                            item.relation,item.conname); END LOOP;
        END $$''')
    op.execute('''CREATE FUNCTION deletion_row_authorized(relation_name text, previous jsonb)
        RETURNS boolean LANGUAGE sql STABLE AS $$
        SELECT EXISTS (SELECT 1 FROM deletion_row_authorizations a JOIN deletion_operations d ON d.id=a.deletion_id
            WHERE d.id::text=current_setting('app.deletion_id',true) AND d.state='cleaning'
            AND a.table_name=relation_name AND previous @> a.row_key) $$''')
    guarded = ('zone_plan_revisions','zone_plan_entries','detected_objects','detected_scene_features',
               'run_plan_bindings','stage_confirmations','annotation_proposals','annotation_versions',
               'deepseek_calls','deepseek_results')
    for table in guarded:
        op.execute(f'''CREATE OR REPLACE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP='DELETE' AND deletion_row_authorized(TG_TABLE_NAME,to_jsonb(OLD)) THEN RETURN OLD; END IF;
                RAISE EXCEPTION '{table}_immutable';
            END $$''')
    for function in ('guard_site_signal_update', 'guard_accepted_run_input'):
        op.execute(f'''DO $$ DECLARE definition text; BEGIN
            SELECT pg_get_functiondef('{function}()'::regprocedure) INTO definition;
            definition=regexp_replace(definition,'BEGIN',
                'BEGIN IF TG_OP=''DELETE'' AND deletion_row_authorized(TG_TABLE_NAME,to_jsonb(OLD)) THEN RETURN OLD; END IF;');
            EXECUTE definition; END $$''')
    op.execute('''CREATE FUNCTION lock_management_admission() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN PERFORM pg_advisory_xact_lock_shared(804298270115); RETURN NEW; END $$''')
    op.execute('''CREATE FUNCTION lock_publication_object() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE object_key text;
        BEGIN
            IF TG_TABLE_NAME='publication_intents' THEN object_key=NEW.final_key;
            ELSIF TG_TABLE_NAME='artifact_metadata' THEN object_key=NEW.key;
            ELSE object_key=NEW.source_key; END IF;
            IF object_key IS NOT NULL THEN
                PERFORM pg_advisory_xact_lock(hashtextextended(object_key,804298270116));
            END IF;
            RETURN NEW;
        END $$''')
    for table in ('publication_intents','artifact_metadata','video_jobs','video_admissions'):
        op.execute(f'''CREATE TRIGGER publication_object_lock BEFORE INSERT OR UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION lock_publication_object()''')
    for table in ('analysis_runs','publication_intents','artifact_metadata','video_jobs','submission_requests',
                  'project_members','project_invitations','video_admissions','site_zones','zone_plan_revisions','project_cover_requests'):
        op.execute(f'''CREATE TRIGGER management_admission_lock BEFORE INSERT OR UPDATE ON {table}
            FOR EACH STATEMENT EXECUTE FUNCTION lock_management_admission()''')


def downgrade():
    raise RuntimeError('membership_audit_requires_forward_migration')

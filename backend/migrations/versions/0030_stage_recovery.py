"""Durable same-run recovery with immutable effective receipt references."""
from alembic import op

revision = '0030_stage_recovery'
down_revision = '0029_management'
branch_labels = depends_on = None


def upgrade():
    op.execute('''ALTER TABLE analysis_runs ADD COLUMN current_attempt_id uuid''')
    op.execute('''CREATE TABLE run_attempts (
        id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES analysis_runs(id) DEFERRABLE INITIALLY DEFERRED,
        parent_attempt_id uuid UNIQUE REFERENCES run_attempts(id) DEFERRABLE,
        failed_stage text, actor_id uuid REFERENCES account_users(id), idempotency_key uuid,
        status text NOT NULL CHECK(status IN ('queued','running','succeeded','failed')),
        before_stages jsonb NOT NULL DEFAULT '[]',
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(run_id,idempotency_key), UNIQUE(run_id,id),
        FOREIGN KEY(run_id,parent_attempt_id) REFERENCES run_attempts(run_id,id) DEFERRABLE)''')
    op.execute("CREATE UNIQUE INDEX run_attempts_one_active ON run_attempts(run_id) WHERE status IN ('queued','running')")
    op.execute('''INSERT INTO run_attempts(id,run_id,status,before_stages)
        SELECT r.id,r.id,CASE WHEN r.state IN ('queued','running','succeeded','failed') THEN r.state ELSE 'failed' END,
        COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY ordinal) FROM analysis_stages s WHERE s.run_id=r.id),'[]')
        FROM analysis_runs r''')
    op.execute('UPDATE analysis_runs SET current_attempt_id=id')
    op.execute('''ALTER TABLE analysis_runs ADD CONSTRAINT analysis_runs_current_attempt_fk
        FOREIGN KEY(id,current_attempt_id) REFERENCES run_attempts(run_id,id) DEFERRABLE INITIALLY DEFERRED''')
    op.execute('ALTER TABLE analysis_runs ALTER COLUMN current_attempt_id SET NOT NULL')
    op.execute('ALTER TABLE deepseek_calls ADD COLUMN attempt_id uuid REFERENCES run_attempts(id) DEFERRABLE')
    op.execute('ALTER TABLE deepseek_calls ADD COLUMN source_call_id uuid REFERENCES deepseek_calls(id) DEFERRABLE')
    op.execute('ALTER TABLE deepseek_calls ADD COLUMN validation_revision text')
    op.execute('ALTER TABLE deepseek_calls DISABLE TRIGGER deepseek_calls_immutable')
    op.execute('UPDATE deepseek_calls SET attempt_id=run_id')
    op.execute('ALTER TABLE deepseek_calls ENABLE TRIGGER deepseek_calls_immutable')
    op.execute('ALTER TABLE deepseek_calls ALTER COLUMN attempt_id SET NOT NULL')
    op.execute('ALTER TABLE deepseek_calls DROP CONSTRAINT deepseek_calls_run_id_call_key_key')
    op.execute('ALTER TABLE deepseek_calls ADD UNIQUE(attempt_id,call_key)')
    op.execute('''ALTER TABLE deepseek_calls ADD CHECK ((source_call_id IS NULL)=(validation_revision IS NULL))''')
    op.execute('''CREATE TABLE attempt_call_refs (
        attempt_id uuid NOT NULL REFERENCES run_attempts(id) DEFERRABLE,
        call_key text NOT NULL, call_id uuid NOT NULL REFERENCES deepseek_calls(id) DEFERRABLE,
        PRIMARY KEY(attempt_id,call_key))''')
    op.execute('''INSERT INTO attempt_call_refs SELECT c.attempt_id,c.call_key,c.id
        FROM deepseek_calls c JOIN deepseek_results r ON r.call_id=c.id WHERE r.result->>'valid'='true' ''')
    op.execute("""CREATE FUNCTION guard_attempt_call_ref() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM run_attempts a JOIN deepseek_calls c ON c.run_id=a.run_id
            JOIN deepseek_results r ON r.call_id=c.id WHERE a.id=NEW.attempt_id AND c.id=NEW.call_id
            AND c.call_key=NEW.call_key AND r.result->>'valid'='true') THEN
            RAISE EXCEPTION 'effective_call_invalid'; END IF; RETURN NEW; END $$""")
    op.execute('CREATE TRIGGER attempt_call_refs_guard BEFORE INSERT ON attempt_call_refs FOR EACH ROW EXECUTE FUNCTION guard_attempt_call_ref()')
    op.execute('''CREATE TABLE detector_stage_outputs (
        run_id uuid NOT NULL REFERENCES analysis_runs(id) DEFERRABLE,
        input_id uuid NOT NULL, input_sha256 text NOT NULL, manifest jsonb NOT NULL, output jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(run_id,input_id),
        FOREIGN KEY(run_id,input_id) REFERENCES run_inputs(run_id,input_id) DEFERRABLE)''')
    for table in ('attempt_call_refs', 'detector_stage_outputs'):
        op.execute(f'''CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN
                IF TG_OP='DELETE' AND deletion_row_authorized(TG_TABLE_NAME,to_jsonb(OLD)) THEN RETURN OLD; END IF;
                RAISE EXCEPTION '{table}_immutable';
            END $$''')
        op.execute(f'''CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()''')
    op.execute('''CREATE FUNCTION guard_run_attempt() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP='DELETE' THEN
            IF deletion_row_authorized(TG_TABLE_NAME,to_jsonb(OLD)) THEN RETURN OLD; END IF;
            RAISE EXCEPTION 'run_attempts_immutable';
        END IF;
        IF (to_jsonb(NEW)-'status') IS DISTINCT FROM (to_jsonb(OLD)-'status')
            OR OLD.status IN ('succeeded','failed') OR
            (OLD.status='running' AND NEW.status='queued') THEN RAISE EXCEPTION 'run_attempts_immutable'; END IF;
        RETURN NEW; END $$''')
    op.execute('CREATE TRIGGER run_attempts_guard BEFORE UPDATE OR DELETE ON run_attempts FOR EACH ROW EXECUTE FUNCTION guard_run_attempt()')
    op.execute('''CREATE FUNCTION bind_run_attempt() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF TG_OP='INSERT' THEN
            NEW.current_attempt_id=NEW.id;
            INSERT INTO run_attempts(id,run_id,status) VALUES (NEW.id,NEW.id,CASE WHEN NEW.state IN ('queued','running','succeeded','failed') THEN NEW.state ELSE 'failed' END);
        ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
            UPDATE run_attempts SET status=CASE WHEN NEW.state IN ('queued','running','succeeded','failed') THEN NEW.state ELSE 'failed' END WHERE id=NEW.current_attempt_id AND status IN ('queued','running');
        END IF; RETURN NEW; END $$''')
    op.execute('CREATE TRIGGER analysis_runs_attempt BEFORE INSERT OR UPDATE ON analysis_runs FOR EACH ROW EXECUTE FUNCTION bind_run_attempt()')
    op.execute('''CREATE FUNCTION bind_call_attempt() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN
        IF NEW.attempt_id IS NULL THEN SELECT current_attempt_id INTO NEW.attempt_id FROM analysis_runs WHERE id=NEW.run_id; END IF;
        IF NOT EXISTS(SELECT 1 FROM run_attempts WHERE id=NEW.attempt_id AND run_id=NEW.run_id) THEN
            RAISE EXCEPTION 'call_attempt_mismatch'; END IF;
        RETURN NEW; END $$''')
    op.execute('CREATE TRIGGER deepseek_calls_attempt BEFORE INSERT ON deepseek_calls FOR EACH ROW EXECUTE FUNCTION bind_call_attempt()')


def downgrade():
    raise RuntimeError('stage_recovery_evidence_requires_forward_migration')

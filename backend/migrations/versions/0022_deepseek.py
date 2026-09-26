"""Add immutable DeepSeek evidence, preserving every historical run."""
from alembic import op

revision = '0022_deepseek'
down_revision = '0021_annotations'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE deepseek_calls (
        id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES analysis_runs(id),
        call_key text NOT NULL, kind text NOT NULL CHECK(kind IN ('frame','assessment')),
        input_id uuid, context jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(run_id,call_key), FOREIGN KEY(run_id,input_id) REFERENCES run_inputs(run_id,input_id))''')
    op.execute('''CREATE TABLE deepseek_results (
        call_id uuid PRIMARY KEY REFERENCES deepseek_calls(id), result jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())''')
    for table in ('deepseek_calls', 'deepseek_results'):
        op.execute(f'''CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$''')
        op.execute(f'''CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()''')
    op.execute('ALTER TABLE detected_objects ALTER COLUMN score DROP NOT NULL')
    op.execute('ALTER TABLE detected_objects ALTER COLUMN box DROP NOT NULL')
    op.execute('ALTER TABLE detected_objects ADD COLUMN details jsonb')


def downgrade():
    raise RuntimeError('deepseek_evidence_preservation_requires_forward_migration')

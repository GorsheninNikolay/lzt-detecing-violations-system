"""Durable video jobs and one-shot external call ledger."""
from alembic import op

revision = '0027_video'
down_revision = '0026_feedback_tools'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE video_jobs (
        id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES site_projects(id),
        zone_id uuid NOT NULL REFERENCES site_zones(id), request_key text NOT NULL,
        request_hash text NOT NULL, source_key text NOT NULL, source_sha256 text NOT NULL,
        source_size bigint NOT NULL, context jsonb NOT NULL, profile_snapshot jsonb NOT NULL,
        state text NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','running','succeeded','failed')),
        stage text NOT NULL DEFAULT 'preparation', progress double precision NOT NULL DEFAULT 0,
        metadata jsonb NOT NULL, device jsonb, result jsonb, error text,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(project_id,request_key))''')
    op.execute('''CREATE TABLE video_calls (
        job_id uuid NOT NULL REFERENCES video_jobs(id), call_key text NOT NULL,
        context jsonb NOT NULL, result jsonb,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(job_id,call_key))''')


def downgrade():
    if op.get_bind().exec_driver_sql('SELECT 1 FROM video_jobs LIMIT 1').first():
        raise RuntimeError('video_data_exists')
    op.execute('DROP TABLE video_calls')
    op.execute('DROP TABLE video_jobs')

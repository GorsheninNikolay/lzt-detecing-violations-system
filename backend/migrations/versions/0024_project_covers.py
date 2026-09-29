"""Persistent public project covers with retry-safe replacement."""
from alembic import op
import sqlalchemy as sa


revision = '0024_project_covers'
down_revision = '0023_hybrid_signals'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE site_projects ADD COLUMN cover_sha256 text')
    op.execute('ALTER TABLE site_projects ADD COLUMN cover_size integer')
    op.execute('''ALTER TABLE site_projects ADD CONSTRAINT project_cover_metadata CHECK (
        (cover_sha256 IS NULL AND cover_size IS NULL) OR
        (cover_sha256 ~ '^[0-9a-f]{64}$' AND cover_size > 0))''')
    op.execute('''CREATE TABLE project_cover_requests (
        request_key uuid PRIMARY KEY,
        project_id uuid NOT NULL REFERENCES site_projects(id),
        body_sha256 text NOT NULL,
        response jsonb NOT NULL)''')
    op.execute('''CREATE TABLE project_cover_gc (
        project_id uuid NOT NULL REFERENCES site_projects(id),
        sha256 text NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        not_before timestamptz NOT NULL DEFAULT clock_timestamp() + interval '10 minutes',
        PRIMARY KEY (project_id, sha256))''')
    op.execute('CREATE INDEX project_cover_gc_due ON project_cover_gc(not_before)')


def downgrade():
    if op.get_bind().execute(sa.text('''SELECT 1 FROM site_projects WHERE cover_sha256 IS NOT NULL
        UNION ALL SELECT 1 FROM project_cover_requests
        UNION ALL SELECT 1 FROM project_cover_gc LIMIT 1''')).first():
        raise RuntimeError('project_cover_data_exists')
    op.drop_index('project_cover_gc_due', table_name='project_cover_gc')
    op.drop_table('project_cover_gc')
    op.drop_table('project_cover_requests')
    op.execute('ALTER TABLE site_projects DROP CONSTRAINT project_cover_metadata')
    op.execute('ALTER TABLE site_projects DROP COLUMN cover_size')
    op.execute('ALTER TABLE site_projects DROP COLUMN cover_sha256')

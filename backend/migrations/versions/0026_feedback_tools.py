"""Private assistant conversations and explicitly illustrative trial imports."""
from alembic import op

revision = '0026_feedback_tools'
down_revision = '0025_accounts'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE assistant_messages (
        id uuid PRIMARY KEY, user_id uuid NOT NULL REFERENCES account_users(id),
        project_id uuid NOT NULL REFERENCES site_projects(id),
        role text NOT NULL CHECK(role IN ('user','assistant')), content text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())''')
    op.execute('CREATE INDEX assistant_private_history ON assistant_messages(user_id,project_id,created_at)')
    op.execute('''CREATE TABLE trial_imports (
        user_id uuid NOT NULL REFERENCES account_users(id), request_key uuid NOT NULL,
        body_sha256 text NOT NULL, project_id uuid NOT NULL REFERENCES site_projects(id),
        manifest jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        PRIMARY KEY(user_id,request_key), UNIQUE(project_id))''')
    op.execute('''CREATE TABLE trial_photos (
        id uuid PRIMARY KEY, project_id uuid NOT NULL REFERENCES site_projects(id),
        filename text NOT NULL, sha256 text NOT NULL, data bytea NOT NULL,
        UNIQUE(project_id,filename))''')


def downgrade():
    for table in ('assistant_messages', 'trial_imports', 'trial_photos'):
        if op.get_bind().exec_driver_sql(f'SELECT 1 FROM {table} LIMIT 1').first():
            raise RuntimeError('feedback_tools_data_exists')
    for table in ('trial_photos', 'trial_imports', 'assistant_messages'):
        op.execute(f'DROP TABLE {table}')

"""Accounts, private projects and revocable invitations."""
from alembic import op

revision = '0025_accounts'
down_revision = '0024_project_covers'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE account_users (
        id uuid PRIMARY KEY, email text NOT NULL UNIQUE, name text NOT NULL,
        password_hash text NOT NULL,recovery_hash text NOT NULL, theme text NOT NULL DEFAULT 'system'
        CHECK(theme IN ('light','dark','system')), verified boolean NOT NULL DEFAULT false)''')
    op.execute('''CREATE TABLE account_sessions (
        token_hash text PRIMARY KEY,user_id uuid NOT NULL REFERENCES account_users(id),
        expires_at timestamptz NOT NULL)''')
    op.execute('''CREATE TABLE project_members (
        project_id uuid NOT NULL REFERENCES site_projects(id),
        user_id uuid NOT NULL REFERENCES account_users(id),
        role text NOT NULL CHECK(role IN ('owner','editor','viewer')),
        PRIMARY KEY(project_id,user_id))''')
    op.execute('''CREATE TABLE project_invitations (
        id uuid PRIMARY KEY,project_id uuid NOT NULL REFERENCES site_projects(id),
        token_hash text NOT NULL UNIQUE,email text,recipient_id uuid REFERENCES account_users(id),role text NOT NULL CHECK(role IN ('editor','viewer')),
        expires_at timestamptz NOT NULL,revoked boolean NOT NULL DEFAULT false)''')
    op.execute('''CREATE TABLE account_notifications (
        id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES account_users(id),
        invitation_id uuid NOT NULL REFERENCES project_invitations(id),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),read boolean NOT NULL DEFAULT false)''')
    op.execute('''CREATE TABLE account_throttles (
        key text PRIMARY KEY,started_at timestamptz NOT NULL DEFAULT clock_timestamp(),attempts int NOT NULL)''')


def downgrade():
    raise RuntimeError('account_data_must_be_preserved')

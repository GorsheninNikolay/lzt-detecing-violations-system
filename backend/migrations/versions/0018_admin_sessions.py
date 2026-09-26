"""Revocable owner sessions and persistent request throttling."""
from alembic import op

revision = "0018_admin_sessions"
down_revision = "0017_feedback"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE admin_credentials (
        login text PRIMARY KEY CHECK (login='gorshenin-nik'), password_hash text NOT NULL)""")
    op.execute("""CREATE TABLE admin_sessions (
        token_hash text PRIMARY KEY, csrf text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        expires_at timestamptz NOT NULL)""")
    op.execute("""CREATE TABLE request_limits (
        scope text NOT NULL, identity text NOT NULL, bucket bigint NOT NULL,
        count integer NOT NULL, PRIMARY KEY(scope, identity, bucket))""")


def downgrade():
    for name in ('request_limits','admin_sessions','admin_credentials'):
        op.drop_table(name)

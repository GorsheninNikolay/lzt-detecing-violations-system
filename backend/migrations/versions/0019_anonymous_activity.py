"""Anonymous sessions and separate accepted-mutation attribution."""
from alembic import op

revision = "0019_anonymous_activity"
down_revision = "0018_admin_sessions"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE anonymous_browsers (
        id uuid PRIMARY KEY, first_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        last_at timestamptz NOT NULL DEFAULT clock_timestamp(), session_id uuid NOT NULL)""")
    op.execute("""CREATE TABLE anonymous_sessions (
        id uuid PRIMARY KEY, browser_id uuid NOT NULL REFERENCES anonymous_browsers(id),
        started_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("""CREATE TABLE anonymous_events (
        id uuid PRIMARY KEY, browser_id uuid NOT NULL REFERENCES anonymous_browsers(id),
        session_id uuid NOT NULL REFERENCES anonymous_sessions(id),
        kind text NOT NULL CHECK (kind IN ('visit','wizard_started','wizard_completed','wizard_skipped')),
        created_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("""CREATE TABLE activity_attribution (
        kind text NOT NULL CHECK (kind IN ('project','run')), object_id uuid NOT NULL,
        browser_id uuid NOT NULL REFERENCES anonymous_browsers(id),
        PRIMARY KEY (kind, object_id))""")
    op.execute("""CREATE TABLE project_requests (
        request_key uuid PRIMARY KEY, body_sha256 text NOT NULL, response jsonb NOT NULL)""")
    op.execute("""CREATE TABLE analytics_collection (
        singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
        started_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
    op.execute("INSERT INTO analytics_collection DEFAULT VALUES")


def downgrade():
    for name in ('analytics_collection','project_requests','activity_attribution','anonymous_events','anonymous_sessions','anonymous_browsers'):
        op.drop_table(name)

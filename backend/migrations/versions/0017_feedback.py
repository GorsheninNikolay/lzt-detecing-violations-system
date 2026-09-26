"""Private, atomically published feedback."""
from alembic import op

revision = "0017_feedback"
down_revision = "0016_project_history"
branch_labels = depends_on = None


def upgrade():
    op.execute("""CREATE TABLE feedback (
        id uuid PRIMARY KEY, request_key uuid UNIQUE NOT NULL, body_sha256 text NOT NULL,
        category text NOT NULL CHECK (category IN ('problem','idea','praise','other')),
        message text NOT NULL CHECK (length(trim(message)) BETWEEN 1 AND 5000),
        context jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        read_at timestamptz)""")
    op.execute("""CREATE TABLE feedback_attachments (
        id uuid PRIMARY KEY, feedback_id uuid NOT NULL REFERENCES feedback(id),
        object_key text UNIQUE NOT NULL CHECK (object_key LIKE 'feedback/%'),
        sha256 text NOT NULL, size integer NOT NULL, media_type text NOT NULL)""")
    op.execute("CREATE INDEX feedback_newest ON feedback (created_at DESC, id)")


def downgrade():
    op.drop_table("feedback_attachments")
    op.drop_table("feedback")

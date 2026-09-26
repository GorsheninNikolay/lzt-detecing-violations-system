"""Record future signal updates without fabricating historical update times."""
from alembic import op

revision = "0020_signal_activity"
down_revision = "0019_anonymous_activity"
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE site_signals ADD COLUMN updated_at timestamptz')


def downgrade():
    op.execute('ALTER TABLE site_signals DROP COLUMN updated_at')

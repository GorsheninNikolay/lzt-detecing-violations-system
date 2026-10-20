"""Persist deletion object backoff without blocking unrelated cleanup."""
from alembic import op

revision = '0031_deletion_gc_retry'
down_revision = '0030_stage_recovery'
branch_labels = depends_on = None


def upgrade():
    op.execute('''ALTER TABLE deletion_objects ADD COLUMN retry_after timestamptz
        NOT NULL DEFAULT clock_timestamp()''')


def downgrade():
    op.execute('ALTER TABLE deletion_objects DROP COLUMN retry_after')

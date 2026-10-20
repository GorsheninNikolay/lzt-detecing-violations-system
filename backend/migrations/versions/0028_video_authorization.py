"""Bind video payments to live authorization and permit one CPU successor."""
from alembic import op

revision = '0028_video_authorization'
down_revision = '0027_video'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE video_jobs ADD COLUMN profile_id uuid REFERENCES observer_profiles(id)')
    op.execute('ALTER TABLE video_jobs ADD COLUMN authorization_revision integer CHECK(authorization_revision>0)')
    op.execute('ALTER TABLE video_jobs ADD COLUMN retry_of uuid UNIQUE REFERENCES video_jobs(id)')


def downgrade():
    if op.get_bind().exec_driver_sql('SELECT 1 FROM video_jobs WHERE profile_id IS NOT NULL OR retry_of IS NOT NULL LIMIT 1').first():
        raise RuntimeError('video_authorization_data_exists')
    op.execute('ALTER TABLE video_jobs DROP COLUMN retry_of, DROP COLUMN authorization_revision, DROP COLUMN profile_id')

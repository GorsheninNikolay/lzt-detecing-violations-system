"""Permit source-bound process signals without a plan; preserve all prior basis."""
from alembic import op

revision = '0023_hybrid_signals'
down_revision = '0022_deepseek'
branch_labels = depends_on = None


def upgrade():
    op.execute('ALTER TABLE site_signals ALTER COLUMN revision_id DROP NOT NULL')
    op.execute("ALTER TABLE site_signals ADD CONSTRAINT signal_work_requires_revision CHECK(work_entry_id IS NULL OR revision_id IS NOT NULL)")


def downgrade():
    raise RuntimeError('hybrid_evidence_preservation_requires_forward_migration')

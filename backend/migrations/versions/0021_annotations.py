"""Separate immutable human annotation versions from model evidence."""
from alembic import op

revision = '0021_annotations'
down_revision = '0020_signal_activity'
branch_labels = depends_on = None


def upgrade():
    op.execute('''CREATE TABLE annotation_proposals (
        id uuid PRIMARY KEY, request_key uuid NOT NULL UNIQUE, body_sha256 text NOT NULL,
        run_id uuid NOT NULL, input_id uuid NOT NULL, input_sha256 text NOT NULL,
        artifact_id uuid NOT NULL REFERENCES artifact_metadata(id), profile_id uuid,
        profile_snapshot jsonb NOT NULL, original_objects jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY(run_id,input_id) REFERENCES run_inputs(run_id,input_id))''')
    op.execute('''CREATE TABLE annotation_versions (
        id uuid PRIMARY KEY, proposal_id uuid NOT NULL REFERENCES annotation_proposals(id),
        revision integer NOT NULL CHECK(revision > 0), objects jsonb NOT NULL,
        status text NOT NULL CHECK(status IN ('pending','approved','rejected')),
        whole_frame_verified boolean NOT NULL DEFAULT false, reason text NOT NULL DEFAULT '',
        request_key uuid NOT NULL UNIQUE, body_sha256 text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
        UNIQUE(proposal_id,revision),
        CHECK(status <> 'approved' OR whole_frame_verified),
        CHECK(status <> 'rejected' OR length(trim(reason)) > 0))''')
    for table in ('annotation_proposals', 'annotation_versions'):
        op.execute(f'''CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$''')
        op.execute(f'''CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table}
            FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()''')


def downgrade():
    for table in ('annotation_versions', 'annotation_proposals'):
        if op.get_bind().exec_driver_sql(f'SELECT 1 FROM {table} LIMIT 1').first():
            raise RuntimeError('annotation_evidence_exists')
        op.execute(f'DROP TABLE {table}')
        op.execute(f'DROP FUNCTION reject_{table}_mutation()')

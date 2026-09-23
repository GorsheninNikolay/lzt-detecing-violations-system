"""Associate invocations and observations with stable ordered inputs."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004_ordered_series"
down_revision = "0003_single_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("publication_intents", sa.Column("submission_key", sa.Text(), sa.ForeignKey("submission_requests.idempotency_key")))
    op.add_column("run_inputs", sa.Column("input_id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False))
    op.create_unique_constraint("run_inputs_input_id_key", "run_inputs", ["input_id"])
    op.create_unique_constraint("run_inputs_run_input_key", "run_inputs", ["run_id", "input_id"])
    op.add_column("observer_invocations", sa.Column("input_id", UUID(as_uuid=True)))
    op.add_column("observations", sa.Column("input_id", UUID(as_uuid=True)))
    op.execute("""UPDATE observer_invocations i SET input_id = r.input_id
        FROM run_inputs r WHERE r.run_id = i.run_id AND r.ordinal = 0""")
    op.execute("""UPDATE observations o SET input_id = r.input_id
        FROM run_inputs r WHERE r.run_id = o.run_id AND r.ordinal = 0""")
    op.alter_column("observer_invocations", "input_id", nullable=False)
    op.alter_column("observations", "input_id", nullable=False)
    op.create_foreign_key("observer_invocations_run_input_fkey", "observer_invocations", "run_inputs",
                          ["run_id", "input_id"], ["run_id", "input_id"])
    op.create_foreign_key("observations_run_input_fkey", "observations", "run_inputs",
                          ["run_id", "input_id"], ["run_id", "input_id"])
    op.drop_constraint("observer_invocations_run_id_key", "observer_invocations", type_="unique")
    op.create_unique_constraint("observer_invocations_run_input_key", "observer_invocations", ["run_id", "input_id"])
    op.drop_constraint("observations_pkey", "observations", type_="primary")
    op.create_primary_key("observations_pkey", "observations", ["run_id", "input_id", "class_name"])


def downgrade() -> None:
    op.drop_column("publication_intents", "submission_key")
    op.drop_constraint("observations_pkey", "observations", type_="primary")
    op.create_primary_key("observations_pkey", "observations", ["run_id", "class_name"])
    op.drop_constraint("observer_invocations_run_input_key", "observer_invocations", type_="unique")
    op.create_unique_constraint("observer_invocations_run_id_key", "observer_invocations", ["run_id"])
    op.drop_constraint("observations_run_input_fkey", "observations", type_="foreignkey")
    op.drop_constraint("observer_invocations_run_input_fkey", "observer_invocations", type_="foreignkey")
    op.drop_column("observations", "input_id")
    op.drop_column("observer_invocations", "input_id")
    op.drop_constraint("run_inputs_input_id_key", "run_inputs", type_="unique")
    op.drop_constraint("run_inputs_run_input_key", "run_inputs", type_="unique")
    op.drop_column("run_inputs", "input_id")

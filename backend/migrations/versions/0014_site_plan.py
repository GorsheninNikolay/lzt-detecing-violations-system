"""Work catalog and immutable zone plans."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0014_site_plan"
down_revision = "0013_evaluation_report"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("catalog_sources",
        sa.Column("sha256", sa.Text(), primary_key=True),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("sheet_name", sa.Text(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False))
    op.create_table("catalog_works",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_sha256", sa.Text(), sa.ForeignKey("catalog_sources.sha256"), nullable=False),
        sa.Column("source_row", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("code", sa.Text()),
        sa.Column("raw_code", sa.Text()),
        sa.Column("raw_code_type", sa.Text()),
        sa.Column("raw_code_format", sa.Text()),
        sa.Column("code_cell", sa.Text(), nullable=False),
        sa.Column("title_cell", sa.Text(), nullable=False),
        sa.Column("parent_source_row", sa.Integer()),
        sa.Column("applicability", JSONB, nullable=False),
        sa.Column("applicability_cells", JSONB, nullable=False),
        sa.UniqueConstraint("source_sha256", "source_row"))
    op.create_table("site_projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False))
    op.create_table("site_zones",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("site_projects.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.UniqueConstraint("project_id", "name"))
    op.create_table("zone_plan_revisions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", UUID(as_uuid=True), sa.ForeignKey("site_zones.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("clock_timestamp()"), nullable=False),
        sa.UniqueConstraint("zone_id", "revision_number"))
    op.create_table("zone_plan_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("revision_id", UUID(as_uuid=True), sa.ForeignKey("zone_plan_revisions.id"), nullable=False),
        sa.Column("catalog_work_id", UUID(as_uuid=True), sa.ForeignKey("catalog_works.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("stage_key", sa.Text()),
        sa.Column("expected_equipment", JSONB, nullable=False),
        sa.Column("allowed_equipment", JSONB, nullable=False),
        sa.Column("excluded_equipment", JSONB, nullable=False),
        sa.CheckConstraint("starts_at <= ends_at"),
        sa.CheckConstraint("state IN ('planned', 'active', 'completed')"))
    for table in ("catalog_sources", "catalog_works", "zone_plan_revisions", "zone_plan_entries"):
        op.execute(f"""CREATE FUNCTION reject_{table}_mutation() RETURNS trigger LANGUAGE plpgsql AS $$
            BEGIN RAISE EXCEPTION '{table}_immutable'; END $$""")
        op.execute(f"CREATE TRIGGER {table}_immutable BEFORE UPDATE OR DELETE ON {table} "
                   f"FOR EACH ROW EXECUTE FUNCTION reject_{table}_mutation()")


def downgrade() -> None:
    for table in ("zone_plan_entries", "zone_plan_revisions", "site_zones", "site_projects", "catalog_works", "catalog_sources"):
        if op.get_bind().execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("site_plan_data_exists")
    for table in ("zone_plan_entries", "zone_plan_revisions", "catalog_works", "catalog_sources"):
        op.execute(f"DROP TRIGGER {table}_immutable ON {table}")
        op.execute(f"DROP FUNCTION reject_{table}_mutation()")
    for table in ("zone_plan_entries", "zone_plan_revisions", "site_zones", "site_projects", "catalog_works", "catalog_sources"):
        op.drop_table(table)

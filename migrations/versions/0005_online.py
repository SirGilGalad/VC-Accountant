"""Tenant row policies for Postgres.

Revision ID: 0005_online
Revises: 0004_packs
Create Date: 2026-11-12
"""

from alembic import op

from core.rls import apply_rls

revision = "0005_online"
down_revision = "0004_packs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    apply_rls(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    from core.schema import metadata

    for table in metadata.tables.values():
        bind.exec_driver_sql(f"DROP POLICY IF EXISTS tenant_isolation ON {table.name}")
        bind.exec_driver_sql(f"ALTER TABLE {table.name} DISABLE ROW LEVEL SECURITY")
    bind.exec_driver_sql("DROP FUNCTION IF EXISTS vca_tenant_id(text)")

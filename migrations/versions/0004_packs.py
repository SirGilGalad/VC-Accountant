"""Property and resort operational tables.

Revision ID: 0004_packs
Revises: 0003_construction
Create Date: 2026-11-12
"""

from alembic import op

from core.schema import metadata

revision = "0004_packs"
down_revision = "0003_construction"
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for name in ("reservation_holds", "sites", "document_index", "occupancies", "units"):
        bind.exec_driver_sql(f"DROP TABLE IF EXISTS {name}")

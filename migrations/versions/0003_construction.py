"""Job budgets for the construction pack.

Revision ID: 0003_construction
Revises: 0002_import
Create Date: 2026-11-12
"""

from alembic import op

from core.schema import metadata

revision = "0003_construction"
down_revision = "0002_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    op.get_bind().exec_driver_sql("DROP TABLE IF EXISTS job_budgets")

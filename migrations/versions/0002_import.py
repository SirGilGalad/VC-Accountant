"""Staging tables for a file import.

Revision ID: 0002_import
Revises: 0001_ledger
Create Date: 2026-11-12
"""

from alembic import op

from core.schema import metadata

revision = "0002_import"
down_revision = "0001_ledger"
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    bind = op.get_bind()
    for name in (
        "import_mappings",
        "import_issues",
        "stg_source_trial_balance",
        "stg_lines",
        "stg_entries",
        "stg_jobs",
        "stg_parties",
        "stg_accounts",
        "import_batches",
    ):
        bind.exec_driver_sql(f"DROP TABLE IF EXISTS {name}")

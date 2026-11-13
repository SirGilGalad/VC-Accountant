"""Shared ledger tables and posting triggers.

Revision ID: 0001_ledger
Revises:
Create Date: 2026-11-12
"""

from alembic import op

from core.schema import metadata
from core.triggers import apply_triggers

revision = "0001_ledger"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    metadata.create_all(bind)
    apply_triggers(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS journal_lines_immutable ON journal_lines")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS journal_lines_balance ON journal_lines")
        bind.exec_driver_sql("DROP TRIGGER IF EXISTS journal_entries_balance ON journal_entries")
    metadata.drop_all(bind)

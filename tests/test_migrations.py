"""Alembic upgrade from an empty database, then a zero trial balance."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from core.db import make_engine, upgrade_sqlite
from core.queries import trial_balance_net
from core.services.companies import NewCompany, insert_company
from core.triggers import apply_triggers


def test_sqlite_upgrade_seeds_a_zero_trial_balance(tmp_path):
    engine = upgrade_sqlite(tmp_path / "migrated.vca")
    with engine.begin() as conn:
        company_id, _member = insert_company(
            conn,
            NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id="construction"),
        )
        assert trial_balance_net(conn, company_id) == 0
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "0002_import"


@pytest.mark.skipif(not os.environ.get("VCA_TEST_PG_URL"), reason="Postgres URL is not set")
def test_postgres_upgrade_and_raw_post_guard():
    from alembic import command
    from alembic.config import Config
    from pathlib import Path

    url = os.environ["VCA_TEST_PG_URL"]
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    engine = make_engine(url)
    with engine.begin() as conn:
        apply_triggers(conn)
        company_id, member_id = insert_company(
            conn,
            NewCompany(
                name="Red Mesa Builders LLC",
                legal_name="Red Mesa Builders LLC",
                pack_id="general",
            ),
        )
        assert trial_balance_net(conn, company_id) == 0
        cash = conn.execute(text("SELECT id FROM accounts WHERE number = '1010'")).scalar()
        entry_id = conn.execute(
            text(
                """
                INSERT INTO journal_entries
                    (company_id, entry_date, number, source_type, status)
                VALUES (:company, '2026-01-01', 'PG', 'manual', 'draft')
                RETURNING id
                """
            ),
            {"company": company_id},
        ).scalar()
        conn.execute(
            text(
                """
                INSERT INTO journal_lines (entry_id, line_no, account_id, debit_cents, credit_cents)
                VALUES (:entry, 1, :account, 100, 0)
                """
            ),
            {"entry": entry_id, "account": cash},
        )
    with pytest.raises(Exception, match="unbalanced entry"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE journal_entries SET status = 'posted' WHERE id = :id"),
                {"id": entry_id},
            )
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM journal_lines WHERE entry_id = :id"), {"id": entry_id})
        conn.execute(text("DELETE FROM journal_entries WHERE id = :id"), {"id": entry_id})
        conn.execute(text("DELETE FROM audit_log WHERE company_id = :id"), {"id": company_id})
        conn.execute(text("DELETE FROM accounts WHERE company_id = :id"), {"id": company_id})
        conn.execute(text("DELETE FROM members WHERE company_id = :id"), {"id": company_id})
        tenant = conn.execute(text("SELECT tenant_id FROM companies WHERE id = :id"), {"id": company_id}).scalar()
        conn.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
        conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant})
    _ = member_id

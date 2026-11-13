"""Posting rules, chart, backup, and legacy migration."""

from __future__ import annotations

import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy import insert, select, text

from core.chart import account_id_by_number
from core.db import upgrade_sqlite
from core.errors import DuplicateAccountError, RoleError, UnbalancedEntryError
from core.queries import account_balance, trial_balance_net
from core.schema import audit_log, jobs, members, periods
from core.services.accounts import create_account
from core.services.backup import backup_file
from core.services.companies import NewCompany, create_company_file, insert_company
from core.services.opening import post_opening_balances
from core.services.posting import add_draft, post_entry, reverse_entry
from tests.conftest import SAMPLE


def _ids(conn, company_id):
    cash = account_id_by_number(conn, company_id, "1010")
    income = account_id_by_number(conn, company_id, "4000")
    return cash, income


def test_one_sided_entry_is_refused(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash, _income = _ids(conn, company_id)
        with pytest.raises(UnbalancedEntryError) as caught:
            entry_id = add_draft(
                conn,
                company_id=company_id,
                member_id=member_id,
                entry_date=date(2026, 1, 15),
                number="1",
                memo=None,
                source_type="manual",
                lines=[{"account_id": cash, "debit_cents": 10000, "credit_cents": 0}],
            )
            post_entry(conn, entry_id, member_id)
    assert caught.value.difference == 10000


def test_raw_sql_cannot_post_unbalanced(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash, _income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 1, 15),
            number="2",
            memo=None,
            source_type="manual",
            lines=[{"account_id": cash, "debit_cents": 10000, "credit_cents": 0}],
        )
    with pytest.raises(Exception, match="unbalanced entry"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE journal_entries SET status = 'posted' WHERE id = :id"),
                {"id": entry_id},
            )


def test_posted_line_cannot_be_edited(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 2, 1),
            number="3",
            memo="sale",
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 5000, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 5000},
            ],
        )
        post_entry(conn, entry_id, member_id)
        line_id = conn.execute(text("SELECT id FROM journal_lines WHERE entry_id = :id"), {"id": entry_id}).scalar()
    with pytest.raises(Exception, match="immutable"):
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE journal_lines SET debit_cents = 1 WHERE id = :id"),
                {"id": line_id},
            )


def test_post_writes_audit(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 2, 1),
            number="4",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 100, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 100},
            ],
        )
        post_entry(conn, entry_id, member_id)
        row = conn.execute(
            select(audit_log).where(
                audit_log.c.entity_id == entry_id,
                audit_log.c.action == "post",
            )
        ).one()
    assert '"draft"' in row.before_json
    assert '"posted"' in row.after_json


def test_viewer_cannot_post(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        viewer_id = conn.execute(
            insert(members).values(
                company_id=company_id,
                display_name="Viewer",
                role="viewer",
                status="active",
            )
        ).inserted_primary_key[0]
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 3, 1),
            number="5",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 100, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 100},
            ],
        )
        with pytest.raises(RoleError):
            post_entry(conn, entry_id, int(viewer_id))


def test_seed_trial_balance_is_zero(company):
    engine, company_id, _member = company
    with engine.begin() as conn:
        assert trial_balance_net(conn, company_id) == 0


def test_general_pack_has_no_job_cost_accounts(tmp_path: Path):
    info = NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id="general")
    engine, company_id, _member = create_company_file(tmp_path / "general.vca", info)
    with engine.begin() as conn:
        numbers = {
            row[0]
            for row in conn.execute(text("SELECT number FROM accounts WHERE company_id = :id"), {"id": company_id})
        }
    assert "1130" not in numbers
    assert "1400" not in numbers
    assert "5000" not in numbers
    assert "1010" in numbers


def test_child_account_and_duplicate(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        parent = account_id_by_number(conn, company_id, "6200")
        child = create_account(
            conn,
            company_id=company_id,
            member_id=member_id,
            number="6250",
            name="Inland Marine",
            account_type="expense",
            parent_id=parent,
        )
        row = conn.execute(text("SELECT parent_id FROM accounts WHERE id = :id"), {"id": child}).one()
        assert row.parent_id == parent
        with pytest.raises(DuplicateAccountError):
            create_account(
                conn,
                company_id=company_id,
                member_id=member_id,
                number="6250",
                name="Again",
                account_type="expense",
                parent_id=parent,
            )


def test_two_companies_can_share_a_job_number(tmp_path: Path):
    engine = upgrade_sqlite(tmp_path / "shared.vca")
    with engine.begin() as conn:
        first, _m1 = insert_company(conn, NewCompany(name="One", legal_name="One", pack_id="construction"))
        second, _m2 = insert_company(conn, NewCompany(name="Two", legal_name="Two", pack_id="general"))
        for company_id in (first, second):
            conn.execute(
                insert(jobs).values(
                    company_id=company_id,
                    number="J-100",
                    name="Sample job",
                    status="active",
                    contract_amount_cents=0,
                )
            )
        count = conn.execute(text("SELECT COUNT(*) FROM jobs WHERE number = 'J-100'")).scalar()
    assert count == 2


def test_opening_balances_match_input(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash = account_id_by_number(conn, company_id, "1010")
        post_opening_balances(
            conn,
            company_id=company_id,
            member_id=member_id,
            books_start=date(2026, 1, 1),
            balances=[{"account_id": cash, "natural_cents": 25000}],
        )
        assert account_balance(conn, cash, date(2025, 12, 31)) == 25000
        assert trial_balance_net(conn, company_id) == 0


def test_backup_matches_trial_balance(company, tmp_path: Path):
    engine, company_id, member_id = company
    source = tmp_path / "red-mesa.vca"
    with engine.begin() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 4, 1),
            number="9",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 8000, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 8000},
            ],
        )
        post_entry(conn, entry_id, member_id)
        expected = trial_balance_net(conn, company_id)
    copy = tmp_path / "copy.vca"
    backup_file(source, copy)
    opened = upgrade_sqlite(copy)
    with opened.begin() as conn:
        assert trial_balance_net(conn, company_id) == expected


def test_reverse_voids_original(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 5, 1),
            number="10",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 400, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 400},
            ],
        )
        post_entry(conn, entry_id, member_id)
        reverse_entry(conn, entry_id, member_id)
        status = conn.execute(text("SELECT status FROM journal_entries WHERE id = :id"), {"id": entry_id}).scalar()
        assert status == "void"
        assert account_balance(conn, cash) == 0


def test_closed_period_blocks_post(company):
    engine, company_id, member_id = company
    from core.errors import ClosedPeriodError

    with engine.begin() as conn:
        conn.execute(
            insert(periods).values(
                company_id=company_id,
                start=date(2026, 1, 1),
                end=date(2026, 1, 31),
                status="closed",
            )
        )
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 1, 15),
            number="11",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": 100, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": 100},
            ],
        )
        with pytest.raises(ClosedPeriodError):
            post_entry(conn, entry_id, member_id)


def test_legacy_vtg_keeps_unbalanced_as_draft(tmp_path: Path):
    from core.legacy import migrate_vtg

    path = tmp_path / "old.vtg"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY, name TEXT, company_type TEXT, legal_name TEXT,
            address TEXT, city TEXT, state TEXT, zip TEXT, phone TEXT, email TEXT,
            ein TEXT, fiscal_year_start_month INTEGER, accounting_method TEXT, db_version TEXT
        );
        CREATE TABLE chart_of_accounts (
            id INTEGER PRIMARY KEY, company_id INTEGER, account_number TEXT, name TEXT,
            account_type TEXT, parent_id INTEGER, tax_line_mapping TEXT, is_active INTEGER,
            is_system INTEGER, notes TEXT
        );
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT, email TEXT, phone TEXT, qb_list_id TEXT
        );
        CREATE TABLE vendors (
            id INTEGER PRIMARY KEY, company_id INTEGER, name TEXT, email TEXT, phone TEXT,
            qb_list_id TEXT, is_1099_eligible INTEGER
        );
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY, first_name TEXT, last_name TEXT, email TEXT, phone TEXT, qb_list_id TEXT
        );
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY, company_id INTEGER, customer_id INTEGER, job_number TEXT,
            job_name TEXT, status TEXT, contract_amount REAL, qb_job_id TEXT
        );
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY, company_id INTEGER, date TEXT, ref_number TEXT, memo TEXT
        );
        CREATE TABLE transaction_lines (
            id INTEGER PRIMARY KEY, transaction_id INTEGER, account_id INTEGER, job_id INTEGER,
            cost_code_id INTEGER, description TEXT, debit REAL, credit REAL
        );
        """
    )
    conn.execute(
        "INSERT INTO companies VALUES (1, 'Red Mesa Builders LLC', 'construction', 'Red Mesa Builders LLC', "
        "'100 Sample Way', 'Kanab', 'UT', '84741', '555-0100', 'pat@example.com', NULL, 1, 'Accrual', '0.3.0')"
    )
    conn.execute(
        "INSERT INTO chart_of_accounts VALUES (1, 1, '1010', 'Operating Checking', 'Asset', NULL, NULL, 1, 1, NULL)"
    )
    conn.execute(
        "INSERT INTO chart_of_accounts VALUES (2, 1, '4000', 'Sales', 'Income', NULL, NULL, 1, 1, NULL)"
    )
    conn.execute("INSERT INTO customers VALUES (1, 1, 'Sample Customer', NULL, NULL, 'C1')")
    conn.execute("INSERT INTO vendors VALUES (1, 1, 'Sample Vendor', NULL, NULL, 'V1', 1)")
    conn.execute("INSERT INTO employees VALUES (1, 'Pat', 'Sample', NULL, NULL, 'E1')")
    conn.execute("INSERT INTO jobs VALUES (1, 1, 1, 'J-100', 'Shop', 'Open', 1000, 'JOB1')")
    conn.execute("INSERT INTO transactions VALUES (1, 1, '2026-01-02', 'B1', 'balanced')")
    conn.execute("INSERT INTO transaction_lines VALUES (1, 1, 1, NULL, NULL, NULL, 10, 0)")
    conn.execute("INSERT INTO transaction_lines VALUES (2, 1, 2, NULL, NULL, NULL, 0, 10)")
    conn.execute("INSERT INTO transactions VALUES (2, 1, '2026-01-03', 'U1', 'one sided')")
    conn.execute("INSERT INTO transaction_lines VALUES (3, 2, 1, NULL, NULL, NULL, 100, 0)")
    conn.commit()
    conn.close()
    dest = migrate_vtg(path)
    assert dest.suffix == ".vca"
    assert list(path.parent.glob("*.vtg.bak-*"))
    engine = upgrade_sqlite(dest)
    with engine.begin() as db:
        posted = db.execute(text("SELECT COUNT(*) FROM journal_entries WHERE status = 'posted'")).scalar()
        drafts = db.execute(text("SELECT COUNT(*) FROM journal_entries WHERE status = 'draft'")).scalar()
        parties = db.execute(text("SELECT COUNT(*) FROM parties")).scalar()
    assert posted == 1
    assert drafts == 1
    assert parties == 3


@settings(max_examples=20, deadline=None)
@given(amount=st.integers(min_value=1, max_value=50_000))
def test_balanced_entries_keep_a_zero_trial_balance(amount: int):
    folder = Path(tempfile.mkdtemp())
    engine, company_id, member_id = create_company_file(folder / "h.vca", SAMPLE)
    with engine.begin() as conn:
        cash, income = _ids(conn, company_id)
        entry_id = add_draft(
            conn,
            company_id=company_id,
            member_id=member_id,
            entry_date=date(2026, 6, 1),
            number="H",
            memo=None,
            source_type="manual",
            lines=[
                {"account_id": cash, "debit_cents": amount, "credit_cents": 0},
                {"account_id": income, "debit_cents": 0, "credit_cents": amount},
            ],
        )
        post_entry(conn, entry_id, member_id)
        assert trial_balance_net(conn, company_id) == 0

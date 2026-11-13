"""Staged import. Imported only after the trial balance ties to the cent."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import func, insert, select, text

from core.import_quickbooks.money import parse_amount
from core.import_quickbooks.quickbooks import AlreadyImported, QuickBooksImport
from core.queries import trial_balance
from core.schema import (
    accounts,
    cost_codes,
    import_issues,
    journal_entries,
    journal_lines,
    stg_accounts,
    stg_entries,
    stg_jobs,
    stg_lines,
    stg_parties,
)

ROOT = Path(__file__).resolve().parents[1] / "fixtures"
QB = ROOT / "quickbooks"
CUTOFF = date(2026, 6, 30)


def _full_files() -> list[Path]:
    return [
        QB / "lists.iif",
        QB / "transaction_detail_2025.csv",
        QB / "transaction_detail_2026.xlsx",
        QB / "trial_balance_2026-06-30.csv",
    ]


def _off_files() -> list[Path]:
    return [
        QB / "lists.iif",
        QB / "transaction_detail_2025.csv",
        QB / "transaction_detail_2026.xlsx",
        QB / "trial_balance_off_by_one_cent.csv",
    ]


def test_amounts_accept_parentheses_minus_and_commas():
    assert parse_amount("1,200.00") == 120000
    assert parse_amount("(1,200.50)") == -120050
    assert parse_amount("-40") == -4000


def test_sample_lists_keep_names_and_the_1099_flag(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    batch_id = importer.stage([ROOT / "sample_lists.iif"], CUTOFF, label="lists")
    with engine.connect() as conn:
        names = {
            (row.number, row.name, row.account_type, row.subtype)
            for row in conn.execute(select(stg_accounts).where(stg_accounts.c.batch_id == batch_id)).all()
        }
        customers = conn.execute(
            select(stg_parties).where(stg_parties.c.batch_id == batch_id, stg_parties.c.kind == "customer")
        ).all()
        vendors = {
            row.display_name: bool(row.is_1099)
            for row in conn.execute(
                select(stg_parties).where(stg_parties.c.batch_id == batch_id, stg_parties.c.kind == "vendor")
            ).all()
        }
        employees = conn.execute(
            select(func.count()).select_from(stg_parties).where(
                stg_parties.c.batch_id == batch_id, stg_parties.c.kind == "employee"
            )
        ).scalar()
        jobs = conn.execute(select(func.count()).select_from(stg_jobs).where(stg_jobs.c.batch_id == batch_id)).scalar()
        errors = [
            row.message
            for row in conn.execute(
                select(import_issues).where(import_issues.c.batch_id == batch_id, import_issues.c.severity == "error")
            ).all()
        ]
    assert ("1010", "Operating Checking", "asset", "bank") in names
    assert ("1100", "Accounts Receivable", "asset", "receivable") in names
    assert ("6000", "Advertising", "expense", None) in names
    assert {row.display_name for row in customers} == {"Canyon Supply", "Red Rock Homes"}
    assert vendors["Mesa Lumber"] is True
    assert vendors["Kanab Electric"] is False
    assert employees == 1
    assert jobs == 1
    assert errors == []
    assert importer.status(batch_id) != "completed"


def test_sample_transactions_stage_four_balanced_entries(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    batch_id = importer.stage([ROOT / "sample_transactions.csv"], CUTOFF, label="txn")
    with engine.connect() as conn:
        entries = conn.execute(select(stg_entries).where(stg_entries.c.batch_id == batch_id)).all()
        for entry in entries:
            totals = conn.execute(
                select(func.sum(stg_lines.c.debit_cents), func.sum(stg_lines.c.credit_cents)).where(
                    stg_lines.c.entry_id == entry.id
                )
            ).one()
            assert int(totals[0]) == int(totals[1])
        messages = [row.message for row in importer.issues(batch_id)]
    assert len(entries) == 4
    assert any("Sales" in message and "not matched" in message for message in messages)


def test_fixture_ties_then_imports_and_matches_the_source_trial_balance(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    with engine.begin() as conn:
        code_id = int(
            conn.execute(
                insert(cost_codes).values(
                    company_id=company_id,
                    code="03",
                    name="Concrete",
                    category="material",
                )
            ).inserted_primary_key[0]
        )
    importer.map_class("03 Concrete", code_id)
    batch_id = importer.stage(_full_files(), CUTOFF, label="Red Mesa 2026")
    assert importer.status(batch_id) == "tied"
    assert importer.error_count(batch_id) == 0
    importer.accept(batch_id)
    assert importer.status(batch_id) == "imported"
    with engine.connect() as conn:
        live = {row["number"]: row["net_cents"] for row in trial_balance(conn, company_id, CUTOFF)}
        parent = conn.execute(
            select(accounts.c.parent_id).where(accounts.c.company_id == company_id, accounts.c.number == "5020")
        ).scalar()
        parent_number = conn.execute(select(accounts.c.number).where(accounts.c.id == parent)).scalar()
        tagged = conn.execute(
            select(func.count())
            .select_from(journal_lines)
            .where(journal_lines.c.cost_code_id == code_id)
        ).scalar()
        source = conn.execute(
            text(
                "SELECT source_type, import_batch_id FROM journal_entries WHERE company_id = :company"
            ),
            {"company": company_id},
        ).all()
    assert live["1010"] == 291000
    assert live["4000"] == -350000
    assert live["6000"] == 15000
    assert live["6100"] == 40000
    assert live["6770"] == 4000
    assert parent_number == "5000"
    assert tagged == 1
    assert source
    assert {row.source_type for row in source} == {"import"}
    assert {row.import_batch_id for row in source} == {batch_id}


def test_one_cent_stays_staged_and_that_account_sorts_first(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    batch_id = importer.stage(_off_files(), CUTOFF, label="off")
    rows = importer.tie(batch_id)
    assert importer.status(batch_id) == "staged"
    assert rows[0]["account_key"] == "1010"
    assert rows[0]["difference_cents"] != 0
    assert abs(rows[0]["difference_cents"]) == 1


def test_reject_leaves_the_books_untouched(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)

    def counts():
        with engine.connect() as conn:
            entries = conn.execute(
                select(func.count()).select_from(journal_entries).where(journal_entries.c.company_id == company_id)
            ).scalar()
            lines = conn.execute(select(func.count()).select_from(journal_lines)).scalar()
        return int(entries), int(lines)

    before = counts()
    batch_id = importer.stage(_full_files(), CUTOFF, label="reject me")
    importer.reject(batch_id)
    assert importer.status(batch_id) == "rejected"
    assert counts() == before
    with engine.connect() as conn:
        left = conn.execute(
            select(func.count()).select_from(stg_lines).where(stg_lines.c.batch_id == batch_id)
        ).scalar()
    assert int(left) == 0


def test_the_same_files_do_not_stage_twice_or_post_twice(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    first = importer.stage(_full_files(), CUTOFF, label="once")
    second = importer.stage(_full_files(), CUTOFF, label="once")
    assert first == second
    with engine.connect() as conn:
        count = conn.execute(
            select(func.count()).select_from(stg_entries).where(stg_entries.c.batch_id == first)
        ).scalar()
    importer.accept(first)
    third = importer.stage(_full_files(), CUTOFF, label="again")
    assert third == first
    with engine.connect() as conn:
        again = conn.execute(
            select(func.count()).select_from(stg_entries).where(stg_entries.c.batch_id == first)
        ).scalar()
        posted = conn.execute(
            select(func.count()).select_from(journal_entries).where(journal_entries.c.company_id == company_id)
        ).scalar()
    assert int(again) == int(count)
    try:
        importer.accept(first)
        raised = False
    except AlreadyImported as exc:
        raised = True
        assert str(first) in str(exc)
        assert "once" in str(exc)
    assert raised
    with engine.connect() as conn:
        posted_after = conn.execute(
            select(func.count()).select_from(journal_entries).where(journal_entries.c.company_id == company_id)
        ).scalar()
    assert posted_after == posted


def test_a_malformed_file_fails_without_raising(company):
    engine, company_id, member_id = company
    importer = QuickBooksImport(engine, company_id, member_id)
    batch_id = importer.stage([QB / "malformed.iif"], CUTOFF, label="bad")
    assert importer.status(batch_id) == "failed"
    assert any(row.severity == "error" for row in importer.issues(batch_id))


def test_opening_gap_is_explicit_and_can_tie(company, tmp_path):
    engine, company_id, member_id = company
    # Detail is the 2025 file only. The trial balance includes the later deposits.
    files = [
        QB / "lists.iif",
        QB / "transaction_detail_2025.csv",
        QB / "trial_balance_2026-06-30.csv",
    ]
    importer = QuickBooksImport(engine, company_id, member_id)
    batch_id = importer.stage(files, CUTOFF, label="hybrid")
    assert importer.status(batch_id) == "staged"
    importer.opening_gap(batch_id)
    assert importer.status(batch_id) == "tied"

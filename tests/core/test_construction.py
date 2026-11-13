"""Construction pack: job cost, billings, over/under, and time in minutes."""

from datetime import date
from pathlib import Path

from sqlalchemy import insert, select, text

from core.queries import home_status, job_cost_detail, over_under_billing
from core.reports import trial_balance_rows, write_csv, write_pdf
from core.schema import cost_codes, members, parties, party_roles, time_entries
from core.services.backup import backup_file
from core.services.companies import NewCompany, create_company_file
from core.services.jobs import create_job, enter_time, parse_hours, post_progress_bill, post_vendor_bill, set_job_budget
from core.services.preferences import get_preference, remembering_layout, reset_layout, set_preference


def test_parse_hours_stores_minutes():
    assert parse_hours("7:30") == 450


def test_job_cost_billings_and_underbilling(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        customer_id = int(
            conn.execute(
                insert(parties).values(company_id=company_id, display_name="Canyon Supply", is_active=True)
            ).inserted_primary_key[0]
        )
        conn.execute(insert(party_roles).values(party_id=customer_id, role="customer", is_1099=False))
        job_id = create_job(
            conn,
            company_id=company_id,
            customer_party_id=customer_id,
            number="J-100",
            name="Kitchen",
            contract_amount_cents=15_000_000,
        )
        code_id = int(
            conn.execute(
                select(cost_codes.c.id).where(cost_codes.c.company_id == company_id, cost_codes.c.code == "03")
            ).scalar()
        )
        set_job_budget(conn, job_id, code_id, 10_000_000)
        post_vendor_bill(
            conn,
            company_id=company_id,
            member_id=member_id,
            job_id=job_id,
            cost_code_id=code_id,
            account_number="5020",
            party_id=None,
            entry_date=date(2026, 6, 1),
            number="B-1",
            amount_cents=4_000_000,
        )
        post_progress_bill(
            conn,
            company_id=company_id,
            member_id=member_id,
            job_id=job_id,
            entry_date=date(2026, 6, 15),
            number="INV-1",
            amount_cents=5_000_000,
        )
        detail = job_cost_detail(conn, job_id)
        figure = over_under_billing(conn, job_id)
        billings = figure["billings_cents"]
    assert any(row["cost_code"] == "03" and row["account_name"] == "Job Materials" and row["cents"] == 4_000_000 for row in detail)
    assert billings == 5_000_000
    assert figure["earned_cents"] == 6_000_000
    assert figure["status"] == "underbilled"
    assert figure["amount_cents"] == 1_000_000


def test_time_entry_is_minutes_and_not_posted(company):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        customer_id = int(
            conn.execute(
                insert(parties).values(company_id=company_id, display_name="Canyon Supply", is_active=True)
            ).inserted_primary_key[0]
        )
        conn.execute(insert(party_roles).values(party_id=customer_id, role="customer", is_1099=False))
        employee_id = int(
            conn.execute(
                insert(parties).values(company_id=company_id, display_name="Pat Sample", is_active=True)
            ).inserted_primary_key[0]
        )
        conn.execute(insert(party_roles).values(party_id=employee_id, role="employee", is_1099=False))
        job_id = create_job(
            conn,
            company_id=company_id,
            customer_party_id=customer_id,
            number="J-100",
            name="Kitchen",
        )
        code_id = int(
            conn.execute(
                select(cost_codes.c.id).where(cost_codes.c.company_id == company_id, cost_codes.c.code == "03")
            ).scalar()
        )
        enter_time(
            conn,
            company_id=company_id,
            employee_party_id=employee_id,
            job_id=job_id,
            cost_code_id=code_id,
            work_date=date(2026, 6, 2),
            hours="7:30",
        )
        stored = conn.execute(select(time_entries.c.minutes, time_entries.c.status)).one()
        posted = conn.execute(text("SELECT COUNT(*) FROM journal_entries")).scalar()
    assert stored.minutes == 450
    assert stored.status == "draft"
    assert posted == 0
    _ = member_id


def test_general_home_collapses_time(tmp_path: Path):
    engine, company_id, _member = create_company_file(
        tmp_path / "general.vca",
        NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id="general"),
    )
    with engine.begin() as conn:
        status = home_status(conn, company_id, date(2026, 6, 15), "general")
        numbers = {row[0] for row in conn.execute(text("SELECT number FROM accounts"))}
    assert status["time_used"] is False
    assert "not used" in status["time"]
    assert "5000" not in numbers


def test_layout_is_per_member_and_survives_a_copy(company, tmp_path: Path):
    engine, company_id, member_id = company
    with engine.begin() as conn:
        set_preference(conn, company_id, member_id, "home.splitter", [240, 640])
        set_preference(conn, company_id, member_id, "layout.remember", False)
        assert remembering_layout(conn, company_id, member_id) is False
        reset_layout(conn, company_id, member_id)
        assert get_preference(conn, company_id, member_id, "home.splitter") is None
        set_preference(conn, company_id, member_id, "home.splitter", [240, 640])
        other = int(
            conn.execute(
                insert(members).values(
                    company_id=company_id,
                    display_name="Second",
                    os_username="second",
                    role="viewer",
                    status="active",
                )
            ).inserted_primary_key[0]
        )
        assert get_preference(conn, company_id, other, "home.splitter") is None
    copy = tmp_path / "copy.vca"
    backup_file(tmp_path / "red-mesa.vca", copy)
    from core.db import upgrade_sqlite

    copied = upgrade_sqlite(copy)
    with copied.begin() as conn:
        assert get_preference(conn, company_id, member_id, "home.splitter") == [240, 640]


def test_report_csv_and_pdf(company, tmp_path: Path):
    engine, company_id, _member = company
    with engine.begin() as conn:
        headers, rows = trial_balance_rows(conn, company_id)
    csv_path = tmp_path / "tb.csv"
    pdf_path = tmp_path / "tb.pdf"
    write_csv(csv_path, headers, rows)
    write_pdf(pdf_path, "Trial Balance", headers, rows)
    assert "Number" in csv_path.read_text(encoding="utf-8")
    assert pdf_path.stat().st_size > 100

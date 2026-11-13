"""Jobs, budgets, and time. Approved time stays operational until payroll exists."""

from __future__ import annotations

from datetime import date

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from core.chart import account_id_by_number
from core.errors import LedgerError
from core.schema import cost_codes, job_budgets, jobs, parties, party_roles, time_entries
from core.services.posting import add_draft, post_entry


def parse_hours(text: str) -> int:
    """7:30 is 7 hours and 30 minutes, stored as 450 minutes."""
    cleaned = text.strip()
    if ":" not in cleaned:
        raise LedgerError("Enter time as hours:minutes")
    hours_text, minutes_text = cleaned.split(":", 1)
    hours = int(hours_text)
    minutes = int(minutes_text)
    if hours < 0 or minutes < 0 or minutes >= 60:
        raise LedgerError("Minutes must be from 0 through 59")
    total = hours * 60 + minutes
    if total <= 0:
        raise LedgerError("Time has to be more than zero")
    return total


def create_job(
    conn: Connection,
    *,
    company_id: int,
    customer_party_id: int,
    number: str,
    name: str,
    status: str = "active",
    contract_amount_cents: int = 0,
    retainage_bp: int | None = None,
) -> int:
    role = conn.execute(
        select(party_roles.c.role).where(
            party_roles.c.party_id == customer_party_id,
            party_roles.c.role == "customer",
        )
    ).first()
    party = conn.execute(select(parties.c.company_id).where(parties.c.id == customer_party_id)).one_or_none()
    if party is None or party.company_id != company_id or role is None:
        raise LedgerError("A job needs a customer in this company")
    if status not in {"estimate", "active", "closed"}:
        raise LedgerError("Job status must be estimate, active, or closed")
    result = conn.execute(
        insert(jobs).values(
            company_id=company_id,
            customer_party_id=customer_party_id,
            number=number.strip(),
            name=name.strip(),
            status=status,
            contract_amount_cents=int(contract_amount_cents),
            retainage_bp=retainage_bp,
        )
    )
    return int(result.inserted_primary_key[0])


def set_job_budget(conn: Connection, job_id: int, cost_code_id: int, amount_cents: int) -> None:
    code = conn.execute(select(cost_codes.c.company_id).where(cost_codes.c.id == cost_code_id)).one()
    job = conn.execute(select(jobs.c.company_id).where(jobs.c.id == job_id)).one()
    if code.company_id != job.company_id:
        raise LedgerError("That cost code is not in this company")
    conn.execute(
        insert(job_budgets).values(job_id=job_id, cost_code_id=cost_code_id, amount_cents=int(amount_cents))
    )


def enter_time(
    conn: Connection,
    *,
    company_id: int,
    employee_party_id: int,
    job_id: int,
    cost_code_id: int,
    work_date: date,
    hours: str,
) -> int:
    minutes = parse_hours(hours)
    result = conn.execute(
        insert(time_entries).values(
            company_id=company_id,
            employee_party_id=employee_party_id,
            job_id=job_id,
            cost_code_id=cost_code_id,
            work_date=work_date,
            minutes=minutes,
            status="draft",
        )
    )
    return int(result.inserted_primary_key[0])


def post_progress_bill(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    job_id: int,
    entry_date: date,
    number: str,
    amount_cents: int,
) -> int:
    receivable = account_id_by_number(conn, company_id, "1100")
    income = account_id_by_number(conn, company_id, "4100")
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=entry_date,
        number=number,
        memo="Progress bill",
        source_type="invoice",
        lines=[
            {"account_id": receivable, "debit_cents": amount_cents, "credit_cents": 0, "job_id": job_id},
            {"account_id": income, "debit_cents": 0, "credit_cents": amount_cents, "job_id": job_id},
        ],
    )
    post_entry(conn, entry_id, member_id)
    return entry_id


def post_vendor_bill(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    job_id: int,
    cost_code_id: int,
    account_number: str,
    party_id: int | None,
    entry_date: date,
    number: str,
    amount_cents: int,
) -> int:
    expense = account_id_by_number(conn, company_id, account_number)
    payable = account_id_by_number(conn, company_id, "2000")
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=entry_date,
        number=number,
        memo="Vendor bill",
        source_type="bill",
        lines=[
            {
                "account_id": expense,
                "debit_cents": amount_cents,
                "credit_cents": 0,
                "job_id": job_id,
                "cost_code_id": cost_code_id,
                "party_id": party_id,
            },
            {
                "account_id": payable,
                "debit_cents": 0,
                "credit_cents": amount_cents,
                "party_id": party_id,
            },
        ],
    )
    post_entry(conn, entry_id, member_id)
    return entry_id

"""Report rows and files. PDF and CSV are produced here. Nothing is transmitted."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table
from sqlalchemy import select
from sqlalchemy.engine import Connection

from core.queries import job_cost_detail, over_under_billing, trial_balance
from core.schema import accounts, jobs, journal_entries, journal_lines, parties


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(int(cents)), 100)
    return f"{sign}{whole:,}.{rest:02d}"


def trial_balance_rows(conn: Connection, company_id: int, as_of: date | None = None) -> tuple[list[str], list[list[str]]]:
    headers = ["Number", "Name", "Debit", "Credit"]
    rows = []
    for row in trial_balance(conn, company_id, as_of):
        net = int(row["net_cents"])
        debit = money(net) if net > 0 else ""
        credit = money(-net) if net < 0 else ""
        rows.append([row["number"], row["name"], debit, credit])
    return headers, rows


def balance_sheet_rows(conn: Connection, company_id: int, as_of: date | None = None) -> tuple[list[str], list[list[str]]]:
    headers = ["Type", "Number", "Name", "Balance"]
    rows = []
    for row in trial_balance(conn, company_id, as_of):
        account = conn.execute(select(accounts.c.type).where(accounts.c.id == row["account_id"])).one()
        if account.type not in {"asset", "liability", "equity"}:
            continue
        rows.append([account.type, row["number"], row["name"], money(row["natural_cents"])])
    return headers, rows


def profit_and_loss_rows(conn: Connection, company_id: int, as_of: date | None = None) -> tuple[list[str], list[list[str]]]:
    headers = ["Type", "Number", "Name", "Amount"]
    rows = []
    for row in trial_balance(conn, company_id, as_of):
        account = conn.execute(select(accounts.c.type).where(accounts.c.id == row["account_id"])).one()
        if account.type not in {"income", "cost_of_sales", "expense", "other_income", "other_expense"}:
            continue
        rows.append([account.type, row["number"], row["name"], money(row["natural_cents"])])
    return headers, rows


def job_profitability_rows(conn: Connection, company_id: int) -> tuple[list[str], list[list[str]]]:
    headers = ["Job", "Contract", "Cost", "Billings", "Earned", "Over/under"]
    rows = []
    for job in conn.execute(select(jobs).where(jobs.c.company_id == company_id).order_by(jobs.c.number)).all():
        figure = over_under_billing(conn, job.id)
        gap = figure["amount_cents"]
        rows.append(
            [
                job.number,
                money(figure["contract_cents"]),
                money(figure["cost_cents"]),
                money(figure["billings_cents"]),
                money(figure["earned_cents"]),
                "" if gap is None else money(gap),
            ]
        )
    return headers, rows


def wip_rows(conn: Connection, company_id: int) -> tuple[list[str], list[list[str]]]:
    headers = ["Job", "Status", "Amount"]
    rows = []
    for job in conn.execute(select(jobs).where(jobs.c.company_id == company_id).order_by(jobs.c.number)).all():
        figure = over_under_billing(conn, job.id)
        amount = figure["amount_cents"]
        rows.append([job.number, figure["status"], "" if amount is None else money(amount)])
    return headers, rows


def job_cost_rows(conn: Connection, job_id: int) -> tuple[list[str], list[list[str]]]:
    headers = ["Cost code", "Name", "Account", "Account name", "Amount"]
    rows = [
        [
            row["cost_code"] or "",
            row["cost_code_name"] or "",
            row["account_number"],
            row["account_name"],
            money(row["cents"]),
        ]
        for row in job_cost_detail(conn, job_id)
    ]
    return headers, rows


def aging_rows(conn: Connection, company_id: int, kind: str, as_of: date) -> tuple[list[str], list[list[str]]]:
    """kind is receivable or payable. Age is measured from the entry date."""
    headers = ["Name", "Date", "Number", "Amount", "Bucket"]
    if kind == "receivable":
        number = "1100"
        amount = journal_lines.c.debit_cents - journal_lines.c.credit_cents
    else:
        number = "2000"
        amount = journal_lines.c.credit_cents - journal_lines.c.debit_cents
    rows_db = conn.execute(
        select(
            parties.c.display_name,
            journal_entries.c.entry_date,
            journal_entries.c.number,
            amount.label("cents"),
        )
        .select_from(
            journal_lines.join(journal_entries, journal_entries.c.id == journal_lines.c.entry_id)
            .join(accounts, accounts.c.id == journal_lines.c.account_id)
            .outerjoin(parties, parties.c.id == journal_lines.c.party_id)
        )
        .where(
            journal_entries.c.company_id == company_id,
            journal_entries.c.status == "posted",
            accounts.c.number == number,
        )
        .order_by(journal_entries.c.entry_date)
    ).all()
    rows = []
    for row in rows_db:
        days = (as_of - row.entry_date).days
        if days <= 30:
            bucket = "current"
        elif days <= 60:
            bucket = "31-60"
        elif days <= 90:
            bucket = "61-90"
        else:
            bucket = "over 90"
        rows.append([row.display_name or "", str(row.entry_date), row.number, money(int(row.cents or 0)), bucket])
    return headers, rows


def write_csv(path: Path | str, headers: list[str], rows: list[list[str]]) -> None:
    path = Path(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def write_pdf(path: Path | str, title: str, headers: list[str], rows: list[list[str]]) -> None:
    path = Path(path)
    document = SimpleDocTemplate(str(path), pagesize=letter)
    data = [headers] + rows
    if len(data) == 1:
        data.append(["—"] * len(headers))
    document.build([Table(data)])

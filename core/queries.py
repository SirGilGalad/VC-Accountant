"""Balances are computed from posted journal lines. Nothing stores them."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, case, func, select
from sqlalchemy.engine import Connection

from core.schema import accounts, journal_entries, journal_lines

POSTED = journal_entries.c.status == "posted"
BILLING_NUMBERS = ("4100", "4120")
RETAINAGE_NUMBER = "1130"


def _posted_lines(as_of: date | None):
    cond = [POSTED]
    if as_of is not None:
        cond.append(journal_entries.c.entry_date <= as_of)
    return journal_lines.join(journal_entries, journal_entries.c.id == journal_lines.c.entry_id).join(
        accounts, accounts.c.id == journal_lines.c.account_id
    ), and_(*cond)


def account_balance(conn: Connection, account_id: int, as_of: date | None = None) -> int:
    """Natural balance in cents. Debit-normal is debit minus credit. Credit-normal is the opposite."""
    joined, cond = _posted_lines(as_of)
    net = func.coalesce(func.sum(journal_lines.c.debit_cents - journal_lines.c.credit_cents), 0)
    natural = case((accounts.c.normal_balance == "credit", -net), else_=net)
    row = conn.execute(
        select(natural).select_from(joined).where(cond, journal_lines.c.account_id == account_id)
    ).one()
    return int(row[0] or 0)


def trial_balance(conn: Connection, company_id: int, as_of: date | None = None) -> list[dict]:
    joined, cond = _posted_lines(as_of)
    net = func.coalesce(func.sum(journal_lines.c.debit_cents - journal_lines.c.credit_cents), 0)
    rows = conn.execute(
        select(
            accounts.c.id,
            accounts.c.number,
            accounts.c.name,
            accounts.c.normal_balance,
            net.label("net_cents"),
        )
        .select_from(joined)
        .where(cond, accounts.c.company_id == company_id)
        .group_by(accounts.c.id, accounts.c.number, accounts.c.name, accounts.c.normal_balance)
        .order_by(accounts.c.number)
    ).all()
    out = []
    for row in rows:
        net_cents = int(row.net_cents or 0)
        natural = -net_cents if row.normal_balance == "credit" else net_cents
        out.append(
            {
                "account_id": row.id,
                "number": row.number,
                "name": row.name,
                "net_cents": net_cents,
                "natural_cents": natural,
            }
        )
    return out


def trial_balance_net(conn: Connection, company_id: int, as_of: date | None = None) -> int:
    return sum(row["net_cents"] for row in trial_balance(conn, company_id, as_of))


def general_ledger(
    conn: Connection, account_id: int, start: date | None = None, end: date | None = None
) -> list[dict]:
    cond = [POSTED, journal_lines.c.account_id == account_id]
    if start is not None:
        cond.append(journal_entries.c.entry_date >= start)
    if end is not None:
        cond.append(journal_entries.c.entry_date <= end)
    rows = conn.execute(
        select(
            journal_entries.c.entry_date,
            journal_entries.c.number,
            journal_entries.c.memo,
            journal_lines.c.debit_cents,
            journal_lines.c.credit_cents,
            journal_lines.c.memo.label("line_memo"),
        )
        .select_from(journal_lines.join(journal_entries, journal_entries.c.id == journal_lines.c.entry_id))
        .where(and_(*cond))
        .order_by(journal_entries.c.entry_date, journal_entries.c.id, journal_lines.c.line_no)
    ).all()
    return [dict(row._mapping) for row in rows]


def job_cost(conn: Connection, job_id: int, as_of: date | None = None, by: str = "account") -> list[dict]:
    joined, cond = _posted_lines(as_of)
    net = func.coalesce(func.sum(journal_lines.c.debit_cents - journal_lines.c.credit_cents), 0)
    group = accounts.c.number if by == "account" else journal_lines.c.cost_code_id
    rows = conn.execute(
        select(group.label("key"), net.label("cents"))
        .select_from(joined)
        .where(
            cond,
            journal_lines.c.job_id == job_id,
            accounts.c.type.in_(("cost_of_sales", "expense")),
        )
        .group_by(group)
    ).all()
    return [{"key": row.key, "cents": int(row.cents or 0)} for row in rows]


def job_billings(conn: Connection, job_id: int, as_of: date | None = None) -> int:
    joined, cond = _posted_lines(as_of)
    credits = func.coalesce(func.sum(journal_lines.c.credit_cents - journal_lines.c.debit_cents), 0)
    row = conn.execute(
        select(credits)
        .select_from(joined)
        .where(cond, journal_lines.c.job_id == job_id, accounts.c.number.in_(BILLING_NUMBERS))
    ).one()
    return int(row[0] or 0)


def retainage_held(conn: Connection, job_id: int) -> int:
    joined, cond = _posted_lines(None)
    net = func.coalesce(func.sum(journal_lines.c.debit_cents - journal_lines.c.credit_cents), 0)
    row = conn.execute(
        select(net)
        .select_from(joined)
        .where(cond, journal_lines.c.job_id == job_id, accounts.c.number == RETAINAGE_NUMBER)
    ).one()
    return int(row[0] or 0)


def job_cost_detail(conn: Connection, job_id: int, as_of: date | None = None) -> list[dict]:
    """Cost by cost code and account. Both are shown so a materials line is not only a number."""
    from core.schema import cost_codes

    joined, cond = _posted_lines(as_of)
    net = func.coalesce(func.sum(journal_lines.c.debit_cents - journal_lines.c.credit_cents), 0)
    rows = conn.execute(
        select(
            cost_codes.c.code,
            cost_codes.c.name.label("cost_code_name"),
            accounts.c.number,
            accounts.c.name.label("account_name"),
            net.label("cents"),
        )
        .select_from(joined.outerjoin(cost_codes, cost_codes.c.id == journal_lines.c.cost_code_id))
        .where(
            cond,
            journal_lines.c.job_id == job_id,
            accounts.c.type.in_(("cost_of_sales", "expense")),
        )
        .group_by(cost_codes.c.code, cost_codes.c.name, accounts.c.number, accounts.c.name)
        .order_by(cost_codes.c.code, accounts.c.number)
    ).all()
    return [
        {
            "cost_code": row.code,
            "cost_code_name": row.cost_code_name,
            "account_number": row.number,
            "account_name": row.account_name,
            "cents": int(row.cents or 0),
        }
        for row in rows
    ]


def over_under_billing(conn: Connection, job_id: int) -> dict:
    """Earned is cost divided by budget, times the contract. Underbilled is earned minus billed."""
    from core.schema import job_budgets, jobs

    job = conn.execute(select(jobs).where(jobs.c.id == job_id)).one()
    budget = int(
        conn.execute(
            select(func.coalesce(func.sum(job_budgets.c.amount_cents), 0)).where(job_budgets.c.job_id == job_id)
        ).scalar()
        or 0
    )
    cost = sum(row["cents"] for row in job_cost(conn, job_id))
    billings = job_billings(conn, job_id)
    contract = int(job.contract_amount_cents or 0)
    if budget <= 0:
        return {
            "status": "needs_budget",
            "amount_cents": None,
            "budget_cents": budget,
            "cost_cents": cost,
            "contract_cents": contract,
            "billings_cents": billings,
            "earned_cents": 0,
        }
    earned = cost * contract // budget
    gap = earned - billings
    if gap > 0:
        status = "underbilled"
    elif gap < 0:
        status = "overbilled"
    else:
        status = "even"
    return {
        "status": status,
        "amount_cents": gap,
        "budget_cents": budget,
        "cost_cents": cost,
        "contract_cents": contract,
        "billings_cents": billings,
        "earned_cents": earned,
    }


def accumulated_depreciation(conn: Connection, asset_id: int, as_of: date | None = None) -> int:
    from core.schema import fixed_assets

    asset = conn.execute(select(fixed_assets).where(fixed_assets.c.id == asset_id)).one()
    joined, cond = _posted_lines(as_of)
    credits = func.coalesce(func.sum(journal_lines.c.credit_cents - journal_lines.c.debit_cents), 0)
    row = conn.execute(
        select(credits)
        .select_from(joined)
        .where(
            cond,
            journal_lines.c.account_id == asset.accum_dep_account_id,
            journal_lines.c.fixed_asset_id == asset_id,
        )
    ).one()
    return int(row[0] or 0)


def format_minutes(minutes: int) -> str:
    hours, rest = divmod(int(minutes), 60)
    return f"{hours} h {rest} m"


def money_plain(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(int(cents)), 100)
    return f"{sign}${whole:,}.{rest:02d}"


def home_status(conn: Connection, company_id: int, today: date, pack_id: str) -> dict:
    """Live lines for the company home. Time is unused outside construction."""
    from core.schema import bank_accounts, jobs, reconciliations, time_entries

    invoices = conn.execute(
        select(journal_entries.c.entry_date, journal_lines.c.debit_cents)
        .select_from(
            journal_lines.join(journal_entries, journal_entries.c.id == journal_lines.c.entry_id).join(
                accounts, accounts.c.id == journal_lines.c.account_id
            )
        )
        .where(
            journal_entries.c.company_id == company_id,
            journal_entries.c.status == "posted",
            journal_entries.c.source_type == "invoice",
            accounts.c.number == "1100",
        )
    ).all()
    due = sum(int(row.debit_cents) for row in invoices)
    late = sum(1 for row in invoices if (today - row.entry_date).days > 30)
    active_jobs = conn.execute(
        select(jobs.c.id).where(jobs.c.company_id == company_id, jobs.c.status == "active")
    ).all()
    under = 0
    for row in active_jobs:
        figure = over_under_billing(conn, row.id)
        if figure["status"] == "underbilled":
            under += 1
    week_start = today.fromordinal(today.toordinal() - today.weekday())
    week_end = week_start.fromordinal(week_start.toordinal() + 6)
    times = conn.execute(
        select(time_entries.c.minutes, time_entries.c.status).where(
            time_entries.c.company_id == company_id,
            time_entries.c.work_date >= week_start,
            time_entries.c.work_date <= week_end,
        )
    ).all()
    entered = sum(int(row.minutes) for row in times)
    unapproved = sum(int(row.minutes) for row in times if row.status != "approved")
    horizon = today.fromordinal(today.toordinal() + 7)
    bills = conn.execute(
        select(journal_entries.c.entry_date, journal_lines.c.credit_cents)
        .select_from(
            journal_lines.join(journal_entries, journal_entries.c.id == journal_lines.c.entry_id).join(
                accounts, accounts.c.id == journal_lines.c.account_id
            )
        )
        .where(
            journal_entries.c.company_id == company_id,
            journal_entries.c.status == "posted",
            journal_entries.c.source_type == "bill",
            accounts.c.number == "2000",
            journal_entries.c.entry_date <= horizon,
        )
    ).all()
    bill_total = sum(int(row.credit_cents) for row in bills)
    reconciled = conn.execute(
        select(reconciliations.c.finished_at)
        .select_from(
            reconciliations.join(bank_accounts, bank_accounts.c.id == reconciliations.c.bank_account_id).join(
                accounts, accounts.c.id == bank_accounts.c.account_id
            )
        )
        .where(
            accounts.c.company_id == company_id,
            accounts.c.number == "1010",
            reconciliations.c.status == "finished",
        )
        .order_by(reconciliations.c.finished_at.desc())
    ).first()
    if reconciled is None or reconciled.finished_at is None:
        banking = "Operating Checking has not been reconciled"
    else:
        stamp = reconciled.finished_at
        shown = stamp.date().isoformat() if hasattr(stamp, "date") else str(stamp)[:10]
        banking = f"Operating Checking last reconciled {shown}"
    time_line = (
        f"This week: {format_minutes(entered)} entered, {format_minutes(unapproved)} not approved"
        if pack_id == "construction"
        else "Time is not used for this company."
    )
    return {
        "bill": f"{len(invoices)} invoices open · {money_plain(due)} due · {late} over 30 days",
        "job": f"{len(active_jobs)} active jobs · {under} underbilled",
        "time": time_line,
        "time_used": pack_id == "construction",
        "pay": f"{len(bills)} bills due in 7 days · {money_plain(bill_total)}",
        "banking": banking,
        "reports": "Job profitability, over/under billing, and profit and loss",
    }

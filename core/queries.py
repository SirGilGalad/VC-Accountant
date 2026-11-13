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


def over_under_billing(conn: Connection, job_id: int) -> dict:
    """Budgets arrive with the construction pack. Until then there is no earned amount."""
    return {"status": "needs_budget", "amount_cents": None}


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

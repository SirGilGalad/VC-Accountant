"""Opening balances are one journal entry, offset to 3900 Opening Balance Equity."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.engine import Connection

from core.chart import account_id_by_number
from core.services.posting import add_draft, post_entry


def post_opening_balances(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    books_start: date,
    balances: list[dict],
) -> int:
    """balances: account_id and natural_cents (positive means the normal side)."""
    from sqlalchemy import select

    from core.schema import accounts

    lines = []
    plug = 0
    for item in balances:
        account = conn.execute(select(accounts).where(accounts.c.id == item["account_id"])).one()
        amount = int(item["natural_cents"])
        if amount == 0:
            continue
        if account.normal_balance == "debit":
            if amount > 0:
                lines.append({"account_id": account.id, "debit_cents": amount, "credit_cents": 0})
                plug -= amount
            else:
                lines.append({"account_id": account.id, "debit_cents": 0, "credit_cents": -amount})
                plug += -amount
        else:
            if amount > 0:
                lines.append({"account_id": account.id, "debit_cents": 0, "credit_cents": amount})
                plug += amount
            else:
                lines.append({"account_id": account.id, "debit_cents": -amount, "credit_cents": 0})
                plug -= -amount
    equity_id = account_id_by_number(conn, company_id, "3900")
    if plug > 0:
        lines.append({"account_id": equity_id, "debit_cents": plug, "credit_cents": 0})
    elif plug < 0:
        lines.append({"account_id": equity_id, "debit_cents": 0, "credit_cents": -plug})
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=books_start - timedelta(days=1),
        number="OPEN",
        memo="Opening balances",
        source_type="manual",
        lines=lines,
    )
    post_entry(conn, entry_id, member_id)
    return entry_id

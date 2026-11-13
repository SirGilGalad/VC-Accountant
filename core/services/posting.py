"""Post, reverse, and draft journal entries. Posted rows are immutable."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from core.errors import (
    ClosedPeriodError,
    InactiveAccountError,
    LineSideError,
    NotFoundError,
    RoleError,
    TooFewLinesError,
    UnbalancedEntryError,
    WrongCompanyError,
)
from core.schema import accounts, cost_codes, jobs, journal_entries, journal_lines, members, parties, periods
from core.services.audit import write_audit

POST_ROLES = {"owner", "accountant", "bookkeeper"}


def _member(conn: Connection, member_id: int):
    row = conn.execute(select(members).where(members.c.id == member_id)).one_or_none()
    if row is None:
        raise NotFoundError(f"Member {member_id} was not found")
    if row.status != "active":
        raise RoleError("This member is disabled")
    return row


def _require_poster(conn: Connection, member_id: int, company_id: int):
    row = _member(conn, member_id)
    if row.company_id != company_id:
        raise WrongCompanyError("Member is not in this company")
    if row.role not in POST_ROLES:
        raise RoleError("A viewer cannot post")
    return row


def add_draft(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    entry_date: date,
    number: str,
    memo: str | None,
    source_type: str,
    lines: list[dict],
) -> int:
    """Insert a draft. Lines are dicts with account_id, debit_cents, credit_cents, and optional tags."""
    _member(conn, member_id)
    result = conn.execute(
        insert(journal_entries).values(
            company_id=company_id,
            entry_date=entry_date,
            number=number,
            memo=memo,
            source_type=source_type,
            status="draft",
        )
    )
    entry_id = int(result.inserted_primary_key[0])
    for index, line in enumerate(lines, start=1):
        _validate_line(conn, company_id, line)
        conn.execute(
            insert(journal_lines).values(
                entry_id=entry_id,
                line_no=index,
                account_id=line["account_id"],
                debit_cents=int(line.get("debit_cents") or 0),
                credit_cents=int(line.get("credit_cents") or 0),
                party_id=line.get("party_id"),
                job_id=line.get("job_id"),
                cost_code_id=line.get("cost_code_id"),
                fixed_asset_id=line.get("fixed_asset_id"),
                pack_ref=line.get("pack_ref"),
                memo=line.get("memo"),
            )
        )
    write_audit(
        conn,
        company_id=company_id,
        member_id=member_id,
        action="create",
        entity_type="journal_entry",
        entity_id=entry_id,
        before=None,
        after={"status": "draft", "number": number},
    )
    return entry_id


def _validate_line(conn: Connection, company_id: int, line: dict) -> None:
    debit = int(line.get("debit_cents") or 0)
    credit = int(line.get("credit_cents") or 0)
    if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
        raise LineSideError("Each line needs exactly one non-zero side")
    account = conn.execute(select(accounts).where(accounts.c.id == line["account_id"])).one_or_none()
    if account is None or account.company_id != company_id:
        raise WrongCompanyError("Account is not in this company")
    if not account.is_active:
        raise InactiveAccountError(f"Account {account.number} is inactive")
    for table, key in ((parties, "party_id"), (jobs, "job_id"), (cost_codes, "cost_code_id")):
        value = line.get(key)
        if value is None:
            continue
        row = conn.execute(select(table).where(table.c.id == value)).one_or_none()
        if row is None or row.company_id != company_id:
            raise WrongCompanyError(f"{key} is not in this company")


def _totals(conn: Connection, entry_id: int) -> tuple[int, int, int]:
    rows = conn.execute(
        select(journal_lines.c.debit_cents, journal_lines.c.credit_cents).where(
            journal_lines.c.entry_id == entry_id
        )
    ).all()
    debits = sum(int(row.debit_cents) for row in rows)
    credits = sum(int(row.credit_cents) for row in rows)
    return len(rows), debits, credits


def post_entry(conn: Connection, entry_id: int, member_id: int) -> None:
    entry = conn.execute(select(journal_entries).where(journal_entries.c.id == entry_id)).one_or_none()
    if entry is None:
        raise NotFoundError(f"Entry {entry_id} was not found")
    if entry.status != "draft":
        raise LedgerStatusError(entry.status)
    _require_poster(conn, member_id, entry.company_id)
    count, debits, credits = _totals(conn, entry_id)
    if debits != credits or debits <= 0:
        raise UnbalancedEntryError(debits, credits)
    if count < 2:
        raise TooFewLinesError("An entry needs at least two lines")
    closed = conn.execute(
        select(periods.c.id).where(
            periods.c.company_id == entry.company_id,
            periods.c.status == "closed",
            periods.c.start <= entry.entry_date,
            periods.c.end >= entry.entry_date,
        )
    ).first()
    if closed is not None:
        raise ClosedPeriodError("That date is in a closed period")
    # Re-check accounts are still active at post time.
    rows = conn.execute(
        select(journal_lines, accounts.c.is_active, accounts.c.company_id)
        .select_from(journal_lines.join(accounts, accounts.c.id == journal_lines.c.account_id))
        .where(journal_lines.c.entry_id == entry_id)
    ).all()
    for row in rows:
        if row.company_id != entry.company_id or not row.is_active:
            raise InactiveAccountError("A line account is inactive or in another company")
        debit = int(row.debit_cents)
        credit = int(row.credit_cents)
        if debit < 0 or credit < 0 or (debit == 0) == (credit == 0):
            raise LineSideError("Each line needs exactly one non-zero side")
    conn.execute(
        update(journal_entries)
        .where(journal_entries.c.id == entry_id)
        .values(
            status="posted",
            posted_at=datetime.now(timezone.utc).replace(tzinfo=None),
            posted_by_member_id=member_id,
        )
    )
    write_audit(
        conn,
        company_id=entry.company_id,
        member_id=member_id,
        action="post",
        entity_type="journal_entry",
        entity_id=entry_id,
        before={"status": "draft"},
        after={"status": "posted"},
    )


class LedgerStatusError(Exception):
    def __init__(self, status: str):
        super().__init__(f"Entry status is {status}")


def reverse_entry(conn: Connection, entry_id: int, member_id: int, reversal_date: date | None = None) -> int:
    entry = conn.execute(select(journal_entries).where(journal_entries.c.id == entry_id)).one()
    if entry.status != "posted":
        raise LedgerStatusError(entry.status)
    _require_poster(conn, member_id, entry.company_id)
    lines = conn.execute(
        select(journal_lines).where(journal_lines.c.entry_id == entry_id).order_by(journal_lines.c.line_no)
    ).all()
    mirrored = [
        {
            "account_id": line.account_id,
            "debit_cents": int(line.credit_cents),
            "credit_cents": int(line.debit_cents),
            "party_id": line.party_id,
            "job_id": line.job_id,
            "cost_code_id": line.cost_code_id,
            "fixed_asset_id": line.fixed_asset_id,
            "pack_ref": line.pack_ref,
            "memo": line.memo,
        }
        for line in lines
    ]
    new_id = add_draft(
        conn,
        company_id=entry.company_id,
        member_id=member_id,
        entry_date=reversal_date or entry.entry_date,
        number=f"R-{entry.number}",
        memo=f"Reversal of {entry.number}",
        source_type="reversal",
        lines=mirrored,
    )
    conn.execute(
        update(journal_entries)
        .where(journal_entries.c.id == new_id)
        .values(reverses_entry_id=entry_id)
    )
    post_entry(conn, new_id, member_id)
    conn.execute(
        update(journal_entries).where(journal_entries.c.id == entry_id).values(status="void")
    )
    conn.execute(
        update(journal_entries).where(journal_entries.c.id == new_id).values(status="void")
    )
    write_audit(
        conn,
        company_id=entry.company_id,
        member_id=member_id,
        action="void",
        entity_type="journal_entry",
        entity_id=entry_id,
        before={"status": "posted"},
        after={"status": "void", "reversal_id": new_id},
    )
    return new_id

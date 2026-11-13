"""Chart of accounts."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from core.chart import normal_balance
from core.errors import AccountNameError, DuplicateAccountError, ParentTypeError, WrongCompanyError
from core.schema import accounts
from core.services.audit import write_audit


def create_account(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    number: str,
    name: str,
    account_type: str,
    subtype: str | None = None,
    parent_id: int | None = None,
    notes: str | None = None,
) -> int:
    cleaned = name.strip()
    if not cleaned:
        raise AccountNameError("An account needs a name")
    number = number.strip()
    if not number:
        raise AccountNameError("An account needs a number")
    existing = conn.execute(
        select(accounts.c.id).where(
            accounts.c.company_id == company_id,
            accounts.c.number == number,
        )
    ).first()
    if existing is not None:
        raise DuplicateAccountError(f"Account number {number} is already used")
    if parent_id is not None:
        parent = conn.execute(select(accounts).where(accounts.c.id == parent_id)).one_or_none()
        if parent is None or parent.company_id != company_id:
            raise WrongCompanyError("The parent account is not in this company")
        if parent.type != account_type:
            raise ParentTypeError("A child account must use the same type as its parent")
        if int(parent.number) >= int(number) if parent.number.isdigit() and number.isdigit() else False:
            raise ParentTypeError("A parent number must be lower than its children")
    result = conn.execute(
        insert(accounts).values(
            company_id=company_id,
            number=number,
            name=cleaned,
            type=account_type,
            subtype=subtype,
            normal_balance=normal_balance(account_type, subtype),
            parent_id=parent_id,
            tax_line=None,
            is_active=True,
            is_system=False,
            notes=notes,
        )
    )
    account_id = int(result.inserted_primary_key[0])
    write_audit(
        conn,
        company_id=company_id,
        member_id=member_id,
        action="create",
        entity_type="account",
        entity_id=account_id,
        before=None,
        after={"number": number, "name": cleaned},
    )
    return account_id


def list_accounts(conn: Connection, company_id: int) -> list:
    return list(
        conn.execute(
            select(accounts).where(accounts.c.company_id == company_id).order_by(accounts.c.number)
        ).all()
    )

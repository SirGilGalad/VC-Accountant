"""Sites and local holds. A hold does not take a payment and does not leave this computer."""

from __future__ import annotations

from datetime import date

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from core.chart import account_id_by_number
from core.errors import LedgerError
from core.schema import reservation_holds, sites
from core.services.posting import add_draft, post_entry


def add_site(
    conn: Connection,
    *,
    company_id: int,
    label: str,
    kind: str,
    nightly_rate_cents: int,
    period_rate_cents: int | None = None,
) -> int:
    if kind not in {"site", "cabin"}:
        raise LedgerError("A site is a site or a cabin")
    result = conn.execute(
        insert(sites).values(
            company_id=company_id,
            label=label.strip(),
            kind=kind,
            nightly_rate_cents=int(nightly_rate_cents),
            period_rate_cents=period_rate_cents,
        )
    )
    return int(result.inserted_primary_key[0])


def _overlaps(arrive: date, depart: date, other_arrive: date, other_depart: date) -> bool:
    return arrive < other_depart and depart > other_arrive


def add_hold(
    conn: Connection,
    *,
    company_id: int,
    guest_party_id: int,
    site_id: int,
    arrive: date,
    depart: date,
    amount_cents: int,
    status: str = "hold",
) -> int:
    if status not in {"hold", "cancelled", "checked_in", "checked_out"}:
        raise LedgerError("That hold status is not allowed")
    if depart <= arrive:
        raise LedgerError("The departure has to be after the arrival")
    site = conn.execute(select(sites.c.id).where(sites.c.id == site_id, sites.c.company_id == company_id)).one_or_none()
    if site is None:
        raise LedgerError("That site is not in this company")
    existing = conn.execute(
        select(reservation_holds.c.arrive, reservation_holds.c.depart).where(
            reservation_holds.c.site_id == site_id,
            reservation_holds.c.status != "cancelled",
        )
    ).all()
    for row in existing:
        if _overlaps(arrive, depart, row.arrive, row.depart):
            raise LedgerError("That site already has a hold for those dates")
    result = conn.execute(
        insert(reservation_holds).values(
            company_id=company_id,
            guest_party_id=guest_party_id,
            site_id=site_id,
            arrive=arrive,
            depart=depart,
            amount_cents=int(amount_cents),
            status=status,
        )
    )
    return int(result.inserted_primary_key[0])


def post_guest_deposit(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    site_id: int,
    hold_id: int | None,
    entry_date: date,
    number: str,
    amount_cents: int,
) -> int:
    ref = f"site:{site_id}"
    cash = account_id_by_number(conn, company_id, "1010")
    liability = account_id_by_number(conn, company_id, "2430")
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=entry_date,
        number=number,
        memo="Guest deposit",
        source_type="deposit",
        lines=[
            {"account_id": cash, "debit_cents": amount_cents, "credit_cents": 0, "pack_ref": ref},
            {"account_id": liability, "debit_cents": 0, "credit_cents": amount_cents, "pack_ref": ref},
        ],
    )
    post_entry(conn, entry_id, member_id)
    if hold_id is not None:
        conn.execute(
            update(reservation_holds)
            .where(reservation_holds.c.id == hold_id, reservation_holds.c.company_id == company_id)
            .values(deposit_entry_id=entry_id)
        )
    return entry_id

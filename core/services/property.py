"""Units, rent, deposits, and a document index. The index stores no files."""

from __future__ import annotations

from datetime import date

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from core.chart import account_id_by_number
from core.errors import LedgerError
from core.schema import document_index, occupancies, units
from core.services.posting import add_draft, post_entry
from packs.property.pack import RETENTION_DEFAULT

DOC_TYPES = ("lease", "notice", "owner_statement", "trust_record", "lien_waiver", "w9", "insurance")
STATES = ("UT", "AZ", "other")


def add_unit(
    conn: Connection,
    *,
    company_id: int,
    property_name: str,
    unit_label: str,
    market_rent_cents: int = 0,
    status: str = "vacant",
) -> int:
    if status not in {"vacant", "occupied", "notice"}:
        raise LedgerError("Unit status must be vacant, occupied, or notice")
    result = conn.execute(
        insert(units).values(
            company_id=company_id,
            property_name=property_name.strip(),
            unit_label=unit_label.strip(),
            market_rent_cents=int(market_rent_cents),
            status=status,
        )
    )
    return int(result.inserted_primary_key[0])


def add_occupancy(
    conn: Connection,
    *,
    unit_id: int,
    tenant_party_id: int,
    start: date,
    end: date | None,
    rent_cents: int,
    deposit_cents: int,
) -> int:
    result = conn.execute(
        insert(occupancies).values(
            unit_id=unit_id,
            tenant_party_id=tenant_party_id,
            start=start,
            end=end,
            rent_cents=int(rent_cents),
            deposit_cents=int(deposit_cents),
        )
    )
    return int(result.inserted_primary_key[0])


def post_rent(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    unit_id: int,
    entry_date: date,
    number: str,
    amount_cents: int,
) -> int:
    unit = conn.execute(select(units.c.id).where(units.c.id == unit_id, units.c.company_id == company_id)).one_or_none()
    if unit is None:
        raise LedgerError("That unit is not in this company")
    ref = f"unit:{unit_id}"
    receivable = account_id_by_number(conn, company_id, "1100")
    income = account_id_by_number(conn, company_id, "4300")
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=entry_date,
        number=number,
        memo="Rent",
        source_type="invoice",
        lines=[
            {"account_id": receivable, "debit_cents": amount_cents, "credit_cents": 0, "pack_ref": ref},
            {"account_id": income, "debit_cents": 0, "credit_cents": amount_cents, "pack_ref": ref},
        ],
    )
    post_entry(conn, entry_id, member_id)
    return entry_id


def post_security_deposit(
    conn: Connection,
    *,
    company_id: int,
    member_id: int,
    unit_id: int,
    entry_date: date,
    number: str,
    amount_cents: int,
) -> int:
    ref = f"unit:{unit_id}"
    cash = account_id_by_number(conn, company_id, "1010")
    held = account_id_by_number(conn, company_id, "2420")
    entry_id = add_draft(
        conn,
        company_id=company_id,
        member_id=member_id,
        entry_date=entry_date,
        number=number,
        memo="Security deposit",
        source_type="deposit",
        lines=[
            {"account_id": cash, "debit_cents": amount_cents, "credit_cents": 0, "pack_ref": ref},
            {"account_id": held, "debit_cents": 0, "credit_cents": amount_cents, "pack_ref": ref},
        ],
    )
    post_entry(conn, entry_id, member_id)
    return entry_id


def add_document(
    conn: Connection,
    *,
    company_id: int,
    doc_type: str,
    state: str,
    party_id: int | None,
    unit_id: int | None,
    recorded_date: date | None,
    location_text: str,
    retention_note: str | None = None,
) -> int:
    if doc_type not in DOC_TYPES:
        raise LedgerError("That document type is not in the index")
    if state not in STATES:
        raise LedgerError("State must be UT, AZ, or other")
    note = (retention_note or "").strip() or RETENTION_DEFAULT
    result = conn.execute(
        insert(document_index).values(
            company_id=company_id,
            doc_type=doc_type,
            state=state,
            party_id=party_id,
            unit_id=unit_id,
            recorded_date=recorded_date,
            retention_note=note,
            location_text=location_text.strip(),
        )
    )
    return int(result.inserted_primary_key[0])


def list_documents(
    conn: Connection,
    company_id: int,
    *,
    doc_type: str | None = None,
    state: str | None = None,
    party_id: int | None = None,
) -> list:
    query = select(document_index).where(document_index.c.company_id == company_id)
    if doc_type:
        query = query.where(document_index.c.doc_type == doc_type)
    if state:
        query = query.where(document_index.c.state == state)
    if party_id is not None:
        query = query.where(document_index.c.party_id == party_id)
    return list(conn.execute(query.order_by(document_index.c.id)).all())

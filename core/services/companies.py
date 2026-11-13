"""Create a company file and the one desktop member."""

from __future__ import annotations

import getpass
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection, Engine

from core.chart import seed_base_chart
from core.db import upgrade_sqlite
from core.errors import LedgerError
from core.packs import PACK_IDS, apply_pack
from core.schema import companies, members, tenants
from core.services.audit import write_audit


@dataclass
class NewCompany:
    name: str
    legal_name: str
    pack_id: str
    entity_type: str = "llc"
    ein: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str = "US"
    phone: str | None = None
    email: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    contact_email: str | None = None
    fiscal_year_start_month: int = 1
    accounting_method: str = "accrual"


def create_company_file(path: Path | str, info: NewCompany) -> tuple[Engine, int, int]:
    if info.pack_id not in PACK_IDS:
        raise LedgerError(f"Unknown pack {info.pack_id}")
    path = Path(path)
    if path.exists():
        raise LedgerError(f"{path} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = upgrade_sqlite(path)
    with engine.begin() as conn:
        company_id, member_id = insert_company(conn, info)
    return engine, company_id, member_id


def insert_company(conn: Connection, info: NewCompany, *, os_username: str | None = None) -> tuple[int, int]:
    if info.pack_id not in PACK_IDS:
        raise LedgerError(f"Unknown pack {info.pack_id}")
    method = info.accounting_method.strip().lower()
    if method not in {"accrual", "cash"}:
        raise LedgerError("Accounting method must be accrual or cash")
    tenant_id = conn.execute(
        insert(tenants).values(subdomain=None, display_name=info.name.strip())
    ).inserted_primary_key[0]
    company_id = conn.execute(
        insert(companies).values(
            tenant_id=tenant_id,
            uuid=str(uuid.uuid4()),
            name=info.name.strip(),
            legal_name=(info.legal_name or info.name).strip(),
            entity_type=info.entity_type,
            ein=(info.ein or None),
            pack_id=info.pack_id,
            address1=info.address1,
            address2=info.address2,
            city=info.city,
            state=info.state,
            postal_code=info.postal_code,
            country=info.country or "US",
            phone=info.phone,
            email=info.email,
            contact_name=info.contact_name,
            contact_phone=info.contact_phone,
            contact_email=info.contact_email,
            fiscal_year_start_month=info.fiscal_year_start_month,
            accounting_method=method,
            schema_version="1",
        )
    ).inserted_primary_key[0]
    username = os_username if os_username is not None else _os_user()
    member_id = conn.execute(
        insert(members).values(
            company_id=company_id,
            display_name=username or "Owner",
            os_username=username,
            role="owner",
            status="active",
        )
    ).inserted_primary_key[0]
    seed_base_chart(conn, int(company_id))
    apply_pack(conn, int(company_id), int(member_id), info.pack_id)
    write_audit(
        conn,
        company_id=int(company_id),
        member_id=int(member_id),
        action="create",
        entity_type="company",
        entity_id=int(company_id),
        after={"name": info.name.strip(), "pack_id": info.pack_id},
    )
    return int(company_id), int(member_id)


def load_company(conn: Connection, company_id: int):
    return conn.execute(select(companies).where(companies.c.id == company_id)).one()


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "Owner"

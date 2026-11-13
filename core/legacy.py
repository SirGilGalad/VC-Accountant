"""Open a v0.3 company file. Back it up, then write a new .vca. Unbalanced history stays draft."""

from __future__ import annotations

import shutil
import sqlite3
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import insert, select, text
from sqlalchemy.engine import Connection

from core.branding import FILE_EXTENSION
from core.chart import normal_balance
from core.db import upgrade_sqlite
from core.schema import (
    accounts,
    companies,
    cost_codes,
    jobs,
    journal_entries,
    journal_lines,
    members,
    parties,
    party_roles,
    tenants,
)
from core.services.companies import _os_user


_TYPE_MAP = {
    "asset": ("asset", None),
    "bank": ("asset", "bank"),
    "accountsreceivable": ("asset", "receivable"),
    "fixedasset": ("asset", "fixed_asset"),
    "othercurrentasset": ("asset", None),
    "otherasset": ("asset", None),
    "contraasset": ("asset", "contra_asset"),
    "liability": ("liability", None),
    "accountspayable": ("liability", "payable"),
    "creditcard": ("liability", "credit_card"),
    "othercurrentliability": ("liability", None),
    "longtermliability": ("liability", None),
    "equity": ("equity", None),
    "income": ("income", None),
    "otherincome": ("other_income", None),
    "costofgoodssold": ("cost_of_sales", None),
    "expense": ("expense", None),
    "otherexpense": ("other_expense", None),
}


def is_legacy(path: Path) -> bool:
    if not path.exists() or path.suffix.lower() != ".vtg":
        return False
    conn = sqlite3.connect(path)
    try:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    return "chart_of_accounts" in names and "alembic_version" not in names


def migrate_vtg(path: Path) -> Path:
    path = Path(path)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(path.name + f".bak-{stamp}")
    shutil.copy2(path, backup)
    dest = path.with_suffix(FILE_EXTENSION)
    if dest.exists():
        dest = path.with_name(path.stem + f"-{stamp}" + FILE_EXTENSION)
    old = sqlite3.connect(path)
    old.row_factory = sqlite3.Row
    engine = upgrade_sqlite(dest)
    try:
        with engine.begin() as conn:
            _copy(old, conn)
    finally:
        old.close()
    return dest


def dollars_to_cents(value) -> int:
    if value is None:
        return 0
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _map_type(raw: str | None) -> tuple[str, str | None]:
    key = (raw or "expense").replace(" ", "").lower()
    return _TYPE_MAP.get(key, ("expense", None))


def _copy(old: sqlite3.Connection, conn: Connection) -> None:
    company = old.execute("SELECT * FROM companies ORDER BY id LIMIT 1").fetchone()
    pack = company["company_type"] if company and company["company_type"] in {
        "construction",
        "general",
    } else "general"
    if company and company["company_type"] == "real_estate":
        pack = "property"
    elif company and company["company_type"] == "rv_resort":
        pack = "resort"
    name = company["name"] if company else "Migrated company"
    tenant_id = conn.execute(insert(tenants).values(display_name=name)).inserted_primary_key[0]
    import uuid

    company_id = conn.execute(
        insert(companies).values(
            tenant_id=tenant_id,
            uuid=str(uuid.uuid4()),
            name=name,
            legal_name=(company["legal_name"] if company and company["legal_name"] else name),
            ein=(company["ein"] if company else None) or None,
            pack_id=pack,
            address1=company["address"] if company else None,
            city=company["city"] if company else None,
            state=company["state"] if company else None,
            postal_code=company["zip"] if company else None,
            phone=company["phone"] if company else None,
            email=company["email"] if company else None,
            fiscal_year_start_month=int(company["fiscal_year_start_month"] or 1) if company else 1,
            accounting_method=_method(company["accounting_method"] if company else None),
            schema_version="1",
        )
    ).inserted_primary_key[0]
    username = _os_user()
    conn.execute(
        insert(members).values(
            company_id=company_id,
            display_name=username,
            os_username=username,
            role="owner",
            status="active",
        )
    )
    account_map: dict[int, int] = {}
    parent_pending: list[tuple[int, int]] = []
    for row in old.execute("SELECT * FROM chart_of_accounts ORDER BY id"):
        account_type, subtype = _map_type(row["account_type"])
        new_id = conn.execute(
            insert(accounts).values(
                company_id=company_id,
                number=str(row["account_number"] or row["id"]),
                name=row["name"],
                type=account_type,
                subtype=subtype,
                normal_balance=normal_balance(account_type, subtype),
                tax_line=None,
                is_active=bool(row["is_active"]) if row["is_active"] is not None else True,
                is_system=bool(row["is_system"]) if row["is_system"] is not None else False,
                notes=row["notes"],
            )
        ).inserted_primary_key[0]
        account_map[row["id"]] = int(new_id)
        if row["parent_id"]:
            parent_pending.append((int(new_id), int(row["parent_id"])))
    for new_id, old_parent in parent_pending:
        mapped = account_map.get(old_parent)
        if mapped:
            conn.execute(text("UPDATE accounts SET parent_id = :p WHERE id = :i"), {"p": mapped, "i": new_id})

    def add_party(display: str, role: str, source: str | None, email=None, phone=None, is_1099=False) -> int:
        party_id = conn.execute(
            insert(parties).values(
                company_id=company_id,
                display_name=display or "Unnamed",
                email=email,
                phone=phone,
                source_id=source or None,
                is_active=True,
            )
        ).inserted_primary_key[0]
        conn.execute(
            insert(party_roles).values(party_id=party_id, role=role, is_1099=bool(is_1099))
        )
        return int(party_id)

    customer_map = {}
    for row in old.execute("SELECT * FROM customers"):
        customer_map[row["id"]] = add_party(row["name"], "customer", row["qb_list_id"], row["email"], row["phone"])
    for row in old.execute("SELECT * FROM vendors"):
        add_party(row["name"], "vendor", row["qb_list_id"], row["email"], row["phone"], row["is_1099_eligible"])
    for row in old.execute("SELECT * FROM employees"):
        display = f"{row['first_name']} {row['last_name']}".strip()
        add_party(display, "employee", row["qb_list_id"], row["email"], row["phone"])

    job_map = {}
    for row in old.execute("SELECT * FROM jobs"):
        status = {"open": "active", "active": "active", "estimate": "estimate", "closed": "closed"}.get(
            str(row["status"] or "").lower(), "active"
        )
        job_id = conn.execute(
            insert(jobs).values(
                company_id=company_id,
                customer_party_id=customer_map.get(row["customer_id"]),
                number=str(row["job_number"] or f"J-{row['id']}"),
                name=row["job_name"],
                status=status,
                contract_amount_cents=dollars_to_cents(row["contract_amount"]),
                source_id=row["qb_job_id"],
            )
        ).inserted_primary_key[0]
        job_map[row["id"]] = int(job_id)

    code_map = {}
    if _has(old, "cost_codes"):
        for row in old.execute("SELECT * FROM cost_codes"):
            category = str(row["category"] or "other").lower()
            if category not in {"labor", "material", "subcontract", "equipment", "other"}:
                category = "other"
            code_id = conn.execute(
                insert(cost_codes).values(
                    company_id=company_id,
                    code=str(row["code"]),
                    name=row["description"] or row["code"],
                    category=category,
                    is_active=True,
                )
            ).inserted_primary_key[0]
            code_map[row["id"]] = int(code_id)

    number = 1
    for txn in old.execute("SELECT * FROM transactions ORDER BY id"):
        raw_lines = list(old.execute("SELECT * FROM transaction_lines WHERE transaction_id = ?", (txn["id"],)))
        built = []
        for line in raw_lines:
            account_id = account_map.get(line["account_id"])
            if account_id is None:
                continue
            debit = dollars_to_cents(line["debit"])
            credit = dollars_to_cents(line["credit"])
            if debit and credit:
                if debit >= credit:
                    debit -= credit
                    credit = 0
                else:
                    credit -= debit
                    debit = 0
            if debit == 0 and credit == 0:
                continue
            built.append(
                {
                    "account_id": account_id,
                    "debit_cents": debit,
                    "credit_cents": credit,
                    "job_id": job_map.get(line["job_id"]),
                    "cost_code_id": code_map.get(line["cost_code_id"]),
                    "memo": line["description"],
                }
            )
        debits = sum(item["debit_cents"] for item in built)
        credits = sum(item["credit_cents"] for item in built)
        balanced = len(built) >= 2 and debits == credits and debits > 0
        entry_id = conn.execute(
            insert(journal_entries).values(
                company_id=company_id,
                entry_date=_as_date(txn["date"]),
                number=str(txn["ref_number"] or number),
                memo=txn["memo"],
                source_type="manual",
                status="draft",
            )
        ).inserted_primary_key[0]
        for index, item in enumerate(built, start=1):
            conn.execute(
                insert(journal_lines).values(
                    entry_id=entry_id,
                    line_no=index,
                    account_id=item["account_id"],
                    debit_cents=item["debit_cents"],
                    credit_cents=item["credit_cents"],
                    job_id=item["job_id"],
                    cost_code_id=item["cost_code_id"],
                    memo=item["memo"],
                )
            )
        if balanced:
            conn.execute(
                text("UPDATE journal_entries SET status = 'posted' WHERE id = :id"),
                {"id": entry_id},
            )
        number += 1
    # Silence unused import if a company has no posted rows to query.
    conn.execute(select(companies.c.id).where(companies.c.id == company_id))


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _method(value: str | None) -> str:
    if value and value.strip().lower().startswith("cash"):
        return "cash"
    return "accrual"


def _has(old: sqlite3.Connection, table: str) -> bool:
    row = old.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None

"""Industry pack ids. Construction seeds extra accounts. Other packs are named for the wizard."""

from __future__ import annotations

import importlib

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from core.chart import account_id_by_number
from core.errors import LedgerError
from core.schema import cost_codes
from core.services.accounts import create_account

PACKS: list[tuple[str, str, str]] = [
    ("construction", "Construction", "Jobs, cost codes, and progress billing on the shared ledger."),
    ("property", "Real estate and property management", "Units, rent, and a document index for Utah and Arizona managers."),
    ("resort", "RV resort and campground", "Sites, cabins, and local reservation holds. Online booking is not connected."),
    ("general", "General business", "The shared chart only."),
    ("professional_services", "Professional services", "Fees, retainers, and engagements kept as jobs."),
    ("retail", "Retail", "Merchandise sales and purchases."),
    ("manufacturing", "Manufacturing", "Raw materials, work in process, and finished goods."),
    ("restaurant", "Restaurant", "Food and beverage sales and cost."),
    ("agriculture", "Agriculture", "Crop and livestock sales and farm costs."),
    ("nonprofit", "Nonprofit", "Contributions, grants, and net-asset classes."),
]

PACK_IDS: tuple[str, ...] = tuple(pack_id for pack_id, _name, _line in PACKS)


def pack_line(pack_id: str) -> str:
    for pid, _name, line in PACKS:
        if pid == pack_id:
            return line
    raise KeyError(pack_id)


def apply_pack(conn: Connection, company_id: int, member_id: int, pack_id: str) -> None:
    """Seed the pack's accounts and cost codes. General has neither."""
    if pack_id not in PACK_IDS:
        raise LedgerError(f"Unknown pack {pack_id}")
    try:
        module = importlib.import_module(f"packs.{pack_id}.pack")
    except ModuleNotFoundError:
        return
    for number, name, account_type, subtype, parent_number in module.accounts:
        parent_id = account_id_by_number(conn, company_id, parent_number) if parent_number else None
        create_account(
            conn,
            company_id=company_id,
            member_id=member_id,
            number=number,
            name=name,
            account_type=account_type,
            subtype=subtype,
            parent_id=parent_id,
            pack_id=pack_id,
        )
    for code, name, category, division in getattr(module, "cost_codes", []):
        exists = conn.execute(
            select(cost_codes.c.id).where(
                cost_codes.c.company_id == company_id,
                cost_codes.c.code == code,
            )
        ).first()
        if exists is not None:
            continue
        conn.execute(
            insert(cost_codes).values(
                company_id=company_id,
                code=code,
                name=name,
                category=category,
                csi_division=division,
                is_active=True,
            )
        )

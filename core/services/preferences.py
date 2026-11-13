"""Last-company prefill and per-member layout keys. No tax id is stored in the prefill file."""

from __future__ import annotations

import json
from pathlib import Path

import platformdirs
from sqlalchemy import delete, insert, select
from sqlalchemy.engine import Connection

from core.schema import ui_preferences

ALLOWED_PREFILL = {
    "address1",
    "address2",
    "city",
    "state",
    "postal_code",
    "country",
    "phone",
    "email",
    "contact_name",
    "contact_phone",
    "contact_email",
    "pack_id",
    "fiscal_year_start_month",
    "accounting_method",
}


def data_dir() -> Path:
    path = Path(platformdirs.user_data_dir("VC Accountant", appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def prefill_path() -> Path:
    return data_dir() / "last_company_details.json"


def recent_path() -> Path:
    return data_dir() / "recent_companies.json"


def save_prefill(details: dict) -> None:
    cleaned = {key: details[key] for key in ALLOWED_PREFILL if key in details and details[key] is not None}
    if "ein" in cleaned:
        raise RuntimeError("Prefill must not store an EIN")
    prefill_path().write_text(json.dumps(cleaned), encoding="utf-8")


def load_prefill() -> dict:
    path = prefill_path()
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: data[key] for key in ALLOWED_PREFILL if key in data}


def remember_recent(entry: dict) -> None:
    path = recent_path()
    rows = []
    if path.exists():
        rows = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in rows if row.get("uuid") != entry["uuid"]]
    rows.insert(0, entry)
    path.write_text(json.dumps(rows[:10]), encoding="utf-8")


def load_recent() -> list[dict]:
    path = recent_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def set_preference(conn: Connection, company_id: int, member_id: int, key: str, value) -> None:
    conn.execute(
        delete(ui_preferences).where(
            ui_preferences.c.company_id == company_id,
            ui_preferences.c.member_id == member_id,
            ui_preferences.c.key == key,
        )
    )
    conn.execute(
        insert(ui_preferences).values(
            company_id=company_id,
            member_id=member_id,
            key=key,
            value_json=json.dumps(value),
        )
    )


def get_preference(conn: Connection, company_id: int, member_id: int, key: str):
    row = conn.execute(
        select(ui_preferences.c.value_json).where(
            ui_preferences.c.company_id == company_id,
            ui_preferences.c.member_id == member_id,
            ui_preferences.c.key == key,
        )
    ).one_or_none()
    if row is None:
        return None
    return json.loads(row.value_json)

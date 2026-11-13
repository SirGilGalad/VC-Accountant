"""Wizard fields round-trip, and prefill never stores an EIN."""

import json
from pathlib import Path

from sqlalchemy import text

from core.services.companies import NewCompany, create_company_file
from core.services.preferences import load_prefill, save_prefill


def test_every_company_field_is_saved(tmp_path: Path):
    info = NewCompany(
        name="Red Mesa Builders LLC",
        legal_name="Red Mesa Builders LLC",
        pack_id="construction",
        entity_type="llc",
        ein=None,
        address1="100 Sample Way",
        address2="Suite 1",
        city="Kanab",
        state="UT",
        postal_code="84741",
        country="US",
        phone="555-0100",
        email="pat@example.com",
        contact_name="Pat Sample",
        contact_phone="555-0101",
        contact_email="pat@example.com",
        fiscal_year_start_month=4,
        accounting_method="cash",
    )
    engine, company_id, _member = create_company_file(tmp_path / "fields.vca", info)
    with engine.begin() as conn:
        row = conn.execute(text("SELECT * FROM companies WHERE id = :id"), {"id": company_id}).mappings().one()
    assert row["address1"] == "100 Sample Way"
    assert row["address2"] == "Suite 1"
    assert row["city"] == "Kanab"
    assert row["state"] == "UT"
    assert row["postal_code"] == "84741"
    assert row["phone"] == "555-0100"
    assert row["email"] == "pat@example.com"
    assert row["contact_name"] == "Pat Sample"
    assert row["contact_phone"] == "555-0101"
    assert row["contact_email"] == "pat@example.com"
    assert row["fiscal_year_start_month"] == 4
    assert row["accounting_method"] == "cash"
    assert row["ein"] is None


def test_prefill_drops_ein(tmp_path, monkeypatch):
    monkeypatch.setattr("core.services.preferences.data_dir", lambda: tmp_path)
    save_prefill(
        {
            "address1": "100 Sample Way",
            "city": "Kanab",
            "ein": "XX-XXXXXXX",
            "name": "Should not stick",
            "pack_id": "construction",
        }
    )
    saved = json.loads((tmp_path / "last_company_details.json").read_text(encoding="utf-8"))
    assert "ein" not in saved
    assert "name" not in saved
    assert load_prefill()["address1"] == "100 Sample Way"


def test_prefill_is_not_written_into_the_working_folder(tmp_path, monkeypatch):
    work = tmp_path / "work"
    data = tmp_path / "appdata"
    work.mkdir()
    data.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr("core.services.preferences.data_dir", lambda: data)
    save_prefill({"address1": "100 Sample Way", "city": "Kanab", "name": "Hidden", "ein": "XX-XXXXXXX"})
    assert list(work.glob("*.json")) == []
    saved = json.loads((data / "last_company_details.json").read_text(encoding="utf-8"))
    assert "ein" not in saved
    assert "name" not in saved

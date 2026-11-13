"""Property, resort, and the named packs share the base chart."""

from datetime import date
from pathlib import Path

from sqlalchemy import select

from core.queries import trial_balance_net
from core.schema import accounts, journal_lines, metadata
from core.services.companies import NewCompany, create_company_file
from core.services.property import add_document, add_unit, list_documents, post_rent, post_security_deposit
from core.services.resort import add_hold, add_site, post_guest_deposit
from packs.property.pack import INDEX_NOTE, RETENTION_DEFAULT
from packs.resort.pack import HOLD_BANNER


def _names(conn, company_id: int) -> dict[str, str]:
    rows = conn.execute(select(accounts.c.number, accounts.c.name).where(accounts.c.company_id == company_id)).all()
    return {row.number: row.name for row in rows}


def _open(tmp_path: Path, pack_id: str):
    return create_company_file(
        tmp_path / f"{pack_id}.vca",
        NewCompany(name="Red Mesa Builders LLC", legal_name="Red Mesa Builders LLC", pack_id=pack_id),
    )


def test_property_keeps_payroll_and_moves_its_own_expenses(tmp_path: Path):
    engine, company_id, _member = _open(tmp_path, "property")
    with engine.begin() as conn:
        names = _names(conn, company_id)
        assert names["6600"] == "Payroll Expenses"
        assert names["6610"] == "Wages"
        assert names["6620"] == "Payroll Taxes"
        assert names["6630"] == "Benefits"
        moved = {name: number for number, name in names.items()}
        assert moved["Property Maintenance"] == "6640"
        assert moved["Property Utilities"] == "6650"
        assert moved["HOA Fees"] == "6660"
        assert moved["Property Taxes"] == "6670"
        assert names["2420"] == "Security Deposits Held"
        assert names["4300"] == "Rental Income"
        assert trial_balance_net(conn, company_id) == 0


def test_resort_keeps_rent_expense(tmp_path: Path):
    engine, company_id, _member = _open(tmp_path, "resort")
    with engine.begin() as conn:
        names = _names(conn, company_id)
        assert names["6700"] == "Rent"
        assert names["6780"] == "Pool and Grounds"
        assert names["2430"] == "Guest Deposits"
        assert trial_balance_net(conn, company_id) == 0


def test_retail_keeps_liability_insurance(tmp_path: Path):
    engine, company_id, _member = _open(tmp_path, "retail")
    with engine.begin() as conn:
        names = _names(conn, company_id)
        assert names["6210"] == "Liability Insurance"
        assert names["6250"] == "Merchant Card Fees"
        assert names["1200"] == "Merchandise Inventory"
        assert trial_balance_net(conn, company_id) == 0


def test_named_packs_add_their_accounts(tmp_path: Path):
    expected = {
        "professional_services": "4500",
        "manufacturing": "1210",
        "restaurant": "2320",
        "agriculture": "4900",
        "nonprofit": "3300",
        "general": None,
    }
    for pack_id, number in expected.items():
        engine, company_id, _member = _open(tmp_path, pack_id)
        with engine.begin() as conn:
            names = _names(conn, company_id)
            assert trial_balance_net(conn, company_id) == 0
            assert len(names) == len(set(names))
        if number is None:
            assert "4500" not in names
            assert "4300" not in names
        else:
            assert number in names


def test_rent_and_deposit_use_pack_refs(tmp_path: Path):
    engine, company_id, member_id = _open(tmp_path, "property")
    with engine.begin() as conn:
        unit_id = add_unit(
            conn,
            company_id=company_id,
            property_name="Wahweap",
            unit_label="4B",
            market_rent_cents=120_000,
        )
        assert trial_balance_net(conn, company_id) == 0
        post_rent(
            conn,
            company_id=company_id,
            member_id=member_id,
            unit_id=unit_id,
            entry_date=date(2026, 6, 1),
            number="RENT-4B",
            amount_cents=120_000,
        )
        post_security_deposit(
            conn,
            company_id=company_id,
            member_id=member_id,
            unit_id=unit_id,
            entry_date=date(2026, 6, 1),
            number="DEP-4B",
            amount_cents=50_000,
        )
        refs = {row.pack_ref for row in conn.execute(select(journal_lines.c.pack_ref)).all()}
        numbers = {
            row.number
            for row in conn.execute(
                select(accounts.c.number)
                .select_from(journal_lines.join(accounts, accounts.c.id == journal_lines.c.account_id))
            ).all()
        }
    assert refs == {f"unit:{unit_id}"}
    assert {"1100", "4300", "1010", "2420"} <= numbers


def test_document_index_filters_and_stores_no_file(tmp_path: Path):
    engine, company_id, _member = _open(tmp_path, "property")
    with engine.begin() as conn:
        add_document(
            conn,
            company_id=company_id,
            doc_type="lease",
            state="AZ",
            party_id=None,
            unit_id=None,
            recorded_date=date(2026, 1, 1),
            location_text="Cabinet A",
        )
        add_document(
            conn,
            company_id=company_id,
            doc_type="w9",
            state="UT",
            party_id=None,
            unit_id=None,
            recorded_date=date(2026, 2, 1),
            location_text="Cabinet B",
        )
        found = list_documents(conn, company_id, doc_type="lease", state="AZ")
        note = found[0].retention_note
    assert len(found) == 1
    assert found[0].location_text == "Cabinet A"
    assert note == RETENTION_DEFAULT
    assert INDEX_NOTE.startswith("This index helps you find records.")


def test_overlapping_holds_are_refused_and_deposits_post(tmp_path: Path):
    engine, company_id, member_id = _open(tmp_path, "resort")
    with engine.begin() as conn:
        site_id = add_site(conn, company_id=company_id, label="A1", kind="site", nightly_rate_cents=4_500)
        add_hold(
            conn,
            company_id=company_id,
            guest_party_id=_guest(conn, company_id),
            site_id=site_id,
            arrive=date(2026, 6, 1),
            depart=date(2026, 6, 5),
            amount_cents=18_000,
        )
        assert trial_balance_net(conn, company_id) == 0
        try:
            add_hold(
                conn,
                company_id=company_id,
                guest_party_id=_guest(conn, company_id),
                site_id=site_id,
                arrive=date(2026, 6, 4),
                depart=date(2026, 6, 8),
                amount_cents=18_000,
            )
            raised = False
        except Exception as exc:
            raised = "already has a hold" in str(exc)
        post_guest_deposit(
            conn,
            company_id=company_id,
            member_id=member_id,
            site_id=site_id,
            hold_id=None,
            entry_date=date(2026, 6, 1),
            number="GD-A1",
            amount_cents=18_000,
        )
        numbers = {
            row.number
            for row in conn.execute(
                select(accounts.c.number)
                .select_from(journal_lines.join(accounts, accounts.c.id == journal_lines.c.account_id))
            ).all()
        }
        refs = {row.pack_ref for row in conn.execute(select(journal_lines.c.pack_ref)).all()}
    assert raised
    assert numbers == {"1010", "2430"}
    assert refs == {f"site:{site_id}"}
    assert "online booking" in HOLD_BANNER.lower()


def test_pack_tables_keep_operational_amounts_off_the_books():
    allowed = {
        "units": {"market_rent_cents"},
        "occupancies": {"rent_cents", "deposit_cents"},
        "sites": {"nightly_rate_cents", "period_rate_cents"},
        "reservation_holds": {"amount_cents"},
        "document_index": set(),
    }
    for name, columns in allowed.items():
        found = {column.name for column in metadata.tables[name].columns if column.name.endswith("cents")}
        assert found == columns
    root = Path(__file__).resolve().parents[2] / "packs"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "Table(" not in text
    screens = Path(__file__).resolve().parents[2] / "desktop" / "packs"
    property_text = (screens / "property.py").read_text(encoding="utf-8")
    resort_text = (screens / "resort.py").read_text(encoding="utf-8")
    assert "QFileDialog" not in property_text
    assert "upload" not in property_text.lower()
    assert "setText(INDEX_NOTE)" in property_text
    for word in ("requests", "urllib", "socket", "http.client"):
        assert word not in resort_text
        assert word not in (root / "resort" / "pack.py").read_text(encoding="utf-8")
    assert "setText(HOLD_BANNER)" in resort_text


def _guest(conn, company_id: int) -> int:
    from sqlalchemy import insert

    from core.schema import parties

    return int(
        conn.execute(insert(parties).values(company_id=company_id, display_name="Guest", is_active=True)).inserted_primary_key[0]
    )

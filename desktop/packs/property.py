"""Units, occupancy, and the document index. This screen does not store a file."""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QTableWidget, QVBoxLayout

from core.schema import units
from core.services.property import add_document, add_unit, list_documents, post_rent, post_security_deposit
from desktop.views.review import fill_table
from packs.property.pack import INDEX_NOTE, RETENTION_DEFAULT
from sqlalchemy import select


def units_screen(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Units and Occupancy")
    with window.launch.engine.connect() as conn:
        rows = conn.execute(
            select(units.c.property_name, units.c.unit_label, units.c.status, units.c.market_rent_cents).where(
                units.c.company_id == window.company_id
            )
        ).all()
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Property", "Unit", "Status", "Market rent"])
    fill_table(table, [[row.property_name, row.unit_label, row.status, str(row.market_rent_cents)] for row in rows])
    add = QPushButton("Add unit")
    rent = QPushButton("Charge rent")
    deposit = QPushButton("Record deposit")

    def _add() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Add unit", "Unit label")
        if not ok or not label.strip():
            return
        with window.launch.engine.begin() as conn:
            add_unit(conn, company_id=window.company_id, property_name="Property", unit_label=label.strip())
        dialog.close()

    def _rent() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Charge rent", "Unit label")
        amount, ok_amount = QInputDialog.getText(dialog, "Charge rent", "Amount in cents")
        if not ok or not ok_amount:
            return
        with window.launch.engine.begin() as conn:
            unit_id = conn.execute(
                select(units.c.id).where(units.c.company_id == window.company_id, units.c.unit_label == label.strip())
            ).scalar()
            post_rent(
                conn,
                company_id=window.company_id,
                member_id=window.member_id,
                unit_id=int(unit_id),
                entry_date=date.today(),
                number=f"RENT-{label.strip()}",
                amount_cents=int(amount),
            )
        window.refresh_lists()

    def _deposit() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Record deposit", "Unit label")
        amount, ok_amount = QInputDialog.getText(dialog, "Record deposit", "Amount in cents")
        if not ok or not ok_amount:
            return
        with window.launch.engine.begin() as conn:
            unit_id = conn.execute(
                select(units.c.id).where(units.c.company_id == window.company_id, units.c.unit_label == label.strip())
            ).scalar()
            post_security_deposit(
                conn,
                company_id=window.company_id,
                member_id=window.member_id,
                unit_id=int(unit_id),
                entry_date=date.today(),
                number=f"DEP-{label.strip()}",
                amount_cents=int(amount),
            )
        window.refresh_lists()

    add.clicked.connect(_add)
    rent.clicked.connect(_rent)
    deposit.clicked.connect(_deposit)
    layout = QVBoxLayout(dialog)
    layout.addWidget(table)
    layout.addWidget(add)
    layout.addWidget(rent)
    layout.addWidget(deposit)
    dialog.exec()


def documents_screen(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Document Index")
    note = QLabel()
    note.setText(INDEX_NOTE)
    note.setWordWrap(True)
    with window.launch.engine.connect() as conn:
        rows = list_documents(conn, window.company_id)
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Type", "State", "Recorded", "Where to find it"])
    fill_table(
        table,
        [[row.doc_type, row.state, str(row.recorded_date or ""), row.location_text] for row in rows],
    )
    add = QPushButton("Add index row")

    def _add() -> None:
        from PyQt6.QtWidgets import QInputDialog

        location, ok = QInputDialog.getText(dialog, "Document Index", "Where to find it")
        if not ok:
            return
        with window.launch.engine.begin() as conn:
            add_document(
                conn,
                company_id=window.company_id,
                doc_type="lease",
                state="UT",
                party_id=None,
                unit_id=None,
                recorded_date=date.today(),
                location_text=location.strip(),
                retention_note=RETENTION_DEFAULT,
            )
        dialog.close()

    add.clicked.connect(_add)
    layout = QVBoxLayout(dialog)
    layout.addWidget(note)
    layout.addWidget(table)
    layout.addWidget(add)
    dialog.exec()

"""Sites and local holds. Nothing on this screen contacts a booking or payment service."""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import QDialog, QLabel, QMessageBox, QPushButton, QTableWidget, QVBoxLayout

from core.schema import parties, reservation_holds, sites
from core.services.resort import add_hold, add_site, post_guest_deposit
from desktop.views.review import fill_table
from packs.resort.pack import HOLD_BANNER
from sqlalchemy import insert, select


def sites_screen(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Sites and Rates")
    with window.launch.engine.connect() as conn:
        rows = conn.execute(
            select(sites.c.label, sites.c.kind, sites.c.nightly_rate_cents).where(sites.c.company_id == window.company_id)
        ).all()
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Label", "Kind", "Nightly rate"])
    fill_table(table, [[row.label, row.kind, str(row.nightly_rate_cents)] for row in rows])
    add = QPushButton("Add site")

    def _add() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Add site", "Label")
        if not ok or not label.strip():
            return
        with window.launch.engine.begin() as conn:
            add_site(
                conn,
                company_id=window.company_id,
                label=label.strip(),
                kind="site",
                nightly_rate_cents=0,
            )
        dialog.close()

    add.clicked.connect(_add)
    layout = QVBoxLayout(dialog)
    layout.addWidget(table)
    layout.addWidget(add)
    dialog.exec()


def holds_screen(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Reservation Holds")
    banner = QLabel()
    banner.setText(HOLD_BANNER)
    banner.setWordWrap(True)
    with window.launch.engine.connect() as conn:
        rows = conn.execute(
            select(reservation_holds.c.arrive, reservation_holds.c.depart, reservation_holds.c.status).where(
                reservation_holds.c.company_id == window.company_id
            )
        ).all()
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Arrive", "Depart", "Status"])
    fill_table(table, [[str(row.arrive), str(row.depart), row.status] for row in rows])
    deposit = QPushButton("Record guest deposit")
    hold = QPushButton("Add hold")

    def _hold() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Add hold", "Site label")
        arrive, ok_arrive = QInputDialog.getText(dialog, "Add hold", "Arrive YYYY-MM-DD")
        depart, ok_depart = QInputDialog.getText(dialog, "Add hold", "Depart YYYY-MM-DD")
        if not ok or not ok_arrive or not ok_depart:
            return
        try:
            with window.launch.engine.begin() as conn:
                site_id = conn.execute(
                    select(sites.c.id).where(sites.c.company_id == window.company_id, sites.c.label == label.strip())
                ).scalar()
                guest_id = int(
                    conn.execute(
                        insert(parties).values(company_id=window.company_id, display_name="Guest", is_active=True)
                    ).inserted_primary_key[0]
                )
                add_hold(
                    conn,
                    company_id=window.company_id,
                    guest_party_id=guest_id,
                    site_id=int(site_id),
                    arrive=date.fromisoformat(arrive.strip()),
                    depart=date.fromisoformat(depart.strip()),
                    amount_cents=0,
                )
        except Exception as exc:
            QMessageBox.warning(dialog, "Reservation Holds", str(exc))

    hold.clicked.connect(_hold)

    def _deposit() -> None:
        from PyQt6.QtWidgets import QInputDialog

        label, ok = QInputDialog.getText(dialog, "Guest deposit", "Site label")
        amount, ok_amount = QInputDialog.getText(dialog, "Guest deposit", "Amount in cents")
        if not ok or not ok_amount:
            return
        with window.launch.engine.begin() as conn:
            site_id = conn.execute(
                select(sites.c.id).where(sites.c.company_id == window.company_id, sites.c.label == label.strip())
            ).scalar()
            post_guest_deposit(
                conn,
                company_id=window.company_id,
                member_id=window.member_id,
                site_id=int(site_id),
                hold_id=None,
                entry_date=date.today(),
                number=f"GD-{label.strip()}",
                amount_cents=int(amount),
            )
        window.refresh_lists()

    deposit.clicked.connect(_deposit)
    layout = QVBoxLayout(dialog)
    layout.addWidget(banner)
    layout.addWidget(table)
    layout.addWidget(hold)
    layout.addWidget(deposit)
    dialog.exec()

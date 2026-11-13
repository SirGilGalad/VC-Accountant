"""Review lists. Figures are read from posted lines."""

from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout

from core.queries import general_ledger
from core.services.accounts import list_accounts


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    whole, rest = divmod(abs(int(cents)), 100)
    return f"{sign}{whole:,}.{rest:02d}"


def fill_table(table: QTableWidget, rows: list[list[str]]) -> None:
    table.setRowCount(len(rows))
    for row_index, row in enumerate(rows):
        for column, value in enumerate(row):
            table.setItem(row_index, column, QTableWidgetItem(value))


def show_register(parent, engine, account_id: int) -> None:
    with engine.connect() as conn:
        accounts = list_accounts(conn, parent.company_id)
        match = next(row for row in accounts if row.id == account_id)
        lines = general_ledger(conn, account_id)
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{match.number} {match.name}")
    dialog.resize(720, 420)
    table = QTableWidget(0, 5)
    table.setHorizontalHeaderLabels(["Date", "Number", "Memo", "Debit", "Credit"])
    fill_table(
        table,
        [
            [
                str(line["entry_date"]),
                line["number"] or "",
                line["line_memo"] or line["memo"] or "",
                money(int(line["debit_cents"])) if line["debit_cents"] else "",
                money(int(line["credit_cents"])) if line["credit_cents"] else "",
            ]
            for line in lines
        ],
    )
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Posted lines only."))
    layout.addWidget(table)
    dialog.exec()

"""Stage an export, tie it, then accept or reject. Nothing posts before Accept."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDateEdit,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.import_quickbooks.quickbooks import AlreadyImported, ImportNotReady, QuickBooksImport
from desktop.views.review import money

IMPORT_LABEL = "Import from QuickBooks"


def attach_launch_button(row, launch) -> None:
    button = QPushButton(IMPORT_LABEL)
    button.clicked.connect(lambda: start_from_launch(launch))
    row.addWidget(button)


def start_from_launch(launch) -> None:
    """New company first, then the import, for a file that is not open yet."""
    launch._open_import_next = True
    launch.new_company()
    launch._open_import_next = False


def add_import_action(menu, window) -> None:
    menu.addAction(f"{IMPORT_LABEL}…", lambda: open_for_company(window))


def open_for_company(window) -> None:
    dialog = ImportDialog(window)
    dialog.exec()
    if hasattr(window, "refresh_lists"):
        window.refresh_lists()


class ImportDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.files: list[str] = []
        self.batch_id: int | None = None
        self.importer = QuickBooksImport(window.launch.engine, window.company_id, window.member_id)
        self.setWindowTitle(IMPORT_LABEL)
        self.resize(860, 640)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose the lists, the transaction detail, and the trial balance."))
        row = QHBoxLayout()
        pick = QPushButton("Choose files")
        pick.clicked.connect(self._pick)
        self.file_label = QLabel("No files yet")
        self.file_label.setWordWrap(True)
        row.addWidget(pick)
        row.addWidget(self.file_label, 1)
        layout.addLayout(row)
        when = QHBoxLayout()
        when.addWidget(QLabel("Cutoff"))
        self.cutoff = QDateEdit()
        self.cutoff.setCalendarPopup(True)
        self.cutoff.setDisplayFormat("yyyy-MM-dd")
        self.cutoff.setDate(QDate.currentDate())
        when.addWidget(self.cutoff)
        when.addStretch(1)
        layout.addLayout(when)
        actions = QHBoxLayout()
        stage = QPushButton("Stage")
        stage.clicked.connect(self._stage)
        self.accept_button = QPushButton("Accept")
        self.accept_button.setEnabled(False)
        self.accept_button.clicked.connect(self._accept)
        reject = QPushButton("Reject")
        reject.clicked.connect(self._reject)
        gap = QPushButton("Opening for years not in detail")
        gap.clicked.connect(self._gap)
        actions.addWidget(stage)
        actions.addWidget(self.accept_button)
        actions.addWidget(reject)
        actions.addWidget(gap)
        layout.addLayout(actions)
        self.status_label = QLabel("Not staged")
        layout.addWidget(self.status_label)
        self.issues = QLabel("")
        self.issues.setWordWrap(True)
        layout.addWidget(self.issues)
        self.tie = QTableWidget(0, 4)
        self.tie.setHorizontalHeaderLabels(["Account", "QuickBooks", "Staged", "Difference"])
        self.tie.cellClicked.connect(self._show_lines)
        layout.addWidget(self.tie, 1)
        self.lines = QTableWidget(0, 4)
        self.lines.setHorizontalHeaderLabels(["Debit", "Credit", "Name", "Class"])
        layout.addWidget(QLabel("Staged lines for the selected account"))
        layout.addWidget(self.lines, 1)

    def _pick(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            IMPORT_LABEL,
            "",
            "Exports (*.iif *.csv *.xlsx)",
        )
        if not paths:
            return
        self.files = paths
        self.file_label.setText(", ".join(path.split("/")[-1].split("\\")[-1] for path in paths))

    def _cutoff(self) -> date:
        picked = self.cutoff.date()
        return date(picked.year(), picked.month(), picked.day())

    def _stage(self) -> None:
        if not self.files:
            QMessageBox.warning(self, IMPORT_LABEL, "Choose the export files first.")
            return
        try:
            self.batch_id = self.importer.stage(self.files, self._cutoff(), label="Import")
        except Exception as exc:
            QMessageBox.critical(self, IMPORT_LABEL, str(exc))
            return
        self._reload()

    def _reload(self) -> None:
        if self.batch_id is None:
            return
        status = self.importer.status(self.batch_id)
        self.status_label.setText(f"Status: {status}")
        self.accept_button.setEnabled(status == "tied")
        messages = [f"{row.severity}: {row.message}" for row in self.importer.issues(self.batch_id)]
        self.issues.setText("\n".join(messages[:12]))
        rows = self.importer.tie(self.batch_id)
        totals = [0, 0, 0]
        self.tie.setRowCount(len(rows) + 1)
        for index, row in enumerate(rows):
            values = [
                row["account_name"],
                money(row["quickbooks_cents"]),
                money(row["staged_cents"]),
                money(row["difference_cents"]),
            ]
            totals[0] += row["quickbooks_cents"]
            totals[1] += row["staged_cents"]
            totals[2] += row["difference_cents"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row["account_key"])
                if row["difference_cents"] != 0:
                    item.setBackground(QColor("#f4d6d6"))
                self.tie.setItem(index, column, item)
        total_items = ["Total", money(totals[0]), money(totals[1]), money(totals[2])]
        for column, value in enumerate(total_items):
            item = QTableWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, "")
            self.tie.setItem(len(rows), column, item)

    def _show_lines(self, row: int, _column: int) -> None:
        if self.batch_id is None:
            return
        item = self.tie.item(row, 0)
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole) or ""
        lines = self.importer.lines_for(self.batch_id, key) if key else []
        self.lines.setRowCount(len(lines))
        for index, line in enumerate(lines):
            values = [
                money(int(line.debit_cents)) if line.debit_cents else "",
                money(int(line.credit_cents)) if line.credit_cents else "",
                line.party_name or "",
                line.source_class or "",
            ]
            for column, value in enumerate(values):
                self.lines.setItem(index, column, QTableWidgetItem(value))

    def _accept(self) -> None:
        if self.batch_id is None:
            return
        try:
            self.importer.accept(self.batch_id)
        except AlreadyImported as exc:
            QMessageBox.warning(self, IMPORT_LABEL, str(exc))
        except ImportNotReady as exc:
            QMessageBox.warning(self, IMPORT_LABEL, str(exc))
        except Exception as exc:
            QMessageBox.critical(self, IMPORT_LABEL, str(exc))
        self._reload()

    def _reject(self) -> None:
        if self.batch_id is None:
            return
        try:
            self.importer.reject(self.batch_id)
        except ImportNotReady as exc:
            QMessageBox.warning(self, IMPORT_LABEL, str(exc))
            return
        self._reload()
        self.lines.setRowCount(0)

    def _gap(self) -> None:
        if self.batch_id is None:
            return
        try:
            self.importer.opening_gap(self.batch_id)
        except ImportNotReady as exc:
            QMessageBox.warning(self, IMPORT_LABEL, str(exc))
            return
        self._reload()

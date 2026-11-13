"""Launch screen: New, Open, Restore, and recent companies."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
)

from core.branding import APP_NAME, FILE_EXTENSION
from core.legacy import is_legacy, migrate_vtg
from core.services.companies import NewCompany, create_company_file, load_company
from core.db import upgrade_sqlite
from core.services.preferences import load_recent, remember_recent
from desktop.company_window import CompanyWindow
from desktop.wizard import NewCompanyWizard
from sqlalchemy import select

from core.schema import companies, members


class LaunchWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(860, 560)
        app = QApplication.instance()
        if app is not None:
            app.setQuitOnLastWindowClosed(False)
        self.engine = None
        self.company_window = None
        self.path: Path | None = None
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel(APP_NAME)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 28px; font-weight: 600;")
        sub = QLabel("Financial management")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        layout.addWidget(sub)
        row = QHBoxLayout()
        for label, handler in (
            ("New Company", self.new_company),
            ("Open Company", self.open_company),
            ("Restore a Backup", self.restore),
        ):
            button = QPushButton(label)
            button.clicked.connect(handler)
            row.addWidget(button)
        layout.addLayout(row)
        layout.addWidget(QLabel("Recent companies"))
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Last used", "Size"])
        self.table.cellDoubleClicked.connect(self._open_recent_row)
        layout.addWidget(self.table)
        self.setCentralWidget(root)
        self.refresh_recent()

    def refresh_recent(self) -> None:
        rows = load_recent()
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            path = Path(row.get("path") or "")
            self.table.setItem(index, 0, QTableWidgetItem(row.get("name") or ""))
            self.table.setItem(index, 1, QTableWidgetItem(row.get("last_opened_at") or ""))
            if path.exists():
                size = path.stat().st_size
                shown = f"{size} B"
            else:
                shown = "File not found"
            self.table.setItem(index, 2, QTableWidgetItem(shown))
            self.table.item(index, 0).setData(Qt.ItemDataRole.UserRole, str(path))

    def new_company(self) -> None:
        wizard = NewCompanyWizard(self)
        if wizard.exec() != QWizard.DialogCode.Accepted:
            return
        data = wizard.collected()
        if not data["name"]:
            QMessageBox.warning(self, "New company", "A company needs a name.")
            return
        default = data["name"].replace(" ", "_") + FILE_EXTENSION
        path, _ = QFileDialog.getSaveFileName(
            self, "Save company", default, f"Company files (*{FILE_EXTENSION})"
        )
        if not path:
            return
        if not path.lower().endswith(FILE_EXTENSION):
            path += FILE_EXTENSION
        try:
            info = NewCompany(**data)
            engine, company_id, member_id = create_company_file(path, info)
        except Exception as exc:
            QMessageBox.critical(self, "New company", str(exc))
            return
        wizard.remember()
        self._open_engine(Path(path), engine, company_id, member_id)

    def open_company(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open company",
            "",
            f"Company files (*{FILE_EXTENSION} *.vtg)",
        )
        if path:
            self.open_path(Path(path))

    def restore(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Restore a backup", "", "Backups (*.bak *.vca)")
        if not path:
            return
        dest, _ = QFileDialog.getSaveFileName(
            self, "Restore into", "restored" + FILE_EXTENSION, f"Company files (*{FILE_EXTENSION})"
        )
        if not dest:
            return
        from core.services.backup import backup_file

        backup_file(path, dest)
        self.open_path(Path(dest))

    def open_path(self, path: Path) -> None:
        try:
            if is_legacy(path):
                path = migrate_vtg(path)
            engine = upgrade_sqlite(path)
            with engine.begin() as conn:
                company = conn.execute(select(companies).limit(1)).one()
                member = conn.execute(
                    select(members).where(members.c.company_id == company.id).limit(1)
                ).one()
            self._open_engine(path, engine, company.id, member.id)
        except Exception as exc:
            QMessageBox.critical(self, "Open company", str(exc))

    def _open_engine(self, path: Path, engine, company_id: int, member_id: int) -> None:
        self.engine = engine
        self.path = path
        with engine.begin() as conn:
            company = load_company(conn, company_id)
        remember_recent(
            {
                "uuid": company.uuid,
                "name": company.name,
                "path": str(path),
                "last_opened_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            }
        )
        self.refresh_recent()
        self.company_window = CompanyWindow(self, path, company_id, member_id, company)
        self.hide()
        self.company_window.show()

    def on_company_closed(self, window: CompanyWindow) -> None:
        window.hide()
        self.company_window = None
        self.show()
        self.refresh_recent()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.company_window is None:
            app = QApplication.instance()
            if app is not None:
                app.quit()
        event.accept()

    def _open_recent_row(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        path = Path(item.data(Qt.ItemDataRole.UserRole))
        if not path.exists():
            QMessageBox.information(self, "Recent companies", "File not found")
            return
        self.open_path(path)


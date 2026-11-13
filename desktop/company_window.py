"""Company window. Close returns to the launch screen. Exit is a separate command."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from core.branding import APP_NAME
from core.services.accounts import create_account, list_accounts
from core.services.backup import backup_file
from desktop.forms import FORM_STATUS

NAV = (
    "Company",
    "Customers",
    "Vendors",
    "Jobs",
    "Employees",
    "Banking",
    "Reports",
    "Lists",
)


class CompanyWindow(QMainWindow):
    def __init__(self, launch, path: Path, company_id: int, member_id: int, company_row):
        super().__init__()
        self.launch = launch
        self.path = Path(path)
        self.company_id = company_id
        self.member_id = member_id
        self.company = company_row
        self._exiting = False
        self.setWindowTitle(f"{APP_NAME} — {company_row.name}")
        self._build()
        self.showMaximized()

    def _build(self) -> None:
        menubar = self.menuBar()
        for name in NAV:
            menu = menubar.addMenu(name)
            if name == "Company":
                menu.addAction("Company Home", lambda: self.stack.setCurrentIndex(0))
                menu.addAction("Back Up Company…", self._backup)
                menu.addAction("Save a Copy As…", self._copy)
                menu.addAction("Close Company", self.close)
                menu.addAction("Help", self._help)
                menu.addAction("About", self._about)
                menu.addAction("Exit", self._exit)
            elif name == "Employees":
                menu.addAction("Payroll forms", lambda: self.stack.setCurrentWidget(self.forms_page))
            else:
                menu.addAction(name, lambda n=name: self._show_section(n))

        root = QWidget()
        layout = QHBoxLayout(root)
        side = QVBoxLayout()
        self.name_label = QLabel(self.company.name)
        self.name_label.setWordWrap(True)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setToolTip(self.company.legal_name)
        side_wrap = QWidget()
        side.addWidget(self.name_label)
        for index, name in enumerate(NAV):
            button = QPushButton(name)
            button.clicked.connect(lambda _checked=False, i=index: self.stack.setCurrentIndex(i))
            side.addWidget(button)
        side.addStretch(1)
        side_wrap.setLayout(side)
        side_wrap.setFixedWidth(180)

        self.stack = QStackedWidget()
        self.stack.addWidget(self._home())
        for name in NAV[1:]:
            if name == "Employees":
                self.forms_page = self._forms()
                self.stack.addWidget(self.forms_page)
            else:
                self.stack.addWidget(self._section(name))
        layout.addWidget(side_wrap)
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage(f"{self.company.name}")

    def _home(self) -> QWidget:
        page = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QLabel(
            "Who you bill, the job, time, who you pay, banking, and reports "
            "share this ledger. Balances come from posted lines."
        )
        left.setWordWrap(True)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Number", "Name", "Type", "Active"])
        self.tree.setColumnCount(4)
        add = QPushButton("Add account")
        add.clicked.connect(self._add_account)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Chart of accounts"))
        right_layout.addWidget(self.tree)
        right_layout.addWidget(add)
        splitter.addWidget(left)
        splitter.addWidget(right)
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        self._load_tree()
        return page

    def _forms(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Payroll forms"))
        self.form_status = QLabel(FORM_STATUS)
        layout.addWidget(self.form_status)
        layout.addStretch(1)
        return page

    def _section(self, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(title))
        layout.addStretch(1)
        return page

    def _show_section(self, name: str) -> None:
        self.stack.setCurrentIndex(NAV.index(name))

    def _load_tree(self) -> None:
        self.tree.clear()
        with self.launch.engine.begin() as conn:
            rows = list_accounts(conn, self.company_id)
        nodes: dict[int, QTreeWidgetItem] = {}
        pending = list(rows)
        guard = 0
        while pending and guard < 10:
            guard += 1
            next_round = []
            for row in pending:
                item = QTreeWidgetItem([row.number, row.name, row.type, "Yes" if row.is_active else "No"])
                if row.parent_id and row.parent_id in nodes:
                    nodes[row.parent_id].addChild(item)
                    nodes[row.id] = item
                elif row.parent_id:
                    next_round.append(row)
                else:
                    self.tree.addTopLevelItem(item)
                    nodes[row.id] = item
            pending = next_round
        self.tree.expandAll()

    def _add_account(self) -> None:
        number, ok = QInputDialog.getText(self, "Add account", "Account number")
        if not ok or not number.strip():
            return
        name, ok = QInputDialog.getText(self, "Add account", "Account name")
        if not ok or not name.strip():
            return
        parent_number, ok = QInputDialog.getText(
            self, "Add account", "Parent number (blank for none)"
        )
        if not ok:
            return
        try:
            with self.launch.engine.begin() as conn:
                rows = list_accounts(conn, self.company_id)
                parent_id = None
                account_type = "expense"
                for row in rows:
                    if parent_number.strip() and row.number == parent_number.strip():
                        parent_id = row.id
                        account_type = row.type
                create_account(
                    conn,
                    company_id=self.company_id,
                    member_id=self.member_id,
                    number=number.strip(),
                    name=name.strip(),
                    account_type=account_type,
                    parent_id=parent_id,
                )
        except Exception as exc:
            QMessageBox.warning(self, "Account", str(exc))
            return
        self._load_tree()

    def _backup(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, "Back Up Company", str(self.path.with_suffix(".vca.bak")))
        if not dest:
            return
        backup_file(self.path, dest)
        self.statusBar().showMessage(f"Backup written to {dest}")

    def _copy(self) -> None:
        dest, _ = QFileDialog.getSaveFileName(self, "Save a Copy As", str(self.path))
        if not dest:
            return
        backup_file(self.path, dest)

    def _help(self) -> None:
        QMessageBox.information(
            self,
            "Help",
            "Every entry posts in a database transaction, so there is nothing else to save.",
        )

    def _about(self) -> None:
        QMessageBox.information(self, "About", APP_NAME)

    def _exit(self) -> None:
        self._exiting = True
        self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._exiting:
            event.accept()
            from PyQt6.QtWidgets import QApplication

            QApplication.quit()
            return
        event.accept()
        self.launch.on_company_closed(self)

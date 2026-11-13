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
    QTableWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from core.branding import APP_NAME
from core.queries import trial_balance
from core.services.accounts import create_account, list_accounts
from core.services.backup import backup_file
from core.services.directory import list_jobs, list_parties
from desktop.forms import FORM_STATUS
from desktop.views.import_wizard import add_import_action
from desktop.views.review import fill_table, money, show_register

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
                add_import_action(menu, self)
                menu.addAction("Close Company", self.close)
                menu.addAction("Help", self._help)
                menu.addAction("About", self._about)
                menu.addAction("Exit", self._exit)
            elif name == "Employees":
                menu.addAction("Payroll forms", lambda: self.stack.setCurrentWidget(self.forms_page))
            elif name == "Reports":
                menu.addAction("Trial Balance", lambda: self._show_section("Reports"))
                menu.addAction("General Ledger", self._pick_register)
            elif name == "Lists":
                menu.addAction("Chart of Accounts", lambda: self._show_section("Lists"))
                menu.addAction("Customers", lambda: self._show_section("Customers"))
                menu.addAction("Vendors", lambda: self._show_section("Vendors"))
                menu.addAction("Employees", lambda: self._show_section("Employees"))
                menu.addAction("Jobs", lambda: self._show_section("Jobs"))
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
        self.refresh_lists()

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
        self.tree.itemDoubleClicked.connect(self._open_register)
        layout = QVBoxLayout(page)
        layout.addWidget(splitter)
        return page

    def _forms(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Payroll forms"))
        self.form_status = QLabel(FORM_STATUS)
        layout.addWidget(self.form_status)
        self.employee_table = QTableWidget(0, 2)
        self.employee_table.setHorizontalHeaderLabels(["Name", "Phone"])
        layout.addWidget(self.employee_table)
        layout.addStretch(1)
        return page

    def _section(self, title: str) -> QWidget:
        if title == "Customers":
            return self._party_page("customer", "Customers")
        if title == "Vendors":
            return self._party_page("vendor", "Vendors")
        if title == "Jobs":
            return self._job_page()
        if title == "Reports":
            return self._report_page()
        if title == "Lists":
            return self._list_page()
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(title))
        layout.addStretch(1)
        return page

    def _party_page(self, role: str, title: str) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel(title))
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(["Name", "Phone", "Email"])
        layout.addWidget(table)
        if role == "customer":
            self.customer_table = table
        else:
            self.vendor_table = table
        return page

    def _job_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Jobs"))
        self.job_table = QTableWidget(0, 3)
        self.job_table.setHorizontalHeaderLabels(["Number", "Name", "Status"])
        layout.addWidget(self.job_table)
        return page

    def _report_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Trial Balance"))
        self.trial_table = QTableWidget(0, 3)
        self.trial_table.setHorizontalHeaderLabels(["Number", "Name", "Balance"])
        layout.addWidget(self.trial_table)
        return page

    def _list_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("Chart of Accounts"))
        self.list_tree = QTreeWidget()
        self.list_tree.setHeaderLabels(["Number", "Name", "Type", "Balance", "Active"])
        self.list_tree.itemDoubleClicked.connect(self._open_register)
        layout.addWidget(self.list_tree)
        return page

    def refresh_lists(self) -> None:
        with self.launch.engine.connect() as conn:
            rows = list_accounts(conn, self.company_id)
            balances = {
                row["account_id"]: row["natural_cents"] for row in trial_balance(conn, self.company_id)
            }
            customers = list_parties(conn, self.company_id, "customer")
            vendors = list_parties(conn, self.company_id, "vendor")
            employees = list_parties(conn, self.company_id, "employee")
            job_rows = list_jobs(conn, self.company_id)
            trial_rows = trial_balance(conn, self.company_id)
        self._fill_tree(self.tree, rows, balances, False)
        if hasattr(self, "list_tree"):
            self._fill_tree(self.list_tree, rows, balances, True)
        fill_table(
            self.customer_table,
            [[row.display_name, row.phone or "", row.email or ""] for row in customers],
        )
        fill_table(
            self.vendor_table,
            [[row.display_name, row.phone or "", row.email or ""] for row in vendors],
        )
        fill_table(
            self.employee_table,
            [[row.display_name, row.phone or ""] for row in employees],
        )
        fill_table(
            self.job_table,
            [[row.number, row.name, row.status] for row in job_rows],
        )
        fill_table(
            self.trial_table,
            [[row["number"], row["name"], money(row["natural_cents"])] for row in trial_rows],
        )

    def _fill_tree(self, tree: QTreeWidget, rows, balances: dict[int, int], with_balance: bool) -> None:
        tree.clear()
        nodes: dict[int, QTreeWidgetItem] = {}
        pending = list(rows)
        guard = 0
        while pending and guard < 12:
            guard += 1
            next_round = []
            for row in pending:
                balance = money(balances.get(row.id, 0))
                active = "Yes" if row.is_active else "No"
                values = [row.number, row.name, row.type, balance, active] if with_balance else [
                    row.number,
                    row.name,
                    row.type,
                    active,
                ]
                item = QTreeWidgetItem(values)
                item.setData(0, Qt.ItemDataRole.UserRole, row.id)
                if row.parent_id and row.parent_id in nodes:
                    nodes[row.parent_id].addChild(item)
                    nodes[row.id] = item
                elif row.parent_id:
                    next_round.append(row)
                else:
                    tree.addTopLevelItem(item)
                    nodes[row.id] = item
            pending = next_round
        tree.expandAll()

    def _open_register(self, item: QTreeWidgetItem, _column: int) -> None:
        account_id = item.data(0, Qt.ItemDataRole.UserRole)
        if account_id:
            show_register(self, self.launch.engine, int(account_id))

    def _pick_register(self) -> None:
        number, ok = QInputDialog.getText(self, "General Ledger", "Account number")
        if not ok or not number.strip():
            return
        with self.launch.engine.connect() as conn:
            rows = list_accounts(conn, self.company_id)
        match = next((row for row in rows if row.number == number.strip()), None)
        if match is None:
            QMessageBox.warning(self, "General Ledger", "That account number is not on the chart.")
            return
        show_register(self, self.launch.engine, int(match.id))

    def _show_section(self, name: str) -> None:
        self.stack.setCurrentIndex(NAV.index(name))

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
        self.refresh_lists()

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

"""Commands from the company menus. Payments stay in the books."""

from __future__ import annotations

from datetime import date

from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
)
from sqlalchemy import select

from core.queries import job_cost_detail, over_under_billing
from core.reports import (
    aging_rows,
    balance_sheet_rows,
    job_profitability_rows,
    profit_and_loss_rows,
    trial_balance_rows,
    wip_rows,
    write_csv,
    write_pdf,
)
from core.schema import cost_codes, jobs
from core.services.jobs import post_progress_bill, post_vendor_bill
from core.services.preferences import remembering_layout, reset_layout, set_preference
from desktop.forms import FORM_STATUS
from desktop.views.review import fill_table, money

BOOKS_ONLY = "Recorded in the books. Nothing was sent."


def _ask(window, title: str, label: str, default: str = "") -> str | None:
    from PyQt6.QtWidgets import QInputDialog

    text, ok = QInputDialog.getText(window, title, label, text=default)
    if not ok:
        return None
    return text.strip()


def company_info(window) -> None:
    company = window.company
    QMessageBox.information(
        window,
        "Company Information",
        f"{company.legal_name}\n{company.address1 or ''} {company.city or ''} {company.state or ''}\n{company.phone or ''}",
    )


def preferences(window) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle("Preferences")
    layout = QVBoxLayout(dialog)
    layout.addWidget(QLabel("Layout"))
    with window.launch.engine.connect() as conn:
        remembered = remembering_layout(conn, window.company_id, window.member_id)
    state = QLabel("Remember my window layout for this company: on" if remembered else "Remember my window layout for this company: off")
    layout.addWidget(state)

    def turn(on: bool) -> None:
        with window.launch.engine.begin() as conn:
            set_preference(conn, window.company_id, window.member_id, "layout.remember", on)
        state.setText(
            "Remember my window layout for this company: on" if on else "Remember my window layout for this company: off"
        )

    row = QHBoxLayout()
    on_button = QPushButton("Remember layout")
    off_button = QPushButton("Do not remember layout")
    reset = QPushButton("Reset layout")
    on_button.clicked.connect(lambda: turn(True))
    off_button.clicked.connect(lambda: turn(False))

    def do_reset() -> None:
        with window.launch.engine.begin() as conn:
            reset_layout(conn, window.company_id, window.member_id)
        window.splitter.setSizes([420, 700])
        state.setText(state.text())

    reset.clicked.connect(do_reset)
    row.addWidget(on_button)
    row.addWidget(off_button)
    row.addWidget(reset)
    layout.addLayout(row)
    dialog.exec()


def restore(window) -> None:
    window.launch.restore()


def open_another(window) -> None:
    window.close()
    window.launch.open_company()


def statements(window) -> None:
    QMessageBox.information(window, "Statements", "Open invoices are on the customer list. Nothing is emailed.")


def form_draft(window, title: str) -> None:
    QMessageBox.information(window, title, FORM_STATUS)


def bank_accounts(window) -> None:
    QMessageBox.information(window, "Bank accounts", "Operating Checking is account 1010. Only the last four digits are stored.")


def show_cost_codes(window) -> None:
    with window.launch.engine.connect() as conn:
        rows = conn.execute(
            select(cost_codes.c.code, cost_codes.c.name, cost_codes.c.category).where(
                cost_codes.c.company_id == window.company_id
            )
        ).all()
    _table(window, "Cost Codes", ["Code", "Name", "Category"], [[row.code, row.name, row.category] for row in rows])


def terms(window) -> None:
    QMessageBox.information(window, "Terms", "Terms are the days stored on each customer or vendor.")


def periods(window) -> None:
    QMessageBox.information(window, "Periods", "No period is closed. Closing a period is a later step.")


def progress_bill(window) -> None:
    number = _ask(window, "New invoice or progress bill", "Invoice number")
    if not number:
        return
    job_number = _ask(window, "New invoice or progress bill", "Job number")
    amount = _ask(window, "New invoice or progress bill", "Amount in cents")
    if not job_number or not amount:
        return
    try:
        with window.launch.engine.begin() as conn:
            job_id = _job_id(conn, window.company_id, job_number)
            post_progress_bill(
                conn,
                company_id=window.company_id,
                member_id=window.member_id,
                job_id=job_id,
                entry_date=date.today(),
                number=number,
                amount_cents=int(amount),
            )
    except Exception as exc:
        QMessageBox.warning(window, "Invoice", str(exc))
        return
    window.refresh_lists()


def receive_payment(window) -> None:
    QMessageBox.information(window, "Receive payment", BOOKS_ONLY + " Use a deposit when you record the cash.")


def vendor_bill(window) -> None:
    number = _ask(window, "Enter bill", "Bill number")
    job_number = _ask(window, "Enter bill", "Job number")
    code = _ask(window, "Enter bill", "Cost code", "03")
    account = _ask(window, "Enter bill", "Account number", "5020")
    amount = _ask(window, "Enter bill", "Amount in cents")
    if not all([number, job_number, code, account, amount]):
        return
    try:
        with window.launch.engine.begin() as conn:
            job_id = _job_id(conn, window.company_id, job_number)
            code_id = conn.execute(
                select(cost_codes.c.id).where(cost_codes.c.company_id == window.company_id, cost_codes.c.code == code)
            ).scalar()
            if code_id is None:
                raise ValueError("That cost code is not on this company")
            post_vendor_bill(
                conn,
                company_id=window.company_id,
                member_id=window.member_id,
                job_id=job_id,
                cost_code_id=int(code_id),
                account_number=account,
                party_id=None,
                entry_date=date.today(),
                number=number,
                amount_cents=int(amount),
            )
    except Exception as exc:
        QMessageBox.warning(window, "Bill", str(exc))
        return
    window.refresh_lists()


def pay_bills(window) -> None:
    QMessageBox.information(window, "Pay bills", BOOKS_ONLY)


def new_job(window) -> None:
    QMessageBox.information(window, "New job", "A job needs a customer. Add the customer on the customer list first.")


def open_job(window) -> None:
    number = _ask(window, "Open job", "Job number")
    if not number:
        return
    with window.launch.engine.connect() as conn:
        try:
            job_id = _job_id(conn, window.company_id, number)
        except Exception as exc:
            QMessageBox.warning(window, "Job", str(exc))
            return
        figure = over_under_billing(conn, job_id)
        detail = job_cost_detail(conn, job_id)
    lines = [
        f"Contract {money(figure['contract_cents'])}",
        f"Cost {money(figure['cost_cents'])}",
        f"Billings {money(figure['billings_cents'])}",
        f"{figure['status']} {'' if figure['amount_cents'] is None else money(figure['amount_cents'])}",
    ]
    for row in detail:
        lines.append(f"{row['cost_code'] or ''} {row['account_name']} {money(row['cents'])}")
    QMessageBox.information(window, number, "\n".join(lines))


def job_cost(window) -> None:
    open_job(window)


def enter_time(window) -> None:
    hours = _ask(window, "Enter time", "Hours:minutes", "7:30")
    if hours is None:
        return
    from core.services.jobs import parse_hours

    try:
        minutes = parse_hours(hours)
    except Exception as exc:
        QMessageBox.warning(window, "Time", str(exc))
        return
    QMessageBox.information(window, "Time", f"{hours} is {minutes} minutes. Pick the employee, job, and cost code on the time grid when you are ready to store it.")


def approve_time(window) -> None:
    QMessageBox.information(
        window,
        "Approve time",
        "Approved time stays on the time record until payroll exists. It is not posted to job labor yet.",
    )


def enter_statement(window) -> None:
    QMessageBox.information(window, "Enter statement", "Statement lines are entered by hand. There is no bank connection.")


def reconcile(window) -> None:
    QMessageBox.information(window, "Reconcile", "Reconciliation compares the statement you entered with the register.")


def transfer(window) -> None:
    QMessageBox.information(window, "Transfers", BOOKS_ONLY)


def deposit(window) -> None:
    QMessageBox.information(window, "Deposits", BOOKS_ONLY)


def show_report(window, kind: str) -> None:
    with window.launch.engine.connect() as conn:
        if kind == "trial":
            title, table = "Trial Balance", trial_balance_rows(conn, window.company_id)
        elif kind == "balance":
            title, table = "Balance Sheet", balance_sheet_rows(conn, window.company_id)
        elif kind == "profit":
            title, table = "Profit & Loss", profit_and_loss_rows(conn, window.company_id)
        elif kind == "job_profitability":
            title, table = "Job Profitability", job_profitability_rows(conn, window.company_id)
        elif kind == "wip":
            title, table = "Over/Under Billing", wip_rows(conn, window.company_id)
        elif kind == "aging":
            title, table = "Aging", aging_rows(conn, window.company_id, "receivable", date.today())
        else:
            title, table = "Report", (["Note"], [["That report is not ready"]])
    headers, rows = table
    dialog = QDialog(window)
    dialog.setWindowTitle(title)
    dialog.resize(760, 480)
    grid = QTableWidget(0, len(headers))
    grid.setHorizontalHeaderLabels(headers)
    fill_table(grid, rows)
    layout = QVBoxLayout(dialog)
    layout.addWidget(grid)

    def export(kind_name: str) -> None:
        suffix = "csv" if kind_name == "csv" else "pdf"
        path, _ = QFileDialog.getSaveFileName(dialog, "Export", f"{title}.{suffix}", f"*.{suffix}")
        if not path:
            return
        if kind_name == "csv":
            write_csv(path, headers, rows)
        else:
            write_pdf(path, title, headers, rows)

    row = QHBoxLayout()
    csv_button = QPushButton("Export CSV")
    pdf_button = QPushButton("Export PDF")
    csv_button.clicked.connect(lambda: export("csv"))
    pdf_button.clicked.connect(lambda: export("pdf"))
    row.addWidget(csv_button)
    row.addWidget(pdf_button)
    layout.addLayout(row)
    dialog.exec()


def _job_id(conn, company_id: int, number: str) -> int:
    job_id = conn.execute(
        select(jobs.c.id).where(jobs.c.company_id == company_id, jobs.c.number == number)
    ).scalar()
    if job_id is None:
        raise ValueError(f"Job {number} was not found")
    return int(job_id)


def _table(window, title: str, headers: list[str], rows: list[list[str]]) -> None:
    dialog = QDialog(window)
    dialog.setWindowTitle(title)
    grid = QTableWidget(0, len(headers))
    grid.setHorizontalHeaderLabels(headers)
    fill_table(grid, rows)
    layout = QVBoxLayout(dialog)
    layout.addWidget(grid)
    dialog.exec()

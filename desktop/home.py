"""Company home. Lanes on the left, chart on the right. Not a flowchart."""

from __future__ import annotations

from datetime import date

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSplitter, QTreeWidget, QVBoxLayout, QWidget

from core.queries import home_status

LANE_TITLES = (
    "Who you bill",
    "The job",
    "Time",
    "Who you pay",
    "Banking",
    "Reports",
)


class HomePane(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.lane_labels: list[QLabel] = []
        left = QWidget()
        left_layout = QVBoxLayout(left)
        status = self._status()
        buttons = {
            "Who you bill": (
                ("New invoice or progress bill", window.new_invoice),
                ("Receive payment", window.receive_payment),
            ),
            "The job": (
                ("Open job", window.open_job),
                ("New job", window.new_job),
                ("Job cost", window.job_cost),
            ),
            "Time": (
                ("Enter time", window.enter_time),
                ("Approve time", window.approve_time),
            ),
            "Who you pay": (
                ("Enter bill", window.enter_bill),
                ("Pay bills", window.pay_bills),
            ),
            "Banking": (
                ("Enter statement", window.enter_statement),
                ("Reconcile", window.reconcile),
            ),
            "Reports": (
                ("Job Profitability", lambda: window.show_report("job_profitability")),
                ("Over/Under Billing", lambda: window.show_report("wip")),
                ("Profit & Loss", lambda: window.show_report("profit")),
            ),
        }
        lines = {
            "Who you bill": status["bill"],
            "The job": status["job"],
            "Time": status["time"],
            "Who you pay": status["pay"],
            "Banking": status["banking"],
            "Reports": status["reports"],
        }
        for title in LANE_TITLES:
            title_label = QLabel(title)
            title_label.setObjectName("lane-title")
            self.lane_labels.append(title_label)
            left_layout.addWidget(title_label)
            line = QLabel(lines[title])
            line.setWordWrap(True)
            left_layout.addWidget(line)
            collapsed = title == "Time" and not status["time_used"]
            if not collapsed:
                row = QHBoxLayout()
                for label, handler in buttons[title]:
                    button = QPushButton(label)
                    button.clicked.connect(handler)
                    row.addWidget(button)
                left_layout.addLayout(row)
        left_layout.addStretch(1)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(QLabel("Chart of accounts"))
        window.tree = QTreeWidget()
        window.tree.setHeaderLabels(["Number", "Name", "Type", "Balance", "Active"])
        window.tree.setColumnCount(5)
        window.tree.itemDoubleClicked.connect(window._open_register)
        add = QPushButton("Add account")
        add.clicked.connect(window._add_account)
        right_layout.addWidget(window.tree)
        right_layout.addWidget(add)
        self.splitter.addWidget(left)
        self.splitter.addWidget(right)
        self.splitter.setSizes([420, 700])
        window.splitter = self.splitter
        layout = QVBoxLayout(self)
        layout.addWidget(self.splitter)

    def _status(self) -> dict:
        with self.window.launch.engine.connect() as conn:
            return home_status(conn, self.window.company_id, date.today(), self.window.company.pack_id)

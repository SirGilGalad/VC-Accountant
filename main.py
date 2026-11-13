#!/usr/bin/env python3
"""
Vantage Core - main.py
Main application for Vantage Core (Contractors Edition)

Flow:
1. Launch screen (jump point)
2. New Company Wizard → simple company info only
3. After creation / Open Company → CompanyMainWindow with:
   - Customizable Dashboard (improved at-a-glance boxes)
   - Boxed sections with icon-linked workflows
"""

import sys
import os
import json
import sqlite3
from datetime import datetime
from PyQt6.QtGui import QBrush
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QMenuBar, QStatusBar, QMessageBox,
    QWizard, QWizardPage, QLineEdit, QComboBox, QFormLayout, QGroupBox,
    QStackedWidget, QScrollArea, QGridLayout, QToolButton, QSizePolicy,
    QFileDialog, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QSplitter,
    QDialog, QTextEdit, QCheckBox, QDialogButtonBox,
    QMdiArea, QMdiSubWindow
)
from PyQt6.QtGui import QAction, QIcon, QBrush, QFont, QColor
from PyQt6.QtCore import Qt, QSettings

# ============================================================
# LAST COMPANY INFO HELPERS (for pre-filling New Company Wizard)
# ============================================================

LAST_COMPANY_FILE = "last_company.json"

def save_last_company_info(data: dict):
    """Save last used company info so the wizard can pre-fill next time."""
    try:
        with open(LAST_COMPANY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_last_company_info() -> dict:
    """Load previously used company info (returns empty dict if none)."""
    if os.path.exists(LAST_COMPANY_FILE):
        try:
            with open(LAST_COMPANY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

# Import database functions
from core.database import initialize_new_company_file, get_connection


# ============================================================
# NEW COMPANY WIZARD (Simple company info only)
# ============================================================
class NewCompanyWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Company - Vantage Core")
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
        self.setMinimumSize(720, 580)

        self.addPage(self._create_company_info_page())
        self.addPage(self._create_contact_page())
        self.addPage(self._create_accounting_page())

        self.finished.connect(self._on_finished)
        self.company_data = {}

        # Pre-fill with last used info if available
        last_info = load_last_company_info()
        if last_info:
            if hasattr(self, 'company_name'):
                self.company_name.setText(last_info.get("name", ""))
            if hasattr(self, 'legal_name'):
                self.legal_name.setText(last_info.get("legal_name", ""))
            if hasattr(self, 'ein'):
                self.ein.setText(last_info.get("ein", ""))
            if hasattr(self, 'address'):
                self.address.setText(last_info.get("address", ""))
            if hasattr(self, 'city'):
                self.city.setText(last_info.get("city", ""))
            if hasattr(self, 'state'):
                self.state.setText(last_info.get("state", ""))
            if hasattr(self, 'zip'):
                self.zip.setText(last_info.get("zip", ""))
            if hasattr(self, 'phone'):
                self.phone.setText(last_info.get("phone", ""))
            if hasattr(self, 'email'):
                self.email.setText(last_info.get("email", ""))

    def _create_company_info_page(self):
        page = QWizardPage()
        page.setTitle("Company Information")
        page.setSubTitle("Enter the basic details for your new company.")

        layout = QVBoxLayout(page)
        group = QGroupBox("Company Details")
        form = QFormLayout(group)

        self.company_name = QLineEdit()
        self.legal_name = QLineEdit()
        self.industry_type = QComboBox()
        self.industry_type.addItems([
            "Construction / Contracting",
            "Real Estate / Property Management",
            "RV Resort / Campground / Hospitality",
            "Retail",
            "Manufacturing",
            "Wholesale / Distribution",
            "Professional Services",
            "Healthcare",
            "Non-Profit / Education",
            "Agriculture",
            "Transportation / Logistics",
            "General Business / Other"
        ])
        self.ein = QLineEdit()
        self.ein.setPlaceholderText("XX-XXXXXXX")

        form.addRow("Company Name *", self.company_name)
        form.addRow("Legal Name", self.legal_name)
        form.addRow("Industry / Entity Type *", self.industry_type)
        form.addRow("EIN / Tax ID", self.ein)

        layout.addWidget(group)
        layout.addStretch()

        note = QLabel("* Required fields")
        note.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(note)
        return page

    def _create_contact_page(self):
        page = QWizardPage()
        page.setTitle("Contact & Address")
        page.setSubTitle("Where can this company be reached?")

        layout = QVBoxLayout(page)
        group = QGroupBox("Contact Information")
        form = QFormLayout(group)

        self.address = QLineEdit()
        self.city = QLineEdit()
        self.state = QLineEdit()
        self.zip = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.contact_person = QLineEdit()

        form.addRow("Street Address", self.address)
        form.addRow("City", self.city)
        form.addRow("State", self.state)
        form.addRow("ZIP Code", self.zip)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Primary Contact", self.contact_person)

        layout.addWidget(group)
        layout.addStretch()
        return page

    def _create_accounting_page(self):
        page = QWizardPage()
        page.setTitle("Accounting Setup")
        page.setSubTitle("Basic accounting preferences for this company.")

        layout = QVBoxLayout(page)
        group = QGroupBox("Accounting Preferences")
        form = QFormLayout(group)

        self.fiscal_year = QComboBox()
        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        for i, m in enumerate(months, 1):
            self.fiscal_year.addItem(f"{i} - {m}", i)
        self.fiscal_year.setCurrentIndex(0)

        self.accounting_method = QComboBox()
        self.accounting_method.addItems(["Accrual", "Cash"])

        form.addRow("Fiscal Year Start Month", self.fiscal_year)
        form.addRow("Accounting Method", self.accounting_method)

        layout.addWidget(group)
        layout.addStretch()

        tip = QLabel("You can change these later in Company Settings.")
        tip.setStyleSheet("color: #6c757d; font-size: 12px;")
        layout.addWidget(tip)
        return page

    def validateCurrentPage(self):
        if self.currentId() == 0:
            if not self.company_name.text().strip():
                QMessageBox.warning(self, "Required", "Company Name is required.")
                return False
        return True

    def _on_finished(self, result):
        if result == QWizard.DialogCode.Accepted:
            self.company_data = {
                "name": self.company_name.text().strip(),
                "legal_name": self.legal_name.text().strip() or self.company_name.text().strip(),
                "industry_type": self.industry_type.currentText(),
                "ein": self.ein.text().strip(),
                "address": self.address.text().strip(),
                "city": self.city.text().strip(),
                "state": self.state.text().strip(),
                "zip": self.zip.text().strip(),
                "phone": self.phone.text().strip(),
                "email": self.email.text().strip(),
                "contact_person": self.contact_person.text().strip(),
                "fiscal_year_start_month": self.fiscal_year.currentData(),
                "accounting_method": self.accounting_method.currentText(),
            }

            # Save last used company info for pre-filling next time
            save_last_company_info(self.company_data)

            self._create_company_file()

    def _create_company_file(self):
        try:
            # Let the user choose where to save the company file
            default_name = self.company_data["name"].replace(" ", "_") + ".vtg"
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save New Company File",
                default_name,
                "Vantage Core Company Files (*.vtg);;All Files (*)"
            )

            if not save_path:
                return  # User cancelled

            if not save_path.lower().endswith(".vtg"):
                save_path += ".vtg"

            if os.path.exists(save_path):
                reply = QMessageBox.question(
                    self, "Overwrite?",
                    f"The file already exists:\n{save_path}\n\nOverwrite it?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
                os.remove(save_path)

            # Map industry to database type
            industry_map = {
                "Construction / Contracting": "construction",
                "Real Estate / Property Management": "real_estate",
                "RV Resort / Campground / Hospitality": "rv_resort",
                "Retail": "retail",
                "Manufacturing": "manufacturing",
                "Wholesale / Distribution": "wholesale",
                "Professional Services": "professional_services",
                "Healthcare": "healthcare",
                "Non-Profit / Education": "nonprofit",
                "Agriculture": "agriculture",
                "Transportation / Logistics": "transportation",
                "General Business / Other": "general",
            }
            company_type = industry_map.get(self.company_data["industry_type"], "general")

            success = initialize_new_company_file(
                save_path,
                company_name=self.company_data["name"],
                company_type=company_type,
                legal_name=self.company_data["legal_name"],
                ein=self.company_data["ein"] or None,
                fiscal_year_start_month=self.company_data["fiscal_year_start_month"],
                accounting_method=self.company_data["accounting_method"]
            )

            if success:
                QMessageBox.information(
                    self,
                    "Company Created",
                    f"Company '{self.company_data['name']}' created successfully!\n\n"
                    f"File saved to:\n{save_path}\n\n"
                    "Opening company interface..."
                )
                if self.parent():
                    self.parent().open_company_window(save_path, self.company_data)
            else:
                QMessageBox.critical(self, "Error", "Failed to create company file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not create company:\n{str(e)}")


# ============================================================
# COMPANY MAIN WINDOW (After company is created / opened)
# ============================================================
class CompanyMainWindow(QMainWindow):
    def __init__(self, company_path: str, company_data: dict, parent=None):
        super().__init__(parent)
        self.company_path = company_path
        self.company_data = company_data

        self.setWindowTitle(f"Vantage Core — {company_data.get('name', 'Company')}")
        self.setGeometry(100, 80, 1500, 950)
        self.setMinimumSize(1200, 800)

        # Icon
        icon_path = "vantage_core_icon.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self._build_ui()
        self.statusBar().showMessage(f"Company loaded: {company_data.get('name')}  |  {company_path}")

        # Open maximized (full screen)
        self.showMaximized()

        # Setup settings for remembering layout per company
        self.settings = QSettings("VantageCore", "CompanyLayout")
        self._restore_layout()

    def closeEvent(self, event):
        """Save layout (splitter sizes, column widths) before closing."""
        self._save_layout()
        QApplication.quit()
        event.accept()

    def _save_layout(self):
        """Save QSplitter state and QTreeWidget header state for this company."""
        try:
            key = f"splitter_{self.company_path}"
            # Find the splitter in Company Home view
            for i in range(self.content_stack.count()):
                widget = self.content_stack.widget(i)
                if "company_home" in str(type(widget)).lower() or hasattr(widget, 'findChild'):
                    splitter = widget.findChild(QSplitter)
                    if splitter:
                        self.settings.setValue(key, splitter.saveState())
                        break

            # Save QTreeWidget header state (column widths)
            tree_key = f"tree_header_{self.company_path}"
            for i in range(self.content_stack.count()):
                widget = self.content_stack.widget(i)
                tree = widget.findChild(QTreeWidget)
                if tree:
                    self.settings.setValue(tree_key, tree.header().saveState())
                    break
        except Exception:
            pass

    def _restore_layout(self):
        """Restore saved splitter and column widths."""
        try:
            key = f"splitter_{self.company_path}"
            splitter_state = self.settings.value(key)
            if splitter_state:
                for i in range(self.content_stack.count()):
                    widget = self.content_stack.widget(i)
                    splitter = widget.findChild(QSplitter)
                    if splitter:
                        splitter.restoreState(splitter_state)
                        break

            tree_key = f"tree_header_{self.company_path}"
            header_state = self.settings.value(tree_key)
            if header_state:
                for i in range(self.content_stack.count()):
                    widget = self.content_stack.widget(i)
                    tree = widget.findChild(QTreeWidget)
                    if tree:
                        tree.header().restoreState(header_state)
                        break
        except Exception:
            pass

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ========== LEFT SIDEBAR ==========
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QFrame {
                background-color: #1a3c6e;
                color: white;
            }
            QToolButton {
                background-color: transparent;
                color: white;
                border: none;
                text-align: left;
                padding: 14px 16px;
                font-size: 14px;
                font-weight: 500;
            }
            QToolButton:hover {
                background-color: #2c5aa0;
            }
            QToolButton:checked {
                background-color: #0d2a4f;
                border-left: 4px solid #4fc3f7;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 20, 0, 20)
        sidebar_layout.setSpacing(4)

        company_label = QLabel(self.company_data.get("name", "Company"))
        company_label.setStyleSheet("font-size: 15px; font-weight: bold; padding: 10px 16px; color: #a0c4ff;")
        company_label.setWordWrap(True)
        company_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar_layout.addWidget(company_label)

        self.nav_buttons = {}
        sections = [
            ("dashboard", "Dashboard"),
            ("company_home", "Home"),
            ("payroll", "Employees"),
            ("customers", "Customers"),
            ("vendors", "Vendors"),
            ("jobs", "Jobs / Projects"),
            ("reports", "Reports"),
            ("settings", "Settings"),
        ]

        for key, label in sections:
            btn = QToolButton()
            btn.setText(f"  {label}")
            btn.setCheckable(True)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.clicked.connect(lambda checked, k=key: self._switch_view(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()
        main_layout.addWidget(sidebar)

        # ========== MAIN CONTENT AREA ==========
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack, stretch=1)

        self.views = {
            "dashboard": self._create_dashboard_view(),
            "company_home": self._create_company_home_view(),  # New Chart of Accounts view
            "payroll": self._create_section_view("Payroll", "Payroll runs, tax forms, employee pay, and unemployment."),
            "customers": self._create_section_view("Customers", "Manage customer list, invoices, and statements."),
            "vendors": self._create_section_view("Vendors", "Manage vendor list, bills, and 1099 tracking."),
            "jobs": self._create_section_view("Jobs / Projects", "Job costing, WIP, progress billing, change orders."),
            "reports": self._create_section_view("Reports", "Custom PDF reports, WIP schedules, profitability, etc."),
            "settings": self._create_section_view("Settings", "Company preferences, tax tables, users (future), backup."),
        }

        for key, widget in self.views.items():
            self.content_stack.addWidget(widget)

        self._switch_view("dashboard")
        self._create_menu_bar()

    def _create_company_home_view(self):
        """Company Home - QB-style workflow with hierarchical Chart of Accounts + draggable QSplitter."""
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(12)

        # Header
        header = QLabel("Company Home")
        header.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a3c6e;")
        main_layout.addWidget(header)

        subtitle = QLabel("Quick access to core activities. Drag the divider to resize panels.")
        subtitle.setStyleSheet("color: #6c757d; font-size: 13px;")
        main_layout.addWidget(subtitle)

        # QSplitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # === Workflow Cards ===
        workflow_group = QGroupBox("Quick Workflows")
        workflow_group.setStyleSheet("""
            QGroupBox {
                font-size: 15px;
                font-weight: 600;
                color: #1a3c6e;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 8px;
                padding-top: 12px;
            }
        """)
        workflow_layout = QGridLayout(workflow_group)
        workflow_layout.setSpacing(12)

        workflows = [
            ("🏦 Banking", "Reconcile bank accounts & transactions", "banking"),
            ("👥 Customers", "Create invoices, receive payments", "customers"),
            ("🧾 Vendors", "Enter bills, pay vendors, 1099s", "vendors"),
            ("📋 Jobs", "Track job costs, progress billing, WIP", "jobs"),
            ("📊 Reports", "Financial reports, tax prep, profitability", "reports"),
            ("⚙️ Settings", "Company info, preferences, users", "settings"),
        ]

        for idx, (title, desc, key) in enumerate(workflows):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("""
                QFrame {
                    background: white;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                    padding: 12px;
                }
                QFrame:hover {
                    border: 1px solid #1a3c6e;
                    background: #f8f9fa;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setSpacing(4)

            title_label = QLabel(title)
            title_label.setStyleSheet("font-size: 15px; font-weight: 700; color: #1a3c6e;")
            card_layout.addWidget(title_label)

            desc_label = QLabel(desc)
            desc_label.setStyleSheet("font-size: 12px; color: #495057;")
            desc_label.setWordWrap(True)
            card_layout.addWidget(desc_label)

            btn = QPushButton("Open")
            btn.setStyleSheet("font-size: 12px; padding: 4px 12px; margin-top: 6px;")
            btn.clicked.connect(lambda checked=False, k=key: self._switch_view(k))
            card_layout.addWidget(btn)

            row = idx // 3
            col = idx % 3
            workflow_layout.addWidget(card, row, col)

        splitter.addWidget(workflow_group)

        # === Hierarchical Chart of Accounts (QTreeWidget) ===
        coa_group = QGroupBox("Chart of Accounts (Hierarchical • Drag divider to resize)")
        coa_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                color: #1a3c6e;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }
        """)
        coa_layout = QVBoxLayout(coa_group)

        tree = QTreeWidget()
        tree.setColumnCount(5)
        tree.setHeaderLabels(["Account #", "Account Name", "Type", "Tax Line", "Active"])
        tree.setAlternatingRowColors(True)
        tree.setSelectionBehavior(QTreeWidget.SelectionBehavior.SelectRows)
        tree.setExpandsOnDoubleClick(True)
        tree.setStyleSheet("""
            QTreeWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                font-size: 13px;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 8px;
                font-weight: bold;
            }
        """)

        # Load and build hierarchical tree
        try:
            conn = get_connection(self.company_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, account_number, name, account_type, tax_line_mapping, is_active, parent_id
                FROM chart_of_accounts
                ORDER BY account_number
            """)
            accounts = cursor.fetchall()
            conn.close()

            account_dict = {}
            for acc in accounts:
                acc_id, number, name, acc_type, tax_line, is_active, parent_id = acc
                account_dict[acc_id] = {
                    'number': number or '',
                    'name': name,
                    'type': acc_type,
                    'tax_line': tax_line or '',
                    'active': 'Yes' if is_active else 'No',
                    'parent_id': parent_id,
                    'children': []
                }

            # Build parent-child relationships (improved)
            for acc_id, data in account_dict.items():
                if data['parent_id'] is not None and data['parent_id'] in account_dict:
                    account_dict[data['parent_id']]['children'].append((acc_id, data))

            def add_tree_item(parent_widget, acc_id, data):
                item = QTreeWidgetItem(parent_widget)
                item.setText(0, data['number'])
                item.setText(1, data['name'])
                item.setText(2, data['type'])
                item.setText(3, data['tax_line'])
                item.setText(4, data['active'])
                sorted_children = sorted(data.get('children', []), key=lambda x: x[1]['number'] or '')
                for child_id, child_data in sorted_children:
                    add_tree_item(item, child_id, child_data)
                return item

            root_items = [(aid, adata) for aid, adata in account_dict.items() if adata['parent_id'] is None or adata['parent_id'] not in account_dict]
            for acc_id, data in sorted(root_items, key=lambda x: x[1]['number'] or ''):
                add_tree_item(tree, acc_id, data)

            tree.expandToDepth(0)

        except Exception as e:
            error_label = QLabel(f"⚠️ Error loading accounts: {str(e)}")
            error_label.setStyleSheet("color: #dc3545;")
            coa_layout.addWidget(error_label)

        coa_layout.addWidget(tree, stretch=1)

        add_btn = QPushButton("＋ Add Custom Account")
        add_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-weight: 600;
                background-color: #1a3c6e;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #15325a;
            }
        """)
        add_btn.clicked.connect(self._show_add_account_dialog)
        coa_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignRight)

        splitter.addWidget(coa_group)
        splitter.setSizes([300, 500])  # Initial sizes

        main_layout.addWidget(splitter, stretch=1)

        return container

    def _show_add_account_dialog(self):
        """Dialog to add a custom account with parent selection."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Custom Account")
        dialog.setMinimumWidth(520)

        layout = QFormLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        # Parent Account
        parent_combo = QComboBox()
        parent_combo.addItem("(None - Top Level Account)", None)

        # Load existing accounts for parent selection
        try:
            conn = get_connection(self.company_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, account_number, name FROM chart_of_accounts ORDER BY account_number")
            for acc_id, number, name in cursor.fetchall():
                display = f"{number} - {name}" if number else name
                parent_combo.addItem(display, acc_id)
            conn.close()
        except Exception:
            pass

        # Account Number
        number_edit = QLineEdit()
        number_edit.setPlaceholderText("e.g. 6501")

        # Account Name
        name_edit = QLineEdit()
        name_edit.setPlaceholderText("e.g. Insurance - General Liability")

        # Account Type
        type_combo = QComboBox()
        type_combo.addItems(["Asset", "Liability", "Equity", "Income", "CostOfGoodsSold", "Expense"])

        # Tax Line Mapping
        tax_edit = QLineEdit()
        tax_edit.setPlaceholderText("e.g. Expense or Schedule C")

        # Description / Notes
        notes_edit = QTextEdit()
        notes_edit.setPlaceholderText("Optional description or notes about this account...")
        notes_edit.setMaximumHeight(80)

        # Active
        active_check = QCheckBox("Active")
        active_check.setChecked(True)

        layout.addRow("Parent Account:", parent_combo)
        layout.addRow("Account Number *:", number_edit)
        layout.addRow("Account Name *:", name_edit)
        layout.addRow("Account Type:", type_combo)
        layout.addRow("Tax Line Mapping:", tax_edit)
        layout.addRow("Description / Notes:", notes_edit)
        layout.addRow("", active_check)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addRow(button_box)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            parent_id = parent_combo.currentData()
            number = number_edit.text().strip()
            name = name_edit.text().strip()
            acc_type = type_combo.currentText()
            tax_line = tax_edit.text().strip()
            notes = notes_edit.toPlainText().strip()
            is_active = active_check.isChecked()

            if not name:
                QMessageBox.warning(self, "Missing Information", "Account Name is required.")
                return

            try:
                conn = get_connection(self.company_path)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO chart_of_accounts 
                    (company_id, account_number, name, account_type, tax_line_mapping, parent_id, is_active, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (self.company_id if hasattr(self, 'company_id') else None, 
                      number, name, acc_type, tax_line, parent_id, is_active, notes))
                conn.commit()
                conn.close()

                QMessageBox.information(self, "Success", f"Account '{name}' added successfully.")
                # Refresh the Company Home view
                self._refresh_company_home()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to add account:\n{str(e)}")

    def _refresh_company_home(self):
        """Refresh the Company Home view after adding an account."""
        # Find and replace the current company_home view
        for i in range(self.content_stack.count()):
            widget = self.content_stack.widget(i)
            if widget == self.views.get("company_home"):
                new_view = self._create_company_home_view()
                self.content_stack.removeWidget(widget)
                widget.deleteLater()
                self.views["company_home"] = new_view
                self.content_stack.insertWidget(i, new_view)
                self.content_stack.setCurrentWidget(new_view)
                break

    def _create_menu_bar(self):
        menubar = self.menuBar()

        # File (keep as is)
        file_menu = menubar.addMenu("&File")
        save_action = QAction("&Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)

        save_as_action = QAction("Save &As...", self)
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self._on_save_as)

        close_action = QAction("Close Company", self)
        close_action.triggered.connect(self.close)

        exit_action = QAction("E&xit", self)
        exit_action.triggered.connect(QApplication.instance().quit)

        file_menu.addAction(save_action)
        file_menu.addAction(save_as_action)
        file_menu.addSeparator()
        file_menu.addAction(close_action)
        file_menu.addSeparator()
        file_menu.addAction(exit_action)

        # === New menus after File (as requested) ===
        edit_menu = menubar.addMenu("&Edit")
        view_menu = menubar.addMenu("&View")
        lists_menu = menubar.addMenu("&Lists")
        favorites_menu = menubar.addMenu("&Favorites")
        contractor_menu = menubar.addMenu("&Contractor")

        # Company (was Company Home)
        company_menu = menubar.addMenu("&Company")
        coa_action = QAction("Chart of Accounts", self)
        coa_action.triggered.connect(lambda: self._switch_view("company_home"))
        company_menu.addAction(coa_action)

        # Employees (was Payroll)
        employees_menu = menubar.addMenu("&Employees")
        payroll_action = QAction("Payroll Dashboard", self)
        payroll_action.triggered.connect(lambda: self._switch_view("payroll"))
        employees_menu.addAction(payroll_action)

        customers_menu = menubar.addMenu("&Customers")
        cust_action = QAction("Customers List", self)
        cust_action.triggered.connect(lambda: self._switch_view("customers"))
        customers_menu.addAction(cust_action)

        vendors_menu = menubar.addMenu("&Vendors")
        vend_action = QAction("Vendors List", self)
        vend_action.triggered.connect(lambda: self._switch_view("vendors"))
        vendors_menu.addAction(vend_action)

        jobs_menu = menubar.addMenu("&Jobs")
        jobs_action = QAction("Jobs / Projects", self)
        jobs_action.triggered.connect(lambda: self._switch_view("jobs"))
        jobs_menu.addAction(jobs_action)

        reports_menu = menubar.addMenu("&Reports")
        reports_action = QAction("Reports Center", self)
        reports_action.triggered.connect(lambda: self._switch_view("reports"))
        reports_menu.addAction(reports_action)

        # Far right menus
        banking_menu = menubar.addMenu("&Banking")
        help_menu = menubar.addMenu("&Help")

    def _switch_view(self, key: str):
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == key)
        index = list(self.views.keys()).index(key)
        self.content_stack.setCurrentIndex(index)

    def _create_dashboard_view(self):
        """Dashboard using QMdiArea for resizable + movable panels (Phase D - Option C using A)."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QLabel(f"Dashboard — {self.company_data.get('name')}")
        header.setStyleSheet("font-size: 22px; font-weight: bold; color: #1a3c6e;")
        layout.addWidget(header)

        # QMdiArea - resizable and movable panels (larger, 3 across x 2 rows)
        self.dashboard_mdi = QMdiArea()
        self.dashboard_mdi.setBackground(QBrush(QColor("#f4f6f9")))
        layout.addWidget(self.dashboard_mdi, stretch=1)

        panels = [
            ("Company Overview", self._create_simple_mdi_panel("Company Overview", self._get_company_overview_text())),
            ("Active Jobs", self._create_simple_mdi_panel("Active Jobs", "No active jobs yet.")),
            ("Cash Position", self._create_simple_mdi_panel("Cash Position", "No bank accounts set up.")),
            ("Payroll Summary", self._create_simple_mdi_panel("Payroll Summary", "No employees or payroll runs yet.")),
            ("Customers", self._create_simple_mdi_panel("Customers", "No customers yet.")),
            ("Vendors", self._create_simple_mdi_panel("Vendors", "No vendors yet.")),
        ]

        # Larger panels - fill more of the screen (closer to Company Home feel)
        start_x, start_y = 20, 20
        panel_width, panel_height = 520, 280   # Much larger
        gap = 15

        for i, (title, content) in enumerate(panels):
            col = i % 3
            row = i // 3
            x = start_x + col * (panel_width + gap)
            y = start_y + row * (panel_height + gap)

            sub = QMdiSubWindow()
            sub.setWidget(content)
            sub.setWindowTitle(title)
            sub.resize(panel_width, panel_height)
            sub.move(x, y)
            self.dashboard_mdi.addSubWindow(sub)
            sub.show()

        return container

    def _create_simple_mdi_panel(self, title, content_text):
        box = QFrame()
        box.setFrameShape(QFrame.Shape.StyledPanel)
        box.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)

        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14px; color: #1a3c6e;")
        layout.addWidget(title_label)

        content = QLabel(content_text)
        content.setWordWrap(True)
        content.setStyleSheet("font-size: 13px; color: #495057;")
        layout.addWidget(content)

        return box

    def _get_company_overview_text(self):
        return (
            f"<b>{self.company_data.get('name', 'N/A')}</b><br>"
            f"Legal: {self.company_data.get('legal_name', 'N/A')}<br>"
            f"Industry: {self.company_data.get('industry_type', 'N/A')}<br>"
            f"EIN: {self.company_data.get('ein') or 'Not set'}<br>"
            f"{self.company_data.get('city', '')}, {self.company_data.get('state', '')} {self.company_data.get('zip', '')}"
        )

    def _create_at_a_glance_box(self, box_data: dict) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 16px;
            }
            QFrame:hover {
                border: 1px solid #1a3c6e;
            }
        """)
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)

        title_label = QLabel(box_data["title"])
        title_label.setStyleSheet("font-size: 15px; font-weight: 600; color: #1a3c6e;")
        layout.addWidget(title_label)

        content = box_data.get("content", "")
        if box_data.get("is_html"):
            content_label = QLabel(content)
            content_label.setTextFormat(Qt.TextFormat.RichText)
        else:
            content_label = QLabel(content)
        content_label.setStyleSheet("font-size: 13px; color: #495057;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        action_text = box_data.get("action")
        if action_text:
            action_btn = QPushButton(action_text)
            action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            action_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #0d6efd;
                    border: none;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 500;
                    padding: 4px 0;
                }
                QPushButton:hover {
                    color: #0a58ca;
                    text-decoration: underline;
                }
            """)
            action_key = box_data.get("action_key", "")
            action_btn.clicked.connect(lambda checked, k=action_key, t=action_text: self._on_dashboard_action(k, t))
            layout.addWidget(action_btn)

        layout.addStretch()
        return frame

    def _on_dashboard_action(self, key: str, title: str):
        QMessageBox.information(
            self,
            title,
            f"'{title}' will open the corresponding workflow.\n\n"
            f"This will be fully implemented as we build out each section."
        )

    def _on_save(self):
        """Save the current company file (already on disk as SQLite)."""
        # Since the database is already written to disk in real time,
        # we just confirm the save and optionally create a timestamped backup.
        try:
            # Simple confirmation for now
            QMessageBox.information(
                self,
                "Saved",
                f"Company file saved successfully.\n\n"
                f"Location:\n{self.company_path}"
            )
            self.statusBar().showMessage(f"Saved: {self.company_path}", 5000)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save company:\n{str(e)}")

    def _on_save_as(self):
        """Save a copy of the current company file to a new location."""
        try:
            current_name = os.path.basename(self.company_path)
            new_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Company As",
                current_name,
                "Vantage Core Company Files (*.vtg);;All Files (*)"
            )

            if not new_path:
                return

            if not new_path.lower().endswith(".vtg"):
                new_path += ".vtg"

            # Copy the SQLite file
            import shutil
            shutil.copy2(self.company_path, new_path)

            # Update current path
            self.company_path = new_path
            self.setWindowTitle(f"Vantage Core — {self.company_data.get('name', 'Company')}")
            self.statusBar().showMessage(f"Saved as: {new_path}", 5000)

            QMessageBox.information(
                self,
                "Saved As",
                f"Company file saved successfully to:\n\n{new_path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Save As Error", f"Could not save company as new file:\n{str(e)}")

    def _create_section_view(self, title: str, description: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        header = QLabel(title)
        header.setStyleSheet("font-size: 26px; font-weight: bold; color: #1a3c6e;")
        layout.addWidget(header)

        desc = QLabel(description)
        desc.setStyleSheet("font-size: 14px; color: #6c757d;")
        layout.addWidget(desc)

        workflow_frame = QFrame()
        workflow_frame.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #dee2e6;
                border-radius: 10px;
            }
        """)
        wf_layout = QVBoxLayout(workflow_frame)
        wf_layout.setContentsMargins(20, 20, 20, 20)
        wf_layout.setSpacing(12)

        wf_title = QLabel("Logical Workflows")
        wf_title.setStyleSheet("font-size: 16px; font-weight: 600; color: #1a3c6e;")
        wf_layout.addWidget(wf_title)

        for i in range(1, 5):
            btn = QPushButton(f"Workflow Step {i} — (to be defined)")
            btn.setMinimumHeight(48)
            btn.setStyleSheet("""
                QPushButton {
                    background: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 6px;
                    text-align: left;
                    padding-left: 16px;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background: #e9ecef;
                    border-color: #1a3c6e;
                }
            """)
            wf_layout.addWidget(btn)

        layout.addWidget(workflow_frame)
        layout.addStretch()
        return widget


# ============================================================
# LAUNCH WINDOW (Jump Point)
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Vantage Core — Contractors Edition")
        self.setMinimumSize(900, 600)

        # Center launch screen on primary monitor
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 1100, 700
        self.setGeometry(
            (screen.width() - w) // 2,
            (screen.height() - h) // 2,
            w, h
        )

        icon_path = "vantage_core_icon.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)

        # Tight header block
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)

        welcome = QLabel("Welcome to")
        welcome.setStyleSheet("font-size: 18px; color: #6c757d;")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Vantage Core")
        title.setStyleSheet("font-size: 36px; font-weight: bold; color: #1a3c6e;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        tagline = QLabel("Financial Management System")
        tagline.setStyleSheet("font-size: 22px; color: #1a3c6e;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_layout.addWidget(welcome)
        header_layout.addWidget(title)
        header_layout.addWidget(tagline)

        subtitle = QLabel("Single-User Desktop")
        subtitle.setStyleSheet("font-size: 16px; color: #6c757d;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(header_widget)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(20)

        btn_new = self._make_action_button("New Company", "#1a3c6e")
        btn_open = self._make_action_button("Open Company", "#2c5aa0")
        btn_import = self._make_action_button("Import from QuickBooks", "#0d6efd")

        btn_new.clicked.connect(self._launch_new_company)
        btn_open.clicked.connect(self._on_open)
        btn_import.clicked.connect(self._on_import)

        btn_layout.addWidget(btn_new)
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_import)

        layout.addLayout(btn_layout)

        # Second row – Search and Restore (same size & spacing as top row, centered)
        btn_layout2 = QHBoxLayout()
        btn_layout2.setSpacing(20)
        btn_layout2.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_search = self._make_action_button("Search for Company File", "#6c757d")
        btn_restore = self._make_action_button("Restore a Company Backup", "#6c757d")

        # Match the exact dimensions of the three main buttons
        btn_search.setMinimumHeight(60)
        btn_search.setMinimumWidth(220)
        btn_restore.setMinimumHeight(60)
        btn_restore.setMinimumWidth(220)

        btn_search.clicked.connect(self._search_for_company_file)
        btn_restore.clicked.connect(self._restore_company_backup)

        btn_layout2.addWidget(btn_search)
        btn_layout2.addWidget(btn_restore)

        layout.addLayout(btn_layout2)

        # Recent Companies quick access panel
        self.recent_group = QGroupBox("Recent Companies")
        self.recent_group.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: 600;
                color: #1a3c6e;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                margin-top: 12px;
                margin-bottom: 12px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
            }
        """)
        recent_layout = QVBoxLayout(self.recent_group)
        recent_layout.setContentsMargins(2, 4, 2, 4)
        recent_layout.setSpacing(0)

        self.recent_table = QTableWidget()
        self.recent_table.setColumnCount(3)
        self.recent_table.setHorizontalHeaderLabels(["Company Name", "Last Used", "Size"])

        # Header alignment
        self.recent_table.horizontalHeaderItem(0).setTextAlignment(Qt.AlignmentFlag.AlignLeft)
        self.recent_table.horizontalHeaderItem(2).setTextAlignment(Qt.AlignmentFlag.AlignRight)
        # Last Used (column 1) stays centered by default

        # Fixed column widths to prevent scrollbar and truncation
        # Proactive: Make all columns user-adjustable by default
        self.recent_table.horizontalHeader().setSectionsMovable(True)
        self.recent_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.recent_table.horizontalHeader().setStretchLastSection(True)

        self.recent_table.setColumnWidth(0, 480)
        self.recent_table.setColumnWidth(1, 160)
        self.recent_table.setColumnWidth(2, 120)

        self.recent_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.recent_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #dee2e6;
                border-radius: 6px;
                background: #f8f9fa;
                font-size: 13px;
                gridline-color: #e9ecef;
            }
            QHeaderView::section {
                background-color: #e9ecef;
                padding: 6px;
                border: none;
                font-weight: bold;
                color: #495057;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QTableWidget::item:hover {
                background: #e9ecef;
            }
            QTableWidget::item:selected {
                background: #1a3c6e;
                color: white;
            }
        """)
        self.recent_table.setMaximumHeight(160)
        self.recent_table.setMinimumWidth(750)
        self.recent_table.setMaximumWidth(800)  # Exact fit for columns without scrollbar
        self.recent_table.verticalHeader().setVisible(False)
        self.recent_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.recent_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.recent_table.itemDoubleClicked.connect(self._open_recent_company)
        recent_layout.addWidget(self.recent_table)

        # Center the Recent Companies panel
        center_layout = QHBoxLayout()
        center_layout.addStretch(1)
        center_layout.addWidget(self.recent_group)
        center_layout.addStretch(1)
        layout.addLayout(center_layout)
        layout.addStretch()

        footer = QLabel("Create a new company or import your existing QuickBooks file to get started.")
        footer.setStyleSheet("color: #adb5bd; font-size: 13px;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

        self.statusBar().showMessage("Ready")

        # Load recent companies
        self.recent_companies = self._load_recent_companies()
        self._refresh_recent_list()

    def _make_action_button(self, text: str, color: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setMinimumHeight(60)
        btn.setMinimumWidth(220)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 16px;
                font-weight: 600;
                padding: 12px 24px;
            }}
            QPushButton:hover {{
                background-color: #15325a;
            }}
        """)
        return btn

    def _launch_new_company(self):
        wizard = NewCompanyWizard(self)
        wizard.exec()

    def open_company_window(self, path: str, data: dict):
        """Called after successful creation or open."""
        self.company_window = CompanyMainWindow(path, data, self)
        self.company_window.show()
        self.hide()
        self.add_to_recent(path, data)

    def _on_open(self):
        """Open an existing .vtg company file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Company File",
            "",  # Start in last used / home directory
            "Vantage Core Company Files (*.vtg);;All Files (*)"
        )

        if not file_path:
            return

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found", f"The selected file does not exist:\n{file_path}")
            return

        # Load company data from the database
        try:
            company_data = self._load_company_data(file_path)
            if company_data:
                self.open_company_window(file_path, company_data)
            else:
                QMessageBox.warning(
                    self,
                    "Invalid Company File",
                    "Could not read company information from this file.\n"
                    "It may be corrupted or not a valid Vantage Core company file."
                )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Opening Company",
                f"An error occurred while opening the company file:\n\n{str(e)}"
            )

    def _load_company_data(self, path: str) -> dict | None:
        """Read the companies table from the .vtg SQLite file."""
        try:
            conn = get_connection(path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT name, legal_name, company_type, ein,
                       address, city, state, zip, phone, email,
                       fiscal_year_start_month, accounting_method
                FROM companies
                LIMIT 1
            """)
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            # Map company_type back to display name
            type_map = {
                "construction": "Construction / Contracting",
                "real_estate": "Real Estate / Property Management",
                "rv_resort": "RV Resort / Campground / Hospitality",
                "retail": "Retail",
                "manufacturing": "Manufacturing",
                "wholesale": "Wholesale / Distribution",
                "professional_services": "Professional Services",
                "healthcare": "Healthcare",
                "nonprofit": "Non-Profit / Education",
                "agriculture": "Agriculture",
                "transportation": "Transportation / Logistics",
                "general": "General Business / Other",
            }
            industry = type_map.get(row["company_type"], row["company_type"].title() if row["company_type"] else "Other")

            return {
                "name": row["name"] or "Unnamed Company",
                "legal_name": row["legal_name"] or row["name"] or "",
                "industry_type": industry,
                "ein": row["ein"] or "",
                "address": row["address"] or "",
                "city": row["city"] or "",
                "state": row["state"] or "",
                "zip": row["zip"] or "",
                "phone": row["phone"] or "",
                "email": row["email"] or "",
                "contact_person": "",  # Not stored yet in schema
                "fiscal_year_start_month": row["fiscal_year_start_month"] or 1,
                "accounting_method": row["accounting_method"] or "Accrual",
            }
        except Exception as e:
            print(f"Error loading company data: {e}")
            return None

    def _on_import(self):
        QMessageBox.information(
            self,
            "Import from QuickBooks",
            "The full QuickBooks Import Wizard will be built after the company interface is solid.\n\n"
            "It will support large company files with progress, logging, and resumable imports."
        )

    def _search_for_company_file(self):
        """Open a file dialog to find and open an existing .vtg company file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Search for Company File",
            "",
            "Vantage Core Company Files (*.vtg);;All Files (*)"
        )
        if file_path and os.path.exists(file_path):
            try:
                company_data = self._load_company_data(file_path)
                if company_data:
                    self.open_company_window(file_path, company_data)
                else:
                    QMessageBox.warning(self, "Invalid File", "Could not read company data from this file.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to open company file:\n{str(e)}")

    def _restore_company_backup(self):
        """Placeholder for restoring a company backup (basic file copy for now)."""
        backup_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Company Backup File",
            "",
            "Vantage Core Backup Files (*.vtg *.bak);;All Files (*)"
        )
        if not backup_path:
            return

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Restored Company As",
            "Restored_Company.vtg",
            "Vantage Core Company Files (*.vtg)"
        )
        if not save_path:
            return

        try:
            import shutil
            shutil.copy2(backup_path, save_path)
            QMessageBox.information(
                self,
                "Restore Successful",
                f"Backup restored to:\n{save_path}\n\nYou can now open it from the Recent Companies list or Search."
            )
            # Optionally auto-open the restored file
            company_data = self._load_company_data(save_path)
            if company_data:
                self.open_company_window(save_path, company_data)
        except Exception as e:
            QMessageBox.critical(self, "Restore Failed", f"Could not restore backup:\n{str(e)}")

    # ============================================================
    # Recent Companies handling
    # ============================================================

    def _get_recent_file(self):
        return os.path.join(os.path.dirname(__file__), "recent_companies.json")

    def _load_recent_companies(self):
        recent_file = self._get_recent_file()
        if os.path.exists(recent_file):
            try:
                with open(recent_file, "r") as f:
                    data = json.load(f)
                    # Filter out files that no longer exist
                    return [entry for entry in data if os.path.exists(entry.get("path", ""))]
            except Exception:
                pass
        return []

    def _save_recent_companies(self):
        recent_file = self._get_recent_file()
        try:
            with open(recent_file, "w") as f:
                json.dump(self.recent_companies, f, indent=2)
        except Exception:
            pass

    def _human_readable_size(self, size_bytes):
        """Convert bytes to human readable format."""
        if size_bytes == 0:
            return "0 B"
        size_name = ("B", "KB", "MB", "GB")
        i = 0
        while size_bytes >= 1024 and i < len(size_name) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_name[i]}"

    def add_to_recent(self, path: str, data: dict):
        entry = {
            "name": data.get("name", "Unnamed Company"),
            "path": path
        }
        # Remove duplicates
        self.recent_companies = [e for e in self.recent_companies if e["path"] != path]
        self.recent_companies.insert(0, entry)
        # Keep only last 8
        self.recent_companies = self.recent_companies[:8]
        self._save_recent_companies()
        self._refresh_recent_list()

    def _refresh_recent_list(self):
        self.recent_table.setRowCount(0)

        for row, entry in enumerate(self.recent_companies):
            try:
                stat = os.stat(entry["path"])
                last_used = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d")
                file_size = self._human_readable_size(stat.st_size)
            except Exception:
                last_used = "Unknown"
                file_size = "?"

            # Company Name (left aligned)
            name_item = QTableWidgetItem(entry["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, entry)
            name_item.setToolTip(entry["path"])

            # Last Used (center aligned)
            last_item = QTableWidgetItem(last_used)
            last_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            last_item.setData(Qt.ItemDataRole.UserRole, entry)

            # Size (right aligned)
            size_item = QTableWidgetItem(file_size)
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            size_item.setData(Qt.ItemDataRole.UserRole, entry)

            self.recent_table.insertRow(row)
            self.recent_table.setItem(row, 0, name_item)
            self.recent_table.setItem(row, 1, last_item)
            self.recent_table.setItem(row, 2, size_item)

        # Fixed column widths for consistent fit
        self.recent_table.setColumnWidth(0, 420)  # Company Name
        self.recent_table.setColumnWidth(1, 150)  # Last Used
        self.recent_table.setColumnWidth(2, 120)  # Size

    def _open_recent_company(self, item):
        row = item.row()
        entry = self.recent_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        path = entry.get("path")

        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"The company file no longer exists:\n{path}")
            self.recent_companies = [e for e in self.recent_companies if e["path"] != path]
            self._save_recent_companies()
            self._refresh_recent_list()
            return

        try:
            company_data = self._load_company_data(path)
            if company_data:
                self.open_company_window(path, company_data)
            else:
                QMessageBox.warning(self, "Invalid File", "Could not read company data from this file.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open recent company:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(True)  # Ensure app exits when last window closes

    window = MainWindow()
    window.show()
    ret = app.exec()
    sys.exit(ret)

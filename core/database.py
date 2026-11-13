#!/usr/bin/env python3
"""
Vantage Core
core/database.py

Handles creation and management of company database files (.vtg).
Includes enhanced schema for:
- Unified company types (construction, real_estate, rv_resort)
- AIA/CSI cost code library support
- CIP (Construction in Progress) tracking
- Depreciation / Fixed Assets
- Time tracking foundation
- Robust import batch tracking
- Extensive industry-specific Chart of Accounts
"""

import sqlite3
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_VERSION = "0.3.0"


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a connection to the SQLite database."""
    conn = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_new_company_file(
    db_path: str,
    company_name: str,
    company_type: str = "construction",
    legal_name: Optional[str] = None,
    ein: Optional[str] = None,
    fiscal_year_start_month: int = 1,
    accounting_method: str = "Accrual"
) -> bool:
    """Create a brand new company file with full schema and extensive Chart of Accounts."""
    if os.path.exists(db_path):
        raise FileExistsError(f"Company file already exists: {db_path}")

    conn = get_connection(db_path)
    try:
        create_schema(conn)
        seed_initial_data(conn, company_name, company_type, legal_name, ein,
                          fiscal_year_start_month, accounting_method)
        conn.commit()
        print(f"✓ Successfully created new company file: {db_path}")
        print(f"  Company: {company_name} | Type: {company_type}")
        return True
    except Exception as e:
        conn.rollback()
        print(f"✗ Error creating company file: {e}")
        raise
    finally:
        conn.close()


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all tables for Vantage Core."""
    cursor = conn.cursor()

    # companies
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            company_type TEXT NOT NULL DEFAULT 'construction'
                CHECK(company_type IN ('construction', 'real_estate', 'rv_resort', 'general')),
            legal_name TEXT,
            address TEXT, city TEXT, state TEXT, zip TEXT,
            phone TEXT, email TEXT, ein TEXT,
            fiscal_year_start_month INTEGER DEFAULT 1,
            accounting_method TEXT DEFAULT 'Accrual',
            qb_company_file_path TEXT,
            db_version TEXT DEFAULT '0.3.0',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # chart_of_accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chart_of_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            account_number TEXT,
            name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            sub_type TEXT,
            parent_id INTEGER,
            tax_line_mapping TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_system BOOLEAN DEFAULT 0,
            opening_balance REAL DEFAULT 0,
            current_balance REAL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (parent_id) REFERENCES chart_of_accounts(id)
        )
    """)

    # customers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL, company_name TEXT,
            address TEXT, phone TEXT, email TEXT,
            qb_list_id TEXT, credit_limit REAL,
            payment_terms TEXT, tax_id TEXT, notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # vendors
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL, company_name TEXT,
            address TEXT, phone TEXT, email TEXT,
            qb_list_id TEXT, payment_terms TEXT, tax_id TEXT,
            is_1099_eligible BOOLEAN DEFAULT 0, notes TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # employees
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            ssn_last4 TEXT, address TEXT, phone TEXT, email TEXT,
            hire_date DATE, pay_type TEXT, pay_rate REAL,
            qb_list_id TEXT, is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # jobs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            customer_id INTEGER,
            job_number TEXT UNIQUE, job_name TEXT NOT NULL,
            description TEXT, status TEXT DEFAULT 'Open',
            contract_amount REAL DEFAULT 0,
            start_date DATE, estimated_completion_date DATE,
            actual_completion_date DATE,
            percent_complete REAL DEFAULT 0,
            percent_complete_method TEXT DEFAULT 'Cost',
            billing_type TEXT DEFAULT 'Progress',
            retainage_percent REAL DEFAULT 10.0,
            cip_account_id INTEGER,
            costs_to_date REAL DEFAULT 0,
            billings_to_date REAL DEFAULT 0,
            retainage_held REAL DEFAULT 0,
            over_under_billing REAL DEFAULT 0,
            aia_billing_number TEXT,
            depreciation_applicable BOOLEAN DEFAULT 0,
            notes TEXT, qb_job_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (customer_id) REFERENCES customers(id)
        )
    """)

    # cost_codes
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            code TEXT NOT NULL, description TEXT,
            division TEXT, category TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            UNIQUE(company_id, code)
        )
    """)

    # job_cost_details
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS job_cost_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            job_id INTEGER NOT NULL,
            cost_code_id INTEGER,
            transaction_line_id INTEGER,
            cost_type TEXT, amount REAL NOT NULL,
            date DATE, vendor_id INTEGER, employee_id INTEGER,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (cost_code_id) REFERENCES cost_codes(id)
        )
    """)

    # fixed_assets
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fixed_assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            asset_name TEXT NOT NULL,
            asset_type TEXT,
            purchase_date DATE, cost_basis REAL,
            depreciation_method TEXT,
            useful_life_years REAL, salvage_value REAL DEFAULT 0,
            accumulated_depreciation REAL DEFAULT 0,
            current_book_value REAL,
            linked_job_id INTEGER,
            gl_asset_account_id INTEGER,
            gl_depreciation_expense_account_id INTEGER,
            notes TEXT, is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # time_entries
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            employee_id INTEGER NOT NULL,
            job_id INTEGER, cost_code_id INTEGER,
            date DATE NOT NULL, hours REAL NOT NULL,
            rate REAL, billable BOOLEAN DEFAULT 1,
            mobile_sync_id TEXT,
            posted_to_payroll BOOLEAN DEFAULT 0,
            posted_to_job_cost BOOLEAN DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (employee_id) REFERENCES employees(id),
            FOREIGN KEY (job_id) REFERENCES jobs(id)
        )
    """)

    # transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL,
            date DATE NOT NULL, ref_number TEXT, memo TEXT,
            total_amount REAL, is_posted BOOLEAN DEFAULT 1,
            import_batch_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # transaction_lines
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transaction_lines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id INTEGER NOT NULL,
            account_id INTEGER NOT NULL,
            job_id INTEGER, cost_code_id INTEGER,
            description TEXT,
            debit REAL DEFAULT 0, credit REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (transaction_id) REFERENCES transactions(id),
            FOREIGN KEY (account_id) REFERENCES chart_of_accounts(id)
        )
    """)

    # bank_accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            account_id INTEGER, bank_name TEXT,
            account_number_last4 TEXT, routing_number TEXT,
            current_balance REAL, last_reconciled_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # bank_transactions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bank_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_account_id INTEGER NOT NULL,
            date DATE, description TEXT, amount REAL,
            transaction_type TEXT, fit_id TEXT,
            is_reconciled BOOLEAN DEFAULT 0,
            matched_transaction_line_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bank_account_id) REFERENCES bank_accounts(id)
        )
    """)

    # import_batches
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            source_type TEXT, source_file TEXT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'In Progress',
            records_processed INTEGER DEFAULT 0,
            records_failed INTEGER DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # import_log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS import_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_batch_id INTEGER NOT NULL,
            entity_type TEXT, entity_id INTEGER,
            action TEXT, message TEXT,
            severity TEXT DEFAULT 'INFO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (import_batch_id) REFERENCES import_batches(id)
        )
    """)

    # payroll_runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payroll_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            pay_period_start DATE, pay_period_end DATE,
            pay_date DATE, status TEXT DEFAULT 'Draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # tax_filings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tax_filings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            form_type TEXT, period TEXT,
            filing_date DATE, status TEXT DEFAULT 'Draft',
            pdf_path TEXT, efile_confirmation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # audit_log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER,
            user TEXT DEFAULT 'SingleUser',
            action TEXT NOT NULL,
            entity_type TEXT, entity_id INTEGER,
            old_value TEXT, new_value TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # Indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cost_codes_company ON cost_codes(company_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_transactions_company_date ON transactions(company_id, date)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_coa_company ON chart_of_accounts(company_id)")

    print("✓ Database schema created successfully (v0.3)")


def seed_initial_data(conn, company_name, company_type, legal_name, ein,
                      fiscal_year_start_month, accounting_method):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO companies (name, company_type, legal_name, ein,
                               fiscal_year_start_month, accounting_method)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (company_name, company_type, legal_name, ein,
          fiscal_year_start_month, accounting_method))
    company_id = cursor.lastrowid

    # Create extensive industry-specific Chart of Accounts
    seed_chart_of_accounts(cursor, company_id, company_type)

    if company_type == "construction":
        seed_aia_cost_codes(cursor, company_id)

    # Optional sample job for construction
    if company_type == "construction":
        cursor.execute("""
            INSERT INTO jobs (company_id, job_name, job_number, status,
                              contract_amount, start_date)
            VALUES (?, 'Sample Job - Ready for Import', 'JOB-0001', 'Open',
                    0, date('now'))
        """, (company_id,))

    print(f"✓ Initial data seeded for company_id={company_id}")


def seed_chart_of_accounts(cursor, company_id: int, company_type: str):
    """
    Create an extensive Chart of Accounts with proper hierarchical structure
    (parent accounts + sub-accounts) based on industry type.
    """
    # We will insert parents first, then children with parent_id
    parent_map = {}  # name -> id

    def insert_account(number, name, account_type, tax_line, parent_name=None):
        parent_id = parent_map.get(parent_name) if parent_name else None
        cursor.execute("""
            INSERT INTO chart_of_accounts 
            (company_id, account_number, name, account_type, tax_line_mapping, parent_id, is_active, is_system)
            VALUES (?, ?, ?, ?, ?, ?, 1, 0)
        """, (company_id, number, name, account_type, tax_line, parent_id))
        return cursor.lastrowid

    # ========== COMMON ACCOUNTS WITH HIERARCHY ==========

    # Assets (mostly flat for now)
    insert_account("1000", "Cash - Operating", "Asset", "Bank")
    insert_account("1010", "Cash - Payroll", "Asset", "Bank")
    insert_account("1020", "Petty Cash", "Asset", "Bank")
    insert_account("1100", "Accounts Receivable", "Asset", "AccountsReceivable")
    insert_account("1110", "Retainage Receivable", "Asset", "Retainage")
    insert_account("1200", "Inventory", "Asset", "Inventory")
    insert_account("1300", "Prepaid Expenses", "Asset", "OtherCurrentAsset")
    insert_account("1400", "Employee Advances", "Asset", "OtherCurrentAsset")

    # Fixed Assets parent + children
    fa_parent = insert_account("1500", "Fixed Assets", "Asset", "FixedAsset")
    parent_map["Fixed Assets"] = fa_parent
    insert_account("1501", "Fixed Assets - Vehicles", "Asset", "FixedAsset", "Fixed Assets")
    insert_account("1502", "Fixed Assets - Equipment", "Asset", "FixedAsset", "Fixed Assets")
    insert_account("1503", "Fixed Assets - Office Equipment", "Asset", "FixedAsset", "Fixed Assets")
    insert_account("1504", "Fixed Assets - Buildings", "Asset", "FixedAsset", "Fixed Assets")
    insert_account("1505", "Fixed Assets - Land", "Asset", "FixedAsset", "Fixed Assets")

    # Accumulated Depreciation parent
    dep_parent = insert_account("1600", "Accumulated Depreciation", "Asset", "ContraAsset")
    parent_map["Accumulated Depreciation"] = dep_parent
    insert_account("1601", "Accum. Dep. - Vehicles", "Asset", "ContraAsset", "Accumulated Depreciation")
    insert_account("1602", "Accum. Dep. - Equipment", "Asset", "ContraAsset", "Accumulated Depreciation")

    insert_account("1700", "Deposits", "Asset", "OtherAsset")
    insert_account("1800", "Other Assets", "Asset", "OtherAsset")

    # Liabilities
    insert_account("2000", "Accounts Payable", "Liability", "AccountsPayable")
    insert_account("2010", "Retainage Payable", "Liability", "Retainage")
    insert_account("2100", "Credit Cards Payable", "Liability", "CreditCard")

    # Payroll Liabilities parent
    pl_parent = insert_account("2200", "Payroll Liabilities", "Liability", "OtherCurrentLiability")
    parent_map["Payroll Liabilities"] = pl_parent
    insert_account("2201", "Federal Income Tax Withheld", "Liability", "OtherCurrentLiability", "Payroll Liabilities")
    insert_account("2202", "Social Security Tax Payable", "Liability", "OtherCurrentLiability", "Payroll Liabilities")
    insert_account("2203", "Medicare Tax Payable", "Liability", "OtherCurrentLiability", "Payroll Liabilities")
    insert_account("2204", "State Income Tax Withheld", "Liability", "OtherCurrentLiability", "Payroll Liabilities")

    insert_account("2300", "Sales Tax Payable", "Liability", "OtherCurrentLiability")
    insert_account("2400", "Customer Deposits", "Liability", "OtherCurrentLiability")
    insert_account("2500", "Short-term Loans Payable", "Liability", "OtherCurrentLiability")
    insert_account("2600", "Current Portion of Long-term Debt", "Liability", "OtherCurrentLiability")
    insert_account("2700", "Long-term Loans Payable", "Liability", "LongTermLiability")
    insert_account("2800", "Notes Payable", "Liability", "LongTermLiability")

    # Equity
    insert_account("3000", "Owner's Capital / Equity", "Equity", "Equity")
    insert_account("3100", "Owner's Draws", "Equity", "Equity")
    insert_account("3200", "Retained Earnings", "Equity", "Equity")

    # Income
    insert_account("4000", "Sales / Service Income", "Income", "Income")
    insert_account("4100", "Other Income", "Income", "OtherIncome")

    # COGS / Direct Costs
    insert_account("5000", "Cost of Goods Sold", "CostOfGoodsSold", "COGS")
    insert_account("5100", "Direct Labor", "CostOfGoodsSold", "COGS")
    insert_account("5200", "Direct Materials", "CostOfGoodsSold", "COGS")
    insert_account("5300", "Subcontractor Costs", "CostOfGoodsSold", "COGS")

    # Expenses with hierarchy for Insurance and Payroll
    insert_account("6000", "Advertising & Marketing", "Expense", "Expense")
    insert_account("6100", "Automobile Expense", "Expense", "Expense")
    insert_account("6200", "Bank Charges & Fees", "Expense", "Expense")
    insert_account("6300", "Depreciation Expense", "Expense", "Depreciation")

    # Insurance parent + children (example requested by user)
    ins_parent = insert_account("6400", "Insurance Expense", "Expense", "Expense")
    parent_map["Insurance Expense"] = ins_parent
    insert_account("6401", "Insurance - Liability", "Expense", "Expense", "Insurance Expense")
    insert_account("6402", "Insurance - Workers Comp", "Expense", "Expense", "Insurance Expense")
    insert_account("6403", "Insurance - Vehicle", "Expense", "Expense", "Insurance Expense")
    insert_account("6404", "Insurance - Health", "Expense", "Expense", "Insurance Expense")
    insert_account("6405", "Insurance - Property", "Expense", "Expense", "Insurance Expense")

    insert_account("6500", "Interest Expense", "Expense", "Expense")
    insert_account("6600", "Legal & Professional Fees", "Expense", "Expense")
    insert_account("6700", "Meals & Entertainment", "Expense", "Expense")
    insert_account("6800", "Office Expense", "Expense", "Expense")

    # Payroll Expenses parent
    pay_parent = insert_account("6900", "Payroll Expenses", "Expense", "Payroll")
    parent_map["Payroll Expenses"] = pay_parent
    insert_account("6901", "Salaries & Wages", "Expense", "Payroll", "Payroll Expenses")
    insert_account("6902", "Payroll Taxes", "Expense", "Payroll", "Payroll Expenses")
    insert_account("6903", "Employee Benefits", "Expense", "Payroll", "Payroll Expenses")

    insert_account("7000", "Rent or Lease", "Expense", "Expense")
    insert_account("7100", "Repairs & Maintenance", "Expense", "Expense")
    insert_account("7200", "Supplies", "Expense", "Expense")
    insert_account("7300", "Taxes & Licenses", "Expense", "Expense")
    insert_account("7400", "Telephone & Internet", "Expense", "Expense")
    insert_account("7500", "Travel Expense", "Expense", "Expense")

    # Utilities parent
    util_parent = insert_account("7600", "Utilities", "Expense", "Expense")
    parent_map["Utilities"] = util_parent
    insert_account("7601", "Utilities - Electric", "Expense", "Expense", "Utilities")
    insert_account("7602", "Utilities - Gas", "Expense", "Expense", "Utilities")
    insert_account("7603", "Utilities - Water", "Expense", "Expense", "Utilities")

    insert_account("7700", "Miscellaneous Expense", "Expense", "Expense")

    print(f"✓ Seeded hierarchical Chart of Accounts for industry type: {company_type}")


def seed_aia_cost_codes(cursor, company_id):
    codes = [
        ("01-0000", "General Requirements", "01 - General Requirements", "Other"),
        ("02-0000", "Existing Conditions", "02 - Existing Conditions", "Other"),
        ("03-0000", "Concrete", "03 - Concrete", "Material"),
        ("03-1000", "Concrete Forming and Accessories", "03 - Concrete", "Material"),
        ("03-2000", "Concrete Reinforcing", "03 - Concrete", "Material"),
        ("03-3000", "Cast-in-Place Concrete", "03 - Concrete", "Material"),
        ("04-0000", "Masonry", "04 - Masonry", "Material"),
        ("05-0000", "Metals", "05 - Metals", "Material"),
        ("06-0000", "Wood, Plastics, and Composites", "06 - Wood, Plastics, and Composites", "Material"),
        ("07-0000", "Thermal and Moisture Protection", "07 - Thermal and Moisture Protection", "Material"),
        ("08-0000", "Openings", "08 - Openings", "Material"),
        ("09-0000", "Finishes", "09 - Finishes", "Material"),
        ("10-0000", "Specialties", "10 - Specialties", "Other"),
        ("11-0000", "Equipment", "11 - Equipment", "Equipment"),
        ("12-0000", "Furnishings", "12 - Furnishings", "Other"),
        ("13-0000", "Special Construction", "13 - Special Construction", "Other"),
        ("14-0000", "Conveying Equipment", "14 - Conveying Equipment", "Equipment"),
        ("21-0000", "Fire Suppression", "21 - Fire Suppression", "Subcontract"),
        ("22-0000", "Plumbing", "22 - Plumbing", "Subcontract"),
        ("23-0000", "HVAC", "23 - HVAC", "Subcontract"),
        ("26-0000", "Electrical", "26 - Electrical", "Subcontract"),
        ("31-0000", "Earthwork", "31 - Earthwork", "Labor"),
        ("32-0000", "Exterior Improvements", "32 - Exterior Improvements", "Labor"),
        ("33-0000", "Utilities", "33 - Utilities", "Subcontract"),
    ]
    for code, desc, division, cat in codes:
        cursor.execute("""
            INSERT INTO cost_codes (company_id, code, description, division, category)
            VALUES (?, ?, ?, ?, ?)
        """, (company_id, code, desc, division, cat))
    print(f"✓ Seeded {len(codes)} AIA/CSI cost codes")


if __name__ == "__main__":
    import tempfile

    temp_dir = tempfile.gettempdir()
    test_path = os.path.join(temp_dir, "test_vantage_core.vtg")

    if os.path.exists(test_path):
        os.remove(test_path)

    initialize_new_company_file(
        test_path,
        company_name="Glen Canyon Construction LLC",
        company_type="construction",
        legal_name="Glen Canyon Construction LLC",
        ein="XX-XXXXXXX",
        fiscal_year_start_month=1,
        accounting_method="Accrual"
    )
    print(f"\n✅ Test file created successfully at: {test_path}")

#!/usr/bin/env python3
"""
Construction Desktop Finance (CDF)
core/importer.py

QB Import Engine - Highest priority module.
Designed to reliably import large, long-standing QuickBooks company files
(Glen Canyon Construction LLC — since 1998).

Supported input formats (Phase 1):
- IIF (QuickBooks Interchange Format) — best for lists
- CSV / Excel exports from QB reports (Transaction Detail, Trial Balance, Job reports, etc.)

Features:
- Batch tracking + resumable imports
- Detailed logging (import_log table)
- Progress reporting
- Smart matching using qb_list_id where available
- Error recovery and partial success support
- Future: Direct COM automation if QB is still installed on the machine
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any
import logging

from .database import get_connection

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

class QBImportEngine:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = get_connection(db_path)
        self.current_batch_id: Optional[int] = None

    def start_new_import_batch(self, source_type: str, source_file: str) -> int:
        """Create a new import batch record and return its ID."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO import_batches (company_id, source_type, source_file, status)
            SELECT id, ?, ?, 'In Progress' FROM companies LIMIT 1
        """, (source_type, source_file))
        self.current_batch_id = cursor.lastrowid
        self.conn.commit()
        logger.info(f"Started import batch #{self.current_batch_id} from {source_file}")
        return self.current_batch_id

    def log_import_event(self, entity_type: str, entity_id: Optional[int],
                         action: str, message: str, severity: str = "INFO"):
        """Log an event to the import_log table."""
        if not self.current_batch_id:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO import_log (import_batch_id, entity_type, entity_id, action, message, severity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.current_batch_id, entity_type, entity_id, action, message, severity))
        self.conn.commit()

    def complete_batch(self, status: str = "Completed", notes: str = ""):
        """Mark the current batch as finished."""
        if not self.current_batch_id:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE import_batches
            SET status = ?, completed_at = CURRENT_TIMESTAMP, notes = ?
            WHERE id = ?
        """, (status, notes, self.current_batch_id))
        self.conn.commit()
        logger.info(f"Import batch #{self.current_batch_id} marked as {status}")

    # ============================================================
    # IIF IMPORT (Best for Lists: Chart of Accounts, Customers, Jobs, etc.)
    # ============================================================
    def import_iif_file(self, iif_path: str) -> Dict[str, int]:
        """
        Import a QuickBooks IIF file.
        Returns counts of imported records per entity type.
        """
        batch_id = self.start_new_import_batch("IIF", iif_path)
        counts = {"accounts": 0, "customers": 0, "vendors": 0, "jobs": 0, "employees": 0, "errors": 0}

        try:
            with open(iif_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            current_section = None
            headers = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('!'):
                    if line.startswith('!'):
                        parts = line[1:].split('\t')
                        current_section = parts[0] if parts else None
                        headers = parts[1:] if len(parts) > 1 else []
                    continue

                fields = line.split('\t')
                try:
                    if current_section == "ACCNT":
                        self._import_account_row(fields, headers)
                        counts["accounts"] += 1
                    elif current_section == "CUST":
                        self._import_customer_row(fields, headers)
                        counts["customers"] += 1
                    elif current_section == "VEND":
                        self._import_vendor_row(fields, headers)
                        counts["vendors"] += 1
                    elif current_section == "EMP":
                        self._import_employee_row(fields, headers)
                        counts["employees"] += 1
                    elif current_section == "JOB":
                        self._import_job_row(fields, headers)
                        counts["jobs"] += 1
                except Exception as e:
                    counts["errors"] += 1
                    self.log_import_event("IIF", None, "ERROR",
                                          f"Line {line_num}: {str(e)}", "ERROR")

            self.complete_batch("Completed", f"Imported {sum(counts.values())} records")
            return counts

        except Exception as e:
            self.complete_batch("Failed", str(e))
            logger.error(f"IIF import failed: {e}")
            raise

    def _import_account_row(self, fields: List[str], headers: List[str]):
        """Map IIF ACCNT row to chart_of_accounts."""
        data = dict(zip(headers, fields))
        cursor = self.conn.cursor()

        # Basic mapping - expand as needed for full fidelity
        name = data.get("NAME", "").strip()
        if not name:
            return

        account_type = data.get("ACCNTTYPE", "Expense")
        # Map QB account types to our types
        type_map = {
            "Bank": "Asset", "AR": "Asset", "Other Asset": "Asset",
            "AP": "Liability", "CreditCard": "Liability", "Other Liability": "Liability",
            "Equity": "Equity",
            "Income": "Income", "Other Income": "Income",
            "Expense": "Expense", "Other Expense": "Expense", "COGS": "CostOfGoodsSold"
        }
        our_type = type_map.get(account_type, "Expense")

        cursor.execute("""
            INSERT OR IGNORE INTO chart_of_accounts
            (company_id, account_number, name, account_type, sub_type, tax_line_mapping)
            SELECT id, ?, ?, ?, ?, ? FROM companies LIMIT 1
        """, (
            data.get("ACCNTNUM", ""),
            name,
            our_type,
            data.get("SUBTYPE", ""),
            data.get("TAXLINE", "")
        ))
        self.conn.commit()

    def _import_customer_row(self, fields: List[str], headers: List[str]):
        data = dict(zip(headers, fields))
        name = data.get("NAME", "").strip()
        if not name:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO customers (company_id, name, company_name, phone, email, qb_list_id)
            SELECT id, ?, ?, ?, ?, ? FROM companies LIMIT 1
        """, (name, data.get("COMPANYNAME", ""), data.get("PHONE", ""), data.get("EMAIL", ""), data.get("LISTID", "")))
        self.conn.commit()

    def _import_vendor_row(self, fields: List[str], headers: List[str]):
        data = dict(zip(headers, fields))
        name = data.get("NAME", "").strip()
        if not name:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO vendors (company_id, name, company_name, phone, email, qb_list_id, 1099_eligible)
            SELECT id, ?, ?, ?, ?, ?, ? FROM companies LIMIT 1
        """, (name, data.get("COMPANYNAME", ""), data.get("PHONE", ""), data.get("EMAIL", ""), data.get("LISTID", ""), 1 if data.get("1099") else 0))
        self.conn.commit()

    def _import_employee_row(self, fields: List[str], headers: List[str]):
        data = dict(zip(headers, fields))
        first = data.get("FIRSTNAME", "").strip()
        last = data.get("LASTNAME", "").strip()
        if not first and not last:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO employees (company_id, first_name, last_name, phone, email, qb_list_id)
            SELECT id, ?, ?, ?, ?, ? FROM companies LIMIT 1
        """, (first, last, data.get("PHONE", ""), data.get("EMAIL", ""), data.get("LISTID", "")))
        self.conn.commit()

    def _import_job_row(self, fields: List[str], headers: List[str]):
        data = dict(zip(headers, fields))
        job_name = data.get("NAME", "").strip()
        if not job_name:
            return
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO jobs (company_id, job_name, job_number, qb_job_id, status)
            SELECT id, ?, ?, ?, 'Open' FROM companies LIMIT 1
        """, (job_name, data.get("JOBNUM", ""), data.get("LISTID", "")))
        self.conn.commit()

    # ============================================================
    # CSV / Excel Report Import (for transactions, balances, etc.)
    # ============================================================
    def import_csv_transactions(self, csv_path: str, date_format: str = "%m/%d/%Y") -> int:
        """
        Import transactions from a CSV export (e.g. Transaction Detail by Account report from QB).
        This is the workhorse for bringing over historical data.
        """
        batch_id = self.start_new_import_batch("CSV", csv_path)
        imported = 0
        errors = 0

        try:
            with open(csv_path, newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        self._import_transaction_row(row)
                        imported += 1
                        if imported % 500 == 0:
                            logger.info(f"Processed {imported} transactions...")
                    except Exception as e:
                        errors += 1
                        self.log_import_event("Transaction", None, "ERROR", str(e), "ERROR")

            self.complete_batch("Completed", f"Imported {imported} transactions, {errors} errors")
            return imported

        except Exception as e:
            self.complete_batch("Failed", str(e))
            raise

    def _import_transaction_row(self, row: Dict[str, str]):
        """Map a row from QB Transaction Detail CSV to our transactions + lines."""
        # This is a simplified example. Real implementation needs robust column mapping,
        # handling of splits, job allocation, etc.
        # For now we create a basic journal entry style transaction.
        cursor = self.conn.cursor()

        date_str = row.get("Date") or row.get("DATE")
        if not date_str:
            return

        # Very basic example - expand heavily in next iteration
        cursor.execute("""
            INSERT INTO transactions (company_id, transaction_type, date, ref_number, memo, total_amount)
            SELECT id, 'JournalEntry', ?, ?, ?, 0 FROM companies LIMIT 1
        """, (date_str, row.get("Num", ""), row.get("Memo", "")[:255] if row.get("Memo") else ""))
        tx_id = cursor.lastrowid

        # Example: one debit/credit line (real version handles full splits + job/cost_code)
        account_name = row.get("Account", "")
        if account_name:
            cursor.execute("""
                SELECT id FROM chart_of_accounts WHERE name LIKE ? LIMIT 1
            """, (f"%{account_name}%",))
            acct = cursor.fetchone()
            if acct:
                debit = float(row.get("Debit", 0) or 0)
                credit = float(row.get("Credit", 0) or 0)
                cursor.execute("""
                    INSERT INTO transaction_lines (transaction_id, account_id, debit, credit)
                    VALUES (?, ?, ?, ?)
                """, (tx_id, acct[0], debit, credit))

        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()


# ============================================================
# Convenience function for quick testing
# ============================================================
if __name__ == "__main__":
    print("QB Import Engine - Test Mode")
    print("This module is designed to be called from the PyQt6 Import Wizard.")
    print("Example usage will be added in the next iteration.")
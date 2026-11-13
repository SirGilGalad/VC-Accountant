"""Base chart seeded for every company. Packs add accounts later. Tax lines stay empty."""

from __future__ import annotations

from sqlalchemy import insert, select
from sqlalchemy.engine import Connection

from core.schema import accounts

# number, name, type, subtype or None, parent number or None
BASE_CHART: list[tuple[str, str, str, str | None, str | None]] = [
    ("1000", "Cash", "asset", None, None),
    ("1010", "Operating Checking", "asset", "bank", "1000"),
    ("1020", "Payroll Checking", "asset", "bank", "1000"),
    ("1030", "Petty Cash", "asset", "bank", "1000"),
    ("1100", "Accounts Receivable", "asset", "receivable", None),
    ("1300", "Prepaid Expenses", "asset", None, None),
    ("1500", "Fixed Assets", "asset", "fixed_asset", None),
    ("1510", "Vehicles", "asset", "fixed_asset", "1500"),
    ("1520", "Equipment", "asset", "fixed_asset", "1500"),
    ("1530", "Office Equipment", "asset", "fixed_asset", "1500"),
    ("1540", "Buildings", "asset", "fixed_asset", "1500"),
    ("1550", "Land", "asset", "fixed_asset", "1500"),
    ("1600", "Accumulated Depreciation", "asset", "contra_asset", None),
    ("1610", "Accum. Dep. – Vehicles", "asset", "contra_asset", "1600"),
    ("1620", "Accum. Dep. – Equipment", "asset", "contra_asset", "1600"),
    ("2000", "Accounts Payable", "liability", "payable", None),
    ("2100", "Credit Cards Payable", "liability", "credit_card", None),
    ("2200", "Payroll Liabilities", "liability", None, None),
    ("2210", "Federal Withholding", "liability", None, "2200"),
    ("2220", "Social Security", "liability", None, "2200"),
    ("2230", "Medicare", "liability", None, "2200"),
    ("2240", "State Withholding", "liability", None, "2200"),
    ("2250", "State Unemployment", "liability", None, "2200"),
    ("2260", "Federal Unemployment", "liability", None, "2200"),
    ("2300", "Sales Tax Payable", "liability", None, None),
    ("2700", "Loans Payable", "liability", None, None),
    ("3000", "Owner's Equity", "equity", None, None),
    ("3100", "Owner's Draws", "equity", None, None),
    ("3200", "Retained Earnings", "equity", None, None),
    ("3900", "Opening Balance Equity", "equity", None, None),
    ("4000", "Sales and Service Income", "income", None, None),
    ("6000", "Advertising", "expense", None, None),
    ("6010", "Auto", "expense", None, None),
    ("6020", "Bank Fees", "expense", None, None),
    ("6100", "Depreciation Expense", "expense", None, None),
    ("6200", "Insurance", "expense", None, None),
    ("6210", "Liability Insurance", "expense", None, "6200"),
    ("6220", "Workers' Comp", "expense", None, "6200"),
    ("6230", "Vehicle Insurance", "expense", None, "6200"),
    ("6240", "Health Insurance", "expense", None, "6200"),
    ("6300", "Interest", "expense", None, None),
    ("6400", "Professional Fees", "expense", None, None),
    ("6500", "Office", "expense", None, None),
    ("6600", "Payroll Expenses", "expense", None, None),
    ("6610", "Wages", "expense", None, "6600"),
    ("6620", "Payroll Taxes", "expense", None, "6600"),
    ("6630", "Benefits", "expense", None, "6600"),
    ("6700", "Rent", "expense", None, None),
    ("6710", "Repairs", "expense", None, None),
    ("6720", "Supplies", "expense", None, None),
    ("6730", "Taxes & Licenses", "expense", None, None),
    ("6740", "Telephone", "expense", None, None),
    ("6750", "Travel", "expense", None, None),
    ("6760", "Utilities", "expense", None, None),
    ("6770", "Miscellaneous", "expense", None, None),
    ("8000", "Other Income", "other_income", None, None),
    ("8100", "Other Expense", "other_expense", None, None),
]

DEBIT_TYPES = {"asset", "expense", "cost_of_sales", "other_expense"}


def normal_balance(account_type: str, subtype: str | None) -> str:
    if subtype == "contra_asset":
        return "credit"
    if account_type in DEBIT_TYPES:
        return "debit"
    return "credit"


def seed_base_chart(conn: Connection, company_id: int) -> None:
    ids: dict[str, int] = {}
    for number, name, account_type, subtype, parent_number in BASE_CHART:
        parent_id = ids[parent_number] if parent_number else None
        result = conn.execute(
            insert(accounts).values(
                company_id=company_id,
                number=number,
                name=name,
                type=account_type,
                subtype=subtype,
                normal_balance=normal_balance(account_type, subtype),
                parent_id=parent_id,
                tax_line=None,
                is_active=True,
                is_system=True,
            )
        )
        ids[number] = int(result.inserted_primary_key[0])


def account_id_by_number(conn: Connection, company_id: int, number: str) -> int:
    row = conn.execute(
        select(accounts.c.id).where(
            accounts.c.company_id == company_id,
            accounts.c.number == number,
        )
    ).one()
    return int(row.id)

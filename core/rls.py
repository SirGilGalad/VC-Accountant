"""Postgres row policies. SQLite company files do not use them."""

from __future__ import annotations

from sqlalchemy.engine import Connection

from core.schema import metadata

_SETTING = "NULLIF(current_setting('app.tenant_id', true), '')::int"
_COMPANIES = f"(SELECT id FROM companies WHERE tenant_id = {_SETTING})"


def _predicate(table_name: str, columns: set[str]) -> str:
    if table_name == "tenants":
        return f"id = {_SETTING}"
    if table_name == "companies":
        return f"tenant_id = {_SETTING}"
    if "company_id" in columns:
        return f"company_id IN {_COMPANIES}"
    if table_name in {"party_roles", "employee_details"}:
        return f"party_id IN (SELECT id FROM parties WHERE company_id IN {_COMPANIES})"
    if table_name == "journal_lines":
        return f"entry_id IN (SELECT id FROM journal_entries WHERE company_id IN {_COMPANIES})"
    if table_name in {"bank_statements", "reconciliations"}:
        return f"bank_account_id IN (SELECT id FROM bank_accounts WHERE company_id IN {_COMPANIES})"
    if table_name == "bank_statement_lines":
        return (
            "statement_id IN (SELECT id FROM bank_statements WHERE bank_account_id IN "
            f"(SELECT id FROM bank_accounts WHERE company_id IN {_COMPANIES}))"
        )
    if table_name == "job_budgets":
        return f"job_id IN (SELECT id FROM jobs WHERE company_id IN {_COMPANIES})"
    if table_name == "occupancies":
        return f"unit_id IN (SELECT id FROM units WHERE company_id IN {_COMPANIES})"
    if table_name.startswith("stg_") or table_name == "import_issues":
        return f"batch_id IN (SELECT id FROM import_batches WHERE company_id IN {_COMPANIES})"
    raise RuntimeError(f"No tenant rule for {table_name}")


def apply_rls(conn: Connection) -> None:
    if conn.dialect.name != "postgresql":
        return
    conn.exec_driver_sql(
        """
        CREATE OR REPLACE FUNCTION vca_tenant_id(lookup text)
        RETURNS integer
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = public
        AS $$ SELECT id FROM tenants WHERE subdomain = lookup $$
        """
    )
    for table in metadata.tables.values():
        name = table.name
        expr = _predicate(name, set(table.c.keys()))
        conn.exec_driver_sql(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
        conn.exec_driver_sql(f"DROP POLICY IF EXISTS tenant_isolation ON {name}")
        conn.exec_driver_sql(
            f"CREATE POLICY tenant_isolation ON {name} USING ({expr}) WITH CHECK ({expr})"
        )

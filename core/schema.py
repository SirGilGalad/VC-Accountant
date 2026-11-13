"""Shared ledger tables. Defined once and used by SQLite and Postgres."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()

PACK_CHECK = (
    "construction",
    "property",
    "resort",
    "general",
    "professional_services",
    "retail",
    "manufacturing",
    "restaurant",
    "agriculture",
    "nonprofit",
)

tenants = Table(
    "tenants",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("subdomain", String(63), unique=True),
    Column("display_name", String(200), nullable=False),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
)

companies = Table(
    "companies",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("tenant_id", Integer, ForeignKey("tenants.id"), nullable=False),
    Column("uuid", String(36), unique=True, nullable=False),
    Column("name", String(200), nullable=False),
    Column("legal_name", String(200), nullable=False),
    Column(
        "entity_type",
        String(20),
        nullable=False,
        server_default="llc",
    ),
    Column("ein", String(20)),
    Column("pack_id", String(40), nullable=False),
    Column("address1", String(200)),
    Column("address2", String(200)),
    Column("city", String(100)),
    Column("state", String(40)),
    Column("postal_code", String(20)),
    Column("country", String(2), nullable=False, server_default="US"),
    Column("phone", String(40)),
    Column("email", String(200)),
    Column("contact_name", String(200)),
    Column("contact_phone", String(40)),
    Column("contact_email", String(200)),
    Column("fiscal_year_start_month", Integer, nullable=False, server_default="1"),
    Column("accounting_method", String(10), nullable=False, server_default="accrual"),
    Column("schema_version", String(20), nullable=False, server_default="1"),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, server_default=func.now(), nullable=False),
    CheckConstraint(
        "pack_id IN (" + ", ".join(f"'{p}'" for p in PACK_CHECK) + ")",
        name="ck_companies_pack",
    ),
    CheckConstraint(
        "entity_type IN ('sole_prop','llc','s_corp','c_corp','partnership','nonprofit','other')",
        name="ck_companies_entity",
    ),
    CheckConstraint(
        "fiscal_year_start_month BETWEEN 1 AND 12",
        name="ck_companies_fy",
    ),
    CheckConstraint(
        "accounting_method IN ('accrual','cash')",
        name="ck_companies_method",
    ),
)

members = Table(
    "members",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("email", String(200)),
    Column("os_username", String(200)),
    Column("role", String(20), nullable=False),
    Column("status", String(20), nullable=False, server_default="active"),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    CheckConstraint(
        "role IN ('owner','accountant','bookkeeper','viewer')",
        name="ck_members_role",
    ),
    CheckConstraint("status IN ('active','disabled')", name="ck_members_status"),
)

parties = Table(
    "parties",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("display_name", String(200), nullable=False),
    Column("legal_name", String(200)),
    Column("email", String(200)),
    Column("phone", String(40)),
    Column("address1", String(200)),
    Column("address2", String(200)),
    Column("city", String(100)),
    Column("state", String(40)),
    Column("postal_code", String(20)),
    Column("tax_id_last4", String(4)),
    Column("source_id", String(80)),
    Column("is_active", Boolean, nullable=False, server_default="1"),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    UniqueConstraint("company_id", "source_id", name="uq_parties_source"),
)

party_roles = Table(
    "party_roles",
    metadata,
    Column("party_id", Integer, ForeignKey("parties.id"), primary_key=True),
    Column("role", String(20), primary_key=True),
    Column("is_1099", Boolean, nullable=False, server_default="0"),
    Column("terms_days", Integer),
    CheckConstraint(
        "role IN ('customer','vendor','employee')",
        name="ck_party_roles_role",
    ),
)

employee_details = Table(
    "employee_details",
    metadata,
    Column("party_id", Integer, ForeignKey("parties.id"), primary_key=True),
    Column("first_name", String(100), nullable=False),
    Column("last_name", String(100), nullable=False),
    Column("hire_date", Date),
    Column("pay_type", String(20)),
    Column("pay_rate_cents", BigInteger),
    CheckConstraint(
        "pay_type IS NULL OR pay_type IN ('hourly','salary')",
        name="ck_employee_pay_type",
    ),
)

accounts = Table(
    "accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("number", String(20), nullable=False),
    Column("name", String(200), nullable=False),
    Column("type", String(20), nullable=False),
    Column("subtype", String(30)),
    Column("normal_balance", String(10), nullable=False),
    Column("parent_id", Integer, ForeignKey("accounts.id")),
    Column("pack_id", String(40)),
    Column("tax_line", String(80)),
    Column("is_active", Boolean, nullable=False, server_default="1"),
    Column("is_system", Boolean, nullable=False, server_default="0"),
    Column("source_id", String(80)),
    Column("notes", Text),
    UniqueConstraint("company_id", "number", name="uq_accounts_number"),
    CheckConstraint(
        "type IN ('asset','liability','equity','income','cost_of_sales','expense','other_income','other_expense')",
        name="ck_accounts_type",
    ),
    CheckConstraint(
        "normal_balance IN ('debit','credit')",
        name="ck_accounts_normal",
    ),
)

cost_codes = Table(
    "cost_codes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("code", String(20), nullable=False),
    Column("name", String(200), nullable=False),
    Column("category", String(20), nullable=False),
    Column("csi_division", String(80)),
    Column("is_active", Boolean, nullable=False, server_default="1"),
    UniqueConstraint("company_id", "code", name="uq_cost_codes_code"),
    CheckConstraint(
        "category IN ('labor','material','subcontract','equipment','other')",
        name="ck_cost_codes_category",
    ),
)

jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("customer_party_id", Integer, ForeignKey("parties.id")),
    Column("number", String(40), nullable=False),
    Column("name", String(200), nullable=False),
    Column("status", String(20), nullable=False, server_default="estimate"),
    Column("contract_amount_cents", BigInteger, nullable=False, server_default="0"),
    Column("retainage_bp", Integer),
    Column("start_date", Date),
    Column("est_completion_date", Date),
    Column("closed_date", Date),
    Column("pct_complete_method", String(20), nullable=False, server_default="cost_to_cost"),
    Column("manual_pct_bp", Integer),
    Column("source_id", String(80)),
    UniqueConstraint("company_id", "number", name="uq_jobs_number"),
    CheckConstraint(
        "status IN ('estimate','active','closed')",
        name="ck_jobs_status",
    ),
)

periods = Table(
    "periods",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("start", Date, nullable=False),
    Column("end", Date, nullable=False),
    Column("status", String(10), nullable=False, server_default="open"),
    CheckConstraint("status IN ('open','closed')", name="ck_periods_status"),
)

journal_entries = Table(
    "journal_entries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("entry_date", Date, nullable=False),
    Column("number", String(40), nullable=False),
    Column("memo", Text),
    Column("source_type", String(20), nullable=False),
    Column("status", String(10), nullable=False, server_default="draft"),
    Column("posted_at", DateTime),
    Column("posted_by_member_id", Integer, ForeignKey("members.id")),
    Column("reverses_entry_id", Integer, ForeignKey("journal_entries.id")),
    Column("import_batch_id", Integer),
    CheckConstraint(
        "source_type IN ('manual','invoice','bill','payment','deposit','payroll','depreciation','import','reversal')",
        name="ck_entries_source",
    ),
    CheckConstraint("status IN ('draft','posted','void')", name="ck_entries_status"),
)

journal_lines = Table(
    "journal_lines",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("entry_id", Integer, ForeignKey("journal_entries.id"), nullable=False),
    Column("line_no", Integer, nullable=False),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=False),
    Column("debit_cents", BigInteger, nullable=False, server_default="0"),
    Column("credit_cents", BigInteger, nullable=False, server_default="0"),
    Column("party_id", Integer, ForeignKey("parties.id")),
    Column("job_id", Integer, ForeignKey("jobs.id")),
    Column("cost_code_id", Integer, ForeignKey("cost_codes.id")),
    Column("fixed_asset_id", Integer),
    Column("pack_ref", String(40)),
    Column("memo", Text),
    CheckConstraint("debit_cents >= 0 AND credit_cents >= 0", name="ck_lines_nonneg"),
    CheckConstraint(
        "(debit_cents = 0) <> (credit_cents = 0)",
        name="ck_lines_one_side",
    ),
)

fixed_assets = Table(
    "fixed_assets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("asset_account_id", Integer, ForeignKey("accounts.id"), nullable=False),
    Column("accum_dep_account_id", Integer, ForeignKey("accounts.id"), nullable=False),
    Column("dep_expense_account_id", Integer, ForeignKey("accounts.id"), nullable=False),
    Column("in_service_date", Date, nullable=False),
    Column("cost_basis_cents", BigInteger, nullable=False),
    Column("method", String(20), nullable=False, server_default="straight_line"),
    Column("useful_life_months", Integer, nullable=False),
    Column("salvage_cents", BigInteger, nullable=False, server_default="0"),
    Column("job_id", Integer, ForeignKey("jobs.id")),
    CheckConstraint("method IN ('straight_line','none')", name="ck_assets_method"),
)

time_entries = Table(
    "time_entries",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("employee_party_id", Integer, ForeignKey("parties.id"), nullable=False),
    Column("job_id", Integer, ForeignKey("jobs.id"), nullable=False),
    Column("cost_code_id", Integer, ForeignKey("cost_codes.id"), nullable=False),
    Column("work_date", Date, nullable=False),
    Column("minutes", Integer, nullable=False),
    Column("billable", Boolean, nullable=False, server_default="1"),
    Column("notes", Text),
    Column("status", String(20), nullable=False, server_default="draft"),
    Column("payroll_entry_id", Integer, ForeignKey("journal_entries.id")),
    CheckConstraint("minutes > 0", name="ck_time_minutes"),
    CheckConstraint("status IN ('draft','approved')", name="ck_time_status"),
)

bank_accounts = Table(
    "bank_accounts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("account_id", Integer, ForeignKey("accounts.id"), nullable=False),
    Column("bank_name", String(200), nullable=False),
    Column("account_last4", String(4)),
    Column("nickname", String(200)),
)

bank_statements = Table(
    "bank_statements",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bank_account_id", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("period_start", Date, nullable=False),
    Column("period_end", Date, nullable=False),
    Column("beginning_balance_cents", BigInteger, nullable=False),
    Column("ending_balance_cents", BigInteger, nullable=False),
    Column("entered_by_member_id", Integer, ForeignKey("members.id"), nullable=False),
)

bank_statement_lines = Table(
    "bank_statement_lines",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("statement_id", Integer, ForeignKey("bank_statements.id"), nullable=False),
    Column("line_date", Date, nullable=False),
    Column("description", String(400), nullable=False),
    Column("amount_cents", BigInteger, nullable=False),
    Column("matched_journal_line_id", Integer, ForeignKey("journal_lines.id")),
    Column("entered_by_member_id", Integer, ForeignKey("members.id"), nullable=False),
)

reconciliations = Table(
    "reconciliations",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("bank_account_id", Integer, ForeignKey("bank_accounts.id"), nullable=False),
    Column("statement_id", Integer, ForeignKey("bank_statements.id"), nullable=False),
    Column("status", String(20), nullable=False, server_default="open"),
    Column("difference_cents", BigInteger),
    Column("finished_at", DateTime),
    Column("finished_by_member_id", Integer, ForeignKey("members.id")),
    CheckConstraint("status IN ('open','finished')", name="ck_recon_status"),
)

form_drafts = Table(
    "form_drafts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id"), nullable=False),
    Column("form_code", String(20), nullable=False),
    Column("revision_key", String(40), nullable=False),
    Column("period", String(20), nullable=False),
    Column("data_json", Text, nullable=False, server_default="{}"),
    Column("status", String(10), nullable=False, server_default="draft"),
    Column("created_at", DateTime, server_default=func.now(), nullable=False),
    Column("updated_at", DateTime, server_default=func.now(), nullable=False),
    CheckConstraint("status = 'draft'", name="ck_form_draft_only"),
)

ui_preferences = Table(
    "ui_preferences",
    metadata,
    Column("company_id", Integer, ForeignKey("companies.id"), primary_key=True),
    Column("member_id", Integer, ForeignKey("members.id"), primary_key=True),
    Column("key", String(80), primary_key=True),
    Column("value_json", Text, nullable=False),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, ForeignKey("companies.id")),
    Column("member_id", Integer, ForeignKey("members.id")),
    Column("action", String(40), nullable=False),
    Column("entity_type", String(40), nullable=False),
    Column("entity_id", Integer),
    Column("before_json", Text),
    Column("after_json", Text),
    Column("at", DateTime, server_default=func.now(), nullable=False),
)

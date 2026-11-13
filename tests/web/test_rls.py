"""Postgres refuses one tenant's rows to another, even without a company filter."""

import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("VCA_TEST_PG_URL"), reason="Postgres URL is not set")


def test_row_policy_hides_the_other_tenant():
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    from sqlalchemy import text

    from core.db import make_engine
    from core.services.companies import NewCompany, insert_company

    url = os.environ["VCA_TEST_PG_URL"]
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    admin = make_engine(url)
    with admin.begin() as conn:
        conn.execute(
            text(
                """
                DO $$
                BEGIN
                  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'vca_app') THEN
                    CREATE ROLE vca_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD 'vca_dev_only';
                  END IF;
                END
                $$
                """
            )
        )
        conn.execute(text("GRANT USAGE ON SCHEMA public TO vca_app"))
        conn.execute(text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO vca_app"))
        conn.execute(text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO vca_app"))
        conn.execute(text("GRANT EXECUTE ON FUNCTION vca_tenant_id(text) TO vca_app"))
        alpha_id, _member = insert_company(
            conn,
            NewCompany(name="Alpha LLC", legal_name="Alpha LLC", pack_id="general", subdomain="alpha-rls"),
        )
        beta_id, _other = insert_company(
            conn,
            NewCompany(name="Beta LLC", legal_name="Beta LLC", pack_id="general", subdomain="beta-rls"),
        )
        alpha_tenant = conn.execute(text("SELECT tenant_id FROM companies WHERE id = :id"), {"id": alpha_id}).scalar()
    app_url = url.replace("://vca:", "://vca_app:")
    app = make_engine(app_url)
    try:
        with app.begin() as conn:
            hidden = conn.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
            conn.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(alpha_tenant)})
            own = conn.execute(
                text("SELECT COUNT(*) FROM accounts WHERE company_id = :id"),
                {"id": alpha_id},
            ).scalar()
            other = conn.execute(
                text("SELECT COUNT(*) FROM accounts WHERE company_id = :id"),
                {"id": beta_id},
            ).scalar()
        assert int(hidden) == 0
        assert int(own) > 0
        assert int(other) == 0
    finally:
        with admin.begin() as conn:
            for company_id in (alpha_id, beta_id):
                conn.execute(text("DELETE FROM accounts WHERE company_id = :id"), {"id": company_id})
                conn.execute(text("DELETE FROM members WHERE company_id = :id"), {"id": company_id})
                tenant = conn.execute(
                    text("SELECT tenant_id FROM companies WHERE id = :id"),
                    {"id": company_id},
                ).scalar()
                conn.execute(text("DELETE FROM companies WHERE id = :id"), {"id": company_id})
                conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant})
        app.dispose()
        admin.dispose()

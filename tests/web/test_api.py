"""Online API behind the development stub. No sign-in."""

import json
from pathlib import Path

import pytest
from sqlalchemy import insert, text

from core.db import sqlite_url
from core.schema import members
from core.services.companies import NewCompany, create_company_file, insert_company


@pytest.fixture
def online(tmp_path, monkeypatch):
    engine, alpha_id, _member = create_company_file(
        tmp_path / "alpha.vca",
        NewCompany(
            name="Red Mesa Builders LLC",
            legal_name="Red Mesa Builders LLC",
            pack_id="general",
            subdomain="alpha",
        ),
    )
    with engine.begin() as conn:
        conn.execute(text("UPDATE members SET os_username = 'dev' WHERE company_id = :id"), {"id": alpha_id})
        beta_id, _beta_member = insert_company(
            conn,
            NewCompany(name="Other LLC", legal_name="Other LLC", pack_id="general", subdomain="beta"),
            os_username="dev",
        )
        conn.execute(
            insert(members).values(
                company_id=alpha_id,
                display_name="viewer",
                os_username="viewer",
                role="viewer",
                status="active",
            )
        )
    monkeypatch.setenv("VCA_ENV", "development")
    monkeypatch.setenv("VCA_DATABASE_URL", sqlite_url(tmp_path / "alpha.vca"))
    monkeypatch.setenv("VCA_DEV_MEMBER", "dev")
    from web.api.deps import reset_engine
    from web.api.main import create_app

    reset_engine()
    return create_app(), alpha_id, beta_id


def test_production_refuses_to_start(monkeypatch):
    monkeypatch.setenv("VCA_ENV", "production")
    from web.api.main import create_app

    with pytest.raises(SystemExit) as caught:
        create_app()
    assert "development" in str(caught.value)


def test_tenant_cannot_read_another_company(online):
    from fastapi.testclient import TestClient

    from web.api.auth_stub import BIND_HOST

    app, alpha_id, beta_id = online
    alpha = TestClient(app, base_url="http://alpha.vantagecorepro.com")
    beta = TestClient(app, base_url="http://beta.vantagecorepro.com")
    own = alpha.get(f"/api/v1/companies/{alpha_id}/accounts")
    assert own.status_code == 200
    assert any(row["number"] == "1010" for row in own.json())
    assert alpha.get(f"/api/v1/companies/{beta_id}/accounts").status_code == 404
    assert beta.get(f"/api/v1/companies/{alpha_id}/accounts").status_code == 404
    assert BIND_HOST == "127.0.0.1"


def test_post_and_report_and_import_stub(online):
    from fastapi.testclient import TestClient

    app, alpha_id, _beta = online
    client = TestClient(app, base_url="http://alpha.vantagecorepro.com")
    accounts = client.get(f"/api/v1/companies/{alpha_id}/accounts").json()
    cash = next(row for row in accounts if row["number"] == "1010")
    income = next(row for row in accounts if row["number"] == "4000")
    draft = client.post(
        f"/api/v1/companies/{alpha_id}/entries",
        json={
            "date": "2026-06-01",
            "number": "JE-1",
            "lines": [
                {"account_id": cash["id"], "debit_cents": 500, "credit_cents": 0},
                {"account_id": income["id"], "debit_cents": 0, "credit_cents": 500},
            ],
        },
    )
    assert draft.status_code == 200
    posted = client.post(f"/api/v1/companies/{alpha_id}/entries/{draft.json()['id']}/post")
    assert posted.status_code == 200
    report = client.get(f"/api/v1/companies/{alpha_id}/reports/trial-balance")
    assert report.status_code == 200
    cash_row = next(row for row in report.json() if row["number"] == "1010")
    assert cash_row["net_cents"] == 500
    blocked = client.post(f"/api/v1/companies/{alpha_id}/imports")
    assert blocked.status_code == 501
    assert blocked.json()["detail"] == "Awaiting security review."
    saved = client.put(
        f"/api/v1/companies/{alpha_id}/preferences/home.splitter",
        json={"value": [420, 700]},
    )
    assert saved.status_code == 200
    again = client.get(f"/api/v1/companies/{alpha_id}/preferences/home.splitter")
    assert again.json()["value"] == [420, 700]


def test_viewer_cannot_post(online, monkeypatch):
    from fastapi.testclient import TestClient

    app, alpha_id, _beta = online
    monkeypatch.setenv("VCA_DEV_MEMBER", "viewer")
    client = TestClient(app, base_url="http://alpha.vantagecorepro.com")
    denied = client.post(
        f"/api/v1/companies/{alpha_id}/entries",
        json={"date": "2026-06-01", "number": "X", "lines": []},
    )
    assert denied.status_code == 403


def test_openapi_matches_the_committed_document(monkeypatch):
    monkeypatch.setenv("VCA_ENV", "development")
    from web.api.main import create_app

    spec = create_app().openapi()
    committed = json.loads(Path("web/api/openapi.json").read_text(encoding="utf-8"))
    assert set(committed["paths"]) == set(spec["paths"])


def test_stub_is_the_only_place_those_words_appear():
    root = Path(__file__).resolve().parents[2]
    allowed = root / "web" / "api" / "auth_stub.py"
    hits = []
    for folder in (root / "web", root / "core"):
        for path in folder.rglob("*.py"):
            text = path.read_text(encoding="utf-8").lower()
            for word in ("password", "secret", "token"):
                if word in text and path != allowed:
                    hits.append(f"{path}:{word}")
    assert hits == []

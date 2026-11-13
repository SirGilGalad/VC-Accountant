"""Request scope: host subdomain, company, and the development member."""

from __future__ import annotations

import os
from collections.abc import Iterator

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.engine import Connection, Engine

from core.db import make_engine
from core.schema import companies, members, tenants
from web.api.auth_stub import assert_development, dev_member_name

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = os.environ.get("VCA_DATABASE_URL", "").strip()
        if not url:
            raise SystemExit("Set VCA_DATABASE_URL. See docs/ONLINE.md")
        _engine = make_engine(url)
    return _engine


def reset_engine() -> None:
    global _engine
    _engine = None


def subdomain_from_host(host: str) -> str:
    name = host.split(",")[0].strip().split(":")[0].lower()
    if name in {"", "localhost", "127.0.0.1", "testserver"}:
        raise HTTPException(status_code=400, detail="Use a company subdomain")
    return name.split(".")[0]


def _tenant_id(conn: Connection, subdomain: str) -> int:
    if conn.dialect.name == "postgresql":
        found = conn.execute(text("SELECT vca_tenant_id(:lookup)"), {"lookup": subdomain}).scalar()
    else:
        found = conn.execute(select(tenants.c.id).where(tenants.c.subdomain == subdomain)).scalar()
    if found is None:
        raise HTTPException(status_code=404, detail="Unknown company host")
    return int(found)


def scoped(company_id: int, request: Request) -> Iterator[tuple[Connection, object, object]]:
    assert_development()
    subdomain = subdomain_from_host(request.headers.get("host", ""))
    member_name = dev_member_name()
    with get_engine().begin() as conn:
        tenant_id = _tenant_id(conn, subdomain)
        if conn.dialect.name == "postgresql":
            conn.execute(text("SELECT set_config('app.tenant_id', :value, true)"), {"value": str(tenant_id)})
        company = conn.execute(
            select(companies).where(companies.c.id == company_id, companies.c.tenant_id == tenant_id)
        ).one_or_none()
        if company is None:
            raise HTTPException(status_code=404, detail="That company is not on this host")
        member = conn.execute(
            select(members).where(
                members.c.company_id == company_id,
                members.c.os_username == member_name,
                members.c.status == "active",
            )
        ).one_or_none()
        if member is None:
            raise HTTPException(status_code=403, detail="The development member is not on this company")
        if request.method != "GET" and member.role == "viewer":
            raise HTTPException(status_code=403, detail="A viewer cannot change the books")
        yield conn, company, member

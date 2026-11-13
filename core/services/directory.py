"""Lists used by the review screens. Balances are not stored here."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Connection

from core.schema import jobs, parties, party_roles


def list_parties(conn: Connection, company_id: int, role: str) -> list:
    return list(
        conn.execute(
            select(
                parties.c.id,
                parties.c.display_name,
                parties.c.phone,
                parties.c.email,
                party_roles.c.is_1099,
            )
            .select_from(parties.join(party_roles, party_roles.c.party_id == parties.c.id))
            .where(parties.c.company_id == company_id, party_roles.c.role == role)
            .order_by(parties.c.display_name)
        ).all()
    )


def list_jobs(conn: Connection, company_id: int) -> list:
    return list(
        conn.execute(
            select(jobs.c.number, jobs.c.name, jobs.c.status).where(jobs.c.company_id == company_id).order_by(jobs.c.number)
        ).all()
    )

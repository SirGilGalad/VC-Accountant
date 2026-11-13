"""Append-only audit rows."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import insert
from sqlalchemy.engine import Connection

from core.schema import audit_log


def write_audit(
    conn: Connection,
    *,
    company_id: int | None,
    member_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | None,
    before: Any = None,
    after: Any = None,
) -> None:
    conn.execute(
        insert(audit_log).values(
            company_id=company_id,
            member_id=member_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_json=None if before is None else json.dumps(before),
            after_json=None if after is None else json.dumps(after),
        )
    )

"""Compare the staged lines with the source trial balance. Net cents, not gross activity."""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.engine import Connection

from core.schema import (
    import_batches,
    import_issues,
    stg_entries,
    stg_lines,
    stg_source_trial_balance,
)


def _nets(rows: list) -> dict[str, int]:
    nets: dict[str, int] = {}
    for row in rows:
        nets[row.account_key] = nets.get(row.account_key, 0) + int(row.debit_cents) - int(row.credit_cents)
    return nets


def tie_rows(conn: Connection, batch_id: int) -> list[dict]:
    source = conn.execute(
        select(
            stg_source_trial_balance.c.account_key,
            stg_source_trial_balance.c.account_path,
            stg_source_trial_balance.c.debit_cents,
            stg_source_trial_balance.c.credit_cents,
        ).where(stg_source_trial_balance.c.batch_id == batch_id)
    ).all()
    staged = conn.execute(
        select(
            stg_lines.c.account_key,
            stg_lines.c.account_name,
            func.sum(stg_lines.c.debit_cents).label("debit_cents"),
            func.sum(stg_lines.c.credit_cents).label("credit_cents"),
        )
        .where(stg_lines.c.batch_id == batch_id)
        .group_by(stg_lines.c.account_key, stg_lines.c.account_name)
    ).all()
    source_net = _nets(source)
    staged_net = _nets(staged)
    names = {row.account_key: row.account_path for row in source}
    for row in staged:
        names.setdefault(row.account_key, row.account_name)
    keys = sorted(set(source_net) | set(staged_net), key=lambda key: (names.get(key) or key))
    report = []
    for key in keys:
        qb = source_net.get(key, 0)
        stg = staged_net.get(key, 0)
        report.append(
            {
                "account_key": key,
                "account_name": names.get(key) or key,
                "quickbooks_cents": qb,
                "staged_cents": stg,
                "difference_cents": stg - qb,
            }
        )
    report.sort(key=lambda row: (row["difference_cents"] == 0, row["account_name"]))
    return report


def _entries_balance(conn: Connection, batch_id: int) -> bool:
    rows = conn.execute(
        select(
            stg_entries.c.id,
            func.coalesce(func.sum(stg_lines.c.debit_cents), 0).label("debit_cents"),
            func.coalesce(func.sum(stg_lines.c.credit_cents), 0).label("credit_cents"),
            func.count(stg_lines.c.id).label("line_count"),
        )
        .select_from(stg_entries.outerjoin(stg_lines, stg_lines.c.entry_id == stg_entries.c.id))
        .where(stg_entries.c.batch_id == batch_id)
        .group_by(stg_entries.c.id)
    ).all()
    if not rows:
        return False
    return all(int(row.debit_cents) == int(row.credit_cents) and int(row.line_count) >= 2 for row in rows)


def error_count(conn: Connection, batch_id: int) -> int:
    return int(
        conn.execute(
            select(func.count())
            .select_from(import_issues)
            .where(import_issues.c.batch_id == batch_id, import_issues.c.severity == "error")
        ).scalar()
        or 0
    )


def consider_tie(conn: Connection, batch_id: int) -> str:
    """Set staged or tied. Failed, imported, and rejected stay as they are."""
    batch = conn.execute(select(import_batches).where(import_batches.c.id == batch_id)).one()
    if batch.status in {"failed", "imported", "rejected"}:
        return batch.status
    rows = tie_rows(conn, batch_id)
    has_source = (
        conn.execute(
            select(func.count()).select_from(stg_source_trial_balance).where(
                stg_source_trial_balance.c.batch_id == batch_id
            )
        ).scalar()
        or 0
    )
    balanced = _entries_balance(conn, batch_id)
    clean = error_count(conn, batch_id) == 0
    tied = bool(has_source) and balanced and clean and all(row["difference_cents"] == 0 for row in rows)
    status = "tied" if tied else "staged"
    conn.execute(update(import_batches).where(import_batches.c.id == batch_id).values(status=status))
    return status

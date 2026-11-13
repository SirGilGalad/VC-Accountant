"""Accept writes the staged batch in one transaction. Reject deletes staging only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine

from core.chart import normal_balance
from core.errors import LedgerError
from core.import_quickbooks.stage import _clear
from core.schema import (
    accounts,
    employee_details,
    import_batches,
    import_mappings,
    jobs,
    parties,
    party_roles,
    stg_accounts,
    stg_entries,
    stg_jobs,
    stg_lines,
    stg_parties,
)
from core.services.posting import add_draft, post_entry


class AlreadyImported(LedgerError):
    def __init__(self, batch_id: int, label: str):
        self.batch_id = batch_id
        self.label = label
        super().__init__(f"These files were already imported in batch {batch_id} ({label}).")


class ImportNotReady(LedgerError):
    pass


def save_mapping(
    conn: Connection,
    *,
    company_id: int,
    source_system: str,
    source_key: str,
    target_table: str,
    target_id: int,
) -> None:
    existing = conn.execute(
        select(import_mappings.c.id).where(
            import_mappings.c.company_id == company_id,
            import_mappings.c.source_system == source_system,
            import_mappings.c.source_key == source_key,
        )
    ).first()
    if existing is not None:
        conn.execute(
            update(import_mappings)
            .where(import_mappings.c.id == existing.id)
            .values(target_table=target_table, target_id=target_id)
        )
        return
    conn.execute(
        insert(import_mappings).values(
            company_id=company_id,
            source_system=source_system,
            source_key=source_key,
            target_table=target_table,
            target_id=target_id,
        )
    )


def accept_import(engine: Engine, batch_id: int, member_id: int) -> None:
    with engine.begin() as conn:
        batch = conn.execute(select(import_batches).where(import_batches.c.id == batch_id)).one()
        prior = conn.execute(
            select(import_batches.c.id, import_batches.c.label).where(
                import_batches.c.company_id == batch.company_id,
                import_batches.c.file_set_hash == batch.file_set_hash,
                import_batches.c.status == "imported",
            )
        ).first()
        if prior is not None:
            raise AlreadyImported(int(prior.id), prior.label)
        if batch.status != "tied":
            raise ImportNotReady("Accept stays off until the batch is tied")
        account_ids = _accounts(conn, batch)
        party_ids = _parties(conn, batch)
        job_ids = _jobs(conn, batch, party_ids)
        _entries(conn, batch, member_id, account_ids, party_ids, job_ids)
        conn.execute(
            update(import_batches)
            .where(import_batches.c.id == batch_id)
            .values(status="imported", finished_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )


def reject_import(engine: Engine, batch_id: int) -> None:
    with engine.begin() as conn:
        batch = conn.execute(select(import_batches).where(import_batches.c.id == batch_id)).one()
        if batch.status == "imported":
            raise ImportNotReady("An imported batch stays in the books. It is not rejected.")
        _clear(conn, batch_id)
        conn.execute(
            update(import_batches)
            .where(import_batches.c.id == batch_id)
            .values(status="rejected", finished_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )


def _accounts(conn: Connection, batch) -> dict[str, int]:
    rows = list(
        conn.execute(select(stg_accounts).where(stg_accounts.c.batch_id == batch.id)).all()
    )
    pending = rows
    mapped: dict[str, int] = {}
    guard = 0
    while pending and guard < 8:
        guard += 1
        next_round = []
        for row in pending:
            if row.parent_key and row.parent_key not in mapped and _needs_parent(row, pending, mapped):
                next_round.append(row)
                continue
            mapped[row.source_key] = _one_account(conn, batch, row, mapped.get(row.parent_key))
            if row.number:
                mapped[row.number] = mapped[row.source_key]
        pending = next_round
    for row in pending:
        mapped[row.source_key] = _one_account(conn, batch, row, mapped.get(row.parent_key))
        if row.number:
            mapped[row.number] = mapped[row.source_key]
    return mapped


def _needs_parent(row, pending, mapped) -> bool:
    return any(item.source_key == row.parent_key for item in pending if item.source_key != row.source_key) or (
        row.parent_key not in mapped
    )


def _one_account(conn: Connection, batch, row, parent_id: int | None) -> int:
    if not row.account_type or not row.number:
        existing = None
        if row.number:
            existing = conn.execute(
                select(accounts.c.id).where(
                    accounts.c.company_id == batch.company_id,
                    accounts.c.number == row.number,
                )
            ).scalar()
        if existing is not None:
            return int(existing)
        raise ImportNotReady(f"Account {row.name} has no type or number, so it was not created")
    found = conn.execute(
        select(accounts.c.id).where(
            accounts.c.company_id == batch.company_id,
            accounts.c.number == row.number,
        )
    ).scalar()
    if found is not None:
        conn.execute(
            update(accounts)
            .where(accounts.c.id == found, accounts.c.source_id.is_(None))
            .values(source_id=row.source_key[:80])
        )
        return int(found)
    by_name = conn.execute(
        select(accounts.c.id).where(
            accounts.c.company_id == batch.company_id,
            accounts.c.name == row.source_key,
        )
    ).scalar()
    if by_name is not None:
        return int(by_name)
    result = conn.execute(
        insert(accounts).values(
            company_id=batch.company_id,
            number=row.number,
            name=row.name,
            type=row.account_type,
            subtype=row.subtype,
            normal_balance=normal_balance(row.account_type, row.subtype),
            parent_id=parent_id,
            tax_line=None,
            is_active=bool(row.is_active),
            is_system=False,
            source_id=row.source_key[:80],
        )
    )
    return int(result.inserted_primary_key[0])


def _parties(conn: Connection, batch) -> dict[str, int]:
    mapped: dict[str, int] = {}
    rows = conn.execute(select(stg_parties).where(stg_parties.c.batch_id == batch.id)).all()
    for row in rows:
        found = conn.execute(
            select(parties.c.id).where(
                parties.c.company_id == batch.company_id,
                parties.c.source_id == row.source_key[:80],
            )
        ).scalar()
        if found is None:
            found = int(
                conn.execute(
                    insert(parties).values(
                        company_id=batch.company_id,
                        display_name=row.display_name,
                        source_id=row.source_key[:80],
                        is_active=True,
                    )
                ).inserted_primary_key[0]
            )
        else:
            found = int(found)
        mapped[row.source_key] = found
        mapped[row.display_name] = found
        if row.kind in {"customer", "vendor", "employee"}:
            role_exists = conn.execute(
                select(party_roles.c.party_id).where(
                    party_roles.c.party_id == found,
                    party_roles.c.role == row.kind,
                )
            ).first()
            if role_exists is None:
                conn.execute(
                    insert(party_roles).values(
                        party_id=found,
                        role=row.kind,
                        is_1099=bool(row.is_1099) if row.kind == "vendor" else False,
                    )
                )
        if row.kind == "employee":
            details = conn.execute(
                select(employee_details.c.party_id).where(employee_details.c.party_id == found)
            ).first()
            if details is None:
                conn.execute(
                    insert(employee_details).values(
                        party_id=found,
                        first_name=row.first_name or row.display_name,
                        last_name=row.last_name or "",
                    )
                )
    return mapped


def _jobs(conn: Connection, batch, party_ids: dict[str, int]) -> dict[str, int]:
    mapped: dict[str, int] = {}
    rows = conn.execute(select(stg_jobs).where(stg_jobs.c.batch_id == batch.id)).all()
    for row in rows:
        number = row.number[:40]
        found = conn.execute(
            select(jobs.c.id).where(jobs.c.company_id == batch.company_id, jobs.c.number == number)
        ).scalar()
        if found is None:
            found = int(
                conn.execute(
                    insert(jobs).values(
                        company_id=batch.company_id,
                        customer_party_id=party_ids.get(row.customer_key),
                        number=number,
                        name=row.name,
                        status="active",
                        source_id=row.source_key[:80],
                    )
                ).inserted_primary_key[0]
            )
        else:
            found = int(found)
        mapped[row.source_key] = found
        mapped[row.name] = found
    return mapped


def _entries(conn: Connection, batch, member_id: int, account_ids, party_ids, job_ids) -> None:
    entries = conn.execute(select(stg_entries).where(stg_entries.c.batch_id == batch.id)).all()
    for entry in entries:
        lines = conn.execute(
            select(stg_lines).where(stg_lines.c.entry_id == entry.id).order_by(stg_lines.c.line_no)
        ).all()
        payload = []
        for line in lines:
            account_id = account_ids.get(line.account_key) or _live_account(conn, batch.company_id, line)
            if account_id is None:
                raise ImportNotReady(f"No account for {line.account_name}")
            cost_code_id = None
            if line.source_class:
                cost_code_id = _mapped_class(conn, batch, line.source_class)
            payload.append(
                {
                    "account_id": account_id,
                    "debit_cents": int(line.debit_cents),
                    "credit_cents": int(line.credit_cents),
                    "party_id": party_ids.get(line.party_name),
                    "job_id": job_ids.get(line.job_name),
                    "cost_code_id": cost_code_id,
                    "memo": line.memo,
                }
            )
        entry_id = add_draft(
            conn,
            company_id=batch.company_id,
            member_id=member_id,
            entry_date=entry.entry_date,
            number=entry.number,
            memo=entry.memo,
            source_type="import",
            lines=payload,
        )
        conn.execute(
            update(journal_entries_table())
            .where(journal_entries_table().c.id == entry_id)
            .values(import_batch_id=batch.id)
        )
        post_entry(conn, entry_id, member_id)


def journal_entries_table():
    from core.schema import journal_entries

    return journal_entries


def _live_account(conn: Connection, company_id: int, line) -> int | None:
    found = conn.execute(
        select(accounts.c.id).where(accounts.c.company_id == company_id, accounts.c.number == line.account_key)
    ).scalar()
    if found is not None:
        return int(found)
    found = conn.execute(
        select(accounts.c.id).where(accounts.c.company_id == company_id, accounts.c.name == line.account_name)
    ).scalar()
    if found is not None:
        return int(found)
    return None


def _mapped_class(conn: Connection, batch, source_class: str) -> int | None:
    row = conn.execute(
        select(import_mappings.c.target_id).where(
            import_mappings.c.company_id == batch.company_id,
            import_mappings.c.source_system == batch.source_system,
            import_mappings.c.source_key == f"class:{source_class}",
            import_mappings.c.target_table == "cost_codes",
        )
    ).scalar()
    return int(row) if row is not None else None


def add_opening_gap(engine: Engine, batch_id: int) -> None:
    """One staged entry for the gap between detail and the source trial balance.

    Dated the day before the cutoff. The offset, if the gap itself does not balance,
    goes to 3900. This is not called automatically.
    """
    from core.import_quickbooks.tie import consider_tie, tie_rows

    with engine.begin() as conn:
        batch = conn.execute(select(import_batches).where(import_batches.c.id == batch_id)).one()
        if batch.status in {"imported", "failed", "rejected"}:
            raise ImportNotReady("This batch cannot take an opening entry")
        if batch.cutoff_date is None:
            raise ImportNotReady("The batch needs a cutoff date")
        gaps = [row for row in tie_rows(conn, batch_id) if row["difference_cents"] != 0]
        if not gaps:
            return
        existing = conn.execute(
            select(stg_entries.c.id).where(
                stg_entries.c.batch_id == batch_id,
                stg_entries.c.source_key == "opening-gap",
            )
        ).scalar()
        if existing is not None:
            conn.execute(delete_lines(existing))
            conn.execute(delete_entry(existing))
        entry_id = int(
            conn.execute(
                insert(stg_entries).values(
                    batch_id=batch_id,
                    source_key="opening-gap",
                    entry_date=batch.cutoff_date - timedelta(days=1),
                    number="OPEN",
                    memo="Opening balance for years not imported in detail",
                    txn_type="opening",
                )
            ).inserted_primary_key[0]
        )
        line_no = 1
        plug = 0
        for gap in gaps:
            # difference is staged minus source. Add the opposite so staged moves to the source.
            need = -int(gap["difference_cents"])
            if need == 0:
                continue
            plug += need
            debit, credit = (need, 0) if need > 0 else (0, -need)
            conn.execute(
                insert(stg_lines).values(
                    batch_id=batch_id,
                    entry_id=entry_id,
                    line_no=line_no,
                    account_key=gap["account_key"],
                    account_name=gap["account_name"],
                    debit_cents=debit,
                    credit_cents=credit,
                    party_name=None,
                    job_name=None,
                    source_class=None,
                    memo="Opening",
                )
            )
            line_no += 1
        if plug != 0:
            debit, credit = (0, plug) if plug > 0 else (-plug, 0)
            conn.execute(
                insert(stg_lines).values(
                    batch_id=batch_id,
                    entry_id=entry_id,
                    line_no=line_no,
                    account_key="3900",
                    account_name="3900 Opening Balance Equity",
                    debit_cents=debit,
                    credit_cents=credit,
                    party_name=None,
                    job_name=None,
                    source_class=None,
                    memo="Opening offset",
                )
            )
        consider_tie(conn, batch_id)


def delete_lines(entry_id: int):
    return delete_table(stg_lines).where(stg_lines.c.entry_id == entry_id)


def delete_entry(entry_id: int):
    return delete_table(stg_entries).where(stg_entries.c.id == entry_id)


def delete_table(table):
    from sqlalchemy import delete

    return delete(table)

"""The import a person runs. Stage, tie, accept, or reject."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from core.import_quickbooks.accept import (
    AlreadyImported,
    ImportNotReady,
    accept_import,
    add_opening_gap,
    reject_import,
    save_mapping,
)
from core.import_quickbooks.stage import stage_import
from core.import_quickbooks.tie import error_count, tie_rows
from core.schema import import_batches, import_issues, stg_lines


class QuickBooksImport:
    def __init__(self, engine: Engine, company_id: int, member_id: int):
        self.engine = engine
        self.company_id = company_id
        self.member_id = member_id

    def stage(self, files: list[Path | str], cutoff: date, label: str = "Import", progress=None) -> int:
        return stage_import(
            self.engine,
            company_id=self.company_id,
            member_id=self.member_id,
            files=files,
            cutoff=cutoff,
            label=label,
            progress=progress,
        )

    def status(self, batch_id: int) -> str:
        with self.engine.connect() as conn:
            return conn.execute(
                select(import_batches.c.status).where(import_batches.c.id == batch_id)
            ).scalar_one()

    def tie(self, batch_id: int) -> list[dict]:
        with self.engine.connect() as conn:
            return tie_rows(conn, batch_id)

    def issues(self, batch_id: int) -> list:
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    select(import_issues)
                    .where(import_issues.c.batch_id == batch_id)
                    .order_by(import_issues.c.id)
                ).all()
            )

    def lines_for(self, batch_id: int, account_key: str) -> list:
        with self.engine.connect() as conn:
            return list(
                conn.execute(
                    select(stg_lines)
                    .where(stg_lines.c.batch_id == batch_id, stg_lines.c.account_key == account_key)
                    .order_by(stg_lines.c.id)
                ).all()
            )

    def accept(self, batch_id: int) -> None:
        accept_import(self.engine, batch_id, self.member_id)

    def reject(self, batch_id: int) -> None:
        reject_import(self.engine, batch_id)

    def opening_gap(self, batch_id: int) -> None:
        add_opening_gap(self.engine, batch_id)

    def map_class(self, source_class: str, cost_code_id: int) -> None:
        with self.engine.begin() as conn:
            save_mapping(
                conn,
                company_id=self.company_id,
                source_system=_source(conn, self.company_id),
                source_key=f"class:{source_class}",
                target_table="cost_codes",
                target_id=cost_code_id,
            )

    def error_count(self, batch_id: int) -> int:
        with self.engine.connect() as conn:
            return error_count(conn, batch_id)


def _source(conn: Connection, company_id: int) -> str:
    from core.import_quickbooks.constants import SOURCE_SYSTEM

    row = conn.execute(
        select(import_batches.c.source_system).where(import_batches.c.company_id == company_id).limit(1)
    ).scalar()
    return row or SOURCE_SYSTEM


__all__ = ["AlreadyImported", "ImportNotReady", "QuickBooksImport"]

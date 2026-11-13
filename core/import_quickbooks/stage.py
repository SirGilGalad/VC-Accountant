"""Parse export files into staging tables. Live books are not touched."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path

from sqlalchemy import delete, insert, select, update
from sqlalchemy.engine import Connection, Engine

from core.chart import BASE_CHART
from core.import_quickbooks.constants import SOURCE_SYSTEM
from core.import_quickbooks.iif import MalformedFile, decode_export, parse_iif
from core.import_quickbooks.report_csv import parse_transaction_detail, parse_trial_balance, read_table
from core.import_quickbooks.tie import consider_tie
from core.schema import (
    import_batches,
    import_issues,
    stg_accounts,
    stg_entries,
    stg_jobs,
    stg_lines,
    stg_parties,
    stg_source_trial_balance,
)

CHUNK = 1000


def file_set_hash(digests: list[str]) -> str:
    joined = "\n".join(sorted(digests))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _kind(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".iif"):
        return "lists"
    if "trial" in lower:
        return "trial_balance"
    return "transactions"


def _clear(conn: Connection, batch_id: int) -> None:
    conn.execute(delete(stg_lines).where(stg_lines.c.batch_id == batch_id))
    conn.execute(delete(stg_entries).where(stg_entries.c.batch_id == batch_id))
    conn.execute(delete(stg_jobs).where(stg_jobs.c.batch_id == batch_id))
    conn.execute(delete(stg_parties).where(stg_parties.c.batch_id == batch_id))
    conn.execute(delete(stg_accounts).where(stg_accounts.c.batch_id == batch_id))
    conn.execute(delete(stg_source_trial_balance).where(stg_source_trial_balance.c.batch_id == batch_id))
    conn.execute(delete(import_issues).where(import_issues.c.batch_id == batch_id))


def _flush(engine: Engine, table, rows: list[dict], progress, done: list[int]) -> None:
    for start in range(0, len(rows), CHUNK):
        chunk = rows[start : start + CHUNK]
        if not chunk:
            continue
        with engine.begin() as conn:
            conn.execute(insert(table), chunk)
        done[0] += len(chunk)
        if progress is not None:
            progress(done[0])


def stage_import(
    engine: Engine,
    *,
    company_id: int,
    member_id: int,
    files: list[Path | str],
    cutoff: date,
    label: str = "Import",
    progress=None,
) -> int:
    payloads = []
    for item in files:
        path = Path(item)
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        payloads.append(
            {
                "name": path.name,
                "data": data,
                "sha256": digest,
                "size": len(data),
                "kind": _kind(path.name),
            }
        )
    digest_key = file_set_hash([item["sha256"] for item in payloads])
    with engine.begin() as conn:
        imported = conn.execute(
            select(import_batches).where(
                import_batches.c.company_id == company_id,
                import_batches.c.file_set_hash == digest_key,
                import_batches.c.status == "imported",
            )
        ).first()
        if imported is not None:
            return int(imported.id)
        existing = conn.execute(
            select(import_batches.c.id).where(
                import_batches.c.company_id == company_id,
                import_batches.c.file_set_hash == digest_key,
                import_batches.c.status != "imported",
            )
        ).first()
        files_json = json.dumps(
            [
                {"name": item["name"], "sha256": item["sha256"], "size": item["size"], "kind": item["kind"]}
                for item in payloads
            ]
        )
        if existing is None:
            batch_id = int(
                conn.execute(
                    insert(import_batches).values(
                        company_id=company_id,
                        source_system=SOURCE_SYSTEM,
                        label=label,
                        status="staged",
                        cutoff_date=cutoff,
                        created_by_member_id=member_id,
                        files_json=files_json,
                        file_set_hash=digest_key,
                    )
                ).inserted_primary_key[0]
            )
        else:
            batch_id = int(existing.id)
            _clear(conn, batch_id)
            conn.execute(
                update(import_batches)
                .where(import_batches.c.id == batch_id)
                .values(
                    status="staged",
                    cutoff_date=cutoff,
                    label=label,
                    files_json=files_json,
                    finished_at=None,
                )
            )
    _load(engine, batch_id, payloads, cutoff, progress)
    with engine.begin() as conn:
        consider_tie(conn, batch_id)
    return batch_id


def _load(engine: Engine, batch_id: int, payloads: list[dict], cutoff: date, progress) -> None:
    accounts: list[dict] = []
    parties: list[dict] = []
    jobs: list[dict] = []
    raw_entries: list[dict] = []
    trial: list[dict] = []
    issues: list[dict] = []
    failed = False
    for item in payloads:
        try:
            parsed = _parse_one(item, cutoff)
        except MalformedFile as exc:
            failed = True
            issues.append(
                {
                    "batch_id": batch_id,
                    "severity": "error",
                    "file_name": item["name"],
                    "row_number": exc.row_number,
                    "message": str(exc),
                }
            )
            continue
        for issue in parsed["issues"]:
            issues.append({"batch_id": batch_id, **issue})
        for row in parsed["accounts"]:
            accounts.append({"batch_id": batch_id, **row})
        for row in parsed["parties"]:
            parties.append({"batch_id": batch_id, **row})
        for row in parsed["jobs"]:
            jobs.append({"batch_id": batch_id, **row})
        raw_entries.extend(parsed["entries"])
        for row in parsed["trial"]:
            trial.append({"batch_id": batch_id, **row})
    entries, match_issues = _drop_unmatched_groups(raw_entries, accounts)
    for issue in match_issues:
        issues.append({"batch_id": batch_id, **issue})
    done = [0]
    _flush(engine, stg_accounts, accounts, progress, done)
    _flush(engine, stg_parties, parties, progress, done)
    _flush(engine, stg_jobs, jobs, progress, done)
    entry_ids: dict[str, int] = {}
    with engine.begin() as conn:
        for entry in entries:
            entry_id = int(
                conn.execute(
                    insert(stg_entries).values(
                        batch_id=batch_id,
                        source_key=entry["source_key"],
                        entry_date=entry["entry_date"],
                        number=entry["number"],
                        memo=entry["memo"],
                        txn_type=entry["txn_type"],
                    )
                ).inserted_primary_key[0]
            )
            entry_ids[entry["source_key"]] = entry_id
            done[0] += 1
    line_rows = []
    for entry in entries:
        entry_id = entry_ids.get(entry["source_key"])
        if entry_id is None:
            continue
        for line_no, line in enumerate(entry["lines"], start=1):
            line_rows.append(
                {
                    "batch_id": batch_id,
                    "entry_id": entry_id,
                    "line_no": line_no,
                    "account_key": line["account_key"],
                    "account_name": line["account_name"],
                    "debit_cents": line["debit_cents"],
                    "credit_cents": line["credit_cents"],
                    "party_name": line["party_name"] or None,
                    "job_name": line["job_name"] or None,
                    "source_class": line["source_class"] or None,
                    "memo": line["memo"] or None,
                }
            )
    _flush(engine, stg_lines, line_rows, progress, done)
    _flush(engine, stg_source_trial_balance, trial, progress, done)
    if issues:
        _flush(engine, import_issues, issues, progress, done)
    if progress is not None:
        progress(done[0])
    if failed:
        with engine.begin() as conn:
            conn.execute(update(import_batches).where(import_batches.c.id == batch_id).values(status="failed"))


def _parse_one(item: dict, cutoff: date) -> dict:
    empty = {"accounts": [], "parties": [], "jobs": [], "entries": [], "trial": [], "issues": []}
    if item["kind"] == "lists":
        text, decode_issues = decode_export(item["data"], item["name"])
        parsed = parse_iif(text, item["name"])
        parsed["entries"] = []
        parsed["trial"] = []
        parsed["issues"] = decode_issues + parsed["issues"]
        return parsed
    rows = read_table(item["data"], item["name"])
    if item["kind"] == "trial_balance":
        parsed = parse_trial_balance(rows, item["name"], cutoff)
        empty["trial"] = parsed["lines"]
        empty["issues"] = parsed["issues"]
        return empty
    parsed = parse_transaction_detail(rows, item["name"])
    empty["entries"] = parsed["entries"]
    empty["issues"] = parsed["issues"]
    return empty


def _drop_unmatched_groups(entries: list[dict], accounts: list[dict]) -> tuple[list[dict], list[dict]]:
    """An unknown account is an issue. A partial name is never a match."""
    known_numbers = {number for number, *_rest in BASE_CHART}
    known_names = {name for _number, name, *_rest in BASE_CHART}
    for row in accounts:
        if row.get("number"):
            known_numbers.add(row["number"])
        if row.get("source_key"):
            known_names.add(row["source_key"])
        if row.get("name"):
            known_names.add(row["name"])
    kept = []
    issues = []
    for entry in entries:
        bad = False
        for line in entry["lines"]:
            key = line["account_key"]
            name = line["account_name"]
            if key in known_numbers or name in known_names or key.isdigit():
                continue
            bad = True
            issues.append(
                {
                    "severity": "error",
                    "file_name": line["file_name"],
                    "row_number": line["row_number"],
                    "message": f"Unknown account {name}. It was not matched.",
                }
            )
        if bad or len(entry["lines"]) < 2:
            if len(entry["lines"]) < 2 and not bad:
                first = entry["lines"][0] if entry["lines"] else {}
                issues.append(
                    {
                        "severity": "error",
                        "file_name": first.get("file_name", ""),
                        "row_number": first.get("row_number"),
                        "message": f"Entry {entry['number']} does not have two lines",
                    }
                )
            continue
        kept.append(entry)
    return kept, issues

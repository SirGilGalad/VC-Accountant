"""Transaction Detail and other columnar reports, CSV or XLSX."""

from __future__ import annotations

import csv
from datetime import date, datetime
from io import StringIO

from openpyxl import load_workbook

from core.import_quickbooks.iif import MalformedFile
from core.import_quickbooks.money import fold_sides

HEADER_ALIASES = {
    "account": "account",
    "account name": "account",
    "type": "type",
    "date": "date",
    "num": "num",
    "number": "num",
    "name": "name",
    "memo": "memo",
    "memo/description": "memo",
    "class": "class",
    "debit": "debit",
    "credit": "credit",
    "trans #": "trans",
    "trans": "trans",
    "transaction": "trans",
}


def account_key(label: str) -> tuple[str, str]:
    """Return (key, display). A leading number is the key. Otherwise the full name is."""
    text = " ".join((label or "").replace("·", " ").split())
    if not text:
        return "", ""
    first, _, rest = text.partition(" ")
    if first.isdigit():
        return first, text
    return text, text


def parse_date(raw: str) -> date | None:
    text = (raw or "").strip()
    if not text:
        return None
    for pattern in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text[:10], pattern).date()
        except ValueError:
            continue
    return None


def read_table(data: bytes, file_name: str) -> list[list[str]]:
    lower = file_name.lower()
    if lower.endswith(".xlsx"):
        return _read_xlsx(data, file_name)
    if lower.endswith(".csv") or lower.endswith(".txt"):
        return _read_csv(data, file_name)
    raise MalformedFile(f"{file_name} is not a CSV or XLSX report")


def _read_csv(data: bytes, file_name: str) -> list[list[str]]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise MalformedFile(f"{file_name} could not be decoded") from exc
    rows = []
    for row in csv.reader(StringIO(text)):
        rows.append([cell.strip() for cell in row])
    return rows


def _read_xlsx(data: bytes, file_name: str) -> list[list[str]]:
    from io import BytesIO

    try:
        book = load_workbook(BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise MalformedFile(f"{file_name} could not be opened") from exc
    sheet = book.active
    rows: list[list[str]] = []
    for row in sheet.iter_rows(values_only=True):
        cells = []
        for value in row:
            if value is None:
                cells.append("")
            elif isinstance(value, datetime):
                cells.append(value.date().isoformat())
            elif isinstance(value, date):
                cells.append(value.isoformat())
            else:
                cells.append(str(value).strip())
        rows.append(cells)
    book.close()
    return rows


def _header_map(row: list[str]) -> dict[str, int] | None:
    found: dict[str, int] = {}
    for index, cell in enumerate(row):
        key = HEADER_ALIASES.get(cell.strip().lower())
        if key and key not in found:
            found[key] = index
    if "debit" in found and ("account" in found or "credit" in found):
        return found
    return None


def _cell(row: list[str], mapping: dict[str, int], name: str) -> str:
    index = mapping.get(name)
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def _is_total(row: list[str]) -> bool:
    for cell in row:
        if cell.strip().lower().startswith("total"):
            return True
    return False


def parse_transaction_detail(rows: list[list[str]], file_name: str) -> dict:
    header_at = None
    mapping = None
    for index, row in enumerate(rows):
        mapping = _header_map(row)
        if mapping and "account" in mapping:
            header_at = index
            break
    if header_at is None or mapping is None:
        raise MalformedFile(f"{file_name} has no account, debit, and credit header")
    grouped: dict[str, dict] = {}
    issues: list[dict] = []
    order: list[str] = []
    for row_number, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        if not any(cell.strip() for cell in row):
            continue
        if _is_total(row):
            continue
        account = _cell(row, mapping, "account")
        debit_raw = _cell(row, mapping, "debit")
        credit_raw = _cell(row, mapping, "credit")
        if not account and not debit_raw and not credit_raw:
            continue
        sides = fold_sides(debit_raw, credit_raw)
        if sides is None or sides == (0, 0):
            issues.append(
                {
                    "severity": "error",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": f"Amount on {account or 'a blank account'} could not be read as one side",
                }
            )
            continue
        debit_cents, credit_cents = sides
        trans = _cell(row, mapping, "trans")
        txn_type = _cell(row, mapping, "type")
        number = _cell(row, mapping, "num")
        txn_date = parse_date(_cell(row, mapping, "date"))
        name = _cell(row, mapping, "name")
        if trans:
            key = f"trans:{trans}"
        else:
            key = "|".join([txn_type, number, _cell(row, mapping, "date"), name])
        if key not in grouped:
            if txn_date is None:
                issues.append(
                    {
                        "severity": "error",
                        "file_name": file_name,
                        "row_number": row_number,
                        "message": f"No date for {account or key}",
                    }
                )
                continue
            grouped[key] = {
                "source_key": key[:200],
                "entry_date": txn_date,
                "number": (number or trans or "import")[:40],
                "memo": _cell(row, mapping, "memo"),
                "txn_type": txn_type[:40],
                "lines": [],
            }
            order.append(key)
        key_id, display = account_key(account)
        if not key_id:
            issues.append(
                {
                    "severity": "error",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": "A line has no account",
                }
            )
            continue
        grouped[key]["lines"].append(
            {
                "account_key": key_id,
                "account_name": display,
                "debit_cents": debit_cents,
                "credit_cents": credit_cents,
                "party_name": name,
                "job_name": "",
                "source_class": _cell(row, mapping, "class"),
                "memo": _cell(row, mapping, "memo"),
                "row_number": row_number,
                "file_name": file_name,
            }
        )
    entries = [grouped[key] for key in order]
    return {"entries": entries, "issues": issues}


def parse_trial_balance(rows: list[list[str]], file_name: str, as_of: date | None) -> dict:
    header_at = None
    mapping = None
    for index, row in enumerate(rows):
        found = _header_map(row)
        if found and "debit" in found and "credit" in found:
            header_at = index
            mapping = found
            break
    if header_at is None or mapping is None:
        raise MalformedFile(f"{file_name} has no debit and credit header")
    lines = []
    issues: list[dict] = []
    for row_number, row in enumerate(rows[header_at + 1 :], start=header_at + 2):
        if not any(cell.strip() for cell in row):
            continue
        if _is_total(row):
            continue
        if "account" in mapping:
            label = _cell(row, mapping, "account")
        else:
            label = next((cell.strip() for cell in row if cell.strip()), "")
        if not label or label.lower() in {"debit", "credit"}:
            continue
        sides = fold_sides(_cell(row, mapping, "debit"), _cell(row, mapping, "credit"))
        if sides is None or sides == (0, 0):
            issues.append(
                {
                    "severity": "error",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": f"Trial balance amount for {label} could not be read",
                }
            )
            continue
        debit_cents, credit_cents = sides
        key, display = account_key(label)
        lines.append(
            {
                "account_key": key,
                "account_path": display,
                "debit_cents": debit_cents,
                "credit_cents": credit_cents,
                "as_of": as_of,
            }
        )
    return {"lines": lines, "issues": issues}

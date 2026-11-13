"""Lists export. The row type is the first token, not a data column."""

from __future__ import annotations

from core.import_quickbooks.constants import QB_ACCOUNT_TYPES


class MalformedFile(Exception):
    def __init__(self, message: str, row_number: int | None = None):
        self.row_number = row_number
        super().__init__(message)


def decode_export(data: bytes, file_name: str) -> tuple[str, list[dict]]:
    """Try utf-8 first. Fall back line by line. Never drop bytes quietly."""
    issues: list[dict] = []
    if b"\x00" in data:
        raise MalformedFile(f"{file_name} is not a text export")
    try:
        return data.decode("utf-8-sig"), issues
    except UnicodeDecodeError:
        pass
    lines_out: list[str] = []
    for number, raw in enumerate(data.splitlines(), start=1):
        try:
            lines_out.append(raw.decode("utf-8"))
            continue
        except UnicodeDecodeError:
            pass
        try:
            lines_out.append(raw.decode("cp1252"))
        except UnicodeDecodeError:
            issues.append(
                {
                    "severity": "error",
                    "file_name": file_name,
                    "row_number": number,
                    "message": "This line could not be decoded",
                }
            )
            raise MalformedFile(f"{file_name} line {number} could not be decoded", number) from None
    issues.append(
        {
            "severity": "info",
            "file_name": file_name,
            "row_number": None,
            "message": "Read with the Windows text encoding after UTF-8 failed",
        }
    )
    return "\n".join(lines_out), issues


def split_fields(line: str) -> list[str]:
    fields: list[str] = []
    buf: list[str] = []
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if quoted:
            if char == '"':
                if index + 1 < len(line) and line[index + 1] == '"':
                    buf.append('"')
                    index += 2
                    continue
                quoted = False
                index += 1
                continue
            buf.append(char)
            index += 1
            continue
        if char == '"':
            quoted = True
            index += 1
            continue
        if char == "\t":
            fields.append("".join(buf))
            buf = []
            index += 1
            continue
        buf.append(char)
        index += 1
    fields.append("".join(buf))
    if quoted:
        raise MalformedFile("A quoted field was not closed")
    while len(fields) > 1 and fields[-1] == "":
        fields.pop()
    return fields


def _flag(value: str | None) -> bool:
    return (value or "").strip().lower() in {"y", "yes", "true", "1", "x"}


def _record(headers: list[str], values: list[str]) -> dict[str, str]:
    paired = {}
    for key, value in zip(headers, values, strict=False):
        paired[key.strip().upper()] = value.strip()
    return paired


def parse_iif(text: str, file_name: str) -> dict:
    """Return accounts, parties, jobs, items and issues. Items are reference only."""
    accounts: list[dict] = []
    parties: list[dict] = []
    jobs: list[dict] = []
    issues: list[dict] = []
    headers: list[str] | None = None
    item_count = 0
    for row_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.rstrip("\r")
        if not line.strip():
            continue
        try:
            fields = split_fields(line)
        except MalformedFile as exc:
            raise MalformedFile(str(exc), row_number) from exc
        token = fields[0].strip()
        if token.startswith("!"):
            headers = [item.strip() for item in fields[1:]]
            continue
        if token in {"ENDTRNS", "ENDSPL", "TRNS", "SPL"}:
            issues.append(
                {
                    "severity": "info",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": "Transaction rows in a lists file are skipped. Export Transaction Detail for those.",
                }
            )
            continue
        if headers is None:
            raise MalformedFile(f"{file_name} has a data row before its header", row_number)
        record = _record(headers, fields[1:])
        kind = token.upper()
        if kind == "ACCNT":
            accounts.append(_account(record, file_name, row_number, issues))
        elif kind == "CUST":
            _customer(record, parties, jobs)
        elif kind == "VEND":
            parties.append(_vendor(record))
        elif kind == "EMP":
            parties.append(_employee(record))
        elif kind == "OTHERNAME":
            name = record.get("NAME") or ""
            if name:
                parties.append(
                    {
                        "source_key": f"other:{name}",
                        "kind": "other",
                        "display_name": name,
                        "is_1099": False,
                        "first_name": None,
                        "last_name": None,
                    }
                )
        elif kind == "INVITEM":
            item_count += 1
            name = record.get("NAME") or "item"
            issues.append(
                {
                    "severity": "info",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": f"Item {name} was read for reference only and was not posted",
                }
            )
        # Unknown list types are ignored as info so a lists file can carry extra sections.
        elif kind:
            issues.append(
                {
                    "severity": "info",
                    "file_name": file_name,
                    "row_number": row_number,
                    "message": f"List type {kind} is not used",
                }
            )
    accounts = _fill_parents(accounts)
    if item_count:
        issues.append(
            {
                "severity": "info",
                "file_name": file_name,
                "row_number": None,
                "message": f"{item_count} items were kept for reference only",
            }
        )
    return {"accounts": accounts, "parties": parties, "jobs": jobs, "issues": issues}


def _account(record: dict, file_name: str, row_number: int, issues: list[dict]) -> dict:
    name = record.get("NAME") or ""
    qb_type = (record.get("ACCNTTYPE") or "").upper()
    number = record.get("ACCNUM") or ""
    mapped = QB_ACCOUNT_TYPES.get(qb_type)
    account_type = None
    subtype = None
    if not name:
        issues.append(
            {
                "severity": "error",
                "file_name": file_name,
                "row_number": row_number,
                "message": "An account row has no name",
            }
        )
    elif mapped is None:
        issues.append(
            {
                "severity": "error",
                "file_name": file_name,
                "row_number": row_number,
                "message": f"Unknown account type {qb_type or '(blank)'} on {name}",
            }
        )
    else:
        account_type, subtype = mapped
    parent_key = None
    leaf = name
    if ":" in name:
        parent_key, leaf = name.rsplit(":", 1)
    return {
        "source_key": name,
        "number": number,
        "name": leaf or name,
        "qb_type": qb_type,
        "account_type": account_type,
        "subtype": subtype,
        "parent_key": parent_key,
        "is_active": (record.get("HIDDEN") or "").upper() not in {"Y", "YES"},
    }


def _fill_parents(accounts: list[dict]) -> list[dict]:
    """A path such as Job Costs:Materials creates the parent when the file omitted it."""
    by_key = {row["source_key"]: row for row in accounts if row["source_key"]}
    for row in list(by_key.values()):
        parent_key = row["parent_key"]
        if parent_key and parent_key not in by_key:
            by_key[parent_key] = {
                "source_key": parent_key,
                "number": "",
                "name": parent_key.split(":")[-1],
                "qb_type": row["qb_type"],
                "account_type": row["account_type"],
                "subtype": row["subtype"],
                "parent_key": parent_key.rsplit(":", 1)[0] if ":" in parent_key else None,
                "is_active": True,
            }
    return list(by_key.values())


def _customer(record: dict, parties: list[dict], jobs: list[dict]) -> None:
    full = record.get("NAME") or ""
    if not full:
        return
    if ":" in full:
        customer_name, job_name = full.split(":", 1)
    else:
        customer_name, job_name = full, ""
    customer_key = f"cust:{customer_name}"
    if not any(row["source_key"] == customer_key for row in parties):
        parties.append(
            {
                "source_key": customer_key,
                "kind": "customer",
                "display_name": customer_name,
                "is_1099": False,
                "first_name": None,
                "last_name": None,
            }
        )
    if job_name:
        jobs.append(
            {
                "source_key": f"job:{full}",
                "number": job_name[:40],
                "name": job_name,
                "customer_key": customer_key,
            }
        )


def _vendor(record: dict) -> dict:
    name = record.get("NAME") or "Vendor"
    flag = record.get("1099") or record.get("1099ELIGIBLE") or ""
    return {
        "source_key": f"vend:{name}",
        "kind": "vendor",
        "display_name": name,
        "is_1099": _flag(flag),
        "first_name": None,
        "last_name": None,
    }


def _employee(record: dict) -> dict:
    name = record.get("NAME") or ""
    first = record.get("FIRSTNAME") or ""
    last = record.get("LASTNAME") or ""
    if not first and not last and name:
        parts = name.split(" ", 1)
        first = parts[0]
        last = parts[1] if len(parts) > 1 else ""
    return {
        "source_key": f"emp:{name or first}",
        "kind": "employee",
        "display_name": name or f"{first} {last}".strip(),
        "is_1099": False,
        "first_name": first or name or "Employee",
        "last_name": last or "",
    }

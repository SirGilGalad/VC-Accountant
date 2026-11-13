"""Version 1 routes. They call the same services as the desktop app."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import insert, select

from core.chart import account_id_by_number
from core.errors import LedgerError, RoleError
from core.packs import PACKS
from core.queries import trial_balance
from core.reports import balance_sheet_rows, profit_and_loss_rows
from core.schema import (
    accounts,
    bank_accounts,
    bank_statement_lines,
    bank_statements,
    cost_codes,
    jobs,
    parties,
    party_roles,
    reconciliations,
)
from core.services.accounts import create_account, list_accounts
from core.services.jobs import create_job, enter_time
from core.services.posting import add_draft, post_entry, reverse_entry
from core.services.preferences import get_preference, set_preference
from web.api.deps import scoped

router = APIRouter(prefix="/api/v1")

REVIEW = "Awaiting security review."


@router.get("/companies/{company_id}/accounts")
def get_accounts(bundle=Depends(scoped)):
    conn, company, _member = bundle
    rows = list_accounts(conn, int(company.id))
    return [
        {"id": row.id, "number": row.number, "name": row.name, "type": row.type, "active": bool(row.is_active)}
        for row in rows
    ]


@router.post("/companies/{company_id}/accounts")
def post_account(body: dict, bundle=Depends(scoped)):
    conn, company, member = bundle
    try:
        account_id = create_account(
            conn,
            company_id=int(company.id),
            member_id=int(member.id),
            number=str(body.get("number") or ""),
            name=str(body.get("name") or ""),
            account_type=str(body.get("type") or ""),
            parent_id=body.get("parent_id"),
        )
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": account_id}


@router.get("/companies/{company_id}/parties")
def get_parties(role: str = "customer", bundle=Depends(scoped)):
    conn, company, _member = bundle
    rows = conn.execute(
        select(parties.c.id, parties.c.display_name, party_roles.c.role)
        .select_from(parties.join(party_roles, party_roles.c.party_id == parties.c.id))
        .where(parties.c.company_id == int(company.id), party_roles.c.role == role)
        .order_by(parties.c.display_name)
    ).all()
    return [{"id": row.id, "display_name": row.display_name, "role": row.role} for row in rows]


@router.post("/companies/{company_id}/parties")
def post_party(body: dict, bundle=Depends(scoped)):
    conn, company, _member = bundle
    role = str(body.get("role") or "customer")
    if role not in {"customer", "vendor", "employee", "other"}:
        raise HTTPException(status_code=400, detail="Unknown role")
    party_id = int(
        conn.execute(
            insert(parties).values(
                company_id=int(company.id),
                display_name=str(body.get("display_name") or "").strip(),
                is_active=True,
            )
        ).inserted_primary_key[0]
    )
    conn.execute(insert(party_roles).values(party_id=party_id, role=role, is_1099=bool(body.get("is_1099"))))
    return {"id": party_id}


@router.get("/companies/{company_id}/jobs")
def get_jobs(bundle=Depends(scoped)):
    conn, company, _member = bundle
    rows = conn.execute(
        select(jobs.c.id, jobs.c.number, jobs.c.name, jobs.c.status).where(jobs.c.company_id == int(company.id))
    ).all()
    return [{"id": row.id, "number": row.number, "name": row.name, "status": row.status} for row in rows]


@router.post("/companies/{company_id}/jobs")
def post_job(body: dict, bundle=Depends(scoped)):
    conn, company, _member = bundle
    try:
        job_id = create_job(
            conn,
            company_id=int(company.id),
            customer_party_id=int(body["customer_party_id"]),
            number=str(body.get("number") or ""),
            name=str(body.get("name") or ""),
            contract_amount_cents=int(body.get("contract_amount_cents") or 0),
        )
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": job_id}


@router.get("/companies/{company_id}/cost-codes")
def get_cost_codes(bundle=Depends(scoped)):
    conn, company, _member = bundle
    rows = conn.execute(
        select(cost_codes.c.id, cost_codes.c.code, cost_codes.c.name).where(cost_codes.c.company_id == int(company.id))
    ).all()
    return [{"id": row.id, "code": row.code, "name": row.name} for row in rows]


@router.post("/companies/{company_id}/entries")
def post_entry_draft(body: dict, bundle=Depends(scoped)):
    conn, company, member = bundle
    try:
        entry_id = add_draft(
            conn,
            company_id=int(company.id),
            member_id=int(member.id),
            entry_date=date.fromisoformat(body["date"]),
            number=str(body.get("number") or ""),
            memo=body.get("memo"),
            source_type=str(body.get("source_type") or "manual"),
            lines=list(body.get("lines") or []),
        )
    except (LedgerError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": entry_id, "status": "draft"}


@router.post("/companies/{company_id}/entries/{entry_id}/post")
def post_existing(entry_id: int, bundle=Depends(scoped)):
    conn, _company, member = bundle
    try:
        post_entry(conn, entry_id, int(member.id))
    except RoleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": entry_id, "status": "posted"}


@router.post("/companies/{company_id}/entries/{entry_id}/reverse")
def reverse_existing(entry_id: int, body: dict | None = None, bundle=Depends(scoped)):
    conn, _company, member = bundle
    when = date.fromisoformat((body or {}).get("date") or date.today().isoformat())
    try:
        reversal_id = reverse_entry(conn, entry_id, int(member.id), when)
    except RoleError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": reversal_id, "status": "posted"}


@router.post("/companies/{company_id}/time")
def post_time(body: dict, bundle=Depends(scoped)):
    conn, company, _member = bundle
    try:
        time_id = enter_time(
            conn,
            company_id=int(company.id),
            employee_party_id=int(body["employee_party_id"]),
            job_id=int(body["job_id"]),
            cost_code_id=int(body["cost_code_id"]),
            work_date=date.fromisoformat(body["work_date"]),
            hours=str(body.get("hours") or ""),
        )
    except LedgerError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"id": time_id}


@router.get("/companies/{company_id}/bank-accounts")
def get_bank_accounts(bundle=Depends(scoped)):
    conn, company, _member = bundle
    rows = conn.execute(
        select(
            bank_accounts.c.id,
            bank_accounts.c.bank_name,
            bank_accounts.c.account_last4,
            accounts.c.number,
        )
        .select_from(bank_accounts.join(accounts, accounts.c.id == bank_accounts.c.account_id))
        .where(bank_accounts.c.company_id == int(company.id))
    ).all()
    return [
        {"id": row.id, "bank_name": row.bank_name, "account_last4": row.account_last4, "number": row.number}
        for row in rows
    ]


@router.post("/companies/{company_id}/bank-accounts")
def post_bank_account(body: dict, bundle=Depends(scoped)):
    _reject_full_numbers(body)
    conn, company, _member = bundle
    last4 = str(body.get("account_last4") or "")
    if last4 and (len(last4) != 4 or not last4.isdigit()):
        raise HTTPException(status_code=400, detail="Store only the last four digits")
    account_id = body.get("account_id")
    if account_id is None and body.get("number"):
        account_id = account_id_by_number(conn, int(company.id), str(body["number"]))
    row_id = int(
        conn.execute(
            insert(bank_accounts).values(
                company_id=int(company.id),
                account_id=int(account_id),
                bank_name=str(body.get("bank_name") or ""),
                account_last4=last4 or None,
            )
        ).inserted_primary_key[0]
    )
    return {"id": row_id}


@router.post("/companies/{company_id}/statements")
def post_statement(body: dict, bundle=Depends(scoped)):
    conn, _company, member = bundle
    statement_id = int(
        conn.execute(
            insert(bank_statements).values(
                bank_account_id=int(body["bank_account_id"]),
                period_start=date.fromisoformat(body["period_start"]),
                period_end=date.fromisoformat(body["period_end"]),
                beginning_balance_cents=int(body.get("beginning_balance_cents") or 0),
                ending_balance_cents=int(body.get("ending_balance_cents") or 0),
                entered_by_member_id=int(member.id),
            )
        ).inserted_primary_key[0]
    )
    for line in body.get("lines") or []:
        conn.execute(
            insert(bank_statement_lines).values(
                statement_id=statement_id,
                line_date=date.fromisoformat(line["line_date"]),
                description=str(line.get("description") or ""),
                amount_cents=int(line.get("amount_cents") or 0),
                entered_by_member_id=int(member.id),
            )
        )
    return {"id": statement_id}


@router.post("/companies/{company_id}/reconciliations")
def post_reconciliation(body: dict, bundle=Depends(scoped)):
    conn, _company, _member = bundle
    row_id = int(
        conn.execute(
            insert(reconciliations).values(
                bank_account_id=int(body["bank_account_id"]),
                statement_id=int(body["statement_id"]),
                status="open",
            )
        ).inserted_primary_key[0]
    )
    return {"id": row_id, "status": "open"}


@router.get("/companies/{company_id}/reports/{name}")
def get_report(name: str, bundle=Depends(scoped)):
    conn, company, _member = bundle
    company_id = int(company.id)
    if name == "trial-balance":
        rows = trial_balance(conn, company_id)
        return [{"number": row["number"], "name": row["name"], "net_cents": row["net_cents"]} for row in rows]
    if name == "balance-sheet":
        headers, rows = balance_sheet_rows(conn, company_id)
        return {"headers": headers, "rows": rows}
    if name == "profit-and-loss":
        headers, rows = profit_and_loss_rows(conn, company_id)
        return {"headers": headers, "rows": rows}
    raise HTTPException(status_code=404, detail="Unknown report")


@router.post("/companies/{company_id}/imports")
def post_import(bundle=Depends(scoped)):
    _ = bundle
    return JSONResponse(status_code=501, content={"detail": REVIEW})


@router.post("/companies/{company_id}/imports/{batch_id}/tie")
def post_tie(batch_id: int, bundle=Depends(scoped)):
    _ = (batch_id, bundle)
    return JSONResponse(status_code=501, content={"detail": REVIEW})


@router.post("/companies/{company_id}/imports/{batch_id}/accept")
def post_accept(batch_id: int, bundle=Depends(scoped)):
    _ = (batch_id, bundle)
    return JSONResponse(status_code=501, content={"detail": REVIEW})


@router.post("/companies/{company_id}/imports/{batch_id}/reject")
def post_reject(batch_id: int, bundle=Depends(scoped)):
    _ = (batch_id, bundle)
    return JSONResponse(status_code=501, content={"detail": REVIEW})


@router.get("/companies/{company_id}/preferences/{key}")
def get_pref(key: str, bundle=Depends(scoped)):
    conn, company, member = bundle
    return {"key": key, "value": get_preference(conn, int(company.id), int(member.id), key)}


@router.put("/companies/{company_id}/preferences/{key}")
def put_pref(key: str, body: dict, bundle=Depends(scoped)):
    conn, company, member = bundle
    set_preference(conn, int(company.id), int(member.id), key, body.get("value"))
    return {"key": key, "value": body.get("value")}


@router.get("/companies/{company_id}/packs/{pack_id}")
def get_pack(pack_id: str, bundle=Depends(scoped)):
    _ = bundle
    for pid, name, line in PACKS:
        if pid == pack_id:
            return {"id": pid, "name": name, "description": line}
    raise HTTPException(status_code=404, detail="Unknown pack")


def _reject_full_numbers(body: dict) -> None:
    for key in body:
        lowered = key.lower().replace("-", "_")
        if "routing" in lowered or lowered in {"account_number", "full_number"}:
            raise HTTPException(status_code=400, detail="Only the last four digits are stored")

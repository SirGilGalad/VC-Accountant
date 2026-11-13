# VC Accountant

VC Accountant is the financial-management application on Vantage Core Pro. One shared double-entry ledger serves every industry. Construction is first. Property management and RV resort holds come later, as account lists and screens on the same books.

Payroll and tax forms are prepared as drafts; nothing is filed. Bank reconciliation uses statement lines you enter. Payments are recorded in the books; no money is moved.

Property management here is for Utah and Arizona managers (units, rent, and a document index). Resort work is site and cabin holds. Online booking and point-of-sale systems are not connected.

Glen Canyon Construction LLC is the first live company to come across from exported lists, transaction detail, and a trial balance. Import stays staged until those figures tie to the cent. The company file itself is never committed.

## Run the desktop app

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

On Windows, `run_vca.bat` does the same thing from this folder. Company files use the `.vca` extension. An older `.vtg` file still opens: it is backed up beside the original and saved as `.vca`.

## Layout

```
core/            schema, services, queries, staged import
packs/           industry packs (later phases)
desktop/         PyQt6 windows
migrations/      Alembic revision for SQLite and Postgres
tests/           pytest
docs/            dependency notes and open security questions
main.py          launcher
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Postgres tests run when `VCA_TEST_PG_URL` is set. GitHub Actions runs them.

# Dependencies

| Package | Why it is here |
|---|---|
| PyQt6 | Desktop windows in `desktop/`. |
| SQLAlchemy | Tables in `core/schema.py` and every service query. |
| alembic | Migrations in `migrations/`, run when a company file opens. |
| platformdirs | User data directory for prefill and recent companies. Not the tax id. |

Dev-only: pytest, pytest-qt, hypothesis, ruff, and psycopg (Postgres tests when `VCA_TEST_PG_URL` is set).

pandas and ReportLab are not dependencies. Spreadsheet reading and PDF reports arrive when a feature uses them.

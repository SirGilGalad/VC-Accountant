# Dependencies

| Package | Why it is here |
|---|---|
| PyQt6 | Desktop windows in `desktop/`. |
| SQLAlchemy | Tables in `core/schema.py` and every service query. |
| alembic | Migrations in `migrations/`, run when a company file opens. |
| platformdirs | User data directory for prefill and recent companies. Not the tax id. |
| openpyxl | Reads .xlsx report exports in the importer. |
| reportlab | Writes PDF files for the reports. |

Dev-only: pytest, pytest-qt, hypothesis, ruff, and psycopg (Postgres tests when `VCA_TEST_PG_URL` is set).

pandas is not a dependency.

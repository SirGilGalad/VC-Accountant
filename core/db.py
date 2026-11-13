"""Engine helpers. Each desktop company file is its own SQLite database."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from core.schema import metadata
from core.triggers import apply_triggers


def sqlite_url(path: Path | str) -> str:
    return "sqlite:///" + str(Path(path).resolve())


def make_engine(url: str) -> Engine:
    engine = create_engine(url, future=True)
    if engine.dialect.name == "sqlite":

        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _record) -> None:  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


def install_schema(engine: Engine) -> None:
    """Create tables and triggers. Used by tests and by the Alembic migration."""
    with engine.begin() as conn:
        metadata.create_all(conn)
        apply_triggers(conn)


def upgrade_sqlite(path: Path | str) -> Engine:
    """Run Alembic to head on a company file, then return an engine."""
    from alembic import command
    from alembic.config import Config

    path = Path(path)
    url = sqlite_url(path)
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    return make_engine(url)


def table_names(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            rows = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            ).all()
            return {row[0] for row in rows}
        rows = conn.execute(
            text("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = 'public'")
        ).all()
        return {row[0] for row in rows}

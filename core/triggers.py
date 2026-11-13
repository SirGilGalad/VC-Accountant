"""Database posting guards. The service layer checks first; these still refuse a bypass."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

_SQLITE = [
    """
    CREATE TRIGGER IF NOT EXISTS journal_entries_balance_before_post
    BEFORE UPDATE OF status ON journal_entries
    WHEN NEW.status = 'posted'
    BEGIN
        SELECT RAISE(ABORT, 'unbalanced entry')
        WHERE (
            SELECT COUNT(*) FROM journal_lines WHERE entry_id = NEW.id
        ) < 2
        OR (
            SELECT COALESCE(SUM(debit_cents), 0) FROM journal_lines WHERE entry_id = NEW.id
        ) != (
            SELECT COALESCE(SUM(credit_cents), 0) FROM journal_lines WHERE entry_id = NEW.id
        );
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS journal_lines_immutable_ins
    BEFORE INSERT ON journal_lines
    WHEN (SELECT status FROM journal_entries WHERE id = NEW.entry_id) IN ('posted', 'void')
    BEGIN
        SELECT RAISE(ABORT, 'posted entry is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS journal_lines_immutable_upd
    BEFORE UPDATE ON journal_lines
    WHEN (SELECT status FROM journal_entries WHERE id = OLD.entry_id) IN ('posted', 'void')
    BEGIN
        SELECT RAISE(ABORT, 'posted entry is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS journal_lines_immutable_del
    BEFORE DELETE ON journal_lines
    WHEN (SELECT status FROM journal_entries WHERE id = OLD.entry_id) IN ('posted', 'void')
    BEGIN
        SELECT RAISE(ABORT, 'posted entry is immutable');
    END
    """,
]

_PG_FUNCTION = """
CREATE OR REPLACE FUNCTION vca_check_entry_balance() RETURNS trigger AS $$
DECLARE
    eid integer;
    n integer;
    d bigint;
    c bigint;
    st text;
BEGIN
    eid := COALESCE(NEW.id, OLD.id);
    SELECT status INTO st FROM journal_entries WHERE id = eid;
    IF st = 'posted' THEN
        SELECT COUNT(*), COALESCE(SUM(debit_cents), 0), COALESCE(SUM(credit_cents), 0)
          INTO n, d, c
          FROM journal_lines
         WHERE entry_id = eid;
        IF n < 2 OR d <> c THEN
            RAISE EXCEPTION 'unbalanced entry';
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql
"""

_PG_LINES_BALANCE = """
CREATE OR REPLACE FUNCTION vca_check_line_parent_balance() RETURNS trigger AS $$
DECLARE
    eid integer;
    n integer;
    d bigint;
    c bigint;
    st text;
BEGIN
    eid := COALESCE(NEW.entry_id, OLD.entry_id);
    SELECT status INTO st FROM journal_entries WHERE id = eid;
    IF st = 'posted' THEN
        SELECT COUNT(*), COALESCE(SUM(debit_cents), 0), COALESCE(SUM(credit_cents), 0)
          INTO n, d, c
          FROM journal_lines
         WHERE entry_id = eid;
        IF n < 2 OR d <> c THEN
            RAISE EXCEPTION 'unbalanced entry';
        END IF;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql
"""

_PG_LINES = """
CREATE OR REPLACE FUNCTION vca_lines_immutable() RETURNS trigger AS $$
DECLARE
    st text;
    eid integer;
BEGIN
    eid := COALESCE(OLD.entry_id, NEW.entry_id);
    SELECT status INTO st FROM journal_entries WHERE id = eid;
    IF st IN ('posted', 'void') THEN
        RAISE EXCEPTION 'posted entry is immutable';
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql
"""


def apply_triggers(conn: Connection) -> None:
    name = conn.dialect.name
    if name == "sqlite":
        for stmt in _SQLITE:
            conn.exec_driver_sql(stmt)
        return
    if name == "postgresql":
        conn.execute(text(_PG_FUNCTION))
        conn.execute(text(_PG_LINES_BALANCE))
        conn.execute(text(_PG_LINES))
        conn.execute(text("DROP TRIGGER IF EXISTS journal_entries_balance ON journal_entries"))
        conn.execute(
            text(
                """
                CREATE CONSTRAINT TRIGGER journal_entries_balance
                AFTER INSERT OR UPDATE ON journal_entries
                DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION vca_check_entry_balance()
                """
            )
        )
        conn.execute(text("DROP TRIGGER IF EXISTS journal_lines_balance ON journal_lines"))
        conn.execute(
            text(
                """
                CREATE CONSTRAINT TRIGGER journal_lines_balance
                AFTER INSERT OR UPDATE OR DELETE ON journal_lines
                DEFERRABLE INITIALLY DEFERRED
                FOR EACH ROW EXECUTE FUNCTION vca_check_line_parent_balance()
                """
            )
        )
        conn.execute(text("DROP TRIGGER IF EXISTS journal_lines_immutable ON journal_lines"))
        conn.execute(
            text(
                """
                CREATE TRIGGER journal_lines_immutable
                BEFORE INSERT OR UPDATE OR DELETE ON journal_lines
                FOR EACH ROW EXECUTE FUNCTION vca_lines_immutable()
                """
            )
        )
        return
    raise RuntimeError(f"No posting triggers for dialect {name}")

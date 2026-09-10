"""
SQLite history storage for WorkDiary Agent.

history.db is the application-owned history database.
This module is independent of LangGraph's checkpointer database.

DB_PATH is a module-level constant so tests can monkeypatch it:
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "test.db"))
"""
import sqlite3
from datetime import datetime
import uuid
from contextlib import contextmanager
from typing import Any, Generator

from ..paths import data_path
from ..time_utils import work_date

DB_PATH = str(data_path("history.db"))

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id TEXT,
    date TEXT NOT NULL,
    template_type TEXT,
    raw_input TEXT,
    polished TEXT,
    export_path TEXT,
    created_at TEXT NOT NULL
)
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the current schema and migrate databases from older releases."""
    conn.execute(_CREATE_TABLE_SQL)
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(reports)").fetchall()
    }
    if "report_id" not in existing:
        conn.execute("ALTER TABLE reports ADD COLUMN report_id TEXT")
    if "export_path" not in existing:
        conn.execute("ALTER TABLE reports ADD COLUMN export_path TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_reports_report_id "
        "ON reports(report_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_reports_template_date "
        "ON reports(template_type, date DESC)"
    )


@contextmanager
def _db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager: open connection, ensure schema, yield, close."""
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        _ensure_schema(conn)
        conn.commit()
        yield conn
    finally:
        conn.close()


def save_report(state: Any) -> str:
    """Insert one row into reports table from AgentState or plain dict.

    Called by save_node (workdiary_agent/nodes/save.py) after HITL approval.
    Uses state.get() so it works with both TypedDict and plain dict.
    """
    # Respect date passed in state (tests inject specific dates); fall back to today.
    date = state.get("date") or work_date(state.get("timezone"))
    report_id = state.get("report_id") or uuid.uuid4().hex
    created_at = datetime.now().astimezone().isoformat()
    raw_input = state.get("raw_input", "") or ""
    template_type = state.get("template_type", "") or ""
    polished = state.get("polished", "") or ""
    export_path = state.get("export_path", "") or ""

    with _db(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reports "
            "(report_id, date, template_type, raw_input, polished, export_path, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(report_id) DO UPDATE SET "
            "date=excluded.date, template_type=excluded.template_type, "
            "raw_input=excluded.raw_input, polished=excluded.polished, "
            "export_path=excluded.export_path, created_at=excluded.created_at",
            (
                report_id,
                date,
                template_type,
                raw_input,
                polished,
                export_path,
                created_at,
            ),
        )
        conn.commit()
    return report_id


def _report_filter_sql(
    *,
    query: str | None = None,
    template_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[str, list[Any]]:
    """Build a parameterized WHERE clause shared by list and count queries."""
    clauses: list[str] = []
    params: list[Any] = []
    if query and query.strip():
        pattern = f"%{query.strip()}%"
        clauses.append("(raw_input LIKE ? OR polished LIKE ?)")
        params.extend([pattern, pattern])
    if template_type:
        clauses.append("template_type = ?")
        params.append(template_type)
    if date_from:
        clauses.append("date >= ?")
        params.append(date_from)
    if date_to:
        clauses.append("date <= ?")
        params.append(date_to)
    return (" WHERE " + " AND ".join(clauses) if clauses else "", params)


def get_all_reports(
    *,
    query: str | None = None,
    template_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[dict]:
    """Return filtered reports ordered by date DESC (most recent first).

    Calling without arguments preserves the original all-records behavior.
    """
    if limit is not None and limit <= 0:
        raise ValueError("limit must be positive")
    if offset < 0:
        raise ValueError("offset must not be negative")

    where_sql, params = _report_filter_sql(
        query=query,
        template_type=template_type,
        date_from=date_from,
        date_to=date_to,
    )
    sql = (
        "SELECT id, report_id, date, template_type, raw_input, polished, "
        "export_path, created_at FROM reports"
        f"{where_sql} ORDER BY date DESC, created_at DESC, id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    elif offset:
        sql += " LIMIT -1 OFFSET ?"
        params.append(offset)

    with _db(DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]


def count_reports(
    *,
    query: str | None = None,
    template_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> int:
    """Return the number of reports matching the history filters."""
    where_sql, params = _report_filter_sql(
        query=query,
        template_type=template_type,
        date_from=date_from,
        date_to=date_to,
    )
    with _db(DB_PATH) as conn:
        row = conn.execute(
            f"SELECT COUNT(*) AS total FROM reports{where_sql}", params
        ).fetchone()
        return int(row["total"])


def get_report(report_id: str) -> dict | None:
    """Return one persisted report by its stable report id."""
    if not report_id:
        return None
    with _db(DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, report_id, date, template_type, raw_input, polished, "
            "export_path, created_at FROM reports WHERE report_id = ?",
            (report_id,),
        ).fetchone()
        return dict(row) if row else None

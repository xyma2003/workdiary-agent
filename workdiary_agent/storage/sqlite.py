"""
SQLite history storage for WorkDiary Agent.

history.db is the application-owned history database.
This module is independent of LangGraph's checkpointer database.

DB_PATH is a module-level constant so tests can monkeypatch it:
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "test.db"))
"""
import sqlite3
import datetime
from contextlib import contextmanager
from typing import Any, Generator

DB_PATH = "history.db"

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    template_type TEXT,
    raw_input TEXT,
    polished TEXT,
    created_at TEXT NOT NULL
)
"""


@contextmanager
def _db(db_path: str) -> Generator[sqlite3.Connection, None, None]:
    """Context manager: open connection, ensure schema, yield, close."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()
        yield conn
    finally:
        conn.close()


def save_report(state: Any) -> None:
    """Insert one row into reports table from AgentState or plain dict.

    Called by save_node (workdiary_agent/nodes/save.py) after HITL approval.
    Uses state.get() so it works with both TypedDict and plain dict.
    """
    date = datetime.date.today().isoformat()
    created_at = datetime.datetime.now().isoformat()
    raw_input = state.get("raw_input", "") or ""
    template_type = state.get("template_type", "") or ""
    polished = state.get("polished", "") or ""

    with _db(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO reports (date, template_type, raw_input, polished, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (date, template_type, raw_input, polished, created_at),
        )
        conn.commit()


def get_all_reports() -> list[dict]:
    """Return all reports ordered by date DESC (most recent first).

    Used by Phase 6 Streamlit history view (STORE-02).
    Returns empty list if no reports exist.
    """
    with _db(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, date, template_type, raw_input, polished, created_at "
            "FROM reports ORDER BY date DESC"
        ).fetchall()
        return [dict(row) for row in rows]

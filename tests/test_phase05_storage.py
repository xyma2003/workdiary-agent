"""
Phase 5 — Storage and Export RED test suite.

Tests cover all 4 success criteria from ROADMAP.md §Phase 5:
  - A completed HITL cycle produces a row in history.db
  - get_all_reports() returns rows ordered by date descending
  - save_markdown() produces exports/daily_report_YYYY-MM-DD.md
  - history.db and graph_state.db are separate files

All 7 tests FAIL (ImportError) in RED state until Plan 05-02 and 05-03
implement workdiary_agent/storage/sqlite.py and workdiary_agent/storage/export.py.

Run: conda run -n llm-data-pipeline pytest tests/test_phase05_storage.py -v
"""
import pytest
import workdiary_agent.storage.sqlite as sqlite_mod
import workdiary_agent.storage.export as export_mod


# ---------------------------------------------------------------------------
# SQLite history tests
# ---------------------------------------------------------------------------

def test_save_report_writes_row(tmp_path, monkeypatch):
    """save_report(state) writes exactly 1 row with all required fields populated."""
    import sqlite3
    db_path = str(tmp_path / "test_history.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)

    state = {
        "raw_input": "今天完成了登录模块",
        "template_type": "技术型",
        "polished": "完成登录模块开发，实现用户认证功能。",
    }
    sqlite_mod.save_report(state)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT date, template_type, raw_input, polished FROM reports"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][1] == "技术型"
    assert rows[0][2] == "今天完成了登录模块"
    assert rows[0][3] == "完成登录模块开发，实现用户认证功能。"
    assert rows[0][0]  # date non-empty


def test_save_report_created_at_set(tmp_path, monkeypatch):
    """The row's created_at field must be a non-empty ISO timestamp string."""
    import sqlite3
    db_path = str(tmp_path / "test_history_created_at.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)

    state = {
        "raw_input": "参加了产品评审会议",
        "template_type": "混合型",
        "polished": "参与产品方向评审，输出三条改进建议。",
    }
    sqlite_mod.save_report(state)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT created_at FROM reports").fetchall()
    conn.close()

    assert len(rows) == 1
    created_at = rows[0][0]
    assert created_at  # non-empty
    assert isinstance(created_at, str)
    # Basic ISO format check: contains 'T' or '-' separators
    assert len(created_at) >= 10


def test_get_all_reports_date_desc(tmp_path, monkeypatch):
    """get_all_reports() returns rows ordered by date DESC — most recent first."""
    db_path = str(tmp_path / "test_history_order.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)

    # Insert older row first
    sqlite_mod.save_report({
        "raw_input": "旧的工作记录",
        "template_type": "管理型",
        "polished": "管理日志条目一。",
        "date": "2026-04-20",
    })
    # Insert newer row second
    sqlite_mod.save_report({
        "raw_input": "新的工作记录",
        "template_type": "技术型",
        "polished": "技术日志条目二。",
        "date": "2026-04-24",
    })

    reports = sqlite_mod.get_all_reports()

    assert len(reports) == 2
    # First result should be the newer date
    assert reports[0]["date"] >= reports[1]["date"]
    assert reports[0]["date"] == "2026-04-24"


def test_get_all_reports_empty(tmp_path, monkeypatch):
    """With an empty DB, get_all_reports() returns an empty list — no exception raised."""
    db_path = str(tmp_path / "test_history_empty.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)

    # Ensure DB is initialized but empty
    # save_report creates the table; calling get_all_reports on a fresh path
    # must either initialize the table or return [] gracefully.
    reports = sqlite_mod.get_all_reports()

    assert reports == []
    assert isinstance(reports, list)


# ---------------------------------------------------------------------------
# Markdown export tests
# ---------------------------------------------------------------------------

def test_save_markdown_creates_file(tmp_path, monkeypatch):
    """save_markdown(text, date) creates exports/daily_report_YYYY-MM-DD.md containing the text."""
    import os
    exports_dir = str(tmp_path / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    export_mod.save_markdown("report text", "2026-04-24")

    expected = os.path.join(exports_dir, "daily_report_2026-04-24.md")
    assert os.path.exists(expected)
    assert "report text" in open(expected, encoding="utf-8").read()


def test_save_markdown_creates_dir(tmp_path, monkeypatch):
    """save_markdown() auto-creates the exports/ directory when it does not exist."""
    import os
    exports_dir = str(tmp_path / "nonexistent" / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    # Directory does not exist — function must not raise FileNotFoundError
    export_mod.save_markdown("另一份日报内容", "2026-04-25")

    expected = os.path.join(exports_dir, "daily_report_2026-04-25.md")
    assert os.path.exists(expected)


# ---------------------------------------------------------------------------
# DB separation test
# ---------------------------------------------------------------------------

def test_db_separation():
    """history.db and graph_state.db must be separate — storage module never references graph_state.db."""
    import inspect

    # DB_PATH must not point to the graph state DB
    assert sqlite_mod.DB_PATH != "graph_state.db"

    # No reference to graph_state.db anywhere in the sqlite storage module source
    src = inspect.getsource(sqlite_mod)
    assert "graph_state.db" not in src

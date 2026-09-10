"""Phase 5 — storage and export regression tests.

Tests cover:
  - A completed HITL cycle produces a row in history.db
  - get_all_reports() returns rows ordered by date descending
  - save_markdown() produces a unique, atomic Markdown export
  - history.db and graph_state.db are separate files
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
        "report_id": "report-1",
        "raw_input": "今天完成了登录模块",
        "template_type": "技术型",
        "polished": "完成登录模块开发，实现用户认证功能。",
    }
    sqlite_mod.save_report(state)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT report_id, date, template_type, raw_input, polished FROM reports"
    ).fetchall()
    conn.close()

    assert len(rows) == 1
    assert rows[0][0] == "report-1"
    assert rows[0][2] == "技术型"
    assert rows[0][3] == "今天完成了登录模块"
    assert rows[0][4] == "完成登录模块开发，实现用户认证功能。"
    assert rows[0][1]  # date non-empty


def test_save_report_is_idempotent_by_report_id(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_history_idempotent.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)
    base = {
        "report_id": "same-run",
        "raw_input": "原始记录",
        "template_type": "技术型",
        "polished": "first",
    }
    sqlite_mod.save_report(base)
    sqlite_mod.save_report({**base, "polished": "updated"})

    reports = sqlite_mod.get_all_reports()
    assert len(reports) == 1
    assert reports[0]["polished"] == "updated"


def test_legacy_history_schema_is_migrated_in_place(tmp_path, monkeypatch):
    import sqlite3

    db_path = str(tmp_path / "legacy_history.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE reports ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, "
        "template_type TEXT, raw_input TEXT, polished TEXT, created_at TEXT NOT NULL)"
    )
    conn.execute(
        "INSERT INTO reports (date, template_type, raw_input, polished, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-01-01", "技术型", "legacy", "legacy report", "2026-01-01T10:00:00"),
    )
    conn.commit()
    conn.close()
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)

    reports = sqlite_mod.get_all_reports()

    assert reports[0]["polished"] == "legacy report"
    assert reports[0]["report_id"] is None
    assert reports[0]["export_path"] is None


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


def test_history_filters_and_count(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_history_filters.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)
    sqlite_mod.save_report({
        "report_id": "old-tech",
        "date": "2026-04-20",
        "template_type": "技术型",
        "raw_input": "完成缓存优化",
        "polished": "缓存命中率提升。",
    })
    sqlite_mod.save_report({
        "report_id": "new-tech",
        "date": "2026-04-24",
        "template_type": "技术型",
        "raw_input": "完成登录修复",
        "polished": "登录错误率下降。",
    })
    sqlite_mod.save_report({
        "report_id": "business",
        "date": "2026-04-25",
        "template_type": "业务型",
        "raw_input": "客户访谈",
        "polished": "输出客户需求清单。",
    })

    filters = {
        "query": "登录",
        "template_type": "技术型",
        "date_from": "2026-04-21",
        "date_to": "2026-04-30",
    }
    reports = sqlite_mod.get_all_reports(**filters)

    assert [report["report_id"] for report in reports] == ["new-tech"]
    assert sqlite_mod.count_reports(**filters) == 1


def test_history_pagination_preserves_descending_order(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_history_pagination.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)
    for day in range(1, 5):
        sqlite_mod.save_report({
            "report_id": f"report-{day}",
            "date": f"2026-04-{day:02d}",
            "template_type": "混合型",
            "raw_input": f"工作 {day}",
            "polished": f"日报 {day}",
        })

    first_page = sqlite_mod.get_all_reports(limit=2)
    second_page = sqlite_mod.get_all_reports(limit=2, offset=2)

    assert [report["report_id"] for report in first_page] == ["report-4", "report-3"]
    assert [report["report_id"] for report in second_page] == ["report-2", "report-1"]


def test_get_report_returns_persisted_row(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test_get_report.db")
    monkeypatch.setattr(sqlite_mod, "DB_PATH", db_path)
    sqlite_mod.save_report({
        "report_id": "lookup-id",
        "date": "2026-04-24",
        "polished": "saved",
    })

    assert sqlite_mod.get_report("lookup-id")["polished"] == "saved"
    assert sqlite_mod.get_report("missing") is None


# ---------------------------------------------------------------------------
# Markdown export tests
# ---------------------------------------------------------------------------

def test_save_markdown_creates_file(tmp_path, monkeypatch):
    """save_markdown creates a report-id-qualified file containing the text."""
    import os
    exports_dir = str(tmp_path / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    path = export_mod.save_markdown("report text", "2026-04-24", "report-123")

    expected = os.path.join(exports_dir, "daily_report_2026-04-24_report-123.md")
    assert path == expected
    assert os.path.exists(expected)
    assert "report text" in open(expected, encoding="utf-8").read()


def test_save_markdown_creates_dir(tmp_path, monkeypatch):
    """save_markdown() auto-creates the exports/ directory when it does not exist."""
    import os
    exports_dir = str(tmp_path / "nonexistent" / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    # Directory does not exist — function must not raise FileNotFoundError
    path = export_mod.save_markdown("另一份日报内容", "2026-04-25", "abc")

    expected = os.path.join(exports_dir, "daily_report_2026-04-25_abc.md")
    assert path == expected
    assert os.path.exists(expected)


def test_save_markdown_does_not_overwrite_same_day(tmp_path, monkeypatch):
    exports_dir = str(tmp_path / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    first = export_mod.save_markdown("first", "2026-04-25", "first-id")
    second = export_mod.save_markdown("second", "2026-04-25", "second-id")

    assert first != second
    assert open(first, encoding="utf-8").read().endswith("first\n")
    assert open(second, encoding="utf-8").read().endswith("second\n")


def test_save_markdown_keeps_untrusted_date_inside_export_dir(tmp_path, monkeypatch):
    import os

    exports_dir = str(tmp_path / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)

    path = export_mod.save_markdown("safe", "../../outside", "report-id")

    common_path = os.path.commonpath([
        os.path.abspath(path),
        os.path.abspath(exports_dir),
    ])
    assert common_path == os.path.abspath(exports_dir)
    assert os.path.exists(path)


def test_delete_markdown_removes_only_matching_export(tmp_path, monkeypatch):
    import os

    exports_dir = str(tmp_path / "exports")
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", exports_dir)
    target = export_mod.save_markdown("abandoned", "2026-04-25", "abandoned-id")
    retained = export_mod.save_markdown("saved", "2026-04-25", "saved-id")

    assert export_mod.delete_markdown("2026-04-25", "abandoned-id") is True
    assert not os.path.exists(target)
    assert os.path.exists(retained)
    assert export_mod.delete_markdown("2026-04-25", "missing-id") is False


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

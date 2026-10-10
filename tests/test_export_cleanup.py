"""Durable deletion recovery, transaction safety, and managed-export boundaries."""

from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

from workdiary_agent.report_service import delete_saved_report, retry_export_cleanup
import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
    return tmp_path


def _create_report(report_id="cleanup-report", *, export_path=None):
    if export_path is None:
        export_path = export_mod.save_markdown("待删除的日报", "2026-04-24", report_id)
    sqlite_mod.save_report({
        "report_id": report_id,
        "date": "2026-04-24",
        "template_type": "技术型",
        "raw_input": "验收输入",
        "polished": "待删除的日报",
        "export_path": str(export_path),
    })
    return sqlite_mod.get_report(report_id)


def _failed_delete(record):
    with patch.object(export_mod.os, "remove", side_effect=PermissionError("file locked")):
        result = delete_saved_report(record["id"])
    assert result.cleanup_status == "pending"
    assert result.cleanup_id is not None
    return result


def _install_trigger(sql):
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute(sql)


def test_failed_export_delete_survives_new_connections_and_repeated_retries(isolated_storage):
    record = _create_report()

    deleted = _failed_delete(record)

    assert deleted.record == record
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert Path(record["export_path"]).exists()
    # Read through a newly opened SQLite connection: the task must not live only
    # in a service object or a Streamlit session that disappears on refresh.
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        persisted = conn.execute(
            "SELECT record_id, report_date, export_path, created_at, last_error "
            "FROM export_cleanup WHERE id = ?", (deleted.cleanup_id,),
        ).fetchone()
    assert persisted[:3] == (record["id"], record["date"], record["export_path"])
    assert persisted[3]
    assert "file locked" in persisted[4]

    with patch.object(export_mod.os, "remove", side_effect=PermissionError("still locked")):
        assert retry_export_cleanup(deleted.cleanup_id) == "pending"
        assert retry_export_cleanup(deleted.cleanup_id) == "pending"

    pending = sqlite_mod.list_export_cleanups()
    assert len(pending) == 1
    assert pending[0]["id"] == deleted.cleanup_id
    assert "still locked" in pending[0]["last_error"]
    assert delete_saved_report(record["id"]) is None
    assert len(sqlite_mod.list_export_cleanups()) == 1

    assert retry_export_cleanup(deleted.cleanup_id) == "complete"
    assert not Path(record["export_path"]).exists()
    assert sqlite_mod.list_export_cleanups() == []
    assert retry_export_cleanup(deleted.cleanup_id) == "not_found"


@pytest.mark.parametrize("during_retry", [False, True])
def test_already_missing_export_completes_cleanup(isolated_storage, during_retry):
    record = _create_report()
    pending = _failed_delete(record) if during_retry else None
    Path(record["export_path"]).unlink()

    if during_retry:
        assert retry_export_cleanup(pending.cleanup_id) == "complete"
    else:
        assert delete_saved_report(record["id"]).cleanup_status == "complete"

    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert sqlite_mod.list_export_cleanups() == []


@pytest.mark.parametrize("target_inside_exports", [False, True])
@pytest.mark.parametrize("during_retry", [False, True])
def test_symlink_export_is_preserved_and_never_follows_its_target(
    isolated_storage, target_inside_exports, during_retry,
):
    record = _create_report()
    pending = _failed_delete(record) if during_retry else None
    target_dir = Path(export_mod.EXPORTS_DIR) if target_inside_exports else isolated_storage
    target = target_dir / "keep.md"
    target.write_text("another file that must remain", encoding="utf-8")
    export = Path(record["export_path"])
    export.unlink()
    export.symlink_to(target)

    if during_retry:
        assert retry_export_cleanup(pending.cleanup_id) == "unmanaged"
    else:
        assert delete_saved_report(record["id"]).cleanup_status == "unmanaged"

    assert export.is_symlink()
    assert target.read_text(encoding="utf-8") == "another file that must remain"
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert sqlite_mod.list_export_cleanups() == []


def test_symlink_parent_cannot_redirect_cleanup_outside_exports(isolated_storage):
    export_dir = Path(export_mod.EXPORTS_DIR)
    export_dir.mkdir()
    outside_dir = isolated_storage / "unmanaged"
    outside_dir.mkdir()
    target = outside_dir / "keep.md"
    target.write_text("keep", encoding="utf-8")
    linked_dir = export_dir / "linked"
    linked_dir.symlink_to(outside_dir, target_is_directory=True)
    record = _create_report(export_path=linked_dir / target.name)

    assert delete_saved_report(record["id"]).cleanup_status == "unmanaged"

    assert target.read_text(encoding="utf-8") == "keep"
    assert linked_dir.is_symlink()
    assert sqlite_mod.list_export_cleanups() == []


def test_parent_traversal_after_symlink_cannot_hide_an_outside_target(isolated_storage):
    export_dir = Path(export_mod.EXPORTS_DIR)
    export_dir.mkdir()
    outside_dir = isolated_storage / "unmanaged"
    (outside_dir / "child").mkdir(parents=True)
    target = outside_dir / "keep.md"
    target.write_text("outside file", encoding="utf-8")
    (export_dir / "link").symlink_to(outside_dir / "child", target_is_directory=True)
    # abspath collapses link/.. lexically, while the filesystem traverses the
    # symlink first. Checking only the normalized spelling would delete target.
    record = _create_report(export_path=str(export_dir / "link") + "/../keep.md")

    assert delete_saved_report(record["id"]).cleanup_status == "unmanaged"

    assert target.read_text(encoding="utf-8") == "outside file"
    assert sqlite_mod.list_export_cleanups() == []


def test_retry_does_not_follow_replaced_export_root(isolated_storage):
    record = _create_report()
    pending = _failed_delete(record)
    export_dir = Path(export_mod.EXPORTS_DIR)
    original_dir = isolated_storage / "original-exports"
    export_dir.rename(original_dir)
    outside_dir = isolated_storage / "unmanaged"
    outside_dir.mkdir()
    target = outside_dir / Path(record["export_path"]).name
    target.write_text("outside file with the same name", encoding="utf-8")
    export_dir.symlink_to(outside_dir, target_is_directory=True)

    assert retry_export_cleanup(pending.cleanup_id) == "unmanaged"

    assert target.read_text(encoding="utf-8") == "outside file with the same name"
    assert (original_dir / target.name).exists()
    assert export_dir.is_symlink()
    assert sqlite_mod.list_export_cleanups() == []


@pytest.mark.parametrize("during_retry", [False, True])
def test_export_still_referenced_by_another_report_is_preserved(
    isolated_storage, during_retry,
):
    record = _create_report()
    pending = _failed_delete(record) if during_retry else None
    export = Path(record["export_path"])
    # A different spelling of the same path must still count as a reference.
    alias = str(export.parent) + "/./" + export.name
    shared = _create_report("other-report", export_path=alias)

    if during_retry:
        assert retry_export_cleanup(pending.cleanup_id) == "in_use"
    else:
        assert delete_saved_report(record["id"]).cleanup_status == "in_use"

    assert export.exists()
    assert sqlite_mod.get_report_by_id(shared["id"]) == shared
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert sqlite_mod.list_export_cleanups() == []


@pytest.mark.parametrize("table,event", [("reports", "DELETE"), ("export_cleanup", "INSERT")])
def test_report_delete_and_cleanup_enqueue_roll_back_together(
    isolated_storage, table, event,
):
    record = _create_report()
    sqlite_mod.list_export_cleanups()
    _install_trigger(
        f"CREATE TRIGGER abort_delete BEFORE {event} ON {table} "
        "BEGIN SELECT RAISE(ABORT, 'injected transaction failure'); END"
    )

    with pytest.raises(sqlite3.IntegrityError, match="injected transaction failure"):
        delete_saved_report(record["id"])

    assert sqlite_mod.get_report_by_id(record["id"]) == record
    assert Path(record["export_path"]).exists()
    assert sqlite_mod.list_export_cleanups() == []


def test_queue_clear_failure_keeps_recoverable_task_after_file_is_removed(isolated_storage):
    record = _create_report()
    sqlite_mod.list_export_cleanups()
    _install_trigger(
        "CREATE TRIGGER block_queue_clear BEFORE DELETE ON export_cleanup "
        "BEGIN SELECT RAISE(ABORT, 'queue is temporarily locked'); END"
    )

    deleted = delete_saved_report(record["id"])

    assert deleted.cleanup_status == "pending"
    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert not Path(record["export_path"]).exists()
    assert [item["id"] for item in sqlite_mod.list_export_cleanups()] == [deleted.cleanup_id]

    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute("DROP TRIGGER block_queue_clear")
    assert retry_export_cleanup(deleted.cleanup_id) == "complete"
    assert sqlite_mod.list_export_cleanups() == []


def test_error_metadata_write_failure_does_not_lose_pending_cleanup(isolated_storage):
    record = _create_report()
    sqlite_mod.list_export_cleanups()
    _install_trigger(
        "CREATE TRIGGER block_queue_error BEFORE UPDATE ON export_cleanup "
        "BEGIN SELECT RAISE(ABORT, 'queue metadata unavailable'); END"
    )

    deleted = _failed_delete(record)

    assert sqlite_mod.get_report_by_id(record["id"]) is None
    assert Path(record["export_path"]).exists()
    assert [item["id"] for item in sqlite_mod.list_export_cleanups()] == [deleted.cleanup_id]
    assert retry_export_cleanup(deleted.cleanup_id) == "complete"


def test_cleanup_schema_migration_preserves_legacy_history(isolated_storage):
    with sqlite3.connect(sqlite_mod.DB_PATH) as conn:
        conn.execute(
            "CREATE TABLE reports ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT NOT NULL, "
            "template_type TEXT, raw_input TEXT, polished TEXT, created_at TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO reports (date, template_type, raw_input, polished, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2026-01-01", "技术型", "legacy input", "legacy report", "2026-01-01T10:00:00"),
        )

    assert sqlite_mod.list_export_cleanups() == []
    migrated = sqlite_mod.get_report_by_id(1)
    assert migrated["raw_input"] == "legacy input"
    assert migrated["polished"] == "legacy report"
    assert migrated["created_at"] == "2026-01-01T10:00:00"
    assert migrated["report_id"] is None
    assert migrated["export_path"] is None

    # A migrated database is usable for the new workflow without clearing its
    # existing history or creating a separate, unrelated database.
    record = _create_report()
    deleted = _failed_delete(record)
    assert retry_export_cleanup(deleted.cleanup_id) == "complete"
    assert sqlite_mod.get_report_by_id(1) == migrated

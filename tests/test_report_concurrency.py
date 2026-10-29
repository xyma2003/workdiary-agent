"""Stale editors and independent processes must not split a report's two stores."""

import multiprocessing
from pathlib import Path
import sqlite3
from unittest.mock import patch

import pytest

import workdiary_agent.report_service as service
import workdiary_agent.storage.export as exports
import workdiary_agent.storage.sqlite as storage


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(exports, "EXPORTS_DIR", str(tmp_path / "exports"))
    return tmp_path


def _create_report(report_id="concurrent-report", *, export_path=None):
    if export_path is None:
        export_path = exports.save_markdown("original", "2026-10-28", report_id)
    storage.save_report({
        "report_id": report_id, "date": "2026-10-28", "template_type": "技术型",
        "raw_input": "synthetic notes", "polished": "original", "export_path": str(export_path),
    })
    return storage.get_report(report_id)


def _edit(record, text="updated", **kwargs):
    return service.update_saved_report(
        record["id"], date=kwargs.pop("date", record["date"]), template_type="技术型",
        raw_input="synthetic notes", polished=text, **kwargs,
    )


def _assert_consistent(record_id, text):
    record = storage.get_report_by_id(record_id)
    assert record["polished"] == text
    assert Path(record["export_path"]).read_text(encoding="utf-8") == (
        f"# 日报 {record['date']}\n\n{text}\n"
    )


def test_stale_editor_is_rejected_before_touching_files(isolated_storage):
    original = _create_report()
    _edit(original, "saved in another page", expected_record=original)
    with patch.object(service, "save_markdown") as write:
        with pytest.raises(service.ReportConflictError, match="其他页面"):
            _edit(original, "stale edits", expected_record=original)
        write.assert_not_called()
    _assert_consistent(original["id"], "saved in another page")


@pytest.mark.parametrize("field,value", [
    ("updated_at", None), ("date", "2026-10-27"), ("polished", "stale"),
    ("raw_input", "stale notes"), ("template_type", "混合型"),
    ("report_id", "different-report"), ("export_path", "different.md"),
])
def test_version_compares_fields_not_only_timestamp(isolated_storage, field, value):
    original = _create_report()
    expected = {**original, field: value}
    with pytest.raises(service.ReportConflictError):
        _edit(original, expected_record=expected)
    _assert_consistent(original["id"], "original")


def test_legacy_null_timestamp_can_be_saved_then_detects_stale_edit(isolated_storage):
    original = _create_report()
    with sqlite3.connect(storage.DB_PATH) as conn:
        conn.execute("UPDATE reports SET updated_at = NULL WHERE id = ?", (original["id"],))
    original = storage.get_report_by_id(original["id"])
    assert original["updated_at"] is None
    _edit(original, expected_record=original)
    with pytest.raises(service.ReportConflictError):
        _edit(original, "stale", expected_record=original)
    _assert_consistent(original["id"], "updated")


@pytest.mark.parametrize("new_date", ["2026-10-28", "2026-10-29"])
def test_commit_failure_restores_original_files_and_row(isolated_storage, monkeypatch, new_date):
    original = _create_report()
    original_bytes = Path(original["export_path"]).read_bytes()
    real_connect = sqlite3.connect

    class FailedCommit(sqlite3.Connection):
        def commit(self):
            if self.in_transaction:
                changed = self.execute(
                    "SELECT polished FROM reports WHERE id = ?", (original["id"],),
                ).fetchone()
                if changed and changed[0] == "must roll back":
                    raise sqlite3.OperationalError("synthetic commit failure")
            return super().commit()

    def connect(*args, **kwargs):
        return real_connect(*args, **kwargs, factory=FailedCommit)

    monkeypatch.setattr(storage.sqlite3, "connect", connect)
    with pytest.raises(sqlite3.OperationalError, match="synthetic commit failure"):
        _edit(original, "must roll back", date=new_date, expected_record=original)
    assert storage.get_report_by_id(original["id"]) == original
    assert Path(original["export_path"]).read_bytes() == original_bytes
    assert list(Path(exports.EXPORTS_DIR).iterdir()) == [Path(original["export_path"])]


@pytest.mark.parametrize("failed_date", ["2026-10-28", "2026-10-29"])
@pytest.mark.parametrize("following_action", ["none", "save", "move", "delete"])
def test_real_sqlite_interrupt_relocks_before_compensation(
    isolated_storage, monkeypatch, failed_date, following_action,
):
    original = _create_report()
    original_bytes = Path(original["export_path"]).read_bytes()
    real_connect = sqlite3.connect
    interrupt_next_update = [True]
    interrupted_states = []
    relocked = []

    def concurrent_action():
        if following_action == "save":
            _edit(original, "later successful edit", expected_record=original)
        elif following_action == "move":
            _edit(original, "later successful edit", date="2026-10-30", expected_record=original)
        elif following_action == "delete":
            assert service.delete_saved_report(original["id"]).cleanup_status == "complete"

    class InterruptedUpdate(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql == "BEGIN IMMEDIATE" and getattr(self, "_auto_rolled_back", False):
                self._auto_rolled_back = False
                # A second connection completes during the actual unlocked
                # interval, immediately before the failed editor reacquires it.
                concurrent_action()
                result = super().execute(sql, parameters)
                relocked.append(self.in_transaction)
                return result
            if sql.startswith("UPDATE reports SET") and interrupt_next_update[0]:
                interrupt_next_update[0] = False
                self.set_progress_handler(lambda: 1, 1)
                try:
                    return super().execute(sql, parameters)
                except sqlite3.OperationalError as exc:
                    # Python 3.10 does not expose sqlite_errorcode on exceptions.
                    interrupted_states.append((str(exc), self.in_transaction))
                    self._auto_rolled_back = True
                    raise
                finally:
                    self.set_progress_handler(None, 0)
            return super().execute(sql, parameters)

    def connect(*args, **kwargs):
        return real_connect(*args, **kwargs, factory=InterruptedUpdate)

    monkeypatch.setattr(storage.sqlite3, "connect", connect)
    with pytest.raises(sqlite3.OperationalError, match="interrupted"):
        _edit(original, "failed edit", date=failed_date, expected_record=original)
    assert interrupted_states == [("interrupted", False)]
    assert relocked == [True]
    if following_action == "none":
        assert storage.get_report_by_id(original["id"]) == original
        assert Path(original["export_path"]).read_bytes() == original_bytes
        assert list(Path(exports.EXPORTS_DIR).iterdir()) == [Path(original["export_path"])]
    elif following_action == "delete":
        assert storage.get_report_by_id(original["id"]) is None
        assert not Path(original["export_path"]).exists()
    else:
        _assert_consistent(original["id"], "later successful edit")
        latest = storage.get_report_by_id(original["id"])
        assert latest["date"] == ("2026-10-30" if following_action == "move" else original["date"])
        if following_action == "move":
            assert not Path(original["export_path"]).exists()


def test_foreign_destination_is_not_overwritten_or_removed(isolated_storage):
    original = _create_report()
    other = Path(exports.export_path_for_report("2026-10-29", original["report_id"]))
    other.write_text("unrelated existing file", encoding="utf-8")
    with pytest.raises(ValueError, match="目标导出文件已存在"):
        _edit(original, date="2026-10-29")
    assert other.read_text(encoding="utf-8") == "unrelated existing file"
    _assert_consistent(original["id"], "original")


def test_shared_export_cannot_be_overwritten_and_is_preserved_when_moving(isolated_storage):
    original = _create_report()
    _create_report("second-report", export_path=original["export_path"])
    with pytest.raises(ValueError, match="其他日报"):
        _edit(original)
    _edit(original, date="2026-10-29")
    assert "original" in Path(original["export_path"]).read_text(encoding="utf-8")
    _assert_consistent(original["id"], "updated")


def _process_edit(db_path, export_dir, record, text, expected, started, written, release, done, queue, fail):
    """Use spawn, so only SQLite coordinates these independently loaded modules."""
    storage.DB_PATH = db_path
    exports.EXPORTS_DIR = export_dir
    real_save = service.save_markdown
    real_update = service.update_report_by_id

    def save(*args, **kwargs):
        result = real_save(*args, **kwargs)
        if written is not None:
            written.set()
            if not release.wait(10):
                raise RuntimeError("test did not release the first writer")
        return result

    def update(*args, **kwargs):
        if fail:
            raise RuntimeError("synthetic update failure")
        return real_update(*args, **kwargs)

    started.set()
    try:
        with patch.object(service, "save_markdown", side_effect=save), patch.object(
            service, "update_report_by_id", side_effect=update,
        ):
            _edit(record, text, expected_record=expected)
        queue.put((text, "saved"))
    except Exception as exc:
        queue.put((text, type(exc).__name__))
    finally:
        done.set()


def _process_delete_or_cleanup(db_path, export_dir, target, action, started, done, queue):
    storage.DB_PATH = db_path
    exports.EXPORTS_DIR = export_dir
    started.set()
    try:
        if action == "delete":
            result = service.delete_saved_report(target)
            queue.put((action, result.cleanup_status))
        else:
            queue.put((action, service.retry_export_cleanup(target)))
    except Exception as exc:
        queue.put((action, type(exc).__name__))
    finally:
        done.set()


@pytest.mark.parametrize("use_expected,first_fails", [(False, False), (True, False), (True, True)])
def test_independent_processes_serialize_file_and_database_updates(
    isolated_storage, use_expected, first_fails,
):
    original = _create_report()
    context = multiprocessing.get_context("spawn")
    a_started, a_written, release, a_done, b_started, b_done = [context.Event() for _ in range(6)]
    queue = context.Queue()
    expected = original if use_expected else None
    common = (storage.DB_PATH, exports.EXPORTS_DIR, original)
    first = context.Process(target=_process_edit, args=(
        *common, "A", expected, a_started, a_written, release, a_done, queue, first_fails,
    ))
    second = context.Process(target=_process_edit, args=(
        *common, "B", expected, b_started, None, None, b_done, queue, False,
    ))
    processes = []
    try:
        first.start()
        processes.append(first)
        assert a_written.wait(10), "first process did not write its export"
        second.start()
        processes.append(second)
        assert b_started.wait(10)
        assert not b_done.wait(0.2), "second writer escaped the database write lock"
        release.set()
        for process in processes:
            process.join(10)
            assert not process.is_alive()
            assert process.exitcode == 0
        outcomes = dict(queue.get(timeout=2) for _ in processes)
        if first_fails:
            assert outcomes == {"A": "RuntimeError", "B": "saved"}
            _assert_consistent(original["id"], "B")
        elif use_expected:
            assert outcomes == {"A": "saved", "B": "ReportConflictError"}
            _assert_consistent(original["id"], "A")
        else:
            assert outcomes == {"A": "saved", "B": "saved"}
            _assert_consistent(original["id"], "B")
    finally:
        release.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        queue.close()
        queue.join_thread()


@pytest.mark.parametrize("action", ["delete", "cleanup"])
def test_delete_and_cleanup_wait_for_an_independent_editor(isolated_storage, action):
    original = _create_report()
    target = original["id"]
    if action == "cleanup":
        # An older durable task still points at an export now owned by this row.
        with sqlite3.connect(storage.DB_PATH) as conn:
            cursor = conn.execute(
                "INSERT INTO export_cleanup (record_id, report_date, export_path, created_at) "
                "VALUES (?, ?, ?, ?)",
                (999, original["date"], original["export_path"], "2026-10-28"),
            )
            target = cursor.lastrowid
    context = multiprocessing.get_context("spawn")
    a_started, a_written, release, a_done, b_started, b_done = [context.Event() for _ in range(6)]
    queue = context.Queue()
    first = context.Process(target=_process_edit, args=(
        storage.DB_PATH, exports.EXPORTS_DIR, original, "A", original,
        a_started, a_written, release, a_done, queue, False,
    ))
    second = context.Process(target=_process_delete_or_cleanup, args=(
        storage.DB_PATH, exports.EXPORTS_DIR, target, action, b_started, b_done, queue,
    ))
    processes = []
    try:
        first.start()
        processes.append(first)
        assert a_written.wait(10)
        second.start()
        processes.append(second)
        assert b_started.wait(10)
        assert not b_done.wait(0.2), "delete/cleanup escaped the editor's write lock"
        release.set()
        for process in processes:
            process.join(10)
            assert not process.is_alive()
            assert process.exitcode == 0
        outcomes = dict(queue.get(timeout=2) for _ in processes)
        if action == "delete":
            assert outcomes == {"A": "saved", "delete": "complete"}
            assert storage.get_report_by_id(original["id"]) is None
            assert not Path(original["export_path"]).exists()
        else:
            assert outcomes == {"A": "saved", "cleanup": "in_use"}
            _assert_consistent(original["id"], "A")
        assert storage.list_export_cleanups() == []
    finally:
        release.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        queue.close()
        queue.join_thread()

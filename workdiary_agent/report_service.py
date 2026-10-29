"""Coordinated CRUD operations for saved reports and their exports."""

from __future__ import annotations

from datetime import date as Date
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import uuid

from .redaction import redact_secrets
from .storage.export import (
    delete_export_path, export_path_for_report, is_managed_export_path, save_markdown,
)
from .storage.sqlite import (
    delete_report_with_cleanup,
    export_cleanup_transaction,
    get_report_by_id,
    report_edit_transaction,
    update_report_by_id,
)


TEMPLATE_TYPES = ("技术型", "业务型", "混合型")
logger = logging.getLogger(__name__)


class ReportConflictError(ValueError):
    """The report changed after the editor loaded its original record."""


_EDIT_VERSION_FIELDS = (
    "id", "report_id", "date", "template_type", "raw_input", "polished",
    "export_path", "created_at", "updated_at", "source_snapshot", "source_snapshot_status",
)


def _validate_update(
    *,
    date: str,
    template_type: str,
    raw_input: str,
    polished: str,
) -> None:
    try:
        parsed_date = Date.fromisoformat(date)
    except (TypeError, ValueError) as exc:
        raise ValueError("日期必须是有效的 YYYY-MM-DD 格式") from exc
    if parsed_date.isoformat() != date:
        raise ValueError("日期必须是有效的 YYYY-MM-DD 格式")
    if template_type not in TEMPLATE_TYPES:
        raise ValueError("模板类型无效")
    if not raw_input.strip():
        raise ValueError("原始输入不能为空")
    if not polished.strip():
        raise ValueError("日报内容不能为空")
    if "[REDACTED_SECRET]" in polished or redact_secrets(polished) != polished:
        raise ValueError("日报内容可能包含凭证或脱敏标记，请先移除")


def _rollback_exports(originals: dict[str, bytes | None]) -> None:
    """Restore only files this edit changed, before releasing the write lock."""
    for path, content in originals.items():
        try:
            if not is_managed_export_path(path):
                raise OSError("导出路径已改变，无法安全恢复")
            if content is None:
                delete_export_path(path)
                continue
            temporary = f"{path}.{uuid.uuid4().hex}.tmp"
            try:
                Path(temporary).write_bytes(content)
                os.replace(temporary, path)
            finally:
                if os.path.isfile(temporary):
                    os.remove(temporary)
        except OSError:
            logger.exception("Failed to roll back an edited report export")


def _export_used_by_other_report(conn, path: str, record_id: int) -> bool:
    return any(
        os.path.realpath(row["export_path"]) == os.path.realpath(path)
        for row in conn.execute(
            "SELECT export_path FROM reports WHERE id != ? "
            "AND export_path IS NOT NULL AND export_path != ''", (record_id,),
        )
    )


def _compensate_failed_edit(conn, old: dict, originals: dict[str, bytes | None]) -> None:
    """Never let compensation from an auto-rolled-back edit undo a later save."""
    if not originals:
        return
    if not conn.in_transaction:
        # SQLITE_INTERRUPT and some I/O errors can roll back automatically and
        # release the write lock before control reaches this exception handler.
        # Another process may already have saved or deleted the same report.
        try:
            conn.execute("BEGIN IMMEDIATE")
            current = get_report_by_id(old["id"], connection=conn)
            if current is None or any(
                current.get(field) != old.get(field)
                for field in _EDIT_VERSION_FIELDS
            ):
                logger.warning("Skipped stale export compensation for report %s", old["id"])
                return
            if not conn.in_transaction:
                raise RuntimeError("Lost the write lock while checking export compensation")
            originals = {
                path: content for path, content in originals.items()
                if not _export_used_by_other_report(conn, path, old["id"])
            }
        except Exception:
            # Preserve the original save error. Without a verified lock and
            # record version, leaving a file untouched is safer than restoring
            # stale bytes or removing a file now owned by another report.
            logger.exception("Could not safely compensate report %s", old["id"])
            return
    _rollback_exports(originals)


def update_saved_report(
    record_id: int,
    *,
    date: str,
    template_type: str,
    raw_input: str,
    polished: str,
    expected_record: dict | None = None,
) -> dict:
    """Serialize saves and reject stale editors before changing any file.

    SQLite protects cooperating processes, including deletion and cleanup. File
    compensation also runs under that lock if an update or commit raises. After
    SQLite auto-rollback, compensation reacquires the lock and verifies the old
    version; a newer edit/deletion is preserved. This is not an atomic
    filesystem/database transaction across a process crash.
    """
    _validate_update(
        date=date,
        template_type=template_type,
        raw_input=raw_input,
        polished=polished,
    )
    with report_edit_transaction(record_id) as (conn, old):
        if old is None:
            raise LookupError("日报记录不存在或已被删除")
        if expected_record is not None and any(
            expected_record.get(field) != old.get(field)
            for field in _EDIT_VERSION_FIELDS
        ):
            raise ReportConflictError("这篇日报已在其他页面更新，请先查看最新内容，再重新编辑。")

        report_id = old.get("report_id") or uuid.uuid4().hex
        new_export_path = export_path_for_report(date, report_id)
        old_export_path = old.get("export_path") or ""
        same_path = bool(old_export_path) and (
            os.path.realpath(old_export_path) == os.path.realpath(new_export_path)
        )
        if not is_managed_export_path(new_export_path):
            raise ValueError("导出路径不安全，请检查导出目录后重试")
        if _export_used_by_other_report(conn, new_export_path, record_id):
            raise ValueError("导出路径已被其他日报使用，未保存修改")
        if os.path.lexists(new_export_path) and not same_path:
            raise ValueError("目标导出文件已存在，未覆盖该文件，请检查后重试")

        original_new = Path(new_export_path).read_bytes() if os.path.exists(new_export_path) else None
        originals: dict[str, bytes | None] = {}
        try:
            save_markdown(polished.strip(), date, report_id)
            originals[new_export_path] = original_new
            updated = update_report_by_id(
                record_id, report_id=report_id, date=date,
                template_type=template_type, raw_input=raw_input.strip(),
                polished=polished.strip(), export_path=new_export_path,
                connection=conn,
            )
            if not updated:
                raise LookupError("日报记录不存在或已被删除")

            if (
                old_export_path and not same_path
                and is_managed_export_path(old_export_path)
                and not _export_used_by_other_report(conn, old_export_path, record_id)
            ):
                try:
                    if os.path.isfile(old_export_path):
                        old_content = Path(old_export_path).read_bytes()
                        if delete_export_path(old_export_path):
                            originals[old_export_path] = old_content
                except OSError:
                    logger.exception("Failed to remove the superseded report export")

            result = get_report_by_id(record_id, connection=conn)
            if result is None:
                raise LookupError("日报记录更新后不可用")
            conn.commit()
            return result
        except BaseException:
            _compensate_failed_edit(conn, old, originals)
            raise


@dataclass(frozen=True)
class DeleteReportResult:
    record: dict
    cleanup_status: str
    cleanup_id: int | None


def retry_export_cleanup(cleanup_id: int) -> str:
    """Retry a persisted task, rechecking ownership before touching the file.

    The write lock prevents database reference changes between the active-report
    check and removal. A crash leaves the task safe to retry,
    even if the file has already been removed.
    """
    try:
        with export_cleanup_transaction(cleanup_id) as (conn, task):
            if task is None:
                return "not_found"
            path = task["export_path"]
            if not is_managed_export_path(path):
                status = "unmanaged"
            elif any(
                os.path.realpath(row["export_path"]) == os.path.realpath(path)
                for row in conn.execute(
                    "SELECT export_path FROM reports WHERE export_path IS NOT NULL "
                    "AND export_path != ''"
                )
            ):
                status = "in_use"
            else:
                try:
                    delete_export_path(path)
                except OSError as exc:
                    conn.execute(
                        "UPDATE export_cleanup SET last_error = ? WHERE id = ?",
                        (redact_secrets(str(exc)), cleanup_id),
                    )
                    return "pending"
                status = "complete"
            conn.execute("DELETE FROM export_cleanup WHERE id = ?", (cleanup_id,))
            return status
    except Exception:
        # The report deletion has already committed. Never misreport this as a
        # failed row deletion: the durable task survives a failed cleanup commit.
        logger.exception("Export cleanup task %s remains pending", cleanup_id)
        return "pending"


def delete_saved_report(record_id: int) -> DeleteReportResult | None:
    """Atomically delete the row and queue its export, then attempt cleanup."""
    deleted = delete_report_with_cleanup(record_id)
    if deleted is None:
        return None
    record, cleanup_id = deleted
    status = retry_export_cleanup(cleanup_id) if cleanup_id is not None else "complete"
    if status == "not_found":  # Another session already completed the task.
        status = "complete"
    return DeleteReportResult(record, status, cleanup_id)

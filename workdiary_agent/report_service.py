"""Coordinated CRUD operations for saved reports and their exports."""

from __future__ import annotations

from datetime import date as Date
import logging
import os
import uuid

from .redaction import redact_secrets
from .storage.export import delete_export_path, save_markdown
from .storage.sqlite import (
    delete_report_by_id,
    get_report_by_id,
    update_report_by_id,
)


TEMPLATE_TYPES = ("技术型", "业务型", "混合型")
logger = logging.getLogger(__name__)


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


def _rollback_export(old: dict, new_export_path: str) -> None:
    """Best-effort compensation when the database update fails."""
    try:
        old_path = old.get("export_path") or ""
        old_report_id = old.get("report_id")
        if old_report_id and os.path.realpath(old_path) == os.path.realpath(new_export_path):
            save_markdown(
                old.get("polished", "") or "",
                old["date"],
                old_report_id,
            )
        else:
            delete_export_path(new_export_path)
    except OSError:
        logger.exception("Failed to roll back an edited report export")


def update_saved_report(
    record_id: int,
    *,
    date: str,
    template_type: str,
    raw_input: str,
    polished: str,
) -> dict:
    """Update a report and keep its Markdown export synchronized."""
    _validate_update(
        date=date,
        template_type=template_type,
        raw_input=raw_input,
        polished=polished,
    )
    old = get_report_by_id(record_id)
    if old is None:
        raise LookupError("日报记录不存在或已被删除")

    report_id = old.get("report_id") or uuid.uuid4().hex
    new_export_path = save_markdown(polished.strip(), date, report_id)
    try:
        updated = update_report_by_id(
            record_id,
            report_id=report_id,
            date=date,
            template_type=template_type,
            raw_input=raw_input.strip(),
            polished=polished.strip(),
            export_path=new_export_path,
        )
        if not updated:
            raise LookupError("日报记录不存在或已被删除")
    except Exception:
        _rollback_export(old, new_export_path)
        raise

    old_export_path = old.get("export_path")
    if old_export_path and os.path.realpath(old_export_path) != os.path.realpath(new_export_path):
        try:
            delete_export_path(old_export_path)
        except OSError:
            logger.exception("Failed to remove the superseded report export")

    result = get_report_by_id(record_id)
    if result is None:  # Defensive against an unexpected concurrent deletion.
        raise LookupError("日报记录更新后不可用")
    return result


def delete_saved_report(record_id: int) -> dict | None:
    """Delete a report row, then remove its managed export when present."""
    record = get_report_by_id(record_id)
    if record is None:
        return None
    if not delete_report_by_id(record_id):
        return None
    try:
        delete_export_path(record.get("export_path"))
    except OSError:
        logger.exception("Failed to remove export for deleted report %s", record_id)
    return record

"""
workdiary_agent.storage — persistence and export utilities.

Public API:
    save_report(state)         — write to history.db
    get_all_reports()          — read/filter history, date DESC
    count_reports()            — count filtered history rows
    get_report(report_id)      — read one history row by stable id
    get_report_by_id(id)       — read one history row by database id
    update_report_by_id(...)   — update one history row
    delete_report_by_id(id)    — delete one history row
    save_markdown(text, date, report_id) — write a unique Markdown export
"""
from .sqlite import (
    count_reports,
    delete_report_by_id,
    get_all_reports,
    get_report,
    get_report_by_id,
    save_report,
    update_report_by_id,
)
from .export import delete_export_path, delete_markdown, save_markdown

__all__ = [
    "save_report",
    "get_all_reports",
    "count_reports",
    "get_report",
    "get_report_by_id",
    "update_report_by_id",
    "delete_report_by_id",
    "save_markdown",
    "delete_markdown",
    "delete_export_path",
]

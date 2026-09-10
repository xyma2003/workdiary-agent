"""
workdiary_agent.storage — persistence and export utilities.

Public API:
    save_report(state)         — write to history.db
    get_all_reports()          — read/filter history, date DESC
    count_reports()            — count filtered history rows
    get_report(report_id)      — read one history row
    save_markdown(text, date, report_id) — write a unique Markdown export
"""
from .sqlite import count_reports, get_all_reports, get_report, save_report
from .export import delete_markdown, save_markdown

__all__ = [
    "save_report",
    "get_all_reports",
    "count_reports",
    "get_report",
    "save_markdown",
    "delete_markdown",
]

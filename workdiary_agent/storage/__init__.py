"""
workdiary_agent.storage — persistence and export utilities.

Public API:
    save_report(state)         — write to history.db
    get_all_reports()          — read history, date DESC
    save_markdown(text, date)  — export to exports/daily_report_{date}.md
"""
from .sqlite import save_report, get_all_reports
from .export import save_markdown

__all__ = ["save_report", "get_all_reports", "save_markdown"]

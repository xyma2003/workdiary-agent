"""
Markdown export for WorkDiary Agent.

EXPORTS_DIR is a module-level constant so tests can monkeypatch it:
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
"""
import os
import re
import uuid

EXPORTS_DIR = "exports"


def save_markdown(polished: str, date: str, report_id: str | None = None) -> str:
    """Write a report to a unique, atomically-replaced Markdown file.

    Auto-creates exports/ directory if it does not exist.
    Returns the file path so save_node can store it in export_path.

    Args:
        polished: The final polished report text.
        date: ISO date string, e.g. "2026-04-24"

    Returns:
        str: Path to the written file.
    """
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    safe_date = re.sub(r"[^0-9A-Za-z_-]", "-", str(date))[:32].strip("-_")
    if not safe_date:
        safe_date = "undated"
    identifier = report_id or uuid.uuid4().hex
    safe_identifier = re.sub(r"[^A-Za-z0-9_-]", "", identifier)[:12]
    if not safe_identifier:
        safe_identifier = uuid.uuid4().hex[:12]
    filename = f"daily_report_{safe_date}_{safe_identifier}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)
    content = f"# 日报 {date}\n\n{polished}\n"
    temp_path = f"{filepath}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(temp_path, filepath)
    return filepath

"""
Markdown export for WorkDiary Agent.

EXPORTS_DIR is a module-level constant so tests can monkeypatch it:
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
"""
import os

EXPORTS_DIR = "exports"


def save_markdown(polished: str, date: str) -> str:
    """Write polished report to exports/daily_report_{date}.md.

    Auto-creates exports/ directory if it does not exist.
    Returns the file path so save_node can store it in export_path.

    Args:
        polished: The final polished report text.
        date: ISO date string, e.g. "2026-04-24"

    Returns:
        str: Path to the written file.
    """
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    filename = f"daily_report_{date}.md"
    filepath = os.path.join(EXPORTS_DIR, filename)
    content = f"# 日报 {date}\n\n{polished}\n"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

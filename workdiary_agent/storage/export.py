"""
Markdown export for WorkDiary Agent.

EXPORTS_DIR is a module-level constant so tests can monkeypatch it:
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))
"""
import os
import re
import stat
import uuid

from ..paths import data_path


EXPORTS_DIR = str(data_path("exports"))


def export_path_for_report(date: str, report_id: str) -> str:
    """Return the deterministic export path for a valid report identifier."""
    safe_date = re.sub(r"[^0-9A-Za-z_-]", "-", str(date))[:32].strip("-_")
    if not safe_date:
        safe_date = "undated"
    safe_identifier = re.sub(r"[^A-Za-z0-9_-]", "", report_id)[:12]
    if not safe_identifier:
        raise ValueError("report_id must contain a filename-safe character")
    filename = f"daily_report_{safe_date}_{safe_identifier}.md"
    return os.path.join(EXPORTS_DIR, filename)


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
    identifier = report_id or uuid.uuid4().hex
    try:
        filepath = export_path_for_report(date, identifier)
    except ValueError:
        filepath = export_path_for_report(date, uuid.uuid4().hex)
    content = f"# 日报 {date}\n\n{polished}\n"
    temp_path = f"{filepath}.{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(temp_path, filepath)
    finally:
        # A failed write/replace must not leave stale temp files behind.
        if os.path.isfile(temp_path):
            os.remove(temp_path)
    return filepath


def delete_markdown(date: str, report_id: str) -> bool:
    """Delete the deterministic export for an abandoned, unpersisted report."""
    try:
        filepath = export_path_for_report(date, report_id)
    except ValueError:
        return False
    if not os.path.isfile(filepath):
        return False
    os.remove(filepath)
    return True


def is_managed_export_path(filepath: str | None) -> bool:
    """Accept paths below the export directory without following symlinks."""
    if not filepath:
        return False
    # The filesystem resolves a symlink before walking through '..', unlike
    # abspath(). Never normalize away that evidence before validation.
    if ".." in filepath.split(os.sep):
        return False
    export_root = os.path.abspath(EXPORTS_DIR)
    target = os.path.abspath(filepath)
    if os.path.islink(export_root):
        return False
    try:
        if target == export_root or os.path.commonpath([export_root, target]) != export_root:
            return False
        real_root = os.path.realpath(export_root)
        if os.path.commonpath([real_root, os.path.realpath(target)]) != real_root:
            return False
    except ValueError:
        return False
    relative = os.path.relpath(target, export_root)
    current = export_root
    for component in relative.split(os.sep):
        current = os.path.join(current, component)
        if os.path.islink(current):
            return False
    return True


def delete_export_path(filepath: str | None) -> bool:
    """Remove a managed export; missing files are harmless, I/O errors propagate."""
    if not is_managed_export_path(filepath):
        return False
    try:
        info = os.stat(filepath, follow_symlinks=False)
    except FileNotFoundError:
        return False
    if not stat.S_ISREG(info.st_mode):
        raise OSError("导出路径不是普通文件，请检查后重试")
    os.remove(filepath)
    return True

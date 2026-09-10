"""Deterministic pre-approval checks for generated report content."""

from __future__ import annotations

import re
from typing import Any


_NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:,\d{3})*(?:\.\d+)?")
_LIST_MARKER_PATTERN = re.compile(r"(?m)^\s*\d+(?:[)、]|\.(?!\d))\s*")


def extract_numbers(text: object) -> set[str]:
    """Extract normalized numeric tokens while ignoring ordered-list markers."""
    normalized_text = _LIST_MARKER_PATTERN.sub("", "" if text is None else str(text))
    return {
        match.group(0).replace(",", "")
        for match in _NUMBER_PATTERN.finditer(normalized_text)
    }


def analyze_report_quality(state: Any) -> dict:
    """Return deterministic warnings without making another model call.

    This is a risk detector, not a proof of factual correctness. It intentionally
    leaves the final decision to the human reviewer.
    """
    report = state.get("edited_text")
    if report is None:
        report = state.get("polished", "") or ""

    source_text = "\n".join(
        str(state.get(field) or "")
        for field in ("raw_input", "git_log", "data_summary")
    )
    source_numbers = extract_numbers(source_text)
    contextual_numbers = extract_numbers(state.get("date"))
    report_numbers = extract_numbers(report)
    unverified_numbers = sorted(
        report_numbers - source_numbers - contextual_numbers
    )

    warnings: list[str] = []
    if unverified_numbers:
        warnings.append(
            "报告出现来源材料中未找到的数字："
            + "、".join(unverified_numbers)
            + "。请确认是否为模型补充。"
        )
    if not source_numbers and "未提供量化指标" not in report:
        warnings.append("来源材料没有量化数据，报告也未标注“未提供量化指标”。")
    if "[REDACTED_SECRET]" in report:
        warnings.append("报告包含已脱敏内容标记，请确认不会影响最终表达。")

    return {
        "warnings": warnings,
        "unverified_numbers": unverified_numbers,
        "source_numbers": sorted(source_numbers),
        "report_numbers": sorted(report_numbers),
    }

"""Deterministic pre-approval checks for generated report content."""

from __future__ import annotations

import re
from typing import Any

from .redaction import redact_secrets


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

    # Only original user/repository material is authoritative. data_summary is
    # itself model-generated and must not be allowed to validate its own output.
    source_text = "\n".join(
        str(state.get(field) or "")
        for field in ("raw_input", "data_input", "git_log")
    )
    source_numbers = extract_numbers(source_text)
    summary_numbers = extract_numbers(state.get("data_summary"))
    contextual_numbers = extract_numbers(state.get("date"))
    report_numbers = extract_numbers(report)
    unverified_numbers = sorted(
        report_numbers - source_numbers - contextual_numbers
    )
    unverified_summary_numbers = sorted(summary_numbers - source_numbers)

    warnings: list[str] = []
    if unverified_summary_numbers:
        warnings.append(
            "指标摘要出现原始材料中未找到的数字："
            + "、".join(unverified_summary_numbers)
            + "。请以原始数据为准。"
        )
    if unverified_numbers:
        warnings.append(
            "报告出现来源材料中未找到的数字："
            + "、".join(unverified_numbers)
            + "。请确认是否为模型补充。"
        )
    if not source_numbers and "未提供量化指标" not in report:
        warnings.append("来源材料没有量化数据，报告也未标注“未提供量化指标”。")
    contains_secret_marker = "[REDACTED_SECRET]" in report
    contains_potential_secret = redact_secrets(report) != report
    if contains_secret_marker or contains_potential_secret:
        warnings.append("报告可能包含凭证或脱敏标记，请移除后再保存。")

    return {
        "warnings": warnings,
        "unverified_numbers": unverified_numbers,
        "unverified_summary_numbers": unverified_summary_numbers,
        "source_numbers": sorted(source_numbers),
        "report_numbers": sorted(report_numbers),
        "contains_secret_marker": contains_secret_marker,
        "contains_potential_secret": contains_potential_secret,
    }

"""Deterministic pre-approval checks for generated report content."""

from __future__ import annotations

import re
from typing import Any

from .redaction import redact_secrets
from .source_snapshot import snapshot_for_storage


_NUMBER_PATTERN = re.compile(r"(?<![\w])\d+(?:,\d{3})*(?:\.\d+)?")
_LIST_MARKER_PATTERN = re.compile(r"(?m)^\s*\d+(?:[)、]|\.(?!\d))\s*")
_TIME_UNIT_ALIASES = {
    "ms": ("ms", "millisecond", "milliseconds", "毫秒"),
    "s": ("s", "sec", "secs", "second", "seconds", "秒"),
    "min": ("min", "mins", "minute", "minutes", "分钟"),
    "h": ("h", "hr", "hrs", "hour", "hours", "小时"),
    "d": ("d", "day", "days", "天"),
}
_TIME_UNIT_LOOKUP = {
    alias: unit for unit, aliases in _TIME_UNIT_ALIASES.items() for alias in aliases
}
_TIME_QUANTITY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_.,:/+−-])(?P<number>\d+(?:,\d{3})*(?:\.\d+)?)"
    r"[^\S\r\n]*(?P<unit>"
    + "|".join(re.escape(alias) for alias in sorted(_TIME_UNIT_LOOKUP, key=len, reverse=True))
    + r")(?![A-Za-z0-9_/:])",
    re.IGNORECASE | re.ASCII,
)


def _time_quantities(text: object) -> dict[str, set[str]]:
    """Collect explicit time units by number; this does not align individual claims."""
    quantities: dict[str, set[str]] = {}
    for match in _TIME_QUANTITY_PATTERN.finditer("" if text is None else str(text)):
        integer, _, fraction = match["number"].replace(",", "").partition(".")
        number = integer.lstrip("0") or "0"
        fraction = fraction.rstrip("0")
        if fraction:
            number += "." + fraction
        unit = _TIME_UNIT_LOOKUP[match["unit"].lower()]
        quantities.setdefault(number, set()).add(unit)
    return quantities


def _time_unit_mismatches(source_text: str, report: object) -> list[dict]:
    """Warn only when a number has source time units, but not the reported unit."""
    source_quantities = _time_quantities(source_text)
    report_quantities = _time_quantities(report)
    return [
        {"number": number, "report_unit": unit, "source_units": sorted(source_units)}
        for number, report_units in sorted(report_quantities.items())
        if (source_units := source_quantities.get(number))
        for unit in sorted(report_units - source_units)
    ]


def extract_numbers(text: object) -> set[str]:
    """Extract normalized numeric tokens while ignoring ordered-list markers."""
    normalized_text = _LIST_MARKER_PATTERN.sub("", "" if text is None else str(text))
    return {
        match.group(0).replace(",", "")
        for match in _NUMBER_PATTERN.finditer(normalized_text)
    }


def review_source_snapshot(state: Any) -> dict | None:
    """Return usable frozen evidence for both the review UI and its checks.

    Old or incompatible checkpoints keep their existing state-based fallback.
    Empty fields in a valid snapshot are still authoritative: combining them
    with later state values would silently invent evidence for that snapshot.
    """
    source = state.get("source_snapshot")
    if not isinstance(source, dict):
        return None
    git = source.get("git")
    if (
        type(source.get("schema_version")) is not int
        or source["schema_version"] != 1
        or source.get("capture_status") not in ("complete", "partial")
        or not all(
            isinstance(source.get(key), str)
            for key in ("captured_at", "raw_input", "data_input")
        )
        or not isinstance(git, dict)
        or git.get("status") not in (
            "captured", "empty", "unavailable", "not_requested", "legacy_unknown",
        )
        or (git.get("log") is not None and not isinstance(git["log"], str))
    ):
        return None
    return snapshot_for_storage({
        "source_snapshot": source,
        "model_usage": state.get("model_usage", source.get("model_usage", [])),
    })


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
    snapshot = review_source_snapshot(state)
    sources = (
        {
            "raw_input": snapshot["raw_input"],
            "data_input": snapshot["data_input"],
            "git_log": snapshot["git"]["log"],
        }
        if snapshot is not None else state
    )
    source_text = "\n".join(
        str(sources.get(field) or "")
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
    time_unit_mismatches = _time_unit_mismatches(source_text, report)

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
    for mismatch in time_unit_mismatches:
        warnings.append(
            f"报告中的时间单位可能与原始材料不一致：{mismatch['number']} {mismatch['report_unit']}；"
            f"来源中同一数值的单位为 {'、'.join(mismatch['source_units'])}。"
            "请对照原始材料核对；此提示不判断单位换算或指标归属。"
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
        "time_unit_mismatches": time_unit_mismatches,
        "source_numbers": sorted(source_numbers),
        "report_numbers": sorted(report_numbers),
        "contains_secret_marker": contains_secret_marker,
        "contains_potential_secret": contains_potential_secret,
    }

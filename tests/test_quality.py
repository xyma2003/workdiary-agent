"""Deterministic report quality checks."""

import pytest

from workdiary_agent.quality import (
    analyze_report_quality,
    extract_numbers,
    review_source_snapshot,
)


def test_number_extraction_ignores_ordered_list_markers():
    assert extract_numbers("1. 第一项\n2、第二项\n3.2% 转化率，用户 12,000") == {
        "3.2",
        "12000",
    }


def test_quality_flags_numbers_absent_from_all_sources():
    result = analyze_report_quality({
        "raw_input": "完成登录稳定性修复",
        "git_log": "abc1234 fix login timeout",
        "data_summary": None,
        "polished": "完成登录修复，错误率下降 20%",
    })

    assert result["unverified_numbers"] == ["20"]
    assert any("20" in warning for warning in result["warnings"])


def test_quality_accepts_numbers_present_in_metrics():
    result = analyze_report_quality({
        "raw_input": "完成性能优化",
        "data_input": "响应时间从 200ms 降至 45ms",
        "data_summary": "响应时间从 200ms 降至 45ms",
        "polished": "完成性能优化，响应时间从 200ms 降至 45ms。",
    })

    assert result["unverified_numbers"] == []
    assert result["warnings"] == []


def test_quality_does_not_trust_hallucinated_metric_summary():
    result = analyze_report_quality({
        "raw_input": "完成性能优化",
        "data_input": "响应时间降至 45ms",
        "data_summary": "响应时间从 200ms 降至 45ms",
        "polished": "响应时间从 200ms 降至 45ms。",
    })

    assert result["unverified_summary_numbers"] == ["200"]
    assert result["unverified_numbers"] == ["200"]


def test_quality_detects_unredacted_secret_in_final_report():
    result = analyze_report_quality({
        "raw_input": "检查部署配置",
        "polished": "检查密钥 sk-abcdefghijklmnopqrstuvwxyz",
    })

    assert result["contains_potential_secret"] is True
    assert result["contains_secret_marker"] is False
    assert any("凭证" in warning for warning in result["warnings"])


def test_quality_requests_missing_metric_disclosure():
    result = analyze_report_quality({
        "raw_input": "完成缓存优化",
        "polished": "完成缓存优化并准备上线。",
    })

    assert any("未提供量化指标" in warning for warning in result["warnings"])


def test_quality_recognizes_report_date_as_source_data():
    result = analyze_report_quality({
        "date": "2026-04-24",
        "raw_input": "完成缓存优化",
        "polished": "2026-04-24 日报：完成缓存优化。",
    })

    assert result["unverified_numbers"] == []
    assert any("未提供量化指标" in warning for warning in result["warnings"])


def _snapshot(**overrides):
    return {
        "schema_version": 1,
        "captured_at": "2026-10-14T02:00:00+00:00",
        "capture_status": "complete",
        "raw_input": "完成 3 项测试",
        "data_input": "响应时间降至 45ms",
        "git": {"status": "captured", "log": "abcdef1 fix: resolve 2 retries"},
        **overrides,
    }


def test_quality_uses_frozen_material_when_checkpoint_state_diverges():
    result = analyze_report_quality({
        "source_snapshot": _snapshot(),
        "raw_input": "人工更新后记录 7 项测试",
        "data_input": "更新后响应时间 20ms",
        "git_log": "fedcba1 fix: resolve 9 retries",
        "data_summary": "完成 3 项测试，响应时间 20ms",
        "edited_text": "完成 3 项测试，响应时间 45ms，修复 2 次重试，新增 7、20、9。",
    })

    assert result["source_numbers"] == ["2", "3", "45"]
    assert result["unverified_numbers"] == ["20", "7", "9"]
    assert result["unverified_summary_numbers"] == ["20"]


def test_empty_frozen_sources_never_borrow_later_state_material():
    result = analyze_report_quality({
        "source_snapshot": _snapshot(
            capture_status="partial",
            raw_input="",
            data_input="",
            git={"status": "unavailable", "log": None},
        ),
        "raw_input": "完成 3 项测试",
        "data_input": "响应时间 45ms",
        "git_log": "abcdef1 fix: resolve 2 retries",
        "polished": "完成 3 项测试，响应时间 45ms，修复 2 次重试。",
    })

    assert result["source_numbers"] == []
    assert result["unverified_numbers"] == ["2", "3", "45"]
    assert any("未提供量化指标" in warning for warning in result["warnings"])


@pytest.mark.parametrize("snapshot", [
    None,
    "corrupt",
    _snapshot(schema_version=99),
    _snapshot(schema_version=True),
    _snapshot(capture_status=["complete"]),
    _snapshot(raw_input=None),
    _snapshot(git={"status": ["captured"], "log": "malformed"}),
    _snapshot(git={"status": "captured", "log": ["malformed"]}),
])
def test_unusable_snapshot_uses_explicit_legacy_state_fallback(snapshot):
    state = {
        "source_snapshot": snapshot,
        "raw_input": "响应时间 45ms",
        "polished": "响应时间 45ms",
    }

    assert review_source_snapshot(state) is None
    assert analyze_report_quality(state)["warnings"] == []


def test_quality_flags_changed_time_unit_and_preserves_number_warning():
    result = analyze_report_quality({
        "raw_input": "响应时间 10ms",
        "polished": "响应时间 10s，完成 20 项检查。",
    })

    assert result["time_unit_mismatches"] == [{
        "number": "10", "report_unit": "s", "source_units": ["ms"],
    }]
    assert result["unverified_numbers"] == ["20"]
    assert any("时间单位" in warning for warning in result["warnings"])
    assert any("20" in warning for warning in result["warnings"])


@pytest.mark.parametrize("source,report", [
    ("10ms", "10 ms"),
    ("10毫秒", "10 milliseconds"),
    ("10 millisecond", "10 MS"),
    ("10秒", "10 SECS"),
    ("10 sec", "10 seconds"),
    ("10 second", "10 s"),
    ("10分钟", "10 mins"),
    ("10 MINUTE", "10 minutes"),
    ("10小时", "10 HR"),
    ("10 hrs", "10 hour"),
    ("10 h", "10 hours"),
    ("10天", "10 DAY"),
    ("10 d", "10 days"),
])
def test_quality_accepts_unchanged_time_unit_and_equivalent_aliases(source, report):
    result = analyze_report_quality({"raw_input": source, "polished": report})

    assert result["time_unit_mismatches"] == []
    assert result["warnings"] == []


@pytest.mark.parametrize("source,report,source_unit,report_unit", [
    ("10 毫秒", "10 秒", "ms", "s"),
    ("10 seconds", "10 分钟", "s", "min"),
    ("10 minutes", "10 小时", "min", "h"),
    ("10 hours", "10 天", "h", "d"),
    ("10 days", "10 milliseconds", "d", "ms"),
])
def test_quality_detects_changes_across_supported_time_units(
    source, report, source_unit, report_unit,
):
    result = analyze_report_quality({"raw_input": source, "polished": report})

    assert result["time_unit_mismatches"] == [{
        "number": "10", "report_unit": report_unit, "source_units": [source_unit],
    }]


def test_quality_accepts_time_pair_found_in_any_original_source():
    result = analyze_report_quality({
        "raw_input": "接口响应 10ms",
        "data_input": "任务完成用时 10s",
        "git_log": "abcdef1 docs: describe retry interval of 10 minutes",
        "polished": "任务完成用时 10 seconds，重试间隔 10 分钟。",
    })

    assert result["time_unit_mismatches"] == []
    assert result["warnings"] == []


def test_quality_reports_all_source_units_without_duplicate_findings():
    result = analyze_report_quality({
        "raw_input": "接口响应 10ms，任务完成用时 10s",
        "data_input": "接口响应 10 毫秒",
        "polished": "任务完成用时 10 minutes，重复记录 10 分钟。",
    })

    assert result["time_unit_mismatches"] == [{
        "number": "10", "report_unit": "min", "source_units": ["ms", "s"],
    }]


@pytest.mark.parametrize("source_number,report_number", [
    ("1,000", "1000.00"),
    ("010.00", "10"),
    ("10", "010.0"),
])
def test_quality_compares_normalized_time_values(source_number, report_number):
    result = analyze_report_quality({
        "raw_input": f"响应时间 {source_number}ms",
        "polished": f"响应时间 {report_number}s",
    })

    expected_number = "1000" if "," in source_number else "10"
    assert result["time_unit_mismatches"] == [{
        "number": expected_number, "report_unit": "s", "source_units": ["ms"],
    }]


def test_quality_does_not_infer_unit_conversion_or_unit_from_bare_number():
    converted = analyze_report_quality({
        "raw_input": "响应时间 1000ms", "polished": "响应时间 1s",
    })
    bare = analyze_report_quality({
        "raw_input": "完成 10 项测试", "polished": "响应时间 10s",
    })

    assert converted["time_unit_mismatches"] == []
    assert converted["unverified_numbers"] == ["1"]
    assert bare["time_unit_mismatches"] == []


@pytest.mark.parametrize("non_time_text", [
    "10models 10secant 10minimum 10hoursly 10dayshift",
    "v10s run10min model_10ms 10s_version 10ms2",
    "10m 10分 10日 10时 10ns 10us 10周",
    "2026-10-28 10:30 10/28",
    "10 ſ 10 MİNS 10 mınutes",
    "1e-10s 1e+10s v1-10s -10s +10s −10s",
])
def test_quality_does_not_treat_word_fragments_or_dates_as_time_units(non_time_text):
    result = analyze_report_quality({
        "raw_input": "响应时间 10ms",
        "polished": non_time_text,
    })
    reversed_result = analyze_report_quality({
        "raw_input": non_time_text,
        "polished": "响应时间 10 seconds",
    })

    assert result["time_unit_mismatches"] == []
    assert reversed_result["time_unit_mismatches"] == []


@pytest.mark.parametrize("frozen_unit,later_unit,report_unit,expected", [
    ("ms", "s", "s", [{"number": "10", "report_unit": "s", "source_units": ["ms"]}]),
    ("s", "ms", "s", []),
])
def test_quality_time_units_use_frozen_material_when_state_diverges(
    frozen_unit, later_unit, report_unit, expected,
):
    result = analyze_report_quality({
        "source_snapshot": _snapshot(
            raw_input=f"响应时间 10{frozen_unit}", data_input="",
            git={"status": "not_requested", "log": None},
        ),
        "raw_input": f"响应时间 10{later_unit}",
        "data_input": f"响应时间 10{later_unit}",
        "git_log": f"abcdef1 measured 10{later_unit}",
        "data_summary": f"响应时间 10{later_unit}",
        "polished": f"响应时间 10{report_unit}",
    })

    assert result["time_unit_mismatches"] == expected


def test_quality_does_not_trust_generated_summary_time_unit():
    result = analyze_report_quality({
        "raw_input": "响应时间 10ms",
        "data_summary": "响应时间 10s",
        "polished": "响应时间 10s",
    })

    assert result["unverified_numbers"] == []
    assert result["unverified_summary_numbers"] == []
    assert result["time_unit_mismatches"] == [{
        "number": "10", "report_unit": "s", "source_units": ["ms"],
    }]


def test_empty_frozen_sources_never_borrow_later_time_units():
    result = analyze_report_quality({
        "source_snapshot": _snapshot(
            capture_status="partial", raw_input="", data_input="",
            git={"status": "unavailable", "log": None},
        ),
        "raw_input": "响应时间 10ms",
        "data_input": "响应时间 10ms",
        "git_log": "abcdef1 measured 10ms",
        "data_summary": "响应时间 10ms",
        "polished": "响应时间 10s",
    })

    assert result["time_unit_mismatches"] == []
    assert result["unverified_numbers"] == ["10"]


@pytest.mark.parametrize("edited,polished,expected", [
    ("响应时间 10s", "响应时间 10ms", [
        {"number": "10", "report_unit": "s", "source_units": ["ms"]},
    ]),
    ("响应时间 10ms", "响应时间 10s", []),
    ("", "响应时间 10s", []),
])
def test_quality_time_units_check_edited_text_including_empty_edit(
    edited, polished, expected,
):
    result = analyze_report_quality({
        "raw_input": "响应时间 10ms", "edited_text": edited, "polished": polished,
    })

    assert result["time_unit_mismatches"] == expected

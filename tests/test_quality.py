"""Deterministic report quality checks."""

from workdiary_agent.quality import analyze_report_quality, extract_numbers


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
        "data_summary": "响应时间从 200ms 降至 45ms",
        "polished": "完成性能优化，响应时间从 200ms 降至 45ms。",
    })

    assert result["unverified_numbers"] == []
    assert result["warnings"] == []


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

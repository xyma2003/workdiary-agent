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

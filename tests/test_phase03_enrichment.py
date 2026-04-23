"""
Phase 3 — Enrichment Tools test suite.
Tests cover all 3 success criteria from ROADMAP.md §Phase 3.
Run: conda run -n llm-data-pipeline pytest tests/test_phase03_enrichment.py -v
All tests FAIL in RED state (enrich_node is a stub, draft_node lacks enrichment context).
"""
import pytest
from unittest.mock import patch, MagicMock
from workdiary_agent.state import AgentState, StructuredInfo
from workdiary_agent.nodes.enrich import enrich_node
from workdiary_agent.nodes.draft import draft_node


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_commit(hexsha: str, message: str) -> MagicMock:
    c = MagicMock()
    c.hexsha = hexsha
    c.message = message
    return c


# ---------------------------------------------------------------------------
# SC-1 + SC-2 (AGENT-03): enrich_node reads today's git commits
# ---------------------------------------------------------------------------

def test_enrich_valid_repo_produces_git_log():
    """SC-1: Valid repo path → git_log contains formatted commit lines."""
    fake_commits = [
        _make_mock_commit("abc1234567890", "feat: add login module\n"),
        _make_mock_commit("def5678901234", "fix: resolve memory leak\n"),
    ]
    mock_repo = MagicMock()
    mock_repo.iter_commits.return_value = fake_commits

    with patch("workdiary_agent.nodes.enrich.git.Repo", return_value=mock_repo):
        state: AgentState = {"repo_path": "/fake/repo"}
        result = enrich_node(state)

    assert "git_log" in result, "result must contain git_log key"
    git_log = result["git_log"]
    assert git_log is not None, "git_log must not be None for valid repo with commits"
    assert "abc1234" in git_log, f"git_log must contain short hash 'abc1234', got: {git_log}"
    assert "feat: add login module" in git_log, f"git_log must contain commit message, got: {git_log}"
    assert "def5678" in git_log, f"git_log must contain second commit hash, got: {git_log}"


def test_enrich_invalid_repo_returns_none_no_exception():
    """SC-2: Invalid repo path → git_log=None, no exception, data_summary key present."""
    # No mock — use a path that doesn't exist; git.Repo will raise NoSuchPathError
    state: AgentState = {"repo_path": "/absolutely/nonexistent/path/xyz_99999"}
    result = enrich_node(state)  # Must NOT raise

    assert "git_log" in result, "result must contain git_log key even on error"
    assert result["git_log"] is None, "git_log must be None for invalid repo"
    # data_summary key must be present (even if None) — stub fails this
    assert "data_summary" in result, "result must contain data_summary key"


def test_enrich_empty_repo_path_returns_none():
    """SC-2 variant: Empty string repo_path → git_log=None, no exception."""
    state: AgentState = {"repo_path": ""}
    result = enrich_node(state)

    assert result.get("git_log") is None, "git_log must be None for empty repo_path"
    assert "data_summary" in result, "result must contain data_summary key"


# ---------------------------------------------------------------------------
# SC-3 (AGENT-04): enrich_node extracts metrics from data_input via LLM
# ---------------------------------------------------------------------------

def test_enrich_with_data_input_produces_summary():
    """SC-3: Non-empty data_input → data_summary extracted by LLM."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "关键指标：转化率15%，GMV环比增长20%，响应时间从200ms降到45ms"
    mock_llm.invoke.return_value = mock_response

    with patch("workdiary_agent.nodes.enrich._make_llm", return_value=mock_llm):
        state: AgentState = {
            "data_input": "转化率15%，GMV增长20%，响应时间从200ms降到45ms"
        }
        result = enrich_node(state)

    assert "data_summary" in result, "result must contain data_summary key"
    assert result["data_summary"] is not None, "data_summary must not be None when data_input provided"
    assert len(result["data_summary"]) > 10, "data_summary must be non-trivially long"
    mock_llm.invoke.assert_called_once()  # LLM must have been called exactly once


def test_enrich_empty_data_input_skips_llm():
    """SC-3 variant: Missing/empty data_input → data_summary=None, LLM NOT called."""
    mock_llm = MagicMock()

    with patch("workdiary_agent.nodes.enrich._make_llm", return_value=mock_llm):
        # No data_input key at all
        result_no_key = enrich_node({})
        # Empty string data_input
        result_empty = enrich_node({"data_input": ""})

    assert result_no_key.get("data_summary") is None, \
        "data_summary must be None when data_input absent"
    assert result_empty.get("data_summary") is None, \
        "data_summary must be None when data_input is empty string"
    mock_llm.invoke.assert_not_called()  # LLM must NOT be called


# ---------------------------------------------------------------------------
# SC-1 + SC-3 via draft_node: enrichment context flows into draft
# ---------------------------------------------------------------------------

def test_draft_node_includes_git_log_in_context():
    """SC-1 via draft: git_log in state → draft content contains git commit info."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "【已选用技术型模板】\n任务：缓存优化\nabc1234 feat: add login module"
    mock_llm.invoke.return_value = mock_response

    with patch("workdiary_agent.nodes.draft._make_llm", return_value=mock_llm):
        state: AgentState = {
            "raw_input": "今天完成了缓存优化",
            "template_type": "技术型",
            "structured_info": StructuredInfo(
                tasks=["缓存优化"],
                outputs=["优化完成"],
                blockers=[],
                progress="完成"
            ),
            "git_log": "abc1234 feat: add login module\ndef5678 fix: resolve bug",
            "data_summary": None,
        }
        result = draft_node(state)

    # Verify the LLM was called with a prompt containing git_log context
    call_args = mock_llm.invoke.call_args
    messages = call_args[0][0]
    full_prompt = " ".join(str(m.content) for m in messages)
    assert "今日 Git commits" in full_prompt, \
        f"draft prompt must contain '今日 Git commits' when git_log is set. Got: {full_prompt[:300]}"
    assert "abc1234" in full_prompt, \
        f"draft prompt must contain the actual git_log content. Got: {full_prompt[:300]}"


def test_draft_node_includes_data_summary_in_context():
    """SC-3 via draft: data_summary in state → draft prompt contains metrics."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "【已选用业务型模板】\n结论：转化率提升\n数据：15%"
    mock_llm.invoke.return_value = mock_response

    with patch("workdiary_agent.nodes.draft._make_llm", return_value=mock_llm):
        state: AgentState = {
            "raw_input": "今天优化了转化漏斗",
            "template_type": "业务型",
            "structured_info": None,
            "git_log": None,
            "data_summary": "关键指标：转化率15%，GMV环比增长20%",
        }
        result = draft_node(state)

    call_args = mock_llm.invoke.call_args
    messages = call_args[0][0]
    full_prompt = " ".join(str(m.content) for m in messages)
    assert "数据指标" in full_prompt, \
        f"draft prompt must contain '数据指标' when data_summary is set. Got: {full_prompt[:300]}"
    assert "转化率15%" in full_prompt, \
        f"draft prompt must contain the actual data_summary content. Got: {full_prompt[:300]}"

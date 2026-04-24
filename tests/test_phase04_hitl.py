"""
Phase 4 — Human-in-the-Loop test suite.
Tests cover all 5 success criteria from ROADMAP.md §Phase 4.
Run: conda run -n llm-data-pipeline pytest tests/test_phase04_hitl.py -v

Route function tests PASS immediately (pure logic).
Graph-integration tests FAIL in RED state until Plan 04-02 + 04-03 are complete.
"""
import pytest
from unittest.mock import patch, MagicMock
from langgraph.types import Command
from workdiary_agent.graph import build_graph, route_after_revise, route_after_review


# ---------------------------------------------------------------------------
# LLM mock helpers
# ---------------------------------------------------------------------------

def _make_llm_mock(return_text: str = "polished draft") -> MagicMock:
    """Return a mock that behaves like ChatAnthropic().invoke() returning AIMessage."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = return_text
    mock_llm.invoke.return_value = mock_response
    mock_llm.with_structured_output.return_value = mock_llm
    return mock_llm


def _mock_all_llm_nodes():
    """Context manager stack mocking all LLM-calling nodes to avoid API calls."""
    return [
        patch("workdiary_agent.nodes.extract._make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.draft._make_llm", return_value=_make_llm_mock("【已选用混合型模板】\n日报初稿内容")),
        patch("workdiary_agent.nodes.polish._make_llm", return_value=_make_llm_mock("polished content")),
        patch("workdiary_agent.nodes.enrich._make_llm", return_value=_make_llm_mock()),
    ]


def _build_test_graph():
    """Build graph with InMemorySaver (no disk writes during tests)."""
    return build_graph(use_sqlite=False)


# ---------------------------------------------------------------------------
# Route function unit tests — PASS immediately (no LLM or graph needed)
# ---------------------------------------------------------------------------

def test_route_after_review_approve():
    """route_after_review returns 'save' when decision is 'approve'."""
    assert route_after_review({"human_decision": "approve"}) == "save"


def test_route_after_review_revise():
    """route_after_review returns 'revise' when decision is 'revise'."""
    assert route_after_review({"human_decision": "revise"}) == "revise"


def test_route_after_review_default():
    """route_after_review defaults to 'save' when human_decision is missing."""
    assert route_after_review({}) == "save"


def test_route_after_revise_under_limit():
    """route_after_revise returns 'polish' when revision_count < 3."""
    assert route_after_revise({"revision_count": 0}) == "polish"
    assert route_after_revise({"revision_count": 2}) == "polish"


def test_route_after_revise_at_limit():
    """route_after_revise returns 'save' when revision_count >= 3."""
    assert route_after_revise({"revision_count": 3}) == "save"
    assert route_after_revise({"revision_count": 4}) == "save"


def test_route_after_revise_unset():
    """route_after_revise defaults revision_count to 0 (state.get pattern)."""
    assert route_after_revise({}) == "polish"


# ---------------------------------------------------------------------------
# Graph-integration tests — FAIL in RED state (require Plan 04-02 + 04-03)
# ---------------------------------------------------------------------------

def test_graph_pauses_at_review():
    """SC-1 / HITL-01: After invoke(), graph pauses at 'review' node (not END).

    FAILS in RED state because review_node is still the Phase 1 stub (returns
    human_decision immediately without calling interrupt()).
    """
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc1"}}
    mocks = _mock_all_llm_nodes()
    # Patch extract to return a StructuredInfo-like mock
    with mocks[0], mocks[1], mocks[2], mocks[3]:
        with patch("workdiary_agent.nodes.extract.ChatAnthropic") as mock_cls:
            mock_cls.return_value = _make_llm_mock()
            result = g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    # SC-1: graph must be paused, not completed
    state = g.get_state(cfg)
    assert "review" in state.next, (
        f"Expected graph paused at 'review', got state.next={state.next}. "
        "review_node must call interrupt() — Phase 1 stub bypasses this."
    )
    assert "__interrupt__" in result, (
        "Expected '__interrupt__' key in result when graph pauses at interrupt(). "
        "review_node stub returns immediately without interrupt()."
    )


def test_approve_path():
    """SC-2 / HITL-04: approve → final_report non-empty, graph reaches END.

    FAILS in RED state: review_node is a stub (no interrupt), so there is
    nothing to resume from.
    """
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc2"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3]:
        with patch("workdiary_agent.nodes.extract.ChatAnthropic"):
            g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    # Resume with approve
    result2 = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert result2.get("final_report"), (
        "final_report should be non-empty after approve. "
        "save_node must return final_report = state.get('polished', '')."
    )
    state = g.get_state(cfg)
    assert not state.next, (
        f"Graph should be at END after approve, got state.next={state.next}"
    )


def test_revise_loop():
    """SC-3 / HITL-03: revise → graph loops back to review (count increments).

    FAILS in RED state: topology still has direct review→revise edge;
    review_node has no interrupt().
    """
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc3"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3]:
        with patch("workdiary_agent.nodes.extract.ChatAnthropic"):
            g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    # First revise
    with mocks[2]:  # polish is called again during loop
        g.invoke(Command(resume={"decision": "revise", "feedback": "请加上业务影响"}), cfg)
    state = g.get_state(cfg)
    assert "review" in state.next, (
        f"Expected graph paused again at 'review' after revise, got {state.next}. "
        "Topology must loop: polish → review (interrupt) → revise → polish."
    )
    count = state.values.get("revision_count", 0)
    assert count == 1, f"revision_count should be 1 after first revise, got {count}"


def test_force_exit_after_3_revisions():
    """SC-4 / HITL-03: 3rd revise → force save, graph at END.

    FAILS in RED state: route_after_revise still returns 'review'|'save'
    (not 'polish'|'save'), and review_node has no interrupt().
    """
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc4"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3]:
        with patch("workdiary_agent.nodes.extract.ChatAnthropic"):
            g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    for i in range(3):
        with mocks[2]:  # polish re-runs each revision loop
            g.invoke(
                Command(resume={"decision": "revise", "feedback": f"第{i+1}次修改意见"}),
                cfg,
            )
    state = g.get_state(cfg)
    assert not state.next, (
        f"After 3 revisions graph should be at END, got state.next={state.next}. "
        "route_after_revise must return 'save' when revision_count >= 3."
    )
    count = state.values.get("revision_count", 0)
    assert count == 3, f"revision_count should be 3 after 3 revisions, got {count}"
    assert state.values.get("final_report"), "final_report must be non-empty after force-exit"

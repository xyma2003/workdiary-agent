"""Human-in-the-loop routing and graph regression tests."""
import pytest
from unittest.mock import patch, MagicMock
from langgraph.types import Command
from workdiary_agent.graph import build_graph, route_after_revise, route_after_review
from workdiary_agent.nodes.polish import polish_node
from workdiary_agent.recovery import list_recoverable_runs
from workdiary_agent.state import StructuredInfo
import workdiary_agent.storage.export as export_mod
import workdiary_agent.storage.sqlite as sqlite_mod


@pytest.fixture(autouse=True)
def _isolate_persistent_outputs(tmp_path, monkeypatch):
    """Graph tests must never write into the application's real data files."""
    monkeypatch.setattr(sqlite_mod, "DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(export_mod, "EXPORTS_DIR", str(tmp_path / "exports"))


# ---------------------------------------------------------------------------
# LLM mock helpers
# ---------------------------------------------------------------------------

def _make_llm_mock(return_text: str = "polished draft") -> MagicMock:
    """Return a mock that behaves like ChatAnthropic().invoke() returning AIMessage."""
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.content = return_text
    mock_llm.invoke.return_value = mock_response
    # with_structured_output must return a mock whose invoke() returns a real StructuredInfo
    # so that LangGraph's msgpack checkpointer can serialize the state.
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = StructuredInfo(
        tasks=["完成登录模块开发"],
        outputs=["登录模块代码"],
        blockers=[],
        progress="登录模块开发完成",
    )
    mock_llm.with_structured_output.return_value = mock_structured
    return mock_llm


def _mock_all_llm_nodes():
    """Context manager stack mocking all LLM-calling nodes to avoid API calls."""
    return [
        patch("workdiary_agent.nodes.extract.make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.draft.make_llm", return_value=_make_llm_mock("【已选用混合型模板】\n日报初稿内容")),
        patch("workdiary_agent.nodes.polish.make_llm", return_value=_make_llm_mock("polished content")),
        patch("workdiary_agent.nodes.enrich.make_llm", return_value=_make_llm_mock()),
        patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify",
              return_value="混合型"),
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
    """Missing decisions return to review and never save implicitly."""
    assert route_after_review({}) == "review"


def test_route_after_revise_under_limit():
    """route_after_revise returns 'polish' when revision_count < 3."""
    assert route_after_revise({"revision_count": 0}) == "polish"
    assert route_after_revise({"revision_count": 2}) == "polish"


def test_route_after_revise_at_limit():
    """An accepted revision is always applied, including the third one."""
    assert route_after_revise({"revision_count": 3}) == "polish"
    assert route_after_revise({"revision_count": 4}) == "polish"


def test_route_after_revise_unset():
    """route_after_revise defaults revision_count to 0 (state.get pattern)."""
    assert route_after_revise({}) == "polish"


# ---------------------------------------------------------------------------
# Graph integration tests
# ---------------------------------------------------------------------------

def test_graph_pauses_at_review():
    """SC-1 / HITL-01: after invoke(), graph pauses at review instead of END."""
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc1"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4]:
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
    recoverable = list_recoverable_runs(g)
    assert recoverable[0]["thread_id"] == "test-sc1"
    assert recoverable[0]["status"] == "reviewing"


def test_approve_path():
    """SC-2 / HITL-04: approve produces final_report and reaches END."""
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc2"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4]:
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
    """SC-3 / HITL-03: revise loops back to review and increments the count."""
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc3"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4]:
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


def test_three_revisions_still_require_approval():
    """The third revision is applied and still requires explicit approval."""
    g = _build_test_graph()
    cfg = {"configurable": {"thread_id": "test-sc4"}}
    mocks = _mock_all_llm_nodes()
    with mocks[0], mocks[1], mocks[2], mocks[3], mocks[4]:
        g.invoke({"raw_input": "今天完成了登录模块开发"}, cfg)
    for i in range(3):
        revised_llm = _make_llm_mock(f"revision {i+1}: applied")
        with patch("workdiary_agent.nodes.polish.make_llm", return_value=revised_llm):
            g.invoke(
                Command(resume={"decision": "revise", "feedback": f"第{i+1}次修改意见"}),
                cfg,
            )
        state_mid = g.get_state(cfg)
        assert "review" in state_mid.next

    state = g.get_state(cfg)
    count = state.values.get("revision_count", 0)
    assert count == 3, f"revision_count should be 3 after 3 revisions, got {count}"
    assert state.values.get("polished") == "revision 3: applied"
    assert state.values.get("feedback_history") == [
        "第1次修改意见", "第2次修改意见", "第3次修改意见"
    ]
    assert not state.values.get("final_report"), "must not save without approval"

    result = g.invoke(Command(resume={"decision": "approve", "feedback": ""}), cfg)
    assert not g.get_state(cfg).next
    assert result.get("final_report") == "revision 3: applied"


def test_revision_limit_returns_to_review():
    assert route_after_review({
        "human_decision": "revise",
        "revision_count": 3,
    }) == "review"


def test_review_rejects_empty_approval_and_over_limit_revision():
    with patch(
        "workdiary_agent.nodes.review.interrupt",
        return_value={"decision": "approve", "edited_text": ""},
    ):
        from workdiary_agent.nodes.review import review_node
        assert review_node({"polished": "content"})["human_decision"] == "review"

    with patch(
        "workdiary_agent.nodes.review.interrupt",
        return_value={"decision": "revise", "feedback": "unapplied"},
    ):
        result = review_node({"revision_count": 3, "feedback_history": []})
        assert result["human_decision"] == "review"
        assert result["feedback_history"] == []


def test_revision_uses_inline_edit_and_all_feedback():
    mock_llm = _make_llm_mock("updated")
    state = {
        "draft": "original draft",
        "polished": "previous polished",
        "edited_text": "user edited base",
        "human_feedback": "第二条意见",
        "feedback_history": ["第一条意见", "第二条意见"],
    }

    with patch("workdiary_agent.nodes.polish.make_llm", return_value=mock_llm):
        result = polish_node(state)

    messages = mock_llm.invoke.call_args.args[0]
    prompt = "\n".join(str(message.content) for message in messages)
    assert "user edited base" in prompt
    assert "original draft" not in prompt
    assert "第一条意见" in prompt
    assert "第二条意见" in prompt
    assert result == {"polished": "updated", "edited_text": None}

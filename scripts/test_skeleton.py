#!/usr/bin/env python
"""
Standalone smoke test for Phase 1 Graph Skeleton.
Verifies all 4 ROADMAP success criteria without pytest.
Run: python scripts/test_skeleton.py
"""
import sys
import os
import typing
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path regardless of cwd when script is invoked
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def test_agent_state_fields():
    from workdiary_agent.state import AgentState
    hints = typing.get_type_hints(AgentState)
    required_fields = {
        "raw_input", "structured_info", "template_type", "draft",
        "polished", "human_decision", "human_feedback", "revision_count",
        "git_log", "repo_path", "final_report", "export_path",
    }
    missing = required_fields - set(hints.keys())
    assert not missing, f"AgentState missing fields: {missing}"
    print(f"PASS: AgentState has all {len(required_fields)} required fields")


def test_all_nodes_present():
    from workdiary_agent.graph import build_graph
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    required = {"extract", "enrich", "route_template", "draft",
                "polish", "review", "revise", "save"}
    missing = required - node_names
    assert not missing, f"Missing nodes: {missing}"
    print(f"PASS: all 8 nodes present: {sorted(node_names & required)}")


def test_conditional_edge_logic():
    from workdiary_agent.graph import route_after_revise
    assert route_after_revise({"revision_count": 0}) == "polish"
    assert route_after_revise({"revision_count": 2}) == "polish"
    assert route_after_revise({"revision_count": 3}) == "polish"
    assert route_after_revise({"revision_count": 4}) == "polish"
    assert route_after_revise({}) == "polish"
    print("PASS: conditional edge logic correct")


def test_invoke_no_error():
    from workdiary_agent.graph import build_graph
    from workdiary_agent.state import StructuredInfo

    mock_llm = MagicMock()
    mock_response = MagicMock(content="【已选用技术型模板】\n完成测试")
    mock_llm.invoke.return_value = mock_response
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = StructuredInfo(
        tasks=["测试"], outputs=["结果"], blockers=[], progress="完成"
    )
    mock_llm.with_structured_output.return_value = mock_structured

    graph = build_graph()
    config = {"configurable": {"thread_id": "test-1"}}
    with patch("workdiary_agent.nodes.extract.make_llm", return_value=mock_llm), \
         patch("workdiary_agent.nodes.draft.make_llm", return_value=mock_llm), \
         patch("workdiary_agent.nodes.polish.make_llm", return_value=mock_llm), \
         patch("workdiary_agent.nodes.route_template.TemplateRouterAgent.classify", return_value="技术型"):
        result = graph.invoke({"raw_input": "test"}, config)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    print("PASS: invoke returns dict")


if __name__ == "__main__":
    failures = []
    for fn in [test_agent_state_fields, test_all_nodes_present,
               test_conditional_edge_logic, test_invoke_no_error]:
        try:
            fn()
        except Exception as e:
            failures.append(f"FAIL {fn.__name__}: {e}")
            print(f"FAIL: {fn.__name__}: {e}")

    if failures:
        print(f"\n{len(failures)} test(s) failed.")
        sys.exit(1)
    else:
        print("\nAll checks passed.")

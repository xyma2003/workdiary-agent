#!/usr/bin/env python
"""
Standalone smoke test for Phase 1 Graph Skeleton.
Verifies all 4 ROADMAP success criteria without pytest.
Run: conda run -n llm-data-pipeline python scripts/test_skeleton.py
"""
import sys
import typing


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
    assert route_after_revise({"revision_count": 0}) == "review"
    assert route_after_revise({"revision_count": 2}) == "review"
    assert route_after_revise({"revision_count": 3}) == "save"
    assert route_after_revise({"revision_count": 4}) == "save"
    assert route_after_revise({}) == "review"
    print("PASS: conditional edge logic correct")


def test_invoke_no_error():
    from workdiary_agent.graph import build_graph
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-1"}}
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

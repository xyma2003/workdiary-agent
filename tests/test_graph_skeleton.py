"""
Phase 1 — Graph Skeleton test suite.
Tests cover all 4 success criteria from ROADMAP.md §Phase 1.
Run: conda run -n llm-data-pipeline pytest tests/test_graph_skeleton.py -v
"""
import typing
import pytest

from workdiary_agent.graph import build_graph, route_after_revise
from workdiary_agent.state import AgentState


# ---------------------------------------------------------------------------
# SC-4 / AGENT-01: AgentState defines all required fields
# ---------------------------------------------------------------------------

def test_agent_state_fields():
    """AgentState TypedDict must define every field used downstream."""
    hints = typing.get_type_hints(AgentState)
    required_fields = {
        "raw_input",
        "structured_info",
        "template_type",
        "draft",
        "polished",
        "human_decision",
        "human_feedback",
        "revision_count",
        "git_log",
        "repo_path",
        "final_report",
        "export_path",
    }
    missing = required_fields - set(hints.keys())
    assert not missing, f"AgentState missing fields: {missing}"


# ---------------------------------------------------------------------------
# SC-2: All 8 node names present in the compiled graph
# ---------------------------------------------------------------------------

def test_all_nodes_present():
    """Graph must contain all 8 required node names."""
    graph = build_graph()
    node_names = set(graph.nodes.keys())
    required = {
        "extract",
        "enrich",
        "route_template",
        "draft",
        "polish",
        "review",
        "revise",
        "save",
    }
    missing = required - node_names
    assert not missing, f"Missing nodes: {missing}"


# ---------------------------------------------------------------------------
# SC-3: Conditional edge respects revision_count
# ---------------------------------------------------------------------------

def test_conditional_edge_logic():
    """route_after_revise must route to 'polish' unless revision_count >= 3.

    Phase 4 (D-06/D-07): destination changed from 'review' to 'polish' to support
    the revise→polish→review loop. Guard logic (count >= 3 → save) is unchanged.
    """
    # Under limit — routes to polish for another revision pass
    assert route_after_revise({"revision_count": 0}) == "polish"
    assert route_after_revise({"revision_count": 1}) == "polish"
    assert route_after_revise({"revision_count": 2}) == "polish"
    # At limit — force exit to save
    assert route_after_revise({"revision_count": 3}) == "save"
    # Over limit
    assert route_after_revise({"revision_count": 4}) == "save"
    # Unset key — total=False TypedDict, must default to 0 via .get()
    assert route_after_revise({}) == "polish"


# ---------------------------------------------------------------------------
# SC-1: graph.invoke() runs without error and returns a dict
# ---------------------------------------------------------------------------

def test_invoke_no_error():
    """graph.invoke({'raw_input': 'test'}, config) must return a dict."""
    graph = build_graph()
    config = {"configurable": {"thread_id": "test-1"}}
    result = graph.invoke({"raw_input": "test"}, config)
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"

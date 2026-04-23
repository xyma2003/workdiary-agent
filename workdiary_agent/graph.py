# workdiary_agent/graph.py
"""
Graph assembly stub. Plan 03 replaces this with the full StateGraph build.

This minimal stub exists so that test_graph_skeleton.py can be imported
for the test_agent_state_fields test (which only needs AgentState).
The other 3 tests (test_all_nodes_present, test_conditional_edge_logic,
test_invoke_no_error) will remain RED until Plan 03 completes this file.
"""
from __future__ import annotations

from .state import AgentState


def route_after_revise(state: AgentState) -> str:
    """Stub: Plan 03 implements conditional routing based on revision_count."""
    raise NotImplementedError("route_after_revise: implemented in Plan 03")


def build_graph():
    """Stub: Plan 03 assembles and compiles the full StateGraph."""
    raise NotImplementedError("build_graph: implemented in Plan 03")

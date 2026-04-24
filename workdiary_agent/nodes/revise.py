# workdiary_agent/nodes/revise.py
"""
Revise node: increments revision_count only.

Phase 4 design (D-08, D-09): human_feedback is already written to state by
review_node. revise_node does NOT re-write it — only increments the counter.
The graph then routes to polish_node (via route_after_revise in graph.py),
which reads human_feedback from state and appends it to the LLM prompt (D-10).

CRITICAL: use state.get("revision_count", 0) — never state["revision_count"].
AgentState uses total=False; bracket access on an unset key raises KeyError.
"""
from ..state import AgentState


def revise_node(state: AgentState) -> dict:
    """Increment revision_count. human_feedback already in state from review_node."""
    count = state.get("revision_count", 0)
    return {"revision_count": count + 1}

# workdiary_agent/nodes/revise.py
"""Revise node stub. Phase 4 applies human_feedback to re-polish the report."""
from ..state import AgentState


def revise_node(state: AgentState) -> dict:
    """Stub: increments revision_count. Phase 4 applies human_feedback to polished.

    CRITICAL: use state.get("revision_count", 0) — never state["revision_count"].
    AgentState uses total=False; bracket access on an unset key raises KeyError.
    """
    count = state.get("revision_count", 0)
    return {"revision_count": count + 1}

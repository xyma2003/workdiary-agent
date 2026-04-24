# workdiary_agent/nodes/save.py
"""
Save node: lightweight Phase 4 upgrade.

D-15: returns final_report = state.get("polished", "").
Phase 5 will add SQLite history write and markdown export — this node is the
correct place for that. For Phase 4, the only job is to make final_report
available in the graph result so the HITL approval cycle can be verified.

Note: history.db (Phase 5) and graph_state.db (LangGraph checkpointer) are
SEPARATE files. This node never touches graph_state.db.
"""
from ..state import AgentState


def save_node(state: AgentState) -> dict:
    """Write final_report from polished content. Phase 5 adds history.db write."""
    return {
        "final_report": state.get("polished", ""),
        "export_path": None,  # Phase 5 sets this
    }

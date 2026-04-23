# workdiary_agent/nodes/save.py
"""Save node stub. Phase 5 replaces this with SQLite history write + markdown export."""
from ..state import AgentState


def save_node(state: AgentState) -> dict:
    """Stub: Phase 5 writes to history.db and exports markdown file."""
    return {"final_report": state.get("polished", "[no polished content]"), "export_path": None}

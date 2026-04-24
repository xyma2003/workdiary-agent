# workdiary_agent/nodes/save.py
"""
Save node: persists completed report to history.db and exports markdown.

D-04: calls storage.save_report(state) to write to history.db
D-05: calls storage.save_markdown(polished, date) to write markdown file
D-07: sets export_path in returned state dict for Phase 6 UI

IMPORTANT: history.db (this node) and graph_state.db (LangGraph SqliteSaver)
are SEPARATE files. This node NEVER touches graph_state.db.
"""
import datetime
from ..state import AgentState
from ..storage import save_report, save_markdown


def save_node(state: AgentState) -> dict:
    """Persist final report to history.db and export as markdown.

    Returns updated state fields: final_report and export_path.
    """
    polished = state.get("polished", "") or ""
    today = datetime.date.today().isoformat()

    # D-04: write to history.db (never graph_state.db)
    save_report(state)

    # D-05, D-06: write exports/daily_report_{YYYY-MM-DD}.md
    export_path = save_markdown(polished, today)

    # D-07: export_path available to Phase 6 Streamlit UI
    return {
        "final_report": polished,
        "export_path": export_path,
    }

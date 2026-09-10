# workdiary_agent/nodes/save.py
"""
Save node: persists completed report to history.db and exports markdown.

D-04: calls storage.save_report(state) to write to history.db
D-05: calls storage.save_markdown(polished, date) to write markdown file
D-07: sets export_path in returned state dict for Phase 6 UI

IMPORTANT: history.db (this node) and graph_state.db (LangGraph SqliteSaver)
are SEPARATE files. This node NEVER touches graph_state.db.
"""
import uuid
from ..state import AgentState
from ..storage import save_report, save_markdown
from ..time_utils import work_date


def save_node(state: AgentState) -> dict:
    """Persist final report to history.db and export as markdown.

    Returns updated state fields: final_report and export_path.
    """
    # Idempotent guard — prevents duplicate saves if node executes more than once
    if state.get("_saved"):
        return {}

    # Prefer user-edited text over AI-generated polished version
    edited_text = state.get("edited_text")
    polished = edited_text if edited_text is not None else (state.get("polished", "") or "")
    report_date = state.get("date") or work_date(state.get("timezone"))
    report_id = state.get("report_id") or uuid.uuid4().hex

    # Use report_id in both destinations. SQLite's unique index makes a retry
    # idempotent, while the unique filename prevents same-day reports colliding.
    export_path = save_markdown(polished, report_date, report_id)
    save_report({
        **state,
        "report_id": report_id,
        "date": report_date,
        "polished": polished,
        "export_path": export_path,
    })

    # D-07: export_path available to Phase 6 Streamlit UI
    return {
        "final_report": polished,
        "export_path": export_path,
        "report_id": report_id,
        "_saved": True,
    }

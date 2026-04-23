# workdiary_agent/nodes/draft.py
"""Draft node stub. Phase 2 replaces this with LLM-based report drafting."""
from ..state import AgentState


def draft_node(state: AgentState) -> dict:
    """Stub: Phase 2 calls LLM to generate report draft from structured_info + template."""
    return {"draft": "[stub draft]"}

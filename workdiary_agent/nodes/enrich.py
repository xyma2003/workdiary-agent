# workdiary_agent/nodes/enrich.py
"""Enrich node stub. Phase 3 replaces this with GitPython commit reading."""
from ..state import AgentState


def enrich_node(state: AgentState) -> dict:
    """Stub: Phase 3 reads git commits from repo_path and fills git_log."""
    return {"git_log": None}

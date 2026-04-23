# workdiary_agent/nodes/review.py
"""
Review node stub.
Phase 4 replaces the body with interrupt() for Human-in-the-Loop pause.
Phase 1: stub that immediately sets human_decision to "revise" so the
revise->review loop exercises the revision_count guard.
"""
from ..state import AgentState


def review_node(state: AgentState) -> dict:
    """Stub: Phase 4 inserts interrupt() here for HITL pause.

    In Phase 1, always returns 'revise' so the loop exercises route_after_revise.
    The loop terminates when revision_count reaches 3 (guard in graph.py).
    """
    return {"human_decision": "revise", "human_feedback": None}

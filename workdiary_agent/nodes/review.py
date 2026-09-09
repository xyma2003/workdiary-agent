# workdiary_agent/nodes/review.py
"""
Review node: HITL pause using interrupt().

On first execution, interrupt() raises GraphInterrupt (a subclass of Exception),
persisting state to the checkpointer and returning the payload dict to the caller
as the '__interrupt__' key. The graph pauses here.

On resume (graph.invoke(Command(resume={...}), config) with the SAME thread_id),
interrupt() returns the dict from Command(resume=...). The node then writes
human_decision and human_feedback to state.

CRITICAL: interrupt() MUST NOT be wrapped in a bare except Exception block.
GraphInterrupt IS-A Exception (chain: GraphInterrupt → GraphBubbleUp → Exception).
A bare except Exception WILL silently swallow the interrupt, causing the graph
to run straight through without pausing. (Pitfall 1 in Phase 4 RESEARCH.md)
"""
from langgraph.types import interrupt
from ..graph_constants import MAX_REVISIONS
from ..state import AgentState


def review_node(state: AgentState) -> dict:
    """HITL pause: sends polished content to user, receives decision/feedback.

    Payload sent to caller contains polished text and current revision count
    so the UI (or test script) can display the content and track loop depth.
    D-02: response = interrupt({polished, revision_count})
    D-03: only "approve" and "revise" decisions are supported; malformed
    responses return to review and never save implicitly.
    """
    # interrupt() raises GraphInterrupt on first pass (graph pauses).
    # On resume, it returns the dict from Command(resume={...}).
    # DO NOT wrap in try/except — GraphInterrupt IS-A Exception and would be swallowed.
    response = interrupt({
        "polished": state.get("polished"),
        "revision_count": state.get("revision_count", 0),
        "max_revisions": MAX_REVISIONS,
        "remaining_revisions": max(
            0, MAX_REVISIONS - state.get("revision_count", 0)
        ),
    })
    if not isinstance(response, dict):
        response = {}
    revision_count = state.get("revision_count", 0)
    decision = response.get("decision", "review")
    feedback = response.get("feedback", "")
    edited_text = response.get("edited_text")
    # A malformed resume payload must never approve and persist content.
    if decision not in ("approve", "revise"):
        decision = "review"
    if decision == "revise" and revision_count >= MAX_REVISIONS:
        decision = "review"

    candidate_text = edited_text if isinstance(edited_text, str) else state.get("polished")
    if decision == "approve" and not (candidate_text or "").strip():
        decision = "review"

    feedback = feedback.strip() if isinstance(feedback, str) else ""
    feedback_history = list(state.get("feedback_history", []))
    if decision == "revise" and feedback:
        feedback_history.append(feedback)

    # Always write edited_text, including None/empty string, so an earlier edit
    # cannot leak into a later review cycle through LangGraph's merge semantics.
    result = {
        "human_decision": decision,
        "human_feedback": feedback,
        "feedback_history": feedback_history,
        "edited_text": edited_text if isinstance(edited_text, str) else None,
    }
    return result

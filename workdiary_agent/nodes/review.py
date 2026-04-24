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
from ..state import AgentState


def review_node(state: AgentState) -> dict:
    """HITL pause: sends polished content to user, receives decision/feedback.

    Payload sent to caller contains polished text and current revision count
    so the UI (or test script) can display the content and track loop depth.
    D-02: response = interrupt({polished, revision_count})
    D-03: only "approve" and "revise" decisions supported; others default to "approve".
    """
    # interrupt() raises GraphInterrupt on first pass (graph pauses).
    # On resume, it returns the dict from Command(resume={...}).
    # DO NOT wrap in try/except — GraphInterrupt IS-A Exception and would be swallowed.
    response = interrupt({
        "polished": state.get("polished"),
        "revision_count": state.get("revision_count", 0),
    })
    decision = response.get("decision", "approve")
    feedback = response.get("feedback", "")
    # D-03 + Claude's discretion: fallback for unrecognised decision values
    if decision not in ("approve", "revise"):
        decision = "approve"
    return {"human_decision": decision, "human_feedback": feedback}

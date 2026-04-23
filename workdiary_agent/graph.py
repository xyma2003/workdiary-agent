# workdiary_agent/graph.py
"""
StateGraph assembly for WorkDiary Agent.

This module owns the graph topology: add_node, add_edge, add_conditional_edges, compile.
Node implementations live in workdiary_agent/nodes/. State schema lives in workdiary_agent/state.py.

Phase evolution:
- Phase 1 (now): All nodes are stubs. review→revise is a direct edge. No interrupt.
- Phase 4: review node body gains interrupt(). This file's compile() call gains no new args
  (interrupt() inside a node does not require compile-time interrupt_before).
- Phase 4 also: InMemorySaver → SqliteSaver swap at the compile() call only.
"""
from __future__ import annotations

from typing import Literal

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from .state import AgentState
from .nodes import (
    extract_node,
    enrich_node,
    route_template_node,
    draft_node,
    polish_node,
    review_node,
    revise_node,
    save_node,
)


# ---------------------------------------------------------------------------
# Conditional edge routing function
# ---------------------------------------------------------------------------

def route_after_revise(state: AgentState) -> Literal["review", "save"]:
    """Routes to 'review' for another revision pass, or 'save' when limit is reached.

    Uses state.get() — NOT state[] — because AgentState uses total=False and
    revision_count may be unset on the first invocation. Unset defaults to 0.
    """
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "review"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph():
    """Build and compile the WorkDiary Agent StateGraph.

    Returns a compiled graph ready for graph.invoke() calls.
    Always pass config={"configurable": {"thread_id": "..."}} — required by InMemorySaver.
    """
    builder = StateGraph(AgentState)

    # --- Register nodes (string name decoupled from function name per Pattern 2) ---
    builder.add_node("extract", extract_node)
    builder.add_node("enrich", enrich_node)
    builder.add_node("route_template", route_template_node)
    builder.add_node("draft", draft_node)
    builder.add_node("polish", polish_node)
    builder.add_node("review", review_node)
    builder.add_node("revise", revise_node)
    builder.add_node("save", save_node)

    # --- Linear edges (Phase 1 topology) ---
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "enrich")
    builder.add_edge("enrich", "route_template")
    builder.add_edge("route_template", "draft")
    builder.add_edge("draft", "polish")
    builder.add_edge("polish", "review")

    # Phase 1: direct edge review→revise (Phase 4 replaces review node body with interrupt())
    builder.add_edge("review", "revise")

    # --- Conditional edge: revise loops back to review until revision_count >= 3 ---
    builder.add_conditional_edges(
        "revise",
        route_after_revise,
        {
            "review": "review",
            "save": "save",
        },
    )

    builder.add_edge("save", END)

    # --- Compile with checkpointer ---
    # InMemorySaver is canonical (MemorySaver is a backwards-compat alias at line 530).
    # Checkpointer is required from Phase 1: Phase 4's interrupt() needs it.
    # Phase 4 swap: replace InMemorySaver() with SqliteSaver.from_conn_string("graph_state.db")
    checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Module-level compiled graph (convenience import)
# ---------------------------------------------------------------------------

#: Pre-compiled graph for quick imports: `from workdiary_agent.graph import graph`
graph = build_graph()

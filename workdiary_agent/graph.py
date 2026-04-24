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
import sqlite3

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver

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
# Conditional edge routing functions
# ---------------------------------------------------------------------------

def route_after_review(state: AgentState) -> Literal["save", "revise"]:
    """Routes from review node based on human_decision written by review_node.

    Returns 'save' if decision is 'approve' (or missing), 'revise' otherwise.
    D-05: approve → save, revise → revise_node.
    """
    decision = state.get("human_decision", "approve")
    return "save" if decision == "approve" else "revise"


def route_after_revise(state: AgentState) -> Literal["polish", "save"]:
    """Routes to 'polish' for another revision pass, or 'save' when limit reached.

    UPDATED for Phase 4 (D-06+D-07): returns 'polish'|'save' (was 'review'|'save').
    Guard LOGIC unchanged: count >= 3 → save. Destination renamed because the
    revise→polish→review loop replaces the old revise→review loop.
    Uses state.get() — NOT state[] — because AgentState total=False.
    """
    count = state.get("revision_count", 0)
    return "save" if count >= 3 else "polish"


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph(use_sqlite: bool = False):
    """Build and compile the WorkDiary Agent StateGraph.

    Args:
        use_sqlite: If True, use SqliteSaver with graph_state.db for persistent
                    checkpointing. If False (default), use InMemorySaver — no disk
                    writes, suitable for unit tests. Production and scripts/test_hitl_cycle.py
                    should pass use_sqlite=True. Unit tests use the default False.

    IMPORTANT — SqliteSaver pattern (D-12/D-13):
        Use sqlite3.connect() + SqliteSaver(conn) directly.
        Do NOT use SqliteSaver.from_conn_string() without a 'with' block —
        that returns a _GeneratorContextManager, not a SqliteSaver,
        causing TypeError at builder.compile().
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

    # --- Linear edges ---
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "enrich")
    builder.add_edge("enrich", "route_template")
    builder.add_edge("route_template", "draft")
    builder.add_edge("draft", "polish")
    builder.add_edge("polish", "review")

    # D-04: deleted builder.add_edge("review", "revise")  — Phase 1 direct edge removed

    # D-05: conditional edge from review (approve→save, revise→revise_node)
    builder.add_conditional_edges(
        "review",
        route_after_review,
        {"save": "save", "revise": "revise"},
    )

    # D-06+D-07: single conditional edge — no separate add_edge("revise","polish") needed.
    # The guard logic (count>=3→save) is unchanged; destination "review" renamed to "polish".
    builder.add_conditional_edges(
        "revise",
        route_after_revise,
        {"polish": "polish", "save": "save"},
    )

    builder.add_edge("save", END)

    # --- Compile with checkpointer ---
    if use_sqlite:
        # Direct connection pattern — avoids from_conn_string() context manager issue.
        # from_conn_string() is a @contextmanager; without 'with' it returns
        # _GeneratorContextManager which fails at builder.compile(). (Pitfall 3)
        conn = sqlite3.connect("graph_state.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)
    else:
        checkpointer = InMemorySaver()
    return builder.compile(checkpointer=checkpointer)


# ---------------------------------------------------------------------------
# Module-level compiled graph (convenience import)
# ---------------------------------------------------------------------------

#: Pre-compiled graph for quick imports: `from workdiary_agent.graph import graph`
graph = build_graph()

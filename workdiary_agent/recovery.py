"""Helpers for discovering resumable LangGraph checkpoint threads."""

from __future__ import annotations

from typing import Any


def list_recoverable_runs(
    graph: Any,
    *,
    limit: int = 10,
    scan_limit: int | None = None,
) -> list[dict]:
    """Return the latest incomplete graph threads, newest first.

    LangGraph's checkpointer remains the only source of truth. Completed graphs
    have no ``next`` nodes and are intentionally excluded.
    """
    recoverable: list[dict] = []
    seen_thread_ids: set[str] = set()

    for checkpoint_tuple in graph.checkpointer.list(None, limit=scan_limit):
        configurable = checkpoint_tuple.config.get("configurable", {})
        thread_id = configurable.get("thread_id")
        if not thread_id or thread_id in seen_thread_ids:
            continue
        seen_thread_ids.add(thread_id)

        config = {"configurable": {"thread_id": thread_id}}
        snapshot = graph.get_state(config)
        values = dict(snapshot.values or {})
        if not snapshot.next or not values.get("raw_input"):
            continue

        checkpoint = checkpoint_tuple.checkpoint or {}
        recoverable.append({
            "thread_id": thread_id,
            "report_id": values.get("report_id"),
            "raw_input": values.get("raw_input", ""),
            "template_type": values.get("template_type"),
            "revision_count": values.get("revision_count", 0),
            "date": values.get("date"),
            "updated_at": checkpoint.get("ts", ""),
            "next_nodes": tuple(snapshot.next),
            "status": "reviewing" if "review" in snapshot.next else "retryable",
        })
        if len(recoverable) >= limit:
            break

    return recoverable

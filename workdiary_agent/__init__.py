# workdiary_agent/__init__.py
"""WorkDiary Agent — LangGraph-based intelligent work diary generator.

Quick start:
    from workdiary_agent.graph import build_graph
    graph = build_graph()
    result = graph.invoke({"raw_input": "今天完成了需求分析"}, {"configurable": {"thread_id": "1"}})
"""
from .graph import build_graph

__all__ = ["build_graph"]

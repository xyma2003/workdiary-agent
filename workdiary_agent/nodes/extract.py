# workdiary_agent/nodes/extract.py
"""Extract node stub. Phase 2 replaces this with LLM-based structured extraction."""
from ..state import AgentState


def extract_node(state: AgentState) -> dict:
    """Stub: Phase 2 calls llm.with_structured_output(StructuredInfo) to fill structured_info."""
    return {"structured_info": None}

# workdiary_agent/state.py
"""
AgentState TypedDict and supporting Pydantic models for WorkDiary Agent.

AgentState uses total=False — all fields are optional at runtime.
Callers must only supply raw_input. All other fields default to None or 0.

IMPORTANT: Use state.get("revision_count", 0) everywhere — never state["revision_count"].
With total=False TypedDict, bracket access on an unset key raises KeyError.
"""
from __future__ import annotations

from typing import Optional
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class StructuredInfo(BaseModel):
    """Structured extraction of user's work description.

    Phase 2 fills this via: llm.with_structured_output(StructuredInfo)
    """
    tasks: list[str] = Field(default_factory=list, description="Tasks worked on today")
    outputs: list[str] = Field(default_factory=list, description="Tangible outputs produced")
    blockers: list[str] = Field(default_factory=list, description="Blockers or issues encountered")
    progress: str = Field(default="", description="Overall progress summary")


class AgentState(TypedDict, total=False):
    """State schema for WorkDiary Agent StateGraph.

    total=False means all fields are optional (not required at invocation time).
    The only field callers must supply is raw_input.
    """

    # --- Input (required by caller) ---
    raw_input: str                       # User's raw work description (口语化)

    # --- Extraction (Phase 2: extract node) ---
    structured_info: Optional[StructuredInfo]

    # --- Template routing (Phase 2: route_template node) ---
    template_type: Optional[str]         # "技术型" | "业务型" | "混合型"

    # --- Draft generation (Phase 2: draft node) ---
    draft: Optional[str]

    # --- Polish (Phase 2: polish node) ---
    polished: Optional[str]

    # --- Human-in-the-loop (Phase 4: review node via interrupt()) ---
    human_decision: Optional[str]        # Literal["approve", "revise", "edit"]
    human_feedback: Optional[str]

    # --- Revision loop guard (Phase 1: revise node increments this) ---
    revision_count: int                  # Use state.get("revision_count", 0) — never bracket access

    # --- Enrichment (Phase 3: enrich node) ---
    git_log: Optional[str]
    repo_path: Optional[str]
    data_input: Optional[str]      # NEW (D-05): user's pasted numeric/tabular text
    data_summary: Optional[str]    # NEW (D-06): LLM-extracted key metrics from data_input

    # --- Final output (Phase 5: save node) ---
    final_report: Optional[str]
    export_path: Optional[str]

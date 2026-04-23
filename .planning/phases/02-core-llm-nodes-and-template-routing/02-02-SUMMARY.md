---
phase: 02-core-llm-nodes-and-template-routing
plan: 02
subsystem: llm
tags: [langchain-anthropic, ChatAnthropic, with_structured_output, langgraph, sub-graph, TypedDict, pydantic]

# Dependency graph
requires:
  - phase: 02-01
    provides: state.py StructuredInfo/AgentState schema, test_phase02_llm_nodes.py RED tests, node stubs

provides:
  - extract_node using ChatAnthropic.with_structured_output(StructuredInfo) for real LLM extraction
  - TemplateRouterAgent compiled sub-graph with analyze_content + decide_template nodes
  - route_template_node delegating to TemplateRouterAgent.classify()
  - workdiary_agent/router/ package (router/__init__.py + router/agent.py)

affects:
  - 02-03-draft-and-polish-nodes
  - 02-04-graph-integration
  - Phase 04 (HITL review flow uses template_type from route_template_node)
  - Phase 06 (Streamlit invokes the full graph with these nodes)

# Tech tracking
tech-stack:
  added:
    - langchain_anthropic.ChatAnthropic (with_structured_output for StructuredInfo)
    - langchain_core.messages.SystemMessage / HumanMessage
    - langgraph.graph.StateGraph (RouterState sub-graph compiled at module level)
  patterns:
    - state.get("key", default) pattern for total=False TypedDict (never bracket access)
    - Sub-graph compiled at module level (_router_graph = _builder.compile())
    - TemplateRouterAgent wrapper class over compiled sub-graph exposing classify()
    - Two-step classification pipeline: analyze_content -> decide_template
    - Fallback normalization in decide_template_node (invalid LLM output -> "混合型")

key-files:
  created:
    - workdiary_agent/router/__init__.py
    - workdiary_agent/router/agent.py
  modified:
    - workdiary_agent/nodes/extract.py
    - workdiary_agent/nodes/route_template.py

key-decisions:
  - "TemplateRouterAgent.classify() uses two-step pipeline (analyze then decide) for richer classification context"
  - "RouterState is independent TypedDict, not shared with AgentState — sub-graph isolation"
  - "Sub-graph compiled once at module level (_router_graph) for performance"
  - "Fallback to '混合型' when LLM returns unexpected text in decide_template_node"
  - "route_template_node builds structured_info summary string to enrich router context"

patterns-established:
  - "LangGraph sub-graph pattern: compile at module level, expose via wrapper class with typed method"
  - "Node always uses state.get() not state[] for total=False TypedDict fields"
  - "Claude model locked to claude-sonnet-4-5 per CLAUDE.md constraint"

requirements-completed: [AGENT-02, AGENT-05, TMPL-01, TMPL-02]

# Metrics
duration: 5min
completed: 2026-04-23
---

# Phase 02 Plan 02: Core LLM Nodes and Template Routing Summary

**ChatAnthropic with_structured_output(StructuredInfo) extract_node + TemplateRouterAgent compiled sub-graph (analyze_content -> decide_template) wired into route_template_node**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-23T08:33:13Z
- **Completed:** 2026-04-23T08:37:42Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Replaced extract_node stub with real ChatAnthropic.with_structured_output(StructuredInfo) call using Chinese system prompt
- Created workdiary_agent/router/ package with TemplateRouterAgent compiled LangGraph sub-graph
- Sub-graph topology: START -> analyze_content -> decide_template -> END, each node using ChatAnthropic
- Updated route_template_node to delegate to TemplateRouterAgent.classify() with enriched structured_info context

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement extract_node with real ChatAnthropic structured output** - `58c4ae2` (feat)
2. **Task 2: Create TemplateRouterAgent sub-graph and update route_template_node** - `3225d1b` (feat)

## Files Created/Modified
- `workdiary_agent/nodes/extract.py` - Replaced stub with ChatAnthropic.with_structured_output(StructuredInfo), Chinese system prompt for extraction
- `workdiary_agent/router/__init__.py` - New package init, exports TemplateRouterAgent
- `workdiary_agent/router/agent.py` - New file: RouterState TypedDict, analyze_content_node, decide_template_node, compiled sub-graph, TemplateRouterAgent wrapper class
- `workdiary_agent/nodes/route_template.py` - Replaced stub with TemplateRouterAgent().classify() delegation

## Decisions Made
- Two-step classification pipeline used (analyze_content -> decide_template) to provide richer context for the final classification decision — single-step would miss nuanced mixed content
- RouterState is independent TypedDict (not sharing AgentState) to maintain sub-graph isolation per LangGraph best practices
- Sub-graph compiled at module level for performance (avoid recompilation on each invocation)
- Fallback to "混合型" when LLM returns unexpected text to prevent invalid state propagation
- route_template_node builds a structured_info summary string when structured_info is available, giving router richer context

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all imports resolved cleanly, graph.py continued to build without modification.

## User Setup Required

None - no external service configuration required. Uses existing Anthropic API credentials from environment.

## Next Phase Readiness
- extract_node and route_template_node are production-ready LLM nodes
- TemplateRouterAgent accessible at workdiary_agent.router.agent.TemplateRouterAgent
- Ready for Phase 02-03: draft_node and polish_node implementation using template_type from state
- No blockers

---
*Phase: 02-core-llm-nodes-and-template-routing*
*Completed: 2026-04-23*

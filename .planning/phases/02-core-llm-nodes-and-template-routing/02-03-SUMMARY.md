---
phase: 02-core-llm-nodes-and-template-routing
plan: 03
subsystem: llm
tags: [langchain-anthropic, ChatAnthropic, template-routing, boss-perspective, TMPL-02, TMPL-03, D-09, D-10, AGENT-07]

# Dependency graph
requires:
  - phase: 02-02
    provides: "route_template_node setting template_type in state, AgentState schema with draft/polished fields"

provides:
  - "draft_node: 3-template LLM draft generation reading template_type from state (TMPL-02, TMPL-03)"
  - "polish_node: boss-perspective LLM refinement with goal verbs and quantification placeholder (AGENT-07, D-09, D-10)"

affects:
  - 02-04-graph-integration
  - Phase 04 (HITL review flow displays draft and polished outputs)
  - Phase 06 (Streamlit renders draft/polished outputs from state)

# Tech tracking
tech-stack:
  added:
    - "ANTHROPIC_CUSTOM_HEADERS env var parsing pattern for internal proxy auth"
  patterns:
    - "Template dispatch via _TEMPLATE_PROMPTS dict keyed on template_type"
    - "_make_llm() factory parsing ANTHROPIC_CUSTOM_HEADERS env var into default_headers"
    - "state.get('template_type', '混合型') — reads from state with sensible default, never hardcodes"
    - "Polish refines draft (state.get('draft')) — never regenerates from scratch (D-09)"

key-files:
  created: []
  modified:
    - workdiary_agent/nodes/draft.py
    - workdiary_agent/nodes/polish.py

key-decisions:
  - "_make_llm() factory added to parse ANTHROPIC_CUSTOM_HEADERS for internal proxy — ChatAnthropic does not read this env var automatically"
  - "Each template has dedicated system prompt constant (_TECH_SYSTEM, _BIZ_SYSTEM, _MIXED_SYSTEM) with hardcoded 【已选用XX模板】 first line"
  - "polish_node guards against empty/stub draft — returns early if draft is missing or '[stub draft]'"
  - "Default template_type fallback to '混合型' in draft_node when state key not set"

patterns-established:
  - "_make_llm() pattern: parse ANTHROPIC_CUSTOM_HEADERS newline-separated 'Key: Value' pairs into ChatAnthropic default_headers"
  - "Template prompt dispatch: _TEMPLATE_PROMPTS dict + dict.get(template_type, fallback) for extensible routing"
  - "System prompt mandates first-line format for TMPL-02 compliance: 【已选用XX模板】"

requirements-completed: [AGENT-06, AGENT-07, TMPL-01, TMPL-02, TMPL-03]

# Metrics
duration: 12min
completed: 2026-04-23
---

# Phase 02 Plan 03: Draft and Polish LLM Nodes Summary

**ChatAnthropic draft_node with 3-template dispatch (技术/业务/混合型) + boss-perspective polish_node with goal verbs and 未提供量化指标 placeholder**

## Performance

- **Duration:** 12 min
- **Started:** 2026-04-23T08:42:07Z
- **Completed:** 2026-04-23T08:54:27Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced draft_node stub with real LLM-backed 3-template dispatch; each template system prompt hardcodes 【已选用XX模板】 as first line (TMPL-02)
- draft_node reads template_type from state.get() — user override is honoured, no hardcoded default template except final fallback to 混合型 (TMPL-03)
- Replaced polish_node stub with ChatAnthropic refinement using boss-perspective system prompt; mandates goal verbs (完成/推进/对齐/输出/跟进) and 未提供量化指标 placeholder (AGENT-07, D-09, D-10)
- Added _make_llm() factory in both nodes to parse ANTHROPIC_CUSTOM_HEADERS env var and pass as default_headers — fixes 400 "Request is not allowed" on internal proxy

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement draft_node with 3-template system and TMPL-02 header** - `a548288` (feat)
2. **Task 2: Implement polish_node with boss-perspective refinement** - `83c07e2` (feat)

## Files Created/Modified
- `workdiary_agent/nodes/draft.py` - Replaced stub; _TECH_SYSTEM, _BIZ_SYSTEM, _MIXED_SYSTEM prompts; _TEMPLATE_PROMPTS dict; template_type from state; _make_llm() with header parsing
- `workdiary_agent/nodes/polish.py` - Replaced stub; _POLISH_SYSTEM with goal verbs + 未提供量化指标 requirement; refines draft not regenerates; _make_llm() with header parsing

## Decisions Made
- _make_llm() factory added to both nodes to parse ANTHROPIC_CUSTOM_HEADERS env var — ChatAnthropic does not automatically read this non-standard env var, causing 400 on internal corporate proxy
- Each of the 3 templates has a dedicated system prompt constant to keep template structures explicit and independently maintainable
- polish_node early-exits on empty/stub draft rather than sending empty content to LLM
- Default fallback to "混合型" in draft_node for resilience when template_type is missing from state

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ChatAnthropic missing custom proxy headers**
- **Found during:** Task 1 (draft_node implementation and test verification)
- **Issue:** `ChatAnthropic(model="claude-sonnet-4-5")` fails with 400 "Request is not allowed" on the internal proxy (`internal-proxy.example.com`). The proxy requires `X-Working-Dir` header from `ANTHROPIC_CUSTOM_HEADERS` env var, which ChatAnthropic does not read automatically.
- **Fix:** Added `_make_llm()` factory that parses `ANTHROPIC_CUSTOM_HEADERS` (newline-separated `Key: Value` pairs) and passes them as `default_headers` to ChatAnthropic. Applied same fix to polish_node.
- **Files modified:** `workdiary_agent/nodes/draft.py`, `workdiary_agent/nodes/polish.py`
- **Verification:** `test_draft_node_uses_template_type_from_state` and `test_polish_node_produces_boss_friendly_output` both pass
- **Committed in:** a548288 (Task 1 commit), 83c07e2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix for LLM calls to work on the project's corporate proxy. No scope creep. Same fix pattern should be backported to extract.py and route_template.py (logged in deferred-items).

## Issues Encountered
- `ANTHROPIC_CUSTOM_HEADERS` env var not automatically consumed by ChatAnthropic — required explicit parsing and passing as `default_headers`. This same bug exists in extract.py and route_template.py from plan 02-02 but is out of scope for this plan.

## User Setup Required
None - uses existing Anthropic API credentials from environment.

## Next Phase Readiness
- draft_node and polish_node are production-ready LLM nodes
- Both nodes handle all 3 template types with correct TMPL-02 headers
- Ready for Phase 02-04: graph integration wiring all nodes into the full StateGraph
- Deferred: extract.py and route_template.py also need _make_llm() fix (backport from this plan)

## Self-Check: PASSED

- FOUND: workdiary_agent/nodes/draft.py
- FOUND: workdiary_agent/nodes/polish.py
- FOUND: .planning/phases/02-core-llm-nodes-and-template-routing/02-03-SUMMARY.md
- FOUND: commit a548288 (feat: draft_node)
- FOUND: commit 83c07e2 (feat: polish_node)

---
*Phase: 02-core-llm-nodes-and-template-routing*
*Completed: 2026-04-23*

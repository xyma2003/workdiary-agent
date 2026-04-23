---
phase: 02-core-llm-nodes-and-template-routing
plan: 04
subsystem: testing
tags: [pytest, langchain-anthropic, proxy-headers, extract, router, draft, polish]

# Dependency graph
requires:
  - phase: 02-core-llm-nodes-and-template-routing
    provides: extract_node, TemplateRouterAgent, draft_node, polish_node implementations from plans 02 and 03
provides:
  - All 5 Phase 2 tests GREEN (test_phase02_llm_nodes.py)
  - All 4 Phase 1 tests still GREEN (test_graph_skeleton.py)
  - _make_llm() proxy-header factory added to extract.py and router/agent.py
affects: [03-human-in-the-loop, 04-git-tool, 05-persistence, 06-streamlit-ui]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_make_llm() factory with ANTHROPIC_CUSTOM_HEADERS: every LLM-calling module must use
      _make_llm() not bare ChatAnthropic() to ensure proxy headers are included"

key-files:
  created: []
  modified:
    - workdiary_agent/nodes/extract.py
    - workdiary_agent/router/agent.py

key-decisions:
  - "_make_llm() with ANTHROPIC_CUSTOM_HEADERS must be used in all LLM-calling modules —
    bare ChatAnthropic() without proxy headers causes 400 BadRequestError on Meituan proxy"

patterns-established:
  - "_make_llm() factory pattern: copy from draft.py/polish.py to any new LLM-calling module"

requirements-completed: [AGENT-02, AGENT-05, AGENT-06, AGENT-07, TMPL-01, TMPL-02, TMPL-03]

# Metrics
duration: 7min
completed: 2026-04-23
---

# Phase 02 Plan 04: Run Phase 2 Test Suite and Reach Human Verification Summary

**All 5 Phase 2 tests GREEN by adding _make_llm() proxy-header factory to extract_node and TemplateRouterAgent; 9/9 total tests passing**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-04-23T09:00:00Z
- **Completed:** 2026-04-23T09:07:00Z
- **Tasks:** 1 completed (Task 2 is checkpoint — awaiting human)
- **Files modified:** 2

## Accomplishments

- Fixed extract_node to use _make_llm() with proxy headers (was using bare ChatAnthropic, getting 400)
- Fixed TemplateRouterAgent analyze_content_node and decide_template_node to use _make_llm()
- All 5 Phase 2 tests pass: extract, router classify, route_template_node, draft, polish
- All 4 Phase 1 regression tests still pass (no regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Run Phase 2 test suite and verify all 5 tests pass (GREEN)** - `a077e6e` (fix)

**Plan metadata:** (pending — waiting for human checkpoint Task 2)

## Files Created/Modified

- `workdiary_agent/nodes/extract.py` - Added _make_llm() factory with ANTHROPIC_CUSTOM_HEADERS support; replaced bare ChatAnthropic() call
- `workdiary_agent/router/agent.py` - Added _make_llm() factory; replaced bare ChatAnthropic() in analyze_content_node and decide_template_node

## Decisions Made

- _make_llm() proxy-header pattern is now established as the mandatory pattern for all LLM-calling modules in this project. The Meituan internal proxy requires X-Working-Dir header which is not passed by bare ChatAnthropic(). This pattern was already present in draft.py and polish.py — extract.py and router/agent.py were simply missing it.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed missing proxy headers in extract_node and TemplateRouterAgent**
- **Found during:** Task 1 (Run Phase 2 test suite)
- **Issue:** extract_node used `ChatAnthropic(model="claude-sonnet-4-5")` without the ANTHROPIC_CUSTOM_HEADERS that the Meituan proxy requires (X-Working-Dir). Same issue in router/agent.py analyze_content_node and decide_template_node. Both caused `anthropic.BadRequestError: 400 Request is not allowed`.
- **Fix:** Added `_make_llm()` factory (identical pattern to draft.py and polish.py) to both files; replaced all bare `ChatAnthropic()` calls with `_make_llm()`.
- **Files modified:** workdiary_agent/nodes/extract.py, workdiary_agent/router/agent.py
- **Verification:** All 5 Phase 2 tests now pass (125s run time, real LLM calls)
- **Committed in:** a077e6e (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug — missing proxy headers)
**Impact on plan:** Required fix for correctness. No scope creep. Pattern was already established in draft.py/polish.py — just not propagated to extract.py and router/agent.py.

## Issues Encountered

- 3 of 5 Phase 2 tests failed on first run due to 400 BadRequestError from Meituan proxy — all resolved by adding _make_llm() factory.
- 2 of 5 tests (draft, polish) were already passing because those files already had _make_llm().

## Known Stubs

None — all nodes produce real LLM-generated output. No hardcoded placeholder values flowing to output.

## User Setup Required

None — no external service configuration required beyond existing ANTHROPIC_* env vars already set.

## Next Phase Readiness

- Phase 2 complete pending human verification of end-to-end pipeline quality (Task 2 checkpoint)
- Human must run the two integration test scripts (Test A + Test B) to verify: template_type, draft headers, polished output verbs/quantification, and template_type override
- Once approved, Phase 3 (human-in-the-loop) can begin

---
*Phase: 02-core-llm-nodes-and-template-routing*
*Completed: 2026-04-23*

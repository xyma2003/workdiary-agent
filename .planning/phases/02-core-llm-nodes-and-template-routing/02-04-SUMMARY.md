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

# Phase 02 Plan 04: Run Phase 2 Test Suite and Human Verification Summary

**All 5 Phase 2 tests GREEN, TMPL-03 user-override bug fixed (576f476), and end-to-end pipeline human-verified: template routing, boss-perspective polish, and quantification all confirmed**

## Performance

- **Duration:** ~20 min (including human review)
- **Started:** 2026-04-23T09:00:00Z
- **Completed:** 2026-04-23T09:20:00Z
- **Tasks:** 2 completed (1 auto + 1 human verify)
- **Files modified:** 3

## Accomplishments

- Fixed extract_node to use _make_llm() with proxy headers (was using bare ChatAnthropic, getting 400)
- Fixed TemplateRouterAgent analyze_content_node and decide_template_node to use _make_llm()
- All 5 Phase 2 tests pass: extract, router classify, route_template_node, draft, polish
- All 4 Phase 1 regression tests still pass (no regressions)
- Fixed TMPL-03 bug: route_template_node was overwriting user-set template_type; now respects pre-set override
- Human verified end-to-end pipeline: template selection visible, boss-perspective verbs present, quantification confirmed, user override respected

## Task Commits

Each task was committed atomically:

1. **Task 1: Run Phase 2 test suite and verify all 5 tests pass (GREEN)** - `a077e6e` (fix)
2. **[Post-task fix] TMPL-03 route_template_node must respect user-set template_type override** - `576f476` (fix)
3. **Task 2: Human confirms end-to-end pipeline quality** - (human checkpoint — approved)

**Plan metadata:** (see final commit)

## Files Created/Modified

- `workdiary_agent/nodes/extract.py` - Added _make_llm() factory with ANTHROPIC_CUSTOM_HEADERS support; replaced bare ChatAnthropic() call
- `workdiary_agent/router/agent.py` - Added _make_llm() factory; replaced bare ChatAnthropic() in analyze_content_node and decide_template_node
- `workdiary_agent/nodes/route_template.py` - Fixed TMPL-03 bug: guard clause added to skip LLM classification when template_type already set in state

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

**2. [Rule 1 - Bug] Fixed TMPL-03: route_template_node overwrote user-set template_type**
- **Found during:** Task 1 post-test / orchestrator review
- **Issue:** route_template_node called TemplateRouterAgent.classify() unconditionally, overwriting any template_type the user had pre-set in state. Test B (user override to 业务型 for technical input) was failing because LLM would re-classify as 技术型.
- **Fix:** Added guard clause: `if state.get("template_type"): return state` — skips LLM classification when template_type already set by user.
- **Files modified:** workdiary_agent/nodes/route_template.py
- **Verification:** Test B output shows 【已选用业务型模板】; human confirmed during checkpoint
- **Committed in:** 576f476 (post-task fix by orchestrator)

---

**Total deviations:** 2 auto-fixed (1 bug — missing proxy headers; 1 bug — TMPL-03 user override)
**Impact on plan:** Both required fixes for correctness. No scope creep. TMPL-03 was a stated requirement (plan frontmatter) that was silently broken until integration testing exposed it.

## Issues Encountered

- 3 of 5 Phase 2 tests failed on first run due to 400 BadRequestError from Meituan proxy — all resolved by adding _make_llm() factory.
- 2 of 5 tests (draft, polish) were already passing because those files already had _make_llm().

## Known Stubs

None — all nodes produce real LLM-generated output. No hardcoded placeholder values flowing to output.

## User Setup Required

None — no external service configuration required beyond existing ANTHROPIC_* env vars already set.

## Next Phase Readiness

- Phase 2 complete — all 7 requirements covered: AGENT-02, AGENT-05, AGENT-06, AGENT-07, TMPL-01, TMPL-02, TMPL-03
- Human-verified: template routing correct, boss-perspective polish confirmed, user override works
- All 9 tests passing (5 Phase 2 + 4 Phase 1), no regressions
- Ready for Phase 3 (Enrichment Tools — git log and numeric data ingestion)

## Self-Check: PASSED

- FOUND: workdiary_agent/nodes/extract.py
- FOUND: workdiary_agent/router/agent.py
- FOUND: workdiary_agent/nodes/route_template.py
- FOUND: .planning/phases/02-core-llm-nodes-and-template-routing/02-04-SUMMARY.md
- FOUND: commit a077e6e (fix: proxy headers in extract and router)
- FOUND: commit 576f476 (fix: TMPL-03 route_template_node user override)

---
*Phase: 02-core-llm-nodes-and-template-routing*
*Completed: 2026-04-23*

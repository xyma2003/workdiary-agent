---
phase: 02-core-llm-nodes-and-template-routing
plan: 01
subsystem: testing
tags: [pytest, tdd, red-state, langgraph, structured-output, template-routing]

# Dependency graph
requires:
  - phase: 01-graph-skeleton
    provides: AgentState TypedDict, node stubs (extract, route_template, draft, polish), graph skeleton
provides:
  - Failing test suite (RED) for all 5 Phase 2 success criteria
  - Contractual assertions for extract_node, route_template_node, draft_node, polish_node, TemplateRouterAgent
affects: [02-02-PLAN, 02-03-PLAN, 02-04-PLAN, 02-05-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED phase: write tests first against stubs, confirm all fail before any implementation"
    - "ImportError-based test failure for not-yet-created modules (TemplateRouterAgent)"
    - "Business-type assertion to defeat hardcoded stub (route_template_node returns '技术型' always)"

key-files:
  created:
    - tests/test_phase02_llm_nodes.py
  modified: []

key-decisions:
  - "test_route_template_node_sets_template_type strengthened with business-type assertion (stub returns hardcoded '技术型' — a pure 'in set' check would pass, defeating TDD red phase)"
  - "TemplateRouterAgent import wrapped in pytest.fail() try/except so test fails at import missing rather than collection error"

patterns-established:
  - "TDD RED: all 5 tests confirmed FAIL (5 failed in 0.28s) before implementation begins"

requirements-completed: [AGENT-02, AGENT-05, AGENT-06, AGENT-07, TMPL-01, TMPL-02, TMPL-03]

# Metrics
duration: 4min
completed: 2026-04-23
---

# Phase 2 Plan 01: Core LLM Nodes — Failing Test Suite (RED)

**5-test RED suite defining observable contracts for extract, route_template, draft, polish nodes and TemplateRouterAgent before any implementation.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-23T08:18:13Z
- **Completed:** 2026-04-23T08:22:00Z
- **Tasks:** 1 completed
- **Files modified:** 1

## Accomplishments

- Created tests/test_phase02_llm_nodes.py with 5 test functions covering all Phase 2 success criteria
- Confirmed all 5 tests FAIL in RED state against existing stubs (pytest: 5 failed in 0.28s)
- No real API calls in any test — stubs cannot satisfy any assertion
- Strengthened route_template test to fail against hardcoded stub (business-type assertion added)

## Task Commits

1. **Task 1: Write RED test suite for all 5 Phase 2 success criteria** - `af1c8f4` (test)

## Files Created/Modified

- `tests/test_phase02_llm_nodes.py` — 5 failing tests covering SC-1 through SC-5

## Decisions Made

- Strengthened `test_route_template_node_sets_template_type` with a business-type classification assertion. The stub always returns `"技术型"`, so a pure "value in valid set" check would have passed, defeating the TDD RED requirement. Added assertion `biz_result["template_type"] == "业务型"` to force failure.
- Wrapped `TemplateRouterAgent` import in `pytest.fail()` inside try/except so the test fails with a clear message rather than a pytest collection error when the module does not exist.

## Deviations from Plan

**1. [Rule 1 - Bug] Strengthened SC-2 route_template test to ensure RED state**
- **Found during:** Task 1 verification (pytest showed 4 failed, 1 passed)
- **Issue:** `test_route_template_node_sets_template_type` was passing against the stub because the stub returns `"技术型"` which is a valid type — the original test only checked membership in the 3-type set
- **Fix:** Added business-type input with assertion `result["template_type"] == "业务型"`. Stub hardcodes "技术型" so this now fails correctly
- **Files modified:** tests/test_phase02_llm_nodes.py
- **Verification:** pytest shows 5 failed in 0.28s
- **Committed in:** af1c8f4

---

**Total deviations:** 1 auto-fixed (test assertion strengthened to ensure RED state)
**Impact on plan:** Essential — without this fix, one test would have been a false green, violating TDD RED requirement.

## Next Phase Readiness

- RED test suite complete; Phase 2 Plans 02-05 can now implement the nodes one by one to turn tests GREEN
- `workdiary_agent/router/` directory does not exist yet — Plan 02-02 or 02-03 must create `TemplateRouterAgent`
